# ContextOS Examples

Three realistic example projects showing how to use ContextOS in different
repo types.

| Example | Stack | Scenario |
|---------|-------|----------|
| `python_fastapi/` | Python · FastAPI · SQLAlchemy | REST API with JWT auth |
| `react_typescript/` | React · TypeScript · Vite | SPA with auth + item CRUD |
| `monorepo/` | Node · Express · React · Turbo | Multi-package workspace |

---

## Workflow

Run these commands from the root of any example directory.

### 1. Initialize

```bash
contextos init
```

Creates `.contextos/` with template files:

```
.contextos/
├── CURRENT_TASK.md    # active task description
├── MEMORY.md          # persistent notes
└── DECISIONS.md       # architecture decisions log
```

### 2. Scan

```bash
contextos scan
```

Walks the repo, builds a file index and dependency graph, and writes:

```
.contextos/
├── file_summaries.json       # per-file summaries and token estimates
├── dependency_graph.json     # import relationships
└── PROJECT_INDEX.md          # human-readable project overview
```

### 3. Set the current task

```bash
contextos task "fix auth bug"
```

Writes `.contextos/CURRENT_TASK.md`. Used by `pack` to rank relevant files.
View the active task:

```bash
contextos task show
```

### 4. Pack context

```bash
contextos pack --budget 8000
```

Selects files most relevant to the current task within the token budget and
writes `.contextos/context_pack.md`. Options:

```bash
# JSON output
contextos pack --budget 8000 --format json

# Summaries only (no source code embedded)
contextos pack --budget 4000 --no-source

# Exclude test files
contextos pack --budget 8000 --no-tests

# Headroom compression (proxy must be running)
contextos pack --budget 8000 --compress headroom
```

### 5. Export for a specific tool

```bash
contextos export claude
contextos export codex
contextos export cursor
contextos export aider
```

Each command writes a tool-specific context file to `.contextos/`:

| Command | Output file |
|---------|-------------|
| `export claude` | `CLAUDE_CONTEXT.md` |
| `export codex` | `CODEX_CONTEXT.md` |
| `export cursor` | `CURSOR_CONTEXT.md` |
| `export aider` | `AIDER_CONTEXT.md` |

Load in Claude Code:

```bash
# In a Claude Code session
/add .contextos/CLAUDE_CONTEXT.md
```

---

## Example: fixing an auth bug in the FastAPI project

```bash
cd examples/python_fastapi

# Initialize and scan
contextos init
contextos scan

# Set task
contextos task "fix auth bug — token expiry not checked correctly in get_current_user"

# Pack with generous budget (auth code is small)
contextos pack --budget 6000

# Export for Claude Code
contextos export claude --task "fix auth bug — token expiry not checked correctly"

# Now open Claude Code and load the context
# /add .contextos/CLAUDE_CONTEXT.md
```

The exported pack will include `app/auth.py`, `app/routes/users.py`, and
`app/models.py` ranked by relevance — exactly the files needed to diagnose
the bug.

---

## Example: adding a feature to the monorepo

```bash
cd examples/monorepo

contextos init
contextos scan
contextos task "add project archiving — soft-delete with archived_at timestamp"
contextos pack --budget 12000 --no-tests
contextos export cursor --task "add project archiving"
```

The context pack will surface `packages/api/src/routes.ts`,
`packages/shared/src/types.ts`, and `packages/shared/src/validators.ts` —
the files that need to change.

---

## Memory and decisions

Record persistent notes that survive across sessions:

```bash
contextos memory add "bcrypt rounds set to 12 for prod — do not lower"
contextos memory decision "use JWT over sessions — stateless for horizontal scaling"
contextos memory list
```

---

## Tips

- Run `contextos scan` again whenever you add or remove files.
- `pack --no-source` is useful when you want summaries only (smaller output, faster to load).
- `--budget` is in approximate tokens. 8000 ≈ 6 KB of source code.
- Secrets are automatically redacted from context packs. Use `--allow-sensitive` only in fully isolated environments.
