# Long Task State

## Current status

- Status: running
- Governing plan: `docs/Kitsune_剩余实验执行规范.md` (SHA-256 `6C6A4095CAF21157EA5607239BDCF8BD9BA9CD3B442045F0661F05D4BFDF4C70`)
- Branch: `exp/overnight-20260712`
- HEAD: `ae29a9d`
- Current milestone: validating isolated UCI runner before OS Scan rerun

## Recovery snapshot

- Draft PR: #4 (open)
- No active Python/KitNET process observed at recovery.
- Existing modified and untracked experiment artifacts predate this state file; preserve and audit them.
- Script audit complete. Required repairs identified:
  - Current UCI outputs share one attack directory, so smoke and full collide.
  - Smoke currently receives `completed`, violating the required state semantics.
  - Full precheck currently loads whole files rather than streaming them.
  - Required metrics, artifact names, traceback persistence, and test coverage are incomplete.
- Next action: replace the UCI execution interface with isolated run directories and add automated tests before any dataset run.

## Current implementation

- Added `scripts/run_uci_experiment.py`: per-attack/per-phase output isolation, stream-based full precheck, data hashes, required artifact names, empty smoke RMSE files, state semantics, and threshold-free score metadata.
- Syntax compilation and a compressed OS Scan CSV parsing check passed in the project `.venv`.
- Next action: add and run synthetic runner tests for index/label variants and smoke/full isolation.

## Latest checks

- Plan and `docs/project_status.md` read on 2026-07-15.
- Git fetch completed; local branch is ahead of origin by one commit.
- D drive free space: approximately 137 GB.
- PR #4 is open Draft: https://github.com/YNU-LiuSiman/kitsune/pull/4
- Project virtual environment created at `.venv` for this worktree; it currently contains the minimum test dependency `numpy` and no global Python packages were modified.

## Resume

1. Read the governing plan and `docs/project_status.md`.
2. Check Git status, worktrees, active processes, and existing result statuses.
3. Continue the engineering-repair milestone without overwriting prior full results.
