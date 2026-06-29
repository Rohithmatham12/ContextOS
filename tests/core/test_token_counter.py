"""Tests for contextos/core/token_counter.py — focus on fallback mode."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from contextos.core.token_counter import (
    _fallback,
    estimate_file_tokens,
    estimate_from_bytes,
    estimate_pack_tokens,
    estimate_tokens,
)

# ---------------------------------------------------------------------------
# _fallback (regex approximation — always available)
# ---------------------------------------------------------------------------


class TestFallback:
    def test_empty_string_returns_zero(self) -> None:
        assert _fallback("") == 0

    def test_single_word(self) -> None:
        assert _fallback("hello") == 1

    def test_multiple_words(self) -> None:
        assert _fallback("hello world foo") == 3

    def test_punctuation_counted_separately(self) -> None:
        # "a,b" → a , b  = 3 tokens
        assert _fallback("a,b") == 3

    def test_semicolons_counted(self) -> None:
        assert _fallback("a;b;c") == 5  # a ; b ; c

    def test_code_snippet_reasonable(self) -> None:
        code = "def foo(x):\n    return x + 1\n"
        result = _fallback(code)
        # At minimum: def, foo, x, return, x, 1 and several punctuation chars
        assert result >= 8

    def test_scales_proportionally(self) -> None:
        unit = _fallback("hello world")
        repeated = _fallback("hello world " * 50)
        assert repeated == unit * 50

    def test_whitespace_only_returns_zero(self) -> None:
        assert _fallback("   \t\n  ") == 0

    def test_digits_counted_as_words(self) -> None:
        assert _fallback("123 456") == 2

    def test_mixed_code(self) -> None:
        result = _fallback("import os\nfrom pathlib import Path\n")
        assert result > 5


# ---------------------------------------------------------------------------
# estimate_tokens — tests both paths
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_returns_positive_for_text(self) -> None:
        assert estimate_tokens("hello world") > 0

    def test_proportional_result(self) -> None:
        short = estimate_tokens("hello")
        long = estimate_tokens("hello " * 200)
        assert long > short * 100

    def test_tiktoken_unavailable_falls_back_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "tiktoken", None)
        # Should not raise; fallback path used
        result = estimate_tokens("hello world code")
        assert result > 0

    def test_tiktoken_exception_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Simulate tiktoken raising an unexpected error."""

        class _BrokenTiktoken:
            def get_encoding(self, name: str) -> object:
                raise RuntimeError("encoding unavailable")

        monkeypatch.setitem(sys.modules, "tiktoken", _BrokenTiktoken())
        result = estimate_tokens("hello world")
        assert result > 0

    def test_consistent_repeated_calls(self) -> None:
        text = "def main(): pass\n"
        assert estimate_tokens(text) == estimate_tokens(text)


# ---------------------------------------------------------------------------
# estimate_file_tokens
# ---------------------------------------------------------------------------


