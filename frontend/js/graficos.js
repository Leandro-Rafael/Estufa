/**
 * Visualizador Gráfico Profissional (AeroFlora OS).
 * Renderiza gráficos com gradientes suaves, eixos de alta precisão e filtros de visualização.
 */

class GraficosManager {
  constructor() {
    this.graficoTempoReal = null;
    this.graficoHistorico = null;
    this.maxPontosTempoReal = 50;
    this.modoVisualizacao = "all"; // all | clima | solo
  }

  inicializar() {
    this._configurarGraficoTempoReal();
    this._configurarGraficoHistorico();
    this._configurarFiltrosVisuais();
  }

  _configurarGraficoTempoReal() {
    const canvas = document.getElementById("grafico-tempo-real");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    // Cria gradientes sutis para as curvas
    const gradTemp = ctx.createLinearGradient(0, 0, 0, 300);
    gradTemp.addColorStop(0, "rgba(244, 63, 94, 0.25)");
    gradTemp.addColorStop(1, "rgba(244, 63, 94, 0.0)");

    const gradAir = ctx.createLinearGradient(0, 0, 0, 300);
    gradAir.addColorStop(0, "rgba(6, 182, 212, 0.25)");
    gradAir.addColorStop(1, "rgba(6, 182, 212, 0.0)");

    const gradSoil = ctx.createLinearGradient(0, 0, 0, 300);
    gradSoil.addColorStop(0, "rgba(16, 185, 129, 0.28)");
    gradSoil.addColorStop(1, "rgba(16, 185, 129, 0.0)");

    this.graficoTempoReal = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Temperatura (°C)",
            data: [],
            borderColor: "#f43f5e",
            backgroundColor: gradTemp,
            fill: true,
            yAxisID: "y",
            tension: 0.35,
            borderWidth: 2.2,
            pointRadius: 0,
            pointHoverRadius: 6,
            pointBackgroundColor: "#f43f5e"
          },
          {
            label: "Umidade Ar (%)",
            data: [],
            borderColor: "#06b6d4",
            backgroundColor: gradAir,
            fill: true,
            yAxisID: "y",
            tension: 0.35,
            borderWidth: 2.2,
            pointRadius: 0,
            pointHoverRadius: 6,
            pointBackgroundColor: "#06b6d4"
          },
          {
            label: "Umidade Solo (%)",
            data: [],
            borderColor: "#10b981",
            backgroundColor: gradSoil,
            fill: true,
            yAxisID: "y",
            tension: 0.35,
            borderWidth: 2.6,
            pointRadius: 0,
            pointHoverRadius: 6,
            pointBackgroundColor: "#10b981"
          },
          {
            label: "Luminosidade (lux)",
            data: [],
            borderColor: "#f59e0b",
            backgroundColor: "transparent",
            yAxisID: "y1",
            tension: 0.35,
            borderWidth: 1.5,
            borderDash: [4, 4],
            pointRadius: 0,
            pointHoverRadius: 5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 250 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            labels: {
              color: "#94a3b8",
              boxWidth: 10,
              padding: 16,
              font: { family: "Plus Jakarta Sans", size: 11, weight: 600 }
            }
          },
          tooltip: {
            backgroundColor: "rgba(13, 18, 28, 0.95)",
            titleColor: "#ffffff",
            bodyColor: "#94a3b8",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8,
            titleFont: { family: "Plus Jakarta Sans", weight: 700 },
            bodyFont: { family: "JetBrains Mono" }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.03)" },
            ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 9 }, maxRotation: 0 }
          },
          y: {
            type: "linear",
            display: true,
            position: "left",
            min: 0,
            max: 100,
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: {
              color: "#94a3b8",
              font: { family: "JetBrains Mono", size: 10 },
              callback: (v) => `${v}% / °C`
            }
          },
          y1: {
            type: "linear",
            display: true,
            position: "right",
            min: 0,
            max: 1000,
            grid: { drawOnChartArea: false },
            ticks: {
              color: "#f59e0b",
              font: { family: "JetBrains Mono", size: 9 },
              callback: (v) => `${v} lx`
            }
          }
        }
      }
    });
  }

  _configurarFiltrosVisuais() {
    document.querySelectorAll(".pill-btn[data-chart-view]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".pill-btn[data-chart-view]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.modoVisualizacao = btn.getAttribute("data-chart-view");
        this._aplicarModoVisualizacao();
      });
    });
  }

  _aplicarModoVisualizacao() {
    if (!this.graficoTempoReal) return;
    const chart = this.graficoTempoReal;

    if (this.modoVisualizacao === "clima") {
      chart.setDatasetVisibility(0, true);  // Temp
      chart.setDatasetVisibility(1, true);  // Air
      chart.setDatasetVisibility(2, false); // Soil
      chart.setDatasetVisibility(3, false); // Light
    } else if (this.modoVisualizacao === "solo") {
      chart.setDatasetVisibility(0, false);
      chart.setDatasetVisibility(1, false);
      chart.setDatasetVisibility(2, true);
      chart.setDatasetVisibility(3, true);
    } else {
      chart.setDatasetVisibility(0, true);
      chart.setDatasetVisibility(1, true);
      chart.setDatasetVisibility(2, true);
      chart.setDatasetVisibility(3, true);
    }
    chart.update("none");
  }

  adicionarLeituraTempoReal(leitura) {
    if (!this.graficoTempoReal) return;

    const horaFormatada = new Date(leitura.data_hora).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });

    const chart = this.graficoTempoReal;
    chart.data.labels.push(horaFormatada);
    chart.data.datasets[0].data.push(leitura.temperatura);
    chart.data.datasets[1].data.push(leitura.umidade_ar);
    chart.data.datasets[2].data.push(leitura.umidade_solo);
    chart.data.datasets[3].data.push(leitura.luminosidade);

    if (chart.data.labels.length > this.maxPontosTempoReal) {
      chart.data.labels.shift();
      chart.data.datasets.forEach(ds => ds.data.shift());
    }

    chart.update("none");
  }

  _configurarGraficoHistorico() {
    const canvas = document.getElementById("grafico-historico");
    if (!canvas) return;

    this.graficoHistorico = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#94a3b8", boxWidth: 12, padding: 16 }
          },
          tooltip: {
            backgroundColor: "rgba(13, 18, 28, 0.95)",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.03)" },
            ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#94a3b8" }
          }
        }
      }
    });
  }

  async carregarHistorico(periodo = "1h", metrica = "", limite = 200) {
    const infoLabel = document.getElementById("historico-pontos-info");
    if (infoLabel) infoLabel.innerText = "Consultando telemetria...";

    try {
      let url = `/api/leituras/historico?periodo=${periodo}&limite=${limite}`;
      if (metrica) url += `&metrica=${metrica}`;

      const res = await fetch(url);
      const json = await res.json();
      const leituras = json.dados || [];

      if (infoLabel) {
        infoLabel.innerText = `${leituras.length} amostras registradas (médias de 10 em 10 min • ${periodo})`;
      }

      this._atualizarGraficoHistorico(leituras, metrica);
      return leituras;
    } catch (err) {
      console.error("[Graficos] Erro:", err);
      if (infoLabel) infoLabel.innerText = "Falha ao carregar telemetria";
      return [];
    }
  }

  _atualizarGraficoHistorico(leituras, metricaFiltro) {
    if (!this.graficoHistorico) return;

    const labels = leituras.map(l => {
      const dt = new Date(l.data_hora);
      return dt.toLocaleDateString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    });

    let datasets = [];

    if (!metricaFiltro || metricaFiltro === "temperatura") {
      datasets.push({
        label: "Temperatura (°C)",
        data: leituras.map(l => l.temperatura),
        borderColor: "#f43f5e",
        backgroundColor: "rgba(244, 63, 94, 0.15)",
        tension: 0.3,
        borderWidth: 2.2,
        fill: true,
        pointRadius: 2
      });
    }

    if (!metricaFiltro || metricaFiltro === "umidade_ar") {
      datasets.push({
        label: "Umidade Ar (%)",
        data: leituras.map(l => l.umidade_ar),
        borderColor: "#06b6d4",
        backgroundColor: "rgba(6, 182, 212, 0.15)",
        tension: 0.3,
        borderWidth: 2.2,
        fill: true,
        pointRadius: 2
      });
    }

    if (!metricaFiltro || metricaFiltro === "umidade_solo") {
      datasets.push({
        label: "Umidade Solo (%)",
        data: leituras.map(l => l.umidade_solo),
        borderColor: "#10b981",
        backgroundColor: "rgba(16, 185, 129, 0.15)",
        tension: 0.3,
        borderWidth: 2.5,
        fill: true,
        pointRadius: 2
      });
    }

    if (!metricaFiltro || metricaFiltro === "luminosidade") {
      datasets.push({
        label: "Luminosidade (lux)",
        data: leituras.map(l => l.luminosidade),
        borderColor: "#f59e0b",
        backgroundColor: "rgba(245, 158, 11, 0.1)",
        tension: 0.3,
        borderWidth: 1.5,
        pointRadius: 1
      });
    }

    this.graficoHistorico.data.labels = labels;
    this.graficoHistorico.data.datasets = datasets;
    this.graficoHistorico.update();
  }
}

const graficosManager = new GraficosManager();
