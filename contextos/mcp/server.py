"""ContextOS MCP Server — exposes repo intelligence as MCP tools.

Allows AI agents (Claude Code, Claude Desktop, etc.) to call ContextOS
directly as a tool rather than running CLI commands. Agents can scan repos,
pack context, search symbols, and read file summaries through the MCP protocol.

Run with:
    contextos serve [--repo .] [--port 8000]

Or register as a stdio server in claude_desktop_config.json:
    {
      "mcpServers": {
        "contextos": {
          "command": "contextos",
          "args": ["serve", "--stdio"]
        }
      }
    }
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="contextos",
    instructions=(
        "ContextOS — repo intelligence for AI agents. "
        "Use pack_context to get a task-relevant context pack. "
        "Use scan_repo to index a repository. "
        "Use list_files to see which files score highest for a task. "
        "Use get_file to read a single file with secret redaction. "
        "Use get_summary to get the static analysis summary of a file."
    ),
)

# The repo root is set once at server startup (see serve_command).
_REPO_ROOT: Path = Path(".")


def set_repo(path: Path) -> None:
    global _REPO_ROOT
    _REPO_ROOT = path.resolve()


def _resolve_repo(repo: str) -> Path:
    """Resolve repo arg to an absolute path. Always returns _REPO_ROOT for '.'."""
    return _REPO_ROOT if repo == "." else Path(repo).resolve()


def _safe_file_path(repo_root: Path, rel_path: str) -> Path | None:
    """Resolve rel_path inside repo_root. Returns None if it escapes the root."""
    try:
        full = (repo_root / rel_path).resolve()
        full.relative_to(repo_root)  # raises ValueError if outside
        return full
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def scan_repo(repo: str = ".") -> str:
    """Scan a repository and build the ContextOS intelligence index.

    Must be called before pack_context or list_files on a new repo.
    Subsequent calls are fast — only changed files are re-summarized.

    Args:
        repo: Absolute or relative path to the repository root.
    """
    from contextos.core.dependency_graph import build_graph, write_graph
    from contextos.core.repo_index import build_index, write_project_index
    from contextos.core.scanner import ScanConfig, scan
    from contextos.core.summarizer import load_summaries, summarize_repo

    repo_path = _resolve_repo(repo)
    ctx_dir = repo_path / ".contextos"
    ctx_dir.mkdir(parents=True, exist_ok=True)

    result = scan(repo_path, ScanConfig(max_file_bytes=524288))

    existing = None
    summaries_path = ctx_dir / "file_summaries.json"
    if summaries_path.exists():
        try:
            existing = load_summaries(summaries_path)
        except Exception:  # noqa: BLE001
            pass

    summaries = summarize_repo(result, output_path=summaries_path, existing=existing)
    index = build_index(repo_path, result, summaries)
    write_project_index(index, ctx_dir / "PROJECT_INDEX.md")
    graph = build_graph(result)
    write_graph(graph, ctx_dir / "dependency_graph.json")

    langs: dict[str, int] = {}
    for f in result.files:
        langs[f.language] = langs.get(f.language, 0) + 1
    top = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:5]
    top_str = ", ".join(f"{lang}:{n}" for lang, n in top)

    return (
        f"Scanned {len(result.files)} files in {repo_path}\n"
        f"Languages: {top_str}\n"
        f"Index written to {ctx_dir}"
    )


@mcp.tool()
def pack_context(
    task: str,
    budget: int = 8000,
    repo: str = ".",
    format: str = "md",
) -> str:
    """Select and return a task-relevant context pack from the repository.

    Ranks all indexed files by relevance to the task using keyword matching,
    import graph centrality, AST symbol overlap, and git churn. Enforces the
    token budget. Automatically redacts secrets.

    Args:
        task: Plain-English description of the current task.
        budget: Maximum tokens to include (default 8000).
        repo: Path to the repository root (default: server's configured repo).
        format: Output format — "md" or "json".
    """
    from contextos.core.pack_builder import PackConfig, build_pack

    repo_path = _resolve_repo(repo)
    ctx_dir = repo_path / ".contextos"

    cfg = PackConfig(
        budget=budget,
        fmt="json" if format == "json" else "md",
        add_timestamp=False,
    )
    content, selection = build_pack(task, repo_path, ctx_dir, config=cfg)

    repo_total = selection.repo_total_tokens
    saved = max(0, repo_total - selection.used_tokens)
    pct = int(saved / repo_total * 100) if repo_total > 0 else 0

    header = (
        f"<!-- ContextOS Pack | task: {task} | "
        f"{len(selection.selected)} files | "
        f"~{selection.used_tokens:,} tokens | "
        f"saved ~{saved:,} tokens ({pct}%) vs full repo -->\n\n"
    )
    return header + content


@mcp.tool()
def list_files(
    task: str,
    top_n: int = 20,
    repo: str = ".",
) -> str:
    """List the top N files ranked by relevance to a task.

    Returns a table of files with their scores and the reasons they were
    selected (keyword match, symbol overlap, import centrality, git churn).

    Args:
        task: Plain-English description of the task.
        top_n: How many files to return (default 20).
        repo: Path to the repository root.
    """
    from contextos.core.context_selector import (
        SelectionConfig,
        _load_graph_safe,
        _load_summaries_safe,
        _load_text_safe,
        _select,
    )

    repo_path = _resolve_repo(repo)
    ctx_dir = repo_path / ".contextos"

    summaries = _load_summaries_safe(ctx_dir)
    graph = _load_graph_safe(ctx_dir)
    memory = _load_text_safe(ctx_dir / "MEMORY.md")

    cfg = SelectionConfig(budget=999_999)  # no budget limit — just rank
    selection = _select(task, summaries, graph, memory, repo_path, cfg)

    lines = [f"Top {min(top_n, len(selection.selected))} files for: {task!r}\n"]
    lines.append(f"{'#':<3} {'Score':>6}  {'File':<50}  Reasons")
    lines.append("-" * 90)
    for i, f in enumerate(selection.selected[:top_n], 1):
        reasons = ", ".join(f.reasons[:3])
        lines.append(f"{i:<3} {f.score:>6.2f}  {f.rel_path:<50}  {reasons}")

    return "\n".join(lines)


@mcp.tool()
def get_file(
    rel_path: str,
    repo: str = ".",
) -> str:
    """Return the content of a single file from the repository, secrets redacted.

    Args:
        rel_path: Relative path to the file from the repo root.
        repo: Path to the repository root.
    """
    from contextos.core.secret_detector import is_secret_file, redact_content

    repo_path = _resolve_repo(repo)

    full_path = _safe_file_path(repo_path, rel_path)
    if full_path is None:
        return "Error: path traversal detected — rel_path must stay inside the repo root."

    if is_secret_file(rel_path):
        return f"Error: {rel_path} is a secret/credential file — content withheld."

    if not full_path.exists():
        return f"Error: {rel_path} not found in {repo_path}"

    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"Error reading {rel_path}: {e}"

    redacted, matches = redact_content(content)
    note = f"<!-- {len(matches)} secret(s) redacted -->\n" if matches else ""
    return note + redacted


@mcp.tool()
def get_summary(
    rel_path: str,
    repo: str = ".",
) -> str:
    """Return the static-analysis summary of a file (language, imports, exports, symbols).

    Much cheaper than get_file when you only need to understand what a file does.

    Args:
        rel_path: Relative path to the file from the repo root.
        repo: Path to the repository root.
    """
    import json

    from contextos.core.context_selector import _load_summaries_safe

    repo_path = _resolve_repo(repo)
    ctx_dir = repo_path / ".contextos"
    summaries = _load_summaries_safe(ctx_dir)

    if rel_path not in summaries:
        return f"Error: no summary for {rel_path}. Run scan_repo first."

    s = summaries[rel_path]
    return json.dumps(s.to_dict(), indent=2)


@mcp.tool()
def churn_report(
    days: int = 30,
    top_n: int = 15,
    repo: str = ".",
) -> str:
    """Show the most frequently modified files in git history.

    Files with high churn are often the most actively developed and most
    likely to be relevant to current tasks.

    Args:
        days: How many days of git history to scan (default 30).
        top_n: How many files to show (default 15).
        repo: Path to the repository root.
    """
    from contextos.core.git_churn import build_churn_map

    repo_path = _resolve_repo(repo)
    churn = build_churn_map(repo_path, days=days)

    if not churn:
        return f"No git history found in {repo_path} (last {days} days)."

    ranked = sorted(churn.items(), key=lambda x: x[1], reverse=True)[:top_n]
    lines = [f"Top {len(ranked)} churned files (last {days} days)\n"]
    lines.append(f"{'Commits':>7}  File")
    lines.append("-" * 60)
    for path, count in ranked:
        lines.append(f"{count:>7}  {path}")

    return "\n".join(lines)
