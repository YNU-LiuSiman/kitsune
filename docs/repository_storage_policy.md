# Repository Storage Policy

## 1. Files Stored in Regular Git

The following file types are committed directly via normal Git:

| Directory / Pattern | Contents |
|---|---|
| `docs/` | Markdown audit reports, protocols, design documents, and storage policy |
| `docx/` | (Target) Course report Word documents, exported PDFs, formal figures, and deliverables |
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

Large binary artifacts that must be preserved are tracked via Git LFS.
Note: Adding LFS attributes to `.gitattributes` does **not** automatically
migrate existing Git objects. Historical files remain in regular Git until
explicitly migrated with `git lfs migrate` (requires separate PR and review).

| Pattern | Rationale |
|---|---|
| `docs/**/*.docx` | Current report location — formal Word deliverables |
| `docs/**/*.pdf` | Current report location — exported PDF reports |
| `docx/**/*.docx` | Target report location — formal Word deliverables |
| `docx/**/*.pdf` | Target report location — exported PDF reports |
| `results/**/raw/**` | Large raw experiment outputs (e.g., per-packet RMSE CSVs) |
| `results/**/*.csv.gz` | Compressed large CSV results |
| `results/**/*.parquet` | Columnar storage for large tabular results |
| `results/**/*.npy` | NumPy array dumps from experiment runs |
| `results/**/*.npz` | Compressed NumPy archive outputs |
| `results/**/*.pkl` | Serialized Python object results |
| `results/**/*.joblib` | Joblib-serialized intermediate results |

## 3. Files Completely Excluded (Not Committed)

The following must never enter the Git repository:

| Category | Examples | Reason |
|---|---|---|
| Raw datasets | `data/` contents (excluding README) | Reproducible via download; too large for Git |
| Packet captures | `*.pcap`, `*.pcapng`, `*.cap` | Large binary files; can be re-acquired from public sources or restored from retained official samples |
| Downloaded archives (non-essential) | `*.7z`, `*.rar`, `*.tar.gz` | Third-party artifacts; not original work |
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

| Directory | Format | Purpose | Status |
|---|---|---|---|
| `docs/` | Markdown (`.md`) + legacy `.docx`/`.pdf` | Machine-readable audit trail, protocols, plans, policy | Current layout |
| `docx/` | Word (`.docx` / `.pdf`) | (Target) Course deliverables; formal reports; embedded figures | Target layout |

**Current layout:** Formal reports (`Kitsune复现报告最终版.docx`, `Kitsune复现报告最终版.pdf`)
reside in `docs/`. This is a **legacy layout**.

**Target layout:** Formal reports should eventually move to `docx/`. Migration
will be performed in a **separate PR** — this PR does not move any files.

**Rule for new work:** Edit workflow documentation in `docs/`. Place final
deliverables in `docx/`.

## 5. Dataset

This project reproduces the **Kitsune Network Attack Dataset** (UCI),
covering nine attack types: Mirai, SSDP Flood, OS Scan, SSL Renegotiation,
ARP MitM, SYN DoS, Fuzzing, Active Wiretap, and Video Injection.

See `data/README.md` for dataset source, expected layout, and download
instructions.

## 6. Recommended `results/` Structure

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

## 7. Raw Logs vs Sanitized Logs

| Type | Content | Storage |
|---|---|---|
| **Raw logs** | Full stdout/stderr; may contain absolute local paths, user names, host names, tokens | Ignored by `.gitignore` |
| **Sanitized logs** | Redacted versions with PII removed; experiment-relevant data preserved intact | Committed via regular Git |

### Must Redact (Remove or Mask)

- Local user names and account names
- Absolute local file system paths (replace with `<REPO_ROOT>`)
- Host names of local machines
- Account credentials, API tokens, keys, and passwords
- Personal information unrelated to the experiment
- Unnecessary real private network addresses

### Must Preserve (Keep Unchanged)

