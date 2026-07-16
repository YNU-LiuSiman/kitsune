"""Isolated, auditable UCI Kitsune runner.

Each invocation runs exactly one dataset and one phase (smoke-1000,
smoke-10000, or full) so its status and artifacts cannot collide.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path

import numpy as np

FMGRACE, ADGRACE, MAXAE, LR, HR = 5000, 50000, 10, 0.1, 0.75
GRACE_ROWS = FMGRACE + ADGRACE + 1
ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Kitsune" / "Kitsune-py"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def git_value(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True,
                              check=True, timeout=10).stdout.strip()
    except Exception:
        return "unknown"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def open_text(path):
    return gzip.open(path, "rt", newline="") if str(path).endswith(".gz") else open(path, "r", newline="")


def numeric_row(row):
    try:
        return [float(str(x).strip().strip('"')) for x in row]
    except ValueError:
        return None


def csv_info(path):
    with open_text(path) as f:
        reader = csv.reader(f)
        first = next(reader, [])
    return numeric_row(first) is None


def rows(path, limit=None):
    header = csv_info(path)
    with open_text(path) as f:
        reader = csv.reader(f)
        if header:
            next(reader, None)
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            values = numeric_row(row)
            if values is None:
                raise ValueError(f"non-numeric CSV row at {i + int(header) + 1}")
            yield values


def label_values(path, limit=None):
    for row in rows(path, limit):
        if len(row) == 1:
            yield row[0]
        elif len(row) == 2:
            yield row[1]
        else:
            raise ValueError("labels must contain one value or index,value")


def index_start(feature_path):
    sample = []
    for r in rows(feature_path, 32):
        if not r:
            raise ValueError("empty feature row")
        sample.append(r[0])
    # UCI's indexed representation is 116 columns (index + 115 features).
    # Never remove a sequential first *feature* from an already 115-dimensional file.
    first = next(rows(feature_path, 1), [])
    if len(first) != 116 or len(sample) < 5:
        return None
    if np.allclose(sample, np.arange(len(sample))):
        return 0
    if np.allclose(sample, np.arange(1, len(sample) + 1)):
        return 1
    return None


def precheck(feature_path, label_path):
    started = time.time()
    idx = index_start(feature_path)
    feature_header, label_header = csv_info(feature_path), csv_info(label_path)
    feature_rows = label_rows = nan_count = inf_count = attacks_train = benign = attacks = 0
    dim = None
    for n, pair in enumerate(zip_longest(rows(feature_path), label_values(label_path), fillvalue=None)):
        feature, label = pair
        if feature is None or label is None:
            raise ValueError("feature and label row counts differ")
        if idx is not None:
            feature = feature[1:]
        if dim is None:
            dim = len(feature)
        if len(feature) != dim:
            raise ValueError("feature column count differs between rows")
        arr = np.asarray(feature, dtype=float)
        nan_count += int(np.isnan(arr).sum())
        inf_count += int(np.isinf(arr).sum())
        if label not in (0.0, 1.0):
            raise ValueError(f"unexpected label value: {label}")
        feature_rows += 1; label_rows += 1
        benign += int(label == 0.0); attacks += int(label == 1.0)
        if n < GRACE_ROWS:
            attacks_train += int(label == 1.0)
    if dim is None:
        raise ValueError("empty feature file")
    return {
        "feature_file": "<DATASET_FEATURE>", "label_file": "<DATASET_LABEL>",
        "csv_has_header": feature_header, "label_has_header": label_header,
        "feature_rows": feature_rows, "label_rows": label_rows, "feature_cols": dim + int(idx is not None),
        "index_col_detected": idx, "actual_feature_dim": dim,
        "label_structure": "index+label" if next(label_values(label_path, 1), None) is not None and len(next(rows(label_path, 1))) == 2 else "label",
        "unique_labels": [0.0, 1.0], "benign_count": benign, "attack_count": attacks,
        "nan_count": nan_count, "inf_count": inf_count, "attack_in_first_55001": attacks_train,
        "feature_size_bytes": Path(feature_path).stat().st_size, "label_size_bytes": Path(label_path).stat().st_size,
        "feature_sha256": sha256(feature_path), "label_sha256": sha256(label_path),
        "precheck_seconds": time.time() - started,
    }


def aucs(scores, labels):
    if not scores or len(set(labels)) != 2:
        return None, None, "execution labels do not contain both classes"
    order = np.argsort(scores)[::-1]; y = np.asarray(labels)[order]
    pos, neg = int(y.sum()), len(y) - int(y.sum())
    tpr = np.cumsum(y) / pos; fpr = np.cumsum(1 - y) / neg
    roc = float(np.trapezoid(np.r_[0, tpr], np.r_[0, fpr]))
    precision = np.cumsum(y) / np.arange(1, len(y) + 1); recall = np.cumsum(y) / pos
    pr = float(np.sum((np.r_[0, recall][1:] - np.r_[0, recall][:-1]) * precision))
    return roc, pr, None


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def run(args):
    phase = "full" if args.phase == "full" else args.phase
    out = Path(args.output_dir) / "uci" / args.attack / phase
    if out.joinpath("status.json").is_file() and args.no_overwrite:
        status = json.loads(out.joinpath("status.json").read_text(encoding="utf-8"))
        if status.get("status") in ("smoke_passed", "completed"):
            print(f"SKIPPED existing successful run: {out}"); return
    out.joinpath("raw").mkdir(parents=True, exist_ok=True)
    log = out / "raw" / "sanitized_run_log.txt"
    try:
        checks = precheck(args.feature, args.labels)
        if checks["actual_feature_dim"] != 115:
            raise ValueError(f"unsupported feature dimension: {checks['actual_feature_dim']} (expected 115)")
        if checks["nan_count"] or checks["inf_count"] or checks["attack_in_first_55001"]:
            raise ValueError("precheck blocked: NaN/Inf or attack contamination")
        write_json(out / "precheck.json", checks)
        write_json(out / "source_hashes.json", {"feature_sha256": checks["feature_sha256"], "label_sha256": checks["label_sha256"]})
        write_json(out / "manifest.json", {"timestamp": utc_now(), "git_commit": git_value("rev-parse", "--short", "HEAD"), "git_branch": git_value("branch", "--show-current"), "phase": phase})
        write_json(out / "config.json", {"attack": args.attack, "FMgrace": FMGRACE, "ADgrace": ADGRACE, "grace_rows": GRACE_ROWS, "maxAE": MAXAE, "learning_rate": LR, "hidden_ratio": HR, "n_features": checks["actual_feature_dim"]})
        if os.environ.get("KITSUNE_SYNTHETIC_TEST") == "1":
            class SyntheticModel:
                def process(self, value): return float(np.mean(np.asarray(value, dtype=float)))
            model = SyntheticModel()
        else:
            if not hasattr(np, "Inf"):
                np.Inf = np.inf  # Kitsune's legacy implementation expects this alias.
            sys.path.insert(0, str(SOURCE_ROOT)); import KitNET.KitNET as kitnet_module
            model = kitnet_module.KitNET(n=checks["actual_feature_dim"], max_autoencoder_size=MAXAE, FM_grace_period=FMGRACE, AD_grace_period=ADGRACE, learning_rate=LR, hidden_ratio=HR)
        limit = {"smoke-1000": 1000, "smoke-10000": 10000, "full": None}[phase]
        scores = []; execution_labels = []; started = time.time(); idx = checks["index_col_detected"]
        for i, (feature, label) in enumerate(zip(rows(args.feature, limit), label_values(args.labels, limit))):
            score = model.process(np.asarray(feature[1:] if idx is not None else feature, dtype=float))
            if i >= GRACE_ROWS: scores.append(float(score)); execution_labels.append(float(label))
        elapsed = time.time() - started
        with open(out / "raw" / "rmse.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["rmse"]); w.writerows([[x] for x in scores])
        with open(out / "raw" / "rmse_with_labels.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["rmse", "label"]); w.writerows(zip(scores, execution_labels))
        roc, pr, reason = aucs(scores, execution_labels)
        metric = {"total_rows": i + 1, "grace_rows": min(i + 1, GRACE_ROWS), "execution_rows": len(scores), "runtime_seconds": elapsed, "throughput_rows_per_second": (i + 1) / elapsed if elapsed else None, "score_direction": "higher_is_more_anomalous", "roc_auc": roc, "pr_auc": pr, "not_applicable_reason": reason, "attack_prevalence": (sum(execution_labels) / len(execution_labels)) if execution_labels else None, "rmse_nan_count": int(np.isnan(scores).sum()), "rmse_inf_count": int(np.isinf(scores).sum())}
        if scores:
            metric.update({"rmse_min": min(scores), "rmse_median": float(np.median(scores)), "rmse_mean": float(np.mean(scores)), "rmse_std": float(np.std(scores)), "rmse_p95": float(np.percentile(scores, 95)), "rmse_p99": float(np.percentile(scores, 99)), "rmse_p99_5": float(np.percentile(scores, 99.5)), "rmse_max": max(scores), "benign_count": execution_labels.count(0.0), "attack_count": execution_labels.count(1.0)})
        write_json(out / "metrics.json", metric); write_json(out / "status.json", {"status": "completed" if phase == "full" else "smoke_passed", "message": "run completed", "attack": args.attack, "phase": phase, "updated": utc_now(), "resume_command": "<PROJECT_ROOT>/.venv/Scripts/python scripts/run_uci_experiment.py ..."})
        log.write_text(f"phase={phase}\nrows={i + 1}\n", encoding="utf-8")
    except Exception as exc:
        log.write_text(traceback.format_exc(), encoding="utf-8")
        write_json(out / "status.json", {"status": "failed", "message": str(exc), "attack": args.attack, "phase": phase, "updated": utc_now(), "resume_command": "<PROJECT_ROOT>/.venv/Scripts/python scripts/run_uci_experiment.py ..."})
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--attack", required=True); p.add_argument("--feature", required=True); p.add_argument("--labels", required=True); p.add_argument("--phase", choices=["smoke-1000", "smoke-10000", "full"], required=True); p.add_argument("--output-dir", default=str(ROOT / "results" / "overnight-20260712")); p.add_argument("--no-overwrite", action="store_true")
    run(p.parse_args())
