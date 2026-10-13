"""Test services"""
import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from services.leituras_service import (
    agregador_leituras,
    obter_ultima_leitura,
    obter_todas_configuracoes,
    inicializar_configuracoes_padrao,
)
from services.alertas_service import processar_alertas_leitura
from services.irrigacao_service import irrigacao_service
from models import Leitura, Configuracao, Alerta, Irrigacao
from schemas import LeituraInput, StatusMetricas


class TestLeiturasService:
    """Test leituras service"""
    
    def test_inicializar_configuracoes_padrao(self, db_session: Session):
        inicializar_configuracoes_padrao(db_session)
        configs = obter_todas_configuracoes(db_session)
        assert len(configs) >= 11
        # Verifica algumas chaves essenciais
        chaves = {c.chave for c in configs}
        assert "temp_min" in chaves
        assert "temp_max" in chaves
        assert "irrigacao_auto_ativada" in chaves
    
    def test_obter_todas_configuracoes(self, db_session: Session, sample_config):
        configs = obter_todas_configuracoes(db_session)
        assert len(configs) >= 11
    
    def test_agregador_leituras_nao_grava_antes_do_tempo(self, db_session: Session):
        """Testa que leituras são agregadas em memória antes de gravar no banco"""
        leitura = LeituraInput(
            temperatura=25.0,
            umidade_ar=60.0,
            umidade_solo=45.0,
            luminosidade=500.0,
            co2=400.0
        )
        
        # Primeira leitura - não deve gravar no banco ainda
        gravou, leitura_db = agregador_leitras.processar_leitura(db_session, leitura)
        assert gravou is False
        assert leitura_db is None
        
        # Verifica que não foi salvo no banco
        count = db_session.query(Leitura).count()
        assert count == 0
    
    def test_obter_ultima_leitura_vazio(self, db_session: Session):
        ultima = obter_ultima_leitura(db_session)
        assert ultima is None


class TestAlertasService:
    """Test alertas service"""
    
    def test_processar_alertas_temperatura_ok(self, db_session: Session, sample_config):
        leitura = LeituraInput(
            temperatura=24.0,
            umidade_ar=60.0,
            umidade_solo=50.0,
            luminosidade=500.0,
            co2=400.0
        )
        
        status, alertas = processar_alertas_leitura(db_session, leitura, sample_config)
        
        assert isinstance(status, StatusMetricas)
        assert status.temperatura == "ok"
        assert len(alertas) == 0
    
    def test_processar_alertas_temperatura_alerta(self, db_session: Session, sample_config):
        leitura = LeituraInput(
            temperatura=19.0,  # Abaixo do alerta_min (20.0)
            umidade_ar=60.0,
            umidade_solo=50.0,
            luminosidade=500.0,
            co2=400.0
        )
        
        status, alertas = processar_alertas_leitura(db_session, leitura, sample_config)
        
        assert status.temperatura == "alerta"
        assert len(alertas) == 1
        assert alertas[0].metrica == "temperatura"
        assert alertas[0].nivel == "alerta"
    
    def test_processar_alertas_temperatura_critico(self, db_session: Session, sample_config):
        leitura = LeituraInput(
            temperatura=17.0,  # Abaixo do min (18.0)
            umidade_ar=60.0,
            umidade_solo=50.0,
            luminosidade=500.0,
            co2=400.0
        )
        
        status, alertas = processar_alertas_leitura(db_session, leitura, sample_config)
        
        assert status.temperatura == "critico"
        assert len(alertas) == 1
        assert alertas[0].nivel == "critico"
    
    def test_processar_alertas_umidade_solo_critico(self, db_session: Session, sample_config):
        leitura = LeituraInput(
            temperatura=24.0,
            umidade_ar=60.0,
            umidade_solo=25.0,  # Abaixo do min (30.0)
            luminosidade=500.0,
            co2=400.0
        )
        
        status, alertas = processar_alertas_leitura(db_session, leitura, sample_config)
        
        assert status.umidade_solo == "critico"
        assert len(alertas) == 1
        assert alertas[0].metrica == "umidade_solo"


class TestIrrigacaoService:
    """Test irrigacao service"""
    
    @pytest.mark.asyncio
    async def test_avaliar_regras_automaticas_desativado(self, db_session: Session, sample_config):
        # Desativa irrigação automática
        config_auto = db_session.query(Configuracao).filter(
            Configuracao.chave == "irrigacao_auto_ativada"
        ).first()
        config_auto.valor = "false"
        db_session.commit()
        
        leitura = LeituraInput(
            temperatura=24.0,
            umidade_ar=60.0,
            umidade_solo=20.0,  # Bem abaixo do limite
            luminosidade=500.0,
            co2=400.0
        )
        
        # Não deve acionar irrigação pois está desativada
        await irrigacao_service.avaliar_regras_automaticas(db_session, sample_config, leitura.umidade_solo)
        
        irrigacoes = db_session.query(Irrigacao).all()
        assert len(irrigacoes) == 0
    
    @pytest.mark.asyncio
    async def test_acionar_irrigacao_manual(self, db_session: Session):
        irrigacao = await irrigacao_service.acionar_manual(
            db_session, 
            duracao_segundos=10,
            motivo="Teste manual"
        )
        
        assert irrigacao is not None
        assert irrigacao.modo == "manual"
        assert irrigacao.duracao_segundos == 10
        assert irrigacao.status == "em_andamento"
    
    @pytest.mark.asyncio
    async def test_parar_irrigacao(self, db_session: Session):
        # Inicia irrigação
        irrigacao = await irrigacao_service.acionar_manual(
            db_session, 
            duracao_segundos=60,
            motivo="Teste"
        )
        
        # Para irrigação
        resultado = await irrigacao_service.parar_irrigacao(db_session)
        
        assert resultado is True
        
        # Verifica se foi atualizado
        db_session.refresh(irrigacao)
        assert irrigacao.status == "interrompido"
        assert irrigacao.data_hora_fim is not None
        assert irrigacao.duracao_segundos is not None