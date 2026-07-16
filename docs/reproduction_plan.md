# Reproduction Plan — Kitsune Network Attack Dataset

## Three Tracks

### Track A: Official End-to-End Verification

```
Mirai PCAP (mirai.zip → mirai.pcap)
  → FeatureExtractor (Scapy or tshark)
  → netStat (AfterImage) → 100-dim feature vectors
  → KitNET (FM grace → AD grace → Execute)
  → Per-sample RMSE
  → Log-normal threshold + anomaly plot
```

**Objective:** Verify the existing example.py pipeline produces the expected
RMSE curve for Mirai attack data. Establishes a hardware/software baseline
for comparison.

**Input:** `Kitsune/Kitsune-py/mirai.zip`
**Parameters:** FMgrace=5000, ADgrace=50000, maxAE=10, lr=0.1, hr=0.75
**Output:** `results/mirai-baseline/`

### Track B: UCI Feature-Level Reproduction (All 9 Attacks)

```
UCI features (<Attack>_dataset.csv.gz)
  → Dimension validation (115 → 100 or wrapper adapt)
  → KitNET (FM grace → AD grace → Execute)
  → Per-sample RMSE
  → Unified evaluation metrics
```

**Objective:** Reproduce Kitsune detection across all 9 attack types using
the UCI pre-extracted features.

**Key note:** UCI provides 115-dim features; the Python PCAP path
produces 100-dim. KitNET's input dimension `n` is a **dynamic constructor
parameter** (`KitNET(n, ...)`), so UCI 115-dim feeds directly to a
KitNET(n=115) instance. No dimension conversion, padding, or stripping
is needed. The 100-dim and 115-dim are two separate experiment tracks;
they are not directly comparable at the feature level.

**Input:** `data/kitsune/<attack>/` — downloaded UCI CSVs
**Parameters:** TBD per attack during tuning
**Output:** `results/<attack_name>/`

### Track C: Improvement Experiments

```
Baseline RMSE from Track A or B
  → EWMA smoothing
  → Parameter sensitivity analysis
  → Dual-channel fusion (if approved)
  → Comparative evaluation
```

**Objective:** Propose and evaluate improvements over baseline Kitsune.
EWMA-based smoothing is the primary candidate; others require approval.

**Input:** RMSE outputs from Track A/B
**Output:** `results/improvements/`

## Data Management

### Column Validation

Each UCI CSV must be checked before processing:

| Check | Action |
|---|---|
| Check | Action |
|---|---|---|
| Feature file column count | Verify actual feature column count. Log actual count. May differ from 115; use actual count as KitNET n. |
| Index column detection | Detect if col 0 is a row index (integer sequence); skip if present |
| Label file | Read from separate label file (UCI distributes labels independently). Do **not** assume labels are in the feature file's last column. |
| Label values | Verify binary 0/1 encoding. Report any other values. |
| Row count: features vs labels | Verify feature row count == label row count |
| NaN/Inf scan | Scan features for NaN or Inf; log count and positions |
| Training contamination | Verify first 55001 samples contain zero attack labels |

### Directory Convention

```
data/kitsune/<attack>/
├── <Attack>_dataset.csv.gz    (official name)
├── <Attack>_labels.csv.gz     (official name)
├── dataset.csv                (decompressed + normalized, if used)
└── labels.csv                 (decompressed labels)
```

A preprocessing script (created in Phase 01) will handle decompression,
column validation, and standardized naming. The preprocessing pipeline
must document the rename from official filenames to internal names.

### Dataset Partitioning (Internal n_trained)

- **FM grace:** n_trained 0 — 5000 (inclusive, 5001 instances processed, clustering triggered at 5000)
- **AD grace:** n_trained 5001 — 55000 (50000 instances of AD training)
- **Execution:** n_trained ≥ 55001 (first execution instance = 55002nd 1-indexed sample)

### Exploratory Run Parameters (All Attacks)

All overnight exploratory runs use these unified parameters:

| Parameter | Value |
|---|---|
| FMgrace | 5000 |
| ADgrace | 50000 |
| maxAE | 10 |
| learning_rate | 0.1 |
| hidden_ratio | 0.75 |

These match `example.py` defaults. Parameter sensitivity analysis is deferred to a later phase.

### Dataset Sizes

Exact dataset sizes (row counts, file sizes) to be confirmed after download.
No size estimates are made without evidence.

## Metrics

### Primary

- **RMSE** per test instance (raw anomaly score)
- **EER** (Equal Error Rate) — threshold where FAR = FRR
- **AUC-ROC** (Area Under ROC Curve)
- **TPR at fixed FPR** (e.g., 1%, 0.1%) matching paper convention

### Secondary

- Execution time (total and per-packet)
- Memory usage (peak resident)
- Training time vs execution time

## Reproducibility Infrastructure

Each experiment run produces:

```
results/<experiment_id>/
├── manifest.json        # Git commit SHA, python version, platform
├── config.json          # All experiment parameters
├── metrics.json         # EER, AUC, TPR@FPR thresholds
├── summary.csv          # Per-label RMSE statistics
├── plots/
│   ├── rmse_timeseries.png
│   ├── roc_curve.png
│   └── threshold_analysis.png
├── logs/
│   └── sanitized/       # Redacted stdout/stderr
└── raw/                 # Per-packet RMSE (large → Git LFS)
```

### Interrupt and Resume

- Experiment script should checkpoint after each attack
- Re-running a completed attack should skip (config option `--force`)
- Partial results must not overwrite complete results

## Success Criteria

### A. System-Level Reproduction Success

- PCAP-to-RMSE end-to-end pipeline verified
- Configuration, logs, timing, and phase transitions saved
- Same input produces same RMSE sequence (within floating-point tolerance)

### B. Algorithm-Level Reproduction Success

- UCI features fed into KitNET via standardized wrapper
- Every test sample produces a recorded RMSE
- All 9 attacks run under a single unified framework

### C. Result-Level Reproduction Success

- Measured results independently recomputable
- Comparison against paper and/or previous class report provided
- Differences must be explained, not hidden
- No parameter tuning to force-match historical results

### D. Improvement Experiment Success

- Baseline and improvement use identical data partitioning
- Same false-positive constraint applied to both
- Report improvements AND regressions AND applicability boundaries
- Not only favorable results selected

## Curriculum Requirement Mapping

| Course Requirement | Implementation | Evidence | Report Chapter |
|---|---|---|---|
| Security frontier paper reproduction | Replicate Kitsune (NDSS'18) on 9 attack types | metrics.json, sanitized logs | Chapter 2-3 |
| Network data acquisition | Source and validate UCI Kitsune dataset | data/README.md, SHA-256 records | Chapter 3 |
| Network data analysis and mining | Feature extraction via AfterImage, anomaly detection via KitNET | RMSE plots, feature maps | Chapter 4 |
| Three+ presentation types | Metrics tables, ROC curves, RMSE time series | results/*/plots/, summary.csv | Chapter 5 |
| Complete system functionality | End-to-end experiment pipeline from data to metrics | scripts/, results/*/ | Chapter 6 |
| Coding, testing, debugging, deployment | Python experiment framework with validation | test scripts, manifest.json | Chapter 6 |
| Innovation | EWMA improvement, parameter sensitivity | improvement results | Chapter 7 |
| Workload | 9 attack types × multiple grace/config variants | All results/ directories | Throughout |
| 40-page body expansion basis | Detailed methodology, all 9 analyses, improvement study | Full report structure | 1-8 |
