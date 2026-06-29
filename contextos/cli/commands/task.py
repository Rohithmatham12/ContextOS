"""task command — manage the current task definition in .contextos/CURRENT_TASK.md."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

console = Console()

_CONTEXTOS_DIR = ".contextos"
_TASK_FILE = "CURRENT_TASK.md"


def _task_path(repo: Path) -> Path:
    return repo / _CONTEXTOS_DIR / _TASK_FILE


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _render_task(description: str, status: str, timestamp: str) -> str:
    return (
        "# Current Task\n\n"
        "> Managed by `contextos task`. Edit freely.\n\n"
        f"**Status:** {status}  \n"
        f"**Set:** {timestamp}\n\n"
        "## Task\n\n"
        f"{description}\n\n"
        "## Acceptance Criteria\n\n"
        "- [ ] \n\n"
        "## Notes\n\n"
    )


def _cleared_template(timestamp: str) -> str:
    return (
        "# Current Task\n\n"
        "> Managed by `contextos task`. Edit freely.\n\n"
        f"**Status:** Cleared  \n"
        f"**Set:** {timestamp}\n\n"
        "## Task\n\n"
        '<!-- No active task. Use `contextos task "<description>"` to set one. -->\n\n'
        "## Acceptance Criteria\n\n"
        "- [ ] \n\n"
        "## Notes\n\n"
    )


# ---------------------------------------------------------------------------
# Implementation helpers (exported for direct use in tests / other modules)
# ---------------------------------------------------------------------------


def _impl_set(description: str, status: str, root: Path) -> None:
    path = _task_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = _now_iso()
    path.write_text(_render_task(description, status, ts), encoding="utf-8")
    console.print(f"[green]✓[/green] Task saved to [bold]{_CONTEXTOS_DIR}/{_TASK_FILE}[/bold]")
    console.print(f"  Task   : {description}")
    console.print(f"  Status : {status}")
    console.print(f"  Set    : {ts}")


def _impl_show(root: Path) -> None:
    path = _task_path(root)
    if not path.exists():
        console.print(
            '[yellow]No active task.[/yellow] Use `contextos task "<description>"` to set one.'
        )
        return
    console.print(Markdown(path.read_text(encoding="utf-8")))


def _impl_clear(root: Path) -> None:
    path = _task_path(root)
    if not path.exists():
        console.print("[yellow]No active task to clear.[/yellow]")
        return
    ts = _now_iso()
    path.write_text(_cleared_template(ts), encoding="utf-8")
    console.print("[green]✓[/green] Task cleared.")


# ---------------------------------------------------------------------------
# Single leaf command — registered on the main app (not as a sub-app)
# ---------------------------------------------------------------------------


def task_command(
    args: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                'Task description to set, or "show" / "clear" / "set <description>". '
                "Multiple words are joined automatically."
            ),
            metavar="[DESCRIPTION|show|clear]",
            show_default=False,
        ),
    ] = None,
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repository root (default: current directory)."),
    ] = Path("."),
    status: Annotated[
        str,
        typer.Option("--status", "-s", help='Task status label (default: "In Progress").'),
    ] = "In Progress",
) -> None:
    """Set, show, or clear the current task in .contextos/CURRENT_TASK.md.

    \b
    Examples:
      contextos task "add rate limiting to the API"   # set task
      contextos task add rate limiting                 # set (words joined automatically)
      contextos task set "description" --status Done   # set with custom status
      contextos task show                              # display current task
      contextos task clear                             # reset task
      contextos task                                   # alias for show
    """
    root = repo.resolve()

    if not args:
        _impl_show(root)
        return

    first = args[0].lower()

    if first == "show" and len(args) == 1:
        _impl_show(root)
    elif first == "clear" and len(args) == 1:
        _impl_clear(root)
    elif first == "set" and len(args) > 1:
        # "task set description words here" → joins remaining args as description
        _impl_set(" ".join(args[1:]), status, root)
    elif first == "set" and len(args) == 1:
        # bare "task set" with no description → show
        _impl_show(root)
    else:
        # Everything else is the task description (words joined)
        _impl_set(" ".join(args), status, root)


# Regex for ISO 8601 timestamp — used in tests
_ISO_RE: re.Pattern[str] = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
