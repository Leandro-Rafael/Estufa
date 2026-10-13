# Guia de Hardware e Conexão Arduino / ESP32 - Estufa Inteligente

Este diretório contém o firmware para microcontroladores compatíveis com Arduino IDE (Arduino Uno, Nano, Mega, ESP32, ESP8266) para coleta de sensores e acionamento de atuadores da estufa.

---

## 1. Sensores e Módulos Suportados

| Sensor / Módulo | Função | Tipo de Saída |
| :--- | :--- | :--- |
| **DHT22** (ou DHT11) | Temperatura (°C) e Umidade do Ar (%) | Digital (Protocolo 1-wire) |
| **Sensor Capacitivo v1.2 / v2.0** | Umidade do Solo (%) | Analógica (Tensão proporcional à umidade) |
| **LDR (Fotoresistor 5mm)** | Luminosidade | Analógica (Divisor de tensão com resistor 10kΩ) |
| **Módulo Relé (1 Canal / 5V ou 3.3V)** | Acionamento da Mini Bomba D'água | Digital (Controle por nível lógico) |
| **Sensor de CO2 (Opcional - ex: MQ-135 / SCD30)** | Nível de CO2 | Estrutura preparada no backend e sketch |

---

## 2. Esquema de Ligação e Pinagem Recomendada

> [!NOTE]  
> Os números de pinos abaixo são valores padrão definidos no arquivo [`estufa_monitor.ino`](file:///arduino/estufa_monitor.ino). Caso sua montagem utilize pinos diferentes, basta alterar as constantes no topo do arquivo.

### Tabela de Conexões:

#### Arduino Uno / Nano:
| Componente | Pino do Módulo | Pino no Arduino | Observações |
| :--- | :--- | :--- | :--- |
| **DHT22 / DHT11** | VCC | 5V | Alimentação |
| | GND | GND | Terra |
| | DATA (OUT) | **D2** | Resistor pull-up de 4.7kΩ ou 10kΩ entre VCC e DATA (se o módulo já tiver, não precisa) |
| **Sensor Capacitivo Solo** | VCC | 5V (ou 3.3V) | Alimentação |
| | GND | GND | Terra |
| | AOUT | **A1** | Entrada analógica |
| **LDR (Luminosidade)** | Terminal 1 | 5V | Ligado ao 5V |
| | Terminal 2 | **A0** | Ligado ao A0 e a um resistor de 10kΩ para o GND |
| **Módulo Relé (Bomba)** | VCC | 5V | Alimentação |
| | GND | GND | Terra |
| | IN | **D7** | Saída digital de controle |

#### ESP32 (3.3V):
- Para ESP32, utilize entradas analógicas do bloco **ADC1** (ex: GPIO 34, 35, 36) para evitar conflitos com Wi-Fi.
- Alimente o sensor de solo com 3.3V para respeitar o limite de tensão do conversor analógico do ESP32.
- Configure o pino do DHT para um GPIO seguro, como GPIO 4 ou 15.

---

## 3. Calibração do Sensor Capacitivo de Umidade do Solo

O sensor capacitivo mede a constante dielétrica do solo e entrega uma tensão analógica inversa (quanto mais úmido, menor a leitura analógica). Para calibrar:

1. Carregue o sketch e abra o Serial Monitor (9600 baud).
2. Segure o sensor limpo no ar (completamente seco). Observe a leitura analógica e anote (exemplo: `650`).
3. Mergulhe a ponta da haste do sensor até a linha indicada em um copo com água. Observe a leitura analógica e anote (exemplo: `280`).
4. Altere as constantes no arquivo [`estufa_monitor.ino`](file:///arduino/estufa_monitor.ino):
   ```cpp
   const int CALIB_SOLO_SECO = 650;     // Leitura no ar seco (0%)
   const int CALIB_SOLO_MOLHADO = 280;  // Leitura na água (100%)
   ```

---

## 4. Bibliotecas Necessárias no Arduino IDE

No Arduino IDE, acesse **Sketch -> Incluir Biblioteca -> Gerenciar Bibliotecas** e instale:

1. **DHT sensor library** (por Adafruit)
2. **Adafruit Unified Sensor** (dependência automática do DHT)

---

## 5. Testando pelo Serial Monitor

Após enviar o código para a placa, abra o **Serial Monitor** na velocidade **9600 baud**. Você deverá ver linhas como:

```json
{"temperatura": 24.5, "umidade_ar": 62.3, "umidade_solo": 48.0, "luminosidade": 720}
```

Para testar comandos manuais, digite e envie no campo de texto do Serial Monitor:
```json
{"acao": "irrigar", "duracao": 5}
```
O relé deve acionar e desarmar automaticamente após 5 segundos.
