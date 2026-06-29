# Safety Model

## Guarantees

### Read-only Source Files

ContextOS opens source files in read mode only. It never modifies, deletes, or moves any file in your repository. All writes go to `.contextos/` within the repository root, or to explicit `--out` paths you specify.

If ContextOS crashes mid-run, no source file is left in a partial state.

### No Network by Default

ContextOS makes zero network calls during normal operation (`init`, `scan`, `task`, `pack`, `export`, `memory`). The only exception is `--compress headroom`, which sends text to a locally running proxy (`http://127.0.0.1:8787` by default). Even then, no data leaves your machine unless you configure the proxy to forward externally.

### No LLM Calls

Context selection is entirely static analysis — keyword matching, import graph centrality, and file metadata. No AI model is called to select, summarize, or rank files.

### No Telemetry

ContextOS collects no analytics, crash reports, or usage data. It has no account system.

---

## Secret Redaction

Before any content appears in a context pack, ContextOS scans it with a 14-pattern regex engine. Detected secrets are replaced with `[REDACTED_*]` placeholders before the file is token-counted, before the pack is rendered, and before it is written to disk.

### Detected Patterns

| Pattern name | Triggers on | Redacted as |
|---|---|---|
| `openai_key` | `sk-` followed by 20+ alphanumeric chars | `[REDACTED_OPENAI_KEY]` |
| `anthropic_key` | `sk-ant-` followed by 20+ chars | `[REDACTED_ANTHROPIC_KEY]` |
| `aws_key_id` | `AKIA` followed by 16 chars | `[REDACTED_AWS_KEY_ID]` |
| `aws_secret` | `aws_secret_access_key = ...` | `[REDACTED_AWS_SECRET]` |
| `github_token` | `ghp_`, `gho_`, `ghu_`, `ghs_` prefixes | `[REDACTED_GITHUB_TOKEN]` |
| `github_fine_grained` | `github_pat_` prefix | `[REDACTED_GITHUB_TOKEN]` |
| `jwt` | `eyJ` base64 header pattern | `[REDACTED_JWT]` |
| `pem_key` | `-----BEGIN ... PRIVATE KEY-----` | `[REDACTED_PRIVATE_KEY]` |
| `slack_token` | `xoxb-`, `xoxp-`, `xoxa-` prefixes | `[REDACTED_SLACK_TOKEN]` |
| `stripe_secret` | `sk_live_`, `rk_live_` prefixes | `[REDACTED_STRIPE_SECRET]` |
| `db_url_with_password` | `postgresql://user:pass@...` | `[REDACTED_DB_PASSWORD]` |
| `bearer_token` | `Authorization: Bearer <token>` | `[REDACTED_BEARER_TOKEN]` |
| `env_secret_assignment` | `PASSWORD=value`, `API_KEY=value` | `[REDACTED_SECRET]` |
| `generic_high_entropy` | Long high-entropy strings in sensitive variable names | `[REDACTED_SECRET]` |

### Important Notes on `env_secret_assignment`

This pattern uses `=` only (not `:`), specifically to avoid false positives on Python type annotations like `password: str`. It matches `VARIABLE_NAME=literal_value` forms in configuration files.

### Redaction Scope

Redaction is value-only for `key=value` patterns. The variable name is preserved:

```
Before: DATABASE_PASSWORD=supersecretvalue123
After:  DATABASE_PASSWORD=[REDACTED_SECRET]
```

This ensures the agent still understands the config structure without seeing the credential.

---

## Filename-Based Exclusion

Certain filenames are excluded from context packs entirely — they are never opened, read, or included even in summary form:

**Excluded filenames (exact match):**
- `.env`, `.env.local`, `.env.production`, `.env.staging`, `.env.development`
- `id_rsa`, `id_ed25519`, `id_ecdsa`, `id_dsa`

**Excluded glob patterns:**
- `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.crt`, `*.cer`
- `credentials.json`, `credentials.yml`, `credentials.yaml`
- `secrets.json`, `secrets.yml`, `secrets.yaml`
- `passwords.txt`, `passwords.json`
- `service_account*.json`

**Safe files (always included if not over budget):**
- `.env.example`, `.env.sample`, `.env.template`, `.env.dist`

---

## Secret Warnings

When redaction occurs, ContextOS emits a warning line for each redacted occurrence:

```
⚠ Redacted secret in app/config.py:14 [openai_key] — sk-XXXXX...XXXXX
```

The snippet shown in the warning is truncated. The full value is never logged.

Warnings appear:
- In the CLI output during `pack` and `export`
- In a "Security Warnings" section at the top of the context pack

---

## `--allow-sensitive` Flag

**This flag disables all secret redaction.** Use it only when:
- You are intentionally reviewing your own credential storage
- You have verified the output goes nowhere except your local terminal
- You accept the risk of the context pack containing live credentials

When `--allow-sensitive` is passed:
- Content pattern scanning is skipped
- Filename exclusions are skipped
- No warnings are emitted
- The rendered pack contains raw content

The flag propagates through the full pipeline: CLI → PackConfig/ExportConfig → SelectionConfig → `_enforce_budget()`.

---

## Memory Safety

`contextos memory add` rejects notes that contain embedded secrets:

```bash
contextos memory add "use TOKEN=sk-abcdef to authenticate"
# Error: secret detected in memory note (openai_key). Remove the credential and try again.
```

This prevents accidentally persisting credentials in `MEMORY.md`, which is a committed file.

---

## Audit Trail

The rendered context pack always includes a "Security Warnings" section listing all redactions that occurred, with file path and line number. This makes it easy to verify what was sanitized before sharing the pack with an AI agent.

---

## Reporting Issues

If you believe ContextOS is leaking secrets that should be redacted, please open an issue at:
https://github.com/Rohithmatham12/ContextOS/issues

Include:
- The pattern that should have been detected
- A sanitized example (replace the real credential with a fake one)
- The ContextOS version (`contextos --version`)
