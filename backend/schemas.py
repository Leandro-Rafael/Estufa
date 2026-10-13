"""
Schemas Pydantic para validação, serialização e resposta das requisições.
"""
from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field

# ----------------- Sensores e Leituras -----------------

class LeituraInput(BaseModel):
    """Payload recebido do hardware (Arduino/ESP32)."""
    temperatura: float = Field(..., description="Temperatura ambiente em °C", ge=-40, le=125)
    umidade_ar: float = Field(..., description="Umidade relativa do ar em %", ge=0, le=100)
    umidade_solo: float = Field(..., description="Umidade do solo em %", ge=0, le=100)
    luminosidade: float = Field(..., description="Nível de luminosidade do sensor LDR", ge=0, le=5000)
    co2: Optional[float] = Field(None, description="Nível de CO2 em ppm (opcional)", ge=0, le=10000)

class LeituraResponse(BaseModel):
    id: int
    data_hora: datetime
    temperatura: float
    umidade_ar: float
    umidade_solo: float
    luminosidade: float
    co2: Optional[float] = None

    class Config:
        from_attributes = True

# ----------------- Status das Métricas -----------------

class StatusMetricas(BaseModel):
    temperatura: str = Field("ok", description="ok | alerta | critico | offline")
    umidade_ar: str = Field("ok", description="ok | alerta | critico | offline")
    umidade_solo: str = Field("ok", description="ok | alerta | critico | offline")
    luminosidade: str = Field("ok", description="ok | alerta | critico | offline")

# ----------------- WebSocket Mensagem -----------------

class WebSocketMensagem(BaseModel):
    tipo: str = "leitura" # leitura, status_dispositivo, alerta, irrigacao
    data_hora: str
    temperatura: Optional[float] = None
    umidade_ar: Optional[float] = None
    umidade_solo: Optional[float] = None
    luminosidade: Optional[float] = None
    co2: Optional[float] = None
    status: Optional[StatusMetricas] = None
    alertas: List[str] = Field(default_factory=list)
    hardware_conectado: Optional[bool] = None

# ----------------- Configurações do Sistema -----------------

class ConfiguracoesPayload(BaseModel):
    """Estrutura completa das configurações do sistema editáveis pelo usuário."""
    temperatura_min: float = Field(20.0, description="Temperatura mínima ideal (°C)")
    temperatura_max: float = Field(28.0, description="Temperatura máxima ideal (°C)")
    tolerancia_temperatura: float = Field(2.0, description="Faixa de tolerância/alerta (°C)")

    umidade_ar_min: float = Field(50.0, description="Umidade do ar mínima ideal (%)")
    umidade_ar_max: float = Field(70.0, description="Umidade do ar máxima ideal (%)")
    tolerancia_umidade_ar: float = Field(5.0, description="Faixa de tolerância do ar (%)")

    umidade_solo_min: float = Field(40.0, description="Umidade do solo mínima ideal (%)")
    umidade_solo_max: float = Field(70.0, description="Umidade do solo máxima ideal (%)")
    tolerancia_umidade_solo: float = Field(5.0, description="Faixa de tolerância do solo (%)")

    luminosidade_min: float = Field(400.0, description="Luminosidade mínima ideal")
    luminosidade_max: float = Field(850.0, description="Luminosidade máxima ideal")
    tolerancia_luminosidade: float = Field(50.0, description="Faixa de tolerância de luminosidade")

    intervalo_leitura: int = Field(5, description="Intervalo de leitura em segundos", ge=1, le=3600)
    alertas_ativos: bool = Field(True, description="Se notificações de alertas estão habilitadas")

    # Configurações de Irrigação
    irrigacao_automatica: bool = Field(False, description="Ativar/desativar irrigação automática")
    irrigacao_solo_min: float = Field(35.0, description="Umidade do solo para iniciar irrigação (%)")
    irrigacao_solo_max: float = Field(65.0, description="Umidade do solo para parar irrigação (%)")
    tempo_max_irrigacao: int = Field(20, description="Tempo máximo de irrigação em segundos", ge=1, le=600)
    intervalo_espera_irrigacao: int = Field(300, description="Espera mínima entre irrigações em segundos", ge=10, le=86400)

class ConfiguracoesUpdate(BaseModel):
    """Permite atualização parcial ou total das configurações."""
    temperatura_min: Optional[float] = None
    temperatura_max: Optional[float] = None
    tolerancia_temperatura: Optional[float] = None

    umidade_ar_min: Optional[float] = None
    umidade_ar_max: Optional[float] = None
    tolerancia_umidade_ar: Optional[float] = None

    umidade_solo_min: Optional[float] = None
    umidade_solo_max: Optional[float] = None
    tolerancia_umidade_solo: Optional[float] = None

    luminosidade_min: Optional[float] = None
    luminosidade_max: Optional[float] = None
    tolerancia_luminosidade: Optional[float] = None

    intervalo_leitura: Optional[int] = None
    alertas_ativos: Optional[bool] = None

    irrigacao_automatica: Optional[bool] = None
    irrigacao_solo_min: Optional[float] = None
    irrigacao_solo_max: Optional[float] = None
    tempo_max_irrigacao: Optional[int] = None
    intervalo_espera_irrigacao: Optional[int] = None

# ----------------- Alertas -----------------

class AlertaResponse(BaseModel):
    id: int
    data_hora: datetime
    metrica: str
    valor: float
    mensagem: str
    nivel: str
    configuracao_usada: Optional[str] = None

    class Config:
        from_attributes = True

# ----------------- Irrigação -----------------

class IrrigacaoManualRequest(BaseModel):
    duracao_segundos: int = Field(10, description="Tempo de acionamento em segundos", ge=1, le=120)

class IrrigacaoStatusResponse(BaseModel):
    irrigando: bool
    modo: str # "desativado", "manual", "automatico"
    automatica_habilitada: bool
    tempo_restante_segundos: int
    ultima_irrigacao: Optional[str] = None
    bloqueado_por_cooldown: bool
    cooldown_restante_segundos: int
    umidade_solo_atual: Optional[float] = None
    regras: Dict[str, Any]

class IrrigacaoResponse(BaseModel):
    id: int
    data_hora_inicio: datetime
    data_hora_fim: Optional[datetime] = None
    duracao_segundos: Optional[int] = None
    modo: str
    motivo: str
    umidade_solo_inicial: Optional[float] = None
    umidade_solo_final: Optional[float] = None
    status: str

    class Config:
        from_attributes = True

# ----------------- Dispositivo / Serial -----------------

class DispositivoStatusResponse(BaseModel):
    conectado: bool
    porta: str
    baudrate: int
    modo_simulacao: bool
    ultima_leitura_recebida: Optional[str] = None
    total_leituras_recebidas: int
    erros_conexao: int
    tempo_ativo_segundos: float
    mensagem_status: str
