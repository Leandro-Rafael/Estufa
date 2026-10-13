"""
Módulo de conexão com o Banco de Dados SQLite usando SQLAlchemy.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# Engine SQLite com suporte seguro a múltiplas threads (FastAPI + Serial Reader)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    """Garante a criação de todas as tabelas no SQLite."""
    import models  # Garante registro dos modelos no metadata
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency injector para rotas do FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
