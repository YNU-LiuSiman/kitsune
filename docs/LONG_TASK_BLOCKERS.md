# Long Task Blockers

## 2026-07-16 — threshold calibration protocol required

All nine persisted RMSE files begin at execution row 55,001 and contain exactly
the execution-row count. No training-period RMSE score series exists locally.
The original first 55,001 labels are benign, but labels are not scores and may
not be used to fabricate a threshold calibration distribution.

Threshold-dependent evaluation is therefore blocked without one of these
user-authorized, label-free protocols:

1. A pre-declared execution calibration window (its rows are excluded from
   final evaluation, and its labels remain unread during calibration); or
2. A score-only baseline rerun that persists RMSE for training rows 0..55,000
   into a new independent calibration artifact, without touching baseline
   results or official Kitsune source.

Forbidden fallbacks: test-label selection, test-F1 optimization, per-dataset
attack-aware threshold selection, or silently treating execution labels as
calibration labels.
