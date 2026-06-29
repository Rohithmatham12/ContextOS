"""Tests for tool-specific exporters (claude, codex, cursor, aider)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from contextos.cli.main import app
from contextos.core.context_selector import ContextSelection, FileResult
from contextos.exporters import aider, claude, codex, cursor
from contextos.exporters.base import (
    ExportConfig,
    _looks_secret,
    _section,
    _trim,
    render_context,
)

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
    """Minimal repo with pre-populated .contextos/ scan data."""
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


@pytest.fixture()
def minimal_selection() -> ContextSelection:
    """A ContextSelection with one file result and one excluded path."""
    return ContextSelection(
        task="add authentication",
        budget=8000,
        used_tokens=120,
        selected=[
            FileResult(
                rel_path="auth.py",
                score=1.5,
                reasons=["path match", "keyword match"],
                tokens=120,
                content="```python\ndef authenticate(): ...\n```",
                kind="full",
            )
        ],
        excluded=["big_module.py"],
    )


# ---------------------------------------------------------------------------
# Base helpers
# ---------------------------------------------------------------------------


class TestSection:
    def test_returns_h2(self) -> None:
        result = _section("Foo", "body text")
        assert result.startswith("## Foo")

    def test_body_present(self) -> None:
        assert "body text" in _section("Foo", "body text")

    def test_trailing_newline(self) -> None:
        assert _section("T", "b").endswith("\n\n")


class TestTrim:
    def test_short_text_unchanged(self) -> None:
        assert _trim("hello", 100) == "hello"

    def test_long_text_truncated(self) -> None:
        long = "a\n" * 300
        result = _trim(long, 100)
        assert len(result) < len(long)
        assert "*[trimmed" in result

    def test_trim_at_newline_boundary(self) -> None:
        text = "line1\nline2\nline3"
        result = _trim(text, 10)
        assert "line3" not in result


class TestLooksSecret:
    def test_env_file(self) -> None:
        assert _looks_secret(".env")

    def test_env_local(self) -> None:
        assert _looks_secret(".env.local")

    def test_secret_in_name(self) -> None:
        assert _looks_secret("app_secrets.json")

    def test_credentials_file(self) -> None:
        assert _looks_secret("credentials.json")

    def test_password_file(self) -> None:
        assert _looks_secret("passwords.txt")

    def test_normal_file_not_secret(self) -> None:
        assert not _looks_secret("auth.py")

    def test_readme_not_secret(self) -> None:
        assert not _looks_secret("README.md")


# ---------------------------------------------------------------------------
# render_context (shared renderer)
# ---------------------------------------------------------------------------


class TestRenderContext:
    def test_contains_tool_name(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "do something",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="TestTool",
            filename="TEST.md",
            usage_note="use it",
            agent_instructions="follow rules",
        )
        assert "TestTool" in out

    def test_contains_task(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "implement auth",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "implement auth" in out

    def test_contains_file_path(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "auth.py" in out

    def test_contains_agent_instructions(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="DO THIS SPECIFIC THING",
        )
        assert "DO THIS SPECIFIC THING" in out

    def test_contains_project_summary(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "## Summary\nThis project does auth.",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "This project does auth" in out

    def test_contains_decisions(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "- Use bcrypt",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "bcrypt" in out

    def test_timestamp_present_when_provided(self, minimal_selection: ContextSelection) -> None:
        ts = "2026-06-29T12:00:00+00:00"
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            ts,
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert ts in out

    def test_no_timestamp_when_empty(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "Generated:" not in out

    def test_token_budget_section(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "Token Budget" in out
        assert "8,000" in out

    def test_excluded_files_section(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "big_module.py" in out

    def test_dep_notes_included(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "- `auth.py` → imports `utils.py`",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "Dependency Notes" in out
        assert "utils.py" in out

    def test_no_dep_notes_section_when_empty(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "Dependency Notes" not in out

    def test_usage_note_present(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="PASTE THIS INTO THE TOOL",
            agent_instructions="i",
        )
        assert "PASTE THIS INTO THE TOOL" in out

    def test_footer_contains_contextos(self, minimal_selection: ContextSelection) -> None:
        out = render_context(
            "task",
            "",
            "",
            minimal_selection,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "ContextOS" in out

    def test_no_files_within_budget(self) -> None:
        empty_sel = ContextSelection(
            task="task",
            budget=8000,
            used_tokens=0,
            selected=[],
            excluded=[],
        )
        out = render_context(
            "task",
            "",
            "",
            empty_sel,
            "",
            "",
            tool_name="T",
            filename="T.md",
            usage_note="n",
            agent_instructions="i",
        )
        assert "No files selected" in out


# ---------------------------------------------------------------------------
# Tool-specific renderers — unique instructions
# ---------------------------------------------------------------------------


class TestClaudeRenderer:
    def test_filename_constant(self) -> None:
        assert claude.FILENAME == "CLAUDE_CONTEXT.md"

    def test_tool_name_constant(self) -> None:
        assert claude.TOOL_NAME == "Claude Code"

    def test_render_returns_string(self, minimal_selection: ContextSelection) -> None:
        out = claude.render("task", "", "", minimal_selection, "", "")
        assert isinstance(out, str)

    def test_contains_claude_specific_instruction(
        self, minimal_selection: ContextSelection
    ) -> None:
        out = claude.render("task", "", "", minimal_selection, "", "")
        assert "Read" in out

    def test_contains_edit_tool_mention(self, minimal_selection: ContextSelection) -> None:
        out = claude.render("task", "", "", minimal_selection, "", "")
        assert "Edit" in out

    def test_contains_ruff_mention(self, minimal_selection: ContextSelection) -> None:
        out = claude.render("task", "", "", minimal_selection, "", "")
        assert "ruff" in out

    def test_claude_code_in_output(self, minimal_selection: ContextSelection) -> None:
        out = claude.render("task", "", "", minimal_selection, "", "")
        assert "Claude Code" in out


class TestCodexRenderer:
    def test_filename_constant(self) -> None:
        assert codex.FILENAME == "CODEX_CONTEXT.md"

    def test_tool_name_constant(self) -> None:
        assert "Codex" in codex.TOOL_NAME

    def test_render_returns_string(self, minimal_selection: ContextSelection) -> None:
        out = codex.render("task", "", "", minimal_selection, "", "")
        assert isinstance(out, str)

    def test_contains_minimal_changes(self, minimal_selection: ContextSelection) -> None:
        out = codex.render("task", "", "", minimal_selection, "", "")
        assert "minimal" in out.lower()

    def test_contains_agents_md_mention(self, minimal_selection: ContextSelection) -> None:
        out = codex.render("task", "", "", minimal_selection, "", "")
        assert "AGENTS.md" in out

    def test_codex_in_output(self, minimal_selection: ContextSelection) -> None:
        out = codex.render("task", "", "", minimal_selection, "", "")
        assert "Codex" in out


class TestCursorRenderer:
    def test_filename_constant(self) -> None:
        assert cursor.FILENAME == "CURSOR_CONTEXT.md"

    def test_tool_name_constant(self) -> None:
        assert cursor.TOOL_NAME == "Cursor"

    def test_render_returns_string(self, minimal_selection: ContextSelection) -> None:
        out = cursor.render("task", "", "", minimal_selection, "", "")
        assert isinstance(out, str)

    def test_contains_cursorrules_mention(self, minimal_selection: ContextSelection) -> None:
        out = cursor.render("task", "", "", minimal_selection, "", "")
        assert "cursor" in out.lower()

    def test_cursor_in_output(self, minimal_selection: ContextSelection) -> None:
        out = cursor.render("task", "", "", minimal_selection, "", "")
        assert "Cursor" in out

    def test_contains_multi_file_mention(self, minimal_selection: ContextSelection) -> None:
        out = cursor.render("task", "", "", minimal_selection, "", "")
        assert "multi-file" in out.lower()


class TestAiderRenderer:
    def test_filename_constant(self) -> None:
        assert aider.FILENAME == "AIDER_CONTEXT.md"

    def test_tool_name_constant(self) -> None:
        assert aider.TOOL_NAME == "Aider"

    def test_render_returns_string(self, minimal_selection: ContextSelection) -> None:
        out = aider.render("task", "", "", minimal_selection, "", "")
        assert isinstance(out, str)

    def test_contains_aider_read_instruction(self, minimal_selection: ContextSelection) -> None:
        out = aider.render("task", "", "", minimal_selection, "", "")
        assert "--read" in out

    def test_contains_minimal_diffs(self, minimal_selection: ContextSelection) -> None:
        out = aider.render("task", "", "", minimal_selection, "", "")
        assert "minimal" in out.lower()

    def test_aider_in_output(self, minimal_selection: ContextSelection) -> None:
        out = aider.render("task", "", "", minimal_selection, "", "")
        assert "Aider" in out


# ---------------------------------------------------------------------------
# export() functions (pipeline integration)
# ---------------------------------------------------------------------------


class TestClaudeExport:
    def test_creates_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        claude.export("add auth", root, ctxdir)
        assert (ctxdir / "CLAUDE_CONTEXT.md").exists()

    def test_returns_content_and_selection(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, sel = claude.export("add auth", root, ctxdir)
        assert isinstance(content, str)
        assert "Claude Code" in content

    def test_content_written_to_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = claude.export("add auth", root, ctxdir)
        assert (ctxdir / "CLAUDE_CONTEXT.md").read_text(encoding="utf-8") == content

    def test_no_source_flag(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = claude.export("add auth", root, ctxdir, config=ExportConfig(no_source=True))
        assert "Claude Code" in content

    def test_exclude_tests_flag(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        _, sel = claude.export("add auth", root, ctxdir, config=ExportConfig(include_tests=False))
        for result in sel.selected:
            assert "test_" not in result.rel_path


class TestCodexExport:
    def test_creates_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        codex.export("add auth", root, ctxdir)
        assert (ctxdir / "CODEX_CONTEXT.md").exists()

    def test_returns_content(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = codex.export("add auth", root, ctxdir)
        assert "Codex" in content


class TestCursorExport:
    def test_creates_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        cursor.export("add auth", root, ctxdir)
        assert (ctxdir / "CURSOR_CONTEXT.md").exists()

    def test_returns_content(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = cursor.export("add auth", root, ctxdir)
        assert "Cursor" in content


class TestAiderExport:
    def test_creates_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        aider.export("add auth", root, ctxdir)
        assert (ctxdir / "AIDER_CONTEXT.md").exists()

    def test_returns_content(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        content, _ = aider.export("add auth", root, ctxdir)
        assert "Aider" in content


# ---------------------------------------------------------------------------
# CLI — export claude
# ---------------------------------------------------------------------------


class TestCLIExportClaude:
    def test_exits_zero(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["export", "claude", "--repo", str(root), "--task", "add auth"])
        assert result.exit_code == 0

    def test_creates_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        runner.invoke(app, ["export", "claude", "--repo", str(root), "--task", "add auth"])
        assert (ctxdir / "CLAUDE_CONTEXT.md").exists()

    def test_success_in_output(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["export", "claude", "--repo", str(root), "--task", "add auth"])
        assert "CLAUDE_CONTEXT.md" in result.output

    def test_task_in_output(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["export", "claude", "--repo", str(root), "--task", "add auth"])
        assert "add auth" in result.output

    def test_out_flag_writes_file(self, repo: tuple[Path, Path], tmp_path: Path) -> None:
        root, _ = repo
        extra = tmp_path / "custom_claude.md"
        runner.invoke(
            app,
            ["export", "claude", "--repo", str(root), "--task", "add auth", "--out", str(extra)],
        )
        assert extra.exists()

    def test_no_tests_flag(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        result = runner.invoke(
            app,
            ["export", "claude", "--repo", str(root), "--task", "add auth", "--no-tests"],
        )
        assert result.exit_code == 0

    def test_no_source_flag(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(
            app,
            ["export", "claude", "--repo", str(root), "--task", "add auth", "--no-source"],
        )
        assert result.exit_code == 0

    def test_budget_flag(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(
            app,
            ["export", "claude", "--repo", str(root), "--task", "add auth", "--budget", "4000"],
        )
        assert result.exit_code == 0

    def test_invalid_budget_exits_one(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(
            app,
            ["export", "claude", "--repo", str(root), "--task", "add auth", "--budget", "0"],
        )
        assert result.exit_code == 1

    def test_invalid_repo_exits_one(self) -> None:
        result = runner.invoke(
            app,
            ["export", "claude", "--repo", "/nonexistent/path", "--task", "task"],
        )
        assert result.exit_code == 1

    def test_no_timestamp_flag(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        runner.invoke(
            app,
            [
                "export",
                "claude",
                "--repo",
                str(root),
                "--task",
                "add auth",
                "--no-timestamp",
            ],
        )
        content = (ctxdir / "CLAUDE_CONTEXT.md").read_text(encoding="utf-8")
        assert "Generated:" not in content


class TestCLIExportCodex:
    def test_exits_zero(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["export", "codex", "--repo", str(root), "--task", "add auth"])
        assert result.exit_code == 0

    def test_creates_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        runner.invoke(app, ["export", "codex", "--repo", str(root), "--task", "add auth"])
        assert (ctxdir / "CODEX_CONTEXT.md").exists()

    def test_invalid_repo_exits_one(self) -> None:
        result = runner.invoke(
            app, ["export", "codex", "--repo", "/no/such/path", "--task", "task"]
        )
        assert result.exit_code == 1


class TestCLIExportCursor:
    def test_exits_zero(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["export", "cursor", "--repo", str(root), "--task", "add auth"])
        assert result.exit_code == 0

    def test_creates_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        runner.invoke(app, ["export", "cursor", "--repo", str(root), "--task", "add auth"])
        assert (ctxdir / "CURSOR_CONTEXT.md").exists()

    def test_invalid_repo_exits_one(self) -> None:
        result = runner.invoke(
            app, ["export", "cursor", "--repo", "/no/such/path", "--task", "task"]
        )
        assert result.exit_code == 1


class TestCLIExportAider:
    def test_exits_zero(self, repo: tuple[Path, Path]) -> None:
        root, _ = repo
        result = runner.invoke(app, ["export", "aider", "--repo", str(root), "--task", "add auth"])
        assert result.exit_code == 0

    def test_creates_output_file(self, repo: tuple[Path, Path]) -> None:
        root, ctxdir = repo
        runner.invoke(app, ["export", "aider", "--repo", str(root), "--task", "add auth"])
        assert (ctxdir / "AIDER_CONTEXT.md").exists()

    def test_invalid_repo_exits_one(self) -> None:
        result = runner.invoke(
            app, ["export", "aider", "--repo", "/no/such/path", "--task", "task"]
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# CLI help
# ---------------------------------------------------------------------------


class TestCLIExportHelp:
    def test_export_group_help(self) -> None:
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "claude" in result.output
        assert "codex" in result.output
        assert "cursor" in result.output
        assert "aider" in result.output

    def test_claude_help(self) -> None:
        result = runner.invoke(app, ["export", "claude", "--help"])
        assert result.exit_code == 0

    def test_codex_help(self) -> None:
        result = runner.invoke(app, ["export", "codex", "--help"])
        assert result.exit_code == 0

    def test_cursor_help(self) -> None:
        result = runner.invoke(app, ["export", "cursor", "--help"])
        assert result.exit_code == 0

    def test_aider_help(self) -> None:
        result = runner.invoke(app, ["export", "aider", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# ExportConfig
# ---------------------------------------------------------------------------


class TestExportConfig:
    def test_defaults(self) -> None:
        cfg = ExportConfig()
        assert cfg.budget == 8000
        assert cfg.include_tests is True
        assert cfg.no_source is False
        assert cfg.add_timestamp is True

    def test_custom_values(self) -> None:
        cfg = ExportConfig(budget=4000, include_tests=False, no_source=True)
        assert cfg.budget == 4000
        assert not cfg.include_tests
        assert cfg.no_source

    def test_no_timestamp(self) -> None:
        cfg = ExportConfig(add_timestamp=False)
        assert not cfg.add_timestamp
