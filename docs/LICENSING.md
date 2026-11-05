# Licensing

## Project code and documentation

Original project source code (Python simulation, experiment runners, Muse
integration, firmware, tests, scripts) and project-authored documentation
in this repository are licensed under the **Apache License, Version 2.0**
(`LICENSE`, exact unmodified text). Copyright and attribution: see `NOTICE`.

Note: earlier internal snapshots of this project used the MIT License; this
public repository is published under Apache-2.0 (recorded in `NOTICE`).

## What Apache-2.0 does NOT cover

- **Meta Model API / Meta Muse (Muse Spark):** access to Meta's API, models
  and weights is governed by Meta's then-current terms. Using
  `muse/adapter.py` requires your own authorized key and your compliance
  with those terms. This repository neither grants nor limits those rights.
- **Third-party libraries used at runtime on developer machines** (e.g.
  Adafruit SSD1306/GFX for OLED sketches, Arduino-ESP32 core, g++): they
  are not redistributed in this repository and keep their own licenses.
  See `docs/THIRD_PARTY_LICENSES.md`.
- **Trademarks:** ESP32, ESP-NOW, Arduino, XGBoost, Adafruit, Meta and
  other names are marks of their respective owners; used here descriptively.
- **Excluded materials:** photographs, presentation decks, externally
  authored papers/PDFs, model weights and datasets referenced by the
  internal project are NOT included in this repository and no license to
  them is granted.

## Independent project statement

This is an independent community/research project and is not affiliated
with, endorsed by, or sponsored by Meta Platforms, Inc.
