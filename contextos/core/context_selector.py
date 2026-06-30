"""Context selector — ranks files by task relevance and enforces a token budget."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contextos.core.dependency_graph import DependencyGraph, load_graph
from contextos.core.summarizer import FileSummary, load_summaries
from contextos.core.token_counter import estimate_tokens

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "and",
        "or",
        "but",
        "not",
        "if",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "we",
        "our",
        "you",
        "your",
        "i",
        "me",
        "my",
        "fix",
        "add",
        "implement",
        "create",
        "update",
        "change",
        "make",
        "get",
        "set",
        "use",
        "using",
        "when",
        "how",
        "what",
        "which",
        "need",
        "want",
        "also",
        "then",
        "now",
        "new",
        "old",
        "all",
        "some",
        "any",
        "more",
        "less",
        "file",
        "code",
        "function",
        "method",
        "class",
        "def",
        "var",
        "let",
        "const",
    }
)

# File-name patterns that are always safe and given a priority bonus
_PRIORITY_NAMES: frozenset[str] = frozenset(
    {
        "readme.md",
        "readme.rst",
        "readme.txt",
        "readme",
        "pyproject.toml",
        "package.json",
        "cargo.toml",
        "requirements.txt",
        ".env.example",
        ".env.sample",
        "makefile",
        "justfile",
        "dockerfile",
    }
)

# Secret/credential file patterns — full content is never included
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\.env$", re.IGNORECASE),
    re.compile(r"^\.env\.[^.]+$", re.IGNORECASE),  # .env.local, .env.prod, etc.
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"\.pfx$", re.IGNORECASE),
    re.compile(r"\.crt$", re.IGNORECASE),
    re.compile(r"id_rsa", re.IGNORECASE),
    re.compile(r"id_ecdsa", re.IGNORECASE),
    re.compile(r"id_ed25519", re.IGNORECASE),
)

# Env-file names that are SAFE to include (templates, not actual secrets)
_SAFE_ENV_NAMES: frozenset[str] = frozenset(
    {".env.example", ".env.sample", ".env.template", ".env.dist"}
)


# ---------------------------------------------------------------------------
# Configuration & data models
# ---------------------------------------------------------------------------


@dataclass
class SelectionConfig:
    budget: int = 8000
    path_weight: float = 2.0
    symbol_weight: float = 1.5
    keyword_weight: float = 1.0
    import_weight: float = 0.3
    readme_bonus: float = 0.3
    dep_factor: float = 0.4
    test_pair_bonus: float = 0.5
    memory_bonus: float = 0.15
    snippet_lines: int = 60
    min_score: float = 0.0
    no_source: bool = False  # summaries only — never include full files or snippets
    allow_sensitive: bool = False  # if True, skip redaction (dangerous — shows raw secrets)


@dataclass
class FileResult:
    rel_path: str
    score: float
    reasons: list[str]
    tokens: int
    content: str
    kind: str  # "full" | "snippet" | "summary"


@dataclass
class ContextSelection:
    task: str
    budget: int
    used_tokens: int
    selected: list[FileResult]
    excluded: list[str]  # paths excluded by budget or safety rules
    secret_warnings: list[str] = field(default_factory=list)  # redaction log
    repo_total_tokens: int = 0  # tokens if entire repo were sent (no ContextOS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "budget": self.budget,
            "used_tokens": self.used_tokens,
            "selected": [
                {
                    "rel_path": r.rel_path,
                    "score": round(r.score, 3),
                    "reasons": r.reasons,
                    "tokens": r.tokens,
                    "kind": r.kind,
                }
                for r in self.selected
            ],
            "excluded": self.excluded,
        }

    def render_markdown(self) -> str:
        lines: list[str] = [
            "# ContextOS Context Pack",
            "",
            f"**Task:** {self.task}",
            f"**Budget:** {self.budget:,} tokens  ",
            f"**Used:** {self.used_tokens:,} tokens ({len(self.selected)} files)",
            "",
            "---",
            "",
        ]
        for result in self.selected:
            lines += [
                f"## `{result.rel_path}` ({result.kind})",
                "",
                f"*Score: {result.score:.2f} — {'; '.join(result.reasons)}*",
                "",
                result.content,
                "",
            ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_context(
    task: str,
    contextos_dir: Path,
    repo_root: Path,
    *,
    config: SelectionConfig | None = None,
) -> ContextSelection:
    """Load scan data from *contextos_dir* and select task-relevant files."""
    cfg = config or SelectionConfig()
    summaries = _load_summaries_safe(contextos_dir)
    graph = _load_graph_safe(contextos_dir)
    memory = _load_text_safe(contextos_dir / "MEMORY.md")
    return _select(task, summaries, graph, memory, repo_root, cfg)


# ---------------------------------------------------------------------------
# Core selection logic (also callable directly in tests)
# ---------------------------------------------------------------------------


def _select(
    task: str,
    summaries: dict[str, FileSummary],
    graph: DependencyGraph,
    memory_content: str,
    repo_root: Path,
    config: SelectionConfig,
) -> ContextSelection:
    if not summaries:
        return ContextSelection(
            task=task,
            budget=config.budget,
            used_tokens=0,
            selected=[],
            excluded=[],
        )

    kw = _keywords(task)
    mem_paths = _extract_memory_paths(memory_content)

    # 1. Initial scoring (secret files tracked separately for excluded list)
    scores: dict[str, tuple[float, list[str]]] = {}
    secret_excluded: list[str] = []
    for rel_path, summary in summaries.items():
        if _is_secret(rel_path):
            secret_excluded.append(rel_path)
            continue
        score, reasons = _score_file(rel_path, summary, kw, mem_paths, config)
        scores[rel_path] = (score, reasons)

    # 2. Dependency expansion
    scores = _expand_deps(scores, graph, config)

    # 3. Test-file pairing
    scores = _pair_tests(scores, set(scores), config)

    # 4. Sort by score descending; drop below min_score
    ranked = sorted(
        [(p, s, r) for p, (s, r) in scores.items() if s >= config.min_score],
        key=lambda x: x[1],
        reverse=True,
    )

    # 5. Budget enforcement
    selected, budget_excluded, warnings = _enforce_budget(ranked, summaries, repo_root, config)

    # Rough repo total: ~4 chars/token, ~60 chars/line average
    repo_total = sum(s.line_count * 15 for s in summaries.values())

    return ContextSelection(
        task=task,
        budget=config.budget,
        used_tokens=sum(f.tokens for f in selected),
        selected=selected,
        excluded=secret_excluded + budget_excluded,
        secret_warnings=warnings,
        repo_total_tokens=repo_total,
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score_file(
    rel_path: str,
    summary: FileSummary,
    keywords: set[str],
    mem_paths: set[str],
    config: SelectionConfig,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if keywords:
        # Path segment matching
        path_tokens = _tokens(rel_path)
        path_hits = keywords & path_tokens
        if path_hits:
            score += len(path_hits) * config.path_weight
            reasons.append(f"path:{','.join(sorted(path_hits)[:4])}")

        # Symbol / export matching
        sym_tokens = {s.lower() for s in summary.exports + summary.symbols}
        sym_tokens -= _STOPWORDS
        sym_hits = keywords & sym_tokens
        if sym_hits:
            score += len(sym_hits) * config.symbol_weight
            reasons.append(f"symbol:{','.join(sorted(sym_hits)[:4])}")

        # Purpose / docstring matching
        desc = (summary.purpose + " " + summary.docstring).lower()
        desc_hits = keywords & (_tokens(desc) - _STOPWORDS)
        if desc_hits:
            score += len(desc_hits) * config.keyword_weight
            reasons.append(f"purpose:{','.join(sorted(desc_hits)[:4])}")

        # Import matching
        imp_tokens = {i.lower().split(".")[0] for i in summary.imports}
        imp_hits = keywords & imp_tokens
        if imp_hits:
            score += len(imp_hits) * config.import_weight
            reasons.append(f"imports:{','.join(sorted(imp_hits)[:4])}")

    # Priority bonus (README, pyproject.toml, …)
    if Path(rel_path).name.lower() in _PRIORITY_NAMES:
        score += config.readme_bonus
        reasons.append("priority:readme/config")

    # Memory mention bonus
    fname = Path(rel_path).name
    if rel_path in mem_paths or fname in mem_paths:
        score += config.memory_bonus
        reasons.append("memory:mentioned")

    return score, reasons


def _expand_deps(
    scores: dict[str, tuple[float, list[str]]],
    graph: DependencyGraph,
    config: SelectionConfig,
) -> dict[str, tuple[float, list[str]]]:
    """Boost files that are direct local dependencies of high-scoring files."""
    if not scores:
        return scores

    result = dict(scores)

    # Build forward adjacency (source → local targets)
    adj: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.kind == "local":
            adj.setdefault(edge.source, []).append(edge.target)

    # Threshold: only expand from files with score ≥ 30% of the max score
    max_score = max(s for s, _ in scores.values())
    threshold = max_score * 0.3

    for path, (score, _) in sorted(scores.items(), key=lambda x: x[1][0], reverse=True):
        if score <= 0 or score < threshold:
            continue
        for dep_path in adj.get(path, []):
            if dep_path not in result:
                continue  # dep not in summaries (binary, package, etc.)
            dep_score, dep_reasons = result[dep_path]
            boost = score * config.dep_factor
            result[dep_path] = (
                dep_score + boost,
                dep_reasons + [f"dep:{Path(path).name}"],
            )

    return result


def _pair_tests(
    scores: dict[str, tuple[float, list[str]]],
    all_paths: set[str],
    config: SelectionConfig,
) -> dict[str, tuple[float, list[str]]]:
    """Boost test files that correspond to high-scoring source files."""
    if not scores:
        return scores

    result = dict(scores)
    max_score = max(s for s, _ in scores.values())
    threshold = max_score * 0.3

    for path, (score, _) in list(scores.items()):
        if score <= 0 or score < threshold:
            continue
        p = Path(path)
        stem = p.stem
        parent = p.parent

        candidates = [
            str(parent / f"test_{stem}.py"),
            str(parent / f"{stem}_test.py"),
            str(Path("tests") / f"test_{stem}.py"),
            str(Path("tests") / parent / f"test_{stem}.py"),
            str(Path("test") / f"test_{stem}.py"),
        ]
        for candidate in candidates:
            # Normalise path separator
            candidate = candidate.replace("\\", "/")
            if candidate not in all_paths:
                continue
            cur_score, cur_reasons = result[candidate]
            result[candidate] = (
                cur_score + config.test_pair_bonus,
                cur_reasons + [f"test_pair:{Path(path).name}"],
            )

    return result


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


def _enforce_budget(
    ranked: list[tuple[str, float, list[str]]],
    summaries: dict[str, FileSummary],
    repo_root: Path,
    config: SelectionConfig,
) -> tuple[list[FileResult], list[str], list[str]]:
    from contextos.core.secret_detector import format_warning, redact_content

    selected: list[FileResult] = []
    excluded: list[str] = []
    all_warnings: list[str] = []
    remaining = config.budget

    for rel_path, score, reasons in ranked:
        if remaining <= 0:
            excluded.append(rel_path)
            continue

        if _is_secret(rel_path):
            excluded.append(rel_path)
            continue

        summary = summaries.get(rel_path)
        raw_content = None if config.no_source else _read_file(repo_root / rel_path)

        # Redact secrets from file content (unless explicitly allowed)
        full_content = raw_content
        if raw_content and not config.allow_sensitive:
            redacted, matches = redact_content(raw_content)
            if matches:
                full_content = redacted
                for m in matches:
                    all_warnings.append(f"{rel_path}:{format_warning(m)}")

        result: FileResult | None = None

        # --- Try full file ---
        if full_content is not None:
            full_tok = estimate_tokens(full_content)
            if full_tok <= remaining:
                result = FileResult(
                    rel_path=rel_path,
                    score=score,
                    reasons=reasons,
                    tokens=full_tok,
                    content=_wrap_code(rel_path, full_content),
                    kind="full",
                )

        # --- Try snippet ---
        if result is None and full_content is not None:
            lines = full_content.splitlines()
            snip_lines = lines[: config.snippet_lines]
            snip = "\n".join(snip_lines)
            snip_tok = estimate_tokens(snip)
            if snip_tok <= remaining:
                note = f"snippet: first {len(snip_lines)} of {len(lines)} lines"
                result = FileResult(
                    rel_path=rel_path,
                    score=score,
                    reasons=reasons,
                    tokens=snip_tok,
                    content=_wrap_code(rel_path, snip, note=note),
                    kind="snippet",
                )

        # --- Try summary ---
        if result is None and summary is not None:
            summary_text = _render_summary(summary)
            sum_tok = estimate_tokens(summary_text)
            if sum_tok <= remaining:
                result = FileResult(
                    rel_path=rel_path,
                    score=score,
                    reasons=reasons,
                    tokens=sum_tok,
                    content=summary_text,
                    kind="summary",
                )

        if result is not None:
            selected.append(result)
            remaining -= result.tokens
        else:
            excluded.append(rel_path)

    return selected, excluded, all_warnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _keywords(task: str) -> set[str]:
    """Extract meaningful keywords from a task description."""
    raw = re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", task)
    expanded: set[str] = set()
    for word in raw:
        expanded.add(word.lower())
        # Split camelCase / PascalCase fragments
        for part in re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", word):
            if len(part) >= 3:
                expanded.add(part.lower())
    return {w for w in expanded if len(w) >= 3 and w not in _STOPWORDS}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", text.lower()))


def _is_secret(rel_path: str) -> bool:
    name = Path(rel_path).name.lower()
    if name in _SAFE_ENV_NAMES:
        return False
    return any(pat.search(name) for pat in _SECRET_PATTERNS)


def _extract_memory_paths(memory_content: str) -> set[str]:
    """Extract file paths mentioned in MEMORY.md."""
    paths: set[str] = set()
    for m in re.finditer(r"`([^`]+\.[a-zA-Z]{1,10})`", memory_content):
        paths.add(m.group(1))
    for m in re.finditer(r'"([^"]+\.[a-zA-Z]{1,10})"', memory_content):
        paths.add(m.group(1))
    return paths


def _render_summary(summary: FileSummary) -> str:
    lines = [f"### `{summary.rel_path}` ({summary.language}, summary)", ""]
    if summary.purpose:
        lines.append(f"- **Purpose:** {summary.purpose}")
    if summary.exports:
        lines.append(f"- **Exports:** {', '.join(f'`{e}`' for e in summary.exports[:8])}")
    if summary.symbols:
        lines.append(f"- **Symbols:** {', '.join(summary.symbols[:8])}")
    if summary.imports:
        lines.append(f"- **Imports:** {', '.join(summary.imports[:8])}")
    if summary.docstring:
        lines.append(f"- **Doc:** {summary.docstring[:200]}")
    lines.append("")
    return "\n".join(lines)


def _wrap_code(rel_path: str, content: str, *, note: str = "") -> str:
    ext = Path(rel_path).suffix.lstrip(".") or "text"
    header = f"### `{rel_path}`" + (f" ({note})" if note else "")
    return f"{header}\n```{ext}\n{content}\n```\n"


def _read_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _load_summaries_safe(contextos_dir: Path) -> dict[str, FileSummary]:
    path = contextos_dir / "file_summaries.json"
    if not path.exists():
        return {}
    try:
        return load_summaries(path)
    except Exception:  # noqa: BLE001
        return {}


def _load_graph_safe(contextos_dir: Path) -> DependencyGraph:
    path = contextos_dir / "dependency_graph.json"
    if not path.exists():
        return DependencyGraph(nodes=[], edges=[], unresolved={}, cycles=[])
    try:
        return load_graph(path)
    except Exception:  # noqa: BLE001
        return DependencyGraph(nodes=[], edges=[], unresolved={}, cycles=[])


def _load_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
