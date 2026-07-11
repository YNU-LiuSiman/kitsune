# Logs Directory

This directory stores experiment execution logs.

**Policy:**
- `logs/sanitized/` — Redacted logs suitable for Git (regular Git, committed)
- `logs/raw/` — Unprocessed logs with potential PII (ignored via .gitignore)
- Root of `logs/` — Not committed directly (only README.md and .gitkeep)

## Log Sanitization

Before committing logs, ensure:

- [ ] Replace absolute paths with `<REPO_ROOT>` or `<USER_HOME>`
- [ ] Remove or mask user names
- [ ] Remove or mask IP addresses and host names
- [ ] Remove API keys, tokens, and passwords
- [ ] Preserve all experiment-relevant output intact
