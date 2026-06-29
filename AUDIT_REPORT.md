# ContextOS Maintainer Audit Report

Date: 2026-06-29

Scope: strict open-source maintainer review of the Python package, Typer CLI, scanner,
context pack builder, secret redaction, tests, packaging metadata, and README.

## Executive Summary

ContextOS is small, well-tested, and generally conservative about filesystem access. The
main high-priority issue found during this audit was that the repository advertises a
strict mypy configuration, but `mypy .` did not pass. That is a release/CI quality gate
failure, especially for a typed CLI package with dynamic exporter and compression
boundaries.

I fixed only that high-priority issue. Lower-priority documentation and packaging gaps
are recorded below but intentionally left unfixed.

## High-Priority Findings Fixed

### HP-1: Configured mypy check failed

Severity: High

Area: typing, CI/release confidence, dynamic plugin boundaries

Evidence:

- `pyproject.toml` enables `[tool.mypy] strict = true`.
- Baseline `mypy .` failed with 27 errors across source and tests.
- Source-level failures included untyped dynamic provider/exporter calls:
  - `contextos/core/compression.py`
  - `contextos/core/headroom_adapter.py`
  - `contextos/cli/commands/export.py`
  - `contextos/core/secret_detector.py`

Impact:

- Contributors cannot run the configured quality gate successfully.
- Dynamic compression/exporter boundaries were opaque to mypy, which weakens confidence
  in CLI code paths that are meant to be extensible.

Fix:

- Added narrow protocols/casts around dynamic exporter and Headroom imports.
- Removed a dead helper in secret redaction.
- Tightened test fixture/type annotations and corrected test imports that referenced a
  helper through the wrong module.

Status: Fixed. `mypy .` now passes.

## Other Findings Not Fixed In This Pass

### README project structure is stale

Severity: Medium

Area: README clarity

Details:

The README's `Project Structure` section lists an older layout such as `cli.py`,
`scanner/`, `intelligence/`, `selector/`, `compressor/`, and `models.py`. The current
repository uses `contextos/cli/commands/`, `contextos/core/`, and `contextos/exporters/`.

Risk:

New contributors will look for files that do not exist.

Status: Not fixed. Documentation-only and not high priority for this pass.

### MIT license declared but no LICENSE file present

Severity: Medium

Area: packaging, open-source hygiene

Details:

`pyproject.toml` declares `license = { text = "MIT" }`, but the repository does not
include a `LICENSE` file.

Risk:

Package metadata is installable, but GitHub/open-source consumers do not get the full
license text in the repository.

Status: Not fixed. Adding license text should be done by the project owner with the
correct copyright holder.

### Package metadata is minimal

Severity: Low

Area: packaging

Details:

The package has name, version, description, readme, Python requirement, dependencies,
and console script configured. It does not include classifiers, project URLs, authors,
or keywords.

Risk:

Lower discoverability and weaker PyPI presentation, but no runtime breakage.

Status: Not fixed. Not high priority.

## Hardening Follow-Up

Additional real-user hardening completed after the initial audit:

- `.contextos/` is now always excluded from scans so generated packs and indexes do not
  feed back into later scans or packs.
- `contextos scan --max-files` now enforces the documented indexing limit instead of
  only changing the displayed count.
- Scanner relative paths are normalized to POSIX separators for stable output across
  Windows, macOS, and Linux.
- Generated/noisy notebook and minified asset files are skipped before content indexing.
- `contextos pack` now regenerates scan data when `.contextos/file_summaries.json` or
  `.contextos/dependency_graph.json` is corrupted or missing.
- Test-file detection now handles Windows-style separators.

Regression coverage added for empty repos, repos without README files, monorepo-shaped
trees, binary files, large lockfiles, minified JS, notebooks, symlinks, permission errors,
invalid Unicode, corrupted `.contextos`, repeated init/scan/pack workflows, Windows path
separators, nested git metadata, and missing optional dependencies.

### `--out` writes exactly the user-provided path

Severity: Low

Area: file handling

Details:

`contextos pack --out` and `contextos export ... --out` write to the provided path
without creating parent directories and without restricting the path to the repository.

Risk:

This is normal CLI behavior for an explicit output flag, but errors may be less friendly
when a parent directory is missing. It is not an unsafe implicit write because the user
must provide `--out`.

Status: Not fixed. Not high priority.

## Areas Reviewed

### CLI behavior

- Typer command registration is straightforward.
- Invalid repo and invalid budget paths return controlled `typer.Exit(code=1)`.
- Tests cover command help, init, scan, task, memory, pack, export, invalid formats,
  missing repos, and secret-related flags.

### Unsafe file handling

- Scanner uses `os.walk(..., followlinks=False)`.
- Symlinks escaping the repo root are rejected.
- Binary files, oversized files, permission errors, encoding errors, `.git`, virtualenvs,
  build artifacts, and cache directories are skipped.
- `init --force` overwrites `.contextos` templates, but that behavior is explicit and
  documented.

### Secret leakage risks

- Secret-looking filenames are excluded from context selection.
- Raw content is redacted before pack/export output unless `--allow-sensitive` is used.
- `--allow-sensitive` is visibly marked dangerous.
- Memory and decision commands reject note text that looks like embedded credentials.

### Platform issues

- The code primarily uses `pathlib`, UTF-8 text IO, and Typer/Rich.
- Windows-specific chmod semantics are skipped in tests.
- No high-priority Mac/Linux/Windows runtime issue was found in the reviewed code.

### Abstractions and complexity

- The separation between scanner, summarizer, selector, pack builder, exporters, and CLI
  commands is reasonable for the package size.
- Dynamic exporter/provider loading needed clearer typing; fixed.
- No large unnecessary abstraction was introduced in this pass.

## Validation

Commands run after fixes:

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy .
```

Final status after hardening:

- `pytest`: 907 passed, 1 skipped
- `ruff`: passed
- `mypy`: passed, 49 source files checked
