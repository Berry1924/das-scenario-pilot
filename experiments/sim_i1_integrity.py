#!/usr/bin/env python3
"""I1 / VS3 — Message integrity: trust-gate fault injection.

Modality: SIMULATION on host Python. The trust gate mirrors
firmware/common/validation/packet_validator.h (CRC16-CCITT + monotonic
sequence + 500 ms freshness + kinematic bounds + local/remote consistency).

NOTE ON EXECUTION TIME: exec_time_us is measured with host Python
time.perf_counter(). It is NOT the ESP32 esp_cpu_get_ccount() figure from
the research spec; the on-chip overhead claim remains UNVERIFIED until a
bench run is possible.

Injected corpus (11,000 frames, deterministic):
  - 5,000 valid frames
  - 1,000 stale            (age 501-10000 ms)
  - 1,000 duplicate        (replayed identical sequence)
  - 1,000 invalid sequence (retrograde jump)
  - 1,000 impossible speed (> 70 m/s)
  - 1,000 impossible distance (negative or > 5000 m)

Baselines:
  A ungated            accepts everything passing CRC
  B sequence-only      duplicate filter only
  C full multi-tier gate (proposed)

Usage (from repo root):
  python3 experiments/sim_i1_integrity.py

Outputs:
  results/raw/I1_gate_decisions.csv   per-frame decisions
  results/derived/I1_summary.json
  results/metadata/I1_*.metadata.json
"""

import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl import packet as P
from daas_impl.simio import RunContext, repo_root, write_checksum_manifest
from daas_impl.trust_gate import TrustGate, TrustGateConfig

CSV_HEADER = ["packet_id", "injected_class", "crc_pass", "seq_pass", "age_ms",
              "age_pass", "bounds_pass", "gate_decision", "baseline_A_accepted",
              "baseline_B_accepted", "exec_time_us"]

N_VALID = 5000
N_PER_CLASS = 1000
CLASSES = ["stale", "duplicate", "invalid_sequence", "impossible_speed",
           "impossible_distance"]
SEED = 3001


def make_valid_frame(rng: random.Random, pid: int, seq: int, ts_ms: int) -> P.V2VPacket:
    pkt = P.V2VPacket(
        sender_id=1 + (pid % 10),
        seq_num=seq,
        timestamp_ms=ts_ms,
        priority=P.PRIORITY_BEACON,
        distance_m=round(rng.uniform(1.0, 60.0), 2),
        speed_mps=round(rng.uniform(0.0, 15.0), 2),
        accel_mps2=round(rng.uniform(-4.0, 2.0), 2),
    )
    return pkt.sign()


def build_corpus(rng: random.Random):
    """Returns list of (packet, class_label, now_ms). Frames are evaluated at
    a simulated receiver time now_ms; the corpus clock base is 100000 ms."""
    corpus = []
    base_ts = 100000

    # 5,000 valid frames: monotonically increasing sequences per sender
    seqs = {sid: 0 for sid in range(1, 11)}
    for i in range(N_VALID):
        sid = 1 + (i % 10)
        seqs[sid] += 1
        ts = base_ts + i * 5  # fresh (age <= 5 ms)
        corpus.append((make_valid_frame(rng, i, seqs[sid], ts), "valid", ts + 5))

    # 1,000 stale: valid payload, age 501-10000 ms
    for i in range(N_PER_CLASS):
        sid = 1 + (i % 10)
        seqs[sid] += 1
        ts = base_ts + 300000 + i * 5
        pkt = make_valid_frame(rng, 10000 + i, seqs[sid], ts)
        age_ms = rng.randint(501, 10000)
        corpus.append((pkt, "stale", ts + age_ms))

    # 1,000 duplicate: replay of an ALREADY-TRANSMITTED sequence per sender
    # (senders 1-10 transmitted seqs 1..500 in the valid phase above, so
    # replaying seq 500 is a true duplicate/replay, not a fresh frame).
    for i in range(N_PER_CLASS):
        sid = 1 + (i % 10)
        ts = base_ts + 600000 + i * 5
        pkt = make_valid_frame(rng, 20000 + i, 500, ts)  # seq 500 already seen
        corpus.append((pkt, "duplicate", ts + 5))

    # 1,000 invalid sequence: retrograde jump (seq < seq_prev). The gate only
    # advances last_seq on fully-accepted frames, so the effective last_seq
    # per sender here is 500 (valid phase); any seq in [1, 499] is a true
    # retrograde/replay frame.
    for i in range(N_PER_CLASS):
        sid = 1 + (i % 10)
        seqs[sid] += 1
        ts = base_ts + 900000 + i * 5
        pkt = make_valid_frame(rng, 30000 + i, rng.randint(1, 499), ts)
        corpus.append((pkt, "invalid_sequence", ts + 5))

    # 1,000 impossible speed: v > 70 m/s
    for i in range(N_PER_CLASS):
        sid = 1 + (i % 10)
        seqs[sid] += 1
        ts = base_ts + 1200000 + i * 5
        pkt = make_valid_frame(rng, 40000 + i, seqs[sid], ts)
        pkt.speed_mps = round(rng.uniform(70.5, 200.0), 2)
        pkt = pkt.sign()
        corpus.append((pkt, "impossible_speed", ts + 5))

    # 1,000 impossible distance: negative or > 5000 m
    for i in range(N_PER_CLASS):
        sid = 1 + (i % 10)
        seqs[sid] += 1
        ts = base_ts + 1500000 + i * 5
        pkt = make_valid_frame(rng, 50000 + i, seqs[sid], ts)
        pkt.distance_m = round(rng.choice([-1.0 * rng.uniform(0.1, 50.0),
                                           rng.uniform(5000.5, 10000.0)]), 2)
        pkt = pkt.sign()
        corpus.append((pkt, "impossible_distance", ts + 5))

    return corpus


