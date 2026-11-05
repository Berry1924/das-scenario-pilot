# MANUAL FLASH — H3 Diagnostic Firmware (COM5 / TX → COM9 / RX)

**You (the user) upload these sketches manually. Nothing is flashed automatically. No destructive flashing without your separate explicit approval.**

- TX node = **COM5** (Vehicle 1: HC-SR04 + ESP-NOW TX) — sketch `tx_node_com5/`
- RX node = **COM9** (Vehicle 2: ESP-NOW RX + validation + ACK + OLED/LED) — sketch `rx_node_com10/`
  *(Earlier references called the RX port COM10; the board now enumerates as COM9 per `usbipd list`. Windows COM numbering may change with USB ports — trust `usbipd list`, not the file name.)*
- Wire format = copy of `firmware/common/protocol/v2v_packet.h` + validator inlines (`packet_validator.h`), merged byte-identical into each sketch folder.

## 1. Dependencies (all verified installed on this PC)

| Component | Verified version | Where |
|---|---|---|
| esp32 Arduino core | **3.3.11** | `<Arduino sketchbook>/packages/esp32/hardware/esp32/3.3.11` |
| Adafruit SSD1306 | 2.5.17 | `<Arduino sketchbook>\libraries\` |
| Adafruit GFX | 1.12.6 | same |
| Board | ESP32 Dev Module (both boards) | — |

**Compile status (run against the installed core via the IDE-bundled arduino-cli 1.5.1):**
- `tx_node_com5.ino` → OK: 887,684 B flash (67%), 45,536 B RAM (13%)
- `rx_node_com10.ino` → OK: 923,976 B flash (70%), 47,088 B RAM (14%)

## 2. MAC-address discovery procedure (do this FIRST)

1. Open `rx_node_com10/rx_node_com10.ino` in Arduino IDE 2.x.
2. Flash it to the **COM9** board (§3).
3. Open Serial Monitor @ **115200 baud**. The boot banner prints:
   `{"boot":"rx_node_com10","node":2,"my_mac":"AA:BB:CC:DD:EE:FF",...}`
4. Copy `my_mac` → open `tx_node_com5/tx_node_com5.ino` → edit:
   `static const uint8_t PEER_MAC[6] = {0xAA,0xBB,0xCC,0xDD,0xEE,0xFF};`
5. Flash the TX sketch to **COM5**. Its own banner also prints `my_mac` (for logging).
   *(The RX learns the TX MAC at runtime from received frames — no edit needed on RX.)*

## 3. Exact upload instructions

### Arduino IDE (GUI)
1. File → Open → `firmware/diagnostics/<sketch folder>/<sketch>.ino`.
2. Tools → Board → esp32 → **ESP32 Dev Module**; Tools → Port → the board's COM port.
3. Sketch → Upload. If upload never starts, hold the board's **BOOT** button while "Connecting…".
4. Serial Monitor @ **115200** (close it before re-flashing).

### Arduino CLI (equivalent, verified working from this machine)
```
& "<arduino-cli>" compile --fqbn esp32:esp32:esp32 "<repo>\firmware\diagnostics\tx_node_com5"
& <same cli> upload --fqbn esp32:esp32:esp32 --port COM5 "<repo>\firmware\diagnostics\tx_node_com5"
& <same cli> upload --fqbn esp32:esp32:esp32 --port COM9 "<repo>\firmware\diagnostics\rx_node_com10"
```
**Important (WSL):** if usbipd has a board attached into WSL, detach first or Windows cannot open the port: `usbipd detach --busid 4-1` (admin not needed for detach of an attach; if the device shows "Shared", `usbipd detach --busid <id>` from an admin shell returns it).

## 4. Bench test procedure (acceptance chain)

1. RX first (COM9), TX second (COM5), both powered via USB.
2. Verify RX OLED boots ("DAAS-V2V RX DIAG / BOOT OK" — `oled:1` in telemetry).
3. Obstacle test: move a flat target in front of the HC-SR04 (≈1 m, then ≈3 m, then away >5 m).
4. RX telemetry shows `last_seq` advancing and `acc_cnt` increasing; `dup_cnt`, `crc_err` ≈ 0.
5. TX telemetry shows `ack_cnt` increasing and `ack_rtt_ms` (single-digit-to-tens ms on bench).
6. OLED shows live distance/seq/RSSI; SAFE LED lit on healthy packets; DANGER LED at <4 m or `brake:1`; buzzer is DISABLED (`BUZZER_ENABLE 0`) until wiring verified — flip to 1 only after polarity/current-limit confirmation.
7. Capture both ports simultaneously with the existing TX-silent collector:
   `python3 tools/hardware/hardware_collector.py --port0 /dev/ttyUSB0 --port1 /dev/ttyUSB1 ...` (after `usbipd attach --wsl` both busids) — or any two serial monitors at 115200.
8. Metrics: PDR ≈ Δacc_cnt/Δlast_seq on RX JSON; ACK RTT from TX JSON `ack_rtt_ms`; sensor accuracy/repeatability = repeated fixed-target distance readings.

## 5. Restoring the original firmware

The original production firmware is in `firmware/vehicle-node/` (multi-file `main.cpp` project). It is **not** a single .ino — restore options:
1. Preferred: ask the implementation agent to regenerate a buildable IDE sketch of the production firmware (note: `v2v_protocol.cpp` recv callback uses the core-2.x signature and needs the 3.x 3-arg `esp_now_recv_info_t` fix to compile on 3.3.11).
2. Or keep the diagnostic sketches archived and re-upload whatever was on the boards before, from your original sketch sources.

Diagnostic upload replaces the flash content — nothing else on the boards is modified. No fuses/eFuse touched, no keys, no RF power changes.

## 6. Safety and change control

- Bench only. No public-road testing. No vehicle integration.
- Buzzer disabled by default; LEDs are current-limited per the installed resistor arrangement.
- No API keys anywhere in these sketches or their telemetry.
- Muse Spark / ML components are outside this real-time path.
- No git operations performed by the agent; these files are additive and uncommitted.
