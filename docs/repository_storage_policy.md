# Repository Storage Policy

## 1. Files Stored in Regular Git

The following file types are committed directly via normal Git:

| Directory / Pattern | Contents |
|---|---|
| `docs/` | Markdown audit reports, protocols, design documents, and storage policy |
| `docx/` | Course report Word documents, exported PDFs, formal figures, and deliverables |
| `scripts/` | Experiment scripts and analysis programs |
| `configs/` | Non-sensitive experiment configurations |
| `tests/` | Test code |
| `results/**/manifest.json` | Experiment identity information (commit hash, timestamp, environment) |
| `results/**/config.json` | Actual experiment parameters used |
| `results/**/metrics.json` | Experiment evaluation metrics |
| `results/**/summary.csv` | Aggregated result summary |
| `results/**/plots/` | Formal publication-ready figures and charts |
| `results/**/logs/sanitized/` | Sanitized (redacted) experiment logs |
| `requirements-reproduction.txt` | Python dependency specification |
| `README.md` | Project overview and reproduction instructions |

## 2. Files Managed by Git LFS

Large binary artifacts that must be preserved are tracked via Git LFS:

| Pattern | Rationale |
|---|---|
| `docx/**/*.docx` | Course report Word source files (may contain embedded figures) |
| `docx/**/*.pdf` | Exported PDF reports with formal typesetting |
| `results/**/raw/**` | Large raw experiment outputs (e.g., per-packet RMSE CSVs) |
| `results/**/*.csv.gz` | Compressed large CSV results (e.g., 100K+ row metrics) |
| `results/**/*.parquet` | Columnar storage for large tabular results |
| `results/**/*.npy` | NumPy array dumps from experiment runs |
| `results/**/*.npz` | Compressed NumPy archive outputs |
| `results/**/*.pkl` | Serialized Python object results |
| `results/**/*.joblib` | Joblib-serialized intermediate results |

## 3. Files Completely Excluded (Not Committed)

The following must never enter the Git repository:

| Category | Examples | Reason |
|---|---|---|
| UCI raw datasets | `data/` contents (excluding README) | Reproducible via download; too large for Git |
| Packet captures | `*.pcap`, `*.pcapng`, `*.cap` | Large binary files; can be regenerated or re-downloaded |
| Downloaded archives | `*.zip`, `*.7z`, `*.rar`, `*.tar.gz` | Third-party artifacts; not original work |
| Conda / Python environments | `venv/`, `.venv/`, `env/`, `conda-meta/` | Platform-specific; reproducible via `requirements*.txt` |
| Python cache | `__pycache__/`, `*.pyc` | Automatically generated; worthless in version control |
| IDE configuration | `.vscode/`, `.idea/` | User-specific; not part of the project |
| Secrets and keys | `*.key`, `*.pem`, `*.token`, `secrets/` | Security risk |
| Local-only config | `configs/local*.json/yaml/yml` | Machine-specific paths and credentials |
| Temporary outputs | `*.tmp`, `*.partial`, `cache/`, `temp/` | Incomplete or reproducible intermediates |
| Interrupted experiment state | `results/**/tmp/`, `results/**/.partial/` | Partial run artifacts with no scientific value |
| Raw unsanitized logs | `logs/raw/`, `results/**/logs/raw/` | May contain absolute paths, user names, or other PII |
| ML experiment trackers | `wandb/`, `mlruns/` | Third-party experiment tracking databases |

## 4. `docs/` vs `docx/`

| Directory | Format | Purpose |
|---|---|---|
| `docs/` | Markdown (`.md`) | Machine-readable; diff-friendly; audit trail, protocols, plans, policy |
| `docx/` | Word (`.docx` / `.pdf`) | Human-readable; course deliverables; formal reports; embedded figures |

**Rule:** Edit workflow documentation in `docs/`. Place final deliverables in `docx/`.

## 5. Recommended `results/` Structure

```
results/
└── <experiment_id>/
    ├── manifest.json       # Git commit, date, hostname (sanitized), dependency versions
    ├── config.json         # Experiment parameters (reproducible)
    ├── metrics.json        # Summary metrics (RMSE, accuracy, etc.)
    ├── summary.csv         # Aggregated results table
    ├── plots/              # Formal figures (PNG/SVG/PDF, regular Git)
    ├── logs/
    │   ├── sanitized/      # Cleaned logs (regular Git)
    │   └── raw/            # Raw logs (ignored via .gitignore)
    └── raw/                # Large numerical results (Git LFS)
```

