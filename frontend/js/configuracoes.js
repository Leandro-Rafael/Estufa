/**
 * Gerenciador de Parâmetros e Presets Biológicos (AeroFlora OS).
 */

class ConfiguracoesManager {
  constructor() {
    this.configs = {};
  }

  async carregar() {
    try {
      const res = await fetch("/api/configuracoes");
      if (!res.ok) throw new Error("Falha ao consultar configurações.");
      this.configs = await res.json();
      this.preencherFormularios(this.configs);
      this.atualizarDicasDashboard(this.configs);
      return this.configs;
    } catch (err) {
      console.error("[Config] Erro:", err);
      return null;
    }
  }

  preencherFormularios(c) {
    this._setVal("cfg_temp_min", c.temperatura_min);
    this._setVal("cfg_temp_max", c.temperatura_max);
    this._setVal("cfg_temp_tol", c.tolerancia_temperatura);

    this._setVal("cfg_uar_min", c.umidade_ar_min);
    this._setVal("cfg_uar_max", c.umidade_ar_max);
    this._setVal("cfg_uar_tol", c.tolerancia_umidade_ar);

    this._setVal("cfg_usolo_min", c.umidade_solo_min);
    this._setVal("cfg_usolo_max", c.umidade_solo_max);
    this._setVal("cfg_usolo_tol", c.tolerancia_umidade_solo);

    this._setVal("cfg_lum_min", c.luminosidade_min);
    this._setVal("cfg_lum_max", c.luminosidade_max);
    this._setVal("cfg_lum_tol", c.tolerancia_luminosidade);

    this._setVal("cfg_intervalo", c.intervalo_leitura);
    const chkAlertas = document.getElementById("cfg_alertas_ativos");
    if (chkAlertas) chkAlertas.checked = !!c.alertas_ativos;

    const chkIrrigAuto = document.getElementById("cfg_irrigacao_automatica");
    if (chkIrrigAuto) chkIrrigAuto.checked = !!c.irrigacao_automatica;

    this._setVal("cfg_irrigacao_solo_min", c.irrigacao_solo_min);
    this._setVal("cfg_irrigacao_solo_max", c.irrigacao_solo_max);
    this._setVal("cfg_irrigacao_tempo_max", c.tempo_max_irrigacao);
    this._setVal("cfg_irrigacao_intervalo_espera", c.intervalo_espera_irrigacao);
  }

  _setVal(id, val) {
    const el = document.getElementById(id);
    if (el && val !== undefined) el.value = val;
  }

