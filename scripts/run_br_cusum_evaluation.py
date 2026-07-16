#!/usr/bin/env python3
"""Pre-registered bidirectional robust CUSUM post-processing for UCI RMSE."""
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

EPSILON = 1e-12
PRIMARY_K = 0.50
KS = (0.25, 0.50, 1.00)
THRESHOLD_METHODS = ("q99", "q99_5", "q99_9")


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2); handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def source_dir(root: Path, attack: str) -> Path:
    return root / "mirai" if attack == "mirai" else root / "uci" / attack / "full"


def robust_parameters(calibration: np.ndarray) -> dict[str, float]:
    values = np.asarray(calibration, dtype=np.float64)
    if values.ndim != 1 or values.size != CALIBRATION_ROWS or not np.isfinite(values).all():
        raise ValueError("calibration must be exactly 10000 finite scores")
    median = float(np.median(values)); mad = float(np.median(np.abs(values - median)))
    return {"calibration_median": median, "calibration_mad": mad, "robust_scale": 1.4826 * mad + EPSILON, "epsilon": EPSILON}


def robust_channels(scores: np.ndarray, median: float, scale: float) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all() or scale <= 0:
        raise ValueError("scores must be finite and scale positive")
    return np.maximum(0.0, (values - median) / scale), np.maximum(0.0, (median - values) / scale)


