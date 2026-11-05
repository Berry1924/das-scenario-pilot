"""Report rendering for ScenarioPilot vertical slices.

Receives results computed by adapter.run_scenario_arms and formats them.
It formats numbers it is given — it never recomputes metrics, and nothing
here sends data to or receives data from a language model.
"""

import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src"))

from daas_impl.simio import (git_hash, utc_now_iso, SOFTWARE_VERSION,
                             repo_root)

METRIC_LABELS = [
    ("pdr_percent", "PDR (%)", "{:.2f}"),
    ("rtt_mean_ms", "RTT mean (ms)", "{:.3f}"),
    ("rtt_p95_ms", "RTT p95 (ms)", "{:.3f}"),
    ("normal_msg_per_s", "Msgs/s/node", "{:.4f}"),
    ("emergency_pdr_percent", "Emergency PDR (%)", "{:.2f}"),
    ("emergency_p95_rtt_ms", "Emergency RTT p95 (ms)", "{:.3f}"),
    ("emergency_preempt_p95_ms", "Preempt airtime p95 (ms)", "{:.3f}"),
    ("packets_per_min", "Packets/min", "{:.2f}"),
    ("bytes_per_s", "Bytes/s", "{:.2f}"),
]


def _fmt(value, spec):
    if value is None:
        return ""
    return spec.format(value)


def paired_deltas(metrics_baseline: dict, metrics_daas: dict) -> dict:
    """Differences of the SAME computed metrics (daas - baseline).
    Pure subtraction of already-computed values, formatted consistently."""
    d = {}
    for key, label, _spec in METRIC_LABELS:
        b, a = metrics_baseline.get(key), metrics_daas.get(key)
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            d[label] = round(a - b, 4)
    for key in ("frames_offered", "frames_delivered", "acks_generated",
                "acks_received"):
        b, a = metrics_baseline.get(key), metrics_daas.get(key)
        if isinstance(b, int) and isinstance(a, int):
            d[key] = a - b
    return d


def build_report_markdown(results: dict) -> str:
    from muse.scenario import scenario_hash
    spec = results["spec"]
    review = results["review"]
    arms = results["arms"]
    b, a = arms["baseline"]["metrics"], arms["daas_v2v"]["metrics"]

    lines = [
        "# MUSE Vertical Slice Report — Baseline vs DAAS-V2V",
        "",
        f"- Generated (UTC): {utc_now_iso()}",
        f"- Modality: **SIMULATION** (software-level, no hardware involved)",
        f"- Scenario: `{spec.name}` · schema_version "
        f"{spec.raw.get('schema_version')} · scenario_hash "
        f"`{scenario_hash(spec)[:16]}…`",
        f"- Seed: `{spec.seed}` (both arms) · software: {SOFTWARE_VERSION} · "
        f"git: `{git_hash()[:12]}`",
        "",
        "## Scenario parameters",
        "",
        "| Parameter | Value |",
        "| --------: | :---- |",
    ]
    for k in ("num_vehicles", "duration_s", "dt_ms", "emergency_intensity",
              "emergency_duration_ms", "speed_mean_mps", "speed_jitter_mps",
              "loss_prob", "comm_range_m", "road_length_m",
              "trust_gate_enabled"):
        lines.append(f"| {k} | {spec.raw.get(k)} |")
    if spec.description:
        lines += ["", f"Description: {spec.description}"]

    lines += [
        "",
        "## Arms (identical conditions: same seed, same environment)",
        "",
        "| Arm | Policy | Emergency isolation |",
        "| :-- | :----- | :------------------ |",
        f"| baseline | `fixed` 10 Hz | `False` |",
        f"| daas_v2v | `adaptive` 2–20 Hz | `True` |",
        "",
        "## Computed metrics (existing WorldMetrics implementations)",
        "",
        "| Metric | baseline | daas_v2v | Δ (daas − baseline) |",
        "| :----- | -------: | -------: | ------------------: |",
    ]
    deltas = paired_deltas(b, a)
    for key, label, num_spec in METRIC_LABELS:
        lines.append(
            f"| {label} | {_fmt(b.get(key), num_spec)} | "
            f"{_fmt(a.get(key), num_spec)} | "
            f"{deltas.get(label, '')} |")

    lines += [
        "",
        "## Scenario review (Meta Model API — advisory only)",
        "",
        f"- Model: `{review.model}`",
        f"- Status: `{review.status}`"
        + (f" · verdict: `{review.verdict}`" if review.verdict else ""),
        f"- Content sha256: `{review.content_sha256[:16]}…`"
        if review.content_sha256 else "- Content sha256: (none)",
        f"- Latency: {review.latency_ms} ms",
    ]
    if review.error:
        lines.append(f"- Error: `{review.error}`")
    if review.summary:
        lines.append(f"- Summary: {review.summary}")
    lines += [
        "",
        "> The model review is advisory provenance. It does not gate, alter,",
        "> or compute any experiment value; validation was performed by the",
        "> strict local schema before any run started.",
        "",
        "## Evidence references",
        "",
        "| Artifact | Path |",
        "| :------- | :--- |",
    ]
    for arm in ("baseline", "daas_v2v"):
        r = arms[arm]
        lines += [
            f"| events ({arm}) | `{r['raw_csv_relpath']}` |",
            f"| metadata ({arm}) | `{r['metadata_json_relpath']}` |",
        ]
    lines += [
        "",
        "## Interpretation caveats",
        "",
        "- Both arms ran the verified `src/daas_impl` world; nothing was",
        "  reimplemented. Metrics come from the existing WorldMetrics code.",
        "- Arms are paired by seed and environment, not byte-identical RNG",
        "  streams (policy choice changes randomness consumption).",
        "- Results are SIMULATION results under the documented simplified",
        "  channel model; no hardware, C-V2X, deployment, or ML-policy claim.",
        "",
    ]
    return "\n".join(lines)


def write_report(results: dict, reports_dir: str | None = None) -> tuple:
    """Write Markdown + JSON sidecar; returns (md_path, json_path)."""
    if reports_dir is None:
        reports_dir = os.path.join(repo_root(), "results", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    name = results["spec"].name
    md_path = os.path.join(reports_dir, f"MUSE_report_{name}.md")
    json_path = os.path.join(reports_dir, f"MUSE_report_{name}.json")

    serialisable = {
        "scenario": results["spec"].raw,
        "scenario_hash": results["scenario_hash"],
        "seed": results["spec"].seed,
        "spark_review": results["review"].to_dict(),
        "arms": {},
        "paired_deltas": paired_deltas(
            results["arms"]["baseline"]["metrics"],
            results["arms"]["daas_v2v"]["metrics"]),
        "generated_utc": utc_now_iso(),
        "software_version": SOFTWARE_VERSION,
        "git_hash": git_hash(),
        "modality": "SIMULATION",
        "metrics_source": "WorldMetrics existing implementations; no LLM",
    }
    for arm in ("baseline", "daas_v2v"):
        r = results["arms"][arm]
        serialisable["arms"][arm] = {
            "policy": r["policy"],
            "emergency_isolation": r["emergency_isolation"],
            "seed": r["seed"],
            "events_logged": r["events_logged"],
            "status": r["status"],
            "metrics": r["metrics"],
            "raw_csv_relpath": r["raw_csv_relpath"],
            "metadata_json_relpath": r["metadata_json_relpath"],
        }

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_report_markdown(results))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, indent=2, sort_keys=True)
    return md_path, json_path
