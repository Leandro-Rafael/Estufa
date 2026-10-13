/**
 * AeroFlora OS - Orquestrador Principal da Interface Web IoT (Senior UI/UX).
 * Gerencia Telemetria, Cálculo de DPV (VPD), Console Serial Interativo,
 * Controle de Irrigação e Análise de Tendências.
 */

// Estado Global
let ultimaDataLeitura = null;
let leiturasAnteriores = { temp: null, uar: null, usolo: null, lum: null };
let timerRelativoInterval = null;
let timerIrrigacaoInterval = null;
let duracaoIrrigacaoRestante = 0;
let duracaoIrrigacaoTotal = 10;
let terminalAutoScroll = true;

document.addEventListener("DOMContentLoaded", async () => {
  console.log("🌿 AeroFlora OS inicializado com sucesso.");

  // 1. Inicializa Gráficos
  graficosManager.inicializar();

  // 2. Carrega Configurações do Banco
  await configManager.carregar();

  // 3. Configura Navegação por Abas
  configurarAbas();

  // 4. Configura Eventos de UI, Botões e Presets
  configurarEventosUI();

  // 5. Configura e Conecta WebSocket
  registrarWebSocketListeners();
  wsClient.conectar();

  // 6. Carrega Estado Inicial e Portas Seriais
  carregarEstadoInicial();
  carregarPortasSeriaisDisponiveis();
  carregarLogsTerminalIniciais();

  // 7. Loop de contagem relativa
  iniciarTimerRelativo();
});

/* ==================== NAVEGAÇÃO DE ABAS ==================== */

function configurarAbas() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const targetId = tab.getAttribute("data-tab");

      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      const panel = document.getElementById(targetId);
      if (panel) panel.classList.add("active");

      // Gatilhos de carregamento sob demanda
      if (targetId === "tab-historico") {
        carregarTabelaEGraficoHistorico();
      } else if (targetId === "tab-irrigacao") {
        atualizarStatusIrrigacao();
        carregarHistoricoIrrigacoes();
      } else if (targetId === "tab-dispositivos") {
        atualizarDiagnosticoDispositivo();
        carregarPortasSeriaisDisponiveis();
      }
    });
  });

  // Botões atalho no topo
  document.getElementById("btn-toggle-terminal")?.addEventListener("click", () => {
    const tabDisp = document.querySelector('[data-tab="tab-dispositivos"]');
    if (tabDisp) tabDisp.click();
  });

  document.getElementById("btn-dash-modal-config")?.addEventListener("click", () => {
    const tabCfg = document.querySelector('[data-tab="tab-configuracoes"]');
    if (tabCfg) tabCfg.click();
  });
}

function abrirConfiguracoesRapidas() {
  const tabCfg = document.querySelector('[data-tab="tab-configuracoes"]');
  if (tabCfg) tabCfg.click();
}

/* ==================== WEBSOCKET & FLUXO DE TELEMETRIA ==================== */

function registrarWebSocketListeners() {
  // 1. Nova Leitura dos Sensores
  wsClient.on("leitura", (dados) => {
    processarNovaLeitura(dados);
  });

  // 2. Mudança de Estado de Hardware
  wsClient.on("status_dispositivo", (dados) => {
    atualizarStatusHardwareHeader(dados.hardware_conectado);
    if (dados.mensagem) {
      showToast(dados.mensagem, dados.hardware_conectado ? "success" : "info");
    }
    atualizarDiagnosticoDispositivo();
  });

  // 3. Telemetria Serial TX/RX (Logs em Tempo Real)
  wsClient.on("log_serial", (dados) => {
    if (dados.evento) {
      adicionarLinhaTerminal(dados.evento);
    }
  });
}

