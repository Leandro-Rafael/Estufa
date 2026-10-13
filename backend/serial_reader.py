"""
Módulo de comunicação Serial com Arduino/ESP32.
Possui detecção inteligente de portas (Arduino/CH340/CP210x), troca dinâmica em tempo de execução,
buffer de telemetria serial em tempo real (RX/TX), reconexão assíncrona resiliente e modo simulação.
"""
import time
import json
import logging
import threading
import random
from collections import deque
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

from config import settings
from schemas import LeituraInput

logger = logging.getLogger("serial_reader")

class SerialManager:
    def __init__(self):
        self.porta: str = settings.SERIAL_PORT
        self.baudrate: int = settings.SERIAL_BAUDRATE
        self.serial_inst: Optional[Any] = None
        self.conectado: bool = False
        self.em_simulacao: bool = settings.SIMULATION_MODE
        self.rodando: bool = False
        self.thread: Optional[threading.Thread] = None

        # Buffer circular de logs em tempo real (últimos 100 eventos para o Console Web)
        self.log_buffer: deque = deque(maxlen=100)

        # Estatísticas
        self.total_leituras: int = 0
        self.erros_conexao: int = 0
        self.tempo_inicio: float = time.time()
        self.ultima_leitura_str: Optional[str] = None
        self.mensagem_status: str = "Inicializando..."
        self.dispositivo_identificado: str = "Desconhecido"

        # Callbacks
        self.on_leitura_callback: Optional[Callable[[LeituraInput], None]] = None
        self.on_status_change_callback: Optional[Callable[[bool, str], None]] = None
        self.on_serial_log_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # Valores base para o simulador realista
        self._sim_temp = 24.5
        self._sim_uar = 62.0
        self._sim_usolo = 55.0
        self._sim_lum = 650.0

    def definir_callback_leitura(self, callback: Callable[[LeituraInput], None]):
        self.on_leitura_callback = callback

    def definir_callback_status(self, callback: Callable[[bool, str], None]):
        self.on_status_change_callback = callback

    def definir_callback_log(self, callback: Callable[[Dict[str, Any]], None]):
        self.on_serial_log_callback = callback

    def registrar_log(self, direcao: str, conteudo: str):
        """Registra mensagem no buffer de telemetria e transmite para clientes Web."""
        evento = {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "direcao": direcao,  # RX, TX, INFO, ALERTA, ERRO
            "conteudo": conteudo
        }
        self.log_buffer.append(evento)
        if self.on_serial_log_callback:
            try:
                self.on_serial_log_callback(evento)
            except Exception:
                pass

    def listar_portas_disponiveis(self) -> List[Dict[str, Any]]:
        """Retorna lista rica de portas seriais detectadas com identificação de placas."""
        portas = []
        if serial and hasattr(serial.tools, 'list_ports'):
            for p in serial.tools.list_ports.comports():
                desc = p.description or ""
                desc_lower = desc.lower()
                is_arduino = any(k in desc_lower for k in ["arduino", "ch340", "cp210", "ftdi", "usb serial", "ch341", "ch9102"])
                portas.append({
                    "device": p.device,
                    "description": desc,
                    "hwid": p.hwid or "",
                    "is_probable_arduino": is_arduino
                })
        return portas

    def trocar_porta_e_reconectar(self, nova_porta: str, novo_baudrate: int = 9600) -> Dict[str, Any]:
        """Permite que o usuário troque a porta COM diretamente pelo site."""
        self.porta = nova_porta
        self.baudrate = novo_baudrate
        self.registrar_log("INFO", f"Configuração atualizada para porta {nova_porta} a {novo_baudrate} bps.")
        return self.reconectar()

    def iniciar(self):
        """Inicia a thread de monitoramento serial."""
        if self.rodando:
            return
        self.rodando = True
        self.thread = threading.Thread(target=self._loop_principal, daemon=True, name="SerialThread")
        self.thread.start()
        self.registrar_log("INFO", f"Monitor Serial iniciado (Porta alvo: {self.porta}, Baud: {self.baudrate})")

    def parar(self):
        """Para a thread e fecha a conexão."""
        self.rodando = False
        self._fechar_conexao()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.registrar_log("INFO", "Monitor Serial finalizado.")

    def reconectar(self) -> Dict[str, Any]:
        """Força o fechamento e nova tentativa imediata de conexão."""
        self._fechar_conexao()
        self._tentar_conectar()
        return {
            "conectado": self.conectado,
            "porta": self.porta,
            "modo_simulacao": self.em_simulacao,
            "mensagem": self.mensagem_status
        }

    def _fechar_conexao(self):
        if self.serial_inst:
            try:
                self.serial_inst.close()
            except Exception as e:
                logger.warning(f"Erro ao fechar porta serial: {e}")
            self.serial_inst = None
        if self.conectado:
            self.conectado = False
            self.registrar_log("INFO", f"Conexão com {self.porta} finalizada.")
            self._notificar_status(False, "Conexão serial fechada")

    def _tentar_conectar(self) -> bool:
        """Tenta abrir a porta serial física e detecta Arduino automaticamente se necessário."""
        if not serial:
            self.mensagem_status = "Biblioteca pyserial não disponível"
            self._ativar_simulacao_se_permitido("Pyserial ausente")
            return False

        porta_alvo = self.porta

        # Auto-detecção: se a porta configurada não estiver disponível, tenta achar um Arduino plugado
        portas_detectadas = self.listar_portas_disponiveis()
        nomes_portas = [p["device"] for p in portas_detectadas]

        if porta_alvo not in nomes_portas:
            # 1. Procura primeiro por placas com identificação explícita de microcontrolador
            provaveis = [p["device"] for p in portas_detectadas if p["is_probable_arduino"]]
            if provaveis:
                porta_alvo = provaveis[0]
                self.porta = porta_alvo
                self.registrar_log("INFO", f"Arduino detectado automaticamente na porta {porta_alvo}! Conectando...")
            else:
                # 2. Se não tiver nome óbvio, procura qualquer porta USB (evitando apenas COM1 de placa-mãe se houver outras)
                usb_portas = [p["device"] for p in portas_detectadas if p["device"].upper() != "COM1"]
                if usb_portas:
                    porta_alvo = usb_portas[0]
                    self.porta = porta_alvo
                    self.registrar_log("INFO", f"Dispositivo Serial USB detectado em {porta_alvo}. Conectando...")
                elif nomes_portas:
                    porta_alvo = nomes_portas[0]
                    self.porta = porta_alvo
                    self.registrar_log("INFO", f"Tentando única porta disponível: {porta_alvo}")

        try:
            self.serial_inst = serial.Serial(
                port=porta_alvo,
                baudrate=self.baudrate,
                timeout=settings.SERIAL_TIMEOUT
            )
            # Limpa buffers
            self.serial_inst.reset_input_buffer()
            self.serial_inst.reset_output_buffer()
            time.sleep(1.8)  # Tempo para reset DTR típico do bootloader do Arduino

            self.conectado = True
            self.em_simulacao = False
            self.dispositivo_identificado = f"{porta_alvo} ({self.baudrate} baud)"
            self.mensagem_status = f"Conectado com sucesso ao hardware em {porta_alvo}"
            self.registrar_log("INFO", f"LINK ESTABELECIDO -> {porta_alvo} @ {self.baudrate}bps")
            self._notificar_status(True, self.mensagem_status)
            return True
        except Exception as e:
            self.erros_conexao += 1
            self.conectado = False
            self.mensagem_status = f"Falha ao conectar em {porta_alvo}: {str(e)}"
            self.registrar_log("ERRO", f"Falha de conexão em {porta_alvo}: {str(e)}")
            self._ativar_simulacao_se_permitido(str(e))
            return False

    def _ativar_simulacao_se_permitido(self, motivo: str):
        if settings.SIMULATION_MODE or settings.AUTO_FALLBACK_SIMULATION:
            if not self.em_simulacao:
                self.registrar_log("ALERTA", f"Hardware offline ({motivo}). Ativando telemetria virtual (Simulação).")
            self.em_simulacao = True
            self.mensagem_status = f"Modo Simulação Ativo (Serial {self.porta} desconectada)"
            self._notificar_status(True, self.mensagem_status)

    def _notificar_status(self, conectado: bool, msg: str):
        if self.on_status_change_callback:
            try:
                self.on_status_change_callback(conectado, msg)
            except Exception as e:
                logger.error(f"Erro no callback de status: {e}")

    def enviar_comando(self, comando_dict: Dict[str, Any]) -> bool:
        """Envia comando JSON para o Arduino e registra telemetria TX."""
        payload = json.dumps(comando_dict) + "\n"
        self.registrar_log("TX", payload.strip())

        if self.conectado and self.serial_inst and self.serial_inst.is_open:
            try:
                self.serial_inst.write(payload.encode("utf-8"))
                self.serial_inst.flush()
                return True
            except Exception as e:
                self.registrar_log("ERRO", f"Erro no envio TX: {e}")
                self._fechar_conexao()
                return False
        elif self.em_simulacao:
            # Em simulação, simula efeito de comando (ex: se acionar bomba, umidade sobe)
            if comando_dict.get("acao") == "irrigar":
                self._irrigando_simulado = True
            elif comando_dict.get("acao") == "parar_irrigacao":
                self._irrigando_simulado = False
            return True
        else:
            self.registrar_log("ERRO", "Tentativa de envio TX sem conexão serial ativa.")
            return False

    def enviar_comando_raw(self, linha: str) -> bool:
        """Permite envio de comandos arbitrários pelo terminal serial do frontend."""
        cmd = linha.strip() + "\n"
        self.registrar_log("TX", linha.strip())
        if self.conectado and self.serial_inst and self.serial_inst.is_open:
            try:
                self.serial_inst.write(cmd.encode("utf-8"))
                self.serial_inst.flush()
                return True
            except Exception as e:
                self.registrar_log("ERRO", f"Falha no envio RAW: {e}")
                return False
        return False

    def _loop_principal(self):
        """Thread worker contínua com auto-reconexão resiliente e buffer seguro."""
        while self.rodando:
            if not self.conectado and not self.em_simulacao:
                self._tentar_conectar()
                if not self.conectado and not self.em_simulacao:
                    time.sleep(settings.SERIAL_RECONNECT_INTERVAL)
                    continue

            # Modo Físico Real
            if self.conectado and self.serial_inst:
                try:
                    if self.serial_inst.in_waiting > 0:
                        raw_line = self.serial_inst.readline()
                        linha = raw_line.decode("utf-8", errors="replace").strip()
                        if linha:
                            self.registrar_log("RX", linha)
                            self._processar_linha(linha)
                    else:
                        time.sleep(0.04)
                except (serial.SerialException, OSError) as e:
                    self.registrar_log("ERRO", f"Comunicação serial interrompida: {e}")
                    self._fechar_conexao()
                    self._ativar_simulacao_se_permitido(str(e))
                except Exception as e:
                    logger.error(f"Erro inesperado no loop serial: {e}")
                    time.sleep(0.5)

            # Modo Simulação
            elif self.em_simulacao:
                self._gerar_leitura_simulada()
                # A cada ciclo tenta detectar se o Arduino foi conectado
                if not settings.SIMULATION_MODE and (self.total_leituras % 4 == 0):
                    if self._tentar_conectar():
                        continue
                time.sleep(3.0)

    def _processar_linha(self, linha: str):
        """Valida e converte o JSON recebido da serial."""
        if not (linha.startswith("{") and linha.endswith("}")):
            return  # Ignora logs ou mensagens não-JSON do firmware
        try:
            dados_dict = json.loads(linha)
            # Confere se contém as chaves esperadas de leitura
            if "temperatura" in dados_dict:
                leitura = LeituraInput(**dados_dict)
                self.total_leituras += 1
                self.ultima_leitura_str = datetime.utcnow().isoformat()
                if self.em_simulacao:
                    self.em_simulacao = False
                    self.registrar_log("INFO", f"DADOS REAIS CAPTADOS DO ARDUINO ({self.porta})! Modo simulação desativado.")
                    self._notificar_status(True, f"Arduino físico ativo em {self.porta}")
                if self.on_leitura_callback:
                    self.on_leitura_callback(leitura)
            elif "status" in dados_dict or "ack" in dados_dict:
                self.registrar_log("INFO", f"ACK Arduino: {dados_dict}")
        except json.JSONDecodeError:
            pass
        except Exception as e:
            self.registrar_log("ALERTA", f"Validação ignorada: {e}")

    def _gerar_leitura_simulada(self):
        """Gera oscilações sutis realistas para testes completos."""
        self._sim_temp += random.uniform(-0.2, 0.2)
        self._sim_temp = round(max(18.0, min(36.0, self._sim_temp)), 1)

        self._sim_uar += random.uniform(-0.6, 0.6)
        self._sim_uar = round(max(35.0, min(85.0, self._sim_uar)), 1)

        if not getattr(self, "_irrigando_simulado", False):
            self._sim_usolo -= random.uniform(0.04, 0.15)
        else:
            self._sim_usolo += random.uniform(2.5, 4.5)
        self._sim_usolo = round(max(20.0, min(85.0, self._sim_usolo)), 1)

        self._sim_lum += random.uniform(-10.0, 10.0)
        self._sim_lum = round(max(150.0, min(950.0, self._sim_lum)), 1)

        leitura = LeituraInput(
            temperatura=self._sim_temp,
            umidade_ar=self._sim_uar,
            umidade_solo=self._sim_usolo,
            luminosidade=self._sim_lum,
            co2=round(random.uniform(410, 580), 1)
        )
        self.total_leituras += 1
        self.ultima_leitura_str = datetime.utcnow().isoformat()
        self.registrar_log("RX [SIM]", json.dumps(leitura.model_dump()))
        if self.on_leitura_callback:
            try:
                self.on_leitura_callback(leitura)
            except Exception as e:
                logger.error(f"Erro no despacho simulado: {e}")

    def obter_status_dispositivo(self) -> Dict[str, Any]:
        """Retorna diagnóstico completo do dispositivo para API REST."""
        return {
            "conectado": self.conectado or self.em_simulacao,
            "porta": self.porta,
            "baudrate": self.baudrate,
            "modo_simulacao": self.em_simulacao,
            "ultima_leitura_recebida": self.ultima_leitura_str,
            "total_leituras_recebidas": self.total_leituras,
            "erros_conexao": self.erros_conexao,
            "tempo_ativo_segundos": round(time.time() - self.tempo_inicio, 1),
            "mensagem_status": self.mensagem_status
        }

serial_manager = SerialManager()
