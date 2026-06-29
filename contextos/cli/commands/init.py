"""init command — initialize the .contextos/ project directory."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from contextos.core import initializer

app = typer.Typer(help="Initialize the .contextos/ directory in a project.")
console = Console()

_STATUS_STYLE: dict[str, str] = {
    "created": "green",
    "overwritten": "yellow",
    "skipped": "dim",
    "error": "red",
}

_STATUS_ICON: dict[str, str] = {
    "created": "✓",
    "overwritten": "↺",
    "skipped": "–",
    "error": "✗",
}


def init_command(
    directory: Annotated[Path, typer.Argument(help="Project directory to initialize.")] = Path("."),
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite all existing files.")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress file-by-file output.")
    ] = False,
) -> None:
    """Create the .contextos/ directory with template files.

    Safe to run multiple times — existing memory files are skipped unless
    --force is passed.  Computed files (file_summaries.json, etc.) are also
    skipped by init; they are overwritten by `scan` and `pack`.
    """
    root = directory.resolve()

    if not root.exists():
        console.print(f"[red]Error:[/red] directory does not exist: {root}")
        raise typer.Exit(code=1)

    result = initializer.run(root, force=force)

    if not quiet:
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("Status", width=2)
        table.add_column("File")
        table.add_column("Note", style="dim")

        for f in result.files:
            icon = _STATUS_ICON.get(f.status, "?")
            style = _STATUS_STYLE.get(f.status, "")
            note = f.message if f.status == "error" else ""
            table.add_row(
                f"[{style}]{icon}[/{style}]",
                f"[{style}].contextos/{f.name}[/{style}]",
                note,
            )

        console.print(table)
        console.print()

    created = len(result.created)
    skipped = len(result.skipped)
    overwritten = len(result.overwritten)
    errors = len(result.errors)

    parts: list[str] = []
    if created:
        parts.append(f"[green]{created} created[/green]")
    if overwritten:
        parts.append(f"[yellow]{overwritten} overwritten[/yellow]")
    if skipped:
        parts.append(f"[dim]{skipped} skipped[/dim]")
    if errors:
        parts.append(f"[red]{errors} error(s)[/red]")

    summary = ", ".join(parts) if parts else "nothing to do"
    console.print(f"[bold]{result.contextos_dir}[/bold]  {summary}")

    if errors:
        raise typer.Exit(code=1)


app.command()(init_command)
