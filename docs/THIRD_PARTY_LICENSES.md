# Third-Party Licenses and Terms Inventory

Scope: this snapshot. Anything not redistributed here is listed for
transparency with its role only; its own terms always apply.

## Redistributed in this repository

- **None known.** The published tree is intended to be 100% original
  project code plus project-authored documentation. If a third-party
  snippet is discovered in the tree, it must be reported via an issue and
  will be removed or properly attributed.

## Used at runtime / build time but NOT redistributed

| Component | Role | Terms (summary) | Where |
|---|---|---|---|
| Python 3.11+ (CPython) | runtime | PSF License (permissive) | developer machine |
| Arduino-ESP32 core 3.3.11 | firmware build | Apache-2.0 / LGPL-2.1 components per Espressif | Espressif Arduino packages |
| g++ / clang++ | host test compilation | GPL toolchain (output not affected) | developer machine |
| Adafruit SSD1306 / Adafruit GFX | OLED driver for ESP32 sketches | BSD-3-Clause (per Adafruit) | installed via Arduino Library Manager, not committed |
| XGBoost / FastAPI / related ML stack | internal `ml/` pipeline only — **excluded from this snapshot** | per upstream projects | pending separate publication |

## Services (terms apply, nothing redistributed)

- **Meta Model API / Meta Muse (Muse Spark):** used at runtime through
  `muse/adapter.py` / `muse/spark_adapter.py` with a user-supplied key.
  Governed by Meta's own terms; no Meta content, weights or SDK material
  is included in this repository.

## Hardware

- ESP32 DevKit-class boards and HC-SR04-class ultrasonic modules:
  commodity hardware; no vendor SDK material is redistributed here.
