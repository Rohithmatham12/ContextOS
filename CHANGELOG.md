# Changelog

All notable changes to ContextOS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-29

### Added

- Initial ContextOS CLI with `init`, `scan`, `task`, `memory`, `pack`, and `export` commands.
- Deterministic repository scanning, summarization, dependency graphing, and task-aware context selection.
- Context pack rendering for Markdown/JSON plus Claude Code, Codex, Cursor, and Aider exporters.
- Secret filename exclusion and content redaction, with explicit `--allow-sensitive` override.
- Optional Headroom compression provider integration.
- Project memory and decision-log helpers under `.contextos/`.
- CI, release documentation, community health files, and issue/PR templates.

### Hardened

- Exclude generated `.contextos/` outputs from future scans.
- Enforce `scan --max-files` in written scan output.
- Skip notebooks and minified generated assets by default.
- Recover from corrupted `.contextos` scan data during pack generation.
- Normalize internal scan paths for cross-platform stability.

### Verified

- `pytest`: 907 passed, 1 skipped.
- `ruff check .`: passing.
- `mypy .`: passing.
- Local wheel build, install, and installed CLI smoke test.
