# MUSE Vertical Slice Report — Baseline vs DAAS-V2V

- Generated (UTC): 2026-10-31T16:38:53Z
- Modality: **SIMULATION** (software-level, no hardware involved)
- Scenario: `vertical_slice_base` · schema_version 1.0 · scenario_hash `df505279e1cd0cee…`
- Seed: `7001` (both arms) · software: daas-impl 1.0.0 · git: `9f9c19ec9ca6`

## Scenario parameters

| Parameter | Value |
| --------: | :---- |
| num_vehicles | 10 |
| duration_s | 120.0 |
| dt_ms | 10.0 |
| emergency_intensity | 0.05 |
| emergency_duration_ms | 2000.0 |
| speed_mean_mps | 8.0 |
| speed_jitter_mps | 3.0 |
| loss_prob | 0.02 |
| comm_range_m | 100.0 |
| road_length_m | 100.0 |
| trust_gate_enabled | False |

Description: Deterministic local scenario mirroring the C1 N=10 tier environment at 120 s duration: paired baseline (fixed 10 Hz, no isolation) vs DAAS-V2V (adaptive 2-20 Hz with emergency isolation). Same seed for both arms.

## Arms (identical conditions: same seed, same environment)

| Arm | Policy | Emergency isolation |
| :-- | :----- | :------------------ |
| baseline | `fixed` 10 Hz | `False` |
| daas_v2v | `adaptive` 2–20 Hz | `True` |

## Computed metrics (existing WorldMetrics implementations)

| Metric | baseline | daas_v2v | Δ (daas − baseline) |
| :----- | -------: | -------: | ------------------: |
| PDR (%) | 98.16 | 98.08 | -0.0764 |
| RTT mean (ms) | 5.511 | 5.509 | -0.002 |
| RTT p95 (ms) | 6.195 | 6.181 | -0.014 |
| Msgs/s/node | 10.0000 | 6.7342 | -3.2658 |
| Emergency PDR (%) | 97.60 | 97.50 | -0.1 |
| Emergency RTT p95 (ms) | 6.206 | 6.085 | -0.121 |
| Preempt airtime p95 (ms) | 76.368 | 29.380 | -46.988 |
| Packets/min | 6000.00 | 4040.50 | -1959.5 |
| Bytes/s | 3200.00 | 2154.93 | -1045.07 |

## Scenario review (Meta Model API — advisory only)

- Model: `muse-spark-1.3`
- Status: `DISABLED_NO_URL`
- Content sha256: (none)
- Latency: 0 ms

> The model review is advisory provenance. It does not gate, alter,
> or compute any experiment value; validation was performed by the
> strict local schema before any run started.

## Evidence references

| Artifact | Path |
| :------- | :--- |
| events (baseline) | `results/raw/MUSE_vertical_slice_base_baseline_seed7001.csv` |
| metadata (baseline) | `results/metadata/MUSE_vertical_slice_base_baseline.metadata.json` |
| events (daas_v2v) | `results/raw/MUSE_vertical_slice_base_daas_v2v_seed7001.csv` |
| metadata (daas_v2v) | `results/metadata/MUSE_vertical_slice_base_daas_v2v.metadata.json` |

## Interpretation caveats

- Both arms ran the verified `src/daas_impl` world; nothing was
  reimplemented. Metrics come from the existing WorldMetrics code.
- Arms are paired by seed and environment, not byte-identical RNG
  streams (policy choice changes randomness consumption).
- Results are SIMULATION results under the documented simplified
  channel model; no hardware, C-V2X, deployment, or ML-policy claim.
