"""Tests for compression.py and headroom_adapter.py."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from contextos.cli.main import app
from contextos.core.compression import (
    AVAILABLE_PROVIDERS,
    CompressionError,
    HeadroomUnavailableError,
    NoOpCompressionProvider,
    get_provider,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# NoOpCompressionProvider
# ---------------------------------------------------------------------------


class TestNoOpProvider:
    def test_name(self) -> None:
        assert NoOpCompressionProvider().name() == "noop"

    def test_returns_input_unchanged(self) -> None:
        text = "hello world"
        assert NoOpCompressionProvider().compress(text, budget=1000) == text

    def test_empty_string(self) -> None:
        assert NoOpCompressionProvider().compress("", budget=0) == ""

    def test_budget_ignored(self) -> None:
        p = NoOpCompressionProvider()
        text = "abc"
        assert p.compress(text, budget=0) == text
        assert p.compress(text, budget=999999) == text

    def test_multiline_preserved(self) -> None:
        text = "line1\nline2\nline3\n"
        assert NoOpCompressionProvider().compress(text, budget=100) == text


# ---------------------------------------------------------------------------
# get_provider factory
# ---------------------------------------------------------------------------


class TestGetProvider:
    def test_unknown_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown compression provider"):
            get_provider("nonexistent")

    def test_error_message_lists_available(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            get_provider("bad")
        assert "headroom" in str(exc_info.value)

    def test_available_providers_tuple(self) -> None:
        assert "headroom" in AVAILABLE_PROVIDERS
        assert isinstance(AVAILABLE_PROVIDERS, tuple)

    def test_get_provider_headroom_import_error(self) -> None:
        # headroom_ai not installed → HeadroomUnavailableError on compress()
        with patch.dict(sys.modules, {"headroom_ai": None}):
            provider = get_provider("headroom")
            with pytest.raises(HeadroomUnavailableError, match="pip install headroom-ai"):
                provider.compress("text", budget=1000)

    def test_get_provider_headroom_returns_instance(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        # Stub headroom_ai so the import succeeds
        stub = types.ModuleType("headroom_ai")
        stub.compress = lambda text, budget, base_url: text  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            provider = get_provider("headroom")
        assert isinstance(provider, HeadroomCompressionProvider)


# ---------------------------------------------------------------------------
# HeadroomCompressionProvider
# ---------------------------------------------------------------------------


class TestHeadroomProvider:
    def _stub_module(self, return_value: str = "compressed") -> types.ModuleType:
        stub = types.ModuleType("headroom_ai")
        stub.compress = MagicMock(return_value=return_value)  # type: ignore[attr-defined]
        return stub

    def test_name(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        assert HeadroomCompressionProvider().name() == "headroom"

    def test_default_base_url(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        p = HeadroomCompressionProvider()
        assert "127.0.0.1" in p.base_url or "localhost" in p.base_url.lower()

    def test_custom_base_url(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        p = HeadroomCompressionProvider(base_url="http://myhost:9000")
        assert p.base_url == "http://myhost:9000"

    def test_env_var_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        monkeypatch.setenv("HEADROOM_BASE_URL", "http://env-host:1234")
        p = HeadroomCompressionProvider()
        assert p.base_url == "http://env-host:1234"

    def test_compress_calls_headroom_module(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        stub = self._stub_module("compacted text")
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            p = HeadroomCompressionProvider(base_url="http://127.0.0.1:8787")
            result = p.compress("original text", budget=500)

        assert result == "compacted text"
        stub.compress.assert_called_once_with(
            "original text", budget=500, base_url="http://127.0.0.1:8787"
        )

    def test_compress_passes_budget(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        captured: dict[str, object] = {}

        def fake_compress(text: str, *, budget: int, base_url: str) -> str:
            captured["budget"] = budget
            return text

        stub = types.ModuleType("headroom_ai")
        stub.compress = fake_compress  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            p = HeadroomCompressionProvider()
            p.compress("hello", budget=4000)

        assert captured["budget"] == 4000

    def test_missing_package_raises_unavailable(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        with patch.dict(sys.modules, {"headroom_ai": None}):
            p = HeadroomCompressionProvider()
            with pytest.raises(HeadroomUnavailableError) as exc_info:
                p.compress("text", budget=1000)

        assert "pip install headroom-ai" in str(exc_info.value)

    def test_missing_package_error_has_setup_hint(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        with patch.dict(sys.modules, {"headroom_ai": None}):
            p = HeadroomCompressionProvider()
            with pytest.raises(HeadroomUnavailableError) as exc_info:
                p.compress("text", budget=1000)

        msg = str(exc_info.value)
        assert "headroom serve" in msg

    def test_proxy_error_raises_unavailable(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        stub = types.ModuleType("headroom_ai")
        stub.compress = MagicMock(side_effect=ConnectionRefusedError("Connection refused"))  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            p = HeadroomCompressionProvider()
            with pytest.raises(HeadroomUnavailableError, match="unreachable"):
                p.compress("text", budget=1000)

    def test_proxy_error_message_includes_url(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        stub = types.ModuleType("headroom_ai")
        stub.compress = MagicMock(side_effect=OSError("timeout"))  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            p = HeadroomCompressionProvider(base_url="http://localhost:9999")
            with pytest.raises(HeadroomUnavailableError) as exc_info:
                p.compress("text", budget=1000)

        assert "localhost:9999" in str(exc_info.value)

    def test_proxy_error_includes_fallback_hint(self) -> None:
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        stub = types.ModuleType("headroom_ai")
        stub.compress = MagicMock(side_effect=RuntimeError("err"))  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            p = HeadroomCompressionProvider()
            with pytest.raises(HeadroomUnavailableError) as exc_info:
                p.compress("text", budget=1000)

        assert "omit --compress" in str(exc_info.value).lower()

    def test_is_compression_provider(self) -> None:
        from contextos.core.compression import CompressionProvider
        from contextos.core.headroom_adapter import HeadroomCompressionProvider

        assert issubclass(HeadroomCompressionProvider, CompressionProvider)

    def test_headroom_unavailable_error_is_compression_error(self) -> None:
        assert issubclass(HeadroomUnavailableError, CompressionError)


# ---------------------------------------------------------------------------
# pack_builder integration
# ---------------------------------------------------------------------------


@pytest.fixture()
def mini_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    ctxdir = root / ".contextos"
    ctxdir.mkdir()

    from contextos.core.dependency_graph import build_graph, write_graph
    from contextos.core.scanner import ScanConfig, scan
    from contextos.core.summarizer import summarize_repo

    result = scan(root, ScanConfig())
    summarize_repo(result, output_path=ctxdir / "file_summaries.json")
    write_graph(build_graph(result), ctxdir / "dependency_graph.json")
    return root, ctxdir


class TestPackBuilderCompression:
    def test_no_compress_returns_unmodified(self, mini_repo: tuple[Path, Path]) -> None:
        from contextos.core.pack_builder import PackConfig, build_pack

        root, ctxdir = mini_repo
        cfg = PackConfig(compress=None, add_timestamp=False)
        content, _ = build_pack("do something", root, ctxdir, config=cfg)
        assert "ContextOS" in content

    def test_noop_compress_unchanged(self, mini_repo: tuple[Path, Path]) -> None:
        # Manually call noop — result must equal uncompressed
        from contextos.core.pack_builder import PackConfig, build_pack

        root, ctxdir = mini_repo
        cfg_no = PackConfig(compress=None, add_timestamp=False)
        content_no, _ = build_pack("task", root, ctxdir, config=cfg_no)

        p = NoOpCompressionProvider()
        assert p.compress(content_no, budget=8000) == content_no

    def test_compress_headroom_called_with_rendered_text(
        self, mini_repo: tuple[Path, Path]
    ) -> None:
        from contextos.core.pack_builder import PackConfig, build_pack

        root, ctxdir = mini_repo

        stub = types.ModuleType("headroom_ai")
        received: list[str] = []

        def fake_compress(text: str, *, budget: int, base_url: str) -> str:
            received.append(text)
            return "COMPRESSED:" + text[:20]

        stub.compress = fake_compress  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"headroom_ai": stub}):
            cfg = PackConfig(compress="headroom", add_timestamp=False)
            content, _ = build_pack("task", root, ctxdir, config=cfg)

        assert content.startswith("COMPRESSED:")
        assert len(received) == 1

    def test_compress_headroom_budget_forwarded(self, mini_repo: tuple[Path, Path]) -> None:
        from contextos.core.pack_builder import PackConfig, build_pack

        root, ctxdir = mini_repo

        stub = types.ModuleType("headroom_ai")
        budgets: list[int] = []

        def fake_compress(text: str, *, budget: int, base_url: str) -> str:
            budgets.append(budget)
            return text

        stub.compress = fake_compress  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"headroom_ai": stub}):
            cfg = PackConfig(compress="headroom", budget=4000, add_timestamp=False)
            build_pack("task", root, ctxdir, config=cfg)

        assert budgets == [4000]

    def test_compress_unavailable_propagates(self, mini_repo: tuple[Path, Path]) -> None:
        from contextos.core.pack_builder import PackConfig, build_pack

        root, ctxdir = mini_repo

        with patch.dict(sys.modules, {"headroom_ai": None}):
            cfg = PackConfig(compress="headroom", add_timestamp=False)
            with pytest.raises(HeadroomUnavailableError):
                build_pack("task", root, ctxdir, config=cfg)

    def test_unknown_compress_raises_value_error(self, mini_repo: tuple[Path, Path]) -> None:
        from contextos.core.pack_builder import PackConfig, build_pack

        root, ctxdir = mini_repo
        cfg = PackConfig(compress="unknown_provider", add_timestamp=False)
        with pytest.raises(ValueError, match="Unknown compression provider"):
            build_pack("task", root, ctxdir, config=cfg)

    def test_compress_writes_to_disk(self, mini_repo: tuple[Path, Path]) -> None:
        from contextos.core.pack_builder import PackConfig, build_pack

        root, ctxdir = mini_repo

        stub = types.ModuleType("headroom_ai")
        stub.compress = lambda text, budget, base_url: "DISK_OUTPUT"  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"headroom_ai": stub}):
            cfg = PackConfig(compress="headroom", add_timestamp=False)
            build_pack("task", root, ctxdir, config=cfg)

        assert (ctxdir / "context_pack.md").read_text(encoding="utf-8") == "DISK_OUTPUT"


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLICompressOption:
    def test_compress_headroom_accepted(self, mini_repo: tuple[Path, Path]) -> None:
        root, _ = mini_repo
        stub = types.ModuleType("headroom_ai")
        stub.compress = lambda text, budget, base_url: text  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            result = runner.invoke(
                app,
                ["pack", str(root), "--task", "test", "--compress", "headroom"],
            )
        assert result.exit_code == 0

    def test_compress_unknown_provider_exits_one(self, mini_repo: tuple[Path, Path]) -> None:
        root, _ = mini_repo
        result = runner.invoke(
            app,
            ["pack", str(root), "--task", "test", "--compress", "invalid_provider"],
        )
        assert result.exit_code == 1
        assert "Unknown compression provider" in result.output

    def test_compress_headroom_unavailable_exits_one(self, mini_repo: tuple[Path, Path]) -> None:
        root, _ = mini_repo
        with patch.dict(sys.modules, {"headroom_ai": None}):
            result = runner.invoke(
                app,
                ["pack", str(root), "--task", "test", "--compress", "headroom"],
            )
        assert result.exit_code == 1
        assert "Compression failed" in result.output

    def test_compress_headroom_install_hint_in_output(self, mini_repo: tuple[Path, Path]) -> None:
        root, _ = mini_repo
        with patch.dict(sys.modules, {"headroom_ai": None}):
            result = runner.invoke(
                app,
                ["pack", str(root), "--task", "test", "--compress", "headroom"],
            )
        assert "headroom-ai" in result.output

    def test_no_compress_omitted_works(self, mini_repo: tuple[Path, Path]) -> None:
        root, _ = mini_repo
        result = runner.invoke(
            app,
            ["pack", str(root), "--task", "test"],
        )
        assert result.exit_code == 0

    def test_compress_flag_shown_in_output(self, mini_repo: tuple[Path, Path]) -> None:
        root, _ = mini_repo
        stub = types.ModuleType("headroom_ai")
        stub.compress = lambda text, budget, base_url: text  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            result = runner.invoke(
                app,
                ["pack", str(root), "--task", "test", "--compress", "headroom"],
            )
        assert "headroom" in result.output

    def test_compress_proxy_error_exits_one(self, mini_repo: tuple[Path, Path]) -> None:
        root, _ = mini_repo
        stub = types.ModuleType("headroom_ai")
        stub.compress = MagicMock(side_effect=ConnectionRefusedError("refused"))  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            result = runner.invoke(
                app,
                ["pack", str(root), "--task", "test", "--compress", "headroom"],
            )
        assert result.exit_code == 1

    def test_compress_proxy_error_shows_message(self, mini_repo: tuple[Path, Path]) -> None:
        root, _ = mini_repo
        stub = types.ModuleType("headroom_ai")
        stub.compress = MagicMock(side_effect=OSError("timeout"))  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"headroom_ai": stub}):
            result = runner.invoke(
                app,
                ["pack", str(root), "--task", "test", "--compress", "headroom"],
            )
        assert "Compression failed" in result.output or "unreachable" in result.output
