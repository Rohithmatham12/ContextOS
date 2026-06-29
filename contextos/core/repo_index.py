"""Repository index builder — generates PROJECT_INDEX.md from scan + summary data."""

from __future__ import annotations

import json
import tomllib
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contextos.core.scanner import ScanResult
from contextos.core.summarizer import FileSummary

# ---------------------------------------------------------------------------
# Detection tables
# ---------------------------------------------------------------------------

# (marker_filename, package_manager_label)  — first match wins
_PM_MARKERS: list[tuple[str, str]] = [
    ("poetry.lock", "poetry"),
    ("Pipfile", "pipenv"),
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("package.json", "npm"),
    ("requirements.txt", "pip"),
    ("pyproject.toml", "pip/pyproject"),
    ("Cargo.toml", "cargo"),
    ("go.mod", "go modules"),
    ("Gemfile", "bundler"),
    ("composer.json", "composer"),
    ("pom.xml", "maven"),
    ("build.gradle", "gradle"),
    ("build.gradle.kts", "gradle"),
]

# import-prefix → framework label
_FRAMEWORK_IMPORTS: dict[str, str] = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "aiohttp": "aiohttp",
    "sanic": "Sanic",
    "typer": "Typer",
    "click": "Click",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    "celery": "Celery",
    "pydantic": "Pydantic",
    "pytest": "pytest",
    "redis": "Redis",
    "boto3": "AWS SDK (boto3)",
    "react": "React",
    "vue": "Vue.js",
    "@angular": "Angular",
    "next": "Next.js",
    "@nestjs": "NestJS",
    "express": "Express",
    "svelte": "Svelte",
    "astro": "Astro",
    "vite": "Vite",
    "jest": "Jest",
    "vitest": "Vitest",
    "prisma": "Prisma",
    "mongoose": "Mongoose",
    "graphql": "GraphQL",
    "tailwindcss": "Tailwind CSS",
    "nuxt": "Nuxt.js",
    "remix": "Remix",
    "trpc": "tRPC",
    "zod": "Zod",
}

# Config files safe to report (no secrets)
_CONFIG_FILE_NAMES: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
        "mypy.ini",
        ".mypy.ini",
        ".flake8",
        "ruff.toml",
        ".ruff.toml",
        "tsconfig.json",
        "jsconfig.json",
        ".eslintrc",
        ".eslintrc.json",
        ".eslintrc.js",
        ".eslintrc.yaml",
        ".eslintrc.yml",
        ".prettierrc",
        ".prettierrc.json",
        ".prettierrc.js",
        "jest.config.js",
        "jest.config.ts",
        "vitest.config.ts",
        "vitest.config.js",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".gitignore",
        ".dockerignore",
        "Makefile",
        "makefile",
        "justfile",
        ".env.example",
        ".env.sample",
        ".env.template",
        ".pre-commit-config.yaml",
        "renovate.json",
        "codecov.yml",
        "codecov.yaml",
        ".github/dependabot.yml",
    }
)

_DIR_PURPOSES: dict[str, str] = {
    "src": "source code",
    "lib": "library code",
    "app": "application code",
    "core": "core logic",
    "api": "API layer",
    "models": "data models",
    "schemas": "schemas",
    "tests": "test suite",
    "test": "test suite",
    "spec": "test suite",
    "specs": "test suite",
    "__tests__": "test suite",
    "docs": "documentation",
    "doc": "documentation",
    "scripts": "utility scripts",
    "config": "configuration",
    "migrations": "database migrations",
    "services": "service layer",
    "utils": "utilities",
    "helpers": "helpers",
    "components": "UI components",
    "pages": "page components",
    "routes": "routing",
    "handlers": "request handlers",
    "controllers": "controllers",
    "middleware": "middleware",
    "static": "static assets",
    "assets": "assets",
    "public": "public files",
    "templates": "templates",
    "views": "views",
    "cli": "CLI commands",
    "commands": "commands",
    "plugins": "plugins",
    "hooks": "hooks",
    "types": "type definitions",
    "interfaces": "type definitions",
    "constants": "constants",
    "fixtures": "test fixtures",
    "cmd": "command entrypoints",
    "internal": "internal packages",
    "pkg": "packages",
    "bin": "binaries / scripts",
}

_ENTRYPOINT_NAMES: frozenset[str] = frozenset(
    {
        "main.py",
        "__main__.py",
        "app.py",
        "server.py",
        "run.py",
        "manage.py",
        "wsgi.py",
        "asgi.py",
        "index.js",
        "main.js",
        "server.js",
        "app.js",
        "index.ts",
        "main.ts",
        "server.ts",
        "app.ts",
        "main.go",
        "main.rs",
        "Program.cs",
        "main.c",
        "main.cpp",
    }
)

