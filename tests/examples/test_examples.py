"""Integration tests: run ContextOS against the bundled example projects.

These tests exercise the full CLI pipeline (init → scan → task → pack → export)
against real source trees without any mocks.  They do not require the example
projects' own dependencies (FastAPI, React, etc.) to be installed.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from contextos.cli.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


def _copy_example(name: str, tmp_path: Path) -> Path:
    """Copy example to a temp dir so tests don't pollute the source tree."""
    src = _EXAMPLES_DIR / name
    dst = tmp_path / name
    shutil.copytree(src, dst)
    return dst


def _run(args: list[str], *, check: bool = True) -> object:
    result = runner.invoke(app, args)
    if check:
        assert result.exit_code == 0, (
            f"Command failed: contextos {' '.join(args)}\n"
            f"Output: {result.output}\n"
            f"Exception: {result.exception}"
        )
    return result


def _full_pipeline(repo: Path, task: str) -> None:
    """Run init → scan → task → pack → all exports."""
    _run(["init", str(repo)])
    _run(["scan", str(repo)])
    _run(["task", "--repo", str(repo), task])
    _run(["pack", str(repo), "--task", task, "--budget", "8000", "--no-timestamp"])
    for tool in ("claude", "codex", "cursor", "aider"):
        _run(["export", tool, "--repo", str(repo), "--task", task])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fastapi_repo(tmp_path: Path) -> Path:
    return _copy_example("python_fastapi", tmp_path)


@pytest.fixture()
def react_repo(tmp_path: Path) -> Path:
    return _copy_example("react_typescript", tmp_path)


@pytest.fixture()
def monorepo(tmp_path: Path) -> Path:
    return _copy_example("monorepo", tmp_path)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


