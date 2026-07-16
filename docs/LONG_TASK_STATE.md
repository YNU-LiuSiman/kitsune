# Long Task State

## Current status

- Status: blocked-partial
- Governing plan: `docs/EWMA_IMPLEMENTATION_PLAN.md` plus the user-specified threshold/EWMA protocol
- Branch: `phase/04-ewma`
- HEAD: `0a1555f`
- Current milestone: threshold protocol blocked after direction/timing/calibration audit

## Recovery snapshot

- Baseline PR: #4 (open Draft; must remain unchanged)
- No active Python/KitNET process observed at recovery.
- Existing modified and untracked experiment artifacts predate this state file; preserve and audit them.
- Script audit complete. Required repairs identified:
  - Current UCI outputs share one attack directory, so smoke and full collide.
  - Smoke currently receives `completed`, violating the required state semantics.
  - Full precheck currently loads whole files rather than streaming them.
  - Required metrics, artifact names, traceback persistence, and test coverage are incomplete.
- Pre-existing modified and untracked files remain outside this phase's staging scope.
- Completed: all nine execution score/label pairs are exactly aligned, finite,
  and start at row 55,001. The readiness audit is under
  `results/overnight-20260712/ewma/`.
- Blocker: no training-period RMSE is persisted. See
  `docs/LONG_TASK_BLOCKERS.md` for the required user decision.

## Current implementation

- Baseline audit artifacts are on the parent branch at `0a1555f`.
- Added `scripts/audit_ewma_readiness.py`; it only reads baseline RMSE/labels
  and writes compact direction/timing/readiness audit JSON. No EWMA series or
  threshold-dependent metric has been created.

## Completion validation

- The serial orchestrator completed all eight remaining UCI datasets.
- Each dataset has successful smoke-1000, smoke-10000, and full statuses.
- Final artifact validation passed: 8 datasets, 20,253,460 total rows, 19,813,452 execution rows; required artifacts exist, RMSE and label row counts match, and no RMSE NaN/Inf was recorded.
- Small validation summary: `results/overnight-20260712/uci_validation_summary.json`.

## Latest checks

- Governing baseline specification, project status, long-task state and blocker files read on 2026-07-16.
- Dedicated `phase/04-ewma` branch created from audited baseline `0a1555f`.
- Project `.venv` is used for all project Python work; it already contains NumPy, SciPy and Matplotlib.
- Validation: `python -m py_compile scripts/audit_ewma_readiness.py` and the
  nine-dataset readiness audit passed. All forward/reverse AUC values and
  attack interval counts were recorded. No score-label misalignment occurred.

## Resume

1. Read `docs/EWMA_IMPLEMENTATION_PLAN.md`, `docs/project_status.md`, and this state file.
2. Check Git status and preserve the pre-existing dirty boundary.
3. Obtain the user-selected legal, label-free calibration protocol from
   `docs/LONG_TASK_BLOCKERS.md`; only then implement thresholds and EWMA.
