"""memory command — manage .contextos/MEMORY.md and .contextos/DECISIONS.md."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

app = typer.Typer(help="Manage project memory and decision log in .contextos/.")
console = Console()

_CONTEXTOS_DIR = ".contextos"
_MEMORY_FILE = "MEMORY.md"
_DECISIONS_FILE = "DECISIONS.md"

# Patterns that suggest embedded secrets — reject notes containing these.
# Matches "keyword=<value>" or "keyword: <value>" (not bare mentions of the word).
_SECRET_RE: re.Pattern[str] = re.compile(
    r"(?:password|secret|api[_\-.]?key|access[_\-.]?token|bearer|private[_\-.]?key)"
    r"\s*[=:]\s*\S{4,}",
    re.IGNORECASE,
)
# Long hex strings that look like raw API keys or hashes.
_HEX_RE: re.Pattern[str] = re.compile(r"[0-9a-fA-F]{40,}")
# Base64 blobs (common in JWT / bearer tokens).
_B64_RE: re.Pattern[str] = re.compile(r"[A-Za-z0-9+/]{60,}={0,2}")


# ---------------------------------------------------------------------------
# Sub-command group
# ---------------------------------------------------------------------------


@app.callback()
def memory_root(ctx: typer.Context) -> None:  # noqa: ARG001
    """Manage .contextos/MEMORY.md and .contextos/DECISIONS.md."""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("add")
def memory_add(
    note: Annotated[str, typer.Argument(help="Note text to append to MEMORY.md.")],
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repository root (default: current directory)."),
    ] = Path("."),
) -> None:
    """Append a timestamped note to .contextos/MEMORY.md."""
    _impl_add(note, repo.resolve())


@app.command("update")
def memory_update(
    note: Annotated[str, typer.Argument(help="Note text to append to MEMORY.md.")],
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repository root (default: current directory)."),
    ] = Path("."),
) -> None:
    """Append a timestamped note to .contextos/MEMORY.md (alias for add)."""
    _impl_add(note, repo.resolve())


@app.command("decision")
def memory_decision(
    text: Annotated[str, typer.Argument(help="Decision text to record.")],
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repository root (default: current directory)."),
    ] = Path("."),
    status: Annotated[
        str,
        typer.Option("--status", "-s", help='Decision status (default: "accepted").'),
    ] = "accepted",
) -> None:
    """Append a timestamped decision to .contextos/DECISIONS.md."""
    _impl_decision(text, status, repo.resolve())


@app.command("list")
def memory_list(
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repository root (default: current directory)."),
    ] = Path("."),
    show_decisions: Annotated[
        bool,
        typer.Option("--decisions/--no-decisions", help="Also show DECISIONS.md."),
    ] = True,
) -> None:
    """Display .contextos/MEMORY.md and optionally DECISIONS.md."""
    _impl_list(repo.resolve(), show_decisions=show_decisions)


@app.command("compact")
def memory_compact(
    repo: Annotated[  # noqa: ARG001
        Path,
        typer.Option("--repo", "-r", help="Repository root (default: current directory)."),
    ] = Path("."),
) -> None:
    """[Placeholder] Compact memory via LLM — not yet implemented."""
    console.print("[yellow]Compaction is not yet implemented.[/yellow]")
    console.print(
        "To compact manually: edit [bold].contextos/MEMORY.md[/bold] and remove outdated entries."
    )
    console.print("Future versions will compress notes into concise summaries using an LLM.")


# ---------------------------------------------------------------------------
# Implementation helpers (also imported directly in tests)
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _memory_path(root: Path) -> Path:
    return root / _CONTEXTOS_DIR / _MEMORY_FILE


def _decisions_path(root: Path) -> Path:
    return root / _CONTEXTOS_DIR / _DECISIONS_FILE


def _contains_secret(text: str) -> bool:
    """Return True if *text* appears to embed a secret or credential value."""
    return bool(_SECRET_RE.search(text) or _HEX_RE.search(text) or _B64_RE.search(text))


def _impl_add(note: str, root: Path) -> None:
    if _contains_secret(note):
        console.print("[red]Error:[/red] Note appears to contain a secret or credential value.")
        console.print("Remove secrets before saving to memory.")
        raise typer.Exit(code=1)

    path = _memory_path(root)
    _ensure_memory(path)
    ts = _now_iso()
    entry = f"- **{ts}** — {note}\n"
    _append_to_notes(path, entry)
    console.print(f"[green]✓[/green] Note appended to [bold]{_CONTEXTOS_DIR}/{_MEMORY_FILE}[/bold]")
    console.print(f"  Set : {ts}")
    console.print(f"  Note: {note}")


def _impl_decision(text: str, status: str, root: Path) -> None:
    if _contains_secret(text):
        console.print(
            "[red]Error:[/red] Decision text appears to contain a secret or credential value."
        )
        raise typer.Exit(code=1)

    path = _decisions_path(root)
    _ensure_decisions(path)
    ts = _now_iso()
    date = ts[:10]
    entry = (
        "\n---\n\n"
        f"### [{date}] Decision\n\n"
        f"**Status:** {status}\n\n"
        f"**Decision:** {text}\n\n"
        f"**Logged:** {ts}\n"
    )
    _append_raw(path, entry)
    console.print(
        f"[green]✓[/green] Decision appended to [bold]{_CONTEXTOS_DIR}/{_DECISIONS_FILE}[/bold]"
    )
    console.print(f"  Status   : {status}")
    console.print(f"  Decision : {text}")
    console.print(f"  Logged   : {ts}")


def _impl_list(root: Path, *, show_decisions: bool = True) -> None:
    mem = _memory_path(root)
    dec = _decisions_path(root)
    found_any = False

    if mem.exists():
        found_any = True
        console.print(f"\n[bold cyan]── {_MEMORY_FILE} ──[/bold cyan]")
        console.print(Markdown(mem.read_text(encoding="utf-8")))

    if show_decisions and dec.exists():
        found_any = True
        console.print(f"\n[bold cyan]── {_DECISIONS_FILE} ──[/bold cyan]")
        console.print(Markdown(dec.read_text(encoding="utf-8")))

    if not found_any:
        console.print(
            "[yellow]No memory files found.[/yellow] "
            "Run `contextos init` or `contextos memory add` first."
        )


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _ensure_memory(path: Path) -> None:
    """Create MEMORY.md with a Notes section if it doesn't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# Project Memory\n\n"
            "> Persistent notes managed by ContextOS. Append-only recommended.\n\n"
            "## Notes\n\n",
            encoding="utf-8",
        )
    elif "## Notes" not in path.read_text(encoding="utf-8"):
        _append_raw(path, "\n## Notes\n\n")


def _ensure_decisions(path: Path) -> None:
    """Create DECISIONS.md with a header if it doesn't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# Decision Log\n\n> Architectural and design decisions. Append-only recommended.\n\n",
            encoding="utf-8",
        )


def _append_to_notes(path: Path, entry: str) -> None:
    """Append *entry* inside the ## Notes section (before next ## or EOF)."""
    text = path.read_text(encoding="utf-8")
    section = "## Notes"
    if section not in text:
        _append_raw(path, f"\n{section}\n\n{entry}")
        return

    idx = text.index(section)
    after_section = text[idx + len(section) :]
    # Find next top-level section heading after ## Notes
    next_h2 = re.search(r"\n##\s", after_section)
    if next_h2:
        insert_pos = idx + len(section) + next_h2.start()
        text = text[:insert_pos] + "\n" + entry + text[insert_pos:]
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += entry
    path.write_text(text, encoding="utf-8")


def _append_raw(path: Path, text: str) -> None:
    """Append *text* verbatim to the end of *path*."""
    existing = path.read_text(encoding="utf-8")
    if existing and not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing + text, encoding="utf-8")
