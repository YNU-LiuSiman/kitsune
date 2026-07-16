# BR-CUSUM Recovery

BR-CUSUM is a read-only post-processing experiment. It does not alter KitNET,
baseline RMSE, EWMA artifacts, or source datasets.

From `<PROJECT_ROOT>` on `phase/05-br-cusum`, regenerate the derived results:

```powershell
.\.venv\Scripts\python.exe scripts\run_br_cusum_evaluation.py
```

The fixed protocol uses execution rows 0..9,999 for calibration and raw row
65,001 onward for evaluation. It computes median/MAD robust channels in both
directions, runs continuous CUSUM with main `k=0.50`, and uses calibration
q99.5 as the main threshold. Labels are used only after score construction for
contamination audit and metrics.

The current main protocol records long non-zero CUSUM runs. This is evidence,
not an error to silently reset or clip. Any reset-on-alarm experiment must be
stored as a separately named sensitivity experiment and cannot replace the
main result.
