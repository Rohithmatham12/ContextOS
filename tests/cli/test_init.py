"""Tests for `contextos init` command and the initializer core module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from contextos.cli.main import app
from contextos.core import initializer

runner = CliRunner()

EXPECTED_FILES = sorted(initializer.ALL_FILES)


# ---------------------------------------------------------------------------
# Core initializer unit tests
# ---------------------------------------------------------------------------


class TestInitializerFirstRun:
    def test_creates_contextos_dir(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        assert (tmp_path / ".contextos").is_dir()

    def test_creates_all_files(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        for name in EXPECTED_FILES:
            assert (tmp_path / ".contextos" / name).exists(), f"missing: {name}"

    def test_all_files_have_content(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        for name in EXPECTED_FILES:
            content = (tmp_path / ".contextos" / name).read_text(encoding="utf-8")
            assert content.strip(), f"{name} is empty"

    def test_all_results_created(self, tmp_path: Path) -> None:
        result = initializer.run(tmp_path)
        assert len(result.created) == len(EXPECTED_FILES)
        assert len(result.skipped) == 0
        assert len(result.errors) == 0

    def test_config_json_is_valid(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        raw = (tmp_path / ".contextos" / "CONFIG.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "version" in data
        assert "scan" in data
        assert "pack" in data

    def test_file_summaries_json_is_valid_empty(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        raw = (tmp_path / ".contextos" / "file_summaries.json").read_text(encoding="utf-8")
        assert json.loads(raw) == {}

    def test_dependency_graph_json_is_valid(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        raw = (tmp_path / ".contextos" / "dependency_graph.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "nodes" in data
        assert "edges" in data

    def test_returns_correct_root(self, tmp_path: Path) -> None:
        result = initializer.run(tmp_path)
        assert result.root == tmp_path.resolve()
        assert result.contextos_dir == tmp_path.resolve() / ".contextos"

    def test_idempotent_directory_creation(self, tmp_path: Path) -> None:
        """Running twice should not raise even if dir already exists."""
        initializer.run(tmp_path)
        initializer.run(tmp_path)  # must not raise


class TestInitializerRepeatedRun:
    def test_existing_memory_files_are_skipped(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        # Modify a memory file
        mem = tmp_path / ".contextos" / "MEMORY.md"
        mem.write_text("user content", encoding="utf-8")

        initializer.run(tmp_path)
        assert mem.read_text(encoding="utf-8") == "user content"

    def test_all_files_skipped_on_second_run(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        result = initializer.run(tmp_path)
        assert len(result.skipped) == len(EXPECTED_FILES)
        assert len(result.created) == 0

    def test_skipped_files_retain_custom_content(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        for name in initializer.MEMORY_FILES:
            path = tmp_path / ".contextos" / name
            path.write_text(f"custom:{name}", encoding="utf-8")

        initializer.run(tmp_path)

        for name in initializer.MEMORY_FILES:
            content = (tmp_path / ".contextos" / name).read_text(encoding="utf-8")
            assert content == f"custom:{name}", f"{name} was overwritten"


class TestInitializerForce:
    def test_force_overwrites_all_files(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        # Mutate every file
        for name in EXPECTED_FILES:
            (tmp_path / ".contextos" / name).write_text("REPLACED", encoding="utf-8")

        initializer.run(tmp_path, force=True)

        for name in EXPECTED_FILES:
            content = (tmp_path / ".contextos" / name).read_text(encoding="utf-8")
            assert content != "REPLACED", f"{name} was not restored"

    def test_force_result_shows_overwritten(self, tmp_path: Path) -> None:
        initializer.run(tmp_path)
        result = initializer.run(tmp_path, force=True)
        assert len(result.overwritten) == len(EXPECTED_FILES)
        assert len(result.created) == 0
        assert len(result.skipped) == 0

    def test_force_on_fresh_dir_shows_created(self, tmp_path: Path) -> None:
        result = initializer.run(tmp_path, force=True)
        # No existing files → all created, none overwritten
        assert len(result.created) == len(EXPECTED_FILES)
        assert len(result.overwritten) == 0


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestInitCLIFirstRun:
    def test_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0

    def test_creates_contextos_dir(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        assert (tmp_path / ".contextos").is_dir()

    def test_creates_all_expected_files(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        for name in EXPECTED_FILES:
            assert (tmp_path / ".contextos" / name).exists()

    def test_output_mentions_created(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert "created" in result.output

    def test_quiet_flag_suppresses_table(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path), "--quiet"])
        assert result.exit_code == 0
        # Table uses "✓" — quiet should suppress it
        assert "✓" not in result.output


class TestInitCLIRepeatedRun:
    def test_repeated_run_exits_zero(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0

    def test_repeated_run_shows_skipped(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert "skipped" in result.output

    def test_repeated_run_does_not_overwrite_memory(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        mem = tmp_path / ".contextos" / "MEMORY.md"
        mem.write_text("do not touch", encoding="utf-8")
        runner.invoke(app, ["init", str(tmp_path)])
        assert mem.read_text(encoding="utf-8") == "do not touch"


class TestInitCLIForce:
    def test_force_exits_zero(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        result = runner.invoke(app, ["init", str(tmp_path), "--force"])
        assert result.exit_code == 0

    def test_force_overwrites_memory_file(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        mem = tmp_path / ".contextos" / "MEMORY.md"
        mem.write_text("custom content", encoding="utf-8")
        runner.invoke(app, ["init", str(tmp_path), "--force"])
        assert mem.read_text(encoding="utf-8") != "custom content"

    def test_force_output_mentions_overwritten(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        result = runner.invoke(app, ["init", str(tmp_path), "--force"])
        assert "overwritten" in result.output

    def test_short_flag_f_works(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        result = runner.invoke(app, ["init", str(tmp_path), "-f"])
        assert result.exit_code == 0


class TestInitCLIEdgeCases:
    def test_nonexistent_directory_exits_one(self) -> None:
        result = runner.invoke(app, ["init", "/nonexistent/path/abc123"])
        assert result.exit_code == 1

    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0

    def test_default_directory_is_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / ".contextos").is_dir()
