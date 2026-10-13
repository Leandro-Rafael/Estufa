"""
Router de Diagnóstico de Hardware, Seleção de Portas e Terminal Serial.
"""
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter
from schemas import DispositivoStatusResponse
from serial_reader import serial_manager

router = APIRouter(prefix="/api/dispositivo", tags=["Dispositivo / Hardware"])

class ConectarPortaRequest(BaseModel):
    porta: str = Field(..., description="Nome da porta serial (ex: COM3, /dev/ttyUSB0)")
    baudrate: int = Field(9600, description="Velocidade em bps")

class EnviarComandoRequest(BaseModel):
    comando: str = Field(..., description="String de comando raw ou JSON para a porta serial")

@router.get("/status", response_model=DispositivoStatusResponse)
def get_status_dispositivo():
    """Retorna status da porta serial, quantidade de leituras e estado de conexão."""
    return serial_manager.obter_status_dispositivo()

@router.post("/reconectar")
def reconectar_dispositivo():
    """Força tentativa imediata de reconexão à porta serial."""
    resultado = serial_manager.reconectar()
    return resultado

@router.post("/conectar")
def conectar_porta(dados: ConectarPortaRequest):
    """Permite selecionar e conectar a uma porta específica detectada pelo usuário."""
    resultado = serial_manager.trocar_porta_e_reconectar(dados.porta, dados.baudrate)
    return resultado

@router.get("/portas")
def listar_portas_seriais():
    """Lista todas as portas seriais detectadas com detalhes das placas conectadas."""
    portas = serial_manager.listar_portas_disponiveis()
    return {"portas_disponiveis": portas}

@router.get("/logs")
def obter_logs_telemetria():
    """Retorna os eventos recentes do buffer de telemetria serial (TX/RX)."""
    return {"logs": list(serial_manager.log_buffer)}

@router.post("/enviar_comando")
def enviar_comando_manual(dados: EnviarComandoRequest):
    """Permite que desenvolvedores e operadores enviem comandos diretos pela serial."""
    sucesso = serial_manager.enviar_comando_raw(dados.comando)
    return {"sucesso": sucesso, "comando_enviado": dados.comando}