def main() -> int:
    rng = random.Random(SEED)
    corpus = build_corpus(rng)

    gate_c = TrustGate(TrustGateConfig())                       # full multi-tier
    gate_b = TrustGate(TrustGateConfig(freshness_enabled=False,
                                       plausibility_enabled=False))  # sequence-only

    rows = []
    exec_times_us = []
    injected = {c: 0 for c in CLASSES}
    rejected_c = {c: 0 for c in CLASSES}
    rejected_b = {c: 0 for c in CLASSES}
    accepted_c = 0
    downweighted_c = 0
    valid_total = 0
    valid_rejected_c = 0
    ungated_accepted = 0
    total = 0

    for pid, (pkt, label, now_ms) in enumerate(corpus):
        total += 1
        if label != "valid":
            injected[label] += 1

        t0 = time.perf_counter()
        d = gate_c.ingest(pkt, now_ms)
        t1 = time.perf_counter()
        exec_us = (t1 - t0) * 1e6
        exec_times_us.append(exec_us)

        # Baseline A: ungated — accepts everything passing CRC
        raw = pkt.to_bytes()
        crc_ok = P.compute_crc16(raw[:P.V2V_CRC_OFFSET]) == pkt.crc16
        if crc_ok:
            ungated_accepted += 1

        # Baseline B: sequence filter only
        d_b = gate_b.ingest(pkt, now_ms)

        if label == "valid":
            valid_total += 1
            if d.rejected:
                valid_rejected_c += 1
        else:
            if d.rejected:
                rejected_c[label] += 1
            if d_b.rejected:
                rejected_b[label] += 1
        if d.accepted:
            accepted_c += 1
        if d.downweighted:
            downweighted_c += 1

        age_ms = max(0.0, now_ms - pkt.timestamp_ms)
        rows.append([
            pid, label, 1 if crc_ok else 0,
            1 if d.code != P.V2V_ERR_DUPLICATE_SEQUENCE else 0,
            round(age_ms, 1),
            1 if age_ms <= 500 else 0,
            1 if d.code != P.V2V_ERR_OUT_OF_BOUNDS else 0,
            "ACCEPTED" if d.accepted else ("REJECTED:" + P.VALIDATION_NAMES.get(d.code, "?")),
            1 if crc_ok else 0,
            1 if d_b.accepted else 0,
            round(exec_us, 2),
        ])

    run = RunContext(
        experiment_id="I1", run_id="I1_trust_gate", seed=SEED, run_number=1,
        configuration={
            "n_valid": N_VALID, "n_per_class": N_PER_CLASS,
            "classes": CLASSES, "corpus_total": total,
            "tau_max_ms": 500, "speed_bounds": [-30.0, 70.0],
            "accel_bounds": [-25.0, 20.0], "dist_max_m": 5000.0,
            "baselines": {"A": "ungated (CRC only)", "B": "sequence-only",
                          "C": "full multi-tier gate"},
            "exec_time_measurement": "host Python time.perf_counter (NOT ESP32 cycle counter)",
            "modality": "SIMULATION",
        },
        raw_csv="results/raw/I1_gate_decisions.csv",
    )
    run.ensure_header(CSV_HEADER)
    run.append_rows(CSV_HEADER, rows)
    run.finalize()

    injected_total = sum(injected.values())
    rejected_total = sum(rejected_c.values())

    def pct(n, d):
        return round(100.0 * n / d, 4) if d else 0.0

    exec_p99 = sorted(exec_times_us)[int(0.99 * len(exec_times_us))]
    summary = {
        "experiment_id": "I1",
        "modality": "SIMULATION",
        "seed": SEED,
        "corpus": {
            "total": total, "valid": valid_total, "injected_anomalies": injected_total,
            "per_class": injected,
        },
        "baseline_C_full_gate": {
            "anomaly_rejection_rate_pct": pct(rejected_total, injected_total),
            "rejection_by_class_pct": {c: pct(rejected_c[c], injected[c]) for c in CLASSES},
            "false_rejection_rate_pct": pct(valid_rejected_c, valid_total),
            "accepted": accepted_c,
            "downweighted": downweighted_c,
        },
        "baseline_B_sequence_only": {
            "rejection_by_class_pct": {c: pct(rejected_b[c], injected[c]) for c in CLASSES},
        },
        "baseline_A_ungated": {
            "accepted_all_crc_pass": ungated_accepted,
        },
        "exec_time_us": {
            "mean": round(statistics.mean(exec_times_us), 2),
            "median": round(statistics.median(exec_times_us), 2),
            "p99": round(exec_p99, 2),
            "measurement": "host Python time.perf_counter (NOT ESP32 cycle counter)",
        },
        "note": ("Exec time is host-Python; the research-spec ESP32 <100 us "
                 "on-chip overhead claim remains UNVERIFIED until bench runs. "
                 "This experiment also serves as the VS3 slice measurement."),
    }

    dpath = os.path.join(repo_root(), "results", "derived")
    os.makedirs(dpath, exist_ok=True)
    with open(os.path.join(dpath, "I1_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    write_checksum_manifest()

    print(json.dumps(summary, indent=2, sort_keys=True))
    ok = (summary["baseline_C_full_gate"]["anomaly_rejection_rate_pct"] == 100.0
          and summary["baseline_C_full_gate"]["false_rejection_rate_pct"] == 0.0)
    print(f"\nI1/VS3: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