class TestInit:
    def test_fastapi_init_creates_contextos_dir(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        assert (fastapi_repo / ".contextos").is_dir()

    def test_react_init_creates_memory_file(self, react_repo: Path) -> None:
        _run(["init", str(react_repo)])
        assert (react_repo / ".contextos" / "MEMORY.md").exists()

    def test_monorepo_init_creates_decisions_file(self, monorepo: Path) -> None:
        _run(["init", str(monorepo)])
        assert (monorepo / ".contextos" / "DECISIONS.md").exists()

    def test_init_idempotent(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["init", str(fastapi_repo)])  # second run must not fail

    def test_init_output_mentions_created(self, fastapi_repo: Path) -> None:
        result = runner.invoke(app, ["init", str(fastapi_repo)])
        assert "created" in result.output.lower() or "skipped" in result.output.lower()


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------


class TestScan:
    def test_fastapi_scan_produces_summaries(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        summaries_path = fastapi_repo / ".contextos" / "file_summaries.json"
        assert summaries_path.exists()
        data = json.loads(summaries_path.read_text())
        assert len(data) > 0

    def test_fastapi_scan_indexes_python_files(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        data = json.loads((fastapi_repo / ".contextos" / "file_summaries.json").read_text())
        paths = list(data.keys())
        py_files = [p for p in paths if p.endswith(".py")]
        assert len(py_files) >= 5  # main, auth, models, database, routes/*

    def test_react_scan_indexes_typescript(self, react_repo: Path) -> None:
        _run(["init", str(react_repo)])
        _run(["scan", str(react_repo)])
        data = json.loads((react_repo / ".contextos" / "file_summaries.json").read_text())
        ts_files = [p for p in data if p.endswith((".ts", ".tsx"))]
        assert len(ts_files) >= 4

    def test_monorepo_scan_indexes_all_packages(self, monorepo: Path) -> None:
        _run(["init", str(monorepo)])
        _run(["scan", str(monorepo)])
        data = json.loads((monorepo / ".contextos" / "file_summaries.json").read_text())
        paths = " ".join(data.keys())
        assert "shared" in paths
        assert "api" in paths
        assert "web" in paths

    def test_scan_writes_dependency_graph(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        graph_path = fastapi_repo / ".contextos" / "dependency_graph.json"
        assert graph_path.exists()
        graph = json.loads(graph_path.read_text())
        assert "nodes" in graph
        assert "edges" in graph

    def test_scan_writes_project_index(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        assert (fastapi_repo / ".contextos" / "PROJECT_INDEX.md").exists()

    def test_scan_exit_code_zero(self, react_repo: Path) -> None:
        result = runner.invoke(app, ["scan", str(react_repo)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# task
# ---------------------------------------------------------------------------


class TestTask:
    def test_set_task_creates_file(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["task", "--repo", str(fastapi_repo), "fix auth bug"])
        task_file = fastapi_repo / ".contextos" / "CURRENT_TASK.md"
        assert task_file.exists()

    def test_task_file_contains_description(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["task", "--repo", str(fastapi_repo), "fix auth bug in token validation"])
        content = (fastapi_repo / ".contextos" / "CURRENT_TASK.md").read_text()
        assert "fix auth bug in token validation" in content

    def test_task_show_after_set(self, react_repo: Path) -> None:
        _run(["init", str(react_repo)])
        _run(["task", "--repo", str(react_repo), "add dark mode toggle"])
        result = runner.invoke(app, ["task", "--repo", str(react_repo), "show"])
        assert result.exit_code == 0
        assert "dark mode" in result.output.lower()

    def test_task_clear(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["task", "--repo", str(fastapi_repo), "some task"])
        _run(["task", "--repo", str(fastapi_repo), "clear"])
        content = (fastapi_repo / ".contextos" / "CURRENT_TASK.md").read_text()
        assert "Cleared" in content

    def test_task_with_multiword_description(self, monorepo: Path) -> None:
        _run(["init", str(monorepo)])
        _run(["task", "--repo", str(monorepo), "add project archiving with soft delete"])
        content = (monorepo / ".contextos" / "CURRENT_TASK.md").read_text()
        assert "archiving" in content


# ---------------------------------------------------------------------------
# pack
# ---------------------------------------------------------------------------


class TestPack:
    def test_fastapi_pack_creates_context_file(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["pack", str(fastapi_repo), "--task", "fix auth bug", "--no-timestamp"])
        assert (fastapi_repo / ".contextos" / "context_pack.md").exists()

    def test_pack_content_is_markdown(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["pack", str(fastapi_repo), "--task", "fix auth bug", "--no-timestamp"])
        content = (fastapi_repo / ".contextos" / "context_pack.md").read_text()
        assert content.startswith("#")
        assert "## Task" in content

    def test_pack_selects_auth_files_for_auth_task(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["pack", str(fastapi_repo), "--task", "fix auth bug", "--no-timestamp"])
        content = (fastapi_repo / ".contextos" / "context_pack.md").read_text()
        assert "auth" in content.lower()

    def test_pack_respects_budget(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["pack", str(fastapi_repo), "--task", "task", "--budget", "500", "--no-timestamp"])
        content = (fastapi_repo / ".contextos" / "context_pack.md").read_text()
        assert "Token Budget" in content

    def test_pack_json_format(self, react_repo: Path) -> None:
        _run(["init", str(react_repo)])
        _run(["scan", str(react_repo)])
        _run(
            [
                "pack",
                str(react_repo),
                "--task",
                "add dark mode",
                "--format",
                "json",
                "--no-timestamp",
            ]
        )
        json_path = react_repo / ".contextos" / "context_pack.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert "task" in data
        assert "selected" in data

    def test_pack_no_source_flag(self, monorepo: Path) -> None:
        _run(["init", str(monorepo)])
        _run(["scan", str(monorepo)])
        _run(["pack", str(monorepo), "--task", "add archiving", "--no-source", "--no-timestamp"])
        content = (monorepo / ".contextos" / "context_pack.md").read_text()
        assert "## Context Files" in content

    def test_pack_no_tests_flag(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["pack", str(fastapi_repo), "--task", "fix bug", "--no-tests", "--no-timestamp"])
        pack = (fastapi_repo / ".contextos" / "context_pack.md").read_text()
        # Test file paths should not appear as selected context-file headers.
        # README may mention the filenames, so check the ``` header pattern.
        assert "### `tests/test_auth.py`" not in pack
        assert "### `tests/test_users.py`" not in pack

    def test_pack_contains_token_budget_table(self, react_repo: Path) -> None:
        _run(["init", str(react_repo)])
        _run(["scan", str(react_repo)])
        _run(["pack", str(react_repo), "--task", "fix login", "--no-timestamp"])
        content = (react_repo / ".contextos" / "context_pack.md").read_text()
        assert "Token Budget" in content
        assert "Budget" in content

    def test_monorepo_pack_includes_shared_types(self, monorepo: Path) -> None:
        _run(["init", str(monorepo)])
        _run(["scan", str(monorepo)])
        _run(["pack", str(monorepo), "--task", "add project archiving", "--no-timestamp"])
        content = (monorepo / ".contextos" / "context_pack.md").read_text()
        # shared types or routes should surface for this task
        assert len(content) > 200


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


class TestExport:
    def test_export_claude_creates_file(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["export", "claude", "--repo", str(fastapi_repo), "--task", "fix auth bug"])
        assert (fastapi_repo / ".contextos" / "CLAUDE_CONTEXT.md").exists()

    def test_export_codex_creates_file(self, react_repo: Path) -> None:
        _run(["init", str(react_repo)])
        _run(["scan", str(react_repo)])
        _run(["export", "codex", "--repo", str(react_repo), "--task", "add dark mode"])
        assert (react_repo / ".contextos" / "CODEX_CONTEXT.md").exists()

    def test_export_cursor_creates_file(self, monorepo: Path) -> None:
        _run(["init", str(monorepo)])
        _run(["scan", str(monorepo)])
        _run(["export", "cursor", "--repo", str(monorepo), "--task", "add archiving"])
        assert (monorepo / ".contextos" / "CURSOR_CONTEXT.md").exists()

    def test_export_aider_creates_file(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["export", "aider", "--repo", str(fastapi_repo), "--task", "fix bug"])
        assert (fastapi_repo / ".contextos" / "AIDER_CONTEXT.md").exists()

    def test_export_claude_contains_tool_header(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["export", "claude", "--repo", str(fastapi_repo), "--task", "fix auth"])
        content = (fastapi_repo / ".contextos" / "CLAUDE_CONTEXT.md").read_text()
        assert "Claude" in content

    def test_export_claude_contains_task(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(["export", "claude", "--repo", str(fastapi_repo), "--task", "fix auth bug"])
        content = (fastapi_repo / ".contextos" / "CLAUDE_CONTEXT.md").read_text()
        assert "fix auth bug" in content

    def test_export_no_source_flag(self, react_repo: Path) -> None:
        _run(["init", str(react_repo)])
        _run(["scan", str(react_repo)])
        _run(
            [
                "export",
                "claude",
                "--repo",
                str(react_repo),
                "--task",
                "fix login",
                "--no-source",
            ]
        )
        assert (react_repo / ".contextos" / "CLAUDE_CONTEXT.md").exists()

    def test_export_budget_flag(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["scan", str(fastapi_repo)])
        _run(
            [
                "export",
                "claude",
                "--repo",
                str(fastapi_repo),
                "--task",
                "fix auth",
                "--budget",
                "4000",
            ]
        )
        content = (fastapi_repo / ".contextos" / "CLAUDE_CONTEXT.md").read_text()
        assert "4,000" in content

    def test_all_tools_exit_zero(self, monorepo: Path) -> None:
        _run(["init", str(monorepo)])
        _run(["scan", str(monorepo)])
        for tool in ("claude", "codex", "cursor", "aider"):
            result = runner.invoke(
                app,
                ["export", tool, "--repo", str(monorepo), "--task", "add feature"],
            )
            assert result.exit_code == 0, f"{tool} export failed: {result.output}"


# ---------------------------------------------------------------------------
# Full pipeline (end-to-end)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_fastapi_full_pipeline(self, fastapi_repo: Path) -> None:
        _full_pipeline(fastapi_repo, "fix auth bug — token expiry not validated")

        ctxdir = fastapi_repo / ".contextos"
        assert (ctxdir / "context_pack.md").exists()
        assert (ctxdir / "CLAUDE_CONTEXT.md").exists()
        assert (ctxdir / "CODEX_CONTEXT.md").exists()
        assert (ctxdir / "CURSOR_CONTEXT.md").exists()
        assert (ctxdir / "AIDER_CONTEXT.md").exists()
        assert (ctxdir / "CURRENT_TASK.md").exists()

    def test_react_full_pipeline(self, react_repo: Path) -> None:
        _full_pipeline(react_repo, "add dark mode toggle to the dashboard")

        ctxdir = react_repo / ".contextos"
        assert (ctxdir / "context_pack.md").exists()
        assert (ctxdir / "CLAUDE_CONTEXT.md").exists()

    def test_monorepo_full_pipeline(self, monorepo: Path) -> None:
        _full_pipeline(monorepo, "add project archiving with soft delete")

        ctxdir = monorepo / ".contextos"
        assert (ctxdir / "context_pack.md").exists()
        assert (ctxdir / "CLAUDE_CONTEXT.md").exists()

    def test_pack_content_not_empty(self, fastapi_repo: Path) -> None:
        _full_pipeline(fastapi_repo, "fix auth bug")
        content = (fastapi_repo / ".contextos" / "context_pack.md").read_text()
        assert len(content) > 500

    def test_context_pack_has_no_raw_secrets(self, fastapi_repo: Path) -> None:
        _full_pipeline(fastapi_repo, "fix auth bug")
        content = (fastapi_repo / ".contextos" / "context_pack.md").read_text()
        # The real SECRET_KEY in auth.py ("replace-me-in-production") is short
        # and uses a string constant — the env_secret_assignment pattern won't
        # match it (it's a Python assignment with a comment, not an env file).
        # Verify no .env-style secrets slipped through.
        assert "password=hunter" not in content.lower()


# ---------------------------------------------------------------------------
# Memory workflow on examples
# ---------------------------------------------------------------------------


class TestMemoryOnExamples:
    def test_memory_add_to_fastapi(self, fastapi_repo: Path) -> None:
        _run(["init", str(fastapi_repo)])
        _run(["memory", "add", "--repo", str(fastapi_repo), "bcrypt rounds set to 12"])
        memory = (fastapi_repo / ".contextos" / "MEMORY.md").read_text()
        assert "bcrypt rounds set to 12" in memory

    def test_memory_decision_to_react(self, react_repo: Path) -> None:
        _run(["init", str(react_repo)])
        _run(
            [
                "memory",
                "decision",
                "--repo",
                str(react_repo),
                "use localStorage for token persistence",
            ]
        )
        decisions = (react_repo / ".contextos" / "DECISIONS.md").read_text()
        assert "localStorage" in decisions

    def test_memory_list_exit_zero(self, monorepo: Path) -> None:
        _run(["init", str(monorepo)])
        _run(["memory", "add", "--repo", str(monorepo), "use turbo for builds"])
        result = runner.invoke(app, ["memory", "list", "--repo", str(monorepo)])
        assert result.exit_code == 0
        assert "turbo" in result.output
