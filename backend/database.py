"""
Módulo de conexão com o Banco de Dados.
Suporta SQLite (desenvolvimento) e PostgreSQL (produção) com pool de conexões.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# Configuração específica por tipo de banco
if settings.is_postgres:
    # PostgreSQL - pool de conexões para produção
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )
else:
    # SQLite - desenvolvimento local
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Garante a criação de todas as tabelas no banco."""
    import models  # Garante registro dos modelos no metadata
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency injector para rotas do FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()