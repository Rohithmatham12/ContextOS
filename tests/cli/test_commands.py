"""CLI command invocation tests using Typer's test runner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from contextos.cli.main import app

runner = CliRunner()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "contextos" in result.output.lower()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.2" in result.output


def test_init_help() -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0


def test_scan_help() -> None:
    result = runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0


def test_task_help() -> None:
    result = runner.invoke(app, ["task", "--help"])
    assert result.exit_code == 0


def test_pack_help() -> None:
    result = runner.invoke(app, ["pack", "--help"])
    assert result.exit_code == 0


def test_memory_help() -> None:
    result = runner.invoke(app, ["memory", "--help"])
    assert result.exit_code == 0


def test_init_creates_contextos_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".contextos").is_dir()


def test_init_repeated_run_exits_zero(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])  # first run
    result = runner.invoke(app, ["init", str(tmp_path)])  # second run — safe, exits 0
    assert result.exit_code == 0


def test_init_force_overwrites(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    result = runner.invoke(app, ["init", str(tmp_path), "--force"])
    assert result.exit_code == 0


def test_scan_on_valid_repo(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    result = runner.invoke(app, ["scan", str(tmp_path)])
    assert result.exit_code == 0


def test_scan_max_files_limits_written_index(tmp_path: Path) -> None:
    for idx in range(5):
        (tmp_path / f"{idx}.py").write_text("x = 1\n", encoding="utf-8")
    result = runner.invoke(app, ["scan", str(tmp_path), "--max-files", "2"])
    assert result.exit_code == 0
    summaries = json.loads((tmp_path / ".contextos" / "file_summaries.json").read_text())
    assert list(summaries) == ["0.py", "1.py"]


def test_repeated_scan_does_not_index_contextos_outputs(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    first = runner.invoke(app, ["scan", str(tmp_path)])
    second = runner.invoke(app, ["scan", str(tmp_path)])
    assert first.exit_code == 0
    assert second.exit_code == 0
    summaries = json.loads((tmp_path / ".contextos" / "file_summaries.json").read_text())
    assert "main.py" in summaries
    assert not any(path.startswith(".contextos/") for path in summaries)


def test_scan_on_nonexistent_path() -> None:
    result = runner.invoke(app, ["scan", "/nonexistent/path/xyz"])
    assert result.exit_code == 1


def test_pack_requires_task(tmp_path: Path) -> None:
    result = runner.invoke(app, ["pack", str(tmp_path)])
    assert result.exit_code != 0


def test_pack_with_task(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    result = runner.invoke(app, ["pack", str(tmp_path), "--task", "add logging"])
    assert result.exit_code == 0
    assert "add logging" in result.output


def test_pack_invalid_format(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    result = runner.invoke(app, ["pack", str(tmp_path), "--task", "test", "--format", "invalid"])
    assert result.exit_code == 1


def test_pack_zero_budget(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    result = runner.invoke(app, ["pack", str(tmp_path), "--task", "test", "--budget", "0"])
    assert result.exit_code == 1


def test_pack_writes_file(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    out = tmp_path / "context.md"
    result = runner.invoke(app, ["pack", str(tmp_path), "--task", "test task", "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "test task" in out.read_text(encoding="utf-8")


def test_task_set() -> None:
    result = runner.invoke(app, ["task", "set", "implement auth"])
    assert result.exit_code == 0
    assert "implement auth" in result.output


def test_task_show() -> None:
    result = runner.invoke(app, ["task", "show"])
    assert result.exit_code == 0


def test_task_clear() -> None:
    result = runner.invoke(app, ["task", "clear"])
    assert result.exit_code == 0


def test_memory_list_exits_zero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["memory", "list", "--repo", str(tmp_path)])
    # No files yet — shows helpful message, exits 0
    assert result.exit_code == 0
