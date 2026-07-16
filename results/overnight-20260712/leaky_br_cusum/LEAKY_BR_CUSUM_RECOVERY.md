# Leaky BR-CUSUM Recovery

This is the final detector-method experiment. It reads existing baseline RMSE
and labels only; it does not alter KitNET, the original BR-CUSUM outputs, EWMA
outputs, or datasets.

From `<PROJECT_ROOT>` on `phase/05b-leaky-br-cusum`:

```powershell
.\.venv\Scripts\python.exe scripts\run_leaky_br_cusum_evaluation.py
```

The fixed main protocol is calibration rows 0..9,999, evaluation from raw row
65,001, `rho=0.95`, `k=0.50`, and q99.5 threshold. Labels are only used after
score construction for audit and evaluation.

Current results show that decay does not remove long non-zero runs under this
protocol. Do not silently reset, clip, or retune it. Reset-on-alarm remains an
optional separately named event-level sensitivity, not a replacement method.
