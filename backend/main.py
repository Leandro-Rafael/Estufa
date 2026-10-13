"""
Aplicação Principal FastAPI para Monitoramento e Controle de Estufa Inteligente.
"""
import os
import asyncio
from datetime import datetime
from typing import Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from database import engine, Base, SessionLocal
from schemas import LeituraInput, WebSocketMensagem, StatusMetricas
from services.leituras_service import (
    inicializar_configuracoes_padrao,
    obter_todas_configuracoes,
    salvar_leitura,
    obter_ultima_leitura,
    agregador_leituras
)
from services.alertas_service import processar_alertas_leitura
from services.irrigacao_service import irrigacao_service
from serial_reader import serial_manager

from routers import sensores, configuracoes, historico, alertas, irrigacao, dispositivo

# ----------------- Gerenciador de WebSockets -----------------

class ConexaoWebSocketManager:
    def __init__(self):
        self.conexoes_ativas: Set[WebSocket] = set()

    async def conectar(self, websocket: WebSocket):
        await websocket.accept()
        self.conexoes_ativas.add(websocket)

    def desconectar(self, websocket: WebSocket):
        self.conexoes_ativas.discard(websocket)

    async def broadcast(self, mensagem_dict: dict):
        """Envia mensagem serializada para todos os clientes conectados."""
        desconectados = set()
        for websocket in list(self.conexoes_ativas):
            try:
                await websocket.send_json(mensagem_dict)
            except Exception:
                desconectados.add(websocket)
        for ws in desconectados:
            self.conexoes_ativas.discard(ws)

ws_manager = ConexaoWebSocketManager()

# ----------------- Loop de Eventos Assíncronos -----------------

loop_principal: asyncio.AbstractEventLoop = None

def callback_nova_leitura_serial(leitura: LeituraInput):
    """
    Chamado a partir da thread serial quando uma leitura é recebida.
    Agenda a execução assíncrona no loop principal do FastAPI.
    """
    if loop_principal and loop_principal.is_running():
        asyncio.run_coroutine_threadsafe(_processar_leitura_assincrona(leitura), loop_principal)

async def _processar_leitura_assincrona(leitura: LeituraInput):
    """
    Salva no SQLite, avalia alertas, checa regras de irrigação e notifica WebSockets.
    """
    db = SessionLocal()
    try:
        # 1. Agrega amostras em memória e só grava no SQLite a cada 10 minutos (mínimo uso do banco)
        gravou, leitura_db = agregador_leituras.processar_leitura(db, leitura)
        agora_iso = datetime.utcnow().isoformat()

        # 2. Carrega configurações ativas
        configs = obter_todas_configuracoes(db)

        # 3. Processa conformidade e alertas (em tempo real)
        status_metricas, lista_alertas = processar_alertas_leitura(db, leitura, configs)

        # 4. Avalia regras de irrigação automática
        await irrigacao_service.avaliar_regras_automaticas(db, configs, leitura.umidade_solo)

        # 5. Prepara payload WebSocket (telemetria contínua instantânea para o frontend)
        payload = {
            "tipo": "leitura",
            "data_hora": agora_iso,
            "temperatura": leitura.temperatura,
            "umidade_ar": leitura.umidade_ar,
            "umidade_solo": leitura.umidade_solo,
            "luminosidade": leitura.luminosidade,
            "co2": leitura.co2,
            "status": status_metricas.model_dump(),
            "alertas": lista_alertas,
            "hardware_conectado": serial_manager.conectado or serial_manager.em_simulacao,
            "snapshot_gravado_banco": gravou
        }

        # 6. Broadcast em tempo real para todos os navegadores conectados
        await ws_manager.broadcast(payload)

    except Exception as e:
        print(f"[ERRO] Falha ao processar leitura: {e}")
    finally:
        db.close()

def callback_status_serial(conectado: bool, mensagem: str):
    """Notifica clientes WebSocket sobre mudança de status do hardware."""
    if loop_principal and loop_principal.is_running():
        msg = {
            "tipo": "status_dispositivo",
            "hardware_conectado": conectado,
            "mensagem": mensagem,
            "data_hora": datetime.utcnow().isoformat()
        }
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(msg), loop_principal)