def cusum(upper: np.ndarray, lower: np.ndarray, k: float, initial_plus: float = 0.0, initial_minus: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    if k < 0 or not np.isfinite(k):
        raise ValueError("k must be finite and non-negative")
    if upper.shape != lower.shape or upper.ndim != 1 or not np.isfinite(upper).all() or not np.isfinite(lower).all():
        raise ValueError("channels must be aligned finite vectors")
    plus, minus = np.empty_like(upper), np.empty_like(lower)
    cp, cm = float(initial_plus), float(initial_minus)
    for index, (u, l) in enumerate(zip(upper, lower)):
        cp = max(0.0, cp + float(u) - k); cm = max(0.0, cm + float(l) - k)
        plus[index] = cp; minus[index] = cm
    return plus, minus


def can_resume(status: str) -> bool:
    """Only completed derived stages are terminal; interrupted stages resume."""
    return status in {"interrupted", "failed", "running"}


def quantile_thresholds(calibration_scores: np.ndarray) -> dict[str, float]:
    values = np.asarray(calibration_scores, dtype=np.float64)
    if values.ndim != 1 or values.size != CALIBRATION_ROWS or not np.isfinite(values).all():
        raise ValueError("threshold calibration must be exactly 10000 finite scores")
    return {"q99": float(np.percentile(values, 99)), "q99_5": float(np.percentile(values, 99.5)), "q99_9": float(np.percentile(values, 99.9))}


def longest_nonzero_run(values: np.ndarray) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value > 0 else 0; longest = max(longest, current)
    return longest


def channel_audit(plus: np.ndarray, minus: np.ndarray, labels: np.ndarray, threshold: float) -> dict:
    upper_alert = plus >= threshold; lower_alert = minus >= threshold
    lower_only = lower_alert & ~upper_alert
    return {
        "upper_channel_alerts": int(upper_alert.sum()), "lower_channel_alerts": int(lower_alert.sum()),
        "lower_only_alerts": int(lower_only.sum()), "lower_only_attack_alerts": int(np.sum(lower_only & (labels == 1))),
        "upper_nonzero_fraction": float(np.mean(plus > 0)), "lower_nonzero_fraction": float(np.mean(minus > 0)),
        "upper_longest_nonzero_run": longest_nonzero_run(plus), "lower_longest_nonzero_run": longest_nonzero_run(minus),
        "upper_max": float(np.max(plus)), "lower_max": float(np.max(minus)),
        "cusum_drift_recorded": bool(longest_nonzero_run(plus) > 10_000 or longest_nonzero_run(minus) > 10_000),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def plot_attack(path: Path, attack: str, rmse: np.ndarray, score: np.ndarray, labels: np.ndarray, threshold: float) -> None:
    index = np.linspace(0, labels.size - 1, min(5000, labels.size), dtype=int)
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    axes[0].plot(index, rmse[index], linewidth=.45, label="baseline RMSE")
    axes[0].set_ylabel("RMSE"); axes[0].legend(fontsize=8)
    axes[1].plot(index, score[index], linewidth=.55, label="BR-CUSUM k=0.50")
    axes[1].axhline(threshold, color="#b22222", linestyle="--", label="q99.5 threshold")
    attacked = index[labels[index] == 1]
    if attacked.size: axes[1].scatter(attacked, np.zeros(attacked.size), s=2, color="#d95f02", label="attack intervals (audit)")
    axes[1].set_title(f"{attack}: n={labels.size:,}; calibration excluded; higher is more anomalous")
    axes[1].set_xlabel("evaluation-row index"); axes[1].set_ylabel("BR-CUSUM score"); axes[1].legend(fontsize=8)
    fig.tight_layout(); path.parent.mkdir(parents=True, exist_ok=True); fig.savefig(path, dpi=160); plt.close(fig)


def global_plots(directory: Path, summaries: list[dict], sensitivity: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True); names = [row["attack"].replace("_", " ") for row in summaries]
    for key, title in (("roc_auc", "ROC-AUC"), ("pr_auc", "PR-AUC"), ("f1", "F1"), ("fpr", "FPR")):
        fig, ax = plt.subplots(figsize=(13, 5)); x = np.arange(len(names)); width = .25
        for offset, method, color in ((-width, "baseline", "#777777"), (0, "ewma", "#4c78a8"), (width, "br_cusum", "#e45756")):
            values = [row[method][key] if row[method][key] is not None else np.nan for row in summaries]
            ax.bar(x + offset, values, width, label=method, color=color)
        ax.set_xticks(x, names, rotation=35, ha="right"); ax.set_title(f"Baseline vs EWMA vs BR-CUSUM: {title}"); ax.legend(); fig.tight_layout(); fig.savefig(directory / f"{key}_comparison.png", dpi=170); plt.close(fig)
    fig, ax = plt.subplots(figsize=(13, 5)); x = np.arange(len(names)); width = .25
    for offset, method, color in ((-width, "baseline", "#777777"), (0, "ewma", "#4c78a8"), (width, "br_cusum", "#e45756")):
        values = [row[method]["detection_delay_rows"] if row[method]["detection_delay_rows"] is not None else np.nan for row in summaries]
        ax.bar(x + offset, values, width, label=method, color=color)
    ax.set_xticks(x, names, rotation=35, ha="right"); ax.set_title("First-attack detection delay"); ax.set_ylabel("rows"); ax.legend(); fig.tight_layout(); fig.savefig(directory / "detection_delay_comparison.png", dpi=170); plt.close(fig)
    fig, axes = plt.subplots(3, 3, figsize=(16, 11)); axes = axes.ravel()
    for ax, attack in zip(axes, [row["attack"] for row in summaries]):
        rows = [row for row in sensitivity if row["attack"] == attack and row["threshold_method"] == PRIMARY_THRESHOLD]
        ax.plot([row["k"] for row in rows], [row["f1"] for row in rows], marker="o"); ax.set_title(f"{attack}: q99.5", fontsize=9); ax.set_xlabel("k"); ax.set_ylabel("F1")
    fig.suptitle("Pre-registered BR-CUSUM k sensitivity", y=1.01); fig.tight_layout(); fig.savefig(directory / "k_sensitivity.png", dpi=170, bbox_inches="tight"); plt.close(fig)


def classify(baseline: dict, br: dict) -> str:
    f1_delta = br["f1"] - baseline["f1"]; fpr_delta = (br["fpr"] or 0.0) - (baseline["fpr"] or 0.0)
    if f1_delta > .01 and fpr_delta <= .01: return "improved"
    if f1_delta < -.01 or fpr_delta > .01: return "degraded"
    return "approximately_unchanged"


def ewma_summary(root: Path) -> dict[str, dict]:
    path = root / "ewma" / "summary.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return {row["attack"]: row["ewma_primary"] for row in loaded["datasets"]}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--results-root", type=Path, default=Path("results/overnight-20260712")); args = parser.parse_args()
    root = args.results_root.resolve(); output = root / "br_cusum"; ewma = ewma_summary(root)
    protocol = {"status": "running", "calibration_rows": CALIBRATION_ROWS, "calibration_raw_start": 55_001, "calibration_raw_end": 65_000, "evaluation_start_raw_index": EVALUATION_START_RAW_INDEX, "threshold_source": "first_10000_execution_scores", "score_direction": "higher_is_more_anomalous", "epsilon": EPSILON, "main_k": PRIMARY_K, "main_threshold_method": PRIMARY_THRESHOLD, "candidate_k": list(KS), "candidate_thresholds": list(THRESHOLD_METHODS), "labels_used_for_parameter_selection": False, "cusum_initialization": {"C_plus_0": 0, "C_minus_0": 0}}
    atomic_json(output / "protocol.json", protocol); summaries, ablation, sensitivity = [], [], []
    for attack in ATTACKS:
        directory = output / attack; status_path = directory / "status.json"; atomic_json(status_path, {"status": "running", "attack": attack, "updated": datetime.now(timezone.utc).isoformat()})
        try:
            scores, labels = read_scores_labels(source_dir(root, attack), attack)
            calibration, evaluation_scores, evaluation_labels = scores[:CALIBRATION_ROWS], scores[CALIBRATION_ROWS:], labels[CALIBRATION_ROWS:]
            if evaluation_scores.size == 0: raise ValueError(f"{attack}: no evaluation rows")
            params = robust_parameters(calibration); upper, lower = robust_channels(scores, params["calibration_median"], params["robust_scale"])
            robust = np.maximum(upper, lower); base_thresholds = quantile_thresholds(calibration); robust_thresholds = quantile_thresholds(robust[:CALIBRATION_ROWS])
            base_auc, robust_auc = aucs(evaluation_scores, evaluation_labels), aucs(robust[CALIBRATION_ROWS:], evaluation_labels)
            baseline_metrics = {method: evaluate(evaluation_scores, evaluation_labels, threshold, base_auc) for method, threshold in base_thresholds.items()}
            robust_metrics = {method: evaluate(robust[CALIBRATION_ROWS:], evaluation_labels, threshold, robust_auc) for method, threshold in robust_thresholds.items()}
            all_cusum, all_thresholds, all_metrics = {}, {}, {}
            for k in KS:
                plus, minus = cusum(upper, lower, k); br = np.maximum(plus, minus); thresholds = quantile_thresholds(br[:CALIBRATION_ROWS]); score_auc = aucs(br[CALIBRATION_ROWS:], evaluation_labels)
                upper_auc = aucs(plus[CALIBRATION_ROWS:], evaluation_labels)
                all_cusum[k] = (plus, minus, br); all_thresholds[k] = thresholds
                all_metrics[k] = {method: evaluate(br[CALIBRATION_ROWS:], evaluation_labels, threshold, score_auc) for method, threshold in thresholds.items()}
                for method, metric in all_metrics[k].items(): sensitivity.append({"attack": attack, "k": k, "threshold_method": method, "threshold_value": thresholds[method], **metric})
            plus, minus, br = all_cusum[PRIMARY_K]; primary_threshold = all_thresholds[PRIMARY_K][PRIMARY_THRESHOLD]
            upper_threshold = quantile_thresholds(plus[:CALIBRATION_ROWS])[PRIMARY_THRESHOLD]
            upper_metrics = evaluate(plus[CALIBRATION_ROWS:], evaluation_labels, upper_threshold, aucs(plus[CALIBRATION_ROWS:], evaluation_labels))
            primary_br = all_metrics[PRIMARY_K][PRIMARY_THRESHOLD]
            audit = {"attack": attack, **params, "calibration_attack_count": int(labels[:CALIBRATION_ROWS].sum()), "calibration_benign_count": int(CALIBRATION_ROWS - labels[:CALIBRATION_ROWS].sum()), "calibration_contamination_rate": float(labels[:CALIBRATION_ROWS].mean()), "calibration_contaminated": bool(labels[:CALIBRATION_ROWS].sum()), "score_direction": "higher_is_more_anomalous", "threshold": primary_threshold, **channel_audit(plus[CALIBRATION_ROWS:], minus[CALIBRATION_ROWS:], evaluation_labels, primary_threshold), "upper_cusum_roc_auc": upper_metrics["roc_auc"], "extreme_score_ratio_to_median": float(np.max(br) / max(float(np.median(br)), EPSILON)), "all_scores_finite": bool(np.isfinite(br).all())}
            atomic_json(directory / "baseline_metrics.json", {"thresholds": base_thresholds, "primary": baseline_metrics[PRIMARY_THRESHOLD], "sensitivity": baseline_metrics})
            atomic_json(directory / "robust_two_sided_metrics.json", {"thresholds": robust_thresholds, "primary": robust_metrics[PRIMARY_THRESHOLD], "sensitivity": robust_metrics})
            atomic_json(directory / "upper_cusum_metrics.json", {"k": PRIMARY_K, "threshold": upper_threshold, "metrics": upper_metrics})
            atomic_json(directory / "br_cusum_metrics.json", {"k": PRIMARY_K, "thresholds": all_thresholds[PRIMARY_K], "primary": primary_br, "sensitivity": all_metrics})
            atomic_json(directory / "temporal_metrics.json", {"baseline": {k: baseline_metrics[PRIMARY_THRESHOLD][k] for k in baseline_metrics[PRIMARY_THRESHOLD] if "attack" in k or "alert" in k or "delay" in k}, "robust_two_sided": {k: robust_metrics[PRIMARY_THRESHOLD][k] for k in robust_metrics[PRIMARY_THRESHOLD] if "attack" in k or "alert" in k or "delay" in k}, "upper_cusum": {k: upper_metrics[k] for k in upper_metrics if "attack" in k or "alert" in k or "delay" in k}, "br_cusum": {k: primary_br[k] for k in primary_br if "attack" in k or "alert" in k or "delay" in k}})
            atomic_json(directory / "channel_audit.json", audit); plot_attack(directory / "plots" / "timeseries.png", attack, evaluation_scores, br[CALIBRATION_ROWS:], evaluation_labels, primary_threshold)
            for name, metric in (("baseline", baseline_metrics[PRIMARY_THRESHOLD]), ("robust_two_sided", robust_metrics[PRIMARY_THRESHOLD]), ("upper_cusum", upper_metrics), ("br_cusum", primary_br), ("ewma", ewma[attack])): ablation.append({"attack": attack, "method": name, "k": (PRIMARY_K if "cusum" in name else None), "threshold_method": PRIMARY_THRESHOLD, **metric})
            summaries.append({"attack": attack, "calibration_attack_count": audit["calibration_attack_count"], "calibration_contamination_rate": audit["calibration_contamination_rate"], "evaluation_rows": int(evaluation_labels.size), "classification": classify(baseline_metrics[PRIMARY_THRESHOLD], primary_br), "baseline": baseline_metrics[PRIMARY_THRESHOLD], "ewma": ewma[attack], "br_cusum": primary_br, "channel_audit": audit})
            atomic_json(status_path, {"status": "completed", "attack": attack, "updated": datetime.now(timezone.utc).isoformat(), "message": "BR-CUSUM evaluation completed"})
        except Exception as error:
            atomic_json(status_path, {"status": "failed", "attack": attack, "updated": datetime.now(timezone.utc).isoformat(), "message": str(error)}); raise
    write_csv(output / "ablation.csv", ablation); write_csv(output / "sensitivity.csv", sensitivity)
    write_csv(output / "summary.csv", [{"attack": row["attack"], "calibration_attack_count": row["calibration_attack_count"], "calibration_contamination_rate": row["calibration_contamination_rate"], "evaluation_rows": row["evaluation_rows"], "classification": row["classification"], **{f"baseline_{k}": v for k, v in row["baseline"].items()}, **{f"ewma_{k}": v for k, v in row["ewma"].items()}, **{f"br_cusum_{k}": v for k, v in row["br_cusum"].items()}, **{f"channel_{k}": v for k, v in row["channel_audit"].items() if isinstance(v, (str, int, float, bool))}} for row in summaries])
    atomic_json(output / "summary.json", {"protocol": protocol, "datasets": summaries, "oracle_exploratory_upper_bound": "not computed; fixed sensitivity grid is not test-label-selected"}); global_plots(output / "plots", summaries, sensitivity)
    protocol["status"] = "completed"; atomic_json(output / "protocol.json", protocol); print(json.dumps({"datasets": len(summaries), "status": "completed"}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
