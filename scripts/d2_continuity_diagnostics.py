#!/usr/bin/env python3
"""D2 — receiver-side communication continuity diagnostics (read-only).

IMPORTANT SCOPE NOTE: the simulator's event logs are SENDER-side. There are
no receiver identities and no receiver-side arrival timestamps anywhere in
results/raw (see world.py:222-229 event rows and world.py:242-253 receiver
loop). What CAN be computed per sender — and what this script computes —
are delivery-continuity DIAGNOSTICS:

  - inter-DELIVERY gap per sender (max, p95): the interval pattern any
    in-range receiver would observe from that sender's delivered frames;
  - consecutive-loss burst lengths per sender (max, p95): runs of
    delivered=0 between deliveries, valid because packet_seq is strictly
    consecutive per sender;
  - emergency-window variants of both (emergency_flag=1 frames).

These are project diagnostics. They are NOT a formal published
Disconnection Time metric — that requires receiver-side reception
timestamps and identities, which are not captured. Nothing is
reconstructed from aggregate PDR; no simulator or metric logic is changed.

Inputs: results/raw/ABL2X2_*.csv (24 runs) and results/raw/C1_events_seed1001.csv
(C1 events have NO delivered flag -> only inter-OFFER schedule continuity
is computable there; delivery gaps are not).
Outputs: results/derived/D2_continuity_diagnostics.json +
results/reports/D2_continuity_report.md.
"""

import csv
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
from daas_impl.world import percentile  # existing helper
from daas_impl.simio import repo_root, utc_now_iso, SOFTWARE_VERSION

ARMS = ["A_baseline", "B_fixed_iso", "C_adapt_noiso", "D_daas_full"]


def sender_stats(rows, delivered_field):
    """Per-sender continuity diagnostics over one run's frame rows."""
    by_sender = {}
    for r in rows:
        by_sender.setdefault(int(r["sender_id"]), []).append(r)
    gap_max, gap_p95, burst_max, burst_p95 = [], [], [], []
    for sid, frames in by_sender.items():
        frames.sort(key=lambda r: (float(r["timestamp_ms"]),
                                   int(r["packet_seq"])))
        seqs = [int(r["packet_seq"]) for r in frames]
        # sequence semantics must be consecutive per sender for bursts
        if any(b - a != 1 for a, b in zip(seqs, seqs[1:])):
            continue  # semantics do not permit burst analysis for this sender
        t = [float(r["timestamp_ms"]) for r in frames]
        d = [int(r[delivered_field]) for r in frames]
        gaps, bursts, run = [], [], 0
        for i in range(len(frames)):
            if d[i]:
                gaps.append(t[i])
                if run:
                    bursts.append(run)
                    run = 0
            else:
                run += 1
        if run:
            bursts.append(run)
        iv = [b - a for a, b in zip(gaps, gaps[1:])]
        if iv:
            gap_max.append(max(iv))
            gap_p95.append(percentile(iv, 95))
        if bursts:
            burst_max.append(max(bursts))
            burst_p95.append(percentile(bursts, 95))
    def m(x):
        return round(statistics.mean(x), 3) if x else None
    return {"inter_delivery_gap_max_ms": m(gap_max),
            "inter_delivery_gap_p95_ms": m(gap_p95),
            "loss_burst_max": m(burst_max),
            "loss_burst_p95": m(burst_p95),
            "senders": len(by_sender)}


def analyse_run(path):
    rows = list(csv.DictReader(open(path)))
    out = {"all_frames": sender_stats(rows, "delivered")}
    emg = [r for r in rows if int(r["emergency_flag"]) == 1]
    out["emergency_window"] = (sender_stats(emg, "delivered")
                               if emg else {"senders": 0})
    out["frames"] = len(rows)
    out["emergency_frames"] = len(emg)
    return out


