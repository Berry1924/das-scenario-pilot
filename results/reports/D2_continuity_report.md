# D2 — Communication continuity diagnostics (sender-side)

- Generated: 2026-10-31T16:38:16Z · daas-impl 1.0.0
- Scope: **Sender-side delivery-continuity diagnostics only; receiver identities and receiver-side arrival timestamps are not captured (world.py:222-229, world.py:242-253). NOT a formal Disconnection Time metric.**

## dense — 3 matched seeds (8001-8003), mean over seeds

Definitions: **delivery gap** = per-SENDER inter-delivery
interval (ms of simulated time between consecutive delivered
frames of that sender) — the pattern any in-range receiver
would observe from that sender; it is NOT a receiver-side
reception measurement. **burst** = run of consecutive
undelivered frames of one sender (counted in FRAMES, not ms).

| Arm | per-sender delivery-gap max (ms) | delivery-gap p95 (ms) | loss-burst max (frames) | loss-burst p95 (frames) | emergency-window delivery-gap p95 (ms) | emergency-window loss-burst max (frames) |
| :-- | ---: | ---: | ---: | ---: | ---: | ---: |
| A_baseline | 219.048 | 100.0 | 1.19 | 1.099 | None | None |
| B_fixed_iso | 219.048 | 100.0 | 1.19 | 1.099 | None | None |
| C_adapt_noiso | 565.714 | 270.0 | 1.095 | 1.077 | None | None |
| D_daas_full | 565.714 | 270.0 | 1.095 | 1.077 | None | None |
## emergency — 3 matched seeds (8001-8003), mean over seeds

Definitions: **delivery gap** = per-SENDER inter-delivery
interval (ms of simulated time between consecutive delivered
frames of that sender) — the pattern any in-range receiver
would observe from that sender; it is NOT a receiver-side
reception measurement. **burst** = run of consecutive
undelivered frames of one sender (counted in FRAMES, not ms).

| Arm | per-sender delivery-gap max (ms) | delivery-gap p95 (ms) | loss-burst max (frames) | loss-burst p95 (frames) | emergency-window delivery-gap p95 (ms) | emergency-window loss-burst max (frames) |
| :-- | ---: | ---: | ---: | ---: | ---: | ---: |
| A_baseline | 210.0 | 100.0 | 1.1 | 1.038 | 111.8 | 1 |
| B_fixed_iso | 223.333 | 100.0 | 1.233 | 1.115 | 50.0 | 1 |
| C_adapt_noiso | 310.0 | 150.0 | 1.067 | 1.053 | 157.9 | 1 |
| D_daas_full | 305.0 | 150.0 | 1.1 | 1.063 | 51.9 | 1.2 |

## Missing fields (why no receiver-side metric is computed)

- Receiver identity: NOT logged — receiver loop `for j, other in
  enumerate(self.nodes)` at `src/daas_impl/world.py:242-253` does
  not record `j`; event rows (`world.py:222-229`) carry only the 7
  sender-side fields.
- Receiver-side arrival timestamp: NOT logged. `one_way_delay_ms`
  is the channel's per-frame modeled delay (same for every
  in-range receiver), not a per-receiver reception time.
- C1 events (`C1_events_seed1001.csv`) additionally lack a
  `delivered` flag: only inter-OFFER schedule continuity computed
  (see JSON); delivery gaps are not computable there.

## Smallest non-invasive future trace capture (proposed, NOT
# implemented — requires explicit approval for src/daas_impl/)

1. Flag-gated per-receiver reception rows in `_deliver`'s receiver
   loop: append `(now_ms + one_way_delay_ms, receiver_j, sender,
   seq, emergency)` per in-range receiver. ~5 lines, default off.
2. Zero-core alternative: deterministic replay reconstruction
   (same seed/config reproduces positions and delivery sets) in an
   experiments-side analyzer.

## Formal-metric disclaimer

These diagnostics are NOT a published Disconnection Time metric.
A formal DT requires receiver-side reception timestamps and
identities; none exist in the current evidence. No DT claim is
made or supportable from the present data.