  atualizarDicasDashboard(c) {
    // 1. Temperatura (escala 0 a 50°C)
    const hintTemp = document.getElementById("hint-temperatura");
    if (hintTemp) hintTemp.innerText = `Ideal: ${c.temperatura_min} a ${c.temperatura_max}°C (±${c.tolerancia_temperatura}°C)`;
    const tMin = document.getElementById("hint-temp-min");
    const tMax = document.getElementById("hint-temp-max");
    if (tMin) tMin.innerText = `${c.temperatura_min}°C`;
    if (tMax) tMax.innerText = `${c.temperatura_max}°C`;
    this._posicionarZona("zone-temperatura", c.temperatura_min, c.temperatura_max, 0, 50);

    // 2. Umidade Ar (escala 0 a 100%)
    const hintUar = document.getElementById("hint-umidade-ar");
    if (hintUar) hintUar.innerText = `Ideal: ${c.umidade_ar_min} a ${c.umidade_ar_max}%`;
    const uMin = document.getElementById("hint-uar-min");
    const uMax = document.getElementById("hint-uar-max");
    if (uMin) uMin.innerText = `${c.umidade_ar_min}%`;
    if (uMax) uMax.innerText = `${c.umidade_ar_max}%`;
    this._posicionarZona("zone-umidade-ar", c.umidade_ar_min, c.umidade_ar_max, 0, 100);

    // 3. Umidade Solo (escala 0 a 100%)
    const hintUsolo = document.getElementById("hint-umidade-solo");
    if (hintUsolo) hintUsolo.innerText = `Ideal: ${c.umidade_solo_min} a ${c.umidade_solo_max}%`;
    const sMin = document.getElementById("hint-usolo-min");
    const sMax = document.getElementById("hint-usolo-max");
    if (sMin) sMin.innerText = `${c.umidade_solo_min}%`;
    if (sMax) sMax.innerText = `${c.umidade_solo_max}%`;
    this._posicionarZona("zone-umidade-solo", c.umidade_solo_min, c.umidade_solo_max, 0, 100);

    // 4. Luminosidade (escala 0 a 1000 lux)
    const hintLum = document.getElementById("hint-luminosidade");
    if (hintLum) hintLum.innerText = `Ideal: ${c.luminosidade_min} a ${c.luminosidade_max} lx`;
    const lMin = document.getElementById("hint-lum-min");
    const lMax = document.getElementById("hint-lum-max");
    if (lMin) lMin.innerText = `${c.luminosidade_min} lx`;
    if (lMax) lMax.innerText = `${c.luminosidade_max} lx`;
    this._posicionarZona("zone-luminosidade", c.luminosidade_min, c.luminosidade_max, 0, 1000);

    // Resumo de Irrigação
    const elIrrigInfo = document.getElementById("dash-irrigacao-trigger-info");
    if (elIrrigInfo) elIrrigInfo.innerText = `Solo < ${c.irrigacao_solo_min}%`;

    const elIrrigAuto = document.getElementById("dash-irrigacao-auto-status");
    if (elIrrigAuto) {
      elIrrigAuto.innerText = c.irrigacao_automatica ? "Ativada" : "Desativada";
      elIrrigAuto.className = c.irrigacao_automatica ? "text-emerald font-bold" : "text-muted";
    }
  }

  _posicionarZona(id, minVal, maxVal, minEscala, maxEscala) {
    const el = document.getElementById(id);
    if (!el) return;
    const rangeTotal = maxEscala - minEscala;
    const leftPct = Math.max(0, Math.min(100, ((minVal - minEscala) / rangeTotal) * 100));
    const widthPct = Math.max(0, Math.min(100 - leftPct, ((maxVal - minVal) / rangeTotal) * 100));
    el.style.left = `${leftPct}%`;
    el.style.width = `${widthPct}%`;
  }

