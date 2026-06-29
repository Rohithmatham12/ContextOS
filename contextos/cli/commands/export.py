"""export command — generate tool-specific context files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Protocol, cast

import typer
from rich.console import Console

from contextos.core.context_selector import ContextSelection
from contextos.exporters.base import ExportConfig

app = typer.Typer(help="Export context packs for specific AI coding tools.")
console = Console()

_CONTEXTOS_DIR = ".contextos"


# ---------------------------------------------------------------------------
# Shared option types (re-declared in each sub-command for Typer compatibility)
# ---------------------------------------------------------------------------

_REPO_HELP = "Repository root (default: current directory)."
_TASK_HELP = "Task description for relevance ranking."
_BUDGET_HELP = "Token budget for context selection."
_TESTS_HELP = "Include test files in context selection."
_SOURCE_HELP = "Include only file summaries; never embed full source."
_TIMESTAMP_HELP = "Omit timestamp for reproducible output."
_OUT_HELP = "Also write output to this additional file path."
_SENSITIVE_HELP = (
    "[DANGEROUS] Disable secret redaction. Secrets will appear in plain text. "
    "Only use in fully isolated, private environments."
)


class _ExporterModule(Protocol):
    TOOL_NAME: str
    FILENAME: str

    def export(
        self,
        task: str,
        repo_root: Path,
        contextos_dir: Path,
        *,
        config: ExportConfig,
    ) -> tuple[str, ContextSelection]: ...


@app.callback()
def export_root(ctx: typer.Context) -> None:  # noqa: ARG001
    """Generate tool-specific context files from your repo and active task."""


# ---------------------------------------------------------------------------
# claude
# ---------------------------------------------------------------------------


@app.command("claude")
def export_claude(
    repo: Annotated[Path, typer.Option("--repo", "-r", help=_REPO_HELP)] = Path("."),
    task: Annotated[str, typer.Option("--task", "-t", help=_TASK_HELP)] = ...,  # type: ignore[assignment]
    budget: Annotated[int, typer.Option("--budget", "-b", help=_BUDGET_HELP)] = 8000,
    include_tests: Annotated[
        bool, typer.Option("--include-tests/--no-tests", help=_TESTS_HELP)
    ] = True,
    no_source: Annotated[bool, typer.Option("--no-source", help=_SOURCE_HELP)] = False,
    no_timestamp: Annotated[bool, typer.Option("--no-timestamp", help=_TIMESTAMP_HELP)] = False,
    allow_sensitive: Annotated[
        bool, typer.Option("--allow-sensitive", help=_SENSITIVE_HELP)
    ] = False,
    out: Annotated[Path | None, typer.Option("--out", "-o", help=_OUT_HELP)] = None,
) -> None:
    """Generate CLAUDE_CONTEXT.md for Claude Code sessions."""
    from contextos.exporters import claude

    _run_export(
        tool_module=claude,
        repo=repo,
        task=task,
        budget=budget,
        include_tests=include_tests,
        no_source=no_source,
        no_timestamp=no_timestamp,
        allow_sensitive=allow_sensitive,
        out=out,
    )


# ---------------------------------------------------------------------------
# codex
# ---------------------------------------------------------------------------


@app.command("codex")
def export_codex(
    repo: Annotated[Path, typer.Option("--repo", "-r", help=_REPO_HELP)] = Path("."),
    task: Annotated[str, typer.Option("--task", "-t", help=_TASK_HELP)] = ...,  # type: ignore[assignment]
    budget: Annotated[int, typer.Option("--budget", "-b", help=_BUDGET_HELP)] = 8000,
    include_tests: Annotated[
        bool, typer.Option("--include-tests/--no-tests", help=_TESTS_HELP)
    ] = True,
    no_source: Annotated[bool, typer.Option("--no-source", help=_SOURCE_HELP)] = False,
    no_timestamp: Annotated[bool, typer.Option("--no-timestamp", help=_TIMESTAMP_HELP)] = False,
    allow_sensitive: Annotated[
        bool, typer.Option("--allow-sensitive", help=_SENSITIVE_HELP)
    ] = False,
    out: Annotated[Path | None, typer.Option("--out", "-o", help=_OUT_HELP)] = None,
) -> None:
    """Generate CODEX_CONTEXT.md for OpenAI Codex / GPT-4 agent sessions."""
    from contextos.exporters import codex

    _run_export(
        tool_module=codex,
        repo=repo,
        task=task,
        budget=budget,
        include_tests=include_tests,
        no_source=no_source,
        no_timestamp=no_timestamp,
        allow_sensitive=allow_sensitive,
        out=out,
    )


# ---------------------------------------------------------------------------
# cursor
# ---------------------------------------------------------------------------


@app.command("cursor")
def export_cursor(
    repo: Annotated[Path, typer.Option("--repo", "-r", help=_REPO_HELP)] = Path("."),
    task: Annotated[str, typer.Option("--task", "-t", help=_TASK_HELP)] = ...,  # type: ignore[assignment]
    budget: Annotated[int, typer.Option("--budget", "-b", help=_BUDGET_HELP)] = 8000,
    include_tests: Annotated[
        bool, typer.Option("--include-tests/--no-tests", help=_TESTS_HELP)
    ] = True,
    no_source: Annotated[bool, typer.Option("--no-source", help=_SOURCE_HELP)] = False,
    no_timestamp: Annotated[bool, typer.Option("--no-timestamp", help=_TIMESTAMP_HELP)] = False,
    allow_sensitive: Annotated[
        bool, typer.Option("--allow-sensitive", help=_SENSITIVE_HELP)
    ] = False,
    out: Annotated[Path | None, typer.Option("--out", "-o", help=_OUT_HELP)] = None,
) -> None:
    """Generate CURSOR_CONTEXT.md for Cursor IDE sessions."""
    from contextos.exporters import cursor

    _run_export(
        tool_module=cursor,
        repo=repo,
        task=task,
        budget=budget,
        include_tests=include_tests,
        no_source=no_source,
        no_timestamp=no_timestamp,
        allow_sensitive=allow_sensitive,
        out=out,
    )


# ---------------------------------------------------------------------------
# aider
# ---------------------------------------------------------------------------


@app.command("aider")
def export_aider(
    repo: Annotated[Path, typer.Option("--repo", "-r", help=_REPO_HELP)] = Path("."),
    task: Annotated[str, typer.Option("--task", "-t", help=_TASK_HELP)] = ...,  # type: ignore[assignment]
    budget: Annotated[int, typer.Option("--budget", "-b", help=_BUDGET_HELP)] = 8000,
    include_tests: Annotated[
        bool, typer.Option("--include-tests/--no-tests", help=_TESTS_HELP)
    ] = True,
    no_source: Annotated[bool, typer.Option("--no-source", help=_SOURCE_HELP)] = False,
    no_timestamp: Annotated[bool, typer.Option("--no-timestamp", help=_TIMESTAMP_HELP)] = False,
    allow_sensitive: Annotated[
        bool, typer.Option("--allow-sensitive", help=_SENSITIVE_HELP)
    ] = False,
    out: Annotated[Path | None, typer.Option("--out", "-o", help=_OUT_HELP)] = None,
) -> None:
    """Generate AIDER_CONTEXT.md for Aider pair-programming sessions."""
    from contextos.exporters import aider

    _run_export(
        tool_module=aider,
        repo=repo,
        task=task,
        budget=budget,
        include_tests=include_tests,
        no_source=no_source,
        no_timestamp=no_timestamp,
        allow_sensitive=allow_sensitive,
        out=out,
    )


# ---------------------------------------------------------------------------
# Shared runner (called by all sub-commands)
# ---------------------------------------------------------------------------


def _run_export(
    *,
    tool_module: object,
    repo: Path,
    task: str,
    budget: int,
    include_tests: bool,
    no_source: bool,
    no_timestamp: bool,
    allow_sensitive: bool = False,
    out: Path | None,
) -> None:
    """Validate inputs, call the tool exporter, and print a summary."""
    from contextos.exporters.base import ExportConfig

    root = repo.resolve()
    if not root.is_dir():
        console.print(f"[red]Error:[/red] {root} is not a directory.")
        raise typer.Exit(code=1)

    if budget <= 0:
        console.print("[red]Error:[/red] --budget must be a positive integer.")
        raise typer.Exit(code=1)

    contextos_dir = root / _CONTEXTOS_DIR
    exporter = cast(_ExporterModule, tool_module)
    tool_name = getattr(exporter, "TOOL_NAME", "Unknown")
    filename = getattr(exporter, "FILENAME", "CONTEXT.md")

    console.print(f"[bold]Exporting[/bold] context for [cyan]{tool_name}[/cyan]")
    console.print(f"  Repo   : {root}")
    console.print(f"  Task   : {task}")
    console.print(f"  Budget : {budget:,} tokens")
    if no_source:
        console.print("  Source : [dim]summaries only[/dim]")
    if not include_tests:
        console.print("  Tests  : [dim]excluded[/dim]")
    if allow_sensitive:
        console.print("  [bold red]⚠  --allow-sensitive: secret redaction DISABLED[/bold red]")

    cfg = ExportConfig(
        budget=budget,
        include_tests=include_tests,
        no_source=no_source,
        add_timestamp=not no_timestamp,
        allow_sensitive=allow_sensitive,
    )

    content, selection = exporter.export(task, root, contextos_dir, config=cfg)

    if selection.secret_warnings and not allow_sensitive:
        console.print(
            f"  [yellow]⚠  {len(selection.secret_warnings)} secret(s) detected and "
            f"redacted with [REDACTED_*][/yellow]"
        )

    default_out = contextos_dir / filename
    console.print(
        f"\n[green]✓[/green] Wrote [bold]{filename}[/bold] "
        f"({len(selection.selected)} files, ~{selection.used_tokens:,} tokens)"
    )
    console.print(f"  Path: {default_out}")

    if out is not None:
        out.write_text(content, encoding="utf-8")
        console.print(f"[green]✓[/green] Also written to [bold]{out}[/bold]")
