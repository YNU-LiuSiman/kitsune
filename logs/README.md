# Logs Directory

This directory stores experiment execution logs.

**Policy:**
- `logs/sanitized/` — Redacted logs suitable for Git (regular Git, committed)
- `logs/raw/` — Unprocessed logs with potential PII (ignored via `.gitignore`)
- Root of `logs/` — Not committed directly (only README.md and .gitkeep)

## Log Sanitization Rules

### Must Redact (Remove or Mask)

- [ ] Local user names and account names
- [ ] Absolute local file system paths (replace with `<REPO_ROOT>`)
- [ ] Host names of local machines
- [ ] Account credentials, API tokens, keys, and passwords
- [ ] Personal information unrelated to the experiment
- [ ] Unnecessary real private network addresses

### Must Preserve (Keep Unchanged)

- [ ] Packet sequence numbers and ordering
- [ ] Attack start positions and timestamps
- [ ] Experiment start and end times
- [ ] Elapsed durations and performance metrics
- [ ] Public dataset IP addresses and network fields where relevant
- [ ] Model phase transition information (training, detection, inference)
- [ ] All experiment parameters required for reproducibility
- [ ] Public dataset identifiers and metadata

### Network Address Sanitization

If private network identifiers must be masked, use stable consistent
mappings (e.g., `<HOST_A>`, `<HOST_B>`) throughout the same log file
to preserve relational integrity.
