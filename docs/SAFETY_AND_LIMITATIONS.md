# Safety and Limitations

**This is a research prototype and bench-validation project. It is NOT
certified automotive safety equipment and must never be used as one.**

## What this system is NOT validated for

- Public-road or mine-site operation of any vehicle.
- Braking control, actuation, or any closed-loop vehicle control.
- Collision-avoidance guarantees of any kind.
- Pedestrian, animal, or obstacle recognition (the ultrasonic sensor
  measures distance only — it performs no semantic recognition).
- Emergency-vehicle recognition or priority handling in the real world.
- Driver-impairment detection of any kind.
- Disaster-response or life-safety deployment.

## Bench-safety notes (hardware path)

- The buzzer output is disabled by default (`BUZZER_ENABLE 0`) and must
  stay disabled until its wiring and behaviour are verified.
- The ultrasonic ECHO line must keep its installed resistor-based
  voltage-limiting arrangement; ECHO must never be connected directly to
  an ESP32 GPIO.
- Bench tests use stationary boards and a fixed, flat target. No moving
  vehicles, no human-in-beam tests, no road or public-space tests.
- GPIO2/GPIO5 strapping behaviour was analyzed for ESP32-WROOM-class
  modules with benign loads (LED / TRIG); the exact module variant should
  be confirmed from the board silkscreen before applying module-specific
  strapping guidance.

## Advisory-layer isolation

The Meta Muse integration is advisory and post-run only. It reads
completed-run reports and emits review text. There is no code path from
Muse output into simulation metrics, firmware behaviour, GPIO, radio
logic, or any real-time safety function. Model output must never be used
to control physical outputs.

## Evidence discipline

- MAC-layer (ESP-NOW send-callback) success is not application delivery.
- A received frame is not an acknowledged exchange.
- ACK round-trip time is measured only on a single (sender-side) clock.
- Status labels in `docs/VALIDATION_STATUS.md` are the single source of
  truth; do not upgrade a label without new captured evidence.

## No warranty

The software is provided "AS IS" under the Apache License, Version 2.0,
without warranty of any kind. See `LICENSE` Sections 7 and 8.
