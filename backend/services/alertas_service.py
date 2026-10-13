"""
Serviço de análise de limites, tolerâncias e geração de alertas para a estufa.
"""
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import Alerta
from schemas import LeituraInput, StatusMetricas

# Controle em memória para evitar flooding/spam contínuo de alertas idênticos no banco
_ultimo_alerta_por_metrica: Dict[str, datetime] = {}
COOLDOWN_REPETICAO_ALERTA_SEGUNDOS = 60

def avaliar_metrica(
    valor: float,
    min_ideal: float,
    max_ideal: float,
    tolerancia: float
) -> Tuple[str, Optional[str]]:
    """
    Avalia o valor de uma métrica em relação à faixa ideal e tolerância.
    Retorna: (status, motivo_se_alerta)
    Status:
      - 'ok': Dentro de [min_ideal, max_ideal] (Verde)
      - 'alerta': Próximo ao limite (Amarelo)
      - 'critico': Fora da tolerância (Vermelho)
    """
    if valor < min_ideal - tolerancia:
        return "critico", f"abaixo do limite crítico ({valor} < {min_ideal - tolerancia})"
    elif valor < min_ideal:
        return "alerta", f"próximo do limite mínimo ({valor} < {min_ideal})"
    elif valor > max_ideal + tolerancia:
        return "critico", f"acima do limite crítico ({valor} > {max_ideal + tolerancia})"
    elif valor > max_ideal:
        return "alerta", f"próximo do limite máximo ({valor} > {max_ideal})"
    else:
        return "ok", None

def processar_alertas_leitura(
    db: Session,
    leitura: LeituraInput,
    configs: Dict[str, Any]
) -> Tuple[StatusMetricas, List[str]]:
    """
    Analisa a leitura em relação às configurações ativas,
    determina os status visuais e persiste novos alertas no banco se necessário.
    """
    alertas_ativos = configs.get("alertas_ativos", True)
    
    # 1. Temperatura
    status_temp, motivo_temp = avaliar_metrica(
        leitura.temperatura,
        configs.get("temperatura_min", 20.0),
        configs.get("temperatura_max", 28.0),
        configs.get("tolerancia_temperatura", 2.0)
    )

    # 2. Umidade do Ar
    status_uar, motivo_uar = avaliar_metrica(
        leitura.umidade_ar,
        configs.get("umidade_ar_min", 50.0),
        configs.get("umidade_ar_max", 70.0),
        configs.get("tolerancia_umidade_ar", 5.0)
    )

    # 3. Umidade do Solo
    status_usolo, motivo_usolo = avaliar_metrica(
        leitura.umidade_solo,
        configs.get("umidade_solo_min", 40.0),
        configs.get("umidade_solo_max", 70.0),
        configs.get("tolerancia_umidade_solo", 5.0)
    )

    # 4. Luminosidade
    status_lum, motivo_lum = avaliar_metrica(
        leitura.luminosidade,
        configs.get("luminosidade_min", 400.0),
        configs.get("luminosidade_max", 850.0),
        configs.get("tolerancia_luminosidade", 50.0)
    )

    status_geral = StatusMetricas(
        temperatura=status_temp,
        umidade_ar=status_uar,
        umidade_solo=status_usolo,
        luminosidade=status_lum
    )

    mensagens_alertas: List[str] = []
    agora = datetime.utcnow()

    # Mapeamento para persistência
    metricas_info = [
        ("temperatura", leitura.temperatura, status_temp, motivo_temp,
         f"Ideal: {configs.get('temperatura_min')}°C a {configs.get('temperatura_max')}°C (Tol: ±{configs.get('tolerancia_temperatura')}°C)",
         "Temperatura"),
        ("umidade_ar", leitura.umidade_ar, status_uar, motivo_uar,
         f"Ideal: {configs.get('umidade_ar_min')}% a {configs.get('umidade_ar_max')}% (Tol: ±{configs.get('tolerancia_umidade_ar')}%)",
         "Umidade do ar"),
        ("umidade_solo", leitura.umidade_solo, status_usolo, motivo_usolo,
         f"Ideal: {configs.get('umidade_solo_min')}% a {configs.get('umidade_solo_max')}% (Tol: ±{configs.get('tolerancia_umidade_solo')}%)",
         "Umidade do solo"),
        ("luminosidade", leitura.luminosidade, status_lum, motivo_lum,
         f"Ideal: {configs.get('luminosidade_min')} a {configs.get('luminosidade_max')} (Tol: ±{configs.get('tolerancia_luminosidade')})",
         "Luminosidade")
    ]

    for chave_metrica, val, status_met, motivo, cfg_str, nome_legivel in metricas_info:
        if status_met in ("alerta", "critico"):
            texto_alerta = f"{nome_legivel} {motivo}"
            mensagens_alertas.append(texto_alerta)

            # Persiste no banco se alertas estiverem habilitados e respeitando cooldown
            if alertas_ativos:
                ultimo_envio = _ultimo_alerta_por_metrica.get(chave_metrica)
                if not ultimo_envio or (agora - ultimo_envio).total_seconds() >= COOLDOWN_REPETICAO_ALERTA_SEGUNDOS:
                    alerta_db = Alerta(
                        data_hora=agora,
                        metrica=chave_metrica,
                        valor=val,
                        mensagem=texto_alerta,
                        nivel=status_met,
                        configuracao_usada=cfg_str
                    )
                    db.add(alerta_db)
                    _ultimo_alerta_por_metrica[chave_metrica] = agora

    if alertas_ativos and mensagens_alertas:
        db.commit()

    return status_geral, mensagens_alertas

def obter_ultimos_alertas(db: Session, limite: int = 50) -> List[Alerta]:
    """Retorna os alertas mais recentes registrados no banco de dados."""
    return db.query(Alerta).order_by(desc(Alerta.id)).limit(limite).all()
