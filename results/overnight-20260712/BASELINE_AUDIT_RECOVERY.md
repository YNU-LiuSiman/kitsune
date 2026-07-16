# UCI Baseline Audit Recovery

The audit is read-only with respect to full experiment artifacts. It derives
small summaries, plots, and a hash manifest from the nine completed UCI full
results.

From `<PROJECT_ROOT>` on `exp/overnight-20260712`, regenerate the audit with:

```powershell
.\.venv\Scripts\python.exe scripts\audit_uci_baselines.py
```

The command checks that `raw/rmse.csv` exactly matches the score column of
`raw/rmse_with_labels.csv`; it stops if counts, ordering, labels, or finiteness
are invalid. It writes only these derived small artifacts:

- `results/overnight-20260712/uci_baseline_summary.json`
- `results/overnight-20260712/uci_baseline_summary.csv`
- `results/overnight-20260712/uci_full_archive_manifest.json`
- `results/overnight-20260712/baseline_audit_plots/*.png`

It does not rerun KitNET, alter raw RMSE files, use threshold metrics, or alter
the official Kitsune source. Dataset-specific full rerun commands and each
result artifact SHA-256 are recorded in `uci_full_archive_manifest.json`.
