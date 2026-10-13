"""Test configuration and fixtures"""
import pytest
import asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app
from database import Base, get_db
from models import Leitura, Configuracao, Alerta, Irrigacao


# Test database (in-memory SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_config(db_session):
    """Create sample configurations"""
    configs = [
        Configuracao(chave="temp_min", valor="18.0", tipo="float"),
        Configuracao(chave="temp_max", valor="30.0", tipo="float"),
        Configuracao(chave="temp_alerta_min", valor="20.0", tipo="float"),
        Configuracao(chave="temp_alerta_max", valor="28.0", tipo="float"),
        Configuracao(chave="umidade_solo_min", valor="30.0", tipo="float"),
        Configuracao(chave="umidade_solo_max", valor="80.0", tipo="float"),
        Configuracao(chave="umidade_solo_alerta_min", valor="40.0", tipo="float"),
        Configuracao(chave="umidade_solo_alerta_max", valor="70.0", tipo="float"),
        Configuracao(chave="irrigacao_duracao_padrao", valor="10", tipo="int"),
        Configuracao(chave="irrigacao_limite_solo", valor="35.0", tipo="float"),
        Configuracao(chave="irrigacao_auto_ativada", valor="true", tipo="bool"),
    ]
    for config in configs:
        db_session.add(config)
    db_session.commit()
    return configs


@pytest.fixture
def sample_leitura(db_session):
    """Create a sample reading"""
    leitura = Leitura(
        temperatura=25.0,
        umidade_ar=60.0,
        umidade_solo=45.0,
        luminosidade=500.0,
        co2=400.0
    )
    db_session.add(leitura)
    db_session.commit()
    db_session.refresh(leitura)
    return leitura