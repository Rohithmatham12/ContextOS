# ContextOS Architecture

## Overview

ContextOS is a pipeline: a repository enters one end, a context pack exits the other. Each stage is a pure transformation — no side effects, no network, no mutation of the source repo.

```
repo path
    │
    ▼
┌──────────┐
│  Scanner │  walks files, respects .gitignore, classifies by language
└──────────┘
    │ FileIndex
    ▼
┌─────────────┐
│ Intelligence│  extracts symbols, imports, call edges → RepoGraph
└─────────────┘
    │ RepoGraph
    ▼
┌──────────┐
│ Selector │  takes task + budget → ranks and clips chunks
└──────────┘
    │ ContextBundle
    ▼
┌────────────┐
│ Compressor │  optional Headroom pass — shrinks tokens further
└────────────┘
    │ CompressedBundle
    ▼
┌──────────┐
│ Exporter │  formats for target agent
└──────────┘
    │
    ▼
context pack (file on disk)
```

## Data Models (`models.py`)

```python
@dataclass
class FileNode:
    path: Path           # absolute path
    rel_path: Path       # relative to repo root
    language: str        # "python", "typescript", etc.
    size_bytes: int
    lines: int
    content: str
    tokens: int          # estimated at scan time

@dataclass
class ChunkNode:
    file: FileNode
    start_line: int
    end_line: int
    chunk_type: str      # "function", "class", "module", "block"
    name: str | None     # symbol name if extractable
    content: str
    tokens: int
    score: float         # set by Selector; 0.0 at creation

@dataclass
class RepoGraph:
    files: list[FileNode]
    chunks: list[ChunkNode]
    imports: dict[Path, list[Path]]    # file → files it imports
    symbols: dict[str, list[ChunkNode]] # symbol name → defining chunks
    call_edges: list[tuple[str, str]]  # (caller_symbol, callee_symbol)

@dataclass
class ContextBundle:
    task: str
    repo_root: Path
    chunks: list[ChunkNode]           # selected, ordered
    total_tokens: int
    budget: int
    strategy: str
    created_at: str                   # ISO 8601, deterministic

@dataclass
class CompressedBundle:
    bundle: ContextBundle
    compressed_content: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
```

## Module Breakdown

### `scanner/`

**`walker.py`** — `RepoWalker`
- Walks a directory tree using `pathlib.Path.rglob`
- Reads `.gitignore` via `gitignore-parser` (or built-in simple parser)
- Skips: binary files, files over a size limit (default 512 KB), lock files, build artifacts
- Returns an ordered list of `FileNode` (ordered by `rel_path` for determinism)

**`classifier.py`** — `LanguageClassifier`
- Maps file extensions to language names
- Detects shebangs for extensionless scripts
- Returns language string or `"unknown"`

**`index.py`** — `FileIndex`
- Thin wrapper over `list[FileNode]`
- Provides lookup by path, by language, by glob pattern
- Computes aggregate stats (total files, total tokens, language breakdown)

### `intelligence/`

**`chunker.py`** — `Chunker`
- Splits files into `ChunkNode` objects
- Two modes:
  - **AST mode** (tree-sitter, optional): function/class/method-level chunks
  - **Line mode** (default): fixed-size overlapping windows (e.g. 50 lines, 10-line overlap)
- Chunk size is bounded: minimum 5 lines, maximum 200 lines
- Always produces at least one chunk per file (the whole file if small)

**`extractor.py`** — `SymbolExtractor`
- Runs in AST mode only
- Extracts: function names, class names, import statements, exported symbols
- Falls back to regex-based extraction for unsupported languages

**`graph.py`** — `GraphBuilder`
- Builds `RepoGraph` from `FileIndex` + extracted symbols
- Import resolution: converts `from foo.bar import baz` → `Path` edges
- Does not execute code; static analysis only
- Cycle detection: records import cycles as metadata, does not fail on them

### `selector/`

**`ranker.py`** — `Ranker`
- Assigns a relevance score to each `ChunkNode` given a task string
- Scoring is additive; no single signal dominates:

| Signal | Weight | Description |
|--------|--------|-------------|
| Keyword overlap | 0.40 | Task tokens that appear in chunk content |
| Symbol match | 0.25 | Task tokens matching extracted symbol names |
| Import centrality | 0.20 | Files imported by many others score higher |
| Recency proxy | 0.15 | Files modified recently score slightly higher |

