#!/usr/bin/env python3
"""Audit immutable UCI baseline scores before threshold/EWMA processing.

The script is deliberately read-only with respect to baseline result files. It
does not choose a threshold, use labels for parameter selection, or write any
processed score series.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

GRACE_ROWS = 55_001
ATTACKS = ["mirai", "os_scan", "fuzzing", "ssl_renegotiation", "arp_mitm", "syn_dos", "active_wiretap", "ssdp_flood", "video_injection"]


def directory(root: Path, attack: str) -> Path:
    return root / "mirai" if attack == "mirai" else root / "uci" / attack / "full"


def load_scores_labels(path: Path, attack: str) -> tuple[np.ndarray, np.ndarray]:
    scores, labels = [], []
    with (path / "raw" / "rmse_with_labels.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != ["rmse", "label"]:
            raise ValueError(f"{attack}: unexpected labelled RMSE header {header!r}")
        for row_number, row in enumerate(reader, start=2):
            if len(row) != 2:
                raise ValueError(f"{attack}: malformed row {row_number}")
            scores.append(float(row[0]))
            labels.append(int(float(row[1].strip().strip('"'))))
    return np.asarray(scores, dtype=np.float64), np.asarray(labels, dtype=np.int8)


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    positive = int(labels.sum())
    negative = int(labels.size - positive)
    if not positive or not negative:
        raise ValueError("ROC-AUC needs both label classes")
    ranks = rankdata(scores, method="average")
    return float((ranks[labels == 1].sum() - positive * (positive + 1) / 2) / (positive * negative))


def ranges(labels: np.ndarray) -> list[tuple[int, int]]:
    starts = np.flatnonzero((labels == 1) & np.r_[True, labels[:-1] != 1])
    ends = np.flatnonzero((labels == 1) & np.r_[labels[1:] != 1, True])
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def statistics(values: np.ndarray) -> dict:
    return {"count": int(values.size), "median": float(np.median(values)), "mean": float(np.mean(values))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("results/overnight-20260712"))
    args = parser.parse_args()
    root = args.results_root.resolve()
    out_root = root / "ewma"
    audits = []
    for attack in ATTACKS:
        result = directory(root, attack)
        scores, labels = load_scores_labels(result, attack)
        plain = np.loadtxt(result / "raw" / "rmse.csv", delimiter=",", skiprows=1, dtype=np.float64)
        plain = np.atleast_1d(plain)
        if plain.size != scores.size or not np.array_equal(plain, scores):
            raise ValueError(f"{attack}: plain and labelled RMSE are not exactly aligned")
        if not np.isfinite(scores).all() or labels.size != scores.size:
            raise ValueError(f"{attack}: non-finite score or score/label mismatch")
        if not np.isin(labels, [0, 1]).all():
            raise ValueError(f"{attack}: labels are not binary 0/1")
        intervals = ranges(labels)
        entry = {
            "attack": attack,
            "execution_start_row": GRACE_ROWS,
            "execution_rows": int(scores.size),
            "labels": {"meaning": {"0": "benign", "1": "attack"}, "count": int(labels.size), "benign_count": int((labels == 0).sum()), "attack_count": int(labels.sum())},
            "score_label_exact_alignment": True,
            "scores_finite": True,
            "benign_rmse": statistics(scores[labels == 0]),
            "attack_rmse": statistics(scores[labels == 1]),
            "attack_intervals": {"count": len(intervals), "first_execution_index": (intervals[0][0] if intervals else None), "first_original_row": (GRACE_ROWS + intervals[0][0] if intervals else None), "sample_first_10": [{"execution_start": start, "execution_end": end, "original_start": GRACE_ROWS + start, "original_end": GRACE_ROWS + end} for start, end in intervals[:10]]},
            "roc_auc_rmse": roc_auc(scores, labels),
            "roc_auc_negative_rmse": roc_auc(-scores, labels),
            "score_direction": "higher_is_more_anomalous",
            "training_rmse_available": False,
            "training_rmse_evidence": "raw/rmse.csv contains exactly execution_rows; no persisted score series covers rows 0..55000",
            "threshold_readiness": "blocked_no_label_free_calibration_scores",
        }
        attack_dir = out_root / attack
        attack_dir.mkdir(parents=True, exist_ok=True)
        (attack_dir / "audit.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        audits.append(entry)
    protocol = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "blocked",
        "reason": "No training-period RMSE was retained. The available RMSE files begin at execution row 55001, so q/mean/MAD thresholds cannot be calibrated from training scores without inventing a calibration rule or using test labels.",
        "prohibited_fallbacks": ["test labels", "test F1 selection", "per-dataset attack-aware alpha or threshold selection"],
        "required_user_decision": "Specify a protocol-authorized label-free calibration window, or authorize a fresh score-only baseline rerun that persists training-period RMSE without modifying official source or baseline outputs.",
        "datasets": audits,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"datasets": len(audits), "status": protocol["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
