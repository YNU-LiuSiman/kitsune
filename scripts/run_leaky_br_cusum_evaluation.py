#!/usr/bin/env python3
"""Final pre-registered drift-control evaluation for Leaky BR-CUSUM."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_ewma_evaluation import ATTACKS, CALIBRATION_ROWS, EVALUATION_START_RAW_INDEX, PRIMARY_THRESHOLD, aucs, evaluate, read_scores_labels
from run_br_cusum_evaluation import EPSILON, PRIMARY_K, channel_audit, longest_nonzero_run, quantile_thresholds, robust_channels, robust_parameters, source_dir

PRIMARY_RHO = 0.95
RHOS = (0.90, 0.95, 0.99)
KS = (0.25, 0.50, 1.00)
THRESHOLDS = ("q99", "q99_5", "q99_9")


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2); handle.write("\n"); temporary = Path(handle.name)
    os.replace(temporary, path)


def leaky_cusum(upper: np.ndarray, lower: np.ndarray, rho: float, k: float, initial_plus: float = 0.0, initial_minus: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 <= rho <= 1.0 or k < 0 or not np.isfinite(rho) or not np.isfinite(k): raise ValueError("rho must be in [0,1] and k non-negative")
    if upper.shape != lower.shape or upper.ndim != 1 or not np.isfinite(upper).all() or not np.isfinite(lower).all(): raise ValueError("channels must be aligned finite vectors")
    plus, minus = np.empty_like(upper), np.empty_like(lower); cp, cm = float(initial_plus), float(initial_minus)
    for index, (u, l) in enumerate(zip(upper, lower)):
        cp = max(0.0, rho * cp + float(u) - k); cm = max(0.0, rho * cm + float(l) - k); plus[index] = cp; minus[index] = cm
    return plus, minus


def drift_audit(score: np.ndarray, plus: np.ndarray, minus: np.ndarray, labels: np.ndarray, threshold: float) -> dict:
    base = channel_audit(plus, minus, labels, threshold); start, end = float(score[0]), float(score[-1])
    return {**base, "evaluation_score_start": start, "evaluation_score_end": end, "score_max": float(np.max(score)), "score_median": float(np.median(score)), "fraction_score_nonzero": float(np.mean(score > 0)), "longest_nonzero_run": longest_nonzero_run(score), "end_to_start_ratio": (end / start if abs(start) > EPSILON else None), "state_reset_count": 0, "all_scores_finite": bool(np.isfinite(score).all())}


def csv_write(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def load_primary(root: Path, directory: str, key: str) -> dict[str, dict]:
    doc = json.loads((root / directory / "summary.json").read_text(encoding="utf-8"))
    return {row["attack"]: row[key] for row in doc["datasets"]}


def classify(original: dict, leaky: dict) -> str:
    f1_delta = leaky["f1"] - original["f1"]; fpr_delta = (leaky["fpr"] or 0.0) - (original["fpr"] or 0.0)
    if f1_delta > .01 and fpr_delta <= .01: return "improved"
    if f1_delta < -.01 or fpr_delta > .01: return "degraded"
    return "approximately_unchanged"


def plot_attack(path: Path, attack: str, score: np.ndarray, labels: np.ndarray, threshold: float, rho: float) -> None:
    index = np.linspace(0, labels.size - 1, min(labels.size, 5000), dtype=int); fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(index, score[index], linewidth=.6, label=f"Leaky BR-CUSUM rho={rho:.2f}, k=0.50")
    ax.axhline(threshold, color="#b22222", linestyle="--", label="q99.5 threshold")
    attacked = index[labels[index] == 1]
    if attacked.size: ax.scatter(attacked, np.zeros(attacked.size), s=2, color="#d95f02", label="attack intervals (audit)")
    ax.set_title(f"{attack}: evaluation n={labels.size:,}; fixed calibration excluded; higher is anomalous")
    ax.set_xlabel("evaluation-row index"); ax.set_ylabel("Leaky BR-CUSUM score"); ax.legend(fontsize=8); fig.tight_layout(); path.parent.mkdir(parents=True, exist_ok=True); fig.savefig(path, dpi=160); plt.close(fig)


def global_plots(directory: Path, rows: list[dict], sensitivity: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True); names = [row["attack"].replace("_", " ") for row in rows]
    for field, title in (("roc_auc", "ROC-AUC"), ("pr_auc", "PR-AUC"), ("f1", "F1"), ("fpr", "FPR")):
        fig, ax = plt.subplots(figsize=(13, 5)); x = np.arange(len(names)); width = .20
        for offset, method, color in ((-1.5*width, "baseline", "#777"), (-.5*width, "ewma", "#4c78a8"), (.5*width, "br_cusum", "#e45756"), (1.5*width, "leaky", "#54a24b")):
            ax.bar(x + offset, [row[method][field] if row[method][field] is not None else np.nan for row in rows], width, label=method, color=color)
        ax.set_xticks(x, names, rotation=35, ha="right"); ax.set_title(f"Four-method comparison: {title}"); ax.legend(); fig.tight_layout(); fig.savefig(directory / f"{field}_comparison.png", dpi=170); plt.close(fig)
    fig, ax = plt.subplots(figsize=(13, 5)); x = np.arange(len(names)); width = .20
    for offset, method, color in ((-1.5*width, "baseline", "#777"), (-.5*width, "ewma", "#4c78a8"), (.5*width, "br_cusum", "#e45756"), (1.5*width, "leaky", "#54a24b")):
        ax.bar(x + offset, [row[method]["detection_delay_rows"] if row[method]["detection_delay_rows"] is not None else np.nan for row in rows], width, label=method, color=color)
    ax.set_xticks(x, names, rotation=35, ha="right"); ax.set_ylabel("rows"); ax.set_title("First-attack detection delay"); ax.legend(); fig.tight_layout(); fig.savefig(directory / "detection_delay_comparison.png", dpi=170); plt.close(fig)
    fig, axes = plt.subplots(3, 3, figsize=(16, 11)); axes = axes.ravel()
    for ax, attack in zip(axes, [row["attack"] for row in rows]):
        values = [item for item in sensitivity if item["attack"] == attack and item["k"] == PRIMARY_K and item["threshold_method"] == PRIMARY_THRESHOLD]
        ax.plot([item["rho"] for item in values], [item["f1"] for item in values], marker="o"); ax.set_title(attack, fontsize=9); ax.set_xlabel("rho"); ax.set_ylabel("F1")
    fig.suptitle("Pre-registered rho sensitivity (k=0.50, q99.5)", y=1.01); fig.tight_layout(); fig.savefig(directory / "rho_sensitivity.png", dpi=170, bbox_inches="tight"); plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--results-root", type=Path, default=Path("results/overnight-20260712")); args = parser.parse_args(); root = args.results_root.resolve(); output = root / "leaky_br_cusum"
    ewma = load_primary(root, "ewma", "ewma_primary"); original = load_primary(root, "br_cusum", "br_cusum")
    baseline_doc = json.loads((root / "ewma" / "summary.json").read_text(encoding="utf-8")); baseline_map = {entry["attack"]: entry["baseline_primary"] for entry in baseline_doc["datasets"]}
    protocol = {"status": "running", "calibration_rows": CALIBRATION_ROWS, "calibration_raw_start": 55_001, "calibration_raw_end": 65_000, "evaluation_start_raw_index": EVALUATION_START_RAW_INDEX, "threshold_source": "first_10000_execution_scores", "score_direction": "higher_is_more_anomalous", "epsilon": EPSILON, "main_rho": PRIMARY_RHO, "main_k": PRIMARY_K, "main_threshold_method": PRIMARY_THRESHOLD, "candidate_rho": list(RHOS), "candidate_k": list(KS), "candidate_thresholds": list(THRESHOLDS), "labels_used_for_parameter_selection": False, "state_reset_count": 0, "reset_on_alarm": "not part of main protocol"}; atomic_json(output / "protocol.json", protocol)
    rows, comparison, sensitivity, drifts = [], [], [], []
    for attack in ATTACKS:
        directory = output / attack; status = directory / "status.json"; atomic_json(status, {"status": "running", "attack": attack, "updated": datetime.now(timezone.utc).isoformat()})
        try:
            scores, labels = read_scores_labels(source_dir(root, attack), attack); calibration = scores[:CALIBRATION_ROWS]; ys = labels[CALIBRATION_ROWS:]
            params = robust_parameters(calibration); upper, lower = robust_channels(scores, params["calibration_median"], params["robust_scale"])
            all_scores, all_thresholds, all_metrics = {}, {}, {}
            for rho in RHOS:
                for k in KS:
                    plus, minus = leaky_cusum(upper, lower, rho, k); score = np.maximum(plus, minus); thresholds = quantile_thresholds(score[:CALIBRATION_ROWS]); score_auc = aucs(score[CALIBRATION_ROWS:], ys)
                    all_scores[(rho, k)] = (plus, minus, score); all_thresholds[(rho, k)] = thresholds; all_metrics[(rho, k)] = {method: evaluate(score[CALIBRATION_ROWS:], ys, value, score_auc) for method, value in thresholds.items()}
                    for method, metric in all_metrics[(rho, k)].items(): sensitivity.append({"attack": attack, "rho": rho, "k": k, "threshold_method": method, "threshold_value": thresholds[method], **metric})
            plus, minus, score = all_scores[(PRIMARY_RHO, PRIMARY_K)]; threshold = all_thresholds[(PRIMARY_RHO, PRIMARY_K)][PRIMARY_THRESHOLD]; primary = all_metrics[(PRIMARY_RHO, PRIMARY_K)][PRIMARY_THRESHOLD]
            audit = {"attack": attack, **params, "rho": PRIMARY_RHO, "k": PRIMARY_K, "threshold": threshold, "calibration_attack_count": int(labels[:CALIBRATION_ROWS].sum()), "calibration_contamination_rate": float(labels[:CALIBRATION_ROWS].mean()), "calibration_contaminated": bool(labels[:CALIBRATION_ROWS].sum()), "score_direction": "higher_is_more_anomalous", **drift_audit(score[CALIBRATION_ROWS:], plus[CALIBRATION_ROWS:], minus[CALIBRATION_ROWS:], ys, threshold)}
            atomic_json(directory / "metrics.json", {"main": primary, "thresholds": all_thresholds[(PRIMARY_RHO, PRIMARY_K)], "sensitivity": {f"rho_{rho:.2f}_k_{k:.2f}": values for (rho, k), values in all_metrics.items()}})
            atomic_json(directory / "temporal_metrics.json", {key: value for key, value in primary.items() if "attack" in key or "alert" in key or "delay" in key})
            atomic_json(directory / "drift_audit.json", audit); atomic_json(directory / "channel_audit.json", {key: audit[key] for key in audit if "channel" in key or "lower" in key or "upper" in key})
            plot_attack(directory / "plots" / "timeseries.png", attack, score[CALIBRATION_ROWS:], ys, threshold, PRIMARY_RHO)
            # Baseline is taken from EWMA's fixed-split summary for the identical protocol.
            for method, metric in (("baseline", baseline_map[attack]), ("ewma", ewma[attack]), ("br_cusum", original[attack]), ("leaky_br_cusum", primary)):
                comparison.append({"attack": attack, "method": method, "rho": (PRIMARY_RHO if method == "leaky_br_cusum" else None), "k": (PRIMARY_K if method == "leaky_br_cusum" else None), **metric})
            rows.append({"attack": attack, "classification_vs_br_cusum": classify(original[attack], primary), "baseline": baseline_map[attack], "ewma": ewma[attack], "br_cusum": original[attack], "leaky": primary, "drift": audit})
            drifts.append({"attack": attack, **{key: value for key, value in audit.items() if isinstance(value, (str, int, float, bool))}}); atomic_json(status, {"status": "completed", "attack": attack, "updated": datetime.now(timezone.utc).isoformat()})
        except Exception as error:
            atomic_json(status, {"status": "failed", "attack": attack, "updated": datetime.now(timezone.utc).isoformat(), "message": str(error)}); raise
    csv_write(output / "comparison.csv", comparison); csv_write(output / "sensitivity.csv", sensitivity); csv_write(output / "drift_audit.csv", drifts)
    csv_write(output / "summary.csv", [{"attack": row["attack"], "classification_vs_br_cusum": row["classification_vs_br_cusum"], **{f"baseline_{k}": v for k, v in row["baseline"].items()}, **{f"ewma_{k}": v for k, v in row["ewma"].items()}, **{f"br_cusum_{k}": v for k, v in row["br_cusum"].items()}, **{f"leaky_{k}": v for k, v in row["leaky"].items()}, **{f"drift_{k}": v for k, v in row["drift"].items() if isinstance(v, (str, int, float, bool))}} for row in rows])
    atomic_json(output / "summary.json", {"protocol": protocol, "datasets": rows, "oracle_exploratory_upper_bound": "not computed; sensitivity grid is not label-selected"}); global_plots(output / "plots", rows, sensitivity); protocol["status"] = "completed"; atomic_json(output / "protocol.json", protocol); print(json.dumps({"datasets": len(rows), "status": "completed"}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
