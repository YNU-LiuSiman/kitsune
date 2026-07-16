# BR-CUSUM Experiment Plan

## Fixed Protocol

- Baseline execution starts at raw row 55,001.
- Calibration is execution rows 0..9,999 (raw 55,001..65,000), selected
  without labels and excluded from all final metrics.
- Evaluation starts at raw row 65,001.
- Robust location and scale use calibration-only median, MAD, and
  `1.4826 * MAD + 1e-12`.
- Both directions are always retained. Main BR-CUSUM uses `k=0.50` and q99.5
  of calibration BR-CUSUM; sensitivity is only `k=0.25,0.50,1.00` and
  q99/q99.5/q99.9.
- Labels are read only after all score transforms and thresholds are fixed.

## Required Outputs

Write derived small artifacts only under `results/overnight-20260712/br_cusum/`:
protocol, summaries, ablation/sensitivity tables, per-dataset metrics/channel
audit/status, and plots. Do not copy RMSE or label files.

## Validation and Stop Conditions

Verify exact score/label alignment and finite scores first. Unit tests cover
robust scoring, CUSUM recurrence, state continuity, no-label parameter
isolation, edge cases and recovery. Stop only for the user-specified unsafe
conditions; baseline and EWMA directories remain read-only.
