"""Deterministic file summarizer — no LLM calls, pure static analysis."""

from __future__ import annotations

import ast
import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contextos.core.scanner import FileEntry, ScanResult

# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

_MAX_DOCSTRING = 500
_MAX_LIST = 50
_MAX_SYMBOLS_MD = 30


@dataclass
class FileSummary:
    rel_path: str
    language: str
    purpose: str
    imports: list[str]
    exports: list[str]  # typed as "def foo", "class Bar", "const X", "type T"
    symbols: list[str]  # all notable names (functions, classes, constants)
    docstring: str  # first meaningful comment or module docstring
    line_count: int
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rel_path": self.rel_path,
            "language": self.language,
            "purpose": self.purpose,
            "imports": self.imports,
            "exports": self.exports,
            "symbols": self.symbols,
            "docstring": self.docstring,
            "line_count": self.line_count,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileSummary:
        def _strs(key: str) -> list[str]:
            val = data.get(key, [])
            return [str(x) for x in val] if isinstance(val, list) else []

        return cls(
            rel_path=str(data.get("rel_path", "")),
            language=str(data.get("language", "")),
            purpose=str(data.get("purpose", "")),
            imports=_strs("imports"),
            exports=_strs("exports"),
            symbols=_strs("symbols"),
            docstring=str(data.get("docstring", "")),
            line_count=int(data.get("line_count") or 0),
            content_hash=str(data.get("content_hash", "")),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def summarize_file(entry: FileEntry, content: str) -> FileSummary:
    """Generate a deterministic, LLM-free summary for a single file."""
    rel = Path(entry.rel_path)
    extracted = _dispatch(entry.language, content, rel)
    return FileSummary(
        rel_path=entry.rel_path,
        language=entry.language,
        purpose=_guess_purpose(rel, entry.language),
        imports=extracted.imports[:_MAX_LIST],
        exports=extracted.exports[:_MAX_LIST],
        symbols=extracted.symbols[:_MAX_LIST],
        docstring=extracted.docstring[:_MAX_DOCSTRING],
        line_count=entry.line_count,
        content_hash=entry.content_hash,
    )


def summarize_repo(
    result: ScanResult,
    *,
    output_path: Path | None = None,
) -> dict[str, FileSummary]:
    """Summarize every file in *result*. Writes JSON to *output_path* if given."""
    summaries: dict[str, FileSummary] = {}
    for entry in result.files:
        try:
            content = entry.path.read_text(encoding="utf-8")
        except OSError:
            continue
        summaries[entry.rel_path] = summarize_file(entry, content)
    if output_path is not None:
        write_summaries(summaries, output_path)
    return summaries


def write_summaries(summaries: dict[str, FileSummary], path: Path) -> None:
    """Serialise *summaries* to a pretty-printed JSON file (sorted by rel_path)."""
    data = {k: v.to_dict() for k, v in sorted(summaries.items())}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_summaries(path: Path) -> dict[str, FileSummary]:
    """Load summaries previously written by :func:`write_summaries`."""
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return {k: FileSummary.from_dict(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _Extracted:
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    docstring: str = ""


def _dispatch(language: str, content: str, path: Path) -> _Extracted:
    _EXTRACTORS: dict[str, Any] = {
        "Python": _extract_python,
        "JavaScript": _extract_js,
        "TypeScript": _extract_js,
        "Markdown": _extract_markdown,
        "JSON": _extract_json,
        "YAML": _extract_yaml,
        "TOML": _extract_toml,
        "Shell": _extract_shell,
    }
    fn = _EXTRACTORS.get(language)
    return fn(content, path) if fn is not None else _Extracted()


# ---------------------------------------------------------------------------
# Language extractors
# ---------------------------------------------------------------------------


def _extract_python(content: str, path: Path) -> _Extracted:  # noqa: ARG001
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _extract_python_regex(content)

    imports: list[str] = []
    exports: list[str] = []
    symbols: list[str] = []
    docstring = ""

    # Module docstring: first statement is a bare string constant
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        first_line = tree.body[0].value.value.strip().partition("\n")[0]
        docstring = first_line

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(node.name)
            if not node.name.startswith("_"):
                kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                exports.append(f"{kind} {node.name}")
        elif isinstance(node, ast.ClassDef):
            symbols.append(node.name)
            if not node.name.startswith("_"):
                exports.append(f"class {node.name}")
            # Include public methods — they're the symbols most useful for task matching
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not child.name.startswith("_") or child.name in ("__init__", "__call__"):
                        symbols.append(child.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper() and len(target.id) > 1:
                    symbols.append(target.id)

    return _Extracted(
        imports=sorted(set(imports)),
        exports=sorted(set(exports)),
        symbols=sorted(set(symbols)),
        docstring=docstring,
    )


def _extract_python_regex(content: str) -> _Extracted:
    """Fallback when Python AST parse fails (syntax errors, encoding edge cases)."""
    imports: list[str] = []
    symbols: list[str] = []
    for m in re.finditer(r"^import\s+([\w.]+)", content, re.MULTILINE):
        imports.append(m.group(1))
    for m in re.finditer(r"^from\s+([\w.]+)\s+import", content, re.MULTILINE):
        imports.append(m.group(1))
    for m in re.finditer(r"^(?:def|class|async\s+def)\s+(\w+)", content, re.MULTILINE):
        symbols.append(m.group(1))
    return _Extracted(
        imports=sorted(set(imports)),
        exports=[],
        symbols=sorted(set(symbols)),
        docstring="",
    )


def _extract_js(content: str, path: Path) -> _Extracted:  # noqa: ARG001
    imports: list[str] = []
    exports: list[str] = []
    symbols: list[str] = []
    docstring = ""

    # Leading comment as docstring (single-line or block)
    for line in content.splitlines()[:30]:
        stripped = line.strip()
        if stripped.startswith("//"):
            text = stripped[2:].strip()
            if text and not docstring:
                docstring = text
                break
        if stripped.startswith("/*"):
            inner = re.sub(r"^/\*+\s*", "", stripped)
            inner = re.sub(r"\*+/$", "", inner).strip()
            if inner and not docstring:
                docstring = inner
                break
        if stripped and not stripped.startswith("*"):
            break

    # ES module imports
    for m in re.finditer(r'\bimport\b[^(].*?from\s+[\'"]([^\'"]+)[\'"]', content):
        imports.append(m.group(1))
    # Side-effect imports: import 'x'
    for m in re.finditer(r'\bimport\s+[\'"]([^\'"]+)[\'"]', content):
        imports.append(m.group(1))
    # CommonJS require
    for m in re.finditer(r'\brequire\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content):
        imports.append(m.group(1))

    # export function / export async function
    for m in re.finditer(
        r"^export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)", content, re.MULTILINE
    ):
        name = m.group(1)
        exports.append(f"function {name}")
        symbols.append(name)

    # export class
    for m in re.finditer(r"^export\s+(?:default\s+)?class\s+(\w+)", content, re.MULTILINE):
        name = m.group(1)
        exports.append(f"class {name}")
        symbols.append(name)

    # export const / let / var
    for m in re.finditer(r"^export\s+(?:const|let|var)\s+(\w+)", content, re.MULTILINE):
        name = m.group(1)
        exports.append(f"const {name}")
        symbols.append(name)

    # export type / interface (TypeScript)
    for m in re.finditer(r"^export\s+(?:type|interface)\s+(\w+)", content, re.MULTILINE):
        name = m.group(1)
        exports.append(f"type {name}")
        symbols.append(name)

    # Non-exported symbols
    for m in re.finditer(r"^(?:async\s+)?function\s+(\w+)\s*[\(<]", content, re.MULTILINE):
        symbols.append(m.group(1))
    for m in re.finditer(r"^class\s+(\w+)", content, re.MULTILINE):
        symbols.append(m.group(1))
    # UPPER_CASE constants
    for m in re.finditer(r"^(?:const|let|var)\s+([A-Z][A-Z0-9_]{1,})\s*=", content, re.MULTILINE):
        symbols.append(m.group(1))

    # Augment with tree-sitter for method-level symbols (optional dep)
    try:
        from contextos.core.ast_extractor import extract_symbols

        lang = "typescript" if path.suffix in (".ts", ".tsx") else "javascript"
        ast_syms = extract_symbols(content, lang, str(path))
        for sym in ast_syms.symbols:
            symbols.append(sym.name)
    except Exception:
        pass

    return _Extracted(
        imports=sorted(set(imports)),
        exports=sorted(set(exports)),
        symbols=sorted(set(symbols)),
        docstring=docstring,
    )


def _extract_markdown(content: str, path: Path) -> _Extracted:  # noqa: ARG001
    symbols: list[str] = []
    docstring = ""

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            if text:
                if not docstring:
                    docstring = text
                symbols.append(text)
        elif stripped and not docstring:
            docstring = stripped
            break

    return _Extracted(
        imports=[],
        exports=[],
        symbols=symbols[:_MAX_SYMBOLS_MD],
        docstring=docstring,
    )


def _extract_json(content: str, path: Path) -> _Extracted:
    symbols: list[str] = []
    docstring = ""

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return _Extracted()

    if isinstance(data, dict):
        symbols = [str(k) for k in data][:20]
        if path.name == "package.json":
            desc = data.get("description")
            name = data.get("name")
            version = data.get("version", "")
            if isinstance(desc, str) and desc:
                docstring = desc
            elif isinstance(name, str) and name:
                docstring = f"npm package: {name}" + (f" v{version}" if version else "")
    elif isinstance(data, list):
        symbols = [f"[{i}]" for i in range(min(len(data), 5))]

    return _Extracted(imports=[], exports=[], symbols=symbols, docstring=docstring)


def _extract_yaml(content: str, path: Path) -> _Extracted:  # noqa: ARG001
    """Extract top-level YAML keys via regex (no PyYAML dependency)."""
    symbols: list[str] = []
    seen: set[str] = set()
    # Lines at column 0 (no leading whitespace) ending with ':'
    for m in re.finditer(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:", content, re.MULTILINE):
        key = m.group(1)
        if key not in seen:
            seen.add(key)
            symbols.append(key)
        if len(symbols) >= 20:
            break
    return _Extracted(imports=[], exports=[], symbols=symbols, docstring="")


def _extract_toml(content: str, path: Path) -> _Extracted:
    symbols: list[str] = []
    docstring = ""

    try:
        data = tomllib.loads(content)
        symbols = [str(k) for k in data][:20]
        if path.name == "pyproject.toml":
            project = data.get("project", {})
            if isinstance(project, dict):
                desc = project.get("description")
                if isinstance(desc, str) and desc:
                    docstring = desc
    except tomllib.TOMLDecodeError:
        # Fallback: grab [section] header names
        seen: set[str] = set()
        for m in re.finditer(r"^\[([^\]]+)\]", content, re.MULTILINE):
            key = m.group(1).strip()
            if key not in seen:
                seen.add(key)
                symbols.append(key)

    return _Extracted(imports=[], exports=[], symbols=symbols, docstring=docstring)


_SHELL_KEYWORDS: frozenset[str] = frozenset(
    {"if", "while", "for", "do", "then", "else", "fi", "case", "esac", "in"}
)


def _extract_shell(content: str, path: Path) -> _Extracted:  # noqa: ARG001
    imports: list[str] = []
    symbols: list[str] = []
    docstring = ""

    # First comment after shebang
    for i, line in enumerate(content.splitlines()[:30]):
        stripped = line.strip()
        if i == 0 and stripped.startswith("#!"):
            continue
        if stripped.startswith("#"):
            text = stripped[1:].strip()
            if text and not docstring:
                docstring = text
        elif stripped:
            break

    # source / . imports
    for m in re.finditer(r"^(?:source\s+|[.]\s+)([^\s$#;]+)", content, re.MULTILINE):
        src = m.group(1).strip("\"'")
        if src:
            imports.append(src)

    # Function definitions: `name() {` or `function name() {`
    seen_symbols: dict[str, None] = {}  # ordered set via dict keys
    for m in re.finditer(r"^(?:function\s+)?(\w+)\s*\(\s*\)\s*\{", content, re.MULTILINE):
        name = m.group(1)
        if name not in _SHELL_KEYWORDS:
            key = f"function {name}"
            seen_symbols[key] = None

    # UPPER_CASE variable assignments
    for m in re.finditer(r"^(?:export\s+)?([A-Z_][A-Z0-9_]{1,})\s*=", content, re.MULTILINE):
        seen_symbols[m.group(1)] = None

    symbols = list(seen_symbols)[:30]

    return _Extracted(
        imports=sorted(set(imports)),
        exports=[],
        symbols=symbols,
        docstring=docstring,
    )


# ---------------------------------------------------------------------------
# Purpose inference
# ---------------------------------------------------------------------------

_SPECIFIC_FILES: dict[str, str] = {
    "readme.md": "project readme",
    "readme.rst": "project readme",
    "readme.txt": "project readme",
    "changelog.md": "changelog",
    "changes.md": "changelog",
    "license": "license file",
    "license.md": "license file",
    "license.txt": "license file",
    "makefile": "build automation",
    "justfile": "build automation",
    "dockerfile": "container definition",
    "docker-compose.yml": "container orchestration",
    "docker-compose.yaml": "container orchestration",
    "package.json": "npm package manifest",
    "package-lock.json": "npm lockfile",
    "yarn.lock": "yarn lockfile",
    "pyproject.toml": "Python project config",
    "setup.py": "Python project config",
    "setup.cfg": "Python project config",
    "cargo.toml": "Rust package manifest",
    "go.mod": "Go module definition",
    "go.sum": "Go dependency checksums",
    "tsconfig.json": "TypeScript config",
    "eslint.config.js": "ESLint config",
    ".eslintrc.json": "ESLint config",
    ".prettierrc": "Prettier config",
    ".gitignore": "git ignore rules",
    ".dockerignore": "Docker ignore rules",
    ".env": "environment variables",
    ".env.example": "environment variable template",
    ".env.local": "local environment variables",
    "conftest.py": "pytest configuration",
}

_STEM_PURPOSES: dict[str, str] = {
    "main": "application entry point",
    "__main__": "application entry point",
    "__init__": "package initializer",
    "app": "application root",
    "config": "configuration",
    "settings": "configuration",
    "constants": "constants",
    "const": "constants",
    "types": "type definitions",
    "interfaces": "type definitions",
    "models": "data models",
    "model": "data model",
    "schema": "schema definition",
    "schemas": "schema definitions",
    "utils": "utility functions",
    "util": "utility functions",
    "helpers": "helper functions",
    "helper": "helper functions",
    "cli": "CLI interface",
    "api": "API layer",
    "routes": "routing",
    "router": "routing",
    "views": "views/controllers",
    "controllers": "controllers",
    "auth": "authentication",
    "authentication": "authentication",
    "authorization": "authorization",
    "middleware": "middleware",
    "db": "database layer",
    "database": "database layer",
    "migrations": "database migrations",
    "migration": "database migration",
    "errors": "error definitions",
    "exceptions": "error definitions",
    "logging": "logging setup",
    "logger": "logging setup",
    "tasks": "task definitions",
    "celery": "task queue",
    "signals": "signal handlers",
    "serializers": "serializers",
    "validators": "validators",
    "permissions": "permission checks",
    "filters": "query filters",
    "decorators": "decorators",
    "hooks": "hooks",
    "plugins": "plugins",
    "registry": "registry",
    "factory": "factory",
    "fixtures": "test fixtures",
}

_LANG_FALLBACKS: dict[str, str] = {
    "Python": "Python module",
    "JavaScript": "JavaScript module",
    "TypeScript": "TypeScript module",
    "Markdown": "documentation",
    "JSON": "JSON data",
    "YAML": "YAML configuration",
    "TOML": "TOML configuration",
    "Shell": "shell script",
    "Dockerfile": "container definition",
    "Makefile": "build automation",
}

_TEST_DIR_NAMES: frozenset[str] = frozenset(
    {"tests", "test", "spec", "specs", "__tests__", "__test__"}
)
_DOCS_DIR_NAMES: frozenset[str] = frozenset({"docs", "doc", "documentation"})


def _guess_purpose(path: Path, language: str) -> str:
    """Infer file purpose from its relative path and language — no I/O."""
    full_name = path.name.lower()

    if full_name in _SPECIFIC_FILES:
        return _SPECIFIC_FILES[full_name]

    # Directory-based signals
    dir_names = {p.lower() for p in path.parts[:-1]}
    if dir_names & _TEST_DIR_NAMES:
        return "test file"
    if dir_names & _DOCS_DIR_NAMES:
        return "documentation"

    name = path.stem.lower()

    # Stem prefix/suffix patterns
    if name.startswith("test_") or name.endswith("_test") or name.endswith("_spec"):
        return "test file"
    if name.endswith("_test"):
        return "test file"

    if name in _STEM_PURPOSES:
        return _STEM_PURPOSES[name]

    return _LANG_FALLBACKS.get(language, "source file")
