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

def load_manifest(experiment_dir, args):
    manifest = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": os.popen("git rev-parse --short HEAD").read().strip() if os.path.isdir(".git") else "unknown",
        "git_branch": os.popen("git branch --show-current").read().strip() if os.path.isdir(".git") else "unknown",
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

def save_rmse(experiment_dir, rmse_values, labels=None):
    raw_dir = os.path.join(experiment_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    np.savetxt(os.path.join(raw_dir, "rmse.csv"), rmse_values, delimiter=",", header="rmse", comments="")
    if labels is not None:
        combined = np.column_stack((rmse_values[:len(labels)], labels[:len(rmse_values)]))
        header = "rmse,label"
        np.savetxt(os.path.join(raw_dir, "rmse_with_labels.csv"), combined, delimiter=",", header=header, comments="")

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

def precheck_data(feature_file, label_file, max_rows=None):
    checks = {}
    # Load features
    print(f"  Loading features from: {feature_file}")
    try:
        features = np.loadtxt(feature_file, delimiter=",", max_rows=max_rows)
        checks["feature_rows"] = features.shape[0]
        checks["feature_cols"] = features.shape[1] if features.ndim > 1 else 1
    except Exception as e:
        return {"error": f"Failed to load features: {e}"}
    # Detect possible index column
    if features.ndim == 2 and np.allclose(features[:, 0], np.arange(features.shape[0])):
        checks["index_col_detected"] = 0
        features = features[:, 1:]
        checks["feature_cols_after_index_removal"] = features.shape[1]
    else:
        checks["index_col_detected"] = None
    checks["actual_feature_dim"] = features.shape[1] if features.ndim > 1 else 1
    # NaN check
    nan_count = np.isnan(features).sum()
    inf_count = np.isinf(features).sum()
    checks["nan_count"] = int(nan_count)
    checks["inf_count"] = int(inf_count)
    if nan_count > 0:
        checks["nan_positions"] = np.argwhere(np.isnan(features)).tolist()[:10]
    if inf_count > 0:
        checks["inf_positions"] = np.argwhere(np.isinf(features)).tolist()[:10]
    # Load labels
    if label_file and os.path.isfile(label_file):
        try:
            labels = np.loadtxt(label_file, delimiter=",", max_rows=max_rows)
            checks["label_rows"] = len(labels)
            unique_labels = np.unique(labels)
            checks["unique_labels"] = unique_labels.tolist()
            checks["labels_01_only"] = set(unique_labels).issubset({0, 1})
        except Exception as e:
            checks["label_error"] = str(e)
    else:
        checks["label_file"] = "not found"
        labels = None
    # Row count consistency
    if "label_rows" in checks and checks.get("feature_rows") != checks.get("label_rows"):
        checks["row_mismatch"] = f"features={checks['feature_rows']} vs labels={checks['label_rows']}"
    # Training contamination check (first FMgrace+ADgrace=55000 rows)
    if labels is not None and len(labels) >= 55001:
        train_labels = labels[:55001]
        attack_in_train = int((train_labels > 0).sum())
        checks["attack_in_first_55001"] = attack_in_train
        checks["training_contamination"] = attack_in_train > 0
    elif labels is not None:
        checks["training_contamination"] = "insufficient rows"
    checks["feature_sample"] = features[:3, :3].tolist() if features.ndim > 1 else features[:3].tolist()
    return checks

# --- KitNET Experiment --------------------------------------------------------

def run_kitnet_on_uci(feature_file, label_file, experiment_dir, max_rows=None):
    _patch_numpy()
    cwd = os.getcwd()
    sys.path.insert(0, SOURCE_ROOT)
    import KitNET.KitNET as KitNET
    os.chdir(SOURCE_ROOT)
    # Load data
    features = np.loadtxt(feature_file, delimiter=",", max_rows=max_rows)
    if features.ndim == 2 and np.allclose(features[:, 0], np.arange(features.shape[0])):
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
    # Load labels for execution phase
    labels = None
    if label_file and os.path.isfile(label_file):
        label_data = np.loadtxt(label_file, delimiter=",", max_rows=max_rows)
        if labels is not None and len(label_data) > FMGRACE + ADGRACE + 1:
            labels = label_data[FMGRACE + ADGRACE + 1:len(rmse_list) + FMGRACE + ADGRACE + 1]
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
    if labels is not None and len(labels) > 0:
        benign_rmse = rmse_arr[labels == 0]
        attack_rmse = rmse_arr[labels == 1]
        metrics["benign_rmse_mean"] = float(np.mean(benign_rmse)) if len(benign_rmse) > 0 else None
        metrics["attack_rmse_mean"] = float(np.mean(attack_rmse)) if len(attack_rmse) > 0 else None
        metrics["benign_count"] = int((labels == 0).sum())
        metrics["attack_count"] = int((labels == 1).sum())
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

def main():
    parser = argparse.ArgumentParser(description="Kitsune Overnight Exploratory Experiment")
    parser.add_argument("--max-rows", type=int, default=None, help="Max rows/packets to process")
    parser.add_argument("--output-dir", default=os.path.join(RESULTS_ROOT, EXP_ID), help="Output directory")
    parser.add_argument("--no-overwrite", action="store_true", help="Skip if results exist")
    parser.add_argument("--attack", default=None, help="Run only specific attack (subdir name)")
    args = parser.parse_args()
    experiment_dir = args.output_dir
    os.makedirs(experiment_dir, exist_ok=True)
    # Check overwrite
    status_file = os.path.join(experiment_dir, "status.json")
    if args.no_overwrite and os.path.isfile(status_file):
        with open(status_file) as f:
            st = json.load(f)
        if st.get("status") == "completed":
            print(f"Results already exist at {experiment_dir} (status=completed). Skipping.")
            return
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
    # Phase 1: Track A - Mirai PCAP Baseline
    print("\n=== Phase 1: Mirai PCAP Baseline (Track A) ===")
    mirai_dir = os.path.join(experiment_dir, "mirai-baseline")
    os.makedirs(mirai_dir, exist_ok=True)
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
    # Phase 2: Scan for UCI data
    print("\n=== Phase 2: UCI Dataset Scan (Track B) ===")
    attacks = scan_uci_data(DATA_ROOT)
    if not attacks:
        print("  No UCI data found under data/kitsune/")
        print("  Creating framework structure for future runs...")
        # Record blocked status
        blocked_dir = os.path.join(experiment_dir, "uci-blocked")
        os.makedirs(blocked_dir, exist_ok=True)
        save_status(blocked_dir, "blocked", "UCI data not available at data/kitsune/. Download and place before re-run.")
        # Create a how-to-continue document
        continue_doc = os.path.join(experiment_dir, "HOW_TO_CONTINUE.md")
        with open(continue_doc, "w") as f:
            f.write("""# How to Continue Overnight Experiment

## Status
UCI dataset was not found at `data/kitsune/`. Only the Mirai PCAP baseline was run.

## To Continue

1. Download the UCI Kitsune Network Attack Dataset from:
   https://archive.ics.uci.edu/dataset/516/kitsune+network+attack+dataset

2. Place each attack's files in:
   data/kitsune/<attack_name>/
   Example: data/kitsune/mirai/mirai_dataset.csv, data/kitsune/mirai/mirai_labels.csv

3. Re-run:
   python scripts/run_experiment.py --output-dir results/overnight-20260712

## Expected Attack Directories
- mirai/
- ssdp_flood/
- os_scan/
- ssl_renegotiation/
- arp_mitm/
- syn_dos/
- fuzzing/
- active_wiretap/
- video_injection/

## Parameters (fixed for all attacks)
- FMgrace=5000, ADgrace=50000, maxAE=10, lr=0.1, hr=0.75
""")
        results_summary["uci"] = {"status": "blocked", "message": "UCI data not found"}
    else:
        print(f"  Found {len(attacks)} attack directories")
        for attack_name, info in sorted(attacks.items()):
            if args.attack and attack_name != args.attack:
                continue
            print(f"\n  --- {attack_name} ---")
            attack_dir = os.path.join(experiment_dir, attack_name)
            os.makedirs(attack_dir, exist_ok=True)
            feature_file = info.get("feature_file")
            label_file = info.get("label_file")
            if not feature_file or not os.path.isfile(feature_file):
                print(f"    SKIPPED: feature file not found")
                save_status(attack_dir, "blocked", "feature file not found")
                results_summary[attack_name] = {"status": "blocked", "message": "feature file not found"}
                continue
            # Pre-checks
            print(f"    Pre-checking data...")
            checks = precheck_data(feature_file, label_file, max_rows=args.max_rows)
            if "error" in checks:
                print(f"    PRE-CHECK FAILED: {checks['error']}")
                save_status(attack_dir, "failed", checks["error"])
                results_summary[attack_name] = {"status": "failed", "message": checks["error"]}
                all_ok = False
                continue
            # Save checks
            with open(os.path.join(attack_dir, "precheck.json"), "w") as f:
                json.dump(checks, f, indent=2)
            print(f"    Feature dim: {checks.get('actual_feature_dim')}, rows: {checks.get('feature_rows')}")
            if checks.get("nan_count", 0) > 0:
                print(f"    WARNING: {checks['nan_count']} NaN values found")
            if checks.get("inf_count", 0) > 0:
                print(f"    WARNING: {checks['inf_count']} Inf values found")
            if checks.get("training_contamination"):
                print(f"    WARNING: {checks.get('attack_in_first_55001')} attack samples in first 55001 rows")
            # Run KitNET
            print(f"    Running KitNET...")
            load_config(attack_dir, attack_name, checks.get("actual_feature_dim", 0))
            try:
                metrics, rmse_arr, labels = run_kitnet_on_uci(
                    feature_file, label_file, attack_dir, max_rows=args.max_rows
                )
                save_metrics(attack_dir, metrics)
                save_rmse(attack_dir, rmse_arr, labels)
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
