# 2x2 Ablation — Adaptive Broadcasting x Emergency Isolation

- Modality: **SIMULATION** · seeds 8001-8003 · duration 60 s · loss 2% · dt 10 ms
- Driver: `experiments/ablation_2x2.py` (thin layer; existing `SimulationWorld`,
  existing metric extraction `muse.adapter.compute_metrics`/`WorldMetrics`)
- Raw: `results/raw/ABL2X2_<scenario>_<arm>_seed<seed>.csv` (24 runs) ·
  derived: `results/derived/ABL2X2_summary.json`

## Dense scenario (N=35, no emergencies) — offered load / pps

| Arm | packets/min | PDR % |
| :-- | ---: | ---: |
| A baseline (fixed, no isolation) | 21000.0 | 98.2286 |
| B fixed + isolation | 21000.0 | 98.2286 |
| C adaptive, no isolation | 7805.0 | 98.108 |
| D adaptive + isolation (full DAAS-V2V) | 7805.0 | 98.108 |

## Emergency scenario (N=10, lambda=0.2/s) — emergency path

| Arm | pps | emergency offered/s | preempt airtime p95 ms | emergency PDR % |
| :-- | ---: | ---: | ---: | ---: |
| A baseline (fixed, no isolation) | 6000.0 | 2.8167 | 83.192 | 97.4279 |
| B fixed + isolation | 6247.6667 | 8.2556 | 39.433 | 98.462 |
| C adaptive, no isolation | 4000.0 | 1.5611 | 121.7897 | 99.0625 |
| D adaptive + isolation (full DAAS-V2V) | 4302.6667 | 7.5389 | 26.768 | 97.7883 |

## Attribution (paired, same seeds)

- A=B exactly in dense (isolation cannot act without adaptive throttling) — measured, not assumed
- Adaptive alone (A->C): routine load -62.8% at N=35; BUT emergency path suppressed (2.82 -> 1.56/s offered, preempt p95 83.2 -> 121.8 ms) — the VS2 hazard quantified
- Isolation alone (A->B): emergency path boosted (2.82 -> 8.26/s; preempt p95 83.2 -> 39.4 ms), +4.1% routine load
- Both (A->D): -28.3% routine load AND emergency path restored (7.54/s; preempt p95 26.8 ms — best of all arms)
- Emergency PDR ~97.4-99.1% in all arms (channel not saturated at N=10); the effects are on rate and latency

## Caveats

- SIMULATION under the documented simplified CSMA/CA approximation; no RF impairment modeling
- 3 seeds; per-arm std in the derived summary; not a hardware result
- No ML policy involved (deterministic density-aware surrogate, per CLAIM_LEDGER)
