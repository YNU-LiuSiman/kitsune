#!/usr/bin/env python3
"""Run the pre-registered, label-free threshold and EWMA UCI evaluation.

Baseline RMSE files are read-only. Threshold functions deliberately accept
scores only, so labels cannot participate in calibration or parameter choice.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata
from scipy.signal import lfilter

GRACE_ROWS = 55_001
CALIBRATION_ROWS = 10_000
EVALUATION_START_RAW_INDEX = 65_001
PRIMARY_ALPHA = 0.10
PRIMARY_THRESHOLD = "q99_5"
ALPHAS = (0.05, 0.10, 0.20, 0.30, 0.50)
ATTACKS = ("mirai", "os_scan", "fuzzing", "ssl_renegotiation", "arp_mitm", "syn_dos", "active_wiretap", "ssdp_flood", "video_injection")


def result_dir(root: Path, attack: str) -> Path:
    return root / "mirai" if attack == "mirai" else root / "uci" / attack / "full"


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def read_scores_labels(directory: Path, attack: str) -> tuple[np.ndarray, np.ndarray]:
    labelled_path = directory / "raw" / "rmse_with_labels.csv"
    rows = np.loadtxt(labelled_path, delimiter=",", skiprows=1, dtype=np.float64)
    rows = np.atleast_2d(rows)
    if rows.shape[1] != 2:
        raise ValueError(f"{attack}: expected rmse,label columns")
    scores = rows[:, 0]
    labels_as_float = rows[:, 1]
    if not np.isfinite(scores).all() or not np.isfinite(labels_as_float).all():
        raise ValueError(f"{attack}: non-finite score or label")
    if not np.isin(labels_as_float, (0.0, 1.0)).all():
        raise ValueError(f"{attack}: labels must be 0 or 1")
    labels = labels_as_float.astype(np.int8)
    plain = np.loadtxt(directory / "raw" / "rmse.csv", delimiter=",", skiprows=1, dtype=np.float64)
    plain = np.atleast_1d(plain)
    if plain.size != scores.size or not np.array_equal(plain, scores):
        raise ValueError(f"{attack}: rmse.csv does not exactly align with labelled scores")
    return scores, labels


def ewma(scores: np.ndarray, alpha: float, initial: float | None = None) -> np.ndarray:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise ValueError("scores must be a non-empty finite 1-D series")
    state = float(values[0] if initial is None else initial)
    if alpha == 0.0:
        return np.full_like(values, state)
    # lfilter computes the same recurrence without a Python loop. Its initial
    # delay is chosen so y[0] = alpha*x[0] + (1-alpha)*state.
    output, _ = lfilter([alpha], [1.0, -(1.0 - alpha)], values, zi=[(1.0 - alpha) * state])
    return output


def threshold_values(calibration_scores: np.ndarray) -> dict[str, float]:
    """Compute thresholds from scores only; no labels are accepted here."""
    values = np.asarray(calibration_scores, dtype=np.float64)
    if values.ndim != 1 or values.size != CALIBRATION_ROWS or not np.isfinite(values).all():
        raise ValueError(f"calibration must contain exactly {CALIBRATION_ROWS} finite scores")
    mean, std = float(np.mean(values)), float(np.std(values))
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return {
        "q99": float(np.percentile(values, 99)), "q99_5": float(np.percentile(values, 99.5)), "q99_9": float(np.percentile(values, 99.9)),
        "mean_plus_3std": mean + 3 * std, "mean_plus_4std": mean + 4 * std, "mean_plus_5std": mean + 5 * std,
        "median_plus_3mad": median + 3 * mad, "median_plus_5mad": median + 5 * mad, "median_plus_7mad": median + 7 * mad,
    }


def aucs(scores: np.ndarray, labels: np.ndarray) -> tuple[float | None, float | None]:
    positive = int(labels.sum()); negative = int(labels.size - positive)
    if not positive or not negative:
        return None, None
    ranks = rankdata(scores, method="average")
    roc = float((ranks[labels == 1].sum() - positive * (positive + 1) / 2) / (positive * negative))
    order = np.argsort(scores, kind="mergesort")[::-1]
    ordered_labels = labels[order]
    precision = np.cumsum(ordered_labels) / np.arange(1, labels.size + 1)
    pr = float(precision[ordered_labels == 1].sum() / positive)
    return roc, pr


def attack_ranges(labels: np.ndarray) -> list[tuple[int, int]]:
    starts = np.flatnonzero((labels == 1) & np.r_[True, labels[:-1] != 1])
    ends = np.flatnonzero((labels == 1) & np.r_[labels[1:] != 1, True])
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def alert_segments(predictions: np.ndarray) -> int:
    return int(np.sum(predictions & np.r_[True, ~predictions[:-1]]))


def should_skip_completed(status_path: Path, no_overwrite: bool) -> bool:
    """Completed derived outputs are retained; interrupted/failed runs resume."""
    if not no_overwrite or not status_path.exists():
        return False
    return json.loads(status_path.read_text(encoding="utf-8")).get("status") == "completed"


def temporal_metrics(predictions: np.ndarray, labels: np.ndarray) -> dict:
    intervals = attack_ranges(labels)
    detected = 0
    first_delay = None
    for start, end in intervals:
        hits = np.flatnonzero(predictions[start:end + 1])
        if hits.size:
            detected += 1
            if start == intervals[0][0]:
                first_delay = int(hits[0])
    return {
        "first_attack_evaluation_index": intervals[0][0] if intervals else None,
        "first_attack_raw_index": EVALUATION_START_RAW_INDEX + intervals[0][0] if intervals else None,
        "first_detection_evaluation_index": (intervals[0][0] + first_delay if first_delay is not None and intervals else None),
        "first_detection_raw_index": (EVALUATION_START_RAW_INDEX + intervals[0][0] + first_delay if first_delay is not None and intervals else None),
        "detection_delay_rows": first_delay,
        "attack_interval_count": len(intervals), "detected_attack_intervals": detected,
        "attack_interval_detection_rate": (detected / len(intervals) if intervals else None),
        "benign_false_positive_count": int(np.sum(predictions & (labels == 0))),
        "continuous_alert_segments": alert_segments(predictions),
    }


def evaluate(scores: np.ndarray, labels: np.ndarray, threshold: float, precomputed_aucs: tuple[float | None, float | None] | None = None) -> dict:
    if scores.size != labels.size:
        raise ValueError("score/label mismatch in evaluation")
    predictions = scores >= threshold
    tp = int(np.sum(predictions & (labels == 1))); fp = int(np.sum(predictions & (labels == 0)))
    tn = int(np.sum(~predictions & (labels == 0))); fn = int(np.sum(~predictions & (labels == 1)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else None
    fpr = fp / (fp + tn) if fp + tn else None
    fnr = fn / (fn + tp) if fn + tp else None
    roc, pr = precomputed_aucs if precomputed_aucs is not None else aucs(scores, labels)
    return {
        "roc_auc": roc, "pr_auc": pr, "precision": precision, "recall": recall,
        "f1": (2 * precision * recall / (precision + recall) if precision + recall else 0.0),
        "accuracy": (tp + tn) / labels.size if labels.size else None, "specificity": specificity,
        "fpr": fpr, "fnr": fnr, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        **temporal_metrics(predictions, labels),
    }


def classification(primary_baseline: dict, primary_ewma: dict) -> str:
    # This is a descriptive, predeclared comparison: F1 improves only when it
    # rises by more than 0.01, and FPR must not rise by more than 0.01.
    f1_delta = primary_ewma["f1"] - primary_baseline["f1"]
    fpr_delta = (primary_ewma["fpr"] or 0.0) - (primary_baseline["fpr"] or 0.0)
    if f1_delta > 0.01 and fpr_delta <= 0.01:
        return "improved"
    if f1_delta < -0.01 or fpr_delta > 0.01:
        return "degraded"
    return "approximately_unchanged"


def plot_attack(path: Path, attack: str, baseline: np.ndarray, smoothed: np.ndarray, labels: np.ndarray, threshold: float, prevalence: float) -> None:
    maximum = min(labels.size, 25_000)
    indexes = np.linspace(0, labels.size - 1, min(labels.size, 5000), dtype=int)
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(indexes, baseline[indexes], linewidth=.45, alpha=.55, label="baseline RMSE")
    ax.plot(indexes, smoothed[indexes], linewidth=.7, label="EWMA alpha=0.10")
    ax.axhline(threshold, color="#b22222", linestyle="--", linewidth=1, label="EWMA q99.5 threshold")
    attack_indexes = indexes[labels[indexes] == 1]
    if attack_indexes.size:
        ax.scatter(attack_indexes, np.full(attack_indexes.size, np.nanmin(np.r_[baseline[indexes], smoothed[indexes]])), s=2, color="#d95f02", label="attack intervals (audit)")
    ax.set_title(f"{attack}: n={labels.size:,}, attack={prevalence:.2%}, alpha=0.10, evaluation starts raw {EVALUATION_START_RAW_INDEX}")
    ax.set_xlabel("evaluation-row index"); ax.set_ylabel("score; higher is more anomalous"); ax.legend(fontsize=8, ncol=2)
    fig.tight_layout(); path.parent.mkdir(parents=True, exist_ok=True); fig.savefig(path, dpi=160); plt.close(fig)


def global_plots(root: Path, summaries: list[dict], alpha_rows: list[dict], threshold_rows: list[dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    names = [item["attack"].replace("_", " ") for item in summaries]
    pairs = [("roc_auc", "ROC-AUC"), ("pr_auc", "PR-AUC"), ("f1", "F1"), ("recall", "Recall"), ("fpr", "FPR")]
    for key, title in pairs:
        fig, ax = plt.subplots(figsize=(12, 5)); x = np.arange(len(names)); width = .38
        baseline = [item["baseline_primary"][key] if item["baseline_primary"][key] is not None else np.nan for item in summaries]
        smoothed = [item["ewma_primary"][key] if item["ewma_primary"][key] is not None else np.nan for item in summaries]
        ax.bar(x-width/2, baseline, width, label="baseline q99.5"); ax.bar(x+width/2, smoothed, width, label="EWMA alpha=0.10 q99.5")
        ax.set_xticks(x, names, rotation=35, ha="right"); ax.set_title(f"Nine UCI evaluation-only {title}; calibration rows excluded"); ax.legend(); fig.tight_layout(); fig.savefig(root / f"{key}_comparison.png", dpi=170); plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 5)); values = [item["ewma_primary"]["detection_delay_rows"] if item["ewma_primary"]["detection_delay_rows"] is not None else np.nan for item in summaries]
    ax.bar(names, values); ax.set_title("EWMA alpha=0.10 detection delay by first attack interval"); ax.set_ylabel("rows after first attack"); ax.tick_params(axis="x", rotation=35); fig.tight_layout(); fig.savefig(root / "detection_delay_comparison.png", dpi=170); plt.close(fig)
    fig, axes = plt.subplots(3, 3, figsize=(16, 11)); axes = axes.ravel()
    for ax, attack in zip(axes, [item["attack"] for item in summaries]):
        rows = [row for row in alpha_rows if row["attack"] == attack]
        ax.plot([row["alpha"] for row in rows], [row["f1"] for row in rows], marker="o")
        ax.set_title(f"{attack}: q99.5 sensitivity", fontsize=9); ax.set_xlabel("alpha"); ax.set_ylabel("F1")
    fig.suptitle("Pre-registered alpha sensitivity; no test-label selection", y=1.01); fig.tight_layout(); fig.savefig(root / "alpha_sensitivity.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    methods = list(threshold_values(np.ones(CALIBRATION_ROWS)).keys())
    fig, axes = plt.subplots(3, 3, figsize=(18, 11)); axes = axes.ravel()
    for ax, attack in zip(axes, [item["attack"] for item in summaries]):
        rows = [row for row in threshold_rows if row["attack"] == attack and row["series"] == "ewma" and row["alpha"] == PRIMARY_ALPHA]
        indexed = {row["threshold_method"]: row["f1"] for row in rows}
        ax.plot(range(len(methods)), [indexed[method] for method in methods], marker="o")
        ax.set_title(f"{attack}: EWMA alpha=0.10", fontsize=9); ax.set_xticks(range(len(methods)), methods, rotation=50, ha="right", fontsize=7); ax.set_ylabel("F1")
    fig.suptitle("Pre-registered threshold-method sensitivity; no test-label selection", y=1.01); fig.tight_layout(); fig.savefig(root / "threshold_sensitivity.png", dpi=170, bbox_inches="tight"); plt.close(fig)


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("results/overnight-20260712"))
    parser.add_argument("--no-overwrite", action="store_true")
    args = parser.parse_args(); root = args.results_root.resolve(); output = root / "ewma"
    protocol = {"status": "running", "calibration_rows": CALIBRATION_ROWS, "calibration_raw_start": GRACE_ROWS, "calibration_raw_end": 65_000, "evaluation_start_raw_index": EVALUATION_START_RAW_INDEX, "threshold_source": "first_10000_execution_scores", "score_direction": "higher_is_more_anomalous", "main_alpha": PRIMARY_ALPHA, "main_threshold_method": PRIMARY_THRESHOLD, "ewma_initialization": "first_calibration_rmse", "candidate_alphas": list(ALPHAS), "threshold_methods": list(threshold_values(np.ones(CALIBRATION_ROWS)).keys()), "labels_used_for_calibration": False, "prediction_rule": "score >= threshold"}
    atomic_json(output / "protocol.json", protocol)
    summaries, threshold_rows, alpha_rows = [], [], []
    for attack in ATTACKS:
        attack_output = output / attack
        status_path = attack_output / "status.json"
        if should_skip_completed(status_path, args.no_overwrite):
            continue
        atomic_json(status_path, {"status": "running", "attack": attack, "updated": datetime.now(timezone.utc).isoformat()})
        try:
            scores, labels = read_scores_labels(result_dir(root, attack), attack)
            if scores.size <= CALIBRATION_ROWS:
                raise ValueError(f"{attack}: insufficient execution rows for calibration/evaluation split")
            calibration = scores[:CALIBRATION_ROWS]
            evaluation_scores, evaluation_labels = scores[CALIBRATION_ROWS:], labels[CALIBRATION_ROWS:]
            baseline_thresholds = threshold_values(calibration)
            baseline_aucs = aucs(evaluation_scores, evaluation_labels)
            baseline_all = {name: evaluate(evaluation_scores, evaluation_labels, value, baseline_aucs) for name, value in baseline_thresholds.items()}
            ewma_by_alpha, ewma_thresholds, ewma_all = {}, {}, {}
            for alpha in ALPHAS:
                smooth = ewma(scores, alpha, initial=float(calibration[0]))
                thresholds = threshold_values(smooth[:CALIBRATION_ROWS])
                ewma_by_alpha[alpha] = smooth
                ewma_thresholds[alpha] = thresholds
                smooth_scores = smooth[CALIBRATION_ROWS:]
                smooth_aucs = aucs(smooth_scores, evaluation_labels)
                ewma_all[alpha] = {name: evaluate(smooth_scores, evaluation_labels, value, smooth_aucs) for name, value in thresholds.items()}
                alpha_rows.append({"attack": attack, "alpha": alpha, "threshold_method": PRIMARY_THRESHOLD, "threshold_value": thresholds[PRIMARY_THRESHOLD], **ewma_all[alpha][PRIMARY_THRESHOLD]})
            primary_baseline = baseline_all[PRIMARY_THRESHOLD]
            primary_ewma = ewma_all[PRIMARY_ALPHA][PRIMARY_THRESHOLD]
            calibration_attack_count = int(labels[:CALIBRATION_ROWS].sum())
            audit = {"attack": attack, "execution_start_raw_index": GRACE_ROWS, "calibration_rows": CALIBRATION_ROWS, "evaluation_start_raw_index": EVALUATION_START_RAW_INDEX, "calibration_attack_count": calibration_attack_count, "calibration_benign_count": int(CALIBRATION_ROWS - calibration_attack_count), "calibration_contaminated": bool(calibration_attack_count), "calibration_contamination_rate": calibration_attack_count / CALIBRATION_ROWS, "score_label_exact_alignment": True, "score_direction": "higher_is_more_anomalous"}
            thresholds_doc = {"attack": attack, "threshold_source": "first_10000_execution_scores", "calibration_rows": CALIBRATION_ROWS, "baseline": baseline_thresholds, "ewma": {str(alpha): values for alpha, values in ewma_thresholds.items()}, "mad_definition": "median(abs(score - median(score)))", "labels_used_for_calibration": False}
            baseline_doc = {"attack": attack, "primary": {"threshold_method": PRIMARY_THRESHOLD, "threshold_value": baseline_thresholds[PRIMARY_THRESHOLD], **primary_baseline}, "sensitivity": baseline_all}
            ewma_doc = {"attack": attack, "primary": {"alpha": PRIMARY_ALPHA, "initialization": "first_calibration_rmse", "threshold_method": PRIMARY_THRESHOLD, "threshold_value": ewma_thresholds[PRIMARY_ALPHA][PRIMARY_THRESHOLD], **primary_ewma}, "alpha_sensitivity": {str(alpha): ewma_all[alpha][PRIMARY_THRESHOLD] for alpha in ALPHAS}}
            atomic_json(attack_output / "audit.json", audit); atomic_json(attack_output / "thresholds.json", thresholds_doc)
            atomic_json(attack_output / "baseline_metrics.json", baseline_doc); atomic_json(attack_output / "ewma_metrics.json", ewma_doc)
            atomic_json(attack_output / "temporal_metrics.json", {"baseline": temporal_metrics(evaluation_scores >= baseline_thresholds[PRIMARY_THRESHOLD], evaluation_labels), "ewma": temporal_metrics(ewma_by_alpha[PRIMARY_ALPHA][CALIBRATION_ROWS:] >= ewma_thresholds[PRIMARY_ALPHA][PRIMARY_THRESHOLD], evaluation_labels)})
            plot_attack(attack_output / "plots" / "timeseries.png", attack, evaluation_scores, ewma_by_alpha[PRIMARY_ALPHA][CALIBRATION_ROWS:], evaluation_labels, ewma_thresholds[PRIMARY_ALPHA][PRIMARY_THRESHOLD], float(evaluation_labels.mean()))
            for method, metric in baseline_all.items(): threshold_rows.append({"attack": attack, "series": "baseline", "alpha": None, "threshold_method": method, "threshold_value": baseline_thresholds[method], **metric})
            for alpha in ALPHAS:
                for method, metric in ewma_all[alpha].items(): threshold_rows.append({"attack": attack, "series": "ewma", "alpha": alpha, "threshold_method": method, "threshold_value": ewma_thresholds[alpha][method], **metric})
            summaries.append({"attack": attack, "calibration_attack_count": calibration_attack_count, "calibration_contamination_rate": calibration_attack_count / CALIBRATION_ROWS, "evaluation_rows": int(evaluation_labels.size), "attack_prevalence": float(evaluation_labels.mean()), "classification": classification(primary_baseline, primary_ewma), "baseline_primary": primary_baseline, "ewma_primary": primary_ewma})
            atomic_json(status_path, {"status": "completed", "attack": attack, "updated": datetime.now(timezone.utc).isoformat(), "message": "pre-registered EWMA evaluation completed"})
        except Exception as error:
            atomic_json(status_path, {"status": "failed", "attack": attack, "updated": datetime.now(timezone.utc).isoformat(), "message": str(error), "recovery_command": ".\\.venv\\Scripts\\python.exe scripts\\run_ewma_evaluation.py --no-overwrite"})
            raise
    write_csv(output / "summary.csv", [{"attack": row["attack"], "calibration_attack_count": row["calibration_attack_count"], "calibration_contamination_rate": row["calibration_contamination_rate"], "evaluation_rows": row["evaluation_rows"], "attack_prevalence": row["attack_prevalence"], "classification": row["classification"], **{f"baseline_{key}": value for key, value in row["baseline_primary"].items()}, **{f"ewma_{key}": value for key, value in row["ewma_primary"].items()}} for row in summaries])
    write_csv(output / "threshold_comparison.csv", threshold_rows); write_csv(output / "alpha_comparison.csv", alpha_rows)
    atomic_json(output / "summary.json", {"protocol": protocol, "datasets": summaries, "oracle_exploratory_upper_bound": "not computed; no per-dataset test-label selection was performed"})
    global_plots(output / "plots", summaries, alpha_rows, threshold_rows)
    protocol["status"] = "completed"; atomic_json(output / "protocol.json", protocol)
    print(json.dumps({"datasets": len(summaries), "status": "completed"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
