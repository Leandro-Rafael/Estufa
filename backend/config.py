"""
Módulo de configurações da aplicação.
Carrega variáveis de ambiente com validação e valores padrão seguros.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # Conexão Serial com Arduino
    SERIAL_PORT: str = "COM3"
    SERIAL_BAUDRATE: int = 9600
    SERIAL_TIMEOUT: float = 1.0
    SERIAL_RECONNECT_INTERVAL: float = 3.0
    
    # Modo de simulação para desenvolvimento/testes sem hardware físico conectado
    # Se habilitado ou se AUTO_FALLBACK_SIMULATION estiver ativo, gera dados simulados
    SIMULATION_MODE: bool = False
    AUTO_FALLBACK_SIMULATION: bool = True  # Permite simulação se a porta serial não abrir, para não travar o frontend

    # Banco de Dados SQLite
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/estufa.db"

    # Servidor Web
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # Diretório estático do Frontend
    FRONTEND_DIR: str = str(BASE_DIR.parent / "frontend")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
