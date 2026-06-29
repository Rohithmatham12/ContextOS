"""OpenAI Codex / GPT-4 Agents exporter — generates CODEX_CONTEXT.md."""

from __future__ import annotations

from pathlib import Path

from contextos.core.context_selector import ContextSelection
from contextos.exporters.base import ExportConfig, build_export, render_context

FILENAME = "CODEX_CONTEXT.md"
TOOL_NAME = "OpenAI Codex"
USAGE_NOTE = (
    "Paste into a Codex or GPT-4 agent session, or commit to the repo root "
    "as `AGENTS.md` for persistent agent instructions."
)

_INSTRUCTIONS = """\
You are an AI coding agent working on the task described above. \
The context files below are the most relevant parts of the codebase.

- Make minimal, targeted changes. Do not rewrite code that does not need to change.
- Preserve existing code style — indentation, naming, and import order.
- Do not introduce new dependencies without explicit justification.
- Reference files by their relative path from the repository root.
- Write or update tests alongside any new or modified functions.
- After making changes, verify the diff is correct before finalising.
- Do not add comments that merely restate what the code does.
""".strip()


def render(
    task: str,
    project_summary: str,
    decisions: str,
    selection: ContextSelection,
    dep_notes: str,
    timestamp: str,
) -> str:
    """Render an OpenAI Codex context pack."""
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
    """Build and write CODEX_CONTEXT.md. Returns (content, selection)."""
    return build_export(task, repo_root, contextos_dir, render, FILENAME, config=config)
