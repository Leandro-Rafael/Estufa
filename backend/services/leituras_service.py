"""
Serviço de gerenciamento de leituras e configurações no banco de dados.
Implementa AGREGADOR TEMPORAL EM MEMÓRIA (10 em 10 minutos) para uso mínimo do SQLite.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import Leitura, Configuracao
from schemas import LeituraInput, ConfiguracoesPayload

# Valores padrão caso o banco de dados esteja zerado
CONFIG_PADROES: Dict[str, tuple[str, str]] = {
    "temperatura_min": ("20.0", "float"),
    "temperatura_max": ("28.0", "float"),
    "tolerancia_temperatura": ("2.0", "float"),

    "umidade_ar_min": ("50.0", "float"),
    "umidade_ar_max": ("70.0", "float"),
    "tolerancia_umidade_ar": ("5.0", "float"),

    "umidade_solo_min": ("40.0", "float"),
    "umidade_solo_max": ("70.0", "float"),
    "tolerancia_umidade_solo": ("5.0", "float"),

    "luminosidade_min": ("400.0", "float"),
    "luminosidade_max": ("850.0", "float"),
    "tolerancia_luminosidade": ("50.0", "float"),

    "intervalo_leitura": ("5", "int"),
    "alertas_ativos": ("true", "bool"),

    "irrigacao_automatica": ("false", "bool"),
    "irrigacao_solo_min": ("35.0", "float"),
    "irrigacao_solo_max": ("65.0", "float"),
    "tempo_max_irrigacao": ("20", "int"),
    "intervalo_espera_irrigacao": ("300", "int"),
    "intervalo_gravacao_banco_minutos": ("10", "int"), # 10 em 10 minutos no banco
}

# ----------------- AGREGADOR DE 10 MINUTOS (MÍNIMO USO DE DISCO) -----------------

class Agregador10Min:
    """
    Acumula as amostras frequentes dos sensores na memória RAM e só
    grava no banco de dados a cada 10 minutos, calculando a média consolidada.
    Isso reduz a escrita no banco em mais de 95% e otimiza o gráfico histórico.
    """
    def __init__(self, intervalo_segundos: int = 600):
        self.intervalo_segundos = intervalo_segundos # 600 segundos = 10 minutos
        self.ultima_gravacao: Optional[datetime] = None
        self.amostras_temp: List[float] = []
        self.amostras_uar: List[float] = []
        self.amostras_usolo: List[float] = []
        self.amostras_lum: List[float] = []
        self.amostras_co2: List[float] = []
        self.ultima_leitura_realtime: Optional[Dict[str, Any]] = None

    def processar_leitura(self, db: Session, dados: LeituraInput) -> Tuple[bool, Optional[Leitura]]:
        agora = datetime.utcnow()

        # Atualiza o snapshot ao vivo em memória (para WebSockets e cards responderem no mesmo instante)
        self.ultima_leitura_realtime = {
            "data_hora": agora.isoformat(),
            "temperatura": dados.temperatura,
            "umidade_ar": dados.umidade_ar,
            "umidade_solo": dados.umidade_solo,
            "luminosidade": dados.luminosidade,
            "co2": dados.co2
        }

        # Acumula na janela da memória
        self.amostras_temp.append(dados.temperatura)
        self.amostras_uar.append(dados.umidade_ar)
        self.amostras_usolo.append(dados.umidade_solo)
        self.amostras_lum.append(dados.luminosidade)
        if dados.co2 is not None:
            self.amostras_co2.append(dados.co2)

        # Checa se deve persistir no SQLite
        deve_gravar = False
        if self.ultima_gravacao is None:
            # Se for a primeiríssima gravação histórica do sistema, salva para inicializar
            total = db.query(Leitura).count()
            if total == 0:
                deve_gravar = True
            else:
                self.ultima_gravacao = agora
        elif (agora - self.ultima_gravacao).total_seconds() >= self.intervalo_segundos:
            deve_gravar = True

        if deve_gravar and self.amostras_temp:
            temp_med = round(sum(self.amostras_temp) / len(self.amostras_temp), 1)
            uar_med = round(sum(self.amostras_uar) / len(self.amostras_uar), 1)
            usolo_med = round(sum(self.amostras_usolo) / len(self.amostras_usolo), 1)
            lum_med = round(sum(self.amostras_lum) / len(self.amostras_lum), 1)
            co2_med = round(sum(self.amostras_co2) / len(self.amostras_co2), 1) if self.amostras_co2 else None

            leitura_db = Leitura(
                data_hora=agora,
                temperatura=temp_med,
                umidade_ar=uar_med,
                umidade_solo=usolo_med,
                luminosidade=lum_med,
                co2=co2_med
            )
            db.add(leitura_db)
            db.commit()
            db.refresh(leitura_db)

            # Esvazia listas para o próximo intervalo de 10 min
            self.amostras_temp.clear()
            self.amostras_uar.clear()
            self.amostras_usolo.clear()
            self.amostras_lum.clear()
            self.amostras_co2.clear()
            self.ultima_gravacao = agora

            return True, leitura_db

        return False, None

agregador_leituras = Agregador10Min(intervalo_segundos=600)

def inicializar_configuracoes_padrao(db: Session) -> None:
    """Garante que todas as chaves de configuração existam no banco."""
    for chave, (val_padrao, tipo) in CONFIG_PADROES.items():
        item = db.query(Configuracao).filter(Configuracao.chave == chave).first()
        if not item:
            novo_item = Configuracao(chave=chave, valor=val_padrao, tipo=tipo)
            db.add(novo_item)
    db.commit()

def obter_todas_configuracoes(db: Session) -> Dict[str, Any]:
    """Retorna dicionário com todas as configurações convertidas para tipos nativos."""
    inicializar_configuracoes_padrao(db)
    itens = db.query(Configuracao).all()
    resultado = {}
    for item in itens:
        resultado[item.chave] = item.get_typed_value()
    return resultado

def salvar_configuracoes(db: Session, config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Atualiza configurações no banco de dados."""
    inicializar_configuracoes_padrao(db)
    for chave, valor in config_dict.items():
        if valor is None:
            continue
        item = db.query(Configuracao).filter(Configuracao.chave == chave).first()
        if item:
            item.valor = str(valor)
            item.atualizado_em = datetime.utcnow()
        else:
            tipo = "float" if isinstance(valor, float) else "int" if isinstance(valor, int) else "bool" if isinstance(valor, bool) else "str"
            item = Configuracao(chave=chave, valor=str(valor), tipo=tipo)
            db.add(item)
    db.commit()
    return obter_todas_configuracoes(db)

