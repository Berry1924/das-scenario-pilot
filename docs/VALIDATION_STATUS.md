# Validation Status

Status date: 2026-11-05. Labels follow the release evidence discipline:
`SIMULATION_VERIFIED` · `STATIC_CHECKED` · `COMPILE_VERIFIED` ·
`USER_REPORTED_FLASHED` · `HARDWARE_BENCH_VERIFIED` (not yet used) ·
`ROAD_TESTED` (not applicable).

| Component | Label | Evidence |
|---|---|---|
| `src/daas_impl` simulation core | `SIMULATION_VERIFIED` | `python3 tests/run_unit_tests.py` — 33/33 OK (2026-11-05, from this published tree) |
| Muse suite (offline/sandbox) | `SIMULATION_VERIFIED` | `python3 muse/tests/run_tests.py` — 41/41 PASS; `python3 -m muse.vertical_slice muse/scenarios/vertical_slice_base.json --sandbox` — PASS |
| Firmware host C++ tests | `SIMULATION_VERIFIED` | 5 suites (`test_wire_protocol`, `test_sequence_freshness`, `test_risk_engine`, `test_hazard_decay`, `test_safety_isolation`) + `vs1_hostcheck.py` PASS; `test_wire_protocol` and `test_safety_isolation` recompiled with g++ and passed 2026-11-05 |
| Firmware diagnostics sketches (`firmware/diagnostics/`) | `COMPILE_VERIFIED` + `USER_REPORTED_FLASHED` | compiled against Arduino-ESP32 core 3.3.11, FQBN `esp32:esp32:esp32` (TX 887,684 B / 67%, RX 923,976 B / 70% program storage); user reports both sketches flashed to the two boards; boot banners confirmed sketch identity, protocol v2, channel 1 and OLED presence |
| Diagnostic end-to-end bench chain (sensor → TX → RX → ACK → OLED/LED) | **PENDING — not yet `HARDWARE_BENCH_VERIFIED`** | application-level ACK correlation and OLED/LED transitions still require captured bench evidence; MAC-layer send-callback success is NOT application delivery |
| Production firmware (`firmware/vehicle-node/`, `vehicle-node-2/`) | `NOT COMPILE-VERIFIED ON CORE 3.x` | known incompatibility: Arduino-ESP32 core 3.x changed the ESP-NOW send/receive callback signatures (`wifi_tx_info_t` / `esp_now_recv_info_t`); production `v2v_protocol.cpp` does not compile unmodified against core 3.3.11. Porting is deliberate future work, not silently patched here |
| ML pipeline (internal `ml/` tree) | excluded from this snapshot | dependency/model/data licensing under review; not part of the published tree |
| Road/vehicle operation | `NOT VALIDATED — NEVER CLAIMED` | research prototype; no public-road testing, no safety certification |

## Measurement distinctions that govern all hardware claims

1. Radio/MAC send-callback success ≠ receiver-side application acceptance.
2. A frame accepted at the RX application ≠ a matched application ACK.
3. ACK round-trip time is computed only on the same (TX) clock; no one-way
   latency is claimed from unsynchronized clocks.
4. The ultrasonic "50.0 m" value in firmware is a no-echo timeout sentinel,
   never a measured distance; HC-SR04-class sensors are proximity/bench
   ranging devices (roughly 0.02–4 m class), not long-range or semantic
   object detectors.
5. Simulation results (`results/`) and hardware bench status are kept
   strictly separate; no historical simulation number is presented as a
   hardware result.
