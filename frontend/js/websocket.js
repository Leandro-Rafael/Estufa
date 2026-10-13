/**
 * Módulo de Comunicação WebSocket em Tempo Real (AeroFlora OS).
 * Conecta ao backend FastAPI, gerencia auto-reconexão exponencial,
 * streaming de telemetria e despacho de logs seriais TX/RX.
 */

class WebSocketClient {
  constructor() {
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectInterval = 10000;
    this.totalPacotes = 0;
    this.listeners = {
      leitura: [],
      status_dispositivo: [],
      log_serial: [],
      status_conexao: []
    };
    this.pingInterval = null;
  }

  conectar() {
    const protocolo = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host || "localhost:8000";
    const wsUrl = `${protocolo}//${host}/ws`;

    this._atualizarStatusUI("conectando");

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log("[WS] Link de telemetria estabelecido com o servidor.");
        this.reconnectAttempts = 0;
        this._atualizarStatusUI("online");
        this._iniciarPing();
      };

      this.socket.onmessage = (event) => {
        try {
          const dados = JSON.parse(event.data);
          this.totalPacotes++;
          this._atualizarContadorPacotes();
          this._despacharMensagem(dados);
        } catch (err) {
          if (event.data !== "pong") {
            console.warn("[WS] Payload não-JSON:", event.data);
          }
        }
      };

      this.socket.onclose = () => {
        console.warn("[WS] Conexão encerrada pelo host.");
        this._atualizarStatusUI("offline");
        this._pararPing();
        this._agendarReconexao();
      };

      this.socket.onerror = (error) => {
        console.error("[WS] Erro no socket:", error);
        this.socket.close();
      };

    } catch (e) {
      console.error("[WS] Falha de inicialização:", e);
      this._agendarReconexao();
    }
  }

  _agendarReconexao() {
    this.reconnectAttempts++;
    const intervalo = Math.min(1500 * Math.pow(1.4, this.reconnectAttempts - 1), this.maxReconnectInterval);
    setTimeout(() => {
      this.conectar();
    }, intervalo);
  }

  _iniciarPing() {
    this._pararPing();
    this.pingInterval = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send("ping");
      }
    }, 25000);
  }

  _pararPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  _atualizarContadorPacotes() {
    const badge = document.getElementById("badge-packets-count");
    if (badge) {
      badge.innerText = `${this.totalPacotes} pkt`;
    }
  }

  _atualizarStatusUI(estado) {
    const dot = document.getElementById("dot-ws");
    const label = document.getElementById("label-ws");
    if (!dot || !label) return;

    if (estado === "online") {
      dot.className = "pill-indicator dot-online";
      label.innerText = "Online (Ativo)";
    } else if (estado === "conectando") {
      dot.className = "pill-indicator dot-warning";
      label.innerText = "Conectando...";
    } else {
      dot.className = "pill-indicator dot-offline";
      label.innerText = "Offline";
    }

    this._notificarListeners("status_conexao", estado);
  }

  on(evento, callback) {
    if (this.listeners[evento]) {
      this.listeners[evento].push(callback);
    }
  }

  _notificarListeners(evento, payload) {
    if (this.listeners[evento]) {
      this.listeners[evento].forEach(fn => fn(payload));
    }
  }

  _despacharMensagem(dados) {
    const tipo = dados.tipo || "leitura";
    if (this.listeners[tipo]) {
      this.listeners[tipo].forEach(fn => fn(dados));
    }
  }
}

const wsClient = new WebSocketClient();
