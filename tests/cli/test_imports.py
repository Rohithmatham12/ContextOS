"""Verify all CLI modules import cleanly and the app is wired correctly."""

from __future__ import annotations


def test_main_app_importable() -> None:
    from contextos.cli.main import app

    assert app is not None


def test_init_command_importable() -> None:
    from contextos.cli.commands.init import app

    assert app is not None


def test_scan_command_importable() -> None:
    from contextos.cli.commands.scan import app

    assert app is not None


def test_task_command_importable() -> None:
    from contextos.cli.commands.task import task_command

    assert task_command is not None


def test_pack_command_importable() -> None:
    from contextos.cli.commands.pack import app

    assert app is not None


def test_memory_command_importable() -> None:
    from contextos.cli.commands.memory import app

    assert app is not None


def test_version_importable() -> None:
    from contextos import __version__

    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"
