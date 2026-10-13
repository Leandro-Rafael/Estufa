"""Initial migration - Create all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create leituras table
    op.create_table(
        'leituras',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('data_hora', sa.DateTime(), default=sa.func.now(), index=True, nullable=False),
        sa.Column('temperatura', sa.Float(), nullable=False),
        sa.Column('umidade_ar', sa.Float(), nullable=False),
        sa.Column('umidade_solo', sa.Float(), nullable=False),
        sa.Column('luminosidade', sa.Float(), nullable=False),
        sa.Column('co2', sa.Float(), nullable=True),
    )

    # Create configuracoes table
    op.create_table(
        'configuracoes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('chave', sa.String(64), unique=True, index=True, nullable=False),
        sa.Column('valor', sa.String(255), nullable=False),
        sa.Column('tipo', sa.String(32), default='float', nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create alertas table
    op.create_table(
        'alertas',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('data_hora', sa.DateTime(), default=sa.func.now(), index=True, nullable=False),
        sa.Column('metrica', sa.String(32), index=True, nullable=False),
        sa.Column('valor', sa.Float(), nullable=False),
        sa.Column('mensagem', sa.String(255), nullable=False),
        sa.Column('nivel', sa.String(16), default='critico', nullable=False),
        sa.Column('configuracao_usada', sa.String(255), nullable=True),
    )

    # Create irrigacoes table
    op.create_table(
        'irrigacoes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('data_hora_inicio', sa.DateTime(), default=sa.func.now(), index=True, nullable=False),
        sa.Column('data_hora_fim', sa.DateTime(), nullable=True),
        sa.Column('duracao_segundos', sa.Integer(), nullable=True),
        sa.Column('modo', sa.String(32), nullable=False),
        sa.Column('motivo', sa.String(255), nullable=False),
        sa.Column('umidade_solo_inicial', sa.Float(), nullable=True),
        sa.Column('umidade_solo_final', sa.Float(), nullable=True),
        sa.Column('status', sa.String(32), default='em_andamento', nullable=False),
    )

    # Insert default configurations
    op.bulk_insert(
        sa.table(
            'configuracoes',
            sa.Column('chave', sa.String(64)),
            sa.Column('valor', sa.String(255)),
            sa.Column('tipo', sa.String(32)),
        ),
        [
            {'chave': 'temp_min', 'valor': '18.0', 'tipo': 'float'},
            {'chave': 'temp_max', 'valor': '30.0', 'tipo': 'float'},
            {'chave': 'temp_alerta_min', 'valor': '20.0', 'tipo': 'float'},
            {'chave': 'temp_alerta_max', 'valor': '28.0', 'tipo': 'float'},
            {'chave': 'umidade_ar_min', 'valor': '40.0', 'tipo': 'float'},
            {'chave': 'umidade_ar_max', 'valor': '80.0', 'tipo': 'float'},
            {'chave': 'umidade_ar_alerta_min', 'valor': '50.0', 'tipo': 'float'},
            {'chave': 'umidade_ar_alerta_max', 'valor': '70.0', 'tipo': 'float'},
            {'chave': 'umidade_solo_min', 'valor': '30.0', 'tipo': 'float'},
            {'chave': 'umidade_solo_max', 'valor': '80.0', 'tipo': 'float'},
            {'chave': 'umidade_solo_alerta_min', 'valor': '40.0', 'tipo': 'float'},
            {'chave': 'umidade_solo_alerta_max', 'valor': '70.0', 'tipo': 'float'},
            {'chave': 'luminosidade_min', 'valor': '200.0', 'tipo': 'float'},
            {'chave': 'luminosidade_max', 'valor': '1000.0', 'tipo': 'float'},
            {'chave': 'luminosidade_alerta_min', 'valor': '400.0', 'tipo': 'float'},
            {'chave': 'luminosidade_alerta_max', 'valor': '850.0', 'tipo': 'float'},
            {'chave': 'irrigacao_duracao_padrao', 'valor': '10', 'tipo': 'int'},
            {'chave': 'irrigacao_limite_solo', 'valor': '35.0', 'tipo': 'float'},
            {'chave': 'irrigacao_auto_ativada', 'valor': 'true', 'tipo': 'bool'},
            {'chave': 'co2_max', 'valor': '1500.0', 'tipo': 'float'},
            {'chave': 'co2_alerta', 'valor': '1000.0', 'tipo': 'float'},
        ]
    )


def downgrade() -> None:
    op.drop_table('irrigacoes')
    op.drop_table('alertas')
    op.drop_table('configuracoes')
    op.drop_table('leituras')