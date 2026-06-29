# Architecture

## Overview

ContextOS is a pipeline. A repository path enters one end; a context pack exits the other. Each stage is a pure transformation — no side effects, no network calls, no mutation of the source repo.

```
repo path
    │
    ▼
┌──────────┐
│  Scanner │  walks files, respects .gitignore, classifies by language
└──────────┘
    │ list[FileResult]
    ▼
┌─────────────────┐
│ Summarizer      │  per-file metadata: language, size, token estimate
└─────────────────┘
    │ file_summaries.json
    ▼
┌──────────────────┐
│ DependencyGraph  │  static import analysis → edges between files
└──────────────────┘
    │ dependency_graph.json
    ▼
┌──────────────────┐
│ ContextSelector  │  task + budget → ranked FileResult list
└──────────────────┘
    │ ContextSelection
    ▼
┌──────────────────┐
│ SecretDetector   │  scan content → redact [REDACTED_*] tokens
└──────────────────┘
    │ redacted ContextSelection
    ▼
┌──────────────────┐
│ PackBuilder      │  render Markdown or JSON context pack
└──────────────────┘
    │ rendered string
    ▼
┌─────────────────────┐
│ Compression (opt.)  │  Headroom proxy → compressed string
└─────────────────────┘
    │
    ▼
context pack (file on disk)
```

---

## Package Layout

```
contextos/
├── cli/
│   ├── main.py                 Typer app; registers sub-commands
│   └── commands/
│       ├── init.py             contextos init
│       ├── scan.py             contextos scan
│       ├── task.py             contextos task
│       ├── pack.py             contextos pack
│       ├── export.py           contextos export {claude,codex,cursor,aider}
│       └── memory.py           contextos memory {add,decision,list,compact}
│
├── core/
│   ├── scanner.py              File walking, binary detection, language classification
│   ├── summarizer.py           Per-file summaries → file_summaries.json
│   ├── dependency_graph.py     Import edge extraction → dependency_graph.json
│   ├── context_selector.py     Relevance ranking + budget enforcement
│   ├── pack_builder.py         Markdown/JSON rendering + disk write
│   ├── secret_detector.py      14-pattern regex engine for secret redaction
│   ├── compression.py          CompressionProvider ABC + factory
│   ├── headroom_adapter.py     HeadroomCompressionProvider (lazy import)
│   ├── initializer.py          .contextos/ directory setup
│   ├── repo_index.py           PROJECT_INDEX.md generation
│   ├── safety.py               Read-only enforcement utilities
│   └── token_counter.py        tiktoken with regex fallback
│
└── exporters/
    ├── base.py                 build_export() pipeline + render_context()
    ├── claude.py               CLAUDE_CONTEXT.md
    ├── codex.py                CODEX_CONTEXT.md
    ├── cursor.py               CURSOR_CONTEXT.md
    └── aider.py                AIDER_CONTEXT.md
```

---

## Key Data Models

### `FileResult` (context_selector.py)

```python
@dataclass
class FileResult:
    rel_path: str       # relative path from repo root
    kind: str           # "full" | "summary"
    content: str        # file content or summary text
    score: float        # relevance score 0.0–1.0
    tokens: int         # estimated token count
    reasons: list[str]  # why this file was selected
```

### `ContextSelection` (context_selector.py)

```python
@dataclass
class ContextSelection:
    selected: list[FileResult]   # files within budget, ranked by score
    excluded: list[str]          # rel_paths that didn't fit
    budget: int                  # token budget passed in
    used_tokens: int             # actual tokens used
    secret_warnings: list[str]   # "path:line [secret:pattern] snippet"
```

### `SelectionConfig` (context_selector.py)

```python
@dataclass
class SelectionConfig:
    budget: int = 8000
    no_source: bool = False       # summaries only
    allow_sensitive: bool = False # skip secret redaction
```

### `PackConfig` (pack_builder.py)

