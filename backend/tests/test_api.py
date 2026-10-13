"""Test API endpoints"""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test health check endpoint"""
    
    def test_health_check(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestSensoresRouter:
    """Test sensores API endpoints"""
    
    def test_get_ultima_leitura_empty(self, client: TestClient):
        response = client.get("/api/sensores/ultima")
        assert response.status_code == 200
        # Pode retornar null se não houver leituras
    
    def test_get_leituras_com_filtro(self, client: TestClient, sample_leitura):
        response = client.get("/api/sensores/historico?limite=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_get_leituras_com_periodo(self, client: TestClient, sample_leitura):
        response = client.get("/api/sensores/historico?periodo=1h")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestConfiguracoesRouter:
    """Test configuracoes API endpoints"""
    
    def test_get_todas_configuracoes(self, client: TestClient, sample_config):
        response = client.get("/api/configuracoes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 11  # configs padrão
    
    def test_get_configuracao_especifica(self, client: TestClient, sample_config):
        response = client.get("/api/configuracoes/temp_min")
        assert response.status_code == 200
        data = response.json()
        assert data["chave"] == "temp_min"
        assert data["valor"] == "18.0"
    
    def test_atualizar_configuracao(self, client: TestClient):
        response = client.put(
            "/api/configuracoes/temp_min",
            json={"valor": "20.0"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valor"] == "20.0"
    
    def test_atualizar_configuracao_invalida(self, client: TestClient):
        response = client.put(
            "/api/configuracoes/chave_inexistente",
            json={"valor": "10.0"}
        )
        assert response.status_code == 404


class TestAlertasRouter:
    """Test alertas API endpoints"""
    
    def test_get_alertas(self, client: TestClient):
        response = client.get("/api/alertas?limite=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_alertas_com_filtro_nivel(self, client: TestClient):
        response = client.get("/api/alertas?nivel=critico")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_limpar_alertas(self, client: TestClient):
        response = client.delete("/api/alertas/limpar")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestIrrigacaoRouter:
    """Test irrigacao API endpoints"""
    
    def test_get_status_irrigacao(self, client: TestClient):
        response = client.get("/api/irrigacao/status")
        assert response.status_code == 200
        data = response.json()
        assert "irrigando" in data
        assert "modo" in data
    
    def test_acionar_irrigacao_manual(self, client: TestClient):
        response = client.post(
            "/api/irrigacao/manual",
            json={"duracao_segundos": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_parar_irrigacao(self, client: TestClient):
        response = client.post("/api/irrigacao/parar")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_get_historico_irrigacoes(self, client: TestClient):
        response = client.get("/api/irrigacao/historico?limite=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestDispositivoRouter:
    """Test dispositivo API endpoints"""
    
    def test_get_status_dispositivo(self, client: TestClient):
        response = client.get("/api/dispositivo/status")
        assert response.status_code == 200
        data = response.json()
        assert "conectado" in data or "em_simulacao" in data
    
    def test_get_portas_seriais(self, client: TestClient):
        response = client.get("/api/dispositivo/portas")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)