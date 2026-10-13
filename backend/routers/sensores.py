"""
Router de Sensores e Leitura Atual.
Suporta leitura direta da memória RAM em tempo real com fallback para o SQLite.
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from services.leituras_service import obter_ultima_leitura, obter_todas_configuracoes
from services.alertas_service import processar_alertas_leitura
from schemas import LeituraInput, StatusMetricas
from serial_reader import serial_manager

router = APIRouter(prefix="/api/leituras", tags=["Sensores e Leituras"])

@router.get("/atual")
def get_leitura_atual(db: Session = Depends(get_db)):
    """
    Retorna a última leitura em tempo real da memória ou SQLite,
    com status visual ('ok', 'alerta', 'critico', 'offline').
    """
    leitura = obter_ultima_leitura(db)
    configs = obter_todas_configuracoes(db)

    if not leitura:
        return {
            "disponivel": False,
            "mensagem": "Nenhuma leitura registrada até o momento.",
            "hardware_conectado": serial_manager.conectado or serial_manager.em_simulacao,
            "status": {
                "temperatura": "offline",
                "umidade_ar": "offline",
                "umidade_solo": "offline",
                "luminosidade": "offline"
            }
        }

    if isinstance(leitura, dict):
        dt = datetime.fromisoformat(leitura["data_hora"]) if isinstance(leitura["data_hora"], str) else leitura["data_hora"]
        temp = leitura["temperatura"]
        uar = leitura["umidade_ar"]
        usolo = leitura["umidade_solo"]
        lum = leitura["luminosidade"]
        co2_val = leitura.get("co2")
        leitura_id = leitura.get("id", 1)
    else:
        dt = leitura.data_hora
        temp = leitura.temperatura
        uar = leitura.umidade_ar
        usolo = leitura.umidade_solo
        lum = leitura.luminosidade
        co2_val = leitura.co2
        leitura_id = leitura.id

    intervalo = configs.get("intervalo_leitura", 5)
    agora = datetime.utcnow()
    segundos_desde_ultima = (agora - dt).total_seconds()
    leitura_desatualizada = segundos_desde_ultima > (intervalo * 6)

    leitura_input = LeituraInput(
        temperatura=temp,
        umidade_ar=uar,
        umidade_solo=usolo,
        luminosidade=lum,
        co2=co2_val
    )

    if leitura_desatualizada and not (serial_manager.conectado or serial_manager.em_simulacao):
        status_calc = StatusMetricas(
            temperatura="offline",
            umidade_ar="offline",
            umidade_solo="offline",
            luminosidade="offline"
        )
        alertas = ["Sensor offline ou sem dados recentes recebidos"]
    else:
        status_calc, alertas = processar_alertas_leitura(db, leitura_input, configs)

    return {
        "disponivel": True,
        "id": leitura_id,
        "data_hora": dt.isoformat(),
        "segundos_atras": int(segundos_desde_ultima),
        "temperatura": temp,
        "umidade_ar": uar,
        "umidade_solo": usolo,
        "luminosidade": lum,
        "co2": co2_val,
        "status": status_calc.model_dump(),
        "alertas": alertas,
        "hardware_conectado": serial_manager.conectado or serial_manager.em_simulacao,
        "modo_simulacao": serial_manager.em_simulacao
    }
