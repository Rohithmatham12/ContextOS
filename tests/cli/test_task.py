"""Tests for the task command — set, show, clear, bare-description form."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from contextos.cli.commands.task import _impl_clear, _impl_set, _impl_show, _task_path
from contextos.cli.main import app

runner = CliRunner()

_TASK_FILE = ".contextos/CURRENT_TASK.md"


def _set_task(tmp: Path, description: str, status: str = "In Progress") -> None:
    _impl_set(description, status, tmp)


# ---------------------------------------------------------------------------
# contextos task "<description>" — bare form (no 'set' sub-command)
# ---------------------------------------------------------------------------


class TestTaskBareDescription:
    def test_bare_description_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "fix the auth bug", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_bare_description_creates_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "fix the auth bug", "--repo", str(tmp_path)])
        assert (tmp_path / _TASK_FILE).exists()

    def test_bare_description_in_output(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "fix the auth bug", "--repo", str(tmp_path)])
        assert "fix the auth bug" in result.output

    def test_bare_description_file_contains_description(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "add rate limiting", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "add rate limiting" in content

    def test_bare_description_file_contains_timestamp(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "fix bug", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "**Set:**" in content
        # ISO timestamp present
        assert "T" in content  # e.g. 2026-06-29T12:00:00+00:00

    def test_bare_description_file_contains_status(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "fix bug", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "**Status:**" in content
        assert "In Progress" in content

    def test_bare_description_file_contains_acceptance_criteria(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "fix bug", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "## Acceptance Criteria" in content
        assert "- [ ]" in content

    def test_bare_description_file_contains_notes(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "fix bug", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "## Notes" in content

    def test_bare_description_creates_contextos_dir_if_missing(self, tmp_path: Path) -> None:
        assert not (tmp_path / ".contextos").exists()
        runner.invoke(app, ["task", "fix bug", "--repo", str(tmp_path)])
        assert (tmp_path / ".contextos").exists()

    def test_bare_description_overwrites_existing_task(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "first task", "--repo", str(tmp_path)])
        runner.invoke(app, ["task", "second task", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "second task" in content
        assert "first task" not in content


# ---------------------------------------------------------------------------
# contextos task set "<description>"
# ---------------------------------------------------------------------------


class TestTaskSet:
    def test_set_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "set", "implement auth", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_set_creates_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "implement auth", "--repo", str(tmp_path)])
        assert (tmp_path / _TASK_FILE).exists()

    def test_set_description_in_output(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "set", "implement auth", "--repo", str(tmp_path)])
        assert "implement auth" in result.output

    def test_set_description_in_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "implement auth", "--repo", str(tmp_path)])
        assert "implement auth" in (tmp_path / _TASK_FILE).read_text()

    def test_set_custom_status(self, tmp_path: Path) -> None:
        runner.invoke(
            app,
            ["task", "set", "refactor DB", "--repo", str(tmp_path), "--status", "Blocked"],
        )
        content = (tmp_path / _TASK_FILE).read_text()
        assert "Blocked" in content

    def test_set_status_in_output(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["task", "set", "refactor DB", "--repo", str(tmp_path), "--status", "Blocked"],
        )
        assert "Blocked" in result.output

    def test_set_timestamp_in_output(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        assert "Set" in result.output

    def test_set_file_starts_with_h1(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert content.startswith("# Current Task")

    def test_set_acceptance_criteria_in_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        assert "## Acceptance Criteria" in (tmp_path / _TASK_FILE).read_text()

    def test_set_notes_section_in_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        assert "## Notes" in (tmp_path / _TASK_FILE).read_text()

    def test_set_task_section_in_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        assert "## Task" in (tmp_path / _TASK_FILE).read_text()

    def test_set_creates_parent_dir(self, tmp_path: Path) -> None:
        assert not (tmp_path / ".contextos").exists()
        runner.invoke(app, ["task", "set", "x", "--repo", str(tmp_path)])
        assert (tmp_path / ".contextos").is_dir()


# ---------------------------------------------------------------------------
# contextos task show
# ---------------------------------------------------------------------------


class TestTaskShow:
    def test_show_exits_zero_with_no_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "show", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_show_no_file_prints_helpful_message(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "show", "--repo", str(tmp_path)])
        assert "No active task" in result.output

    def test_show_displays_task_description(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "refactor auth", "--repo", str(tmp_path)])
        result = runner.invoke(app, ["task", "show", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "refactor auth" in result.output

    def test_show_displays_status(self, tmp_path: Path) -> None:
        runner.invoke(
            app,
            ["task", "set", "do thing", "--repo", str(tmp_path), "--status", "Done"],
        )
        result = runner.invoke(app, ["task", "show", "--repo", str(tmp_path)])
        assert "Done" in result.output

    def test_show_after_clear_mentions_cleared(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        result = runner.invoke(app, ["task", "show", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        # Cleared template should be shown
        assert "Cleared" in result.output or "Current Task" in result.output


# ---------------------------------------------------------------------------
# contextos task clear
# ---------------------------------------------------------------------------


class TestTaskClear:
    def test_clear_exits_zero_with_existing_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        result = runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_clear_exits_zero_with_no_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_clear_no_file_prints_message(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        assert "No active task to clear" in result.output

    def test_clear_success_prints_confirmation(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        result = runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        assert "cleared" in result.output.lower()

    def test_clear_overwrites_file_with_template(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix auth bug", "--repo", str(tmp_path)])
        runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "fix auth bug" not in content

    def test_clear_file_still_has_structure(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "# Current Task" in content
        assert "## Task" in content
        assert "## Acceptance Criteria" in content
        assert "## Notes" in content

    def test_clear_sets_cleared_status(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "Cleared" in content

    def test_clear_updates_timestamp(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix bug", "--repo", str(tmp_path)])
        runner.invoke(app, ["task", "clear", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "**Set:**" in content


# ---------------------------------------------------------------------------
# contextos task (no args) — shows current task
# ---------------------------------------------------------------------------


class TestTaskNoArgs:
    def test_no_args_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_no_args_no_file_shows_message(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["task", "--repo", str(tmp_path)])
        assert "No active task" in result.output

    def test_no_args_with_task_shows_description(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "fix API", "--repo", str(tmp_path)])
        result = runner.invoke(app, ["task", "--repo", str(tmp_path)])
        assert "fix API" in result.output


# ---------------------------------------------------------------------------
# Implementation helpers (_impl_*) direct tests
# ---------------------------------------------------------------------------


class TestImplHelpers:
    def test_impl_set_creates_file(self, tmp_path: Path) -> None:
        _impl_set("test task", "In Progress", tmp_path)
        assert _task_path(tmp_path).exists()

    def test_impl_set_content(self, tmp_path: Path) -> None:
        _impl_set("do stuff", "Blocked", tmp_path)
        content = _task_path(tmp_path).read_text()
        assert "do stuff" in content
        assert "Blocked" in content
        assert "## Acceptance Criteria" in content
        assert "## Notes" in content
        assert "**Set:**" in content

    def test_impl_show_no_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _impl_show(tmp_path)  # no file → no crash

    def test_impl_clear_no_file(self, tmp_path: Path) -> None:
        _impl_clear(tmp_path)  # no file → no crash

    def test_impl_clear_resets_content(self, tmp_path: Path) -> None:
        _impl_set("original task", "In Progress", tmp_path)
        _impl_clear(tmp_path)
        content = _task_path(tmp_path).read_text()
        assert "original task" not in content
        assert "Cleared" in content

    def test_impl_set_creates_parent_dir(self, tmp_path: Path) -> None:
        nested = tmp_path / "subdir"
        _impl_set("task", "In Progress", nested)
        assert _task_path(nested).exists()

    def test_impl_set_iso_timestamp_format(self, tmp_path: Path) -> None:
        _impl_set("task", "In Progress", tmp_path)
        content = _task_path(tmp_path).read_text()
        # Look for ISO 8601 timestamp (contains 'T' and '+' or 'Z')
        import re

        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", content)


# ---------------------------------------------------------------------------
# File content structure invariants
# ---------------------------------------------------------------------------


class TestFileStructure:
    def test_h1_title(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "x", "--repo", str(tmp_path)])
        assert (tmp_path / _TASK_FILE).read_text().startswith("# Current Task")

    def test_sections_in_order(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "x", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        task_idx = content.index("## Task")
        ac_idx = content.index("## Acceptance Criteria")
        notes_idx = content.index("## Notes")
        assert task_idx < ac_idx < notes_idx

    def test_checkbox_in_acceptance_criteria(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "x", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "- [ ]" in content

    def test_status_line_present(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "x", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "**Status:**" in content

    def test_set_line_present(self, tmp_path: Path) -> None:
        runner.invoke(app, ["task", "set", "x", "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert "**Set:**" in content

    def test_multi_word_description_preserved(self, tmp_path: Path) -> None:
        desc = "implement end-to-end auth flow with OAuth2"
        runner.invoke(app, ["task", "set", desc, "--repo", str(tmp_path)])
        content = (tmp_path / _TASK_FILE).read_text()
        assert desc in content
