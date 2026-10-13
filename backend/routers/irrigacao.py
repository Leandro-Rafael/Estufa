"""
Router de Controle e Monitoramento da Irrigação.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import Irrigacao
from schemas import (
    IrrigacaoManualRequest,
    IrrigacaoStatusResponse,
    IrrigacaoResponse,
    ConfiguracoesUpdate,
    ConfiguracoesPayload
)
from services.irrigacao_service import irrigacao_service
from services.leituras_service import (
    obter_todas_configuracoes,
    salvar_configuracoes,
    obter_ultima_leitura
)

router = APIRouter(prefix="/api/irrigacao", tags=["Irrigação"])

@router.get("/status", response_model=IrrigacaoStatusResponse)
def get_status_irrigacao(db: Session = Depends(get_db)):
    """Retorna o status atual da irrigação (ativo, modo, cooldown, regras)."""
    configs = obter_todas_configuracoes(db)
    ultima_leitura = obter_ultima_leitura(db)
    umidade_solo = ultima_leitura.umidade_solo if ultima_leitura else None
    status = irrigacao_service.obter_status(db, configs, umidade_solo)
    return status

@router.post("/manual")
async def acionar_irrigacao_manual(dados: IrrigacaoManualRequest, db: Session = Depends(get_db)):
    """
    Aciona a irrigação no modo manual por um tempo determinado em segundos.
    """
    if irrigacao_service.irrigando:
        raise HTTPException(status_code=400, detail="A irrigação já está em andamento.")

    configs = obter_todas_configuracoes(db)
    ultima_leitura = obter_ultima_leitura(db)
    umidade_solo = ultima_leitura.umidade_solo if ultima_leitura else None

    # Respeita o teto máximo de segurança configurado
    tempo_max = configs.get("tempo_max_irrigacao", 20)
    duracao = min(dados.duracao_segundos, tempo_max)

    sucesso = await irrigacao_service.iniciar_irrigacao(
        db=db,
        duracao_segundos=duracao,
        modo="manual",
        motivo="Acionamento manual solicitado pelo usuário via painel web",
        umidade_solo_atual=umidade_solo
    )

    if not sucesso:
        raise HTTPException(status_code=500, detail="Falha ao iniciar comando de irrigação.")

    return {
        "sucesso": True,
        "mensagem": f"Irrigação manual iniciada com duração de {duracao} segundos.",
        "duracao_segundos": duracao
    }

@router.post("/parar")
async def parar_irrigacao(db: Session = Depends(get_db)):
    """Interrompe imediatamente qualquer irrigação em andamento."""
    if not irrigacao_service.irrigando:
        return {"sucesso": True, "mensagem": "A irrigação já estava desligada."}

    ultima_leitura = obter_ultima_leitura(db)
    umidade_solo = ultima_leitura.umidade_solo if ultima_leitura else None

    sucesso = await irrigacao_service.parar_irrigacao(
        motivo="Interrupção manual solicitada pelo usuário",
        umidade_solo_final=umidade_solo
    )

    return {"sucesso": sucesso, "mensagem": "Comando de parada de irrigação executado."}

@router.put("/configuracoes", response_model=ConfiguracoesPayload)
def update_irrigacao_config(dados: ConfiguracoesUpdate, db: Session = Depends(get_db)):
    """Atualiza especificamente os parâmetros e regras de irrigação."""
    dados_dict = dados.model_dump(exclude_unset=True)
    novas_configs = salvar_configuracoes(db, dados_dict)
    return ConfiguracoesPayload(**novas_configs)

@router.get("/historico", response_model=List[IrrigacaoResponse])
def get_historico_irrigacao(
    limite: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Retorna o histórico dos acionamentos de irrigação."""
    registros = db.query(Irrigacao).order_by(desc(Irrigacao.id)).limit(limite).all()
    return registros
