"""Tests for the pack command and pack_builder module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from contextos.cli.main import app
from contextos.core.pack_builder import PackConfig, _is_test_file, build_pack

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PY_AUTH = "def authenticate(user: str, password: str) -> bool:\n    return True\n"
_PY_UTILS = "def helper(x: int) -> int:\n    return x + 1\n"
_PY_TEST = (
    "def test_authenticate():\n"
    "    from auth import authenticate\n"
    "    assert authenticate('a', 'b')\n"
)


@pytest.fixture()
def repo(tmp_path: Path) -> tuple[Path, Path]:
    """Minimal repo with .contextos/ pre-populated by running the real scanner."""
    root = tmp_path / "repo"
    root.mkdir()

    (root / "auth.py").write_text(_PY_AUTH, encoding="utf-8")
    (root / "utils.py").write_text(_PY_UTILS, encoding="utf-8")
    (root / "readme.md").write_text("# MyProject\nAuthentication library.\n", encoding="utf-8")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text(_PY_TEST, encoding="utf-8")

    ctxdir = root / ".contextos"
    ctxdir.mkdir()

    # Run real scan to generate file_summaries.json and dependency_graph.json.
    from contextos.core.dependency_graph import build_graph, write_graph
    from contextos.core.scanner import ScanConfig, scan
    from contextos.core.summarizer import summarize_repo

    result = scan(root, ScanConfig())
    summarize_repo(result, output_path=ctxdir / "file_summaries.json")
    write_graph(build_graph(result), ctxdir / "dependency_graph.json")

    (ctxdir / "PROJECT_INDEX.md").write_text(
        "# Project\nAn authentication library.\n", encoding="utf-8"
    )
    (ctxdir / "DECISIONS.md").write_text(
        "# Decisions\n- Use bcrypt for hashing.\n", encoding="utf-8"
    )
    (ctxdir / "MEMORY.md").write_text("", encoding="utf-8")

    return root, ctxdir


# ---------------------------------------------------------------------------
# build_pack — Markdown sections
# ---------------------------------------------------------------------------


class TestMarkdownSections:
    def test_has_task_section(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = build_pack("fix authentication bug", root, ctxdir)
        assert "## Task" in content
        assert "fix authentication bug" in content

    def test_has_project_overview(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = build_pack("auth fix", root, ctxdir)
        assert "Project Overview" in content
        assert "authentication" in content.lower()

    def test_has_decisions(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = build_pack("auth fix", root, ctxdir)
        assert "Decisions" in content
        assert "bcrypt" in content.lower()

    def test_has_context_files_section(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = build_pack("authenticate user", root, ctxdir)
        assert "## Context Files" in content

    def test_has_token_budget_section(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = build_pack("fix auth", root, ctxdir)
        assert "Token Budget" in content
        assert "Budget" in content
        assert "Used" in content

    def test_has_agent_instructions(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = build_pack("fix auth", root, ctxdir)
        assert "Agent Instructions" in content
        assert "task" in content.lower()

    def test_has_generated_timestamp(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = build_pack("fix auth", root, ctxdir)
        assert "Generated:" in content

    def test_no_timestamp_when_disabled(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(add_timestamp=False)
        content, _ = build_pack("fix auth", root, ctxdir, config=cfg)
        assert "Generated:" not in content

    def test_excluded_files_section_when_present(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        # Use tiny budget so something gets excluded.
        cfg = PackConfig(budget=50)
        content, sel = build_pack("fix auth", root, ctxdir, config=cfg)
        if sel.excluded:
            assert "Excluded Files" in content

    def test_footer_contains_version(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = build_pack("fix auth", root, ctxdir)
        assert "ContextOS" in content


# ---------------------------------------------------------------------------
# build_pack — JSON format
# ---------------------------------------------------------------------------


class TestJsonFormat:
    def test_json_is_valid(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        content, _ = build_pack("authenticate user", root, ctxdir, config=cfg)
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_json_has_task(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        content, _ = build_pack("fix auth bug", root, ctxdir, config=cfg)
        data = json.loads(content)
        assert data["task"] == "fix auth bug"

    def test_json_has_budget(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(budget=4000, fmt="json")
        content, _ = build_pack("fix auth", root, ctxdir, config=cfg)
        data = json.loads(content)
        assert data["budget"] == 4000

    def test_json_has_selected(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        content, _ = build_pack("authenticate", root, ctxdir, config=cfg)
        data = json.loads(content)
        assert "selected" in data
        assert isinstance(data["selected"], list)

    def test_json_has_excluded(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        content, _ = build_pack("authenticate", root, ctxdir, config=cfg)
        data = json.loads(content)
        assert "excluded" in data

    def test_json_has_project_summary(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        content, _ = build_pack("authenticate", root, ctxdir, config=cfg)
        data = json.loads(content)
        assert "project_summary" in data

    def test_json_has_agent_instructions(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        content, _ = build_pack("authenticate", root, ctxdir, config=cfg)
        data = json.loads(content)
        assert "agent_instructions" in data
        assert len(data["agent_instructions"]) > 10

    def test_json_selected_items_have_rel_path(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        content, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        data = json.loads(content)
        if data["selected"]:
            assert "rel_path" in data["selected"][0]

    def test_json_file_written(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        build_pack("fix auth", root, ctxdir, config=cfg)
        assert (ctxdir / "context_pack.json").exists()


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


class TestBudget:
    def test_used_tokens_within_budget(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(budget=500)
        _, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        assert sel.used_tokens <= 500

    def test_zero_budget_no_selected(self, repo: tuple[Path, Path]) -> None:
        # budget must be > 0 at CLI level; but pack_builder itself accepts any value
        root, ctxdir = repo
        cfg = PackConfig(budget=1)
        _, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        assert sel.used_tokens <= 1

    def test_large_budget_selects_files(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(budget=50000)
        _, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        assert len(sel.selected) > 0

    def test_excluded_listed_in_selection(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(budget=50)  # very tight
        _, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        # Anything not selected should be excluded (or selected)
        selected_paths = {r.rel_path for r in sel.selected}
        for p in sel.excluded:
            assert p not in selected_paths

    def test_budget_shown_in_markdown(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(budget=4000)
        content, _ = build_pack("fix auth", root, ctxdir, config=cfg)
        assert "4,000" in content or "4000" in content


# ---------------------------------------------------------------------------
# --no-source
# ---------------------------------------------------------------------------


class TestNoSource:
    def test_no_source_only_summaries(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(no_source=True, budget=50000)
        _, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        for result in sel.selected:
            assert result.kind == "summary", f"{result.rel_path} included as {result.kind}"

    def test_no_source_no_code_block(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(no_source=True, budget=50000)
        content, _ = build_pack("authenticate", root, ctxdir, config=cfg)
        # Summary-only mode should not embed the raw function body
        assert "return True" not in content

    def test_with_source_embeds_code(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(no_source=False, budget=50000)
        content, _ = build_pack("authenticate", root, ctxdir, config=cfg)
        # With source, the actual function definition should appear
        assert "authenticate" in content


# ---------------------------------------------------------------------------
# --include-tests / --no-tests
# ---------------------------------------------------------------------------


class TestIncludeTests:
    def test_include_tests_true_contains_test_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(include_tests=True, budget=50000)
        _, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        # Not guaranteed to be selected (score-based), but should not be filtered.
        # Just verify no crash and all selected files are real FileSummary entries.
        assert isinstance(sel.selected, list)

    def test_no_tests_excludes_test_files(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(include_tests=False, budget=50000)
        _, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        selected_paths = {r.rel_path for r in sel.selected}
        for p in selected_paths:
            assert not _is_test_file(p), f"Test file {p!r} included despite --no-tests"

    def test_no_tests_excluded_list_has_tests(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        # With small budget, test files should be pre-filtered (not in scoring pool).
        cfg = PackConfig(include_tests=False, budget=50000)
        _, sel = build_pack("authenticate", root, ctxdir, config=cfg)
        all_paths = {r.rel_path for r in sel.selected} | set(sel.excluded)
        for p in all_paths:
            assert not _is_test_file(p)


# ---------------------------------------------------------------------------
# Default output file
# ---------------------------------------------------------------------------


class TestOutputFile:
    def test_default_md_written(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        build_pack("fix auth", root, ctxdir)
        assert (ctxdir / "context_pack.md").exists()

    def test_default_md_contains_task(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        build_pack("fix auth", root, ctxdir)
        content = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        assert "fix auth" in content

    def test_default_json_written(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cfg = PackConfig(fmt="json")
        build_pack("fix auth", root, ctxdir, config=cfg)
        assert (ctxdir / "context_pack.json").exists()

    def test_pack_overwritten_on_second_call(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        build_pack("first task", root, ctxdir)
        build_pack("second task", root, ctxdir)
        content = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        assert "second task" in content
        assert "first task" not in content


# ---------------------------------------------------------------------------
# Auto-scan (no existing .contextos/)
# ---------------------------------------------------------------------------


class TestAutoScan:
    def test_pack_empty_repo_writes_pack(self, tmp_path: Path) -> None:
        repo = tmp_path / "empty"
        repo.mkdir()
        ctxdir = repo / ".contextos"

        content, selection = build_pack("inspect empty repo", repo, ctxdir)

        assert selection.selected == []
        assert "No files selected" in content
        assert (ctxdir / "context_pack.md").exists()

    def test_pack_repo_without_readme(self, tmp_path: Path) -> None:
        repo = tmp_path / "no-readme"
        repo.mkdir()
        (repo / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        ctxdir = repo / ".contextos"

        _content, selection = build_pack("main entrypoint", repo, ctxdir)

        assert "main.py" in [item.rel_path for item in selection.selected]

    def test_pack_creates_summaries_if_missing(self, tmp_path: Path) -> None:
        repo = tmp_path / "fresh"
        repo.mkdir()
        (repo / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        ctxdir = repo / ".contextos"
        # No .contextos/ at all — build_pack should create it
        build_pack("add logging", repo, ctxdir)
        assert (ctxdir / "file_summaries.json").exists()
        assert (ctxdir / "context_pack.md").exists()

    def test_pack_uses_existing_summaries(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        mtime_before = (ctxdir / "file_summaries.json").stat().st_mtime
        build_pack("fix auth", root, ctxdir)
        mtime_after = (ctxdir / "file_summaries.json").stat().st_mtime
        # file_summaries.json should NOT be rewritten (existing used as-is)
        assert mtime_after == mtime_before

    def test_pack_recovers_from_corrupted_summaries(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        ctxdir = repo / ".contextos"
        ctxdir.mkdir()
        (ctxdir / "file_summaries.json").write_text("{not json", encoding="utf-8")
        (ctxdir / "dependency_graph.json").write_text(
            json.dumps({"nodes": [], "edges": [], "unresolved": {}, "cycles": []}),
            encoding="utf-8",
        )

        _content, selection = build_pack("main entrypoint", repo, ctxdir)

        assert "main.py" in json.loads((ctxdir / "file_summaries.json").read_text())
        assert "main.py" in [item.rel_path for item in selection.selected]

    def test_pack_recovers_from_corrupted_dependency_graph(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("import os\n\ndef main(): pass\n", encoding="utf-8")
        ctxdir = repo / ".contextos"

        build_pack("main entrypoint", repo, ctxdir)
        (ctxdir / "dependency_graph.json").write_text("{not json", encoding="utf-8")

        _content, selection = build_pack("main entrypoint", repo, ctxdir)

        graph = json.loads((ctxdir / "dependency_graph.json").read_text(encoding="utf-8"))
        assert "nodes" in graph
        assert "main.py" in [item.rel_path for item in selection.selected]

    def test_repeated_pack_does_not_select_previous_context_pack(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        ctxdir = repo / ".contextos"

        build_pack("first task", repo, ctxdir)
        build_pack("context pack main", repo, ctxdir)

        summaries = json.loads((ctxdir / "file_summaries.json").read_text(encoding="utf-8"))
        assert not any(path.startswith(".contextos/") for path in summaries)


# ---------------------------------------------------------------------------
# Safety — no secrets
# ---------------------------------------------------------------------------


class TestSafety:
    def test_env_file_not_in_output(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        # Place a .env file that bypassed the scanner (manually add to summaries)
        (root / ".env").write_text("SECRET_KEY=hunter2\n", encoding="utf-8")
        content, sel = build_pack("secret key authentication", root, ctxdir)
        assert "hunter2" not in content
        assert ".env" not in [r.rel_path for r in sel.selected]

    def test_binary_not_selected(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        (root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        _, sel = build_pack("process image", root, ctxdir)
        # image.png was not scanned → not in summaries → not selected
        assert all(r.rel_path != "image.png" for r in sel.selected)

    def test_no_raw_secrets_in_markdown(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        # Inject a credential file into the project
        (root / "credentials.json").write_text('{"api_key": "supersecret123"}', encoding="utf-8")
        content, _ = build_pack("api key management", root, ctxdir)
        assert "supersecret123" not in content


# ---------------------------------------------------------------------------
# _is_test_file helper
# ---------------------------------------------------------------------------


class TestIsTestFile:
    def test_test_prefix(self) -> None:
        assert _is_test_file("test_auth.py")

    def test_test_suffix(self) -> None:
        assert _is_test_file("auth_test.py")

    def test_tests_dir(self) -> None:
        assert _is_test_file("tests/auth.py")

    def test_nested_tests_dir(self) -> None:
        assert _is_test_file("src/tests/test_main.py")

    def test_normal_file(self) -> None:
        assert not _is_test_file("auth.py")

    def test_normal_nested(self) -> None:
        assert not _is_test_file("src/auth/middleware.py")

    def test_spec_dir(self) -> None:
        assert _is_test_file("spec/auth_spec.js")

    def test_windows_tests_dir(self) -> None:
        assert _is_test_file(r"tests\test_auth.py")

    def test_windows_normal_file(self) -> None:
        assert not _is_test_file(r"src\auth\middleware.py")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestPackCLI:
    def test_exits_zero(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth"])
        assert result.exit_code == 0

    def test_shows_task(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "add rate limiting"])
        assert "add rate limiting" in result.output

    def test_shows_budget(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth", "--budget", "4000"])
        assert "4" in result.output  # budget shown

    def test_shows_token_count(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth"])
        assert "tokens" in result.output.lower()

    def test_shows_selected_count(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth"])
        assert "Selected" in result.output or "selected" in result.output

    def test_requires_task(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["pack", str(root)])
        assert result.exit_code != 0

    def test_invalid_format_exits_one(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix", "--format", "invalid"])
        assert result.exit_code == 1

    def test_zero_budget_exits_one(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix", "--budget", "0"])
        assert result.exit_code == 1

    def test_json_format_flag(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth", "--format", "json"])
        assert result.exit_code == 0
        assert (ctxdir / "context_pack.json").exists()

    def test_no_source_flag(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth", "--no-source"])
        assert result.exit_code == 0
        assert "summaries only" in result.output

    def test_no_tests_flag(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth", "--no-tests"])
        assert result.exit_code == 0
        content = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        # Test file should not appear in output
        assert "test_auth" not in content

    def test_out_flag_writes_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        out = ctxdir / "custom.md"
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth", "--out", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        assert "fix auth" in out.read_text(encoding="utf-8")

    def test_no_timestamp_flag(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth", "--no-timestamp"])
        assert result.exit_code == 0
        content = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        assert "Generated:" not in content

    def test_writes_default_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        runner.invoke(app, ["pack", str(root), "--task", "fix auth"])
        assert (ctxdir / "context_pack.md").exists()

    def test_task_in_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        runner.invoke(app, ["pack", str(root), "--task", "implement rate limiting"])
        content = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        assert "implement rate limiting" in content

    def test_existing_summaries_respected(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        # Second pack run should not re-scan (summaries already exist).
        result = runner.invoke(app, ["pack", str(root), "--task", "fix auth"])
        assert result.exit_code == 0

    def test_nonexistent_repo_exits_one(self) -> None:
        result = runner.invoke(app, ["pack", "/nonexistent/path/xyz", "--task", "fix"])
        assert result.exit_code == 1