def c1_offer_continuity(path):
    """C1 events have no delivered flag: inter-OFFER schedule continuity only.
    NOTE (found during D2): the C1 event writer (sim_c1_density_adaptation.py
    :121-124) leaves density_tier and policy EMPTY in event rows, so per-tier
    grouping is impossible; an aggregate over the mixed file is provided."""
    rows = list(csv.DictReader(open(path)))
    out = {}
    for tier in ("10", "35", "50"):
        for pol in ("fixed", "adaptive"):
            sel = [r for r in rows
                   if r["density_tier"] == tier and r["policy"] == pol]
            if not sel:
                continue
            by_n = {}
            for r in sel:
                by_n.setdefault(int(r["node_id"]), []).append(
                    float(r["tx_time_ms"]))
            iv = []
            for ts in by_n.values():
                ts.sort()
                iv += [b - a for a, b in zip(ts, ts[1:])]
            out[f"tier{tier}_{pol}"] = {
                "inter_offer_gap_mean_ms": round(statistics.mean(iv), 3),
                "inter_offer_gap_p95_ms": round(percentile(iv, 95), 3),
                "nodes": len(by_n)}
    if not out and rows:
        # tier/policy columns are empty in the source rows — aggregate only
        by_n = {}
        for r in rows:
            by_n.setdefault(int(r["node_id"]), []).append(
                float(r["tx_time_ms"]))
        iv = []
        for ts in by_n.values():
            ts.sort()
            iv += [b - a for a, b in zip(ts, ts[1:])]
        out["ALL_MIXED_UNSPLIT"] = {
            "inter_offer_gap_mean_ms": round(statistics.mean(iv), 3),
            "inter_offer_gap_p95_ms": round(percentile(iv, 95), 3),
            "nodes": len(by_n),
            "note": "tier/policy columns empty in C1 event rows "
                    "(sim_c1_density_adaptation.py:121-124); per-tier "
                    "offer-continuity not computable from this file"}
    return out


