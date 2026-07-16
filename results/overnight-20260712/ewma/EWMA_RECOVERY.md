# EWMA Evaluation Recovery

The EWMA evaluation is a post-processing stage. Baseline RMSE and label files
are read-only and remain outside this directory.

From `<PROJECT_ROOT>` on `phase/04-ewma`, regenerate all derived EWMA results:

```powershell
.\.venv\Scripts\python.exe scripts\run_ewma_evaluation.py
```

The fixed protocol is:

- calibration: execution rows 0..9,999 (raw rows 55,001..65,000);
- evaluation: raw row 65,001 onward;
- main threshold: q99.5 of the calibration score series;
- EWMA main alpha: 0.10, initialized from the first calibration RMSE;
- score direction: higher is more anomalous.

Calibration is score-only. Labels are read only after calibration for the
post-hoc contamination audit and final evaluation. The script records failed
or completed per-dataset `status.json` files. An interrupted or failed dataset
can be safely regenerated because only derived small artifacts are written.