def callback_log_serial(evento: dict):
    """Transmite eventos da telemetria serial em tempo real para o Console Web."""
    if loop_principal and loop_principal.is_running():
        msg = {
            "tipo": "log_serial",
            "evento": evento
        }
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(msg), loop_principal)

# ----------------- Ciclo de Vida da Aplicação -----------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop_principal
    loop_principal = asyncio.get_running_loop()

    # Cria tabelas no SQLite
    Base.metadata.create_all(bind=engine)

    # Popula configurações padrão se primeira execução
    db = SessionLocal()
    try:
        inicializar_configuracoes_padrao(db)
    finally:
        db.close()

    # Configura integrações do leitor serial e serviço de irrigação
    serial_manager.definir_callback_leitura(callback_nova_leitura_serial)
    serial_manager.definir_callback_status(callback_status_serial)
    serial_manager.definir_callback_log(callback_log_serial)
    irrigacao_service.registrar_comando_hardware_callback(serial_manager.enviar_comando)

    # Inicia a thread serial em background
    serial_manager.iniciar()

    yield

    # Encerra thread serial
    serial_manager.parar()

# ----------------- Instância FastAPI -----------------

app = FastAPI(
    title="Estufa Monitor & Control API",
    description="Sistema para monitoramento de sensores e controle de irrigação em tempo real.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS liberado para acesso local via celular ou IP de rede
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui os Routers da API
app.include_router(sensores.router)
app.include_router(configuracoes.router)
app.include_router(historico.router)
app.include_router(alertas.router)
app.include_router(irrigacao.router)
app.include_router(dispositivo.router)

# ----------------- WebSocket Endpoint -----------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.conectar(websocket)
    try:
        # Envia de imediato a última leitura ao conectar
        db = SessionLocal()
        try:
            from services.leituras_service import obter_ultima_leitura
            ultima = obter_ultima_leitura(db)
            configs = obter_todas_configuracoes(db)
            if ultima:
                t_val = ultima["temperatura"] if isinstance(ultima, dict) else ultima.temperatura
                u_val = ultima["umidade_ar"] if isinstance(ultima, dict) else ultima.umidade_ar
                s_val = ultima["umidade_solo"] if isinstance(ultima, dict) else ultima.umidade_solo
                l_val = ultima["luminosidade"] if isinstance(ultima, dict) else ultima.luminosidade
                c_val = ultima.get("co2") if isinstance(ultima, dict) else ultima.co2
                dt_str = ultima["data_hora"] if isinstance(ultima, dict) else ultima.data_hora.isoformat()

                status_calc, _ = processar_alertas_leitura(
                    db,
                    LeituraInput(
                        temperatura=t_val,
                        umidade_ar=u_val,
                        umidade_solo=s_val,
                        luminosidade=l_val,
                        co2=c_val
                    ),
                    configs
                )
                await websocket.send_json({
                    "tipo": "leitura",
                    "data_hora": dt_str,
                    "temperatura": t_val,
                    "umidade_ar": u_val,
                    "umidade_solo": s_val,
                    "luminosidade": l_val,
                    "co2": c_val,
                    "status": status_calc.model_dump(),
                    "alertas": [],
                    "hardware_conectado": serial_manager.conectado or serial_manager.em_simulacao
                })
        finally:
            db.close()

        # Mantém conexão viva aguardando mensagens ou ping
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.desconectar(websocket)
    except Exception:
        ws_manager.desconectar(websocket)

# ----------------- Arquivos Estáticos do Frontend -----------------

frontend_path = settings.FRONTEND_DIR
if os.path.exists(frontend_path):
    css_path = os.path.join(frontend_path, "css")
    js_path = os.path.join(frontend_path, "js")
    if os.path.exists(css_path):
        app.mount("/css", StaticFiles(directory=css_path), name="css")
    if os.path.exists(js_path):
        app.mount("/js", StaticFiles(directory=js_path), name="js")
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(frontend_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
