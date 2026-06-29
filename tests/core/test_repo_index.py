"""Tests for contextos/core/repo_index.py."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from contextos.cli.main import app
from contextos.core.repo_index import (
    RepoIndex,
    _detect_frameworks,
    _detect_package_managers,
    _detect_project_name,
    _find_config_files,
    _find_entrypoints,
    _find_important_dirs,
    _find_test_dirs,
    build_index,
    write_project_index,
)
from contextos.core.scanner import ScanResult, scan
from contextos.core.summarizer import FileSummary, summarize_repo

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _scan(root: Path) -> ScanResult:
    return scan(root)


def _summary(rel_path: str, language: str, imports: list[str], exports: list[str]) -> FileSummary:
    raw = b"content"
    return FileSummary(
        rel_path=rel_path,
        language=language,
        purpose="source file",
        imports=imports,
        exports=exports,
        symbols=[],
        docstring="",
        line_count=10,
        content_hash=hashlib.sha256(raw).hexdigest(),
    )


def _make_scan_result(root: Path) -> tuple[ScanResult, dict[str, FileSummary]]:
    result = _scan(root)
    summaries = summarize_repo(result)
    return result, summaries


# ---------------------------------------------------------------------------
# Project name detection
# ---------------------------------------------------------------------------


class TestDetectProjectName:
    def test_from_pyproject_toml(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "pyproject.toml",
            '[project]\nname = "my-package"\nversion = "1.0"\n',
        )
        assert _detect_project_name(tmp_path) == "my-package"

    def test_from_package_json(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "package.json",
            json.dumps({"name": "my-app", "version": "1.0.0"}),
        )
        assert _detect_project_name(tmp_path) == "my-app"

    def test_from_cargo_toml(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "Cargo.toml",
            '[package]\nname = "my-crate"\nversion = "0.1.0"\n',
        )
        assert _detect_project_name(tmp_path) == "my-crate"

    def test_pyproject_takes_precedence_over_package_json(self, tmp_path: Path) -> None:
        _write(tmp_path / "pyproject.toml", '[project]\nname = "py-name"\n')
        _write(tmp_path / "package.json", json.dumps({"name": "js-name"}))
        assert _detect_project_name(tmp_path) == "py-name"

    def test_fallback_to_directory_name(self, tmp_path: Path) -> None:
        # No manifest files → use the directory name
        name = _detect_project_name(tmp_path)
        assert name == tmp_path.name

    def test_malformed_pyproject_falls_back(self, tmp_path: Path) -> None:
        _write(tmp_path / "pyproject.toml", "[not valid toml\n")
        # No Cargo.toml or package.json → falls back to dir name
        name = _detect_project_name(tmp_path)
        assert name == tmp_path.name


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------


class TestDetectPackageManagers:
    def test_detects_pyproject(self, tmp_path: Path) -> None:
        _write(tmp_path / "pyproject.toml", "[project]\n")
        pms = _detect_package_managers(tmp_path)
        assert "pip/pyproject" in pms

    def test_detects_requirements_txt(self, tmp_path: Path) -> None:
        _write(tmp_path / "requirements.txt", "flask\n")
        pms = _detect_package_managers(tmp_path)
        assert "pip" in pms

    def test_detects_npm(self, tmp_path: Path) -> None:
        _write(tmp_path / "package.json", "{}")
        pms = _detect_package_managers(tmp_path)
        assert "npm" in pms

    def test_yarn_detected_before_npm(self, tmp_path: Path) -> None:
        _write(tmp_path / "yarn.lock", "")
        _write(tmp_path / "package.json", "{}")
        pms = _detect_package_managers(tmp_path)
        assert pms.index("yarn") < pms.index("npm")

    def test_detects_cargo(self, tmp_path: Path) -> None:
        _write(tmp_path / "Cargo.toml", "[package]\n")
        pms = _detect_package_managers(tmp_path)
        assert "cargo" in pms

    def test_detects_poetry(self, tmp_path: Path) -> None:
        _write(tmp_path / "poetry.lock", "# lock\n")
        pms = _detect_package_managers(tmp_path)
        assert "poetry" in pms

    def test_no_pm_when_no_markers(self, tmp_path: Path) -> None:
        pms = _detect_package_managers(tmp_path)
        assert pms == []

    def test_multiple_pms_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "pyproject.toml", "[project]\n")
        _write(tmp_path / "package.json", "{}")
        pms = _detect_package_managers(tmp_path)
        assert len(pms) >= 2


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------


class TestDetectFrameworks:
    def test_detects_fastapi(self, tmp_path: Path) -> None:
        s = {"api.py": _summary("api.py", "Python", ["fastapi"], [])}
        fws = _detect_frameworks(s, tmp_path)
        assert "FastAPI" in fws

    def test_detects_flask(self, tmp_path: Path) -> None:
        s = {"app.py": _summary("app.py", "Python", ["flask"], [])}
        assert "Flask" in _detect_frameworks(s, tmp_path)

    def test_detects_react_from_import(self, tmp_path: Path) -> None:
        s = {"app.jsx": _summary("app.jsx", "JavaScript", ["react"], [])}
        assert "React" in _detect_frameworks(s, tmp_path)

    def test_detects_pytest_from_import(self, tmp_path: Path) -> None:
        s = {"test_x.py": _summary("test_x.py", "Python", ["pytest"], [])}
        assert "pytest" in _detect_frameworks(s, tmp_path)

    def test_no_frameworks_when_no_known_imports(self, tmp_path: Path) -> None:
        s = {"main.py": _summary("main.py", "Python", ["os", "sys"], [])}
        assert _detect_frameworks(s, tmp_path) == []

    def test_multiple_frameworks(self, tmp_path: Path) -> None:
        s = {
            "api.py": _summary("api.py", "Python", ["fastapi", "sqlalchemy"], []),
            "test.py": _summary("test.py", "Python", ["pytest"], []),
        }
        fws = _detect_frameworks(s, tmp_path)
        assert "FastAPI" in fws
        assert "SQLAlchemy" in fws
        assert "pytest" in fws

    def test_frameworks_sorted(self, tmp_path: Path) -> None:
        s = {
            "a.py": _summary("a.py", "Python", ["flask", "celery", "pydantic"], []),
        }
        fws = _detect_frameworks(s, tmp_path)
        assert fws == sorted(fws)

    def test_submodule_import_matches(self, tmp_path: Path) -> None:
        # "fastapi.routing" should still detect FastAPI
        s = {"x.py": _summary("x.py", "Python", ["fastapi.routing"], [])}
        assert "FastAPI" in _detect_frameworks(s, tmp_path)

    def test_framework_from_config_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "vite.config.ts", "export default {};")
        assert "Vite" in _detect_frameworks({}, tmp_path)


# ---------------------------------------------------------------------------
# Important directories
# ---------------------------------------------------------------------------


class TestFindImportantDirs:
    def test_top_level_dirs_reported(self, tmp_path: Path) -> None:
        for name in ["a.py", "b.py"]:
            _write(tmp_path / "src" / name, "pass\n")
        _write(tmp_path / "root.py", "pass\n")
        result = _scan(tmp_path)
        dirs = _find_important_dirs(result)
        dir_names = [d for d, _, _ in dirs]
        assert "src" in dir_names

    def test_purpose_inferred(self, tmp_path: Path) -> None:
        for name in ["a.py", "b.py"]:
            _write(tmp_path / "tests" / name, "pass\n")
        result = _scan(tmp_path)
        dirs = _find_important_dirs(result)
        purposes = {d: p for d, _, p in dirs}
        assert purposes.get("tests") == "test suite"

    def test_sorted_by_file_count_desc(self, tmp_path: Path) -> None:
        for name in ["a.py", "b.py", "c.py"]:
            _write(tmp_path / "big" / name, "pass\n")
        _write(tmp_path / "small" / "x.py", "pass\n")
        result = _scan(tmp_path)
        dirs = _find_important_dirs(result)
        counts = [c for _, c, _ in dirs]
        assert counts == sorted(counts, reverse=True)

    def test_root_level_files_not_reported_as_dir(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        result = _scan(tmp_path)
        dirs = _find_important_dirs(result)
        dir_names = [d for d, _, _ in dirs]
        assert "main.py" not in dir_names


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


class TestFindEntrypoints:
    def test_main_py_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        result = _scan(tmp_path)
        summaries = summarize_repo(result)
        eps = _find_entrypoints(result, summaries)
        assert "main.py" in eps

    def test_app_py_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.py", "pass\n")
        result = _scan(tmp_path)
        summaries = summarize_repo(result)
        eps = _find_entrypoints(result, summaries)
        assert "app.py" in eps

    def test_nested_entrypoint(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "main.py", "pass\n")
        result = _scan(tmp_path)
        summaries = summarize_repo(result)
        eps = _find_entrypoints(result, summaries)
        assert "src/main.py" in eps

    def test_non_entrypoint_not_included(self, tmp_path: Path) -> None:
        _write(tmp_path / "utils.py", "pass\n")
        result = _scan(tmp_path)
        summaries = summarize_repo(result)
        eps = _find_entrypoints(result, summaries)
        assert "utils.py" not in eps

    def test_sorted_output(self, tmp_path: Path) -> None:
        for name in ["main.py", "app.py", "server.py"]:
            _write(tmp_path / name, "pass\n")
        result = _scan(tmp_path)
        summaries = summarize_repo(result)
        eps = _find_entrypoints(result, summaries)
        assert eps == sorted(eps)


# ---------------------------------------------------------------------------
# Test directories
# ---------------------------------------------------------------------------


class TestFindTestDirs:
    def test_tests_dir_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "tests" / "test_main.py", "pass\n")
        result = _scan(tmp_path)
        summaries = summarize_repo(result)
        dirs = _find_test_dirs(result, summaries)
        assert "tests" in dirs

    def test_spec_dir_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "spec" / "app_spec.py", "pass\n")
        result = _scan(tmp_path)
        summaries = summarize_repo(result)
        dirs = _find_test_dirs(result, summaries)
        assert "spec" in dirs

    def test_non_test_dirs_excluded(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "app.py", "pass\n")
        result = _scan(tmp_path)
        summaries = summarize_repo(result)
        dirs = _find_test_dirs(result, summaries)
        assert "src" not in dirs


# ---------------------------------------------------------------------------
# Config files
# ---------------------------------------------------------------------------


class TestFindConfigFiles:
    def test_pyproject_toml_included(self, tmp_path: Path) -> None:
        _write(tmp_path / "pyproject.toml", "[project]\n")
        _write(tmp_path / "main.py", "pass\n")
        result = _scan(tmp_path)
        cfs = _find_config_files(result)
        assert "pyproject.toml" in cfs

    def test_gitignore_included(self, tmp_path: Path) -> None:
        _write(tmp_path / ".gitignore", "*.pyc\n")
        _write(tmp_path / "main.py", "pass\n")
        result = _scan(tmp_path)
        cfs = _find_config_files(result)
        assert ".gitignore" in cfs

    def test_env_file_excluded(self, tmp_path: Path) -> None:
        _write(tmp_path / ".env", "SECRET_KEY=abc123\n")
        _write(tmp_path / "main.py", "pass\n")
        result = _scan(tmp_path)
        cfs = _find_config_files(result)
        assert ".env" not in cfs

    def test_env_example_included(self, tmp_path: Path) -> None:
        _write(tmp_path / ".env.example", "SECRET_KEY=changeme\n")
        _write(tmp_path / "main.py", "pass\n")
        result = _scan(tmp_path)
        cfs = _find_config_files(result)
        assert ".env.example" in cfs

    def test_github_workflow_included(self, tmp_path: Path) -> None:
        _write(tmp_path / ".github" / "workflows" / "ci.yml", "on: push\n")
        _write(tmp_path / "main.py", "pass\n")
        result = _scan(tmp_path)
        cfs = _find_config_files(result)
        assert any("ci.yml" in cf for cf in cfs)

    def test_sorted_output(self, tmp_path: Path) -> None:
        for f in ["pyproject.toml", ".gitignore", "Makefile"]:
            _write(tmp_path / f, "# config\n")
        _write(tmp_path / "main.py", "pass\n")
        result = _scan(tmp_path)
        cfs = _find_config_files(result)
        assert cfs == sorted(cfs)


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------


class TestBuildIndex:
    def test_returns_repo_index(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", '"""App."""\n\ndef run():\n    pass\n')
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries)
        assert isinstance(idx, RepoIndex)

    def test_project_name_populated(self, tmp_path: Path) -> None:
        _write(tmp_path / "pyproject.toml", '[project]\nname = "demo"\n')
        _write(tmp_path / "main.py", "pass\n")
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries)
        assert idx.project_name == "demo"

    def test_languages_populated(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "pass\n")
        _write(tmp_path / "b.py", "pass\n")
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries)
        assert "Python" in idx.detected_languages

    def test_entrypoints_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries)
        assert "main.py" in idx.entrypoints

    def test_test_dirs_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "tests" / "test_app.py", "def test_x(): pass\n")
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries)
        assert "tests" in idx.test_dirs

    def test_no_timestamp_when_disabled(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "pass\n")
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries, include_timestamp=False)
        assert idx.generated_at == ""

    def test_timestamp_present_by_default(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "pass\n")
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries)
        assert idx.generated_at != ""

    def test_package_managers_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "pyproject.toml", "[project]\n")
        _write(tmp_path / "main.py", "pass\n")
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries)
        assert "pip/pyproject" in idx.package_managers


# ---------------------------------------------------------------------------
# RepoIndex.render()
# ---------------------------------------------------------------------------


class TestRenderIndex:
    def _simple_index(self) -> RepoIndex:
        return RepoIndex(
            project_name="demo-app",
            detected_languages={"Python": 10, "YAML": 2},
            package_managers=["pip/pyproject", "poetry"],
            frameworks=["FastAPI", "pytest"],
            important_dirs=[("src", 8, "source code"), ("tests", 4, "test suite")],
            entrypoints=["src/main.py"],
            test_dirs=["tests"],
            config_files=["pyproject.toml", ".gitignore"],
            top_files=[],
            generated_at="",
        )

    def test_renders_as_string(self) -> None:
        assert isinstance(self._simple_index().render(), str)

    def test_contains_project_name(self) -> None:
        md = self._simple_index().render()
        assert "demo-app" in md

    def test_contains_languages(self) -> None:
        md = self._simple_index().render()
        assert "Python" in md

    def test_contains_package_managers(self) -> None:
        md = self._simple_index().render()
        assert "pip/pyproject" in md
        assert "poetry" in md

    def test_contains_frameworks(self) -> None:
        md = self._simple_index().render()
        assert "FastAPI" in md
        assert "pytest" in md

    def test_contains_entrypoints(self) -> None:
        md = self._simple_index().render()
        assert "src/main.py" in md

    def test_contains_test_dirs(self) -> None:
        md = self._simple_index().render()
        assert "tests" in md

    def test_contains_config_files(self) -> None:
        md = self._simple_index().render()
        assert "pyproject.toml" in md

    def test_contains_safety_note(self) -> None:
        md = self._simple_index().render()
        assert "No secrets" in md
        assert "source code" in md.lower()

    def test_no_secrets_value_included(self) -> None:
        idx = self._simple_index()
        md = idx.render()
        # Secret values should never appear
        assert "hunter2" not in md
        assert "SECRET_KEY" not in md

    def test_starts_with_h1(self) -> None:
        md = self._simple_index().render()
        assert md.startswith("# Project Index")

    def test_timestamp_omitted_when_empty(self) -> None:
        md = self._simple_index().render()
        # generated_at="" → no timestamp token in footer
        assert "Generated:" not in md

    def test_timestamp_included_when_set(self) -> None:
        idx = self._simple_index()
        idx.generated_at = "2026-06-29T12:00:00+00:00"
        md = idx.render()
        assert "Generated:" in md
        assert "2026-06-29" in md

    def test_empty_sections_omitted(self) -> None:
        idx = RepoIndex(
            project_name="bare",
            detected_languages={},
            package_managers=[],
            frameworks=[],
            important_dirs=[],
            entrypoints=[],
            test_dirs=[],
            config_files=[],
            top_files=[],
            generated_at="",
        )
        md = idx.render()
        assert "Package Managers" not in md
        assert "Frameworks" not in md

    def test_top_files_rendered(self) -> None:
        raw = b"x"
        summary = FileSummary(
            rel_path="src/core.py",
            language="Python",
            purpose="core logic",
            imports=["os"],
            exports=["def process"],
            symbols=["process"],
            docstring="Core.",
            line_count=50,
            content_hash=hashlib.sha256(raw).hexdigest(),
        )
        idx = self._simple_index()
        idx.top_files = [summary]
        md = idx.render()
        assert "src/core.py" in md
        assert "core logic" in md


# ---------------------------------------------------------------------------
# write_project_index
# ---------------------------------------------------------------------------


class TestWriteProjectIndex:
    def test_writes_file(self, tmp_path: Path) -> None:
        idx = RepoIndex(
            project_name="test",
            detected_languages={"Python": 1},
            package_managers=[],
            frameworks=[],
            important_dirs=[],
            entrypoints=[],
            test_dirs=[],
            config_files=[],
            top_files=[],
            generated_at="",
        )
        out = tmp_path / "PROJECT_INDEX.md"
        write_project_index(idx, out)
        assert out.exists()
        assert "# Project Index" in out.read_text()

    def test_content_is_valid_markdown(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        result, summaries = _make_scan_result(tmp_path)
        idx = build_index(tmp_path, result, summaries, include_timestamp=False)
        out = tmp_path / "PROJECT_INDEX.md"
        write_project_index(idx, out)
        content = out.read_text()
        assert content.startswith("#")
        assert "---" in content  # footer separator


# ---------------------------------------------------------------------------
# scan CLI integration
# ---------------------------------------------------------------------------


class TestScanCLIIntegration:
    def test_creates_contextos_dir(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        result = runner.invoke(app, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".contextos").is_dir()

    def test_creates_project_index(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        runner.invoke(app, ["scan", str(tmp_path)])
        assert (tmp_path / ".contextos" / "PROJECT_INDEX.md").exists()

    def test_creates_file_summaries(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        runner.invoke(app, ["scan", str(tmp_path)])
        summaries_path = tmp_path / ".contextos" / "file_summaries.json"
        assert summaries_path.exists()
        data = json.loads(summaries_path.read_text())
        assert "main.py" in data

    def test_project_index_content(self, tmp_path: Path) -> None:
        _write(tmp_path / "pyproject.toml", '[project]\nname = "testproj"\n')
        _write(tmp_path / "main.py", "pass\n")
        runner.invoke(app, ["scan", str(tmp_path)])
        content = (tmp_path / ".contextos" / "PROJECT_INDEX.md").read_text()
        assert "testproj" in content
        assert "No secrets" in content

    def test_no_index_flag_skips_writing(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        runner.invoke(app, ["scan", str(tmp_path), "--no-index"])
        assert not (tmp_path / ".contextos" / "PROJECT_INDEX.md").exists()

    def test_scan_output_mentions_contextos(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        result = runner.invoke(app, ["scan", str(tmp_path)])
        assert ".contextos" in result.output

    def test_no_secrets_in_index_output(self, tmp_path: Path) -> None:
        _write(tmp_path / ".env", "SECRET_KEY=hunter2\nDATABASE_URL=postgres://user:pass@host/db\n")
        _write(tmp_path / "main.py", "x = 1\n")
        runner.invoke(app, ["scan", str(tmp_path)])
        index_path = tmp_path / ".contextos" / "PROJECT_INDEX.md"
        if index_path.exists():
            content = index_path.read_text()
            assert "hunter2" not in content
            assert "user:pass" not in content