_TEST_DIR_NAMES: frozenset[str] = frozenset(
    {"tests", "test", "spec", "specs", "__tests__", "__test__"}
)


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass
class RepoIndex:
    project_name: str
    detected_languages: dict[str, int]
    package_managers: list[str]
    frameworks: list[str]
    important_dirs: list[tuple[str, int, str]]  # (dir_path, file_count, purpose)
    entrypoints: list[str]
    test_dirs: list[str]
    config_files: list[str]
    top_files: list[FileSummary]
    generated_at: str  # ISO timestamp, or "" to omit

    def render(self) -> str:
        """Render the index as a Markdown document."""
        out: list[str] = []

        out += [
            "# Project Index",
            "",
            "> Auto-generated by `contextos scan`. Run `contextos scan` to refresh.",
            "",
        ]

        # --- Project ---
        out += ["## Project", ""]
        out.append(f"- **Name:** {self.project_name}")
        if self.detected_languages:
            top = list(self.detected_languages.items())[:6]
            lang_str = ", ".join(f"{lang} ({n})" for lang, n in top)
            out.append(f"- **Languages:** {lang_str}")
        out.append("")

        # --- Package managers ---
        if self.package_managers:
            out += ["## Package Managers", ""]
            for pm in self.package_managers:
                out.append(f"- {pm}")
            out.append("")

        # --- Frameworks ---
        if self.frameworks:
            out += ["## Frameworks & Libraries", ""]
            for fw in self.frameworks:
                out.append(f"- {fw}")
            out.append("")

        # --- Directory structure ---
        if self.important_dirs:
            out += ["## Directory Structure", ""]
            out.append("| Directory | Files | Notes |")
            out.append("|-----------|------:|-------|")
            for d, count, purpose in self.important_dirs:
                out.append(f"| `{d}/` | {count} | {purpose} |")
            out.append("")

        # --- Entry points ---
        if self.entrypoints:
            out += ["## Entry Points", ""]
            for ep in self.entrypoints:
                out.append(f"- `{ep}`")
            out.append("")

        # --- Test locations ---
        if self.test_dirs:
            out += ["## Test Locations", ""]
            for td in self.test_dirs:
                out.append(f"- `{td}/`")
            out.append("")

        # --- Config files ---
        if self.config_files:
            out += ["## Configuration Files", ""]
            for cf in self.config_files:
                out.append(f"- `{cf}`")
            out.append("")

        # --- Key files ---
        if self.top_files:
            out += ["## Key Files", ""]
            out.append("| File | Language | Purpose |")
            out.append("|------|----------|---------|")
            for s in self.top_files:
                exports_str = ", ".join(s.exports[:3])
                purpose = s.purpose + (f" — {exports_str}" if exports_str else "")
                out.append(f"| `{s.rel_path}` | {s.language} | {purpose} |")
            out.append("")

        # --- Footer ---
        out.append("---")
        out.append("")
        note = "No secrets or source code included."
        if self.generated_at:
            note = f"Generated: {self.generated_at} · {note}"
        out.append(f"*{note}*")
        out.append("")

        return "\n".join(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_index(
    root: Path,
    result: ScanResult,
    summaries: dict[str, FileSummary],
    *,
    include_timestamp: bool = True,
) -> RepoIndex:
    """Build a RepoIndex from a completed scan and its file summaries."""
    root = root.resolve()

    entrypoints = _find_entrypoints(result, summaries)
    test_dirs = _find_test_dirs(result, summaries)

    return RepoIndex(
        project_name=_detect_project_name(root),
        detected_languages=result.language_counts(),
        package_managers=_detect_package_managers(root),
        frameworks=_detect_frameworks(summaries, root),
        important_dirs=_find_important_dirs(result),
        entrypoints=entrypoints,
        test_dirs=test_dirs,
        config_files=_find_config_files(result),
        top_files=_rank_top_files(summaries, set(entrypoints)),
        generated_at=(
            datetime.now(tz=UTC).isoformat(timespec="seconds") if include_timestamp else ""
        ),
    )


def write_project_index(index: RepoIndex, path: Path) -> None:
    """Write the rendered Markdown to *path*."""
    path.write_text(index.render(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _detect_project_name(root: Path) -> str:
    """Read project name from manifest files; fall back to directory name."""
    for loader in (_name_from_pyproject, _name_from_package_json, _name_from_cargo):
        name = loader(root)
        if name:
            return name
    return root.name


def _name_from_pyproject(root: Path) -> str:
    path = root / "pyproject.toml"
    if not path.exists():
        return ""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        project = data.get("project", {})
        if isinstance(project, dict):
            name = project.get("name")
            if isinstance(name, str) and name:
                return name
    except Exception:  # noqa: BLE001
        pass
    return ""


def _name_from_package_json(root: Path) -> str:
    path = root / "package.json"
    if not path.exists():
        return ""
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            name = data.get("name")
            if isinstance(name, str) and name:
                return name
    except Exception:  # noqa: BLE001
        pass
    return ""


def _name_from_cargo(root: Path) -> str:
    path = root / "Cargo.toml"
    if not path.exists():
        return ""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        pkg = data.get("package", {})
        if isinstance(pkg, dict):
            name = pkg.get("name")
            if isinstance(name, str) and name:
                return name
    except Exception:  # noqa: BLE001
        pass
    return ""


def _detect_package_managers(root: Path) -> list[str]:
    """Detect package managers from presence of marker files."""
    seen: set[str] = set()
    detected: list[str] = []
    for filename, label in _PM_MARKERS:
        if (root / filename).exists() and label not in seen:
            seen.add(label)
            detected.append(label)
    return detected


def _detect_frameworks(summaries: dict[str, FileSummary], root: Path) -> list[str]:
    """Infer frameworks from aggregated imports and config file presence."""
    all_imports: set[str] = set()
    for s in summaries.values():
        for imp in s.imports:
            all_imports.add(imp.lower())

    found: set[str] = set()
    for imp in all_imports:
        for prefix, label in _FRAMEWORK_IMPORTS.items():
            if imp == prefix or imp.startswith(prefix + ".") or imp.startswith(prefix + "/"):
                found.add(label)

    # Config-file signals that don't rely on import scanning
    _CFG_SIGNALS: dict[str, str] = {
        "next.config.js": "Next.js",
        "next.config.ts": "Next.js",
        "vite.config.ts": "Vite",
        "vite.config.js": "Vite",
        "angular.json": "Angular",
        "nuxt.config.ts": "Nuxt.js",
        "nuxt.config.js": "Nuxt.js",
        "astro.config.mjs": "Astro",
        "svelte.config.js": "Svelte",
        "remix.config.js": "Remix",
        "nest-cli.json": "NestJS",
    }
    for fname, label in _CFG_SIGNALS.items():
        if (root / fname).exists():
            found.add(label)

    return sorted(found)


def _find_important_dirs(result: ScanResult) -> list[tuple[str, int, str]]:
    """Return top-level directories sorted by file count (descending)."""
    counts: Counter[str] = Counter()
    for entry in result.files:
        parts = Path(entry.rel_path).parts
        if len(parts) > 1:
            counts[parts[0]] += 1

    dirs: list[tuple[str, int, str]] = []
    for d, count in counts.most_common():
        purpose = _DIR_PURPOSES.get(d.lower(), "")
        dirs.append((d, count, purpose))

    return dirs[:15]


def _find_entrypoints(result: ScanResult, summaries: dict[str, FileSummary]) -> list[str]:
    """Identify likely application entry points."""
    found: set[str] = set()
    for entry in result.files:
        fname = Path(entry.rel_path).name.lower()
        if fname in _ENTRYPOINT_NAMES:
            found.add(entry.rel_path)
    for rel_path, s in summaries.items():
        if s.purpose == "application entry point":
            found.add(rel_path)
    return sorted(found)[:10]


def _find_test_dirs(result: ScanResult, summaries: dict[str, FileSummary]) -> list[str]:
    """Find directories that contain tests."""
    dirs: set[str] = set()
    for entry in result.files:
        parts = Path(entry.rel_path).parts
        for i, part in enumerate(parts[:-1]):
            if part.lower() in _TEST_DIR_NAMES:
                dirs.add(str(Path(*parts[: i + 1])))
    for rel_path, s in summaries.items():
        if s.purpose == "test file":
            parts = Path(rel_path).parts
            if len(parts) > 1:
                dirs.add(parts[0])
    return sorted(dirs)[:10]


def _find_config_files(result: ScanResult) -> list[str]:
    """Collect config files safe to mention (no secrets)."""
    found: list[str] = []
    seen: set[str] = set()
    for entry in result.files:
        rel = entry.rel_path
        fname = Path(rel).name.lower()
        # Top-level config files
        if fname in _CONFIG_FILE_NAMES and rel not in seen:
            found.append(rel)
            seen.add(rel)
        # GitHub Actions workflows
        if rel.startswith(".github/workflows/") and rel.endswith((".yml", ".yaml")):
            if rel not in seen:
                found.append(rel)
                seen.add(rel)
    return sorted(found)


def _rank_top_files(
    summaries: dict[str, FileSummary],
    entrypoints: set[str],
    *,
    n: int = 12,
) -> list[FileSummary]:
    """Rank files by a simple relevance score and return top *n*."""

    def _score(s: FileSummary) -> float:
        return (
            (10.0 if s.rel_path in entrypoints else 0.0)
            + len(s.exports) * 1.0
            + len(s.symbols) * 0.5
            + len(s.imports) * 0.3
        )

    return sorted(summaries.values(), key=_score, reverse=True)[:n]
