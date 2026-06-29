"""Aider exporter — generates AIDER_CONTEXT.md."""

from __future__ import annotations

from pathlib import Path

from contextos.core.context_selector import ContextSelection
from contextos.exporters.base import ExportConfig, build_export, render_context

FILENAME = "AIDER_CONTEXT.md"
TOOL_NAME = "Aider"
USAGE_NOTE = (
    "Load with `aider --read AIDER_CONTEXT.md`, or place in the repo root "
    "and add to `.aiderignore` if you do not want Aider to edit it directly."
)

_INSTRUCTIONS = """\
You are Aider, an AI pair-programming assistant, working on the task above. \
The context files are the most relevant parts of the codebase for this task.

- Produce minimal diffs. Only change what is necessary for the task.
- Match the exact indentation, quote style, and import ordering of each file.
- Do not add unrequested features or refactor surrounding code.
- Reference functions and classes by their exact signatures as shown.
- If a file is shown as a summary, use `/add <path>` to load it before editing.
- After applying changes, verify with the relevant test command.
- Commit only the changes related to the current task.
""".strip()


def render(
    task: str,
    project_summary: str,
    decisions: str,
    selection: ContextSelection,
    dep_notes: str,
    timestamp: str,
) -> str:
    """Render an Aider context pack."""
    return render_context(
        task,
        project_summary,
        decisions,
        selection,
        dep_notes,
        timestamp,
        tool_name=TOOL_NAME,
        filename=FILENAME,
        usage_note=USAGE_NOTE,
        agent_instructions=_INSTRUCTIONS,
    )


def export(
    task: str,
    repo_root: Path,
    contextos_dir: Path,
    *,
    config: ExportConfig | None = None,
) -> tuple[str, ContextSelection]:
    """Build and write AIDER_CONTEXT.md. Returns (content, selection)."""
    return build_export(task, repo_root, contextos_dir, render, FILENAME, config=config)
