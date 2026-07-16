# Project Status

## Current Baseline

| Field | Value |
|---|---|
| Stable main SHA | `0b2d937` |
| Current phase | Threshold protocol and EWMA post-processing evaluation |
| Current branch | `phase/04-ewma` |
| Last PR | #5 Draft — EWMA follow-up to baseline audit |
| Last review | Nine-dataset fixed-window threshold/EWMA evaluation validated |
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
- [x] Fixed label-free calibration protocol: first 10,000 execution scores, excluded from evaluation
- [x] Nine-dataset baseline versus EWMA (`alpha=0.10`) comparison with threshold and alpha sensitivity outputs

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
- EWMA evaluation completed under its fixed protocol; interpretation must retain per-dataset improvement/neutral/degradation outcomes rather than a global improvement claim.

## Next Phase

Use the generated summaries and figures in the report, discuss calibration-window limitations and extreme finite RMSE values, and avoid claiming a universal EWMA gain. Do not modify official Kitsune source for this review.

## Recent Review Conclusion (PR #1)

- Repository storage policy approved
- Academic datasets corrected from BotIoT/CIC-IDS to UCI Kitsune
- Log sanitization rules refined to preserve experimental fidelity
- `.gitattributes` covers both `docs/` and `docx/` for LFS
- All verification tests (check-ignore, check-attr) passed