function processarNovaLeitura(dados) {
  ultimaDataLeitura = new Date(dados.data_hora);

  // Timestamp
  const elHora = document.getElementById("dash-ultima-leitura");
  if (elHora) {
    elHora.innerText = ultimaDataLeitura.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  }

  if (dados.hardware_conectado !== undefined) {
    atualizarStatusHardwareHeader(dados.hardware_conectado);
  }

  // 1. Temperatura
  atualizarCardSensor(
    "temperatura",
    dados.temperatura,
    "°C",
    dados.status ? dados.status.temperatura : "ok",
    0, 50,
    leiturasAnteriores.temp
  );

  // 2. Umidade do Ar
  atualizarCardSensor(
    "umidade-ar",
    dados.umidade_ar,
    "%",
    dados.status ? dados.status.umidade_ar : "ok",
    0, 100,
    leiturasAnteriores.uar
  );

  // 3. Umidade do Solo
  atualizarCardSensor(
    "umidade-solo",
    dados.umidade_solo,
    "%",
    dados.status ? dados.status.umidade_solo : "ok",
    0, 100,
    leiturasAnteriores.usolo
  );

  // 4. Luminosidade
  atualizarCardSensor(
    "luminosidade",
    dados.luminosidade,
    "lx",
    dados.status ? dados.status.luminosidade : "ok",
    0, 1000,
    leiturasAnteriores.lum
  );

  // Armazena para cálculo de tendências na próxima amostragem
  leiturasAnteriores = {
    temp: dados.temperatura,
    uar: dados.umidade_ar,
    usolo: dados.umidade_solo,
    lum: dados.luminosidade
  };

  // 5. Cálculo Agronômico de VPD (Déficit de Pressão de Vapor)
  calcularEAtualizarVPD(dados.temperatura, dados.umidade_ar);

  // 6. Atualização do Gráfico em Tempo Real
  graficosManager.adicionarLeituraTempoReal(dados);

  // 7. Banners e Notificações de Alerta
  if (dados.alertas && dados.alertas.length > 0) {
    exibirBannerAlerta(dados.alertas[0]);
    recarregarAlertasRecentes();
  } else {
    fecharBannerAlerta();
  }
}

function atualizarCardSensor(idSufixo, valor, unidade, status, minEscala, maxEscala, valorAnterior) {
  const card = document.getElementById(`card-${idSufixo}`);
  const elVal = document.getElementById(`val-${idSufixo}`);
  const badge = document.getElementById(`badge-${idSufixo}`);
  const bar = document.getElementById(`bar-${idSufixo}`);
  const trendEl = document.getElementById(`trend-${idSufixo}`);

  if (elVal) {
    elVal.innerText = (valor !== null && valor !== undefined) ? valor.toFixed(1) : "--.-";
  }

  // Barra de progresso visual
  if (bar && valor !== null && valor !== undefined) {
    const pct = Math.min(100, Math.max(0, ((valor - minEscala) / (maxEscala - minEscala)) * 100));
    bar.style.width = `${pct}%`;
  }

  // Tendência (+/-)
  if (trendEl && valorAnterior !== null && valor !== null) {
    const diff = valor - valorAnterior;
    if (Math.abs(diff) >= 0.15) {
      if (diff > 0) {
        trendEl.innerHTML = `<span class="trend-icon" style="color:var(--emerald);">▲</span> <span class="trend-text">+${diff.toFixed(1)}</span>`;
      } else {
        trendEl.innerHTML = `<span class="trend-icon" style="color:var(--cyan);">▼</span> <span class="trend-text">${diff.toFixed(1)}</span>`;
      }
    } else {
      trendEl.innerHTML = `<span class="trend-icon">→</span> <span class="trend-text">estável</span>`;
    }
  }

  // Estilização do Status
  if (card && badge) {
    card.classList.remove("status-ok", "status-alerta", "status-critico", "status-offline");
    badge.classList.remove("pill-green", "pill-yellow", "pill-red", "pill-gray");

    if (status === "ok") {
      card.classList.add("status-ok");
      badge.classList.add("pill-green");
      badge.innerText = "Nominal";
      if (bar) bar.style.backgroundColor = "var(--emerald)";
    } else if (status === "alerta") {
      card.classList.add("status-alerta");
      badge.classList.add("pill-yellow");
      badge.innerText = "Tolerância";
      if (bar) bar.style.backgroundColor = "var(--amber)";
    } else if (status === "critico") {
      card.classList.add("status-critico");
      badge.classList.add("pill-red");
      badge.innerText = "Crítico";
      if (bar) bar.style.backgroundColor = "var(--rose)";
    } else {
      card.classList.add("status-offline");
      badge.classList.add("pill-gray");
      badge.innerText = "Offline";
      if (bar) bar.style.backgroundColor = "var(--gray)";
    }
  }
}