- Packet sequence numbers and ordering
- Attack start positions and timestamps
- Experiment start and end times
- Elapsed durations and performance metrics
- Public dataset IP addresses and network fields where relevant
- Model phase transition information (training, detection, etc.)
- All experiment parameters required for reproducibility
- Public dataset identifiers and metadata

### Network Address Sanitization

If private network identifiers must be masked, use stable consistent
mappings (e.g., `<HOST_A>`, `<HOST_B>`) throughout the same log file to
preserve relational integrity.

## 8. Dataset Management

Raw datasets (UCI Kitsune Network Attack Dataset) are **not** committed.

Each dataset is documented in `data/README.md` with:
- Dataset name and version
- Original download URL (to be confirmed during audit phase)
- Expected directory layout under `data/`
- Required file names
- SHA-256 checksums for integrity verification (to be recorded after manual verification)

Users reproduce experiments by following `data/README.md` download and
setup instructions.

## 9. Why Conda Environments and Raw Data Are Excluded

| Asset | Reason for Exclusion |
|---|---|
| Conda environment | Platform-specific; reproducible via `requirements*.txt` |
| UCI Kitsune dataset | Publicly downloadable; exact sizes to be confirmed during audit |
| PCAP files (third-party) | Can be re-acquired from public sources or restored from retained official compressed samples |
| Python cache | Automatically regenerated; no scientific value |
| IDE metadata | Editor-specific; irrelevant to reproducibility |

## 10. Currently Tracked Large Files (Actual Sizes)

The following large files are already tracked in Git history (sizes verified
via `git ls-files` + `Get-Item.Length`):

| File | Bytes | Readable Size | Type | Recommendation |
|---|---|---|---|---|
| `Kitsune/Kitsune-py/mirai.pcap` | 62,859,800 | 59.95 MB | Binary packet capture (third-party) | Future PR: `git rm --cached` and ignore; it is a derived file from `mirai.zip` |
| `Kitsune/Kitsune-py/mirai.zip` | 7,824,919 | 7.46 MB | Compressed archive (third-party) | Keep temporarily — official offline sample needed for smoke tests |
| `Kitsune/Kitsune-py/Kitsune paper.pdf` | 4,384,530 | 4.18 MB | Published paper (third-party) | Keep in regular Git — small, and serves as reproduction reference |
| `Kitsune/Kitsune-py/Kitsune_fig.png` | 248,332 | 242.51 KB | Figure from original repo | Keep — small, part of original distribution |
| `docs/Kitsune复现报告最终版.docx` | 816,877 | 797.73 KB | Formal report (own work) | Keep; future PR: move to `docx/` and manage via LFS |
| `docs/Kitsune复现报告最终版.pdf` | 1,330,084 | 1.27 MB | Exported report (own work) | Keep; future PR: move to `docx/` and manage via LFS |

### Recommended Future Actions

| Action | When |
|---|---|
| `git rm --cached Kitsune/Kitsune-py/mirai.pcap` | Separate cleanup PR |
| Add `mirai.pcap` pattern to `.gitignore` | Same cleanup PR |
| Move reports from `docs/` to `docx/` | Separate migration PR |
| Migrate `docx/` files to Git LFS | Same migration PR (attribute already configured) |
| `git lfs migrate` for historical LFS cleanup | Only if necessary; requires careful review |

**Not yet executed:** `git rm --cached`, `git lfs migrate`, `git filter-repo`,
file moves, or any history-rewriting operations. These require explicit
human approval in separate PRs.

## 11. Implementation Status

| Component | Status |
|---|---|
| `.gitignore` | Updated (this PR) |
| `.gitattributes` | Created (this PR) |
| `data/README.md` | Updated (this PR) |
| `results/README.md` | Created (this PR) |
| `logs/README.md` | Created (this PR) |
| `docs/repository_storage_policy.md` | Updated (this PR) |
| Un-track `mirai.pcap` | Pending — separate PR |
| Move reports `docs/` → `docx/` | Pending — separate PR |
| Migrate `docx/` to LFS | Pending — same migration PR |
| Historical LFS migration | Pending — human review required |
