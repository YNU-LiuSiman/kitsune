# Project Status

## Current Baseline

| Field | Value |
|---|---|
| Stable main SHA | `0b2d937` |
| Current phase | Phase 00 — Repository and Reproduction Audit |
| Current branch | `phase/00-repository-audit` |
| Last PR | #1 merged (repository storage policy) |
| Last review | PR #1 approved and merged |
| Last updated | 2026-07-12 |

## Completed

- [x] Repository initialization and governance files (`.gitignore`, `.gitattributes`, storage policy)
- [x] Dataset directory structure (`data/`, `logs/`, `results/`)
- [x] Legacy report moved to `docs/`
- [x] Nested git repository removed from `Kitsune/Kitsune-py/`
- [x] Phase 00 audit documents (repository_audit, reproduction_plan, open_questions, project_status)
- [x] PR #3 created (phase/00-repository-audit, awaiting review)
- [x] Overnight experiment script (scripts/run_experiment.py)
- [x] Mirai PCAP baseline full run: 764,137 packets, 709,136 execution rows, ~590 pkts/sec
- [x] Confirmed 100-dim output: "100 features to 16 autoencoders"
- [x] PR #4 created (exp/overnight-20260712)

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
2. **UCI dataset download:** URL, SHA-256, exact column layout TBD in audit phase.
3. **Grace periods:** All exploratory runs use FMgrace=5000, ADgrace=50000 (unified). Parameter tuning deferred.
4. **Threshold determination:** Log-normal cutoff method from example.py; applicability to UCI data needs verification.

## Blockers

- UCI dataset must be downloaded and verified before Track B can begin.
- 100/115-dim: not a blocker for UCI (KitNET n is dynamic), but affects comparability.
- Mirai PCAP baseline confirmed; UCI data still missing.

## Next Phase

`phase/01-experiment-setup` (after Phase 00 PR approved and merged)

## Recent Review Conclusion (PR #1)

- Repository storage policy approved
- Academic datasets corrected from BotIoT/CIC-IDS to UCI Kitsune
- Log sanitization rules refined to preserve experimental fidelity
- `.gitattributes` covers both `docs/` and `docx/` for LFS
- All verification tests (check-ignore, check-attr) passed