def main() -> int:
    root = repo_root()
    runs = {}
    import re
    pat = re.compile(r"^ABL2X2_(dense|emergency)_(.+)_seed(\d+)$")
    for path in sorted(glob.glob(os.path.join(
            root, "results/raw/ABL2X2_*.csv"))):
        m = pat.match(os.path.basename(path)[:-4])
        if not m:
            continue
        scenario, arm, seed = m.group(1), m.group(2), m.group(3)
        runs.setdefault(scenario, {}).setdefault(arm, {})[seed] = \
            analyse_run(path)

    # aggregate over matched seeds (mean of per-run values)
    summary = {"generated_utc": utc_now_iso(),
               "software_version": SOFTWARE_VERSION,
               "modality": "SIMULATION",
               "scope_warning":
                   "Sender-side delivery-continuity diagnostics only; "
                   "receiver identities and receiver-side arrival "
                   "timestamps are not captured (world.py:222-229, "
                   "world.py:242-253). NOT a formal Disconnection Time "
                   "metric.",
               "arms": {}, "c1_events_seed1001_offer_continuity":
                   c1_offer_continuity(os.path.join(
                       root, "results/raw/C1_events_seed1001.csv"))}
    for scenario, by_arm in runs.items():
        for arm in ARMS:
            seeds = by_arm[arm]
            keys = ["inter_delivery_gap_max_ms", "inter_delivery_gap_p95_ms",
                    "loss_burst_max", "loss_burst_p95"]
            agg = {}
            for k in keys:
                vals = [seeds[s]["all_frames"][k] for s in seeds
                        if seeds[s]["all_frames"][k] is not None]
                agg[k] = round(statistics.mean(vals), 3) if vals else None
            summary["arms"].setdefault(scenario, {})[arm] = agg

    dpath = os.path.join(root, "results", "derived")
    os.makedirs(dpath, exist_ok=True)
    with open(os.path.join(dpath, "D2_continuity_diagnostics.json"),
              "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    # markdown report
    L = ["# D2 — Communication continuity diagnostics (sender-side)","",
         f"- Generated: {summary['generated_utc']} · {summary['software_version']}",
         f"- Scope: **{summary['scope_warning']}**",""]
    for scenario in runs:
        L += [f"## {scenario} — 3 matched seeds (8001-8003), mean over seeds",
              "",
              "Definitions: **delivery gap** = per-SENDER inter-delivery",
              "interval (ms of simulated time between consecutive delivered",
              "frames of that sender) — the pattern any in-range receiver",
              "would observe from that sender; it is NOT a receiver-side",
              "reception measurement. **burst** = run of consecutive",
              "undelivered frames of one sender (counted in FRAMES, not ms).",
              "",
              "| Arm | per-sender delivery-gap max (ms) | delivery-gap p95 (ms) | "
              "loss-burst max (frames) | loss-burst p95 (frames) | "
              "emergency-window delivery-gap p95 (ms) | emergency-window loss-burst max (frames) |",
              "| :-- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for arm in ARMS:
            a = summary["arms"][scenario][arm]
            ew = runs[scenario][arm]
            emg_gap = emg_burst = None
            vals_gap, vals_burst = [], []
            for s in ew:
                e = ew[s]["emergency_window"]
                if e.get("inter_delivery_gap_p95_ms") is not None:
                    vals_gap.append(e["inter_delivery_gap_p95_ms"])
                if e.get("loss_burst_max") is not None:
                    vals_burst.append(e["loss_burst_max"])
            emg_gap = round(statistics.mean(vals_gap), 1) if vals_gap else None
            emg_burst = round(statistics.mean(vals_burst), 1) if vals_burst else None
            L.append(f"| {arm} | {a['inter_delivery_gap_max_ms']} | "
                     f"{a['inter_delivery_gap_p95_ms']} | "
                     f"{a['loss_burst_max']} | {a['loss_burst_p95']} | "
                     f"{emg_gap} | {emg_burst} |")
    L += ["",
          "## Missing fields (why no receiver-side metric is computed)",
          "",
          "- Receiver identity: NOT logged — receiver loop `for j, other in",
          "  enumerate(self.nodes)` at `src/daas_impl/world.py:242-253` does",
          "  not record `j`; event rows (`world.py:222-229`) carry only the 7",
          "  sender-side fields.",
          "- Receiver-side arrival timestamp: NOT logged. `one_way_delay_ms`",
          "  is the channel's per-frame modeled delay (same for every",
          "  in-range receiver), not a per-receiver reception time.",
          "- C1 events (`C1_events_seed1001.csv`) additionally lack a",
          "  `delivered` flag: only inter-OFFER schedule continuity computed",
          "  (see JSON); delivery gaps are not computable there.",
          "",
          "## Smallest non-invasive future trace capture (proposed, NOT",
          "# implemented — requires explicit approval for src/daas_impl/)",
          "",
          "1. Flag-gated per-receiver reception rows in `_deliver`'s receiver",
          "   loop: append `(now_ms + one_way_delay_ms, receiver_j, sender,",
          "   seq, emergency)` per in-range receiver. ~5 lines, default off.",
          "2. Zero-core alternative: deterministic replay reconstruction",
          "   (same seed/config reproduces positions and delivery sets) in an",
          "   experiments-side analyzer.",
          "",
          "## Formal-metric disclaimer",
          "",
          "These diagnostics are NOT a published Disconnection Time metric.",
          "A formal DT requires receiver-side reception timestamps and",
          "identities; none exist in the current evidence. No DT claim is",
          "made or supportable from the present data.",""]
    rpath = os.path.join(root, "results", "reports")
    os.makedirs(rpath, exist_ok=True)
    with open(os.path.join(rpath, "D2_continuity_report.md"), "w") as f:
        f.write("\n".join(L))
    print("[D2] diagnostics written:",
          "results/derived/D2_continuity_diagnostics.json,",
          "results/reports/D2_continuity_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
