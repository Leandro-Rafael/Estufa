"""
Módulo de configurações da aplicação.
Carrega variáveis de ambiente com validação e valores padrão seguros.
Suporta SQLite (desenvolvimento) e PostgreSQL (produção).
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # Conexão Serial com Arduino/ESP32
    SERIAL_PORT: str = "COM3"
    SERIAL_BAUDRATE: int = 115200
    SERIAL_TIMEOUT: float = 1.0
    SERIAL_RECONNECT_INTERVAL: float = 3.0

    # Modo de simulação para desenvolvimento/testes sem hardware físico
    SIMULATION_MODE: bool = False
    AUTO_FALLBACK_SIMULATION: bool = True

    # Banco de Dados - SQLite (dev) ou PostgreSQL (prod)
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/estufa.db"

    # Servidor Web - Render injeta PORT automaticamente
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

    @property
    def is_postgres(self) -> bool:
        """Detecta se está usando PostgreSQL pela URL."""
        return self.DATABASE_URL.startswith("postgresql")

settings = Settings()