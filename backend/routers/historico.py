"""
Router de Histórico de Leituras com Filtros Flexíveis.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from services.leituras_service import obter_historico_leituras

router = APIRouter(prefix="/api/leituras", tags=["Histórico"])

@router.get("/historico")
def get_historico(
    inicio: Optional[datetime] = Query(None, description="Data/hora inicial ISO (ex: 2026-10-11T12:00:00)"),
    fim: Optional[datetime] = Query(None, description="Data/hora final ISO"),
    periodo: Optional[str] = Query(None, description="Período rápido: '1h', '6h', '24h', '7d'"),
    metrica: Optional[str] = Query(None, description="Filtrar métrica: 'temperatura', 'umidade_ar', 'umidade_solo', 'luminosidade'"),
    limite: int = Query(200, ge=10, le=2000, description="Quantidade máxima de pontos retornados"),
    db: Session = Depends(get_db)
):
    """
    Retorna série temporal de leituras para gráficos históricos e tabelas.
    """
    leituras = obter_historico_leituras(
        db=db,
        inicio=inicio,
        fim=fim,
        limite=limite,
        periodo=periodo
    )

    dados = []
    for l in leituras:
        item: Dict[str, Any] = {
            "id": l.id,
            "data_hora": l.data_hora.isoformat(),
        }
        if metrica:
            if hasattr(l, metrica):
                item[metrica] = getattr(l, metrica)
        else:
            item["temperatura"] = l.temperatura
            item["umidade_ar"] = l.umidade_ar
            item["umidade_solo"] = l.umidade_solo
            item["luminosidade"] = l.luminosidade
            item["co2"] = l.co2
        dados.append(item)

    return {
        "total": len(dados),
        "periodo_aplicado": periodo,
        "dados": dados
    }
