"""Initializer — creates the .contextos/ project directory and template files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CONTEXTOS_DIR = ".contextos"

# Protected from overwrite without --force (user-editable content)
MEMORY_FILES: frozenset[str] = frozenset(
    {
        "PROJECT_INDEX.md",
        "CURRENT_TASK.md",
        "DECISIONS.md",
        "MEMORY.md",
        "CONFIG.json",
    }
)

# Created if absent; overwritten by scan/pack commands in normal operation
COMPUTED_FILES: frozenset[str] = frozenset(
    {
        "file_summaries.json",
        "dependency_graph.json",
        "context_pack.md",
    }
)

ALL_FILES: frozenset[str] = MEMORY_FILES | COMPUTED_FILES


@dataclass
class FileResult:
    name: str
    status: str  # "created" | "skipped" | "overwritten" | "error"
    message: str = field(default="")


@dataclass
class InitResult:
    root: Path
    contextos_dir: Path
    files: list[FileResult] = field(default_factory=list)

    @property
    def created(self) -> list[FileResult]:
        return [f for f in self.files if f.status == "created"]

    @property
    def skipped(self) -> list[FileResult]:
        return [f for f in self.files if f.status == "skipped"]

    @property
    def overwritten(self) -> list[FileResult]:
        return [f for f in self.files if f.status == "overwritten"]

    @property
    def errors(self) -> list[FileResult]:
        return [f for f in self.files if f.status == "error"]


def run(root: Path, *, force: bool = False) -> InitResult:
    """Create or refresh the .contextos/ directory in *root*.

    On first run all files are created.  On subsequent runs, files in
    MEMORY_FILES are skipped unless *force* is True; COMPUTED_FILES are
    also skipped by init (scan/pack overwrite them independently).
    """
    resolved = root.resolve()
    contextos_dir = resolved / CONTEXTOS_DIR
    contextos_dir.mkdir(parents=True, exist_ok=True)

    result = InitResult(root=resolved, contextos_dir=contextos_dir)

    for name in sorted(ALL_FILES):
        result.files.append(_write_file(contextos_dir / name, name, force=force))

    return result


def _write_file(path: Path, name: str, *, force: bool) -> FileResult:
    template = _template(name)
    existed = path.exists()

    if existed and not force:
        return FileResult(name=name, status="skipped")

    try:
        path.write_text(template, encoding="utf-8")
    except OSError as exc:
        return FileResult(name=name, status="error", message=str(exc))

    return FileResult(name=name, status="overwritten" if existed else "created")


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def _template(name: str) -> str:
    templates: dict[str, str] = {
        "PROJECT_INDEX.md": _tpl_project_index(),
        "CURRENT_TASK.md": _tpl_current_task(),
        "DECISIONS.md": _tpl_decisions(),
        "MEMORY.md": _tpl_memory(),
        "CONFIG.json": _tpl_config(),
        "file_summaries.json": _tpl_file_summaries(),
        "dependency_graph.json": _tpl_dependency_graph(),
        "context_pack.md": _tpl_context_pack(),
    }
    return templates.get(name, "")


def _tpl_project_index() -> str:
    return """\
# Project Index

> Auto-populated by `contextos scan`. Edit freely — scan will merge, not overwrite.

## Project Name

<!-- Replace with your project name -->

## Description

<!-- What does this project do? -->

## Tech Stack

<!-- e.g. Python 3.11, FastAPI, PostgreSQL -->

## Key Entry Points

| File | Purpose |
|------|---------|
| <!-- path --> | <!-- description --> |

## Architecture Notes

<!-- High-level structure overview -->

## Important Invariants

<!-- Non-obvious constraints agents must respect -->
"""


def _tpl_current_task() -> str:
    return """\
# Current Task

> Set with `contextos task set "<description>"`. Edit freely.

## Task

<!-- What are you working on right now? -->

## Acceptance Criteria

- [ ] <!-- When is this done? -->

## Files Likely Involved

<!-- List files relevant to this task -->

## Context for Agent

<!-- What should the AI coding agent know before starting? -->

## Scratch / Notes

<!-- Working notes — delete freely -->
"""


def _tpl_decisions() -> str:
    return """\
# Decision Log

> Record architectural and design decisions here. Append-only recommended.

<!-- Copy and fill in the template below for each decision. -->

---

## Template

### [YYYY-MM-DD] Decision Title

**Status:** proposed | accepted | superseded | deprecated

**Context:** What problem were you solving?

**Decision:** What did you decide?

**Consequences:** Trade-offs and downstream effects.

---
"""


def _tpl_memory() -> str:
    return """\
# Project Memory

> Persistent notes for ContextOS. Survives across sessions and context resets.

## Important Facts

<!-- Key facts about the project that are easy to forget -->

## Gotchas

<!-- Non-obvious things that caused bugs or confusion -->

## Conventions

<!-- Naming patterns, code style, project-specific idioms -->

## Environment

<!-- Required env vars, external services, credentials needed -->

## Useful Commands

<!-- Commands that are always needed but easy to forget -->
```bash
# e.g.
```
"""


def _tpl_config() -> str:
    config = {
        "version": "0.1",
        "scan": {
            "max_files": 5000,
            "max_file_bytes": 524288,
            "exclude": [
                ".git",
                "__pycache__",
                "node_modules",
                "*.pyc",
                "*.pyo",
                ".contextos",
                ".venv",
                "dist",
                "build",
            ],
        },
        "pack": {
            "default_budget": 8000,
            "default_format": "md",
            "default_strategy": "default",
        },
        "memory": {
            "inject_project_index": True,
            "inject_current_task": True,
            "inject_memory": True,
        },
    }
    return json.dumps(config, indent=2) + "\n"


def _tpl_file_summaries() -> str:
    return json.dumps({}, indent=2) + "\n"


def _tpl_dependency_graph() -> str:
    stub = {
        "_note": "Populated by `contextos scan`. Do not edit manually.",
        "nodes": [],
        "edges": [],
    }
    return json.dumps(stub, indent=2) + "\n"


def _tpl_context_pack() -> str:
    return """\
<!-- Generated by `contextos pack`. Do not edit manually. -->
<!-- Run `contextos pack --task "<task>" --budget <n>` to regenerate. -->
"""