  async salvarConfiguracoesGerais() {
    const payload = {
      temperatura_min: parseFloat(document.getElementById("cfg_temp_min").value),
      temperatura_max: parseFloat(document.getElementById("cfg_temp_max").value),
      tolerancia_temperatura: parseFloat(document.getElementById("cfg_temp_tol").value),

      umidade_ar_min: parseFloat(document.getElementById("cfg_uar_min").value),
      umidade_ar_max: parseFloat(document.getElementById("cfg_uar_max").value),
      tolerancia_umidade_ar: parseFloat(document.getElementById("cfg_uar_tol").value),

      umidade_solo_min: parseFloat(document.getElementById("cfg_usolo_min").value),
      umidade_solo_max: parseFloat(document.getElementById("cfg_usolo_max").value),
      tolerancia_umidade_solo: parseFloat(document.getElementById("cfg_usolo_tol").value),

      luminosidade_min: parseFloat(document.getElementById("cfg_lum_min").value),
      luminosidade_max: parseFloat(document.getElementById("cfg_lum_max").value),
      tolerancia_luminosidade: parseFloat(document.getElementById("cfg_lum_tol").value),

      intervalo_leitura: parseInt(document.getElementById("cfg_intervalo").value, 10),
      alertas_ativos: document.getElementById("cfg_alertas_ativos").checked
    };

    const res = await fetch("/api/configuracoes", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Erro ao persistir configurações.");
    this.configs = await res.json();
    this.atualizarDicasDashboard(this.configs);
    return this.configs;
  }

  async salvarRegrasIrrigacao() {
    const payload = {
      irrigacao_automatica: document.getElementById("cfg_irrigacao_automatica").checked,
      irrigacao_solo_min: parseFloat(document.getElementById("cfg_irrigacao_solo_min").value),
      irrigacao_solo_max: parseFloat(document.getElementById("cfg_irrigacao_solo_max").value),
      tempo_max_irrigacao: parseInt(document.getElementById("cfg_irrigacao_tempo_max").value, 10),
      intervalo_espera_irrigacao: parseInt(document.getElementById("cfg_irrigacao_intervalo_espera").value, 10)
    };

    const res = await fetch("/api/irrigacao/configuracoes", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Erro ao salvar regras de irrigação.");
    this.configs = await res.json();
    this.atualizarDicasDashboard(this.configs);
    return this.configs;
  }

  aplicarPresetCultura(tipo) {
    const presets = {
      hortalicas: {
        temp_min: 18.0, temp_max: 24.0, temp_tol: 2.0,
        uar_min: 60.0, uar_max: 75.0, uar_tol: 5.0,
        usolo_min: 55.0, usolo_max: 75.0, usolo_tol: 5.0,
        lum_min: 350.0, lum_max: 700.0, lum_tol: 50.0
      },
      tomate: {
        temp_min: 21.0, temp_max: 27.0, temp_tol: 2.0,
        uar_min: 55.0, uar_max: 70.0, uar_tol: 5.0,
        usolo_min: 50.0, usolo_max: 70.0, usolo_tol: 5.0,
        lum_min: 500.0, lum_max: 900.0, lum_tol: 50.0
      },
      orquideas: {
        temp_min: 18.0, temp_max: 28.0, temp_tol: 3.0,
        uar_min: 60.0, uar_max: 80.0, uar_tol: 5.0,
        usolo_min: 35.0, usolo_max: 55.0, usolo_tol: 5.0,
        lum_min: 200.0, lum_max: 500.0, lum_tol: 50.0
      },
      suculentas: {
        temp_min: 20.0, temp_max: 32.0, temp_tol: 3.0,
        uar_min: 30.0, uar_max: 50.0, uar_tol: 5.0,
        usolo_min: 20.0, usolo_max: 40.0, usolo_tol: 5.0,
        lum_min: 600.0, lum_max: 1000.0, lum_tol: 50.0
      }
    };

    const p = presets[tipo];
    if (!p) return;

    this._setVal("cfg_temp_min", p.temp_min);
    this._setVal("cfg_temp_max", p.temp_max);
    this._setVal("cfg_temp_tol", p.temp_tol);

    this._setVal("cfg_uar_min", p.uar_min);
    this._setVal("cfg_uar_max", p.uar_max);
    this._setVal("cfg_uar_tol", p.uar_tol);

    this._setVal("cfg_usolo_min", p.usolo_min);
    this._setVal("cfg_usolo_max", p.usolo_max);
    this._setVal("cfg_usolo_tol", p.usolo_tol);

    this._setVal("cfg_lum_min", p.lum_min);
    this._setVal("cfg_lum_max", p.lum_max);
    this._setVal("cfg_lum_tol", p.lum_tol);
  }

  async restaurarPadroes() {
    const padroes = {
      temperatura_min: 20.0,
      temperatura_max: 28.0,
      tolerancia_temperatura: 2.0,
      umidade_ar_min: 50.0,
      umidade_ar_max: 70.0,
      tolerancia_umidade_ar: 5.0,
      umidade_solo_min: 40.0,
      umidade_solo_max: 70.0,
      tolerancia_umidade_solo: 5.0,
      luminosidade_min: 400.0,
      luminosidade_max: 850.0,
      tolerancia_luminosidade: 50.0,
      intervalo_leitura: 5,
      alertas_ativos: true,
      irrigacao_automatica: false,
      irrigacao_solo_min: 35.0,
      irrigacao_solo_max: 65.0,
      tempo_max_irrigacao: 20,
      intervalo_espera_irrigacao: 300
    };

    const res = await fetch("/api/configuracoes", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(padroes)
    });

    if (!res.ok) throw new Error("Erro ao restaurar padrões.");
    this.configs = await res.json();
    this.preencherFormularios(this.configs);
    this.atualizarDicasDashboard(this.configs);
    return this.configs;
  }
}

const configManager = new ConfiguracoesManager();