- Scores are normalized to [0.0, 1.0]
- Scoring is purely local: no embeddings, no LLM calls

**`budget.py`** — `BudgetEnforcer`
- Takes ranked `ChunkNode` list and a token budget
- Greedy selection: add highest-scoring chunks until budget is exhausted
- Two modes:
  - `greedy`: pure score-descending fill
  - `balanced`: ensures at least one chunk from each file that appears in the top N

**`strategy.py`** — `SelectionStrategy`
- Named presets that combine Ranker weights + BudgetEnforcer mode
- Built-in: `default`, `deep-file` (fewer files, deeper), `wide-repo` (more files, shallower)
- Custom strategies via TOML config

### `compressor/`

**`headroom.py`** — `HeadroomCompressor`
- Optional; only active when `headroom-ai` is installed and proxy is reachable
- Sends `ContextBundle` content to local Headroom proxy at `http://127.0.0.1:8787`
- Returns `CompressedBundle` with compressed text and token delta
- Fails gracefully: if proxy is unreachable, returns original bundle unchanged
- No data leaves the machine; proxy is local

### `exporter/`

Each exporter takes a `ContextBundle | CompressedBundle` and returns a `str`.

**`base.py`** — `BaseExporter` (abstract)
- `render(bundle) -> str`
- `filename() -> str`

**`markdown.py`** — renders as fenced code blocks with file headers

**`xml.py`** — renders as `<file path="...">` XML tags (Claude-style)

**`claude.py`** — XML blocks + a task preamble formatted for Claude Code's system prompt

**`codex.py`** — plain text blocks formatted for `AGENTS.md` injection

**`cursor.py`** — splits into `.cursorrules` (repo summary) + `context.md` (file blocks)

**`aider.py`** — tab-separated file list + content blocks for Aider's `--read` input

**`json_.py`** — machine-readable JSON: metadata + chunks as structured objects

### `cli.py`

Built with Typer. Three top-level commands:

```
contextos scan   <repo>                          # index and summarize
contextos pack   <repo> --task --budget --format # select and export
contextos graph  <repo>                          # print import graph (optional)
```

All commands are read-only on the source repo. Output goes to stdout or `--out <path>`.

## Token Counting

Token counting uses a priority chain:

1. `tiktoken` with the model's actual tokenizer (if installed and model known)
2. `tiktoken` with `cl100k_base` as a universal approximation
3. `len(content) // 4` as a last-resort fallback

The counting method is reported in bundle metadata so consumers know which approximation was used.

## Determinism Contract

Given identical inputs (repo state, task string, budget, strategy), ContextOS always produces byte-for-byte identical output. This is guaranteed by:

- File iteration order: `sorted(path.rglob(...))` — lexicographic, OS-independent
- Chunk ordering: deterministic by `(file.rel_path, start_line)`
- Score tie-breaking: ties broken by `(rel_path, start_line)` not by dict insertion order
- Timestamps: `created_at` in output can be suppressed with `--no-timestamp` for reproducible diffs

## Extension Points

| Extension | Mechanism |
|-----------|-----------|
| New language chunker | Register in `chunker.py` dispatch table |
| New ranking signal | Add signal function to `ranker.py`, assign weight |
| New exporter | Subclass `BaseExporter`, register in `cli.py` |
| Custom selection strategy | TOML config file, loaded by `strategy.py` |
| Alternative compressor | Implement `Compressor` protocol in `compressor/` |

## Security Model

- **Read-only**: ContextOS never writes to the source repo
- **No execution**: no `eval`, no subprocess of repo code, no dynamic imports from repo
- **No network by default**: all network features gated behind explicit flags
- **Path traversal**: all paths validated to stay within the declared repo root
- **Output only to declared destinations**: `--out` flag or stdout; no implicit file writes

## Dependencies

### Required
- `typer` — CLI
- `pathlib` (stdlib) — path handling
- `dataclasses` (stdlib) — models
- `tomllib` (stdlib, Python 3.11+) — config parsing

### Optional
- `tiktoken` — accurate token counting
- `tree-sitter` + language grammars — AST chunking
- `gitignore-parser` — full `.gitignore` spec support
- `headroom-ai` — compression

### Dev only
- `pytest` — tests
- `pytest-cov` — coverage
- `ruff` — lint + format
- `mypy` — type checking
