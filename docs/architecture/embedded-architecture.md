# Embedded Systems & Hardware Architecture

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Hardware Platform:** Espressif ESP32-WROOM-32 Microcontroller  
**Document Type:** Embedded Systems Engineering Specification  

---

## 1. Microcontroller Hardware Architecture

The vehicle node is powered by an Espressif ESP32-WROOM-32 module:
- **Processor:** Dual-core Xtensa 32-bit LX6 microprocessors running at 240 MHz.
- **Memory:** 520 KB on-chip SRAM, 448 KB ROM, 4 MB external SPI flash.
- **RF Subsystem:** Integrated 2.4 GHz Wi-Fi (802.11 b/g/n) with integrated balun, RF switch, and PCB trace antenna.
- **Hardware Peripherals:** Hardware I2C (400 kHz Fast Mode), 3x UARTs, 16x PWM channels, high-resolution 64-bit hardware timers.

```
+-----------------------------------------------------------------------------------+
|                           ESP32 EMBEDDED CONCURRENCY MODEL                        |
+-----------------------------------------------------------------------------------+
|  CORE 0 (Protocol & RF Comm Engine)          CORE 1 (Application & Risk Engine)   |
|  ==================================          ==================================   |
|  - ESP-NOW MAC Transceiver Task              - Sensor Polling Task (20 Hz)        |
|  - Hardware Wi-Fi RX/TX Interrupts           - Deterministic Risk & TTC Engine    |
|  - Wire Protocol CRC16-CCITT Verification    - Hazard State Anti-Flicker Latch    |
|  - Monotonic Sequence Drop Accounting        - Fallback Watchdog Monitor (2.5s)   |
|  - High-Priority Safety Queue Preemption     - Cockpit HMI (I2C OLED, Buzzer, LED)|
|                                              - Serial Telemetry Streamer (10 Hz)  |
|                         \                          /                              |
|                          \                        /                               |
|                           [ FreeRTOS Shared State ]                               |
+-----------------------------------------------------------------------------------+
```

---

## 2. Hardware Pinout & Wiring Specification

| GPIO Pin | Function / Identifier | Direction | Electrical Circuit Configuration | Module / Hardware Component |
| :---: | :--- | :---: | :--- | :--- |
| **GPIO 5** | `PIN_ULTRASONIC_TRIG` | Output | 3.3V Push-Pull (10 $\mu\text{s}$ pulse) | HC-SR04 Trigger Pin |
| **GPIO 18** | `PIN_ULTRASONIC_ECHO` | Input | 5V to 3.3V Resistor Divider (1k$\Omega$ / 2k$\Omega$) | HC-SR04 Echo Pin |
| **GPIO 19** | `PIN_BRAKE_SWITCH` | Input | Active-LOW, Internal Pull-Up (45k$\Omega$) | Tactile Emergency Brake Push Button |
| **GPIO 4** | `PIN_LED_DANGER` | Output | Active-HIGH via 330$\Omega$ Current Limiting Resistor | Red 5mm High-Intensity Warning LED |
| **GPIO 2** | `PIN_LED_SAFE` | Output | Active-HIGH via 330$\Omega$ (also drives on-board LED)| Green 5mm Status LED |
| **GPIO 13** | `PIN_BUZZER` | Output | Active-HIGH driving NPN 2N2222 Transistor Buffer| 5V Active Piezo Buzzer (>85 dBA) |
| **GPIO 21** | `PIN_OLED_SDA` | Bidirectional | I2C Serial Data, 4.7k$\Omega$ External Pull-Up | SSD1306 0.96" 128x64 OLED Display |
| **GPIO 22** | `PIN_OLED_SCL` | Output | I2C Serial Clock (400 kHz), 4.7k$\Omega$ Pull-Up | SSD1306 0.96" 128x64 OLED Display |
| **UART0 TX** | Serial Out (`GPIO 1`)| Output | Direct CP2102 / CH340 USB Bridge | USB Telemetry Streaming to Host |
| **UART0 RX** | Serial In (`GPIO 3`) | Input | Direct CP2102 / CH340 USB Bridge | Host Rate Adaptation Command Stream |

---

## 3. Pin Mapping Defect Audit & Resolution (ADR-005)

### Historical Conflict in `daas_v1.ino`
During repository auditing, an unresolved hardware pin allocation collision was discovered in legacy code:
```c
// Code excerpt from legacy daas_v1.ino (Lines 18 and 23):
#define BRAKE_PIN 4
...
#define LED_DANGER_PIN 4
```
**Impact:** If both macros target GPIO 4, pressing the active-low brake button shorts the LED output pin to ground, potentially causing latch-up, erroneous brake triggering, or burning out the microcontroller output driver.

### Resolution in Modular Architecture
In accordance with ADR-005, the pin mapping has been strictly formalized:
- **GPIO 19:** Permanently dedicated to `PIN_BRAKE_SWITCH` with `INPUT_PULLUP`.
- **GPIO 4:** Permanently dedicated to `PIN_LED_DANGER` output.
- Hardware breadboards have been re-wired and verified matching this specification.

---

## 4. Mining Vehicle Power Subsystem (Planned Phase 4)

While the bench prototype runs from regulated 5V USB, commercial haul dumpers operate on a 24V DC negative-ground electrical system characterized by severe electrical transients (ISO 7637-2 load dump surges up to 120V).

**Production Power Stage Design:**
- **Input:** 9V – 36V DC nominal with reverse-polarity protection diode and TVS diode (Transient Voltage Suppressor).
- **Primary Stage:** Automotive-grade wide-input synchronous buck regulator (e.g. TI LM5164) stepping down 24V to 5.0V at 3A.
- **Secondary Stage:** Ultra-low-noise LDO regulator (e.g. TI TPS7A4700) generating stable 3.3V for the ESP32 and RF front end.
