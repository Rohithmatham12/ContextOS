"""AST-level symbol extraction using tree-sitter.

Extracts function/class/method names from Python, TypeScript, and JavaScript
source files. Used by the context selector to rank files by symbol relevance
rather than just keyword overlap.

Falls back silently to an empty symbol list when tree-sitter is unavailable
or the file cannot be parsed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SymbolInfo:
    name: str
    kind: str  # "function" | "class" | "method"
    start_line: int
    end_line: int
    parent: str | None = None  # class name for methods


@dataclass
class FileSymbols:
    rel_path: str
    symbols: list[SymbolInfo] = field(default_factory=list)
    parse_error: bool = False

    def names(self) -> set[str]:
        return {s.name for s in self.symbols}

    def function_names(self) -> set[str]:
        return {s.name for s in self.symbols if s.kind in ("function", "method")}

    def class_names(self) -> set[str]:
        return {s.name for s in self.symbols if s.kind == "class"}


_SUPPORTED = {"python", "typescript", "javascript"}

_LANG_CACHE: dict[str, Any] = {}


def _get_parser(language: str) -> Any | None:
    """Return a cached tree-sitter Parser for the given language, or None."""
    if language in _LANG_CACHE:
        return _LANG_CACHE[language]

    try:
        from tree_sitter import Language, Parser

        if language == "python":
            import tree_sitter_python as _tspy

            raw = _tspy.language()
        elif language == "typescript":
            import tree_sitter_typescript as _tsts

            raw = _tsts.language_typescript()
        elif language == "javascript":
            import tree_sitter_javascript as _tsjs

            raw = _tsjs.language()
        else:
            _LANG_CACHE[language] = None
            return None

        parser = Parser(Language(raw))
        _LANG_CACHE[language] = parser
        return parser
    except Exception:
        _LANG_CACHE[language] = None
        return None


def extract_symbols(content: str, language: str, rel_path: str) -> FileSymbols:
    """Extract top-level and method symbols from source content."""
    result = FileSymbols(rel_path=rel_path)

    if language not in _SUPPORTED:
        return result

    parser = _get_parser(language)
    if parser is None:
        return result

    try:
        src = content.encode("utf-8", errors="replace")
        tree = parser.parse(src)
        if language == "python":
            _extract_python(tree.root_node, src, result)
        else:
            _extract_js_ts(tree.root_node, src, result)
    except Exception:
        result.parse_error = True

    return result


def _extract_python(
    node: Any, src: bytes, result: FileSymbols, parent: str | None = None
) -> None:
    """Walk Python AST, extract function_definition and class_definition nodes."""
    for child in node.children:
        if child.type == "function_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                kind = "method" if parent else "function"
                result.symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=kind,
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parent=parent,
                    )
                )
                _extract_python(child, src, result, parent=parent)

        elif child.type == "class_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                result.symbols.append(
                    SymbolInfo(
                        name=name,
                        kind="class",
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parent=parent,
                    )
                )
                body = child.child_by_field_name("body")
                if body:
                    _extract_python(body, src, result, parent=name)

        elif child.type not in ("decorated_definition",):
            _extract_python(child, src, result, parent=parent)

        elif child.type == "decorated_definition":
            _extract_python(child, src, result, parent=parent)


def _extract_js_ts(
    node: Any, src: bytes, result: FileSymbols, parent: str | None = None
) -> None:
    """Walk JS/TS AST, extract function and class declarations."""
    for child in node.children:
        if child.type in ("function_declaration", "function_expression", "arrow_function"):
            name_node = child.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                kind = "method" if parent else "function"
                result.symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=kind,
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parent=parent,
                    )
                )

        elif child.type == "class_declaration":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                result.symbols.append(
                    SymbolInfo(
                        name=name,
                        kind="class",
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parent=parent,
                    )
                )
                body = child.child_by_field_name("body")
                if body:
                    _extract_js_ts(body, src, result, parent=name)

        elif child.type == "method_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                result.symbols.append(
                    SymbolInfo(
                        name=name,
                        kind="method",
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parent=parent,
                    )
                )
        else:
            _extract_js_ts(child, src, result, parent=parent)


def extract_from_file(path: Path, language: str, rel_path: str) -> FileSymbols:
    """Read a file and extract its symbols. Returns empty FileSymbols on error."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        return extract_symbols(content, language, rel_path)
    except OSError:
        return FileSymbols(rel_path=rel_path, parse_error=True)


def symbol_score(file_symbols: FileSymbols, keywords: set[str]) -> float:
    """Score a file based on keyword overlap with its symbol names.

    Matches against symbol name tokens — camelCase and snake_case are split.
    A keyword matching a symbol name scores higher than a keyword in a comment.
    """
    if not file_symbols.symbols or not keywords:
        return 0.0

    total = 0.0
    for sym in file_symbols.symbols:
        sym_tokens = _tokenize_identifier(sym.name)
        matches = sym_tokens & keywords
        if matches:
            weight = 2.0 if sym.kind == "function" else 1.5 if sym.kind == "method" else 1.0
            total += weight * len(matches)

    return total


_SPLIT_RE = re.compile(r"[_\-]|(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _tokenize_identifier(name: str) -> set[str]:
    parts = _SPLIT_RE.split(name)
    return {p.lower() for p in parts if len(p) > 1}
