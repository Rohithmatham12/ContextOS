"""Safety utilities for the repository scanner."""

from __future__ import annotations

import fnmatch
from pathlib import Path

# Directories that are always skipped; never configurable away.
ALWAYS_EXCLUDE: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "coverage",
        ".next",
        ".turbo",
        "target",
        "vendor",
    }
)

LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".rb": "Ruby",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hxx": "C++",
    ".cs": "C#",
    ".php": "PHP",
    ".swift": "Swift",
    ".r": "R",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".json": "JSON",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".xml": "XML",
    ".md": "Markdown",
    ".mdx": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".tf": "Terraform",
    ".hcl": "HCL",
    ".lua": "Lua",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".lhs": "Haskell",
    ".clj": "Clojure",
    ".cljs": "Clojure",
    ".dart": "Dart",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protobuf",
    ".nix": "Nix",
    ".zig": "Zig",
}

_BINARY_CHECK_BYTES = 8192


def is_binary(data: bytes) -> bool:
    """Return True if *data* looks like a binary file (contains null bytes)."""
    return b"\x00" in data[:_BINARY_CHECK_BYTES]


def is_safe_symlink(path: Path, root: Path) -> bool:
    """Return True if symlink *path* resolves to a location inside *root*.

    Broken or unresolvable symlinks are treated as unsafe.
    """
    try:
        target = path.resolve()
        return target.is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def detect_language(path: Path) -> str:
    """Guess programming language from file name or extension."""
    name = path.name.lower()
    if name == "dockerfile":
        return "Dockerfile"
    if name == "makefile":
        return "Makefile"
    if name == "gemfile" or name == "rakefile":
        return "Ruby"
    if name in {".env", ".env.example", ".env.local"}:
        return "Env"
    return LANGUAGE_MAP.get(path.suffix.lower(), "Unknown")


def load_gitignore_patterns(root: Path) -> list[str]:
    """Load patterns from <root>/.gitignore. Returns [] if absent or unreadable."""
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return []
    try:
        text = gitignore.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    patterns: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        # Skip comments, blanks, and negation patterns (negations not implemented)
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue
        patterns.append(stripped)
    return patterns


def matches_gitignore(rel_str: str, patterns: list[str]) -> bool:
    """Return True if *rel_str* (path relative to repo root) matches any gitignore pattern."""
    name = Path(rel_str).name
    for pat in patterns:
        clean_pat = pat.rstrip("/")
        if fnmatch.fnmatch(rel_str, clean_pat):
            return True
        if fnmatch.fnmatch(name, clean_pat):
            return True
        # Handle patterns with directory component
        if "/" in clean_pat and fnmatch.fnmatch(rel_str, f"**/{clean_pat}"):
            return True
    return False
