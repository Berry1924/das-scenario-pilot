# Contributing to DAAS-V2V / SIH26007

Thank you for your interest in contributing to the **DAAS-V2V Mine Vehicle Safety System**! This repository is maintained as a rigorous research- and engineering-grade project.

---

## 1. Code of Conduct
All contributors and maintainers are expected to uphold scientific integrity and respectful collaboration as detailed in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## 2. Research & Engineering Integrity Policy

To maintain repository truth and academic credibility:
1. **Never Fabricate Claims:** Do not claim deployment in commercial mines, field measurements, or compliance with certifications that have not been physically conducted.
2. **Clear Status Labeling:** Any planned or simulated component must be explicitly marked as `PLANNED` or `SYNTHETIC SIMULATION`.
3. **Hardware Pinout Accuracy:** Any modification to ESP32 pinouts must be cross-verified with physical schematics and documented via an ADR in `docs/project/decision-log.md`.
4. **Safety-Path Invariant:** No change may introduce queuing delays, rate throttling, or ML model dependencies to life-critical emergency braking packets (`PRIORITY_EMERGENCY`).

---

## 3. Development Workflow

1. Fork the repository and create a feature branch from `develop`:
   ```bash
   git checkout develop
   git checkout -b feature/your-feature-name
   ```
2. For embedded firmware modifications:
   - Run native host unit tests:
     ```bash
     python firmware/tests/run_tests.py
     ```
   - Ensure all 5 test suites pass with zero errors.
3. For machine learning modifications:
   - Run Python test suite:
     ```bash
     pytest ml/tests/ -v
     ```
4. Commit your changes using conventional commit messages (`feat:`, `fix:`, `docs:`, `chore:`).
5. Open a Pull Request targeting the `develop` branch.
