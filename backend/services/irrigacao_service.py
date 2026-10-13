"""
Serviço de controle de irrigação (Manual e Automática) com proteções de segurança.
"""
from datetime import datetime, timedelta
import asyncio
from typing import Optional, Dict, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import SessionLocal
from models import Irrigacao

class IrrigacaoService:
    def __init__(self):
        self.irrigando: bool = False
        self.id_irrigacao_atual: Optional[int] = None
        self.modo_atual: str = "desativado" # "desativado", "manual", "automatico"
        self.data_inicio_atual: Optional[datetime] = None
        self.duracao_planejada_segundos: int = 0
        self.ultima_irrigacao_fim: Optional[datetime] = None
        self.umidade_solo_inicial: Optional[float] = None
        self.comando_serial_callback: Optional[Callable[[Dict[str, Any]], bool]] = None
        self._task_temporizador: Optional[asyncio.Task] = None

    def registrar_comando_hardware_callback(self, callback: Callable[[Dict[str, Any]], bool]):
        """Registra a função que envia comandos para o hardware (Serial / Wi-Fi / MQTT)."""
        self.comando_serial_callback = callback

    def obter_status(self, db: Session, configs: Dict[str, Any], umidade_solo_atual: Optional[float] = None) -> Dict[str, Any]:
        """Retorna o estado detalhado do sistema de irrigação."""
        agora = datetime.utcnow()
        tempo_restante = 0
        if self.irrigando and self.data_inicio_atual:
            decorrido = (agora - self.data_inicio_atual).total_seconds()
            tempo_restante = max(0, int(self.duracao_planejada_segundos - decorrido))

        cooldown_restante = 0
        intervalo_min = configs.get("intervalo_espera_irrigacao", 300)
        if self.ultima_irrigacao_fim:
            tempo_desde_ultima = (agora - self.ultima_irrigacao_fim).total_seconds()
            if tempo_desde_ultima < intervalo_min:
                cooldown_restante = int(intervalo_min - tempo_desde_ultima)

        modo = "automatico" if configs.get("irrigacao_automatica", False) else ("manual" if self.irrigando else "desativado")
        if self.irrigando:
            modo = self.modo_atual

        ultima_reg = db.query(Irrigacao).order_by(desc(Irrigacao.id)).first()
        ultima_data_str = ultima_reg.data_hora_inicio.isoformat() if ultima_reg and ultima_reg.data_hora_inicio else None

        return {
            "irrigando": self.irrigando,
            "modo": modo,
            "automatica_habilitada": configs.get("irrigacao_automatica", False),
            "tempo_restante_segundos": tempo_restante,
            "ultima_irrigacao": ultima_data_str,
            "bloqueado_por_cooldown": cooldown_restante > 0,
            "cooldown_restante_segundos": cooldown_restante,
            "umidade_solo_atual": umidade_solo_atual,
            "regras": {
                "irrigacao_solo_min": configs.get("irrigacao_solo_min", 35.0),
                "irrigacao_solo_max": configs.get("irrigacao_solo_max", 65.0),
                "tempo_max_irrigacao": configs.get("tempo_max_irrigacao", 20),
                "intervalo_espera_irrigacao": intervalo_min
            }
        }

    async def iniciar_irrigacao(
        self,
        db: Session,
        duracao_segundos: int,
        modo: str,
        motivo: str,
        umidade_solo_atual: Optional[float] = None
    ) -> bool:
        """Inicia acionamento de irrigação com registro no banco e envio ao hardware."""
        if self.irrigando:
            return False

        agora = datetime.utcnow()
        self.irrigando = True
        self.modo_atual = modo
        self.data_inicio_atual = agora
        self.duracao_planejada_segundos = duracao_segundos
        self.umidade_solo_inicial = umidade_solo_atual

        # Registra no banco
        registro = Irrigacao(
            data_hora_inicio=agora,
            duracao_segundos=duracao_segundos,
            modo=modo,
            motivo=motivo,
            umidade_solo_inicial=umidade_solo_atual,
            status="em_andamento"
        )
        db.add(registro)
        db.commit()
        db.refresh(registro)
        self.id_irrigacao_atual = registro.id

        # Envia comando ao hardware (Arduino por Serial ou futuramente ESP32 via HTTP/MQTT)
        if self.comando_serial_callback:
            comando = {
                "acao": "irrigar",
                "duracao": duracao_segundos
            }
            self.comando_serial_callback(comando)

        # Agenda temporizador de desligamento assíncrono para garantir proteção no backend
        loop = asyncio.get_event_loop()
        self._task_temporizador = loop.create_task(self._monitorar_fim_irrigacao(duracao_segundos))
        return True

    async def _monitorar_fim_irrigacao(self, segundos: int):
        """Espera a duração planejada e finaliza a irrigação se ainda estiver ativa."""
        try:
            await asyncio.sleep(segundos)
            if self.irrigando:
                await self.parar_irrigacao(motivo="Tempo planejado finalizado")
        except asyncio.CancelledError:
            pass

    async def parar_irrigacao(self, motivo: str = "Parada manual", umidade_solo_final: Optional[float] = None) -> bool:
        """Encerra a irrigação ativa e envia comando de desligamento."""
        if not self.irrigando:
            return False

        if self._task_temporizador and not self._task_temporizador.done():
            self._task_temporizador.cancel()

        agora = datetime.utcnow()
        self.irrigando = False
        self.ultima_irrigacao_fim = agora

        # Envia comando de parada para hardware
        if self.comando_serial_callback:
            self.comando_serial_callback({"acao": "parar_irrigacao"})

        # Atualiza registro no banco
        if self.id_irrigacao_atual:
            db = SessionLocal()
            try:
                reg = db.query(Irrigacao).filter(Irrigacao.id == self.id_irrigacao_atual).first()
                if reg:
                    reg.data_hora_fim = agora
                    decorrido = int((agora - reg.data_hora_inicio).total_seconds())
                    reg.duracao_segundos = decorrido
                    reg.umidade_solo_final = umidade_solo_final
                    reg.status = "concluido" if "finalizado" in motivo.lower() else "interrompido"
                    db.commit()
            finally:
                db.close()

        self.id_irrigacao_atual = None
        self.modo_atual = "desativado"
        return True

    async def avaliar_regras_automaticas(self, db: Session, configs: Dict[str, Any], umidade_solo_atual: float):
        """
        Executado a cada nova leitura recebida dos sensores.
        Verifica se deve disparar ou encerrar a irrigação automática.
        """
        irrigacao_auto = configs.get("irrigacao_automatica", False)
        limite_min = configs.get("irrigacao_solo_min", 35.0)
        limite_max = configs.get("irrigacao_solo_max", 65.0)
        tempo_max = configs.get("tempo_max_irrigacao", 20)
        intervalo_min = configs.get("intervalo_espera_irrigacao", 300)

        # Se já está irrigando e atingiu a umidade máxima do solo, desliga imediatamente
        if self.irrigando:
            if umidade_solo_atual >= limite_max:
                await self.parar_irrigacao(
                    motivo=f"Umidade do solo atingiu o nível desejado ({umidade_solo_atual}% >= {limite_max}%)",
                    umidade_solo_final=umidade_solo_atual
                )
            return

        # Se irrigação automática não está habilitada, nada a fazer
        if not irrigacao_auto:
            return

        # Verifica cooldown
        agora = datetime.utcnow()
        if self.ultima_irrigacao_fim:
            decorrido_cooldown = (agora - self.ultima_irrigacao_fim).total_seconds()
            if decorrido_cooldown < intervalo_min:
                return

        # Verifica se o solo está seco (abaixo do mínimo configurado)
        if umidade_solo_atual < limite_min:
            motivo = f"Umidade do solo ({umidade_solo_atual}%) abaixo do mínimo configurado ({limite_min}%)"
            await self.iniciar_irrigacao(
                db=db,
                duracao_segundos=tempo_max,
                modo="automatico",
                motivo=motivo,
                umidade_solo_atual=umidade_solo_atual
            )

irrigacao_service = IrrigacaoService()
