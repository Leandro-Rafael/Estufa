"""
Modelos ORM do SQLAlchemy para o banco de dados da Estufa Inteligente.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Text
from database import Base

class Leitura(Base):
    """
    Tabela de leituras periódicas coletadas dos sensores.
    """
    __tablename__ = "leituras"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    data_hora = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    temperatura = Column(Float, nullable=False)        # Graus Celsius (°C)
    umidade_ar = Column(Float, nullable=False)         # Porcentagem (%)
    umidade_solo = Column(Float, nullable=False)       # Porcentagem (%)
    luminosidade = Column(Float, nullable=False)       # Valor 0-1023 ou lux
    co2 = Column(Float, nullable=True)                 # ppm (preparado para expansão futura)

    def to_dict(self):
        return {
            "id": self.id,
            "data_hora": self.data_hora.isoformat() if self.data_hora else None,
            "temperatura": self.temperatura,
            "umidade_ar": self.umidade_ar,
            "umidade_solo": self.umidade_solo,
            "luminosidade": self.luminosidade,
            "co2": self.co2
        }


class Configuracao(Base):
    """
    Tabela de configurações editáveis pelo usuário no painel web.
    """
    __tablename__ = "configuracoes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chave = Column(String(64), unique=True, index=True, nullable=False)
    valor = Column(String(255), nullable=False)
    tipo = Column(String(32), default="float", nullable=False) # float, int, bool, str
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_typed_value(self):
        if self.tipo == "float":
            return float(self.valor)
        elif self.tipo == "int":
            return int(self.valor)
        elif self.tipo == "bool":
            return self.valor.lower() in ("true", "1", "t", "yes", "sim")
        return self.valor


class Alerta(Base):
    """
    Tabela de histórico de alertas disparados pelo sistema.
    """
    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    data_hora = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    metrica = Column(String(32), index=True, nullable=False) # temperatura, umidade_ar, umidade_solo, luminosidade
    valor = Column(Float, nullable=False)
    mensagem = Column(String(255), nullable=False)
    nivel = Column(String(16), default="critico", nullable=False) # alerta (amarelo), critico (vermelho)
    configuracao_usada = Column(String(255), nullable=True) # Resumo da faixa ativa no momento

    def to_dict(self):
        return {
            "id": self.id,
            "data_hora": self.data_hora.isoformat() if self.data_hora else None,
            "metrica": self.metrica,
            "valor": self.valor,
            "mensagem": self.mensagem,
            "nivel": self.nivel,
            "configuracao_usada": self.configuracao_usada
        }


class Irrigacao(Base):
    """
    Tabela de registro e auditoria de irrigações realizadas (manuais e automáticas).
    """
    __tablename__ = "irrigacoes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    data_hora_inicio = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    data_hora_fim = Column(DateTime, nullable=True)
    duracao_segundos = Column(Integer, nullable=True)
    modo = Column(String(32), nullable=False) # "manual", "automatico"
    motivo = Column(String(255), nullable=False)
    umidade_solo_inicial = Column(Float, nullable=True)
    umidade_solo_final = Column(Float, nullable=True)
    status = Column(String(32), default="em_andamento", nullable=False) # "em_andamento", "concluido", "interrompido", "falha"

    def to_dict(self):
        return {
            "id": self.id,
            "data_hora_inicio": self.data_hora_inicio.isoformat() if self.data_hora_inicio else None,
            "data_hora_fim": self.data_hora_fim.isoformat() if self.data_hora_fim else None,
            "duracao_segundos": self.duracao_segundos,
            "modo": self.modo,
            "motivo": self.motivo,
            "umidade_solo_inicial": self.umidade_solo_inicial,
            "umidade_solo_final": self.umidade_solo_final,
            "status": self.status
        }
