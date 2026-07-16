# Leaky BR-CUSUM Closing Experiment Plan

This is the final new detection-method experiment. It is a drift-control
variant of BR-CUSUM, not a replacement for the already recorded BR-CUSUM main
result.

## Fixed Protocol

- Calibration: execution rows 0..9,999 (raw 55,001..65,000); evaluation begins
  at raw row 65,001.
- Calibration uses only scores. Labels are read only afterwards for audit and
  evaluation.
- Robust upper/lower channels are unchanged from BR-CUSUM.
- Main recurrence uses `rho=0.95`, `k=0.50`, continuous state, and q99.5 of
  calibration Leaky BR-CUSUM. Sensitivity is only the pre-registered rho, k,
  and q grids.
- No reset-on-alarm result is part of the main experiment.

## Required Analysis

Compare baseline, EWMA, original BR-CUSUM and Leaky BR-CUSUM; retain all
finite extremes. Report drift, upper/lower channel contribution, detection
delay and per-dataset improvement/neutral/degradation relative to original
BR-CUSUM. Do not develop a fourth method after this experiment.
