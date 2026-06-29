"""Cursor IDE exporter — generates CURSOR_CONTEXT.md."""

from __future__ import annotations

from pathlib import Path

from contextos.core.context_selector import ContextSelection
from contextos.exporters.base import ExportConfig, build_export, render_context

FILENAME = "CURSOR_CONTEXT.md"
TOOL_NAME = "Cursor"
USAGE_NOTE = (
    "Paste into a Cursor chat (@-mention or drag-drop), or copy the rules section "
    "into `.cursor/rules/contextos.mdc` for persistent project rules."
)

_INSTRUCTIONS = """\
You are the Cursor AI assistant working on the task described above. \
The context files are the most relevant parts of the codebase for this task.

- Follow the existing code patterns and naming conventions in the shown files.
- Use Cursor's multi-file edit capability for refactors that span multiple files.
- Reference file paths relative to the project root.
- Check the Token Budget table — if a file is shown only as a summary, \
  open it in the editor before editing.
- Run linting and the test suite after completing changes.
- Keep edits focused on the current task; avoid unrelated cleanup.
""".strip()


def render(
    task: str,
    project_summary: str,
    decisions: str,
    selection: ContextSelection,
    dep_notes: str,
    timestamp: str,
) -> str:
    """Render a Cursor context pack."""
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
    """Build and write CURSOR_CONTEXT.md. Returns (content, selection)."""
    return build_export(task, repo_root, contextos_dir, render, FILENAME, config=config)
