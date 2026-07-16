# Threshold Protocol and EWMA Improvement Plan

## Scope

Evaluate existing UCI execution-period RMSE as immutable baseline scores. EWMA
is a post-processing series only; it must not change original RMSE files,
KitNET parameters, official source, or baseline result directories.

## Milestones

1. Create `phase/04-ewma` from the audited baseline and record the dirty-tree
   boundary.
2. Revalidate nine score/label pairs: count, execution offset `55001`, binary
   label semantics, score direction, attack intervals, and forward/reversed
   ROC-AUC.
3. Establish that a legal label-free calibration source exists before computing
   threshold-dependent metrics. Training labels may verify benign status but
   may not be used to select a threshold. If no training RMSE is retained and
   no protocol-authorized calibration window is specified, stop for user
   direction rather than using execution labels or optimizing test F1.
4. Only after milestone 3 passes: implement fixed threshold families and EWMA
   alphas, add tests, write independent `results/overnight-20260712/ewma/`
   outputs, and make plots.
5. Validate artifacts, commit only scripts/tests/small summaries and plots,
   push `phase/04-ewma`, and create a new Draft PR. PR #4 remains unchanged.

## Fixed Decisions

- Score direction: `higher_is_more_anomalous`; reversed scores are diagnostic
  only.
- EWMA candidates: 0.05, 0.10, 0.20, 0.30, 0.50.
- If implementation proceeds, the main alpha is pre-fixed at 0.10; other
  values are exploratory and no per-dataset test-label selection is allowed.
- No threshold may use execution labels, attack labels, or test-F1 selection.

## Validation

- Score and label rows must match exactly and scores must be finite.
- Training/calibration-score availability must be evidenced, not assumed.
- Unit tests cover EWMA arithmetic, threshold isolation, alignment and temporal
  metrics before real summary generation.

## Stop Conditions

Stop and request direction if a legal label-free calibration source cannot be
constructed, score/label alignment fails, official source would need changing,
or any operation could overwrite baseline artifacts.
