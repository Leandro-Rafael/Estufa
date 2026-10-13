"""
Bateria de testes automatizados para o sistema de monitoramento de estufa.
"""
import sys
import os
from pathlib import Path

# Adiciona o diretório backend ao sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Base, engine, init_db
from models import Leitura, Configuracao, Alerta, Irrigacao
from schemas import LeituraInput
from services.leituras_service import (
    inicializar_configuracoes_padrao,
    obter_todas_configuracoes,
    salvar_configuracoes,
    salvar_leitura
)
from services.alertas_service import avaliar_metrica, processar_alertas_leitura

client = TestClient(app)

def test_database_and_configuracoes():
    """Valida inicialização do banco SQLite e configurações padrão."""
    init_db()
    db = SessionLocal()
    try:
        inicializar_configuracoes_padrao(db)
        salvar_configuracoes(db, {"temperatura_min": 20.0, "temperatura_max": 28.0})
        configs = obter_todas_configuracoes(db)
        assert "temperatura_min" in configs
        assert configs["temperatura_min"] == 20.0
        assert configs["temperatura_max"] == 28.0
        assert configs["alertas_ativos"] is True
    finally:
        db.close()

def test_avaliacao_metricas_e_alertas():
    """Valida a classificação em ok (verde), alerta (amarelo) e crítico (vermelho)."""
    # Temperatura ideal: 20 a 28, tolerância 2
    # 24°C => ok
    status, _ = avaliar_metrica(24.0, 20.0, 28.0, 2.0)
    assert status == "ok"

    # 19°C => alerta (entre 18 e 20)
    status, motivo = avaliar_metrica(19.0, 20.0, 28.0, 2.0)
    assert status == "alerta"

    # 15°C => critico (< 18)
    status, motivo = avaliar_metrica(15.0, 20.0, 28.0, 2.0)
    assert status == "critico"

    # 35°C => critico (> 30)
    status, motivo = avaliar_metrica(35.0, 20.0, 28.0, 2.0)
    assert status == "critico"

def test_salvar_leitura():
    """Valida inserção de leitura no banco e processamento de alertas."""
    db = SessionLocal()
    try:
        dados = LeituraInput(
            temperatura=35.0, # Crítico alto
            umidade_ar=30.0,  # Crítico baixo
            umidade_solo=45.0,# Ideal
            luminosidade=600.0# Ideal
        )
        leitura = salvar_leitura(db, dados)
        assert leitura.id is not None
        assert leitura.temperatura == 35.0

        configs = obter_todas_configuracoes(db)
        status_calc, alertas = processar_alertas_leitura(db, dados, configs)
        assert status_calc.temperatura == "critico"
        assert status_calc.umidade_ar == "critico"
        assert status_calc.umidade_solo == "ok"
        assert len(alertas) >= 2
    finally:
        db.close()

def test_endpoints_rest():
    """Valida os principais endpoints da API REST."""
    # 1. Leitura atual
    res = client.get("/api/leituras/atual")
    assert res.status_code == 200
    json_leitura = res.json()
    assert "status" in json_leitura

    # 2. Obter configurações
    res = client.get("/api/configuracoes")
    assert res.status_code == 200
    configs = res.json()
    assert configs["temperatura_min"] == 20.0

    # 3. Atualizar configurações
    res = client.put("/api/configuracoes", json={"temperatura_min": 21.5})
    assert res.status_code == 200
    assert res.json()["temperatura_min"] == 21.5

    # 4. Status da irrigação
    res = client.get("/api/irrigacao/status")
    assert res.status_code == 200
    assert "irrigando" in res.json()

    # 5. Acionamento manual de irrigação
    res = client.post("/api/irrigacao/manual", json={"duracao_segundos": 5})
    assert res.status_code == 200
    assert res.json()["sucesso"] is True

    # 6. Parada de irrigação
    res = client.post("/api/irrigacao/parar")
    assert res.status_code == 200

    # 7. Status do dispositivo
    res = client.get("/api/dispositivo/status")
    assert res.status_code == 200
    assert "baudrate" in res.json()

    # 8. Histórico de leituras
    res = client.get("/api/leituras/historico?limite=10")
    assert res.status_code == 200
    assert "dados" in res.json()

    # 9. Histórico de alertas
    res = client.get("/api/alertas?limite=10")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

if __name__ == "__main__":
    print("Executando bateria de testes...")
    test_database_and_configuracoes()
    test_avaliacao_metricas_e_alertas()
    test_salvar_leitura()
    test_endpoints_rest()
    print("[OK] Todos os 4 conjuntos de testes foram aprovados com sucesso!")