/* ==================== CÁLCULO DE DPV (VPD) ==================== */

function calcularEAtualizarVPD(temp, uar) {
  if (temp === null || uar === null || temp === undefined || uar === undefined) return;

  // Pressão de vapor de saturação (kPa) via fórmula padrão de Tetens
  const vpsat = 0.61078 * Math.exp((17.27 * temp) / (temp + 237.3));
  const vpair = vpsat * (uar / 100);
  const vpd = Math.max(0, vpsat - vpair);

  const elVpd = document.getElementById("val-vpd");
  const badgeVpd = document.getElementById("badge-vpd");
  if (elVpd) elVpd.innerText = vpd.toFixed(2);

  if (badgeVpd) {
    if (vpd >= 0.8 && vpd <= 1.2) {
      badgeVpd.innerText = "Transpiração Ótima";
      badgeVpd.style.color = "var(--emerald)";
      badgeVpd.style.background = "rgba(16, 185, 129, 0.2)";
    } else if (vpd < 0.5) {
      badgeVpd.innerText = "Umidade Excessiva";
      badgeVpd.style.color = "var(--cyan)";
      badgeVpd.style.background = "rgba(6, 182, 212, 0.2)";
    } else if (vpd > 1.4) {
      badgeVpd.innerText = "Estresse Hídrico";
      badgeVpd.style.color = "var(--rose)";
      badgeVpd.style.background = "rgba(244, 63, 94, 0.2)";
    } else {
      badgeVpd.innerText = "Moderado";
      badgeVpd.style.color = "var(--amber)";
      badgeVpd.style.background = "rgba(245, 158, 11, 0.2)";
    }
  }
}

function atualizarStatusHardwareHeader(conectado) {
  const dot = document.getElementById("dot-hardware");
  const label = document.getElementById("label-hardware");
  if (!dot || !label) return;

  if (conectado) {
    dot.className = "pill-indicator dot-online";
    label.innerText = "Arduino Conectado";
  } else {
    dot.className = "pill-indicator dot-offline";
    label.innerText = "Hardware Offline";
  }
}

/* ==================== ALERTAS & BANNERS ==================== */

function exibirBannerAlerta(texto) {
  const banner = document.getElementById("banner-alerta-topo");
  const txt = document.getElementById("banner-alerta-texto");
  if (banner && txt) {
    txt.innerText = texto;
    banner.classList.remove("hidden");
  }
}

function fecharBannerAlerta() {
  const banner = document.getElementById("banner-alerta-topo");
  if (banner) banner.classList.add("hidden");
}

