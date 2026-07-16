#!/usr/bin/env python3
"""Create a reproducible local audit for the nine completed UCI baselines.

This script reads existing result artifacts only.  It never alters experiment
outputs, source data, or the official Kitsune implementation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata


GRACE_ROWS = 55_001
ATTACKS = [
    "mirai", "os_scan", "fuzzing", "ssl_renegotiation", "arp_mitm",
    "syn_dos", "active_wiretap", "ssdp_flood", "video_injection",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def result_dir(root: Path, attack: str) -> Path:
    return root / "mirai" if attack == "mirai" else root / "uci" / attack / "full"


def read_scores_labels(directory: Path, attack: str) -> tuple[np.ndarray, np.ndarray]:
    labeled = directory / "raw" / "rmse_with_labels.csv"
    if not labeled.exists():
        raise FileNotFoundError(f"missing labelled RMSE file: {labeled}")
    scores, labels = [], []
    with labeled.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or len(header) < 2:
            raise ValueError(f"invalid labelled RMSE header for {attack}")
        for number, row in enumerate(reader, start=2):
            if len(row) < 2:
                raise ValueError(f"short labelled RMSE row {number} for {attack}")
            scores.append(float(row[0]))
            labels.append(int(float(row[1].strip().strip('"'))))
    score_array = np.asarray(scores, dtype=np.float64)
    label_array = np.asarray(labels, dtype=np.int8)
    if score_array.size != label_array.size:
        raise ValueError(f"score/label count mismatch for {attack}")
    if not np.isin(label_array, [0, 1]).all():
        raise ValueError(f"non-binary labels in execution RMSE for {attack}")
    plain = directory / "raw" / "rmse.csv"
    if plain.exists():
        plain_scores = np.loadtxt(plain, delimiter=",", skiprows=1, dtype=np.float64)
        plain_scores = np.atleast_1d(plain_scores)
        if plain_scores.size != score_array.size or not np.array_equal(plain_scores, score_array):
            raise ValueError(f"rmse.csv is not exactly aligned with rmse_with_labels.csv for {attack}")
    return score_array, label_array


def aucs(scores: np.ndarray, labels: np.ndarray) -> tuple[float | None, float | None, str | None]:
    positives = int(labels.sum())
    negatives = int(labels.size - positives)
    if not positives or not negatives:
        return None, None, "execution labels contain only one class"
    ranks = rankdata(scores, method="average")
    roc = float((ranks[labels == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))
    order = np.argsort(scores, kind="mergesort")[::-1]
    sorted_labels = labels[order]
    positives_seen = np.cumsum(sorted_labels)
    positions = np.arange(1, labels.size + 1)
    precision = positives_seen / positions
    pr = float(precision[sorted_labels == 1].sum() / positives)
    return roc, pr, None


def stat(values: np.ndarray) -> dict:
    if not values.size:
        return {"count": 0, "min": None, "median": None, "mean": None, "std": None,
                "p95": None, "p99": None, "p99_5": None, "p99_9": None, "max": None}
    return {
        "count": int(values.size), "min": float(np.min(values)), "median": float(np.median(values)),
        "mean": float(np.mean(values)), "std": float(np.std(values)),
        "p95": float(np.percentile(values, 95)), "p99": float(np.percentile(values, 99)),
        "p99_5": float(np.percentile(values, 99.5)), "p99_9": float(np.percentile(values, 99.9)),
        "max": float(np.max(values)),
    }


def sampled(values: np.ndarray, limit: int = 5000) -> np.ndarray:
    if values.size <= limit:
        return values
    return values[np.linspace(0, values.size - 1, limit, dtype=int)]


def archive_entry(root: Path, directory: Path, attack: str) -> dict:
    files = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    if attack == "mirai":
        rerun = "<PROJECT_ROOT>/.venv/Scripts/python.exe scripts/run_experiment.py --attack mirai --output-dir results/overnight-20260712 --no-overwrite"
        recoverable = all((directory / p).exists() for p in ["config.json", "precheck.json", "status.json", "raw/rmse.csv", "raw/rmse_with_labels.csv"])
        condition = "legacy-compatible: result, configuration and precheck artifacts are present"
    else:
        rerun = f"<PROJECT_ROOT>/.venv/Scripts/python.exe scripts/run_uci_experiment.py --attack {attack} --phase full --output-dir results/overnight-20260712 --no-overwrite"
        required = ["manifest.json", "config.json", "precheck.json", "status.json", "metrics.json", "source_hashes.json", "raw/rmse.csv", "raw/rmse_with_labels.csv", "raw/sanitized_run_log.txt"]
        recoverable = all((directory / p).exists() for p in required)
        condition = "complete" if recoverable else "missing required recovery artifacts"
    return {"dataset": attack, "result_directory": directory.relative_to(root).as_posix(), "files": files,
            "total_size_bytes": sum(item["size_bytes"] for item in files), "rerun_command": rerun,
            "recovery_complete": recoverable, "recovery_condition": condition}


def make_plots(plot_dir: Path, rows: list[dict], arrays: dict[str, tuple[np.ndarray, np.ndarray]]) -> None:
    plot_dir.mkdir(parents=True, exist_ok=True)
    names = [row["dataset"] for row in rows]
    labels = [name.replace("_", " ") for name in names]
    plt.style.use("seaborn-v0_8-whitegrid")
    for key, title, filename in [("roc_auc", "ROC-AUC", "roc_auc_comparison.png"), ("pr_auc", "PR-AUC (average precision)", "pr_auc_comparison.png")]:
        values = [row[key] if row[key] is not None else np.nan for row in rows]
        fig, ax = plt.subplots(figsize=(12, 5))
        bars = ax.bar(labels, values, color="#2f6f9f")
        ax.set_ylim(0, 1.05); ax.set_ylabel(key); ax.set_title(f"Nine UCI baselines: {title} (execution after {GRACE_ROWS:,}-row grace)")
        ax.tick_params(axis="x", rotation=35)
        for bar, value in zip(bars, values):
            if np.isfinite(value): ax.text(bar.get_x() + bar.get_width()/2, value + .02, f"{value:.3f}", ha="center", fontsize=8)
        fig.tight_layout(); fig.savefig(plot_dir / filename, dpi=170); plt.close(fig)
    fig, axes = plt.subplots(3, 3, figsize=(16, 12)); axes = axes.ravel()
    for ax, row in zip(axes, rows):
        scores, _ = arrays[row["dataset"]]
        ax.plot(np.linspace(0, scores.size - 1, min(scores.size, 5000)), np.log1p(sampled(scores)), linewidth=.45, color="#236192")
        ax.set_title(f"{row['dataset']} | n={scores.size:,} | grace={GRACE_ROWS:,}", fontsize=9)
        ax.set_xlabel("execution row"); ax.set_ylabel("log(1+RMSE)")
    fig.suptitle("RMSE execution time series (each panel downsampled only for plotting)", y=1.01)
    fig.tight_layout(); fig.savefig(plot_dir / "rmse_timeseries_panels.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    dist = [np.log1p(sampled(arrays[name][0], 15000)) for name in names]
    fig, ax = plt.subplots(figsize=(14, 6)); ax.boxplot(dist, tick_labels=labels, showfliers=False)
    ax.set_title(f"RMSE distribution comparison (log1p; execution after {GRACE_ROWS:,}-row grace)"); ax.set_ylabel("log(1+RMSE)"); ax.tick_params(axis="x", rotation=35)
    fig.tight_layout(); fig.savefig(plot_dir / "rmse_distribution_comparison.png", dpi=170); plt.close(fig)
    fig, axes = plt.subplots(3, 3, figsize=(16, 12)); axes = axes.ravel()
    for ax, row in zip(axes, rows):
        scores, ys = arrays[row["dataset"]]
        values = [np.log1p(sampled(scores[ys == 0], 8000)), np.log1p(sampled(scores[ys == 1], 8000))]
        ax.boxplot(values, tick_labels=["benign", "attack"], showfliers=False)
        ax.set_title(f"{row['dataset']} | n={scores.size:,}", fontsize=9); ax.set_ylabel("log(1+RMSE)")
    fig.suptitle("Benign versus attack RMSE distributions (execution only)", y=1.01)
    fig.tight_layout(); fig.savefig(plot_dir / "benign_attack_boxplots.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    ratios = [row["extreme_audit"]["max_to_median_ratio"] for row in rows]
    fig, ax = plt.subplots(figsize=(12, 5)); ax.bar(labels, ratios, color="#a54a35")
    ax.set_yscale("log"); ax.set_ylabel("max / median RMSE (log scale)"); ax.set_title("Extreme RMSE audit: magnitude relative to dataset median")
    ax.tick_params(axis="x", rotation=35); fig.tight_layout(); fig.savefig(plot_dir / "extreme_rmse_audit.png", dpi=170); plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("results/overnight-20260712"))
    args = parser.parse_args()
    root = args.results_root.resolve()
    rows, arrays, archive = [], {}, []
    for attack in ATTACKS:
        directory = result_dir(root, attack)
        if not directory.exists():
            raise FileNotFoundError(f"missing full result directory: {directory}")
        scores, labels = read_scores_labels(directory, attack)
        if not np.isfinite(scores).all():
            raise ValueError(f"non-finite RMSE values in {attack}")
        overall = stat(scores); benign = stat(scores[labels == 0]); attack_stat = stat(scores[labels == 1])
        roc, pr, reason = aucs(scores, labels)
        top = np.argsort(scores)[-10:][::-1]
        median = overall["median"]
        ratio = float(overall["max"] / median) if median and median > 0 else math.inf
        original_row = [int(GRACE_ROWS + index) for index in top]
        cause = ("extreme relative magnitude; score/label alignment is verified, but input scale and normalization boundary should be inspected before causal attribution"
                 if ratio > 100 else "finite extreme values with verified score/label alignment; could reflect true attack transitions or model/input dynamics and are retained")
        row = {
            "dataset": attack, "total_rows": int(scores.size + GRACE_ROWS), "grace_rows": GRACE_ROWS,
            "execution_rows": int(scores.size), "score_direction": "higher_is_more_anomalous",
            "label_count": int(labels.size), "benign_count": int((labels == 0).sum()), "attack_count": int(labels.sum()),
            "attack_prevalence": float(labels.mean()), "finite": True, "roc_auc": roc, "pr_auc": pr,
            "metric_unavailable_reason": reason, "rmse_statistics": overall,
            "benign_rmse_statistics": benign, "attack_rmse_statistics": attack_stat,
            "extreme_audit": {"max_execution_row_index": int(top[0]), "max_original_row_index": original_row[0],
                "max_label": int(labels[top[0]]), "top_10": [{"execution_row_index": int(i), "original_row_index": int(GRACE_ROWS + i), "rmse": float(scores[i]), "label": int(labels[i])} for i in top],
                "max_to_median_ratio": ratio, "interpretation": cause},
        }
        rows.append(row); arrays[attack] = (scores, labels); archive.append(archive_entry(root, directory, attack))
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    summary = {"schema_version": 1, "generated_at": generated, "scope": "nine completed UCI baseline full results", "threshold_metrics_omitted": ["accuracy", "precision", "recall", "f1"], "datasets": rows}
    (root / "uci_baseline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["dataset", "total_rows", "grace_rows", "execution_rows", "label_count", "benign_count", "attack_count", "attack_prevalence", "score_direction", "finite", "roc_auc", "pr_auc"]
    with (root / "uci_baseline_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in rows: writer.writerow({field: row.get(field) for field in fields})
    archive_doc = {"schema_version": 1, "generated_at": generated, "entries": archive, "total_size_bytes": sum(entry["total_size_bytes"] for entry in archive)}
    (root / "uci_full_archive_manifest.json").write_text(json.dumps(archive_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_plots(root / "baseline_audit_plots", rows, arrays)
    print(json.dumps({"datasets": len(rows), "total_execution_rows": sum(row["execution_rows"] for row in rows), "archive_bytes": archive_doc["total_size_bytes"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
