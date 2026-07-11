# AGENTS.md — Kitsune Reproduction Project

## Working Conventions
- Use `phase/*` branches for phase work, `chore/*` for cleanup
- Never commit to main directly; always use PR with review
- No `git push --force`, `git lfs migrate`, or history rewrite
- All experiments produce `manifest.json`, `config.json`, `metrics.json`
- Absolute paths, user names, host names, tokens never appear in docs

## Directory Roles
- `<GIT_ROOT>` = repo root (where `.gitignore` lives)
- `<SOURCE_ROOT>` = `Kitsune/Kitsune-py/` — official Kitsune source
- docs/ = Markdown process documents
- docx/ = (target) formal reports
- data/ = datasets (contents ignored except README)
- results/ = experiment outputs
- logs/ = sanitized logs in `sanitized/`; raw logs ignored

## Forbidden
- Modifying `example.py`, `Kitsune.py`, `FeatureExtractor.py`, `AfterImage.py`, `netStat.py`, `KitNET/*.py`
- Running full-scale experiments without approval
- Generating fictional parameters or results
