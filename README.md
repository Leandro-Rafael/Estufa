# Estufa Monitor 🌱

Sistema profissional de monitoramento e automação de estufa inteligente com **FastAPI (Python)**, **Frontend Vanilla (HTML/CSS/JS)**, **SQLite** e **ESP32/Arduino** via Serial.

## 📋 Visão Geral

| Componente | Tecnologia |
|------------|------------|
| **Backend API** | FastAPI + SQLAlchemy + SQLite + WebSockets |
| **Frontend** | HTML5 + CSS3 (Custom Design System) + Vanilla JS + Chart.js |
| **Hardware** | ESP32/Arduino via Serial USB |
| **Banco de Dados** | SQLite (desenvolvimento) / PostgreSQL (produção) |
| **Deploy Frontend** | Netlify (Static Site + PWA) |
| **Deploy Backend** | Docker (Railway, Render, Fly.io, VPS) |
| **CI/CD** | GitHub Actions |

## 🎯 Funcionalidades

- ✅ **Telemetria em tempo real** via WebSocket (temperatura, umidade ar/solo, luminosidade, CO₂)
- ✅ **Cálculo agronômico de VPD** (Déficit de Pressão de Vapor)
- ✅ **Agregação inteligente** - salva no banco a cada 10 min (mínimo uso do banco)
- ✅ **Sistema de alertas** com níveis (OK, Alerta, Crítico) + cooldown
- ✅ **Irrigação automática/manual** com regras configuráveis
- ✅ **Console serial interativo** no navegador
- ✅ **Dashboard responsivo** (mobile-first) com abas
- ✅ **PWA instalável** com Service Worker
- ✅ **Deploy Netlify (frontend) + Container (backend)**

## 📡 Sensores Suportados

| Sensor | Medida | Comunicação |
|--------|--------|-------------|
| **DHT22** | Temp. Ar (°C) / Umidade (%) | GPIO (1-Wire) |
| **Capacitivo** | Umidade Solo (%) | ADC |
| **BH1750** | Luminosidade (lux) | I2C |
| **SCD41** | CO₂ (ppm) / Temp / Umidade | I2C |

## 🚀 Quick Start

### 1. Clone e Configure Backend

```bash
cd Nailton/estufa-monitor/backend
cp .env.example .env
# Edite .env com suas configurações

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Rodar migrações
alembic upgrade head

# Iniciar backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Configure Frontend

```bash
cd ../frontend
npm install
npm run dev  # Desenvolvimento com proxy para backend
# Abre http://localhost:5173
```

### 3. Configure ESP32/Arduino

1. Abra `arduino/estufa_monitor.ino` no Arduino IDE
2. Instale bibliotecas:
   - **DHT sensor library** (Adafruit)
   - **Adafruit Unified Sensor**
   - **BH1750** (by claws)
   - **Sensirion I2C SCD4x**
   - **ArduinoJson** (v7+)
3. Atualize credenciais:
   ```cpp
   #define WIFI_SSID "SEU_WIFI"
   #define WIFI_PASSWORD "SUA_SENHA"
   #define BACKEND_URL "http://SEU_IP_LOCAL:8000"
   ```
4. Flash no ESP32
5. Abra Serial Monitor (115200 baud) → calibre:
   ```
   calibrate_soil_dry    // Solo seco
   calibrate_soil_wet    // Solo molhado
   status                // Ver status
   help                  // Ajuda
   ```

## 🐳 Deploy com Docker

### Backend
```bash
cd backend
docker build -t estufa-backend .
docker run -d -p 8000:8000 -v $(pwd)/data:/app/data estufa-backend
```

### Frontend (Netlify)
```bash
cd frontend
npm run build
# Arraste a pasta 'dist' para Netlify Drop Zone
# OU: netlify deploy --prod --dir=dist
```

### Docker Compose (Local)
```bash
docker-compose up -d
```

## ☁️ Deploy Produção

### Frontend → Netlify (Recomendado)
1. Push para GitHub
2. Netlify: "Add new site" → "Import from Git"
3. Build: `npm run build` | Publish: `dist`
4. Configure redirects para API backend no `netlify.toml`

### Backend → Railway / Render / Fly.io / VPS
```bash
# Railway
railway login
railway init
railway up

# Render
# Conecte repo GitHub → New Web Service → Docker