```python
@dataclass
class PackConfig:
    budget: int = 8000
    include_tests: bool = True
    no_source: bool = False
    fmt: str = "md"               # "md" | "json"
    add_timestamp: bool = True
    allow_sensitive: bool = False
    compress: str | None = None   # "headroom" | None
```

### `ExportConfig` (exporters/base.py)

```python
@dataclass
class ExportConfig:
    budget: int = 8000
    include_tests: bool = True
    no_source: bool = False
    add_timestamp: bool = True
    allow_sensitive: bool = False
```

---

## Context Selection

`_select()` in `context_selector.py` implements a two-pass algorithm:

**Pass 1 — Scoring.** Each file receives a relevance score combining:
- Keyword overlap between task description and file path/summary
- Import graph centrality (files imported by many others score higher)
- Recency signal (files mentioned in `CURRENT_TASK.md` or `MEMORY.md`)

**Pass 2 — Budget enforcement.** `_enforce_budget()` greedily fills the budget:
1. Try embedding the full file content. If it fits, add it as `kind="full"`.
2. If it doesn't fit, try embedding just the summary. If that fits, add it as `kind="summary"`.
3. If even the summary doesn't fit, exclude the file.

Secret redaction happens inside `_enforce_budget()` — content is scanned and redacted before token counting, so the budget reflects the redacted size.

---

## Secret Detection

`secret_detector.py` implements 14 regex patterns covering:

| Category | Patterns |
|----------|----------|
| AI keys | OpenAI (`sk-`), Anthropic (`sk-ant-`) |
| Cloud | AWS access key ID (`AKIA...`), AWS secret key |
| VCS | GitHub classic PATs (`ghp_`, `gho_`, `ghu_`, `ghs_`), fine-grained (`github_pat_`) |
| Auth | JWTs (`eyJ...`), PEM private keys, Bearer tokens |
| Services | Slack (`xoxb-`), Stripe live/restricted keys |
| Config | Database URLs with passwords, env-style `KEY=value` assignments |

**Filename exclusion** runs before content scanning. Files matching `.env`, `id_rsa`, `*.pem`, `credentials.*`, `passwords.*`, etc. are excluded from context packs entirely. `.env.example` and `.env.sample` are explicitly safe.

**Value-preserving redaction** for `key=value` patterns: only the value is replaced, so `DATABASE_PASSWORD=[REDACTED_SECRET]` preserves the variable name.

---

## Compression

The `CompressionProvider` ABC defines a single method:

```python
def compress(self, text: str, *, budget: int) -> str: ...
```

`NoOpCompressionProvider` returns text unchanged (default).

`HeadroomCompressionProvider` lazy-imports `headroom_ai` and delegates to the local proxy at `http://127.0.0.1:8787` (or `HEADROOM_BASE_URL`). If the package is missing or the proxy is unreachable, it raises `HeadroomUnavailableError` with setup instructions.

Compression runs after rendering — the full rendered Markdown is compressed, then written to disk.

---

## Exporter Pipeline

All four exporters (`claude`, `codex`, `cursor`, `aider`) share the same pipeline via `build_export()` in `exporters/base.py`:

```
_ensure_scan() → _load_summaries_safe() → _select() → _load_text_safe() → render() → write()
```

Each exporter provides:
- `FILENAME` — output filename (e.g. `CLAUDE_CONTEXT.md`)
- `TOOL_NAME` — display name
- `USAGE_NOTE` — how to load the file in the target tool
- `_INSTRUCTIONS` — tool-specific agent instructions appended to the pack
- `render()` — thin wrapper around `render_context()` from `base.py`

---

## Design Constraints

**Determinism.** Same inputs → same output. File ordering is always sorted. Scores are deterministic given the same task string. No random seeds, no timestamps in selection logic.

**No optional imports at module level.** `tiktoken`, `headroom_ai` are lazy-imported inside functions with graceful fallbacks. A missing optional dependency never prevents ContextOS from running.

**Read-only.** ContextOS never writes outside `.contextos/` directories. Source files are opened in read mode only.

**No LLM calls by default.** All analysis is static. The compression step (Headroom) is explicitly opt-in and still uses a local model — no external API calls.
