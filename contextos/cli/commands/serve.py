"""serve command — start the ContextOS MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Start the ContextOS MCP server.")
console = Console()


def serve_command(
    repo: Annotated[
        Path,
        typer.Argument(help="Repository root to serve. Defaults to current directory."),
    ] = Path("."),
    stdio: Annotated[
        bool,
        typer.Option(
            "--stdio",
            help="Run in stdio mode for Claude Desktop / Claude Code integration.",
        ),
    ] = False,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="HTTP port (ignored in --stdio mode)."),
    ] = 8000,
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host (ignored in --stdio mode)."),
    ] = "127.0.0.1",
) -> None:
    """Start the ContextOS MCP server.

    \b
    Stdio mode (Claude Desktop / Claude Code):
      contextos serve --stdio

    HTTP mode (browser / curl testing):
      contextos serve --port 8000

    \b
    To register with Claude Desktop, add to claude_desktop_config.json:
      {
        "mcpServers": {
          "contextos": {
            "command": "contextos",
            "args": ["serve", "--stdio", "/path/to/your/project"]
          }
        }
      }
    """
    try:
        from contextos.mcp.server import mcp, set_repo
    except ImportError as e:
        console.print(f"[red]Error:[/red] MCP server requires the 'mcp' package.\n{e}")
        console.print("Install: [bold]pip install rm-contextos\\[mcp][/bold]")
        raise typer.Exit(code=1) from e

    repo_path = repo.resolve()
    if not repo_path.is_dir():
        console.print(f"[red]Error:[/red] {repo_path} is not a directory.")
        raise typer.Exit(code=1)

    set_repo(repo_path)

    if stdio:
        import sys

        err = Console(file=sys.stderr)
        err.print(f"[bold]ContextOS MCP Server[/bold] (stdio) — repo: {repo_path}")
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = host
        mcp.settings.port = port

        console.print(f"[bold]ContextOS MCP Server[/bold] — http://{host}:{port}")
        console.print(f"  Repo    : {repo_path}")
        console.print("  Tools   : scan_repo, pack_context, list_files,")
        console.print("            get_file, get_summary, churn_report")
        console.print(f"  SSE     : http://{host}:{port}/sse")
        console.print(f"  MCP     : http://{host}:{port}/mcp")
        console.print("\nPress Ctrl+C to stop.\n")
        mcp.run(transport="streamable-http")


app.command()(serve_command)