Only `raw/` (for large results) uses Git LFS. All other files use regular Git.

## 6. Raw Logs vs Sanitized Logs

| Type | Content | Storage |
|---|---|---|
| **Raw logs** | Full stdout/stderr; may contain absolute local paths, user names, IPs, timestamps | Ignored by `.gitignore` |
| **Sanitized logs** | Redacted versions: paths replaced with relative, user names removed, timestamps normalized | Committed via regular Git |

**Sanitization rules:**
- Replace `C:\Users\username` with `<USER_HOME>`
- Replace `D:\path\to\project` with `<REPO_ROOT>`
- Remove or mask IP addresses and host names
- Remove API keys and tokens
- Keep experiment-relevant output intact

## 7. Dataset Management

Raw datasets (UCI BotIoT, CIC-IDS, etc.) are **not** committed.

Each dataset is documented in `data/README.md` with:
- Dataset name and version
- Original download URL
- Expected directory layout under `data/`
- Required file names
- SHA-256 checksums for integrity verification

Users reproduce experiments by running `data/README.md` download instructions.

## 8. Why Conda Environments and Raw Data Are Excluded

| Asset | Size (typical) | Reason for Exclusion |
|---|---|---|
| Conda environment | 1–5 GB | Platform-specific; reproducible via `requirements*.txt` |
| UCI BotIoT dataset | 50–100 GB | Publicly downloadable; too large for any Git repository |
| PCAP files | 50 MB–10 GB | Third-party captures; referenced by URL |
| Python cache | 10–100 MB | Automatically regenerated; no scientific value |
| IDE metadata | 1–10 MB | Editor-specific; irrelevant to reproducibility |

## 9. Currently Tracked Large Files

The following large files are already tracked in Git history:

| File | Size | Type |
|---|---|---|
| `Kitsune/Kitsune-py/mirai.pcap` | ~60 MB | Binary packet capture (third-party) |
| `Kitsune/Kitsune-py/mirai.zip` | ~400 KB | Compressed archive (third-party) |
| `Kitsune/Kitsune-py/Kitsune paper.pdf` | ~3 MB | Published paper (third-party, already in original repo) |
| `docs/Kitsune复现报告最终版.docx` | varies | Course report (own work, formal deliverable) |
| `docs/Kitsune复现报告最终版.pdf` | varies | Exported report (own work, formal deliverable) |

## 10. Recommended Actions for Existing Large Files

The following actions are **proposed** for future execution (not yet applied):

1. **`mirai.pcap` (~60 MB):** Consider one of:
   - (Recommended) Add to `.gitignore` and remove from tracking via `git rm --cached`. Keep download instructions in `data/README.md`.
   - Convert to Git LFS if retention in history is essential.

2. **`mirai.zip` (~400 KB):** Small enough to stay, but conceptually should be treated like `mirai.pcap`. Consider adding to `.gitignore`.

3. **`Kitsune paper.pdf` (~3 MB):** Part of the original `Kitsune-py` distribution. Acceptable to keep. Consider LFS if many such PDFs accumulate.

4. **Own reports (`docs/*.docx`, `docs/*.pdf`):** These are formal deliverables and should be **retained**. When the `docx/` directory is adopted, they should be moved there and tracked via Git LFS.

**Not yet executed:** `git rm --cached`, `git lfs migrate`, or `git filter-repo`. These require explicit human approval.

## 11. Implementation Status

| Component | Status |
|---|---|
| `.gitignore` | Updated (this PR) |
| `.gitattributes` | Created (this PR) |
| `data/README.md` | Created (this PR) |
| `results/README.md` | Created (this PR) |
| `logs/README.md` | Created (this PR) |
| `docs/repository_storage_policy.md` | Created (this PR) |
| Migrate existing large files to LFS | Pending human review |
| `git rm --cached` for mirai.pcap / mirai.zip | Pending human review |
| `git lfs migrate` for historical cleanup | Pending human review |
