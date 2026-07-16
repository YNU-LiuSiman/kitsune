# Long Task State

## Current status

- Status: done
- Governing plan: `docs/BR_CUSUM_IMPLEMENTATION_PLAN.md` plus the user-specified BR-CUSUM protocol
- Branch: `phase/05-br-cusum`
- HEAD: `6ce625b`
- Current milestone: BR-CUSUM committed; preparing branch push and Draft PR

## Recovery snapshot

- Baseline PRs: #4 and #5 (open Draft; must remain unchanged)
- No active Python/KitNET process observed at recovery.
- Existing modified and untracked experiment artifacts predate this state file; preserve and audit them.
- Script audit complete. Required repairs identified:
  - Current UCI outputs share one attack directory, so smoke and full collide.
  - Smoke currently receives `completed`, violating the required state semantics.
  - Full precheck currently loads whole files rather than streaming them.
  - Required metrics, artifact names, traceback persistence, and test coverage are incomplete.
- Pre-existing modified and untracked files remain outside this phase's staging scope.
- New outputs are restricted to `results/overnight-20260712/br_cusum/`.
- Completed: all nine execution score/label pairs are exactly aligned, finite,
  and start at row 55,001. The readiness audit is under
  `results/overnight-20260712/ewma/`.
- The fixed user-authorized, label-free execution calibration window resolves
  the threshold blocker. Its rows 0..9,999 are excluded from final evaluation.

## Current implementation

- Baseline audit artifacts are on the parent branch at `0a1555f`.
- Added `scripts/run_ewma_evaluation.py` and synthetic tests. The script uses
  only the fixed calibration score window for thresholds and writes derived
  small results under `results/overnight-20260712/ewma/`.
- BR-CUSUM reads baseline RMSE only and uses the same fixed execution-period
  calibration split.
- Added `scripts/run_br_cusum_evaluation.py` and synthetic tests. The main
  protocol completed nine datasets without copying score or label files.

## Completion validation

- The serial orchestrator completed all eight remaining UCI datasets.
- Each dataset has successful smoke-1000, smoke-10000, and full statuses.
- Final artifact validation passed: 8 datasets, 20,253,460 total rows, 19,813,452 execution rows; required artifacts exist, RMSE and label row counts match, and no RMSE NaN/Inf was recorded.
- Small validation summary: `results/overnight-20260712/uci_validation_summary.json`.

## Latest checks

- Governing baseline specification, project status, long-task state and blocker files read on 2026-07-16.
- Dedicated `phase/04-ewma` branch created from audited baseline `0a1555f`.
- Draft PR #5 created against `exp/overnight-20260712`; PR #4 remains unchanged.
- Project `.venv` is used for all project Python work; it already contains NumPy, SciPy and Matplotlib.
- Validation: `python -m py_compile scripts/audit_ewma_readiness.py` and the
  nine-dataset readiness audit passed. All forward/reverse AUC values and
  attack interval counts were recorded. No score-label misalignment occurred.
- Validation: `python -m unittest discover -s tests -v` passed 11/11 in
  7.556 seconds, including EWMA arithmetic, alpha boundaries, label isolation,
  temporal metrics, extreme scores, and interrupted-resume semantics.
- Nine-dataset execution completed using the user-authorized fixed window:
  9 summaries, 486 threshold rows, 45 alpha rows, 9 completed statuses and no
  raw score/label copies in the EWMA output directory. Final full test suite:
  11/11 passed in 7.434 seconds.
- Checkpoint commits: `b6aeffd` (implementation/tests) and `7412331`
  (nine-dataset derived results, figures, protocol and recovery note).
- BR-CUSUM validation: 19/19 tests passed in 7.541 seconds. Nine completed
  statuses, 45 ablation rows, 81 sensitivity rows and no copied raw files.
  Main-channel audit found long non-zero CUSUM drift and zero lower-channel
  main-threshold alerts on all nine datasets; results are retained unchanged.
- Checkpoint commits: `b9701a4` (detector/tests) and `9c03ede`
  (nine-dataset results, plots and documentation).

## Resume

1. Read `docs/EWMA_IMPLEMENTATION_PLAN.md`, `docs/project_status.md`, and this state file.
2. Check Git status and preserve the pre-existing dirty boundary.
3. Push `phase/05-br-cusum` and create a Draft PR against `phase/04-ewma`.
   Do not treat the main drift result as evidence to tune k with labels.
