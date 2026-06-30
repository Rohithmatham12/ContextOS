"""Pack builder — assemble a full context pack from scan data and task context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contextos import __version__
from contextos.core.context_selector import (
    ContextSelection,
    SelectionConfig,
    _load_graph_safe,
    _load_summaries_safe,
    _load_text_safe,
    _select,
)
from contextos.core.dependency_graph import DependencyGraph

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PACK_MD = "context_pack.md"
_PACK_JSON = "context_pack.json"

_AGENT_INSTRUCTIONS = """\
You are working on the task described above. The context files below are the \
most relevant parts of the codebase, selected to fit within a token budget.

- Follow existing code style and patterns.
- Only reference files shown in this pack unless you have strong evidence \
  they exist.
- If you need to edit a file shown only as a summary, ask for its full \
  content before making changes.
""".strip()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class PackConfig:
    budget: int = 8000
    include_tests: bool = True
    no_source: bool = False
    fmt: str = "md"  # "md" | "json"
    add_timestamp: bool = True
    allow_sensitive: bool = False  # if True, skip secret redaction (dangerous)
    compress: str | None = None  # compression provider name, e.g. "headroom"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_pack(
    task: str,
    repo_root: Path,
    contextos_dir: Path,
    *,
    config: PackConfig | None = None,
) -> tuple[str, ContextSelection]:
    """Build a context pack and return (rendered_content, selection).

    Always writes to *contextos_dir*/context_pack.{md,json} as a side effect.
    """
    cfg = config or PackConfig()

    # Ensure .contextos/ has scan data; run a fresh scan if missing.
    _ensure_scan(repo_root, contextos_dir)

    # Load summaries, optionally filtering test files.
    summaries = _load_summaries_safe(contextos_dir)
    if not cfg.include_tests:
        summaries = {p: s for p, s in summaries.items() if not _is_test_file(p)}

    graph = _load_graph_safe(contextos_dir)
    memory = _load_text_safe(contextos_dir / "MEMORY.md")

    sel_cfg = SelectionConfig(
        budget=cfg.budget,
        no_source=cfg.no_source,
        allow_sensitive=cfg.allow_sensitive,
    )
    selection = _select(task, summaries, graph, memory, repo_root, sel_cfg)

    # Load context documents.
    project_summary = _load_text_safe(contextos_dir / "PROJECT_INDEX.md")
    decisions = _load_text_safe(contextos_dir / "DECISIONS.md")

    # Timestamp.
    ts = datetime.now(tz=UTC).isoformat(timespec="seconds") if cfg.add_timestamp else ""

    # Dep notes for selected files.
    dep_notes = _build_dep_notes(selection, graph)

    # Render.
    if cfg.fmt == "json":
        content = _render_json(task, project_summary, decisions, selection, dep_notes, ts, cfg)
        out_name = _PACK_JSON
    else:
        content = _render_markdown(task, project_summary, decisions, selection, dep_notes, ts, cfg)
        out_name = _PACK_MD

    # Optional compression pass.
    if cfg.compress:
        from contextos.core.compression import get_provider

        provider = get_provider(cfg.compress)
        content = provider.compress(content, budget=cfg.budget)

    # Always persist to .contextos/.
    contextos_dir.mkdir(parents=True, exist_ok=True)
    (contextos_dir / out_name).write_text(content, encoding="utf-8")

    return content, selection


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _render_markdown(
    task: str,
    project_summary: str,
    decisions: str,
    selection: ContextSelection,
    dep_notes: str,
    timestamp: str,
    cfg: PackConfig,
) -> str:
    parts: list[str] = []

    # Header
    header_lines = ["# ContextOS Context Pack", ""]
    if timestamp:
        header_lines += [f"> Generated: {timestamp}  ", ""]
    if cfg.allow_sensitive:
        header_lines += [
            "> ⚠️  **WARNING: --allow-sensitive is active.**",
            "> Secrets and credentials may be present in this file. Handle with care.",
            "",
        ]
    parts.append("\n".join(header_lines))

    # Secret redaction notice
    if selection.secret_warnings and not cfg.allow_sensitive:
        warn_lines = [
            f"> ⚠️  **{len(selection.secret_warnings)} secret(s) detected and redacted.**",
            "> Values replaced with `[REDACTED_*]` tokens. Use `--allow-sensitive` to disable.",
        ]
        parts.append("\n".join(warn_lines) + "\n\n")

    # Task
    parts.append(_section("Task", task.strip()))

    # Project overview (optional)
    if project_summary.strip():
        content = _trim(project_summary, 600)
        parts.append(_section("Project Overview", content))

    # Relevant decisions (optional)
    if decisions.strip():
        content = _trim(decisions, 400)
        parts.append(_section("Relevant Decisions", content))

    # Context files
    if selection.selected:
        file_lines: list[str] = []
        for result in selection.selected:
            file_lines += [
                f"### `{result.rel_path}` ({result.kind})",
                "",
                f"*Score: {result.score:.2f} — {'; '.join(result.reasons) or 'no specific match'}*",
                "",
                result.content,
                "",
            ]
        parts.append(_section("Context Files", "\n".join(file_lines)))
    else:
        parts.append(_section("Context Files", "*No files selected within budget.*"))

    # Dependency notes (optional)
    if dep_notes.strip():
        parts.append(_section("Dependency Notes", dep_notes))

    # Token budget
    budget_lines = [
        "| Metric | Value |",
        "|--------|-------|",
        f"| Budget | {selection.budget:,} tokens |",
        f"| Used | {selection.used_tokens:,} tokens |",
        f"| Files selected | {len(selection.selected)} |",
        f"| Files excluded | {len(selection.excluded)} |",
    ]
    parts.append(_section("Token Budget", "\n".join(budget_lines)))

    # Excluded files
    if selection.excluded:
        excl_lines = ["| File | Note |", "|------|------|"]
        for p in selection.excluded:
            reason = "over budget" if not _is_secret_name(p) else "secret/credential file"
            excl_lines.append(f"| `{p}` | {reason} |")
        parts.append(_section("Excluded Files", "\n".join(excl_lines)))

    # Agent instructions
    parts.append(_section("Agent Instructions", _AGENT_INSTRUCTIONS))

    # Footer
    parts.append(f"---\n*Generated by ContextOS v{__version__}*\n")

    return "\n".join(parts)


def _render_json(
    task: str,
    project_summary: str,
    decisions: str,
    selection: ContextSelection,
    dep_notes: str,
    timestamp: str,
    cfg: PackConfig,
) -> str:
    data: dict[str, Any] = {
        "contextos_version": __version__,
        "generated": timestamp,
        "task": task,
        "budget": selection.budget,
        "used_tokens": selection.used_tokens,
        "project_summary": project_summary.strip(),
        "decisions": decisions.strip(),
        "selected": [
            {
                "rel_path": r.rel_path,
                "kind": r.kind,
                "score": round(r.score, 3),
                "reasons": r.reasons,
                "tokens": r.tokens,
                "content": r.content,
            }
            for r in selection.selected
        ],
        "excluded": [
            {
                "rel_path": p,
                "reason": "over budget" if not _is_secret_name(p) else "secret/credential",
            }
            for p in selection.excluded
        ],
        "dependency_notes": dep_notes,
        "agent_instructions": _AGENT_INSTRUCTIONS,
        "secret_warnings": selection.secret_warnings,
        "allow_sensitive": cfg.allow_sensitive,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.rstrip()}\n\n"


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit("\n", 1)[0] + "\n\n*[trimmed for token budget]*"


def _build_dep_notes(selection: ContextSelection, graph: DependencyGraph) -> str:
    if not selection.selected:
        return ""

    selected_paths = {r.rel_path for r in selection.selected}

    # Forward deps: source → [local targets in selection]
    forward: dict[str, list[str]] = {}
    # Reverse deps: target → [sources in selection]
    reverse: dict[str, list[str]] = {}

    for edge in graph.edges:
        if edge.kind != "local":
            continue
        if edge.source in selected_paths:
            forward.setdefault(edge.source, []).append(edge.target)
        if edge.target in selected_paths and edge.source in selected_paths:
            reverse.setdefault(edge.target, []).append(edge.source)

    if not forward and not reverse:
        return ""

    lines: list[str] = []
    seen: set[str] = set()
    for path in selected_paths:
        deps = forward.get(path, [])
        if deps:
            dep_str = ", ".join(f"`{d}`" for d in sorted(deps)[:6])
            lines.append(f"- `{path}` → imports {dep_str}")
            seen.add(path)
        importers = reverse.get(path, [])
        if importers and path not in seen:
            imp_str = ", ".join(f"`{i}`" for i in sorted(importers)[:6])
            lines.append(f"- `{path}` ← imported by {imp_str}")

    return "\n".join(lines[:20])  # cap at 20 entries


def _is_test_file(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    path = Path(normalized)
    name = path.name
    parts = path.parts
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "tests" in parts
        or "test" in parts
        or "__tests__" in parts
        or "spec" in parts
    )


def _is_secret_name(rel_path: str) -> bool:
    """Quick check used in excluded-files table (not the full _is_secret logic)."""
    name = Path(rel_path).name.lower()
    return name.startswith(".env") or "secret" in name or "credential" in name or "password" in name


def _ensure_scan(repo_root: Path, contextos_dir: Path) -> None:
    """Run a scan if scan data is missing or unreadable."""
    if _scan_data_valid(contextos_dir):
        return
    _run_scan(repo_root, contextos_dir)


def _scan_data_valid(contextos_dir: Path) -> bool:
    summaries_path = contextos_dir / "file_summaries.json"
    graph_path = contextos_dir / "dependency_graph.json"
    if not summaries_path.exists() or not graph_path.exists():
        return False

    from contextos.core.dependency_graph import load_graph
    from contextos.core.summarizer import load_summaries

    try:
        load_summaries(summaries_path)
        load_graph(graph_path)
    except Exception:  # noqa: BLE001
        return False
    return True


def _run_scan(repo_root: Path, contextos_dir: Path) -> None:
    from contextos.core.dependency_graph import build_graph, write_graph
    from contextos.core.scanner import ScanConfig, scan
    from contextos.core.summarizer import load_summaries, summarize_repo

    contextos_dir.mkdir(parents=True, exist_ok=True)
    cfg = ScanConfig(max_file_bytes=524288)
    result = scan(repo_root, cfg)

    from contextos.core.summarizer import FileSummary

    # Load existing summaries as cache — skip re-summarizing unchanged files
    existing: dict[str, FileSummary] | None = None
    summaries_path = contextos_dir / "file_summaries.json"
    if summaries_path.exists():
        try:
            existing = load_summaries(summaries_path)
        except Exception:  # noqa: BLE001
            existing = None

    summarize_repo(result, output_path=summaries_path, existing=existing)
    graph = build_graph(result)
    write_graph(graph, contextos_dir / "dependency_graph.json")
