"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from contextos.cli.main import app


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cli_app() -> object:
    return app


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Minimal synthetic repo for CLI tests."""
    (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def helper(): return 1\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    return tmp_path
