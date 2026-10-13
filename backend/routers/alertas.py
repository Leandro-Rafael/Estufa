"""
Router de Consulta e Histórico de Alertas.
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Alerta
from schemas import AlertaResponse
from services.alertas_service import obter_ultimos_alertas

router = APIRouter(prefix="/api/alertas", tags=["Alertas"])

@router.get("", response_model=List[AlertaResponse])
def get_alertas(
    limite: int = Query(50, ge=1, le=500, description="Número de alertas a retornar"),
    db: Session = Depends(get_db)
):
    """
    Retorna o histórico de alertas registrados no sistema, ordenados do mais recente ao mais antigo.
    """
    alertas = obter_ultimos_alertas(db, limite=limite)
    return alertas

@router.delete("/limpar")
def limpar_alertas(db: Session = Depends(get_db)):
    """Limpa o histórico de alertas no banco de dados."""
    total = db.query(Alerta).delete()
    db.commit()
    return {"sucesso": True, "alertas_removidos": total}
