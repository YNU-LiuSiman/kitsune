# Results Directory

This directory stores experiment outputs and evaluation results.

**Policy:** Formal results (metrics, summaries, plots, sanitized logs) are
committed via regular Git. Large raw outputs are tracked via Git LFS.

## Structure

```
results/
└── <experiment_id>/
    ├── manifest.json       # Experiment identity (commit, timestamp, env)
    ├── config.json         # Parameters used in the run
    ├── metrics.json        # Summary evaluation metrics
    ├── summary.csv         # Aggregated results table
    ├── plots/              # Formal figures (regular Git)
    ├── logs/
    │   ├── sanitized/      # Cleaned logs (regular Git)
    │   └── raw/            # Raw logs (ignored, not committed)
    └── raw/                # Large numerical results (Git LFS)
```

## Naming Convention

Use descriptive experiment IDs:

- `mirai-baseline` — Mirai attack baseline run
- `mirai-ablation-<variant>` — Ablation study variants
- `cross-dataset-<name>` — Cross-dataset validation
