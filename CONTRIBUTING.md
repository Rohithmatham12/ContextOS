# Contributing to ContextOS

Thanks for helping improve ContextOS. Keep contributions focused, tested, and
easy to review.

## Development Setup

```bash
git clone https://github.com/Rohithmatham12/ContextOS
cd ContextOS
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Checks

Run these before opening a pull request:

```bash
pytest
ruff check .
mypy .
```

The CI workflow also runs Ruff format checks:

```bash
ruff format --check contextos/ tests/
```

## Pull Request Guidelines

- Keep changes scoped to one bug fix, hardening improvement, or documentation update.
- Add or update tests for behavior changes.
- Do not add network behavior unless it is explicit, documented, and opt-in.
- Do not weaken secret redaction or filesystem safety checks.
- Update `CHANGELOG.md` for user-visible changes.

## Release Notes

ContextOS follows semantic versioning. For pre-1.0 releases, minor versions may
still include breaking changes, but they should be documented clearly.
