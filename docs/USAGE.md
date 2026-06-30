# Usage Guide

## The Standard Workflow

```
init  →  scan  →  task  →  pack / export
```

Run `init` and `scan` once per project. Run `task` and `pack` for each new task.

---

## Step 1 — Initialize

```bash
cd my-project
contextos init
```

Creates `.contextos/` with template files. Safe to run repeatedly.

```
.contextos/
├── CURRENT_TASK.md     active task — edit freely
├── MEMORY.md           timestamped notes — append-only
├── DECISIONS.md        architectural decisions — append-only
└── PROJECT_INDEX.md    project overview — edit freely
```

Options:

```bash
contextos init --force          # overwrite all template files
contextos init --quiet          # suppress per-file output
contextos init ./other-project  # initialize a specific directory
```

---

## Step 2 — Scan

```bash
contextos scan
```

Walks the repo, identifies languages, extracts import relationships, writes the file index.

```bash
contextos scan ./my-project     # scan a specific path
contextos scan --no-index       # stats only, don't write output files
```

Re-run `scan` whenever you add or rename files. It overwrites `file_summaries.json` and `dependency_graph.json` but never touches `MEMORY.md`, `DECISIONS.md`, or `CURRENT_TASK.md`.

---

## Step 3 — Set a Task

```bash
contextos task "fix auth bug — token expiry not validated on refresh"
```

Words after `task` are joined automatically — quotes are optional for single-word tasks:

```bash
contextos task add rate limiting to the API
```

Sub-command form (supports `--status`):

```bash
contextos task set "refactor the auth layer" --status "Blocked"
```

Show the active task:

```bash
contextos task show
contextos task           # alias for show
```

Clear the task:

```bash
contextos task clear
```

The task is stored in `.contextos/CURRENT_TASK.md` as plain Markdown. Edit it freely to add acceptance criteria, notes, or links.

---

## Step 4 — Pack

```bash
contextos pack . --task "fix auth bug" --budget 8000
```

The `--task` flag overrides whatever is in `CURRENT_TASK.md` for relevance ranking. Omit it to use the file directly (not yet wired — use the flag).

### Common Patterns

**Tight budget (summaries only):**
```bash
contextos pack . --task "fix auth" --budget 4000 --no-source
```
Includes file summaries and metadata but no source code. Useful when you want an overview without filling the context window.

**Exclude test files:**
```bash
contextos pack . --task "fix bug" --budget 8000 --no-tests
```

**JSON output (for tooling):**
```bash
contextos pack . --task "fix auth" --budget 8000 --format json
```
Writes `.contextos/context_pack.json` with structured metadata.

**Save to a specific path:**
```bash
contextos pack . --task "task" --budget 8000 --out ./context.md
```
Still writes to `.contextos/context_pack.md`; also copies to `./context.md`.

**Reproducible output (no timestamp):**
```bash
contextos pack . --task "task" --budget 8000 --no-timestamp
```

**With Headroom compression:**
```bash
contextos pack . --task "fix auth" --budget 8000 --compress headroom
```
Requires `headroom-ai` installed and `headroom serve` running. See [`HEADROOM.md`](HEADROOM.md).

---

## Step 5 — Export for a Specific Tool

```bash
contextos export claude --repo . --task "fix auth bug"
```

Available exporters:

| Command | Output file | Notes |
|---------|-------------|-------|
| `export claude` | `CLAUDE_CONTEXT.md` | Includes Claude Code–specific instructions |
| `export codex`  | `CODEX_CONTEXT.md`  | Formatted for `AGENTS.md` convention |
| `export cursor` | `CURSOR_CONTEXT.md` | Hints for `.cursor/rules/` |
| `export aider`  | `AIDER_CONTEXT.md`  | Use with `aider --read` |

All exporters accept the same flags as `pack`.

### Loading into Claude Code

```bash
contextos export claude --repo . --task "fix auth bug"
# In a Claude Code session:
# /add .contextos/CLAUDE_CONTEXT.md
```

### Loading into Aider

```bash
contextos export aider --repo . --task "fix auth bug"
aider --read .contextos/AIDER_CONTEXT.md src/auth.py
```

---

## Memory and Decisions

### Persistent Notes

```bash
# Add a note
contextos memory add "bcrypt rounds set to 12 in production — do not lower"

# Update is an alias for add (both append)
contextos memory update "confirmed: rounds stay at 12 per security review"

# Show notes and decisions
contextos memory list
contextos memory list --no-decisions   # notes only
```

Entry format in `MEMORY.md`:

```markdown
- **2026-06-29T14:23:01+00:00** — bcrypt rounds set to 12 in production — do not lower
```

### Architectural Decisions

```bash
contextos memory decision "use JWTs over sessions — stateless for horizontal scaling"
contextos memory decision "adopt trunk-based development" --status proposed
```

Statuses: `accepted` (default), `proposed`, `superseded`, `rejected`.

Entry format in `DECISIONS.md`:

```markdown
---

### [2026-06-29] Decision

**Status:** accepted

**Decision:** use JWTs over sessions — stateless for horizontal scaling

**Logged:** 2026-06-29T14:23:01+00:00
```

### Rules

- Entries are append-only — never deleted or modified automatically.
- Notes containing embedded secrets are rejected (same detection engine as pack).
- Both files are included in context packs when relevant.

---

## Working with Example Projects

The `examples/` directory contains three pre-built repos you can run ContextOS against immediately:

```bash
cd examples/python_fastapi
contextos init
contextos scan
contextos task "fix auth bug — token expiry not validated"
contextos pack . --task "fix auth bug" --budget 8000
contextos export claude --task "fix auth bug"
```

See the [examples folder](https://github.com/Rohithmatham12/ContextOS/tree/master/examples) for walkthroughs of all three examples.

---

## Tips

**Re-scan after structural changes.** Adding files, renaming modules, or changing import structure warrants a fresh `scan`.

**Use `--no-source` for large repos.** If token budget is tight and you just need an overview, summaries often provide enough context for the agent to ask the right questions.

**Check what was excluded.** The "Excluded Files" section in the context pack shows what didn't fit. If a critical file was excluded, increase `--budget` or use `--no-source` to free space.

**`.contextos/` is yours to edit.** `PROJECT_INDEX.md` and `CURRENT_TASK.md` are plain Markdown. Add context ContextOS can't infer — team conventions, deployment notes, known constraints.

**Commit `.contextos/MEMORY.md` and `.contextos/DECISIONS.md`.** These files accumulate project knowledge over time. Sharing them with your team means agents have the same context everyone else does.

**Don't commit context packs.** `context_pack.md`, `CLAUDE_CONTEXT.md`, and similar files are generated artifacts. Add them to `.gitignore`:

```
.contextos/context_pack.*
.contextos/*_CONTEXT.md
```
