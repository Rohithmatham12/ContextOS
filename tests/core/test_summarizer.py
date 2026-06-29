"""Tests for contextos/core/summarizer.py — deterministic file summarization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from textwrap import dedent

import pytest

from contextos.core.scanner import FileEntry, scan
from contextos.core.summarizer import (
    FileSummary,
    load_summaries,
    summarize_file,
    summarize_repo,
    write_summaries,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(tmp_path: Path, filename: str, content: str, language: str) -> tuple[FileEntry, str]:
    """Write *content* to tmp_path/<filename> and return (FileEntry, content)."""
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    raw = content.encode()
    return (
        FileEntry(
            path=path,
            rel_path=filename,
            extension=Path(filename).suffix.lower(),
            size=len(raw),
            line_count=len(content.splitlines()),
            language=language,
            content_hash=hashlib.sha256(raw).hexdigest(),
        ),
        content,
    )


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

PYTHON_MODULE = dedent(
    '''\
    """A utility module for demo purposes."""

    import os
    import sys
    from pathlib import Path
    from typing import Optional

    VERSION = "1.0"
    MAX_RETRIES = 3
    _internal = "ignored"

    class MyClass:
        """A test class."""

        def method(self) -> None:
            pass

    async def async_func() -> None:
        """An async helper."""
        pass

    def public_func(x: int) -> str:
        return str(x)

    def _private_func() -> None:
        pass
    '''
)


class TestSummarizePython:
    def test_docstring_extracted(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "utils.py", PYTHON_MODULE, "Python")
        s = summarize_file(entry, content)
        assert s.docstring == "A utility module for demo purposes."

    def test_imports_extracted(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "utils.py", PYTHON_MODULE, "Python")
        s = summarize_file(entry, content)
        assert "os" in s.imports
        assert "sys" in s.imports
        assert "pathlib" in s.imports
        assert "typing" in s.imports

    def test_public_functions_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "utils.py", PYTHON_MODULE, "Python")
        s = summarize_file(entry, content)
        assert "def public_func" in s.exports
        assert "async def async_func" in s.exports

    def test_private_function_not_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "utils.py", PYTHON_MODULE, "Python")
        s = summarize_file(entry, content)
        assert not any("_private_func" in e for e in s.exports)

    def test_class_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "utils.py", PYTHON_MODULE, "Python")
        s = summarize_file(entry, content)
        assert "class MyClass" in s.exports

    def test_upper_case_constants_in_symbols(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "utils.py", PYTHON_MODULE, "Python")
        s = summarize_file(entry, content)
        assert "VERSION" in s.symbols
        assert "MAX_RETRIES" in s.symbols

    def test_all_symbols_present(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "utils.py", PYTHON_MODULE, "Python")
        s = summarize_file(entry, content)
        assert "MyClass" in s.symbols
        assert "public_func" in s.symbols
        assert "async_func" in s.symbols

    def test_purpose_main(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "main.py", "pass\n", "Python")
        s = summarize_file(entry, content)
        assert s.purpose == "application entry point"

    def test_purpose_test_file_from_prefix(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "test_utils.py", "pass\n", "Python")
        s = summarize_file(entry, content)
        assert s.purpose == "test file"

    def test_purpose_test_file_from_dir(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "tests/helper.py", "pass\n", "Python")
        s = summarize_file(entry, content)
        assert s.purpose == "test file"

    def test_purpose_init(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "__init__.py", "pass\n", "Python")
        s = summarize_file(entry, content)
        assert s.purpose == "package initializer"

    def test_syntax_error_fallback(self, tmp_path: Path) -> None:
        bad = "def broken(\n    x: int\n # missing closing paren\n"
        entry, content = _entry(tmp_path, "broken.py", bad, "Python")
        s = summarize_file(entry, content)
        # Should not raise; symbols may be empty or partial
        assert isinstance(s.symbols, list)
        assert isinstance(s.imports, list)

    def test_metadata_from_entry(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "utils.py", PYTHON_MODULE, "Python")
        s = summarize_file(entry, content)
        assert s.line_count == entry.line_count
        assert s.content_hash == entry.content_hash
        assert s.language == "Python"
        assert s.rel_path == "utils.py"

    def test_empty_file(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "empty.py", "", "Python")
        s = summarize_file(entry, content)
        assert s.docstring == ""
        assert s.imports == []
        assert s.exports == []

    def test_imports_sorted_unique(self, tmp_path: Path) -> None:
        src = "import os\nimport os\nimport sys\n"
        entry, content = _entry(tmp_path, "dup.py", src, "Python")
        s = summarize_file(entry, content)
        assert s.imports == sorted(set(s.imports))
        assert len(s.imports) == len(set(s.imports))


# ---------------------------------------------------------------------------
# JavaScript / TypeScript
# ---------------------------------------------------------------------------

JS_MODULE = dedent(
    """\
    // Main application module
    import React from 'react';
    import { useState, useEffect } from 'react';
    const fs = require('fs');

    export function main() {
      return 'hello';
    }

    export class AppComponent {
      render() {}
    }

    export const VERSION = '2.0';

    function internalHelper() {}

    class PrivateClass {}
    """
)

TS_MODULE = dedent(
    """\
    // TypeScript service module
    import { Observable } from 'rxjs';
    import type { Config } from './config';

    export interface IService {
      start(): void;
    }

    export type Handler = (req: unknown) => void;

    export class ServiceImpl {
      start(): void {}
    }

    export async function bootstrap(): Promise<void> {}
    """
)


class TestSummarizeJavaScript:
    def test_docstring_from_comment(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "app.js", JS_MODULE, "JavaScript")
        s = summarize_file(entry, content)
        assert s.docstring == "Main application module"

    def test_imports_extracted(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "app.js", JS_MODULE, "JavaScript")
        s = summarize_file(entry, content)
        assert "react" in s.imports
        assert "fs" in s.imports

    def test_exported_function_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "app.js", JS_MODULE, "JavaScript")
        s = summarize_file(entry, content)
        assert "function main" in s.exports

    def test_exported_class_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "app.js", JS_MODULE, "JavaScript")
        s = summarize_file(entry, content)
        assert "class AppComponent" in s.exports

    def test_exported_const_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "app.js", JS_MODULE, "JavaScript")
        s = summarize_file(entry, content)
        assert "const VERSION" in s.exports

    def test_internal_symbols_captured(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "app.js", JS_MODULE, "JavaScript")
        s = summarize_file(entry, content)
        assert "internalHelper" in s.symbols or "PrivateClass" in s.symbols

    def test_purpose_javascript_module(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "helper.js", JS_MODULE, "JavaScript")
        s = summarize_file(entry, content)
        assert "JavaScript" in s.purpose or s.purpose == "helper functions"


class TestSummarizeTypeScript:
    def test_docstring_from_comment(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "service.ts", TS_MODULE, "TypeScript")
        s = summarize_file(entry, content)
        assert s.docstring == "TypeScript service module"

    def test_imports_extracted(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "service.ts", TS_MODULE, "TypeScript")
        s = summarize_file(entry, content)
        assert "rxjs" in s.imports
        assert "./config" in s.imports

    def test_interface_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "service.ts", TS_MODULE, "TypeScript")
        s = summarize_file(entry, content)
        assert "type IService" in s.exports

    def test_type_alias_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "service.ts", TS_MODULE, "TypeScript")
        s = summarize_file(entry, content)
        assert "type Handler" in s.exports

    def test_async_function_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "service.ts", TS_MODULE, "TypeScript")
        s = summarize_file(entry, content)
        assert "function bootstrap" in s.exports

    def test_class_in_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "service.ts", TS_MODULE, "TypeScript")
        s = summarize_file(entry, content)
        assert "class ServiceImpl" in s.exports


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

MD_CONTENT = dedent(
    """\
    # My Awesome Project

    A brief description of what this does.

    ## Installation

    Run pip install.

    ## Usage

    Call main().

    ### Advanced Usage

    For power users.
    """
)


class TestSummarizeMarkdown:
    def test_docstring_is_first_heading(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "README.md", MD_CONTENT, "Markdown")
        s = summarize_file(entry, content)
        assert s.docstring == "My Awesome Project"

    def test_headings_in_symbols(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "README.md", MD_CONTENT, "Markdown")
        s = summarize_file(entry, content)
        assert "My Awesome Project" in s.symbols
        assert "Installation" in s.symbols
        assert "Usage" in s.symbols
        assert "Advanced Usage" in s.symbols

    def test_no_imports_or_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "README.md", MD_CONTENT, "Markdown")
        s = summarize_file(entry, content)
        assert s.imports == []
        assert s.exports == []

    def test_purpose_readme(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "README.md", MD_CONTENT, "Markdown")
        s = summarize_file(entry, content)
        assert s.purpose == "project readme"

    def test_plain_paragraph_as_docstring(self, tmp_path: Path) -> None:
        content = "No headings here.\n\nJust paragraphs.\n"
        entry, c = _entry(tmp_path, "notes.md", content, "Markdown")
        s = summarize_file(entry, c)
        assert s.docstring == "No headings here."


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

PACKAGE_JSON = json.dumps(
    {
        "name": "my-app",
        "version": "1.2.3",
        "description": "A sample application",
        "scripts": {"build": "tsc", "test": "jest"},
        "dependencies": {"react": "^18.0.0"},
    },
    indent=2,
)

GENERIC_JSON = json.dumps({"host": "localhost", "port": 5432, "database": "mydb"}, indent=2)


class TestSummarizeJSON:
    def test_top_level_keys_as_symbols(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "db.json", GENERIC_JSON, "JSON")
        s = summarize_file(entry, content)
        assert "host" in s.symbols
        assert "port" in s.symbols
        assert "database" in s.symbols

    def test_package_json_docstring(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "package.json", PACKAGE_JSON, "JSON")
        s = summarize_file(entry, content)
        assert s.docstring == "A sample application"

    def test_package_json_purpose(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "package.json", PACKAGE_JSON, "JSON")
        s = summarize_file(entry, content)
        assert s.purpose == "npm package manifest"

    def test_invalid_json_graceful(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "bad.json", "{not valid json}", "JSON")
        s = summarize_file(entry, content)
        assert s.symbols == []
        assert s.docstring == ""

    def test_array_json_indexed_symbols(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "list.json", '["a","b","c"]', "JSON")
        s = summarize_file(entry, content)
        assert "[0]" in s.symbols


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------

YAML_CONTENT = dedent(
    """\
    version: "3.8"
    services:
      web:
        image: nginx
        ports:
          - "80:80"
      db:
        image: postgres
    volumes:
      data:
    networks:
      frontend:
    """
)


class TestSummarizeYAML:
    def test_top_level_keys_as_symbols(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "docker-compose.yml", YAML_CONTENT, "YAML")
        s = summarize_file(entry, content)
        assert "version" in s.symbols
        assert "services" in s.symbols
        assert "volumes" in s.symbols
        assert "networks" in s.symbols

    def test_nested_keys_not_included(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "docker-compose.yml", YAML_CONTENT, "YAML")
        s = summarize_file(entry, content)
        # "web", "db", "image", "ports" are nested — should NOT appear
        assert "image" not in s.symbols

    def test_no_imports_or_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "config.yaml", YAML_CONTENT, "YAML")
        s = summarize_file(entry, content)
        assert s.imports == []
        assert s.exports == []

    def test_purpose_yaml_config(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "config.yaml", YAML_CONTENT, "YAML")
        s = summarize_file(entry, content)
        assert "YAML" in s.purpose or "configuration" in s.purpose


# ---------------------------------------------------------------------------
# TOML
# ---------------------------------------------------------------------------

PYPROJECT_TOML = dedent(
    """\
    [project]
    name = "myapp"
    version = "0.1.0"
    description = "My demo project"
    requires-python = ">=3.11"

    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"

    [tool.ruff]
    line-length = 100

    [tool.pytest.ini_options]
    testpaths = ["tests"]
    """
)

GENERIC_TOML = dedent(
    """\
    [database]
    host = "localhost"
    port = 5432

    [cache]
    backend = "redis"
    """
)


class TestSummarizeTOML:
    def test_top_level_keys_from_pyproject(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "pyproject.toml", PYPROJECT_TOML, "TOML")
        s = summarize_file(entry, content)
        assert "project" in s.symbols
        assert "build-system" in s.symbols or "build_system" in s.symbols

    def test_pyproject_docstring_from_description(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "pyproject.toml", PYPROJECT_TOML, "TOML")
        s = summarize_file(entry, content)
        assert s.docstring == "My demo project"

    def test_pyproject_purpose(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "pyproject.toml", PYPROJECT_TOML, "TOML")
        s = summarize_file(entry, content)
        assert s.purpose == "Python project config"

    def test_generic_toml_sections(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "config.toml", GENERIC_TOML, "TOML")
        s = summarize_file(entry, content)
        assert "database" in s.symbols
        assert "cache" in s.symbols

    def test_invalid_toml_fallback(self, tmp_path: Path) -> None:
        bad = "[broken\nkey = value\n"
        entry, content = _entry(tmp_path, "bad.toml", bad, "TOML")
        s = summarize_file(entry, content)
        # Fallback should not raise
        assert isinstance(s.symbols, list)


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------

SHELL_SCRIPT = dedent(
    """\
    #!/usr/bin/env bash
    # Main deployment script for production

    set -euo pipefail

    DB_URL="postgres://localhost/mydb"
    export APP_NAME="myapp"
    export MAX_WORKERS=4

    source ./lib/helpers.sh
    . ./lib/config.sh

    function deploy() {
      echo "Deploying ${APP_NAME}..."
    }

    cleanup() {
      echo "Cleaning up..."
    }

    function run_migrations() {
      echo "Running migrations..."
    }
    """
)


class TestSummarizeShell:
    def test_docstring_from_first_comment(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "deploy.sh", SHELL_SCRIPT, "Shell")
        s = summarize_file(entry, content)
        assert s.docstring == "Main deployment script for production"

    def test_functions_in_symbols(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "deploy.sh", SHELL_SCRIPT, "Shell")
        s = summarize_file(entry, content)
        assert "function deploy" in s.symbols
        assert "function cleanup" in s.symbols
        assert "function run_migrations" in s.symbols

    def test_upper_case_vars_in_symbols(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "deploy.sh", SHELL_SCRIPT, "Shell")
        s = summarize_file(entry, content)
        assert "DB_URL" in s.symbols or "APP_NAME" in s.symbols or "MAX_WORKERS" in s.symbols

    def test_source_imports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "deploy.sh", SHELL_SCRIPT, "Shell")
        s = summarize_file(entry, content)
        assert any("helpers" in imp or "config" in imp for imp in s.imports)

    def test_no_exports(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "deploy.sh", SHELL_SCRIPT, "Shell")
        s = summarize_file(entry, content)
        assert s.exports == []

    def test_shebang_not_in_docstring(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "run.sh", SHELL_SCRIPT, "Shell")
        s = summarize_file(entry, content)
        assert not s.docstring.startswith("#!")
        assert "bin" not in s.docstring


# ---------------------------------------------------------------------------
# Unknown / unsupported language
# ---------------------------------------------------------------------------


class TestSummarizeUnknown:
    def test_unknown_language_returns_empty(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "file.xyz", "some content\n", "Unknown")
        s = summarize_file(entry, content)
        assert s.imports == []
        assert s.exports == []
        assert s.symbols == []

    def test_metadata_still_populated(self, tmp_path: Path) -> None:
        entry, content = _entry(tmp_path, "file.xyz", "content\n", "Unknown")
        s = summarize_file(entry, content)
        assert s.rel_path == "file.xyz"
        assert s.language == "Unknown"
        assert s.line_count == entry.line_count


# ---------------------------------------------------------------------------
# FileSummary serialization
# ---------------------------------------------------------------------------


class TestFileSummarySerialization:
    def _make_summary(self) -> FileSummary:
        return FileSummary(
            rel_path="src/main.py",
            language="Python",
            purpose="application entry point",
            imports=["os", "sys"],
            exports=["def main"],
            symbols=["main", "VERSION"],
            docstring="Entry point.",
            line_count=20,
            content_hash="abc123",
        )

    def test_to_dict_round_trip(self) -> None:
        s = self._make_summary()
        d = s.to_dict()
        s2 = FileSummary.from_dict(d)
        assert s2.rel_path == s.rel_path
        assert s2.imports == s.imports
        assert s2.exports == s.exports
        assert s2.symbols == s.symbols
        assert s2.line_count == s.line_count

    def test_from_dict_missing_keys_graceful(self) -> None:
        s = FileSummary.from_dict({"rel_path": "a.py", "language": "Python"})
        assert s.imports == []
        assert s.exports == []
        assert s.docstring == ""
        assert s.line_count == 0


# ---------------------------------------------------------------------------
# write_summaries / load_summaries
# ---------------------------------------------------------------------------


class TestWriteLoadSummaries:
    def test_write_creates_valid_json(self, tmp_path: Path) -> None:
        summary = FileSummary(
            rel_path="a.py",
            language="Python",
            purpose="module",
            imports=["os"],
            exports=["def foo"],
            symbols=["foo"],
            docstring="Hello.",
            line_count=5,
            content_hash="abc",
        )
        out = tmp_path / "summaries.json"
        write_summaries({"a.py": summary}, out)
        raw = json.loads(out.read_text())
        assert "a.py" in raw
        assert raw["a.py"]["language"] == "Python"

    def test_round_trip(self, tmp_path: Path) -> None:
        summary = FileSummary(
            rel_path="b.py",
            language="Python",
            purpose="utility functions",
            imports=["pathlib"],
            exports=["class Foo"],
            symbols=["Foo", "BAR"],
            docstring="A module.",
            line_count=42,
            content_hash="deadbeef",
        )
        out = tmp_path / "out.json"
        write_summaries({"b.py": summary}, out)
        loaded = load_summaries(out)
        assert "b.py" in loaded
        s = loaded["b.py"]
        assert s.language == "Python"
        assert s.imports == ["pathlib"]
        assert s.exports == ["class Foo"]
        assert s.symbols == ["Foo", "BAR"]
        assert s.docstring == "A module."
        assert s.line_count == 42

    def test_output_sorted_by_rel_path(self, tmp_path: Path) -> None:
        def _s(name: str) -> FileSummary:
            return FileSummary(
                rel_path=name,
                language="Python",
                purpose="module",
                imports=[],
                exports=[],
                symbols=[],
                docstring="",
                line_count=1,
                content_hash="x",
            )

        out = tmp_path / "s.json"
        write_summaries({"z.py": _s("z.py"), "a.py": _s("a.py"), "m.py": _s("m.py")}, out)
        raw = json.loads(out.read_text())
        keys = list(raw.keys())
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# summarize_repo integration
# ---------------------------------------------------------------------------


class TestSummarizeRepo:
    def test_all_scanned_files_summarized(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text('"""Main."""\n\ndef run():\n    pass\n', encoding="utf-8")
        (tmp_path / "README.md").write_text("# My Project\n\nDocs here.\n", encoding="utf-8")
        result = scan(tmp_path)
        summaries = summarize_repo(result)
        assert set(summaries.keys()) == {f.rel_path for f in result.files}

    def test_writes_json_when_output_path_given(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        out = tmp_path / ".contextos" / "file_summaries.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        result = scan(tmp_path)
        summarize_repo(result, output_path=out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "app.py" in data

    def test_no_output_when_path_none(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        out = tmp_path / "file_summaries.json"
        result = scan(tmp_path)
        summarize_repo(result)  # no output_path
        assert not out.exists()

    def test_mixed_file_types(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text('"""App."""\nimport os\n', encoding="utf-8")
        (tmp_path / "index.js").write_text(
            "// index\nexport function hello() {}\n", encoding="utf-8"
        )
        (tmp_path / "config.yaml").write_text("host: localhost\nport: 8080\n", encoding="utf-8")
        result = scan(tmp_path)
        summaries = summarize_repo(result)
        assert summaries["app.py"].language == "Python"
        assert summaries["index.js"].language == "JavaScript"
        assert summaries["config.yaml"].language == "YAML"

    def test_python_summary_correct(self, tmp_path: Path) -> None:
        src = '"""Utility functions."""\nimport os\n\ndef helper():\n    pass\n'
        (tmp_path / "utils.py").write_text(src, encoding="utf-8")
        result = scan(tmp_path)
        summaries = summarize_repo(result)
        s = summaries["utils.py"]
        assert s.docstring == "Utility functions."
        assert "os" in s.imports
        assert "def helper" in s.exports

    @pytest.mark.skipif(
        not hasattr(__builtins__, "__dict__"),
        reason="permission test environment check",
    )
    def test_empty_repo(self, tmp_path: Path) -> None:
        result = scan(tmp_path)
        summaries = summarize_repo(result)
        assert summaries == {}
