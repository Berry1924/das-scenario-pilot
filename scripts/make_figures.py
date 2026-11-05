#!/usr/bin/env python3
"""Generate figures for the evidence package into results/plots/.

Reads derived summaries (results/derived/*.json) and raw CSVs. Uses
matplotlib when available; writes PNG at 150 dpi. SIMULATION data only.

Usage (from repo root):
  python3 scripts/make_figures.py
"""

import csv
import json
import os
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl.simio import repo_root

PLOTS = os.path.join(repo_root(), "results", "plots")
DERIVED = os.path.join(repo_root(), "results", "derived")


def load_json(name):
    with open(os.path.join(DERIVED, name)) as f:
        return json.load(f)


def fig_c1():
    s = load_json("C1_summary.json")
    tiers = sorted({int(k.split("_")[0][1:]) for k in s["tiers"]})
    fig, ax = plt.subplots(1, 3, figsize=(13, 4))
    for i, (metric, label) in enumerate([
            ("pdr_pct", "PDR (%)"), ("rtt_p95_ms", "RTT P95 (ms)"),
            ("packets_per_min", "Fleet packets/min")]):
        for policy, style in [("fixed", "o-"), ("adaptive", "s-")]:
            ys, es = [], []
            for t in tiers:
                st = s["tiers"][f"N{t}_{policy}"][metric]
                ys.append(st["mean"])
                es.append(st["std"])
            ax[i].errorbar(tiers, ys, yerr=es, fmt=style, capsize=3,
                           label=policy)
        ax[i].set_xlabel("Vehicle density N")
        ax[i].set_ylabel(label)
        ax[i].set_title(f"C1 (SIMULATION): {label}")
        ax[i].grid(alpha=0.3)
        ax[i].legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS, "C1_density.png"), dpi=150)
    plt.close()


def fig_t1():
    s = load_json("T1_summary.json")
    ages = [int(a) for a in sorted(s["rmse_by_age_over_accel_seeds"],
                                   key=lambda x: int(x))]
    means = [s["rmse_by_age_over_accel_seeds"][str(a)]["rmse_mean_s"] for a in ages]
    stds = [s["rmse_by_age_over_accel_seeds"][str(a)]["rmse_std_s"] for a in ages]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(ages, means, yerr=stds, fmt="o-", capsize=3, color="tab:red",
                label="stale TTC RMSE")
    ax.axvline(500, color="k", ls="--", alpha=0.6, label="500 ms freshness gate")
    ax.set_xlabel("Message age $A_j$ (ms)")
    ax.set_ylabel("TTC RMSE (s)")
    ax.set_title("T1 (SIMULATION): message age vs TTC estimation error\n"
                 "fit: RMSE = %.6f * A^%.3f" % (s["fit_rmse_alpha"], s["fit_rmse_beta"]))
    ax.grid(alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS, "T1_age_vs_ttc_error.png"), dpi=150)
    plt.close()


def fig_f1():
    s = load_json("F1_summary.json")
    tiers = ["clear", "light_dust", "moderate_fog", "dense_fog"]
    labels = ["Clear\n100 m", "Light dust\n50 m", "Moderate fog\n20 m",
              "Dense fog\n5 m"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    for method, style in [("local", "o-"), ("v2v", "^-"), ("fusion", "s-")]:
        ys = [s["tiers"][t][method]["warning_distance_m"]["mean"] for t in tiers]
        ax[0].plot(range(len(tiers)), ys, style, label=method)
        ys = [s["tiers"][t][method]["false_negative_rate_pct"] for t in tiers]
        ax[1].plot(range(len(tiers)), ys, style, label=method)
    ax[0].set_xticks(range(len(tiers)), labels)
    ax[0].set_ylabel("Warning distance (m)")
    ax[0].axhline(25, color="k", ls="--", alpha=0.5, label="25 m stop envelope")
    ax[0].set_title("F1 (SIMULATION): warning distance")
    ax[1].set_xticks(range(len(tiers)), labels)
    ax[1].set_ylabel("False-negative rate (%)")
    ax[1].set_title("F1 (SIMULATION): false-negative rate")
    for a in ax:
        a.grid(alpha=0.3)
        a.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS, "F1_fusion.png"), dpi=150)
    plt.close()


def fig_r1():
    with open(os.path.join(repo_root(), "results", "raw", "R1_scenarios.csv")) as f:
        rows = list(csv.DictReader(f))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for base in ["A_naive_volatile", "C_proposed"]:
        xs, ys = [], []
        for level in ["0.0", "0.1", "0.2", "0.3", "0.5", "1.0"]:
            g = [r for r in rows if r["scenario"] == "loss_scan"
                 and r["baseline"] == base and r["fault_param"] == level]
            if not g:
                continue
            xs.append(100.0 * float(level))
            ys.append(statistics.mean([float(r["warning_dropout_ms"]) for r in g]))
        ax.plot(xs, ys, "o-", label=base)
    ax.set_xlabel("Steady packet loss (%)")
    ax.set_ylabel("Warning dropout during hazard (ms)")
    ax.set_title("R1 (SIMULATION): warning continuity vs packet loss\n"
                 "(baseline B static-hang omitted: dropout=0 but ghost warnings)")
    ax.grid(alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS, "R1_fallback.png"), dpi=150)
    plt.close()


def fig_vs2():
    s = load_json("VS2_summary.json")
    configs = ["A_fixed_shared", "B_adaptive_no_isolation", "C_adaptive_isolation"]
    labels = ["A fixed/shared", "B adaptive\n(no isolation)", "C adaptive\n+ isolation"]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
    rates = [s["configs"][c]["emergency_msg_rate_hz"] for c in configs]
    preempts = [s["configs"][c]["emergency_preempt_p95_ms"] for c in configs]
    ax[0].bar(labels, rates, color=["tab:blue", "tab:orange", "tab:green"])
    ax[0].set_ylabel("Emergency msg rate during\nemergency windows (Hz)")
    ax[0].set_title("VS2 (SIMULATION): emergency rate")
    ax[1].bar(labels, preempts, color=["tab:blue", "tab:orange", "tab:green"])
    ax[1].set_ylabel("Emergency preemption P95 (ms)")
    ax[1].set_title("VS2 (SIMULATION): preemption latency")
    for a in ax:
        a.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS, "VS2_isolation.png"), dpi=150)
    plt.close()


def main() -> int:
    os.makedirs(PLOTS, exist_ok=True)
    made = []
    for name, fn in [("C1", fig_c1), ("T1", fig_t1), ("F1", fig_f1),
                     ("R1", fig_r1), ("VS2", fig_vs2)]:
        try:
            fn()
            made.append(name)
            print(f"[fig] {name} written")
        except FileNotFoundError as e:
            print(f"[fig] {name} skipped (missing derived file: {e})")
    print(f"[fig] {len(made)} figures in results/plots/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
