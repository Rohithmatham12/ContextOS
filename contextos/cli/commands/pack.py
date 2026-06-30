"""pack command — select task-relevant context and export a context pack."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Select task-relevant context and export a context pack.")
console = Console()

_FORMATS = ("md", "json", "xml", "claude", "codex")
_CONTEXTOS_DIR = ".contextos"


def pack_command(
    repo: Annotated[Path, typer.Argument(help="Path to the repository root.")] = Path("."),
    task: Annotated[
        str,
        typer.Option("--task", "-t", help="Task description for relevance ranking."),
    ] = ...,  # type: ignore[assignment]
    budget: Annotated[
        int,
        typer.Option("--budget", "-b", help="Token budget for the context pack."),
    ] = 8000,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=f"Output format: {', '.join(_FORMATS)}."),
    ] = "md",
    include_tests: Annotated[
        bool,
        typer.Option(
            "--include-tests/--no-tests",
            help="Include test files in context selection.",
        ),
    ] = True,
    no_source: Annotated[
        bool,
        typer.Option(
            "--no-source",
            help="Include only file summaries; never embed full source code.",
        ),
    ] = False,
    compress: Annotated[
        str | None,
        typer.Option(
            "--compress",
            help=(
                "Compression provider to apply after context selection. "
                "Available: headroom. "
                "Requires headroom-ai installed and proxy running. "
                "Omit to skip compression."
            ),
        ),
    ] = None,
    no_timestamp: Annotated[
        bool,
        typer.Option("--no-timestamp", help="Omit timestamp for reproducible output."),
    ] = False,
    allow_sensitive: Annotated[
        bool,
        typer.Option(
            "--allow-sensitive",
            help=(
                "[DANGEROUS] Disable secret redaction. Secrets and credentials will appear "
                "in plain text in the output. Only use in fully isolated, private environments."
            ),
        ),
    ] = False,
    out: Annotated[
        Path | None,
        typer.Option("--out", "-o", help="Also write output to this file path."),
    ] = None,
) -> None:
    """Scan repo, rank files by task relevance, enforce token budget, and export.

    \b
    Examples:
      contextos pack . --task "add rate limiting" --budget 8000
      contextos pack . --task "fix auth" --format json --out context.json
      contextos pack . --task "refactor DB" --no-source --budget 4000
      contextos pack . --task "add tests" --no-tests --budget 16000
    """
    if output_format not in _FORMATS:
        console.print(
            f"[red]Error:[/red] Unknown format '{output_format}'. "
            f"Choose from: {', '.join(_FORMATS)}"
        )
        raise typer.Exit(code=1)

    repo = repo.resolve()
    if not repo.is_dir():
        console.print(f"[red]Error:[/red] {repo} is not a directory.")
        raise typer.Exit(code=1)

    if budget <= 0:
        console.print("[red]Error:[/red] --budget must be a positive integer.")
        raise typer.Exit(code=1)

    # Map legacy/alias formats to canonical ones.
    fmt = "md" if output_format in ("xml", "claude", "codex") else output_format

    contextos_dir = repo / _CONTEXTOS_DIR

    console.print(f"[bold]Packing[/bold] {repo}")
    console.print(f"  Task         : {task}")
    console.print(f"  Budget       : {budget:,} tokens")
    console.print(f"  Format       : {output_format}")
    if no_source:
        console.print("  Source       : [dim]summaries only[/dim]")
    if not include_tests:
        console.print("  Tests        : [dim]excluded[/dim]")
    if compress:
        console.print(f"  Compress     : [cyan]{compress}[/cyan]")
    if allow_sensitive:
        console.print("  [bold red]⚠  --allow-sensitive: secret redaction DISABLED[/bold red]")

    from contextos.core.compression import AVAILABLE_PROVIDERS, CompressionError
    from contextos.core.pack_builder import PackConfig, build_pack
    from contextos.core.token_counter import estimate_tokens

    if compress is not None and compress not in AVAILABLE_PROVIDERS:
        choices = ", ".join(AVAILABLE_PROVIDERS)
        console.print(
            f"[red]Error:[/red] Unknown compression provider {compress!r}. Available: {choices}."
        )
        raise typer.Exit(code=1)

    cfg = PackConfig(
        budget=budget,
        include_tests=include_tests,
        no_source=no_source,
        fmt=fmt,
        add_timestamp=not no_timestamp,
        allow_sensitive=allow_sensitive,
        compress=compress,
    )

    try:
        content, selection = build_pack(task, repo, contextos_dir, config=cfg)
    except CompressionError as exc:
        console.print(f"[red]Compression failed:[/red]\n\n{exc}")
        raise typer.Exit(code=1) from exc

    if selection.secret_warnings and not allow_sensitive:
        console.print(
            f"  [yellow]⚠  {len(selection.secret_warnings)} secret(s) detected and "
            f"redacted with [REDACTED_*][/yellow]"
        )

    token_est = estimate_tokens(content)
    repo_total = selection.repo_total_tokens
    saved = max(0, repo_total - selection.used_tokens)
    pct = int(saved / repo_total * 100) if repo_total > 0 else 0

    console.print(
        f"  Context files: [magenta]~{selection.used_tokens:,}[/magenta] tokens"
        f"  (budget: {budget:,})"
    )
    console.print(f"  Pack total   : [magenta]~{token_est:,}[/magenta] tokens (incl. metadata)")
    console.print(
        f"  Selected     : [cyan]{len(selection.selected)}[/cyan] files  "
        f"([yellow]{len(selection.excluded)}[/yellow] excluded)"
    )
    if repo_total > 0:
        console.print()
        console.print("  [bold]Token savings vs no ContextOS[/bold]")
        total_files = len(selection.selected) + len(selection.excluded)
        console.print(
            f"    Without ContextOS : [red]~{repo_total:,}[/red] tokens  "
            f"(entire repo, {total_files} files)"
        )
        console.print(
            f"    With ContextOS    : [green]~{selection.used_tokens:,}[/green] tokens  "
            f"({len(selection.selected)} files)"
        )
        console.print(
            f"    Saved             : [bold green]~{saved:,} tokens ({pct}% reduction)[/bold green]"
        )

    pack_ext = "json" if fmt == "json" else "md"
    default_out = contextos_dir / f"context_pack.{pack_ext}"
    console.print(f"\n[green]✓[/green] Pack written to [bold]{default_out}[/bold]")

    if out is not None:
        out.write_text(content, encoding="utf-8")
        console.print(f"[green]✓[/green] Also written to [bold]{out}[/bold]")


app.command()(pack_command)
