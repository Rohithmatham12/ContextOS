# Contributing

## Setup

```bash
git clone https://github.com/Rohithmatham12/ContextOS
cd ContextOS
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
pip install -e ".[dev]"
```

Verify the setup:

```bash
pytest                           # all tests pass
ruff check contextos/ tests/     # zero warnings
```

## Running Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=contextos --cov-report=term-missing

# Single module
pytest tests/core/test_context_selector.py

# Single test
pytest tests/core/test_secret_detector.py::TestDetectOpenAIKey -v
```

Coverage gate: 80% minimum. PRs that drop coverage below this will not be merged.

## Linting and Formatting

```bash
# Check for lint errors
ruff check contextos/ tests/

# Auto-fix safe issues
ruff check --fix contextos/ tests/

# Format
ruff format contextos/ tests/

# Type check
mypy contextos/
```

All four must pass cleanly before opening a PR.

## Project Conventions

### Code Style

- Line limit: 100 characters (enforced by ruff)
- No comments explaining what the code does — well-named identifiers do that
- Comments only for non-obvious invariants, constraints, or workarounds
- No docstrings on internal helpers; public API only
- `pathlib.Path` everywhere — no `os.path`, no string concatenation for paths

### Optional Imports

All optional dependencies must be lazy-imported inside functions:

```python
# Correct
def count_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4

# Wrong — breaks installs without tiktoken
import tiktoken
```

This rule applies to: `tiktoken`, `headroom_ai`, `tree_sitter`.

### Determinism

ContextOS produces byte-identical output for identical inputs. Any change that breaks this is a regression. Use `sorted()` whenever iterating over directory contents.

### Secret Safety

Never add real credentials or API keys to fixtures, tests, or documentation. Use obviously fake values (e.g., `fake-api-key-for-testing`). For test patterns that need to match real token formats, construct them dynamically from parts — never as a single literal string that would trigger push protection.

```python
# Correct — dynamic construction
_XOXB = "xoxb-" + "1" * 12 + "-" + "1" * 12 + "-" + "a" * 24

# Wrong — literal token triggers GitHub push protection
_XOXB = "xoxb-<12digits>-<12digits>-<24chars>"  # don't write as a real-looking literal
```

### Fixture Repos

Fixture repos in `tests/fixtures/` are real directories with real files — not mocked. Keep them minimal. Never add synthetic data that looks like a real credential.

---

## Adding a Feature

### New Exporter

1. Create `contextos/exporters/<name>.py` subclassing the base pattern in `exporters/base.py`
2. Define `FILENAME`, `TOOL_NAME`, `USAGE_NOTE`, `_INSTRUCTIONS`
3. Register the tool name in `contextos/cli/commands/export.py`
4. Add tests in `tests/exporters/test_<name>.py`
5. Document in the README export table and `docs/USAGE.md`

### New Secret Pattern

1. Add the regex to `_CONTENT_PATTERNS` in `contextos/core/secret_detector.py`
2. Add a corresponding test class in `tests/core/test_secret_detector.py` following the existing pattern
3. Update the pattern table in `docs/SAFETY.md`

### New CLI Command

1. Create `contextos/cli/commands/<command>.py` with a Typer sub-app
2. Register in `contextos/cli/main.py`
3. Add tests in `tests/cli/test_<command>.py`
4. Document in `docs/USAGE.md` and README CLI reference

---

## Pull Request Process

1. Branch from `master`: `git checkout -b feature/<short-description>`
2. Write tests first (or alongside) — PRs without tests for new functionality will not be merged
3. All tests pass, all lint checks pass, coverage does not drop
4. PR title: short and specific (`Add Stripe pattern to secret detector`)
5. PR body: what changed and why — not a blow-by-blow of implementation details

Keep PRs focused. A PR that adds a feature and refactors unrelated code is harder to review and slower to merge. Split them.

---

## Reporting Bugs

Open an issue at https://github.com/Rohithmatham12/ContextOS/issues.

Include:
- ContextOS version (`contextos --version`)
- Python version (`python --version`)
- Operating system
- Minimal command that reproduces the issue
- Expected vs actual output

For secret detection issues: sanitize the example — replace the real credential with a fake one before posting.

---

## Non-Goals

To keep PRs in scope, here is what ContextOS deliberately does not do:

- No cloud storage or context sharing
- No executing repo code during analysis
- No LLM calls during context selection (by default)
- No embedding-based ranking (until v1.0, opt-in only)
- No telemetry or analytics
- No paid features

If your contribution requires a network call, an external service, or storing data outside `.contextos/`, it needs a very clear opt-in flag and thorough discussion before implementation.