def salvar_leitura(db: Session, dados: LeituraInput) -> Leitura:
    """Persiste leitura direta no SQLite (usado em testes ou gravações manuais)."""
    leitura = Leitura(
        data_hora=datetime.utcnow(),
        temperatura=dados.temperatura,
        umidade_ar=dados.umidade_ar,
        umidade_solo=dados.umidade_solo,
        luminosidade=dados.luminosidade,
        co2=dados.co2
    )
    db.add(leitura)
    db.commit()
    db.refresh(leitura)
    return leitura

def obter_ultima_leitura(db: Session) -> Optional[Dict[str, Any]]:
    """
    Recupera a leitura mais recente em tempo real da memória RAM se disponível,
    ou consulta o SQLite caso o servidor tenha acabado de iniciar.
    """
    if agregador_leituras.ultima_leitura_realtime:
        return agregador_leituras.ultima_leitura_realtime

    db_item = db.query(Leitura).order_by(desc(Leitura.id)).first()
    if db_item:
        return db_item.to_dict()
    return None

def obter_historico_leituras(
    db: Session,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
    limite: int = 200,
    periodo: Optional[str] = None
) -> List[Leitura]:
    """
    Recupera histórico consolidado do banco (pontos calculados de 10 em 10 minutos).
    Garante máxima velocidade de resposta e mínimo consumo de armazenamento.
    """
    query = db.query(Leitura)

    agora = datetime.utcnow()
    if periodo:
        if periodo == "1h":
            inicio = agora - timedelta(hours=1)
        elif periodo == "6h":
            inicio = agora - timedelta(hours=6)
        elif periodo == "24h":
            inicio = agora - timedelta(hours=24)
        elif periodo == "7d":
            inicio = agora - timedelta(days=7)

    if inicio:
        query = query.filter(Leitura.data_hora >= inicio)
    if fim:
        query = query.filter(Leitura.data_hora <= fim)

    leituras = query.order_by(desc(Leitura.id)).limit(limite).all()
    leituras.reverse()
    return leituras
