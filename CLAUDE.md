# ContextOS — Claude Code Instructions

## Project

ContextOS is a context operating system for AI coding agents. It scans repos, builds intelligence, selects context under a token budget, and exports context packs. Python 3.11+, Typer CLI, pytest.

## Working Directory

All source lives in `/Users/rohithmatam/ContextOS/`. The main package is `contextos/`.

## Architecture (read ARCHITECTURE.md first)

Pipeline: `Scanner → Intelligence → Selector → Compressor → Exporter`

Key files:
- `contextos/models.py` — all data models (`FileNode`, `ChunkNode`, `ContextBundle`, etc.)
- `contextos/cli.py` — Typer app; `scan` and `pack` commands
- `contextos/scanner/` — file walking, classification, indexing
- `contextos/intelligence/` — chunking, token counting
- `contextos/selector/` — ranking, budget enforcement
- `contextos/exporter/` — output formatters (md, xml, claude, json)

## Development Rules

**Never modify the source repo under analysis.** ContextOS is read-only with respect to any repo it scans.

**No network calls by default.** All new features requiring network must be gated behind an explicit flag.

**Determinism is a hard requirement.** Any change that breaks byte-identical output on identical input is a regression. Run `test_determinism.py` before every commit.

**No optional imports at module level.** Use lazy imports inside functions for `tiktoken`, `tree_sitter`, `headroom_ai`. Always have a fallback.

```python
# Correct:
def count_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4

# Wrong:
import tiktoken  # top-level optional import — breaks installs without tiktoken
```

**Use `pathlib.Path` exclusively.** No `os.path`, no string concatenation for paths.

**Chunk boundaries are immutable.** Once a `ChunkNode` is created, its `start_line` and `end_line` do not change.

## Current Task Priority

See `TASKS.md`. Work in phase order: Phase 0 → Phase 1 → Phase 2 → etc. Do not start a phase until all tasks in the previous phase have passing tests.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=contextos --cov-report=term-missing

# Run only a module
pytest tests/scanner/

# Run determinism test
pytest tests/integration/test_determinism.py -v
```

Coverage gate: 80% minimum. Do not merge code that drops coverage below this.

## Code Style

- `ruff check contextos/ tests/` — zero warnings allowed
- `ruff format contextos/ tests/` — enforced
- `mypy --strict contextos/` — no type errors allowed
- Docstrings on all public functions and classes
- No comments explaining *what* the code does; comments only for non-obvious *why*

## Adding a New Exporter

1. Create `contextos/exporter/<name>.py` with a class subclassing `BaseExporter`
2. Implement `render(bundle: ContextBundle) -> str` and `filename() -> str`
3. Register in `cli.py` format dispatch table
4. Add tests in `tests/exporter/test_<name>.py`
5. Document in `ARCHITECTURE.md` exporter table and `README.md` output formats table

## Common Pitfalls

- **Sort before iterating files.** `path.rglob()` order is OS-dependent. Always `sorted(...)`.
- **Overlapping chunks inflate token counts.** `ContextBundle.total_tokens` is the sum of selected chunk tokens, which may exceed the actual unique content tokens due to overlap. Document this.
- **Empty task string is valid.** `Ranker.rank(chunks, task="")` must not crash; it returns all chunks with equal score 0.0.
- **Budget of 0 returns empty selection.** Not an error. `[]` with `total_tokens=0`.

## Fixtures

Fixture repos live in `tests/fixtures/`. They are real directories with real files — not mocked. Never add actual secrets, real API keys, or non-synthetic data to fixtures.

## Git Workflow

- Branch: `feature/<task-id>-<short-description>` (e.g., `feature/T-011-repo-walker`)
- Commit after each passing task, not after each file edit
- PR title: `[T-XXX] Short description`
- Do not push directly to `main`
