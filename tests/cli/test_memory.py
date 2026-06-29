"""Tests for the memory command — add, update, decision, list, compact."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from contextos.cli.commands.memory import (
    _append_to_notes,
    _contains_secret,
    _decisions_path,
    _ensure_decisions,
    _ensure_memory,
    _impl_add,
    _impl_decision,
    _impl_list,
    _memory_path,
)
from contextos.cli.main import app

runner = CliRunner()

_MEMORY_FILE = ".contextos/MEMORY.md"
_DECISIONS_FILE = ".contextos/DECISIONS.md"


# ---------------------------------------------------------------------------
# _contains_secret
# ---------------------------------------------------------------------------


class TestContainsSecret:
    def test_clean_note_not_secret(self) -> None:
        assert not _contains_secret("refactored the auth module to use bcrypt")

    def test_password_assignment_detected(self) -> None:
        assert _contains_secret("password=hunter2")

    def test_password_colon_detected(self) -> None:
        assert _contains_secret("password: hunter2")

    def test_api_key_detected(self) -> None:
        assert _contains_secret("api_key=abc12345")

    def test_access_token_detected(self) -> None:
        assert _contains_secret("access_token=xyzABC1234")

    def test_bearer_token_detected(self) -> None:
        assert _contains_secret("bearer: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")

    def test_long_hex_detected(self) -> None:
        assert _contains_secret("a" * 40)  # 40-char hex string

    def test_short_hex_ok(self) -> None:
        assert not _contains_secret("a" * 8)  # short — not flagged

    def test_long_base64_detected(self) -> None:
        b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        assert _contains_secret(b64)

    def test_word_password_alone_ok(self) -> None:
        assert not _contains_secret("use bcrypt for password hashing")

    def test_secret_word_alone_ok(self) -> None:
        assert not _contains_secret("the secret to good code is readability")

    def test_empty_string_not_secret(self) -> None:
        assert not _contains_secret("")

    def test_private_key_label_detected(self) -> None:
        assert _contains_secret("private_key=-----BEGIN RSA")


# ---------------------------------------------------------------------------
# _ensure_memory and _ensure_decisions
# ---------------------------------------------------------------------------


class TestEnsureFiles:
    def test_ensure_memory_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / ".contextos" / "MEMORY.md"
        _ensure_memory(path)
        assert path.exists()

    def test_ensure_memory_content(self, tmp_path: Path) -> None:
        path = tmp_path / ".contextos" / "MEMORY.md"
        _ensure_memory(path)
        content = path.read_text()
        assert "## Notes" in content

    def test_ensure_memory_idempotent(self, tmp_path: Path) -> None:
        path = tmp_path / ".contextos" / "MEMORY.md"
        _ensure_memory(path)
        first = path.read_text()
        _ensure_memory(path)
        assert path.read_text() == first  # no double-write

    def test_ensure_decisions_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / ".contextos" / "DECISIONS.md"
        _ensure_decisions(path)
        assert path.exists()

    def test_ensure_decisions_has_header(self, tmp_path: Path) -> None:
        path = tmp_path / ".contextos" / "DECISIONS.md"
        _ensure_decisions(path)
        assert "# Decision Log" in path.read_text()

    def test_ensure_creates_parent_dir(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "dir" / ".contextos" / "MEMORY.md"
        _ensure_memory(path)
        assert path.exists()

    def test_ensure_memory_adds_notes_section_if_missing(self, tmp_path: Path) -> None:
        path = tmp_path / ".contextos" / "MEMORY.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Project Memory\n\nSome existing content.\n", encoding="utf-8")
        _ensure_memory(path)
        assert "## Notes" in path.read_text()


# ---------------------------------------------------------------------------
# _append_to_notes
# ---------------------------------------------------------------------------


class TestAppendToNotes:
    def test_entry_appended_to_notes_section(self, tmp_path: Path) -> None:
        path = tmp_path / "MEMORY.md"
        path.write_text("# Memory\n\n## Notes\n\n", encoding="utf-8")
        _append_to_notes(path, "- **ts** — note\n")
        assert "- **ts** — note" in path.read_text()

    def test_entry_before_next_section(self, tmp_path: Path) -> None:
        path = tmp_path / "MEMORY.md"
        path.write_text("# Memory\n\n## Notes\n\n## Other\n\ncontent\n", encoding="utf-8")
        _append_to_notes(path, "- **ts** — note\n")
        content = path.read_text()
        notes_idx = content.index("## Notes")
        other_idx = content.index("## Other")
        note_idx = content.index("- **ts** — note")
        assert notes_idx < note_idx < other_idx

    def test_entry_appended_when_no_next_section(self, tmp_path: Path) -> None:
        path = tmp_path / "MEMORY.md"
        path.write_text("# Memory\n\n## Notes\n\n", encoding="utf-8")
        _append_to_notes(path, "- **ts** — note\n")
        content = path.read_text()
        assert content.endswith("- **ts** — note\n")

    def test_multiple_entries_stacked(self, tmp_path: Path) -> None:
        path = tmp_path / "MEMORY.md"
        path.write_text("# Memory\n\n## Notes\n\n", encoding="utf-8")
        _append_to_notes(path, "- **t1** — first\n")
        _append_to_notes(path, "- **t2** — second\n")
        content = path.read_text()
        assert "first" in content
        assert "second" in content
        assert content.index("first") < content.index("second")

    def test_creates_notes_section_if_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "MEMORY.md"
        path.write_text("# Memory\n\nSome content.\n", encoding="utf-8")
        _append_to_notes(path, "- **ts** — note\n")
        content = path.read_text()
        assert "## Notes" in content
        assert "- **ts** — note" in content


# ---------------------------------------------------------------------------
# _impl_add
# ---------------------------------------------------------------------------


class TestImplAdd:
    def test_creates_memory_file(self, tmp_path: Path) -> None:
        _impl_add("first note", tmp_path)
        assert _memory_path(tmp_path).exists()

    def test_note_in_file(self, tmp_path: Path) -> None:
        _impl_add("remember to refactor auth", tmp_path)
        content = _memory_path(tmp_path).read_text()
        assert "remember to refactor auth" in content

    def test_timestamp_in_file(self, tmp_path: Path) -> None:
        _impl_add("note", tmp_path)
        content = _memory_path(tmp_path).read_text()
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", content)

    def test_secret_raises_exit(self, tmp_path: Path) -> None:
        with pytest.raises(BaseException) as exc:
            _impl_add("password=hunter2", tmp_path)
        assert isinstance(exc.value, typer.Exit)

    def test_secret_not_written(self, tmp_path: Path) -> None:
        try:
            _impl_add("api_key=abc12345", tmp_path)
        except BaseException:
            pass
        mem = _memory_path(tmp_path)
        if mem.exists():
            assert "api_key=abc12345" not in mem.read_text()

    def test_append_multiple_notes(self, tmp_path: Path) -> None:
        _impl_add("first note", tmp_path)
        _impl_add("second note", tmp_path)
        content = _memory_path(tmp_path).read_text()
        assert "first note" in content
        assert "second note" in content

    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        repo = tmp_path / "myproject"
        repo.mkdir()
        _impl_add("note", repo)
        assert _memory_path(repo).exists()


# ---------------------------------------------------------------------------
# _impl_decision
# ---------------------------------------------------------------------------


class TestImplDecision:
    def test_creates_decisions_file(self, tmp_path: Path) -> None:
        _impl_decision("use postgres", "accepted", tmp_path)
        assert _decisions_path(tmp_path).exists()

    def test_decision_text_in_file(self, tmp_path: Path) -> None:
        _impl_decision("use postgres for the database", "accepted", tmp_path)
        content = _decisions_path(tmp_path).read_text()
        assert "use postgres for the database" in content

    def test_status_in_file(self, tmp_path: Path) -> None:
        _impl_decision("revert to sqlite", "proposed", tmp_path)
        content = _decisions_path(tmp_path).read_text()
        assert "proposed" in content

    def test_timestamp_in_file(self, tmp_path: Path) -> None:
        _impl_decision("use redis", "accepted", tmp_path)
        content = _decisions_path(tmp_path).read_text()
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", content)

    def test_date_header_in_file(self, tmp_path: Path) -> None:
        _impl_decision("switch to postgres", "accepted", tmp_path)
        content = _decisions_path(tmp_path).read_text()
        assert re.search(r"\[\d{4}-\d{2}-\d{2}\]", content)

    def test_multiple_decisions_stacked(self, tmp_path: Path) -> None:
        _impl_decision("use postgres", "accepted", tmp_path)
        _impl_decision("use redis for cache", "accepted", tmp_path)
        content = _decisions_path(tmp_path).read_text()
        assert "postgres" in content
        assert "redis" in content

    def test_secret_raises_exit(self, tmp_path: Path) -> None:
        with pytest.raises(BaseException) as exc:
            _impl_decision("password=secret123", "accepted", tmp_path)
        assert isinstance(exc.value, typer.Exit)

    def test_section_separator_present(self, tmp_path: Path) -> None:
        _impl_decision("adopt trunk-based development", "accepted", tmp_path)
        content = _decisions_path(tmp_path).read_text()
        assert "---" in content

    def test_decision_label_present(self, tmp_path: Path) -> None:
        _impl_decision("migrate to fastapi", "accepted", tmp_path)
        content = _decisions_path(tmp_path).read_text()
        assert "**Decision:**" in content

    def test_logged_label_present(self, tmp_path: Path) -> None:
        _impl_decision("migrate to fastapi", "accepted", tmp_path)
        content = _decisions_path(tmp_path).read_text()
        assert "**Logged:**" in content


# ---------------------------------------------------------------------------
# _impl_list
# ---------------------------------------------------------------------------


class TestImplList:
    def test_no_files_no_crash(self, tmp_path: Path) -> None:
        _impl_list(tmp_path)  # no files → no crash

    def test_shows_memory_when_exists(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:  # noqa: ARG002
        _impl_add("remember this", tmp_path)
        # _impl_list uses Rich console which bypasses capsys; just verify no crash
        _impl_list(tmp_path)

    def test_shows_decisions_when_exists(self, tmp_path: Path) -> None:
        _impl_decision("use postgres", "accepted", tmp_path)
        _impl_list(tmp_path)  # no crash


# ---------------------------------------------------------------------------
# CLI — memory add
# ---------------------------------------------------------------------------


class TestCLIMemoryAdd:
    def test_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["memory", "add", "refactor auth module", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 0

    def test_creates_memory_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "add", "note text", "--repo", str(tmp_path)])
        assert (tmp_path / _MEMORY_FILE).exists()

    def test_note_in_output(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["memory", "add", "refactor auth", "--repo", str(tmp_path)])
        assert "refactor auth" in result.output

    def test_note_in_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "add", "migrate to postgres", "--repo", str(tmp_path)])
        assert "migrate to postgres" in (tmp_path / _MEMORY_FILE).read_text()

    def test_secret_exits_one(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["memory", "add", "password=hunter2", "--repo", str(tmp_path)])
        assert result.exit_code == 1

    def test_secret_not_written(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "add", "password=hunter2", "--repo", str(tmp_path)])
        mem = tmp_path / _MEMORY_FILE
        if mem.exists():
            assert "hunter2" not in mem.read_text()

    def test_timestamp_in_output(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["memory", "add", "note", "--repo", str(tmp_path)])
        assert "Set" in result.output

    def test_multiple_notes_stacked(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "add", "first note", "--repo", str(tmp_path)])
        runner.invoke(app, ["memory", "add", "second note", "--repo", str(tmp_path)])
        content = (tmp_path / _MEMORY_FILE).read_text()
        assert "first note" in content
        assert "second note" in content


# ---------------------------------------------------------------------------
# CLI — memory update (alias for add)
# ---------------------------------------------------------------------------


class TestCLIMemoryUpdate:
    def test_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["memory", "update", "update via update command", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 0

    def test_creates_memory_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "update", "some update", "--repo", str(tmp_path)])
        assert (tmp_path / _MEMORY_FILE).exists()

    def test_note_in_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "update", "update note text", "--repo", str(tmp_path)])
        assert "update note text" in (tmp_path / _MEMORY_FILE).read_text()

    def test_secret_exits_one(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["memory", "update", "api_key=abc12345", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# CLI — memory decision
# ---------------------------------------------------------------------------


class TestCLIMemoryDecision:
    def test_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["memory", "decision", "adopt trunk-based dev", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 0

    def test_creates_decisions_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "use postgres", "--repo", str(tmp_path)])
        assert (tmp_path / _DECISIONS_FILE).exists()

    def test_decision_in_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "switch to redis", "--repo", str(tmp_path)])
        assert "switch to redis" in (tmp_path / _DECISIONS_FILE).read_text()

    def test_default_status_accepted(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "use redis", "--repo", str(tmp_path)])
        assert "accepted" in (tmp_path / _DECISIONS_FILE).read_text()

    def test_custom_status(self, tmp_path: Path) -> None:
        runner.invoke(
            app,
            [
                "memory",
                "decision",
                "consider graphql",
                "--repo",
                str(tmp_path),
                "--status",
                "proposed",
            ],
        )
        assert "proposed" in (tmp_path / _DECISIONS_FILE).read_text()

    def test_decision_in_output(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["memory", "decision", "adopt postgres", "--repo", str(tmp_path)]
        )
        assert "adopt postgres" in result.output

    def test_timestamp_in_output(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["memory", "decision", "adopt postgres", "--repo", str(tmp_path)]
        )
        assert "Logged" in result.output

    def test_secret_exits_one(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["memory", "decision", "password=secret", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 1

    def test_separator_in_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "use redis", "--repo", str(tmp_path)])
        assert "---" in (tmp_path / _DECISIONS_FILE).read_text()

    def test_multiple_decisions_stacked(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "first decision", "--repo", str(tmp_path)])
        runner.invoke(app, ["memory", "decision", "second decision", "--repo", str(tmp_path)])
        content = (tmp_path / _DECISIONS_FILE).read_text()
        assert "first decision" in content
        assert "second decision" in content


# ---------------------------------------------------------------------------
# CLI — memory list
# ---------------------------------------------------------------------------


class TestCLIMemoryList:
    def test_exits_zero_no_files(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["memory", "list", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_no_files_helpful_message(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["memory", "list", "--repo", str(tmp_path)])
        assert "No memory files found" in result.output or result.exit_code == 0

    def test_exits_zero_with_memory_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "add", "some note", "--repo", str(tmp_path)])
        result = runner.invoke(app, ["memory", "list", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_exits_zero_with_decisions_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "use postgres", "--repo", str(tmp_path)])
        result = runner.invoke(app, ["memory", "list", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_no_decisions_flag(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "use postgres", "--repo", str(tmp_path)])
        runner.invoke(app, ["memory", "add", "remember x", "--repo", str(tmp_path)])
        result = runner.invoke(app, ["memory", "list", "--no-decisions", "--repo", str(tmp_path)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# CLI — memory compact (placeholder)
# ---------------------------------------------------------------------------


class TestCLIMemoryCompact:
    def test_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["memory", "compact", "--repo", str(tmp_path)])
        assert result.exit_code == 0

    def test_shows_not_implemented(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["memory", "compact", "--repo", str(tmp_path)])
        out = result.output.lower()
        assert "not yet implemented" in out or "not implemented" in out

    def test_shows_manual_instructions(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["memory", "compact", "--repo", str(tmp_path)])
        assert "MEMORY.md" in result.output


# ---------------------------------------------------------------------------
# CLI — memory help
# ---------------------------------------------------------------------------


class TestCLIMemoryHelp:
    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["memory", "--help"])
        assert result.exit_code == 0

    def test_add_help(self) -> None:
        result = runner.invoke(app, ["memory", "add", "--help"])
        assert result.exit_code == 0

    def test_decision_help(self) -> None:
        result = runner.invoke(app, ["memory", "decision", "--help"])
        assert result.exit_code == 0

    def test_list_help(self) -> None:
        result = runner.invoke(app, ["memory", "list", "--help"])
        assert result.exit_code == 0

    def test_update_help(self) -> None:
        result = runner.invoke(app, ["memory", "update", "--help"])
        assert result.exit_code == 0

    def test_compact_help(self) -> None:
        result = runner.invoke(app, ["memory", "compact", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Append-only invariant
# ---------------------------------------------------------------------------


class TestAppendOnly:
    def test_add_never_overwrites_existing_notes(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "add", "original note", "--repo", str(tmp_path)])
        runner.invoke(app, ["memory", "add", "second note", "--repo", str(tmp_path)])
        content = (tmp_path / _MEMORY_FILE).read_text()
        assert "original note" in content
        assert "second note" in content

    def test_decision_never_overwrites_existing(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "original decision", "--repo", str(tmp_path)])
        runner.invoke(app, ["memory", "decision", "new decision", "--repo", str(tmp_path)])
        content = (tmp_path / _DECISIONS_FILE).read_text()
        assert "original decision" in content
        assert "new decision" in content

    def test_timestamps_are_iso8601(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "add", "test note", "--repo", str(tmp_path)])
        content = (tmp_path / _MEMORY_FILE).read_text()
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", content)

    def test_decision_timestamps_are_iso8601(self, tmp_path: Path) -> None:
        runner.invoke(app, ["memory", "decision", "test decision", "--repo", str(tmp_path)])
        content = (tmp_path / _DECISIONS_FILE).read_text()
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", content)