# Fly.io
fly launch --dockerfile backend/Dockerfile
fly deploy
```

## 📁 Estrutura do Projeto

```
Nailton/estufa-monitor/
├── .github/workflows/ci-cd.yml    # CI/CD Pipeline
├── docker-compose.yml             # Docker Compose local
├── README.md                      # Esta documentação
├── backend/
│   ├── main.py                    # FastAPI app + WebSocket + lifespan
│   ├── config.py                  # Settings via .env (pydantic-settings)
│   ├── database.py                # SQLAlchemy + SessionLocal
│   ├── models.py                  # ORM (Leitura, Config, Alerta, Irrigacao)
│   ├── schemas.py                 # Pydantic models
│   ├── routers/                   # API endpoints
│   │   ├── sensores.py
│   │   ├── configuracoes.py
│   │   ├── historico.py
│   │   ├── alertas.py
│   │   ├── irrigacao.py
│   │   └── dispositivo.py
│   ├── services/                  # Business logic
│   │   ├── leituras_service.py    # Agregação 10min + CRUD
│   │   ├── alertas_service.py     # Processamento alertas + VPD
│   │   └── irrigacao_service.py   # Regras automáticas + manual
│   ├── serial_reader.py           # Thread serial + callbacks
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── alembic.ini                # Migrações
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/001_initial.py
│   ├── tests/                     # Pytest
│   │   ├── conftest.py
│   │   ├── test_api.py
│   │   └── test_services.py
│   ├── pytest.ini
│   └── .env.example
├── frontend/
│   ├── index.html                 # Dashboard completo (tabs, charts, terminal)
│   ├── css/style.css              # Design system custom (obsidian theme)
│   ├── js/app.js                  # WebSocket, VPD, charts, irrigação, terminal
│   ├── package.json
│   ├── vite.config.js             # Vite + PWA + Build otimizado
│   ├── netlify.toml               # Config Netlify
│   ├── public/
│   │   └── manifest.json          # PWA Manifest
│   └── dist/                      # Build output (após npm run build)
├── arduino/
│   └── estufa_monitor.ino         # Firmware ESP32 completo
└── estufa.db                      # SQLite (criado automaticamente)
```

## 🔌 API Endpoints

### Sensores
```http
GET  /api/sensores/ultima              # Última leitura
GET  /api/sensores/historico?periodo=24h&limite=100
POST /api/sensores/leitura             # ESP32 envia leitura
```

### Configurações
```http
GET    /api/configuracoes              # Todas
GET    /api/configuracoes/{chave}      # Específica
PUT    /api/configuracoes/{chave}      # Atualizar
```

### Alertas
```http
GET  /api/alertas?limite=20&nivel=critico
DELETE /api/alertas/limpar
```

### Irrigação
```http
GET  /api/irrigacao/status
POST   /api/irrigacao/manual     { "duracao_segundos": 10 }
POST   /api/irrigacao/parar
GET    /api/irrigacao/historico?limite=15
```

### Dispositivo
```http
GET /api/dispositivo/status
GET /api/dispositivo/portas
```

### WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.tipo === 'leitura') { /* atualiza UI */ }
};
```

## ⏰ Agregação Automática (10 min)

O sistema **não salva cada leitura no banco** (seriam 2880/dia). Em vez disso:

```
ESP32 (30s) → Memória (agregador) 
     ↓ (10 min)
SQLite (1 registro agregado: média, min, max, count)
```

Isso reduz escrita no banco em **99.7%**.

## 🔔 Alertas

### Níveis
- **OK** (verde): Dentro da faixa ideal
- **Alerta** (amarelo): Fora da faixa de tolerância
- **Crítico** (vermelho): Fora da faixa segura

### Cooldown
Evita spam: 60 min padrão entre alertas da mesma métrica.

## 🔧 Variáveis de Ambiente (Backend/.env)

```env
APP_NAME=Estufa Monitor
DEBUG=false
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite:///./data/estufa.db
FRONTEND_DIR=../frontend
SERIAL_PORT=/dev/ttyUSB0
BAUD_RATE=115200
SIMULATE_SERIAL=false
BACKEND_URL=http://localhost:8000
```

## 📱 PWA (Progressive Web App)

O frontend é instalável:
- **Mobile**: "Adicionar à tela inicial"
- **Desktop**: Instala como app nativo
- **Offline**: Service Worker cacheia assets
- **Atualização automática** via `vite-plugin-pwa`

## 🧪 Testes

```bash
# Backend
cd backend
pytest tests/ -v --cov=./

# Frontend
cd frontend
npm run test
```

## 📈 Monitoramento

- **Health check**: `GET /health`
- **Logs estruturados** (JSON) via structlog
- **Métricas**: `/metrics` (prometheus ready)

## 🛠 Troubleshooting

| Problema | Solução |
|----------|---------|
| ESP32 não conecta WiFi | Verifique SSID/PASSWORD, RSSI > -80 dBm |
| Serial não conecta | Verifique `SERIAL_PORT`, permissão `dialout` |
| WebSocket não conecta | CORS, proxy Netlify → backend URL correta |
| Banco não cria tabelas | `alembic upgrade head` |
| Gráfico vazio | Aguarde primeira agregação (10 min) ou envie leitura manual |
| Calibração solo | Serial Monitor → `calibrate_soil_dry` / `calibrate_soil_wet` |

## 🔄 Migração Futura

| Para | Mudanças |
|------|----------|
| **PostgreSQL** | `DATABASE_URL=postgresql://user:pass@host/db` + `alembic upgrade head` |
| **TimescaleDB** | Extensão no PostgreSQL + hypertables para leituras |
| **MQTT** | Substituir Serial por MQTT broker (Mosquitto/EMQX) |
| **Kubernetes** | Helm charts + HPA + PersistentVolumes |

## 📄 Licença

MIT License - Use livremente para seu projeto de estufa!

---

**Desenvolvido para monitoramento profissional de estufa** 🌱
**Arquitetura**: FastAPI + Vanilla JS + ESP32 Serial