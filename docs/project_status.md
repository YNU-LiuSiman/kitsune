# Project Status

## Current Baseline

| Field | Value |
|---|---|
| Stable main SHA | `0b2d937` |
| Current phase | Baseline result audit and unified evaluation |
| Current branch | `exp/overnight-20260712` |
| Last PR | #4 Draft — remaining UCI experiments and audit |
| Last review | Nine UCI full-result artifacts audited locally |
| Last updated | 2026-07-16 |

## Completed

- [x] Repository initialization and governance files (`.gitignore`, `.gitattributes`, storage policy)
- [x] Dataset directory structure (`data/`, `logs/`, `results/`)
- [x] Legacy report moved to `docs/`
- [x] Nested git repository removed from `Kitsune/Kitsune-py/`
- [x] Mirai UCI full baseline and eight remaining UCI full baselines
- [x] Full-result artifact validation: required artifacts, RMSE/label counts and finite-value checks
- [x] Nine-dataset threshold-free audit: ROC-AUC, PR-AUC, class distributions and extreme-value audit
- [x] Local archive manifest with file hashes and recovery commands

## Locked Decisions

- Keep `mirai.zip` (7.46 MB) as offline smoke-test sample
- Future PR: remove `mirai.pcap` (59.95 MB) with `git rm --cached`
- Keep `Kitsune paper.pdf` (4.18 MB) in regular Git
- No `git lfs migrate` or history rewrite
- No direct commits to `main`
- No auto-merge of PRs
- No modifications to official Kitsune Python source

## Open Issues

1. **100-dim vs 115-dim:** Two separate tracks. Python PCAP → AfterImage → KitNET(n=100). UCI CSV → KitNET(n=115). Not a compatibility issue; KitNET n is dynamic.
2. **Extreme RMSE values:** Several datasets have finite but very large max/median ratios. Score/label alignment is verified; input scale and normalization boundaries require review before causal interpretation.
3. **Grace periods:** All exploratory runs use FMgrace=5000, ADgrace=50000 (unified). Parameter tuning deferred.
4. **Threshold determination:** Log-normal cutoff method from example.py; applicability to UCI data needs verification.

## Blockers

- No baseline-data integrity blocker was found in the unified audit.
- EWMA is intentionally deferred until the baseline audit conclusions are reviewed.

## Next Phase

Review the baseline audit, decide how to investigate extreme finite RMSE values, then consider a separately specified EWMA phase. Do not modify official Kitsune source for this review.

## Recent Review Conclusion (PR #1)

- Repository storage policy approved
- Academic datasets corrected from BotIoT/CIC-IDS to UCI Kitsune
- Log sanitization rules refined to preserve experimental fidelity
- `.gitattributes` covers both `docs/` and `docx/` for LFS
- All verification tests (check-ignore, check-attr) passed
