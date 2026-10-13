"""
Router de Gerenciamento das Configurações do Sistema.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import ConfiguracoesUpdate, ConfiguracoesPayload
from services.leituras_service import obter_todas_configuracoes, salvar_configuracoes
from serial_reader import serial_manager

router = APIRouter(prefix="/api/configuracoes", tags=["Configurações"])

@router.get("", response_model=ConfiguracoesPayload)
def get_configuracoes(db: Session = Depends(get_db)):
    """Retorna todas as configurações ativas no sistema."""
    configs = obter_todas_configuracoes(db)
    return ConfiguracoesPayload(**configs)

@router.put("", response_model=ConfiguracoesPayload)
def update_configuracoes(dados: ConfiguracoesUpdate, db: Session = Depends(get_db)):
    """
    Atualiza as configurações do sistema no banco SQLite.
    Persiste mesmo após reiniciar o servidor ou o Arduino.
    """
    dados_dict = dados.model_dump(exclude_unset=True)
    novas_configs = salvar_configuracoes(db, dados_dict)

    # Se o intervalo de leitura mudou, notifica o hardware se conectado
    if "intervalo_leitura" in dados_dict:
        serial_manager.enviar_comando({
            "acao": "set_intervalo",
            "valor": dados_dict["intervalo_leitura"]
        })

    return ConfiguracoesPayload(**novas_configs)
