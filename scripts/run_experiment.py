"""
Overnight exploratory experiment runner for Kitsune reproduction.

Usage:
    python scripts/run_experiment.py --max-rows 1000 --output-dir results/overnight-20260712
    python scripts/run_experiment.py --max-rows 10000 --output-dir results/overnight-20260712
    python scripts/run_experiment.py --output-dir results/overnight-20260712 --no-overwrite
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

import numpy as np

# --- Constants ---------------------------------------------------------------
SOURCE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Kitsune", "Kitsune-py")
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RESULTS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

FMGRACE = 5000
ADGRACE = 50000
MAXAE = 10
LR = 0.1
HR = 0.75

EXP_ID = "overnight-20260712"

# --- Helpers -----------------------------------------------------------------

def _get_git_sha():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"

def _get_git_branch():
    try:
        r = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"

def load_manifest(experiment_dir, args):
    manifest = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _get_git_sha(),
        "git_branch": _get_git_branch(),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "args": vars(args),
    }
    os.makedirs(experiment_dir, exist_ok=True)
    with open(os.path.join(experiment_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

def load_config(experiment_dir, attack, n_features):
    config = {
        "attack": attack,
        "FMgrace": FMGRACE,
        "ADgrace": ADGRACE,
        "maxAE": MAXAE,
        "learning_rate": LR,
        "hidden_ratio": HR,
        "n_features": n_features,
    }
    with open(os.path.join(experiment_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

def save_status(experiment_dir, status, message=""):
    status_file = os.path.join(experiment_dir, "status.json")
    data = {"status": status, "message": message, "updated": datetime.now(timezone.utc).isoformat()}
    with open(status_file, "w") as f:
        json.dump(data, f, indent=2)

def save_metrics(experiment_dir, metrics):
    with open(os.path.join(experiment_dir, "provisional_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

def save_rmse(experiment_dir, rmse_values, execution_labels=None, all_labels=None):
    raw_dir = os.path.join(experiment_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    np.savetxt(os.path.join(raw_dir, "rmse.csv"), rmse_values, delimiter=",", header="rmse", comments="")
    if execution_labels is not None and len(execution_labels) == len(rmse_values):
        combined = np.column_stack((rmse_values, execution_labels))
        np.savetxt(os.path.join(raw_dir, "rmse_with_labels.csv"), combined, delimiter=",", header="rmse,label", comments="")
    if all_labels is not None:
        full_rmse = np.zeros(len(all_labels))
        grace_end = FMGRACE + ADGRACE + 1
        exec_len = min(len(rmse_values), len(all_labels) - grace_end)
        full_rmse[grace_end:grace_end + exec_len] = rmse_values[:exec_len]
        full = np.column_stack((full_rmse, all_labels))
        np.savetxt(os.path.join(raw_dir, "full_rmse_with_labels.csv"), full, delimiter=",", header="rmse,label", comments="")

def scan_uci_data(data_dir):
    attacks_info = {}
    base = os.path.join(data_dir, "kitsune")
    if not os.path.isdir(base):
        return attacks_info
    for attack_dir in sorted(os.listdir(base)):
        attack_path = os.path.join(base, attack_dir)
        if not os.path.isdir(attack_path):
            continue
        feature_file = None
        label_file = None
        for fname in os.listdir(attack_path):
            fpath = os.path.join(attack_path, fname)
            if "dataset" in fname.lower() and fname.endswith(".csv"):
                feature_file = fpath
            elif "label" in fname.lower() and fname.endswith(".csv"):
                label_file = fpath
        if feature_file is None:
            for fname in os.listdir(attack_path):
                fpath = os.path.join(attack_path, fname)
                if fname.endswith(".csv") and fname != os.path.basename(label_file or ""):
                    feature_file = fpath
        attacks_info[attack_dir] = {"path": attack_path, "feature_file": feature_file, "label_file": label_file}
    return attacks_info

# --- Data Pre-checks ---------------------------------------------------------

def _load_csv(path, max_rows=None):
    """Load CSV with automatic header detection. Returns (data, had_header)."""
    with open(path, "r") as f:
        first_line = f.readline().strip()
    # Check if first line looks like a numeric row
    tokens = first_line.split(",")
    has_header = False
    for t in tokens[:5]:
        t = t.strip()
        if t and not t.replace(".", "").replace("-", "").replace("+", "").replace("e", "").replace("E", "").isdigit():
            has_header = True
            break
    skiprows = 1 if has_header else 0
    data = np.loadtxt(path, delimiter=",", skiprows=skiprows, max_rows=max_rows)
    return data, has_header

def _detect_index_col(features):
    """Detect if column 0 is a row index (0-start or 1-start). Returns the starting value or None."""
    if features.ndim < 2 or features.shape[0] < 5:
        return None
    col0 = features[:, 0]
    n = features.shape[0]
    if np.allclose(col0, np.arange(n)):
        return 0
    if np.allclose(col0, np.arange(1, n + 1)):
        return 1
    return None

def precheck_data(feature_file, label_file, max_rows=None):
    checks = {}
    # Load features
    print(f"  Loading features from: {feature_file}")
    try:
        features, had_header = _load_csv(feature_file, max_rows=max_rows)
        checks["feature_rows"] = features.shape[0]
        checks["feature_cols"] = features.shape[1] if features.ndim > 1 else 1
        checks["csv_has_header"] = had_header
    except Exception as e:
        return {"error": f"Failed to load features: {e}"}
    # Detect possible index column
    idx_start = _detect_index_col(features)
    if idx_start is not None:
        checks["index_col_detected"] = idx_start
        checks["index_col_basis"] = f"column 0 matches {idx_start}-started sequential integers"
        features = features[:, 1:]
        checks["feature_cols_after_index_removal"] = features.shape[1]
    else:
        checks["index_col_detected"] = None
        checks["index_col_basis"] = "column 0 does not match sequential integers"
    checks["actual_feature_dim"] = features.shape[1] if features.ndim > 1 else 1
    # NaN/Inf check
    nan_count = int(np.isnan(features).sum())
    inf_count = int(np.isinf(features).sum())
    checks["nan_count"] = nan_count
    checks["inf_count"] = inf_count
    if nan_count > 0:
        checks["nan_positions"] = np.argwhere(np.isnan(features)).tolist()[:5]
    if inf_count > 0:
        checks["inf_positions"] = np.argwhere(np.isinf(features)).tolist()[:5]
    # Load labels
    labels = _load_labels(label_file, max_rows, checks)
    # Row count consistency
    if "label_rows" in checks and checks.get("feature_rows") != checks.get("label_rows"):
        checks["row_mismatch"] = f"features={checks['feature_rows']} vs labels={checks['label_rows']}"
    # Training contamination check (first FMgrace+ADgrace=55001 rows)
    if labels is not None and len(labels) >= 55001:
        train_labels = labels[:55001]
        attack_in_train = int((train_labels > 0).sum())
        checks["attack_in_first_55001"] = attack_in_train
        checks["training_contamination"] = attack_in_train > 0
    elif labels is not None:
        checks["training_contamination"] = "insufficient rows"
    checks["feature_sample"] = features[:3, :3].tolist() if features.ndim > 1 else features[:3].tolist()
    return checks, labels

def _load_labels(label_file, max_rows, checks):
    if not label_file or not os.path.isfile(label_file):
        checks["label_file"] = "not found"
        return None
    try:
        raw, _ = _load_csv(label_file, max_rows=max_rows)
        checks["label_rows"] = len(raw)
        # Ensure 1D
        if raw.ndim == 2:
            if raw.shape[1] == 2:
                raw = raw[:, 1]
            elif raw.shape[1] == 1:
                raw = raw[:, 0]
        labels = np.asarray(raw, dtype=float).ravel()
        unique_labels = np.unique(labels)
        checks["unique_labels"] = unique_labels.tolist()
        checks["labels_01_only"] = set(unique_labels).issubset({0, 1})
        return labels
    except Exception as e:
        checks["label_error"] = str(e)
        return None

# --- KitNET Experiment --------------------------------------------------------

def run_kitnet_on_uci(feature_file, label_file, experiment_dir, max_rows=None):
    _patch_numpy()
    cwd = os.getcwd()
    sys.path.insert(0, SOURCE_ROOT)
    import KitNET.KitNET as KitNET
    os.chdir(SOURCE_ROOT)
    # Load data
    features, _ = _load_csv(feature_file, max_rows=max_rows)
    if _detect_index_col(features) is not None:
        features = features[:, 1:]
    n_features = features.shape[1]
    # Create KitNET directly (not via Kitsune wrapper since no PCAP)
    kitnet = KitNET.KitNET(n=n_features, max_autoencoder_size=MAXAE,
                           FM_grace_period=FMGRACE, AD_grace_period=ADGRACE,
                           learning_rate=LR, hidden_ratio=HR)
    rmse_list = []
    grace_count = 0
    start_time = time.time()
    for i in range(len(features)):
        x = features[i]
        rmse = kitnet.process(x)
        if i < FMGRACE + ADGRACE + 1:
            grace_count += 1
        else:
            rmse_list.append(rmse)
        if (i + 1) % 10000 == 0:
            elapsed = time.time() - start_time
            print(f"    Processed {i+1}/{len(features)} rows, elapsed: {elapsed:.1f}s")
    total_time = time.time() - start_time
    rmse_arr = np.array(rmse_list)
    # Load labels and align with execution phase
    labels = None
    if label_file and os.path.isfile(label_file):
        raw_labels, _ = _load_csv(label_file, max_rows=max_rows)
        # Ensure 1D
        if raw_labels.ndim == 2:
            if raw_labels.shape[1] == 2:
                raw_labels = raw_labels[:, 1]
            elif raw_labels.shape[1] == 1:
                raw_labels = raw_labels[:, 0]
        label_data = np.asarray(raw_labels, dtype=float).ravel()
        if len(label_data) > FMGRACE + ADGRACE + 1:
            labels = label_data[FMGRACE + ADGRACE + 1:FMGRACE + ADGRACE + 1 + len(rmse_arr)]
    metrics = {
        "total_rows": len(features),
        "grace_rows": grace_count,
        "execution_rows": len(rmse_list),
        "total_time_seconds": total_time,
        "rows_per_second": len(features) / total_time if total_time > 0 else 0,
        "rmse_mean": float(np.mean(rmse_arr)) if len(rmse_arr) > 0 else None,
        "rmse_std": float(np.std(rmse_arr)) if len(rmse_arr) > 0 else None,
        "rmse_min": float(np.min(rmse_arr)) if len(rmse_arr) > 0 else None,
        "rmse_max": float(np.max(rmse_arr)) if len(rmse_arr) > 0 else None,
    }
    # Add percentiles
    if len(rmse_arr) > 0:
        sorted_r = np.sort(rmse_arr)
        n = len(sorted_r)
        metrics["rmse_median"] = float(sorted_r[n // 2])
        metrics["rmse_p95"] = float(sorted_r[int(n * 0.95)])
        metrics["rmse_p99"] = float(sorted_r[int(n * 0.99)])
        metrics["rmse_p99_5"] = float(sorted_r[int(n * 0.995)])
    if labels is not None and len(labels) > 0:
        benign_mask = labels == 0
        attack_mask = labels == 1
        benign_rmse = rmse_arr[benign_mask]
        attack_rmse = rmse_arr[attack_mask]
        metrics["benign_rmse_mean"] = float(np.mean(benign_rmse)) if len(benign_rmse) > 0 else None
        metrics["attack_rmse_mean"] = float(np.mean(attack_rmse)) if len(attack_rmse) > 0 else None
        metrics["benign_count"] = int(np.sum(benign_mask))
        metrics["attack_count"] = int(np.sum(attack_mask))
        metrics["n_labels"] = len(labels)
    os.chdir(cwd)
    return metrics, rmse_arr, labels


# --- Mirai PCAP Baseline ------------------------------------------------------
def _patch_numpy():
    """Compatibility shim: restore np.Inf for numpy >= 2.0 (Kitsune uses legacy API)."""
    import numpy as _np
    if not hasattr(_np, 'Inf'):
        _np.Inf = _np.inf

def run_mirai_pcap_baseline(experiment_dir, max_rows=None):
    _patch_numpy()
    cwd = os.getcwd()
    sys.path.insert(0, SOURCE_ROOT)
    from Kitsune import Kitsune
    os.chdir(SOURCE_ROOT)
    import zipfile
    zip_path = os.path.join(SOURCE_ROOT, "mirai.zip")
    if os.path.isfile(zip_path):
        print("  Extracting mirai.zip...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(SOURCE_ROOT)
    pcap_path = os.path.join(SOURCE_ROOT, "mirai.pcap")
    if not os.path.isfile(pcap_path):
        return {"error": "mirai.pcap not found"}, [], None
    limit = max_rows if max_rows else np.inf
    K = Kitsune(pcap_path, limit, MAXAE, FMGRACE, ADGRACE)
    print("  Running Kitsune on Mirai PCAP...")
    rmse_list = []
    start_time = time.time()
    i = 0
    while True:
        rmse = K.proc_next_packet()
        if rmse == -1:
            break
        rmse_list.append(rmse)
        i += 1
        if i % 5000 == 0:
            print(f"    Processed {i} packets, elapsed: {time.time()-start_time:.1f}s")
        if max_rows and i >= max_rows:
            break
    total_time = time.time() - start_time
    rmse_arr = np.array(rmse_list)
    metrics = {
        "total_packets": len(rmse_list),
        "total_time_seconds": total_time,
        "packets_per_second": len(rmse_list) / total_time if total_time > 0 else 0,
        "grace_rows": min(FMGRACE + ADGRACE + 1, len(rmse_list)),
        "execution_rows": max(0, len(rmse_list) - FMGRACE - ADGRACE - 1),
        "rmse_mean": float(np.mean(rmse_arr[FMGRACE + ADGRACE + 1:])) if len(rmse_arr) > FMGRACE + ADGRACE else None,
        "rmse_std": float(np.std(rmse_arr[FMGRACE + ADGRACE + 1:])) if len(rmse_arr) > FMGRACE + ADGRACE else None,
    }
    os.chdir(cwd)
    return metrics, rmse_arr, None

# --- Main ---------------------------------------------------------------------

# --- Synthetic Test -----------------------------------------------------------

def test_synthetic_uci():
    """Run a synthetic 115-dim 1000-row UCI test to verify the KitNET pipeline."""
    print("=" * 60)
    print("Synthetic UCI Test (115-dim, 1000 rows, 0/1 labels)")
    print("=" * 60)
    _patch_numpy()

    # Generate synthetic data
    n_rows = 1000
    n_dims = 115
    rng = np.random.RandomState(42)
    features = rng.randn(n_rows, n_dims).astype(np.float64)
    # Add sequential index as col 0
    idx = np.arange(n_rows).reshape(-1, 1).astype(np.float64)
    feat_with_idx = np.column_stack((idx, features))
    labels = np.zeros(n_rows, dtype=np.float64)
    labels[700:] = 1.0  # Attacks start at row 700 (after grace)
    labels_with_idx = np.column_stack((np.arange(n_rows).astype(np.float64), labels))

    # Write temp files
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="kitsune_test_")
    feat_path = os.path.join(tmpdir, "test_dataset.csv")
    lab_path = os.path.join(tmpdir, "test_labels.csv")
    np.savetxt(feat_path, feat_with_idx, delimiter=",", header="idx," + ",".join(f"f{i}" for i in range(n_dims)), comments="")
    np.savetxt(lab_path, labels_with_idx, delimiter=",", header="idx,label", comments="")

    try:
        # Test header detection
        data, had_header = _load_csv(feat_path)
        assert had_header, "Header detection failed"
        assert data.shape == (n_rows, n_dims + 1), f"Feature shape mismatch: {data.shape}"
        print(f"  Header detection: OK ({data.shape})")

        # Test index detection
        idx_start = _detect_index_col(data)
        assert idx_start == 0, f"Index detection failed: {idx_start}"
        print(f"  Index detection: OK (start={idx_start})")

        # Test with index removal
        features_clean = data[:, 1:]
        assert features_clean.shape == (n_rows, n_dims), f"Index removal failed: {features_clean.shape}"
        print(f"  Index removal: OK ({features_clean.shape})")

        # Test precheck
        checks, chk_labels = precheck_data(feat_path, lab_path)
        assert "error" not in checks, f"Precheck error: {checks.get('error')}"
        assert checks["actual_feature_dim"] == n_dims, f"Dim mismatch: {checks['actual_feature_dim']}"
        assert checks["nan_count"] == 0, f"Unexpected NaN"
        assert checks["inf_count"] == 0, f"Unexpected Inf"
        assert chk_labels is not None, "Labels not loaded"
        assert len(chk_labels) == n_rows, f"Label count mismatch"
        print(f"  Precheck: OK (dim={checks['actual_feature_dim']}, rows={checks['feature_rows']})")

        # Test run_kitnet_on_uci
        metrics, rmse_arr, exec_labels = run_kitnet_on_uci(feat_path, lab_path, tmpdir)
        assert metrics["total_rows"] == n_rows, f"Total rows mismatch"
        assert metrics["execution_rows"] == max(0, n_rows - FMGRACE - ADGRACE - 1), f"Exec rows mismatch"
        print(f"  KitNET run: OK (total={metrics['total_rows']}, exec={metrics['execution_rows']}, "
              f"time={metrics['total_time_seconds']:.3f}s)")

        # Verify grace period all zeros
        assert np.allclose(rmse_arr[:metrics['execution_rows']], 0, atol=1e-10), "Non-zero RMSE in grace"
        print(f"  Grace zeros: OK")

        # Verify no NaN/Inf in RMSE
        assert not np.any(np.isnan(rmse_arr)), "NaN in RMSE"
        assert not np.any(np.isinf(rmse_arr)), "Inf in RMSE"
        print(f"  RMSE NaN/Inf: OK")

        # Verify labels alignment
        if exec_labels is not None:
            assert len(exec_labels) == metrics["execution_rows"], f"Labels/rmse length mismatch"
            print(f"  Label alignment: OK ({len(exec_labels)} execution labels)")

        print(f"\nALL SYNTHETIC TESTS PASSED")
        print(f"Test directory: {tmpdir}")
        return True
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\nTEST ERROR: {e}")
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Kitsune Overnight Exploratory Experiment")
    parser.add_argument("--max-rows", type=int, default=None, help="Max rows/packets to process")
    parser.add_argument("--output-dir", default=os.path.join(RESULTS_ROOT, EXP_ID), help="Output directory")
    parser.add_argument("--no-overwrite", action="store_true", help="Skip if results exist")
    parser.add_argument("--attack", default=None, help="Run only specific attack (subdir name)")
    parser.add_argument("--test", action="store_true", help="Run synthetic test and exit")
    args = parser.parse_args()

    if args.test:
        ok = test_synthetic_uci()
        sys.exit(0 if ok else 1)
    experiment_dir = args.output_dir
    os.makedirs(experiment_dir, exist_ok=True)
    load_manifest(experiment_dir, args)
    save_status(experiment_dir, "running")
    print(f"Experiment output: {experiment_dir}")
    print(f"Max rows: {args.max_rows or 'unlimited'}")
    print(f"Source root: {SOURCE_ROOT}")
    print(f"Data root: {DATA_ROOT}")
    results_summary = {}
    all_ok = True
    total_rows = 0
    total_start = time.time()

    def _is_attack_done(attack_dir):
        sf = os.path.join(attack_dir, "status.json")
        if args.no_overwrite and os.path.isfile(sf):
            with open(sf) as f:
                st = json.load(f)
            if st.get("status") == "completed":
                print(f"    SKIPPED (already completed): {attack_dir}")
                return True
        return False

    # Phase 1: Track A - Mirai PCAP Baseline
    print("\n=== Phase 1: Mirai PCAP Baseline (Track A) ===")
    mirai_dir = os.path.join(experiment_dir, "mirai-baseline")
    os.makedirs(mirai_dir, exist_ok=True)
    if not _is_attack_done(mirai_dir):
        load_config(mirai_dir, "mirai-pcap", 100)
        try:
            metrics, rmse_arr, _ = run_mirai_pcap_baseline(mirai_dir, max_rows=args.max_rows)
            if "error" in metrics:
                print(f"  SKIPPED: {metrics['error']}")
                save_status(mirai_dir, "blocked", metrics["error"])
                results_summary["mirai-pcap"] = {"status": "blocked", "message": metrics["error"]}
            else:
                save_metrics(mirai_dir, metrics)
                save_rmse(mirai_dir, rmse_arr)
                save_status(mirai_dir, "completed")
                results_summary["mirai-pcap"] = {"status": "completed", "packets": metrics["total_packets"]}
                total_rows += metrics["total_packets"]
                print(f"  OK: {metrics['total_packets']} packets in {metrics['total_time_seconds']:.1f}s")
        except Exception as e:
            print(f"  ERROR: {e}")
            traceback.print_exc()
            save_status(mirai_dir, "failed", str(e))
            results_summary["mirai-pcap"] = {"status": "failed", "message": str(e)}
            all_ok = False
    else:
        results_summary["mirai-pcap"] = {"status": "completed", "note": "skipped (already done)"}

    # Phase 2: Scan for UCI data
    print("\n=== Phase 2: UCI Dataset Scan (Track B) ===")
    attacks = scan_uci_data(DATA_ROOT)
    if not attacks:
        print("  No UCI data found under data/kitsune/")
        print("  Creating framework structure for future runs...")
        blocked_dir = os.path.join(experiment_dir, "uci-blocked")
        os.makedirs(blocked_dir, exist_ok=True)
        save_status(blocked_dir, "blocked", "UCI data not available at data/kitsune/. Download and place before re-run.")
        results_summary["uci"] = {"status": "blocked", "message": "UCI data not found"}
    else:
        print(f"  Found {len(attacks)} attack directories")
        for attack_name, info in sorted(attacks.items()):
            if args.attack and attack_name != args.attack:
                continue
            print(f"\n  --- {attack_name} ---")
            attack_dir = os.path.join(experiment_dir, attack_name)
            os.makedirs(attack_dir, exist_ok=True)
            if _is_attack_done(attack_dir):
                results_summary[attack_name] = {"status": "completed", "note": "skipped (already done)"}
                continue
            feature_file = info.get("feature_file")
            label_file = info.get("label_file")
            if not feature_file or not os.path.isfile(feature_file):
                print(f"    SKIPPED: feature file not found")
                save_status(attack_dir, "blocked", "feature file not found")
                results_summary[attack_name] = {"status": "blocked", "message": "feature file not found"}
                continue
            # Pre-checks
            print(f"    Pre-checking data...")
            checks, precheck_labels = precheck_data(feature_file, label_file, max_rows=args.max_rows)
            if "error" in checks:
                print(f"    PRE-CHECK FAILED: {checks['error']}")
                save_status(attack_dir, "failed", checks["error"])
                results_summary[attack_name] = {"status": "failed", "message": checks["error"]}
                all_ok = False
                continue
            # Block on NaN/Inf
            if checks.get("nan_count", 0) > 0 or checks.get("inf_count", 0) > 0:
                msg = f"NaN={checks['nan_count']}, Inf={checks['inf_count']} in features"
                print(f"    BLOCKED: {msg}")
                save_status(attack_dir, "blocked", msg)
                results_summary[attack_name] = {"status": "blocked", "message": msg}
                continue
            # Block on row mismatch
            if checks.get("row_mismatch"):
                print(f"    BLOCKED: row mismatch - {checks['row_mismatch']}")
                save_status(attack_dir, "blocked", checks["row_mismatch"])
                results_summary[attack_name] = {"status": "blocked", "message": checks["row_mismatch"]}
                continue
            # Block on training contamination
            if checks.get("training_contamination"):
                n_attack = checks.get("attack_in_first_55001", 0)
                print(f"    BLOCKED: {n_attack} attack samples in first 55001 train rows")
                save_status(attack_dir, "blocked", f"{n_attack} attack samples in first 55001 rows")
                results_summary[attack_name] = {"status": "blocked", "message": "training contamination"}
                continue
            # Save checks
            with open(os.path.join(attack_dir, "precheck.json"), "w") as f:
                json.dump(checks, f, indent=2)
            print(f"    Feature dim: {checks.get('actual_feature_dim')}, rows: {checks.get('feature_rows')}")
            # Run KitNET
            print(f"    Running KitNET...")
            load_config(attack_dir, attack_name, checks.get("actual_feature_dim", 0))
            try:
                metrics, rmse_arr, exec_labels = run_kitnet_on_uci(
                    feature_file, label_file, attack_dir, max_rows=args.max_rows
                )
                save_metrics(attack_dir, metrics)
                save_rmse(attack_dir, rmse_arr, execution_labels=exec_labels, all_labels=precheck_labels)
                save_status(attack_dir, "completed")
                results_summary[attack_name] = {"status": "completed", "rows": metrics.get("total_rows")}
                total_rows += metrics.get("total_rows", 0)
                print(f"    OK: {metrics.get('total_rows', 0)} rows in {metrics.get('total_time_seconds', 0):.1f}s")
            except Exception as e:
                print(f"    ERROR: {e}")
                traceback.print_exc()
                save_status(attack_dir, "failed", str(e))
                results_summary[attack_name] = {"status": "failed", "message": str(e)}
                all_ok = False
    # Summary
    total_elapsed = time.time() - total_start
    completed = sum(1 for v in results_summary.values() if v.get("status") == "completed")
    failed = sum(1 for v in results_summary.values() if v.get("status") == "failed")
    blocked = sum(1 for v in results_summary.values() if v.get("status") == "blocked")
    print("\n" + "=" * 50)
    print(f"OVERNIGHT EXPERIMENT COMPLETE")
    print(f"  Total time: {total_elapsed:.1f}s")
    print(f"  Completed: {completed}")
    print(f"  Failed: {failed}")
    print(f"  Blocked: {blocked}")
    print(f"  Total rows/packets: {total_rows}")
    print(f"  Output: {experiment_dir}")
    print("=" * 50)
    summary = {
        "total_time_seconds": total_elapsed,
        "completed": completed,
        "failed": failed,
        "blocked": blocked,
        "total_rows": total_rows,
        "results": results_summary,
    }
    with open(os.path.join(experiment_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    save_status(experiment_dir, "completed" if all_ok else "partial", f"completed={completed}, failed={failed}, blocked={blocked}")
    print(f"\nSummary saved to {os.path.join(experiment_dir, 'summary.json')}")
    print(f"Status: {'ALL OK' if all_ok else 'PARTIAL (see summary)'}")

if __name__ == "__main__":
    main()
