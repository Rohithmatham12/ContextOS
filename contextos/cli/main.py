"""ContextOS CLI entrypoint."""

from __future__ import annotations

import typer

from contextos import __version__
from contextos.cli.commands import export, memory
from contextos.cli.commands.init import init_command
from contextos.cli.commands.pack import pack_command
from contextos.cli.commands.scan import scan_command
from contextos.cli.commands.task import task_command

app = typer.Typer(
    name="contextos",
    help="ContextOS — a context operating system for AI coding agents.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# All leaf commands registered directly — avoids Typer 0.26 sub-app callback issues
app.command("init")(init_command)
app.command("scan")(scan_command)
app.command("pack")(pack_command)
app.command("task")(task_command)

# Group commands with sub-commands use add_typer
app.add_typer(memory.app, name="memory")
app.add_typer(export.app, name="export")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"contextos {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """ContextOS — build repo intelligence and export context packs for AI agents."""
