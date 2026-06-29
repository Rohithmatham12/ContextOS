"""Dependency graph builder — extracts import edges from Python and JS/TS files."""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contextos.core.scanner import ScanResult

_JS_EXTENSIONS: tuple[str, ...] = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

# Matches: import [stuff] from 'module'  and  import 'side-effect'
_JS_IMPORT_FROM: re.Pattern[str] = re.compile(
    r"""import\s+(?:type\s+)?(?:[^'";\n]*?from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
# Matches: require('module')
_JS_REQUIRE: re.Pattern[str] = re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)""")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DGNode:
    id: str  # rel_path
    language: str


@dataclass
class DGEdge:
    source: str  # rel_path of importing file
    target: str  # rel_path (local) or package name (package)
    kind: str  # "local" | "package"
    raw_import: str  # truncated raw import string for traceability


@dataclass
class DependencyGraph:
    nodes: list[DGNode]
    edges: list[DGEdge]
    unresolved: dict[str, list[str]]  # {rel_path: [import_strings]}
    cycles: list[list[str]]  # detected circular chains

    def to_dict(self) -> dict[str, Any]:
        return {
            "_note": "Populated by `contextos scan`. Do not edit manually.",
            "nodes": [{"id": n.id, "language": n.language} for n in self.nodes],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "kind": e.kind,
                    "raw_import": e.raw_import,
                }
                for e in self.edges
            ],
            "unresolved": self.unresolved,
            "cycles": self.cycles,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DependencyGraph:
        nodes = [DGNode(id=n["id"], language=n.get("language", "")) for n in data.get("nodes", [])]
        edges = [
            DGEdge(
                source=e["source"],
                target=e["target"],
                kind=e.get("kind", ""),
                raw_import=e.get("raw_import", ""),
            )
            for e in data.get("edges", [])
        ]
        return cls(
            nodes=nodes,
            edges=edges,
            unresolved=data.get("unresolved", {}),
            cycles=data.get("cycles", []),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_graph(result: ScanResult) -> DependencyGraph:
    """Parse all files in *result* and return a dependency graph."""
    known_files: set[str] = {e.rel_path for e in result.files}
    all_edges: list[DGEdge] = []
    all_unresolved: dict[str, list[str]] = {}

    for entry in result.files:
        lang = entry.language
        if lang not in ("Python", "JavaScript", "TypeScript"):
            continue
        try:
            content = entry.path.read_text(encoding="utf-8")
        except OSError:
            continue

        if lang == "Python":
            edges, unresolved = _extract_python_deps(content, entry.rel_path, known_files)
        else:
            edges, unresolved = _extract_js_deps(content, entry.rel_path, known_files)

        all_edges.extend(edges)
        if unresolved:
            all_unresolved[entry.rel_path] = unresolved

    nodes = [DGNode(id=e.rel_path, language=e.language) for e in result.files]
    return DependencyGraph(
        nodes=nodes,
        edges=all_edges,
        unresolved=all_unresolved,
        cycles=_find_cycles(all_edges),
    )


def write_graph(graph: DependencyGraph, path: Path) -> None:
    """Write *graph* to *path* as pretty-printed JSON."""
    path.write_text(
        json.dumps(graph.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_graph(path: Path) -> DependencyGraph:
    """Load a graph previously written by :func:`write_graph`."""
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return DependencyGraph.from_dict(raw)


# ---------------------------------------------------------------------------
# Python extraction
# ---------------------------------------------------------------------------


def _extract_python_deps(
    content: str,
    rel_path: str,
    known_files: set[str],
) -> tuple[list[DGEdge], list[str]]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [], []

    edges: list[DGEdge] = []
    unresolved: list[str] = []
    seen_targets: set[str] = set()

    def _add(target: str, kind: str, raw: str) -> None:
        if target in seen_targets:
            return
        seen_targets.add(target)
        edges.append(DGEdge(source=rel_path, target=target, kind=kind, raw_import=raw))

    for node in tree.body:  # top-level statements only
        if isinstance(node, ast.Import):
            for alias in node.names:
                raw = f"import {alias.name}"
                local = _resolve_python_abs(alias.name, known_files)
                if local:
                    _add(local, "local", raw)
                else:
                    _add(alias.name.split(".")[0], "package", raw)

        elif isinstance(node, ast.ImportFrom):
            level = node.level
            module = node.module or ""

            if level > 0:
                if module:
                    # from .module import name
                    raw = f"from {'.' * level}{module} import ..."
                    base = _resolve_python_rel(module, level, rel_path)
                    local = _find_python_file(base, known_files)
                    if local:
                        _add(local, "local", raw)
                    else:
                        unresolved.append(f"{'.' * level}{module}")
                else:
                    # from . import name1, name2 — each name may be a submodule
                    for alias in node.names:
                        raw = f"from {'.' * level} import {alias.name}"
                        base = _resolve_python_rel(alias.name, level, rel_path)
                        local = _find_python_file(base, known_files)
                        if local:
                            _add(local, "local", raw)
                        # Not marked unresolved — alias may be a class/function
            else:
                raw = f"from {module} import ..." if module else "from  import ..."
                local = _resolve_python_abs(module, known_files) if module else None
                if local:
                    _add(local, "local", raw)
                else:
                    pkg = module.split(".")[0] if module else ""
                    if pkg:
                        _add(pkg, "package", raw)

    return edges, unresolved


def _resolve_python_abs(module: str, known_files: set[str]) -> str | None:
    """Map an absolute module name to a local file, or return None."""
    base = module.replace(".", "/")
    for candidate in (base + ".py", base + "/__init__.py"):
        if candidate in known_files:
            return candidate
    return None


def _resolve_python_rel(name: str, level: int, importing_file: str) -> str:
    """Compute the local file-path base for a relative Python import."""
    parts = importing_file.replace("\\", "/").split("/")
    # parts[-1] is the filename; level=1 → current package dir; level=2 → parent
    base_parts = parts[: max(0, len(parts) - level)]
    if name:
        return "/".join(base_parts + name.split("."))
    return "/".join(base_parts)


def _find_python_file(base: str, known_files: set[str]) -> str | None:
    for candidate in (base + ".py", base + "/__init__.py"):
        if candidate in known_files:
            return candidate
    return None


# ---------------------------------------------------------------------------
# JS/TS extraction
# ---------------------------------------------------------------------------


def _extract_js_deps(
    content: str,
    rel_path: str,
    known_files: set[str],
) -> tuple[list[DGEdge], list[str]]:
    edges: list[DGEdge] = []
    unresolved: list[str] = []
    seen: set[str] = set()

    def _process(module: str, raw: str) -> None:
        if module in seen:
            return
        seen.add(module)
        if module.startswith((".", "/")):
            local = _resolve_js_import(module, rel_path, known_files)
            if local:
                edges.append(
                    DGEdge(source=rel_path, target=local, kind="local", raw_import=raw[:120])
                )
            else:
                unresolved.append(module)
        else:
            pkg = module.split("/")[0]  # strip subpath ("react-dom/client" → "react-dom")
            edges.append(DGEdge(source=rel_path, target=pkg, kind="package", raw_import=raw[:120]))

    for m in _JS_IMPORT_FROM.finditer(content):
        _process(m.group(1), m.group(0))
    for m in _JS_REQUIRE.finditer(content):
        _process(m.group(1), m.group(0))

    return edges, unresolved


def _resolve_js_import(module: str, importing_file: str, known_files: set[str]) -> str | None:
    """Resolve a relative/absolute JS import string to a known file path."""
    import_dir = str(Path(importing_file).parent)
    if import_dir == ".":
        import_dir = ""

    if module.startswith("/"):
        base = module.lstrip("/")
    else:
        raw_path = os.path.join(import_dir, module) if import_dir else module
        base = os.path.normpath(raw_path).replace("\\", "/").lstrip("/")
        if base == ".":
            base = ""

    candidates: list[str] = [
        base,
        *(base + ext for ext in _JS_EXTENSIONS),
        *(base + "/index" + ext for ext in _JS_EXTENSIONS),
    ]
    return next((c for c in candidates if c in known_files), None)


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def _find_cycles(edges: list[DGEdge]) -> list[list[str]]:
    """Detect cycles in the local import graph using recursive DFS."""
    adj: dict[str, list[str]] = {}
    for edge in edges:
        if edge.kind == "local":
            adj.setdefault(edge.source, []).append(edge.target)

    all_nodes = set(adj.keys()) | {t for ts in adj.values() for t in ts}
    visited: set[str] = set()
    in_stack: set[str] = set()
    seen_keys: set[frozenset[str]] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        in_stack.add(node)
        path.append(node)

        for neighbor in sorted(adj.get(node, [])):
            if neighbor in in_stack:
                idx = path.index(neighbor)
                cycle = path[idx:] + [neighbor]
                key = frozenset(cycle)
                if key not in seen_keys:
                    seen_keys.add(key)
                    cycles.append(cycle)
            elif neighbor not in visited:
                dfs(neighbor, path)

        path.pop()
        in_stack.discard(node)

    for node in sorted(all_nodes):
        if node not in visited:
            dfs(node, [])

    return cycles
