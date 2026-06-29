# ContextOS — Codex / OpenAI Agent Instructions

## Project Summary

ContextOS is a Python CLI tool that scans a code repository, builds repo intelligence, selects task-relevant content under a token budget, and exports context packs for AI coding agents (Claude Code, Codex, Cursor, Aider). It is deterministic, read-only, and requires no network access by default.

## Repository Layout

```
ContextOS/
├── contextos/               # main Python package
│   ├── __init__.py
│   ├── cli.py               # Typer CLI: scan, pack commands
│   ├── models.py            # FileNode, ChunkNode, ContextBundle, etc.
│   ├── scanner/             # file walking, language classification, file index
│   │   ├── classifier.py
│   │   ├── walker.py
│   │   └── index.py
│   ├── intelligence/        # chunking, token counting
│   │   ├── chunker.py
│   │   └── token_counter.py
│   ├── selector/            # ranking, budget enforcement, strategy
│   │   ├── ranker.py
│   │   ├── budget.py
│   │   └── strategy.py
│   ├── compressor/          # optional Headroom integration
│   │   └── headroom.py
│   └── exporter/            # output formatters
│       ├── base.py
│       ├── markdown.py
│       ├── xml.py
│       ├── claude.py
│       └── json_.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── simple_py/       # synthetic Python fixture repo
│   │   └── mixed/           # synthetic multi-language fixture repo
│   ├── scanner/
│   ├── intelligence/
│   ├── selector/
│   ├── exporter/
│   ├── cli/
│   └── integration/
├── docs/                    # setup documentation
├── ARCHITECTURE.md          # detailed design
├── TASKS.md                 # ordered implementation tasks
├── CLAUDE.md                # Claude Code agent instructions
└── CODEX.md                 # this file
```

## Key Constraints

1. **Read-only**: never write to the repo being scanned
2. **No network by default**: all network features behind explicit flags
3. **Deterministic**: same inputs → byte-identical output (use `--no-timestamp` for diffs)
4. **No optional imports at module level**: lazy-import tiktoken, tree-sitter, headroom

## Data Flow

```
repo_path → RepoWalker → [FileNode] → Chunker → [ChunkNode]
         → Ranker(task) → scored [ChunkNode]
         → BudgetEnforcer(budget) → ContextBundle
         → Exporter(format) → str
```

## Core Data Models (`contextos/models.py`)

```python
@dataclass
class FileNode:
    path: Path
    rel_path: Path
    language: str
    size_bytes: int
    lines: int
    content: str
    tokens: int

@dataclass
class ChunkNode:
    file: FileNode
    start_line: int
    end_line: int
    chunk_type: str    # "block" in MVP, "function"/"class" in v0.2
    name: str | None
    content: str
    tokens: int
    score: float       # 0.0 at creation, set by Ranker

@dataclass
class ContextBundle:
    task: str
    repo_root: Path
    chunks: list[ChunkNode]
    total_tokens: int
    budget: int
    strategy: str
    created_at: str    # ISO 8601; omit with --no-timestamp for determinism
```

## Implementing a Task

Consult `TASKS.md` for the ordered list. Each task maps to a specific file and function. Before writing code:

1. Read `ARCHITECTURE.md` for the component you are implementing
2. Check `tests/` for the corresponding test file — tests exist before implementation
3. Write the implementation to pass the tests
4. Run `pytest tests/<module>/` to verify
5. Run `pytest --cov=contextos --cov-fail-under=80` before marking done

## CLI Interface

```
contextos scan <repo>
    --max-files INT          # default 5000
    --out PATH               # write stats to file instead of stdout

contextos pack <repo>
    --task TEXT              # required: task description for relevance ranking
    --budget INT             # default 8000 tokens
    --format [md|xml|claude|codex|json]  # default: md
    --compress               # use Headroom proxy (must be running)
    --no-timestamp           # omit created_at for reproducible output
    --out PATH               # write to file; default stdout
    --strategy [default|deep-file|wide-repo]  # default: default
```

## Running Tests

```bash
# All tests
pytest

# Specific module
pytest tests/scanner/test_walker.py -v

# Coverage
pytest --cov=contextos --cov-report=term-missing

# Integration
pytest tests/integration/ -v
```

## Code Standards

- Python 3.11+, `from __future__ import annotations` in every file
- All paths via `pathlib.Path`; never `os.path`
- Sort file lists: `sorted(nodes, key=lambda n: n.rel_path.as_posix())`
- Type annotations on all function signatures
- `ruff` for lint and format (enforced in CI)
- `mypy --strict` (enforced in CI)

## What Not To Do

- Do not add `print()` inside library code — use Python `logging` with `logging.getLogger(__name__)`
- Do not call `subprocess` to analyze repo code
- Do not open files outside the declared `repo_root` during scanning
- Do not mutate a `ChunkNode` after creation
- Do not assume `tiktoken` is installed — always have the `len(text) // 4` fallback
- Do not hardcode file paths — use `pathlib.Path` and `repo_root` as the anchor

## Fixture Repos

`tests/fixtures/simple_py/` — use this for most unit tests. Known structure:
- `main.py` imports from `utils.py` and `models.py`
- `utils.py` has 2 functions (~30 lines each)
- `models.py` has 1 dataclass (~20 lines)
- `.gitignore` excludes `*.pyc`, `__pycache__/`

`tests/fixtures/mixed/` — use for scanner exclusion tests:
- Contains a binary file (`assets/logo.png`) — must be excluded
- Contains a `.gitignore` that excludes `assets/`
- Contains a JS file — tests multi-language handling
