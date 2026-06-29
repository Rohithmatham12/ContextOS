"""scan command — walk a repository and report file index statistics."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from contextos.core.scanner import ScanConfig, scan

app = typer.Typer(help="Scan a repository and display file index statistics.")
console = Console()


def scan_command(
    repo: Annotated[Path, typer.Argument(help="Path to the repository root.")] = Path("."),
    max_files: Annotated[int, typer.Option("--max-files", help="Maximum files to index.")] = 5000,
    show_languages: Annotated[
        bool, typer.Option("--languages/--no-languages", help="Show language breakdown.")
    ] = True,
    no_index: Annotated[
        bool,
        typer.Option("--no-index", help="Skip writing .contextos/ output files."),
    ] = False,
) -> None:
    """Scan a repository and write a project index to .contextos/."""
    repo = repo.resolve()

    if not repo.is_dir():
        console.print(f"[red]Error:[/red] {repo} is not a directory.")
        raise typer.Exit(code=1)

    console.print(f"[bold]Scanning[/bold] {repo} …")

    config = ScanConfig(max_file_bytes=524288)
    result = scan(repo, config)

    total = min(result.total_files, max_files)
    console.print(f"\nFiles indexed : [cyan]{total}[/cyan]")
    console.print(f"Files skipped : [yellow]{result.total_skipped}[/yellow]")

    if result.skipped:
        reason_counts = Counter(s.reason for s in result.skipped)
        reason_summary = ", ".join(f"{r}={n}" for r, n in sorted(reason_counts.items()))
        console.print(f"Skip reasons  : [dim]{reason_summary}[/dim]")

    if result.files:
        from contextos.core.token_counter import estimate_from_bytes

        total_bytes = sum(e.size for e in result.files)
        token_est = estimate_from_bytes(total_bytes)
        console.print(f"Token estimate : [magenta]~{token_est:,}[/magenta]")

    if show_languages and result.files:
        table = Table(title="Language breakdown", show_header=True, header_style="bold")
        table.add_column("Language", style="cyan")
        table.add_column("Files", justify="right")
        for lang, count in result.language_counts().items():
            table.add_row(lang, str(count))
        console.print(table)

    if no_index:
        return

    # Write .contextos/ output files
    contextos_dir = repo / ".contextos"
    try:
        contextos_dir.mkdir(parents=True, exist_ok=True)
        _write_index_files(repo, result, contextos_dir)
        console.print(f"\n[green]✓[/green] Written to [bold]{contextos_dir}[/bold]")
    except OSError as exc:
        console.print(f"\n[yellow]Warning:[/yellow] Could not write .contextos/: {exc}")


def _write_index_files(repo: Path, result: object, contextos_dir: Path) -> None:
    from contextos.core.dependency_graph import build_graph, write_graph
    from contextos.core.repo_index import build_index, write_project_index
    from contextos.core.scanner import ScanResult
    from contextos.core.summarizer import summarize_repo

    assert isinstance(result, ScanResult)

    summaries = summarize_repo(result, output_path=contextos_dir / "file_summaries.json")
    index = build_index(repo, result, summaries)
    write_project_index(index, contextos_dir / "PROJECT_INDEX.md")
    graph = build_graph(result)
    write_graph(graph, contextos_dir / "dependency_graph.json")


app.command()(scan_command)