async function recarregarAlertasRecentes() {
  try {
    const res = await fetch("/api/alertas?limite=10");
    const alertas = await res.json();
    const container = document.getElementById("lista-alertas-dashboard");
    const countBadge = document.getElementById("count-alertas-hoje");

    if (countBadge) countBadge.innerText = alertas.length;
    if (!container) return;

    if (alertas.length === 0) {
      container.innerHTML = `
        <div class="empty-alerts-state">
          <span class="empty-icon">✓</span>
          <p>Nenhuma violação registrada. Condições nominais.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = alertas.map(a => {
      const hora = new Date(a.data_hora).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      const classe = a.nivel === "critico" ? "alerta-critico" : "alerta-alerta";
      return `
        <div class="alerta-item-lux ${classe}">
          <div class="alerta-item-top">
            <strong>${a.metrica.toUpperCase()} (${a.valor})</strong>
            <span class="mono">${hora}</span>
          </div>
          <div>${a.mensagem}</div>
        </div>
      `;
    }).join("");
  } catch (e) {
    console.error("Erro alertas:", e);
  }
}

async function limparHistoricoAlertas() {
  try {
    await fetch("/api/alertas/limpar", { method: "DELETE" });
    recarregarAlertasRecentes();
    showToast("Histórico de alertas limpo.", "info");
  } catch (e) {
    showToast("Erro ao limpar alertas.", "error");
  }
}

/* ==================== CONTROLE DE IRRIGAÇÃO ==================== */

async function atualizarStatusIrrigacao() {
  try {
    const res = await fetch("/api/irrigacao/status");
    const s = await res.json();

    const badgeDash = document.getElementById("dash-badge-irrigacao");
    const badgeManual = document.getElementById("irrigacao-badge-status-manual");
    const modoDash = document.getElementById("dash-irrigacao-modo");
    const boxAcao = document.getElementById("box-acao-irrigando");
    const pumpCircle = document.getElementById("pump-circle-anim");
    const pumpTitle = document.getElementById("pump-status-title");
    const pumpDesc = document.getElementById("pump-status-desc");
    const timerCard = document.getElementById("status-irrigando-box");

    if (badgeDash) {
      badgeDash.innerText = s.irrigando ? "Operando" : "Standby";
      badgeDash.className = s.irrigando ? "status-pill pill-green" : "status-pill pill-gray";
    }

    if (badgeManual) {
      badgeManual.innerText = s.irrigando ? "Ligada" : "Desligada";
      badgeManual.className = s.irrigando ? "status-pill pill-green" : "status-pill pill-gray";
    }

    if (modoDash) modoDash.innerText = s.modo.toUpperCase();

    if (s.irrigando) {
      if (pumpCircle) pumpCircle.classList.add("active");
      if (pumpTitle) pumpTitle.innerText = "Bomba d'água LIGADA";
      if (pumpDesc) pumpDesc.innerText = `Vazão ativa em modo ${s.modo}`;
      if (boxAcao) boxAcao.classList.remove("hidden");
      if (timerCard) timerCard.classList.remove("hidden");
      iniciarContagemIrrigacao(s.tempo_restante_segundos);
    } else {
      if (pumpCircle) pumpCircle.classList.remove("active");
      if (pumpTitle) pumpTitle.innerText = "Bomba Desligada";
      if (pumpDesc) pumpDesc.innerText = "Aguardando gatilho de solo ou disparo manual";
      if (boxAcao) boxAcao.classList.add("hidden");
      if (timerCard) timerCard.classList.add("hidden");
      pararContagemIrrigacao();
    }
  } catch (e) {
    console.error("Erro status irrigação:", e);
  }
}

function iniciarContagemIrrigacao(segundos) {
  duracaoIrrigacaoRestante = segundos;
  duracaoIrrigacaoTotal = Math.max(duracaoIrrigacaoTotal, segundos);
  atualizarDisplayTimerIrrigacao();

  pararContagemIrrigacao();
  timerIrrigacaoInterval = setInterval(() => {
    duracaoIrrigacaoRestante--;
    if (duracaoIrrigacaoRestante <= 0) {
      pararContagemIrrigacao();
      atualizarStatusIrrigacao();
      carregarHistoricoIrrigacoes();
    } else {
      atualizarDisplayTimerIrrigacao();
    }
  }, 1000);
}

function pararContagemIrrigacao() {
  if (timerIrrigacaoInterval) {
    clearInterval(timerIrrigacaoInterval);
    timerIrrigacaoInterval = null;
  }
}

function atualizarDisplayTimerIrrigacao() {
  const elDash = document.getElementById("timer-irrigacao-segundos");
  const elPage = document.getElementById("span-tempo-irrigando");
  const bar = document.getElementById("bar-tempo-irrigando");

  if (elDash) elDash.innerText = `${duracaoIrrigacaoRestante}s`;
  if (elPage) elPage.innerText = `${duracaoIrrigacaoRestante}`;

  if (bar && duracaoIrrigacaoTotal > 0) {
    const pct = Math.max(0, Math.min(100, (duracaoIrrigacaoRestante / duracaoIrrigacaoTotal) * 100));
    bar.style.width = `${pct}%`;
  }
}

async function acionarIrrigacaoManual(segundos) {
  try {
    duracaoIrrigacaoTotal = segundos;
    const res = await fetch("/api/irrigacao/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duracao_segundos: segundos })
    });
    const dados = await res.json();
    if (!res.ok) throw new Error(dados.detail || "Erro ao acionar bomba.");

    showToast(`Bomba d'água ativada por ${segundos}s!`, "success");
    atualizarStatusIrrigacao();
    setTimeout(carregarHistoricoIrrigacoes, 1500);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function pararIrrigacaoManual() {
  try {
    await fetch("/api/irrigacao/parar", { method: "POST" });
    showToast("Comando de parada executado.", "info");
    atualizarStatusIrrigacao();
    setTimeout(carregarHistoricoIrrigacoes, 1000);
  } catch (err) {
    showToast("Erro ao parar irrigação.", "error");
  }
}

async function carregarHistoricoIrrigacoes() {
  try {
    const res = await fetch("/api/irrigacao/historico?limite=15");
    const lista = await res.json();
    const tbody = document.getElementById("tabela-irrigacoes-corpo");
    if (!tbody) return;

    if (lista.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Nenhum acionamento auditado até o momento.</td></tr>';
      return;
    }

    tbody.innerHTML = lista.map(item => {
      const dt = new Date(item.data_hora_inicio).toLocaleString("pt-BR");
      const statusBadge = item.status === "concluido" ? "pill-green" : "pill-yellow";
      return `
        <tr>
          <td class="mono">${dt}</td>
          <td class="mono font-bold">${item.duracao_segundos || 0}s</td>
          <td><span class="status-pill pill-gray">${item.modo.toUpperCase()}</span></td>
          <td>${item.motivo}</td>
          <td class="mono">${item.umidade_solo_inicial !== null ? item.umidade_solo_inicial + "%" : "--"}</td>
          <td class="mono">${item.umidade_solo_final !== null ? item.umidade_solo_final + "%" : "--"}</td>
          <td><span class="status-pill ${statusBadge}">${item.status}</span></td>
        </tr>
      `;
    }).join("");
  } catch (e) {
    console.error("Erro histórico irrigação:", e);
  }
}

/* ==================== HISTÓRICO & FILTROS ==================== */

let periodoHistoricoAtivo = "1h";

async function carregarTabelaEGraficoHistorico() {
  const metrica = document.getElementById("filtro-metrica")?.value || "";
  const limite = parseInt(document.getElementById("filtro-limite")?.value || "200", 10);

  const leituras = await graficosManager.carregarHistorico(periodoHistoricoAtivo, metrica, limite);
  renderizarTabelaHistorico(leituras);
}

function renderizarTabelaHistorico(leituras) {
  const tbody = document.getElementById("tabela-historico-corpo");
  if (!tbody) return;

  if (leituras.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Nenhum registro para os filtros selecionados.</td></tr>';
    return;
  }

  const copia = [...leituras].reverse();

  tbody.innerHTML = copia.slice(0, 100).map(l => {
    const dt = new Date(l.data_hora).toLocaleString("pt-BR");
    return `
      <tr>
        <td class="mono text-muted">${dt}</td>
        <td class="mono font-bold">${l.temperatura !== undefined ? l.temperatura.toFixed(1) + "°C" : "--"}</td>
        <td class="mono">${l.umidade_ar !== undefined ? l.umidade_ar.toFixed(1) + "%" : "--"}</td>
        <td class="mono text-emerald">${l.umidade_solo !== undefined ? l.umidade_solo.toFixed(1) + "%" : "--"}</td>
        <td class="mono">${l.luminosidade !== undefined ? l.luminosidade.toFixed(0) + " lx" : "--"}</td>
        <td class="mono">${l.co2 !== null && l.co2 !== undefined ? l.co2 + " ppm" : "--"}</td>
        <td><span class="status-pill pill-green">OK</span></td>
      </tr>
    `;
  }).join("");
}

/* ==================== HARDWARE, PORTAS & TERMINAL SERIAL ==================== */

async function carregarPortasSeriaisDisponiveis() {
  try {
    const res = await fetch("/api/dispositivo/portas");
    const json = await res.json();
    const select = document.getElementById("select-portas-seriais");
    const descEl = document.getElementById("port-details-desc");

    if (!select) return;

    const portas = json.portas_disponiveis || [];
    if (portas.length === 0) {
      select.innerHTML = '<option value="">Nenhuma porta serial detectada</option>';
      if (descEl) descEl.innerText = "Nenhum Arduino detectado. Conecte o cabo USB para atualizar.";
      return;
    }

    select.innerHTML = portas.map(p => {
      const destaque = p.is_probable_arduino ? " (Arduino / Placa USB)" : "";
      return `<option value="${p.device}" ${p.is_probable_arduino ? 'selected' : ''}>${p.device} — ${p.description}${destaque}</option>`;
    }).join("");

    if (descEl && select.selectedIndex >= 0) {
      const selecionada = portas[select.selectedIndex];
      descEl.innerText = `Driver: ${selecionada.description || 'Padrão'} | HWID: ${selecionada.hwid || 'N/A'}`;
    }
  } catch (e) {
    console.error("Erro portas seriais:", e);
  }
}

async function atualizarDiagnosticoDispositivo() {
  try {
    const res = await fetch("/api/dispositivo/status");
    const st = await res.json();

    const badge = document.getElementById("badge-dispositivo-status");
    if (badge) {
      badge.innerText = st.conectado ? (st.modo_simulacao ? "Modo Simulação" : "Conectado") : "Desconectado";
      badge.className = st.conectado ? "status-pill pill-green" : "status-pill pill-red";
    }

    const _set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    };

    _set("disp-porta", st.porta);
    _set("disp-baud", `${st.baudrate} bps`);
    _set("disp-simulacao", st.modo_simulacao ? "Simulação Virtual" : "Hardware Físico");
    _set("disp-total-leituras", st.total_leituras_recebidas);
    _set("disp-erros", st.erros_conexao);
    _set("disp-uptime", `${st.tempo_ativo_segundos}s`);
  } catch (e) {
    console.error("Erro diagnóstico:", e);
  }
}

async function carregarLogsTerminalIniciais() {
  try {
    const res = await fetch("/api/dispositivo/logs");
    const json = await res.json();
    const logs = json.logs || [];
    const term = document.getElementById("terminal-serial-logs");
    if (!term) return;

    term.innerHTML = "";
    if (logs.length === 0) {
      term.innerHTML = '<div class="term-line term-info">[SYSTEM] Terminal de telemetria ativo. Aguardando pacotes do Arduino...</div>';
      return;
    }

    logs.forEach(evento => adicionarLinhaTerminal(evento));
  } catch (e) {
    console.error("Erro logs:", e);
  }
}

function adicionarLinhaTerminal(evento) {
  const term = document.getElementById("terminal-serial-logs");
  if (!term) return;

  const linha = document.createElement("div");
  linha.className = "term-line";

  const dir = evento.direcao || "INFO";
  let classeCor = "term-info";
  if (dir.includes("RX")) classeCor = "term-rx";
  else if (dir.includes("TX")) classeCor = "term-tx";
  else if (dir.includes("ERRO")) classeCor = "term-erro";
  else if (dir.includes("ALERTA")) classeCor = "term-alerta";

  linha.innerHTML = `<span class="text-muted">[${evento.timestamp}]</span> <span class="${classeCor}">[${dir}]</span> ${evento.conteudo}`;
  term.appendChild(linha);

  // Mantém máximo de 100 linhas no DOM
  if (term.childNodes.length > 120) {
    term.removeChild(term.firstChild);
  }

  if (terminalAutoScroll) {
    term.scrollTop = term.scrollHeight;
  }
}

/* ==================== CONFIGURAÇÃO DE EVENTOS UI ==================== */

function configurarEventosUI() {
  // Conectar Porta Selecionada
  document.getElementById("btn-conectar-porta-selecionada")?.addEventListener("click", async () => {
    const porta = document.getElementById("select-portas-seriais")?.value;
    const baud = parseInt(document.getElementById("select-baudrate")?.value || "9600", 10);
    if (!porta) {
      showToast("Nenhuma porta selecionada.", "error");
      return;
    }

    showToast(`Conectando em ${porta} @ ${baud}bps...`, "info");
    try {
      const res = await fetch("/api/dispositivo/conectar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ porta: porta, baudrate: baud })
      });
      const data = await res.json();
      atualizarDiagnosticoDispositivo();
      showToast(data.mensagem || "Porta conectada!", data.conectado ? "success" : "info");
    } catch (e) {
      showToast("Erro ao conectar à porta.", "error");
    }
  });

  // Auto-detectar & Reconectar
  document.getElementById("btn-reconectar-serial")?.addEventListener("click", async () => {
    showToast("Escaneando portas USB e reconectando...", "info");
    try {
      const res = await fetch("/api/dispositivo/reconectar", { method: "POST" });
      const data = await res.json();
      carregarPortasSeriaisDisponiveis();
      atualizarDiagnosticoDispositivo();
      showToast(data.mensagem, data.conectado ? "success" : "info");
    } catch (e) {
      showToast("Falha na reconexão.", "error");
    }
  });

  // Terminal Serial: Enviar Comando Manual
  const inputCmd = document.getElementById("input-comando-serial-manual");
  const btnEnviarCmd = document.getElementById("btn-enviar-comando-serial");

  const executarEnvioComando = async () => {
    const cmd = inputCmd?.value.trim();
    if (!cmd) return;
    try {
      await fetch("/api/dispositivo/enviar_comando", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comando: cmd })
      });
      if (inputCmd) inputCmd.value = "";
    } catch (e) {
      showToast("Erro ao transmitir comando.", "error");
    }
  };

  btnEnviarCmd?.addEventListener("click", executarEnvioComando);
  inputCmd?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") executarEnvioComando();
  });

  // Limpar Terminal
  document.getElementById("btn-limpar-console")?.addEventListener("click", () => {
    const term = document.getElementById("terminal-serial-logs");
    if (term) term.innerHTML = '<div class="term-line term-info">[SYSTEM] Console limpo.</div>';
  });

  // Toggle Auto-scroll
  const btnAutoScroll = document.getElementById("btn-toggle-autoscroll");
  btnAutoScroll?.addEventListener("click", () => {
    terminalAutoScroll = !terminalAutoScroll;
    btnAutoScroll.classList.toggle("active", terminalAutoScroll);
    btnAutoScroll.innerText = terminalAutoScroll ? "Auto-scroll ON" : "Auto-scroll OFF";
  });

  // Botões de Irrigação Rápida
  document.getElementById("btn-dash-irrigar-rapido")?.addEventListener("click", () => {
    acionarIrrigacaoManual(10);
  });

  document.getElementById("btn-dash-parar-irrigacao")?.addEventListener("click", () => {
    pararIrrigacaoManual();
  });

  document.getElementById("btn-iniciar-irrigacao-manual")?.addEventListener("click", () => {
    const customVal = document.getElementById("irrigacao-duracao-custom")?.value;
    const seg = parseInt(customVal || "10", 10);
    acionarIrrigacaoManual(seg);
  });

  document.getElementById("btn-parar-irrigacao-imediato")?.addEventListener("click", () => {
    pararIrrigacaoManual();
  });

  // Pílulas de Duração
  document.querySelectorAll(".pill-duracao").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".pill-duracao").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      const d = pill.getAttribute("data-duracao");
      const input = document.getElementById("irrigacao-duracao-custom");
      if (input) input.value = d;
    });
  });

  // Salvar Regras de Irrigação
  document.getElementById("btn-salvar-regras-irrigacao")?.addEventListener("click", async () => {
    try {
      await configManager.salvarRegrasIrrigacao();
      showToast("Regras de irrigação salvas no banco!", "success");
      atualizarStatusIrrigacao();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Salvar Configurações Gerais
  document.getElementById("form-configuracoes")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await configManager.salvarConfiguracoesGerais();
      showToast("Faixas ideais atualizadas com sucesso!", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Restaurar Padrões
  document.getElementById("btn-restaurar-configs-padrao")?.addEventListener("click", async () => {
    if (confirm("Deseja restaurar todas as faixas e tolerâncias padrão?")) {
      try {
        await configManager.restaurarPadroes();
        showToast("Padrões de microclima restaurados!", "info");
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });

  // Filtros de Período do Histórico
  document.querySelectorAll(".btn-periodo").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-periodo").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      periodoHistoricoAtivo = btn.getAttribute("data-periodo");
      carregarTabelaEGraficoHistorico();
    });
  });

  document.getElementById("btn-aplicar-filtro-historico")?.addEventListener("click", () => {
    carregarTabelaEGraficoHistorico();
  });

  document.getElementById("btn-exportar-csv")?.addEventListener("click", exportarTabelaCSV);
}

function aplicarPreset(tipo) {
  configManager.aplicarPresetCultura(tipo);
  showToast(`Preset de ${tipo.toUpperCase()} carregado no formulário! Clique em salvar para persistir.`, "info");
}

/* ==================== UTILITÁRIOS ==================== */

async function carregarEstadoInicial() {
  try {
    const res = await fetch("/api/leituras/atual");
    const dados = await res.json();
    if (dados.disponivel) {
      processarNovaLeitura(dados);
    }
    recarregarAlertasRecentes();
    atualizarStatusIrrigacao();
    atualizarDiagnosticoDispositivo();
  } catch (e) {
    console.error("Erro estado inicial:", e);
  }
}

function iniciarTimerRelativo() {
  if (timerRelativoInterval) clearInterval(timerRelativoInterval);
  timerRelativoInterval = setInterval(() => {
    const elRel = document.getElementById("dash-tempo-relativo");
    if (!elRel || !ultimaDataLeitura) return;

    const diffSeg = Math.floor((new Date() - ultimaDataLeitura) / 1000);
    if (diffSeg < 5) elRel.innerText = "(agora mesmo)";
    else if (diffSeg < 60) elRel.innerText = `(${diffSeg}s atrás)`;
    else elRel.innerText = `(${Math.floor(diffSeg / 60)}m atrás)`;
  }, 2000);
}

function showToast(mensagem, tipo = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast-lux ${tipo}`;

  const icones = { success: "✅", error: "❌", info: "ℹ️" };
  toast.innerHTML = `<span>${icones[tipo] || "ℹ️"}</span> <span>${mensagem}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.25s ease";
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

function exportarTabelaCSV() {
  const rows = document.querySelectorAll("#tabela-historico tr");
  let csv = [];
  rows.forEach(row => {
    const cols = row.querySelectorAll("td, th");
    let rowData = [];
    cols.forEach(col => rowData.push(`"${col.innerText.trim()}"`));
    csv.push(rowData.join(","));
  });

  const blob = new Blob([csv.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `aeroflora_telemetria_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
