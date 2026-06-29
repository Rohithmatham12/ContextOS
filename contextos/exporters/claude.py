"""Claude Code exporter — generates CLAUDE_CONTEXT.md."""

from __future__ import annotations

from pathlib import Path

from contextos.core.context_selector import ContextSelection
from contextos.exporters.base import ExportConfig, build_export, render_context

FILENAME = "CLAUDE_CONTEXT.md"
TOOL_NAME = "Claude Code"
USAGE_NOTE = (
    "Load with `/add CLAUDE_CONTEXT.md` in a Claude Code session, "
    "or commit to the repo root as `CLAUDE.md` for persistent instructions."
)

_INSTRUCTIONS = """\
You are working on the task described above. The context files are the most \
relevant parts of the codebase, pre-selected to fit within your token budget.

- Use the `Read` tool to inspect any file before editing it.
- Reference locations as `path/to/file:line_number` for precision.
- Use `Edit` (targeted replace) rather than `Write` (full overwrite) whenever possible.
- Follow existing code style — formatting, naming conventions, and patterns already in use.
- Only reference files shown in this context unless you are certain others exist.
- Run linting (`ruff check`) and the test suite after making changes.
- Never bypass git hooks (`--no-verify`) unless the user explicitly requests it.
- If you need the full content of a file shown only as a summary, use the `Read` tool \
  or ask the user to provide it before editing.
""".strip()


def render(
    task: str,
    project_summary: str,
    decisions: str,
    selection: ContextSelection,
    dep_notes: str,
    timestamp: str,
) -> str:
    """Render a Claude Code context pack."""
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
    """Build and write CLAUDE_CONTEXT.md. Returns (content, selection)."""
    return build_export(task, repo_root, contextos_dir, render, FILENAME, config=config)