class TestEstimateFileTokens:
    def test_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("def foo(): pass\n", encoding="utf-8")
        assert estimate_file_tokens(f) > 0

    def test_nonexistent_file_returns_zero(self) -> None:
        assert estimate_file_tokens(Path("/definitely/does/not/exist/file.py")) == 0

    def test_empty_file_returns_zero(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        assert estimate_file_tokens(f) == 0

    def test_larger_file_more_tokens(self, tmp_path: Path) -> None:
        small = tmp_path / "small.py"
        large = tmp_path / "large.py"
        small.write_text("x = 1\n", encoding="utf-8")
        large.write_text("x = 1\n" * 200, encoding="utf-8")
        assert estimate_file_tokens(large) > estimate_file_tokens(small)

    def test_utf8_content(self, tmp_path: Path) -> None:
        f = tmp_path / "unicode.py"
        f.write_text("# café résumé naïve\npass\n", encoding="utf-8")
        assert estimate_file_tokens(f) > 0


# ---------------------------------------------------------------------------
# estimate_pack_tokens
# ---------------------------------------------------------------------------


class TestEstimatePackTokens:
    def test_string_input(self) -> None:
        pack = "# context pack\nsome code content here\n"
        assert estimate_pack_tokens(pack) > 0

    def test_empty_string(self) -> None:
        assert estimate_pack_tokens("") == 0

    def test_path_input(self, tmp_path: Path) -> None:
        f = tmp_path / "pack.md"
        f.write_text("# context pack\nsome content\n", encoding="utf-8")
        assert estimate_pack_tokens(f) > 0

    def test_path_nonexistent_returns_zero(self) -> None:
        assert estimate_pack_tokens(Path("/no/such/pack.md")) == 0

    def test_string_and_path_agree(self, tmp_path: Path) -> None:
        content = "# pack\ndef foo(): pass\n"
        f = tmp_path / "pack.md"
        f.write_text(content, encoding="utf-8")
        assert estimate_pack_tokens(content) == estimate_pack_tokens(f)

    def test_larger_pack_more_tokens(self) -> None:
        small = "# pack\ncode\n"
        large = "# pack\ncode\n" * 100
        assert estimate_pack_tokens(large) > estimate_pack_tokens(small)


# ---------------------------------------------------------------------------
# estimate_from_bytes
# ---------------------------------------------------------------------------


class TestEstimateFromBytes:
    def test_zero_bytes(self) -> None:
        assert estimate_from_bytes(0) == 0

    def test_negative_bytes_clamped(self) -> None:
        assert estimate_from_bytes(-100) == 0

    def test_positive_estimate(self) -> None:
        assert estimate_from_bytes(3500) > 0

    def test_proportional(self) -> None:
        assert estimate_from_bytes(1000) > estimate_from_bytes(100)

    def test_ratio_near_3_5(self) -> None:
        # 3500 bytes → ~1000 tokens
        est = estimate_from_bytes(3500)
        assert 900 <= est <= 1100

    def test_large_codebase(self) -> None:
        # 1 MB ≈ 285,000 tokens — reasonable for a medium codebase
        est = estimate_from_bytes(1_000_000)
        assert 200_000 <= est <= 400_000


# ---------------------------------------------------------------------------
# Fallback-mode integration (tiktoken blocked)
# ---------------------------------------------------------------------------


class TestFallbackMode:
    """All estimate_* functions work correctly when tiktoken is unavailable."""

    def test_estimate_tokens_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "tiktoken", None)
        result = estimate_tokens("def main(): return 42\n")
        # fallback: def, main, return, 42, (, ), :
        assert result >= 5

    def test_estimate_file_tokens_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "tiktoken", None)
        f = tmp_path / "code.py"
        f.write_text("import os\nimport sys\n", encoding="utf-8")
        assert estimate_file_tokens(f) >= 2

    def test_estimate_pack_tokens_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "tiktoken", None)
        result = estimate_pack_tokens("# context pack\ndef foo(): pass\n")
        assert result > 0

    def test_result_matches_fallback_directly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "tiktoken", None)
        text = "hello world foo bar"
        assert estimate_tokens(text) == _fallback(text)


# ---------------------------------------------------------------------------
# CLI integration — scan and pack show token output
# ---------------------------------------------------------------------------


class TestCLITokenOutput:
    def test_scan_shows_token_estimate(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from contextos.cli.main import app

        (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        result = CliRunner().invoke(app, ["scan", str(tmp_path), "--no-index"])
        assert result.exit_code == 0
        assert "Token estimate" in result.output

    def test_pack_shows_token_estimate(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from contextos.cli.main import app

        result = CliRunner().invoke(
            app, ["pack", str(tmp_path), "--task", "test", "--budget", "2000"]
        )
        assert result.exit_code == 0
        assert "Tokens" in result.output

    def test_scan_no_files_no_token_line(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from contextos.cli.main import app

        result = CliRunner().invoke(app, ["scan", str(tmp_path), "--no-index"])
        assert result.exit_code == 0
        # Empty repo → no "Token estimate" line
        assert "Token estimate" not in result.output
