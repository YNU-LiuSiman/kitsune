# Project Status

## Current Baseline

| Field | Value |
|---|---|
| Stable main SHA | `0b2d937` |
| Current phase | BR-CUSUM robust bidirectional post-processing evaluation |
| Current branch | `phase/05-br-cusum` |
| Last PR | pending Draft — BR-CUSUM follow-up to EWMA |
| Last review | Nine-dataset fixed-window BR-CUSUM evaluation validated |
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
- [x] Nine-dataset BR-CUSUM (`k=0.50`) comparison with robust/two-sided and upper-CUSUM ablations

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
- BR-CUSUM main protocol exhibits long non-zero CUSUM drift across all nine datasets; its lower channel had no main-threshold alerts. This must be reported as a limitation, not hidden by resetting or clipping.

## Next Phase

Use the baseline, EWMA, and BR-CUSUM summaries in the report. Discuss the fixed calibration split, extreme finite RMSE values, CUSUM drift and the inactive lower channel; avoid universal improvement claims. Do not modify official Kitsune source for this review.

## Recent Review Conclusion (PR #1)

- Repository storage policy approved
- Academic datasets corrected from BotIoT/CIC-IDS to UCI Kitsune
- Log sanitization rules refined to preserve experimental fidelity
- `.gitattributes` covers both `docs/` and `docx/` for LFS
- All verification tests (check-ignore, check-attr) passed
