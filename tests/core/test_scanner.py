"""Tests for contextos/core/scanner.py and contextos/core/safety.py."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from contextos.core.safety import (
    ALWAYS_EXCLUDE,
    detect_language,
    is_binary,
    is_safe_symlink,
    load_gitignore_patterns,
    matches_gitignore,
)
from contextos.core.scanner import ScanConfig, ScanResult, scan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_bytes(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _rel_paths(result: ScanResult) -> set[str]:
    return {f.rel_path for f in result.files}


def _skip_reasons(result: ScanResult) -> dict[str, str]:
    return {s.rel_path: s.reason for s in result.skipped}


# ---------------------------------------------------------------------------
# safety.py unit tests
# ---------------------------------------------------------------------------


class TestIsBinary:
    def test_null_byte_is_binary(self) -> None:
        assert is_binary(b"hello\x00world") is True

    def test_pure_text_not_binary(self) -> None:
        assert is_binary(b"hello world\n") is False

    def test_empty_bytes_not_binary(self) -> None:
        assert is_binary(b"") is False

    def test_null_only_in_prefix(self) -> None:
        # null within first 8192 bytes → binary
        assert is_binary(b"a" * 100 + b"\x00" + b"b" * 100) is True

    def test_utf8_multibyte_not_binary(self) -> None:
        assert is_binary("こんにちは".encode()) is False


class TestIsSafeSymlink:
    def test_symlink_inside_root_is_safe(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        target = _write(root / "real.txt", "hello")
        link = root / "link.txt"
        link.symlink_to(target)
        assert is_safe_symlink(link, root) is True

    def test_symlink_outside_root_is_unsafe(self, tmp_path: Path) -> None:
        outside = _write(tmp_path / "outside.txt", "secret")
        root = tmp_path / "repo"
        root.mkdir()
        link = root / "evil.txt"
        link.symlink_to(outside)
        assert is_safe_symlink(link, root) is False

    def test_absolute_escape_symlink_is_unsafe(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        link = root / "escape.txt"
        link.symlink_to(Path("/etc"))
        assert is_safe_symlink(link, root) is False


class TestDetectLanguage:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("main.py", "Python"),
            ("app.ts", "TypeScript"),
            ("index.js", "JavaScript"),
            ("main.go", "Go"),
            ("lib.rs", "Rust"),
            ("README.md", "Markdown"),
            ("config.yaml", "YAML"),
            ("schema.sql", "SQL"),
            ("Dockerfile", "Dockerfile"),
            ("Makefile", "Makefile"),
            ("unknown.xyz", "Unknown"),
        ],
    )
    def test_known_extensions(self, filename: str, expected: str) -> None:
        assert detect_language(Path(filename)) == expected


class TestGitignore:
    def test_load_absent_gitignore(self, tmp_path: Path) -> None:
        assert load_gitignore_patterns(tmp_path) == []

    def test_load_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("# comment\n\n*.pyc\n", encoding="utf-8")
        patterns = load_gitignore_patterns(tmp_path)
        assert patterns == ["*.pyc"]

    def test_load_skips_negation_patterns(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.log\n!important.log\n", encoding="utf-8")
        patterns = load_gitignore_patterns(tmp_path)
        assert "!important.log" not in patterns

    def test_matches_filename_glob(self) -> None:
        assert matches_gitignore("src/foo.pyc", ["*.pyc"]) is True

    def test_matches_exact_name(self) -> None:
        assert matches_gitignore("secret.env", ["secret.env"]) is True

    def test_no_match(self) -> None:
        assert matches_gitignore("main.py", ["*.pyc", "*.log"]) is False

    def test_trailing_slash_stripped(self) -> None:
        assert matches_gitignore("dist", ["dist/"]) is True


# ---------------------------------------------------------------------------
# scanner.py integration tests
# ---------------------------------------------------------------------------


class TestScanBasic:
    def test_finds_text_files(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "x = 1\n")
        _write(tmp_path / "b.py", "y = 2\n")
        result = scan(tmp_path)
        assert "a.py" in _rel_paths(result)
        assert "b.py" in _rel_paths(result)

    def test_empty_directory(self, tmp_path: Path) -> None:
        result = scan(tmp_path)
        assert result.total_files == 0
        assert result.total_skipped == 0

    def test_invalid_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not a directory"):
            scan(tmp_path / "nonexistent")

    def test_result_root_is_resolved(self, tmp_path: Path) -> None:
        result = scan(tmp_path)
        assert result.root == tmp_path.resolve()

    def test_deterministic_ordering(self, tmp_path: Path) -> None:
        for name in ["z.py", "a.py", "m.py"]:
            _write(tmp_path / name, f"# {name}\n")
        result = scan(tmp_path)
        rel_paths = [f.rel_path for f in result.files]
        assert rel_paths == sorted(rel_paths)

    def test_file_entry_metadata(self, tmp_path: Path) -> None:
        content = "def foo():\n    return 42\n"
        _write(tmp_path / "foo.py", content)
        result = scan(tmp_path)
        assert len(result.files) == 1
        entry = result.files[0]
        assert entry.rel_path == "foo.py"
        assert entry.extension == ".py"
        assert entry.language == "Python"
        assert entry.size == len(content.encode("utf-8"))
        assert entry.line_count == 2
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert entry.content_hash == expected_hash

    def test_language_counts(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "# py")
        _write(tmp_path / "b.py", "# py")
        _write(tmp_path / "c.js", "// js")
        result = scan(tmp_path)
        counts = result.language_counts()
        assert counts["Python"] == 2
        assert counts["JavaScript"] == 1

    def test_nested_directories_scanned(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "core" / "utils.py", "pass\n")
        result = scan(tmp_path)
        assert any("utils.py" in f.rel_path for f in result.files)

    def test_relative_paths_use_posix_separators(self, tmp_path: Path) -> None:
        _write(tmp_path / "apps" / "api" / "main.py", "pass\n")
        result = scan(tmp_path)
        assert "apps/api/main.py" in _rel_paths(result)
        assert not any("\\" in p for p in _rel_paths(result))

    def test_line_count_empty_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "empty.py", "")
        result = scan(tmp_path)
        assert result.files[0].line_count == 0

    def test_line_count_no_trailing_newline(self, tmp_path: Path) -> None:
        _write(tmp_path / "no_nl.py", "x = 1")
        result = scan(tmp_path)
        assert result.files[0].line_count == 1

    def test_monorepo_shape_scanned_deterministically(self, tmp_path: Path) -> None:
        _write(tmp_path / "apps" / "api" / "main.py", "def api(): pass\n")
        _write(tmp_path / "apps" / "web" / "index.ts", "export const web = true;\n")
        _write(tmp_path / "packages" / "shared" / "util.py", "def util(): pass\n")
        result = scan(tmp_path)
        assert [f.rel_path for f in result.files] == [
            "apps/api/main.py",
            "apps/web/index.ts",
            "packages/shared/util.py",
        ]


class TestScanSkipBinary:
    def test_binary_file_skipped(self, tmp_path: Path) -> None:
        _write_bytes(tmp_path / "image.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00")
        result = scan(tmp_path)
        assert result.total_files == 0
        reasons = _skip_reasons(result)
        assert reasons.get("image.png") == "binary"

    def test_null_byte_in_text_file_skipped(self, tmp_path: Path) -> None:
        _write_bytes(tmp_path / "weird.txt", b"hello\x00world")
        result = scan(tmp_path)
        assert _skip_reasons(result).get("weird.txt") == "binary"

    def test_binary_skipped_text_passes(self, tmp_path: Path) -> None:
        _write_bytes(tmp_path / "bin.dat", b"\x00\x01\x02\x03")
        _write(tmp_path / "text.py", "print('hello')\n")
        result = scan(tmp_path)
        assert "text.py" in _rel_paths(result)
        assert "bin.dat" not in _rel_paths(result)


class TestScanSkipLargeFile:
    def test_file_over_limit_skipped(self, tmp_path: Path) -> None:
        big = tmp_path / "big.txt"
        big.write_bytes(b"x" * 100)
        config = ScanConfig(max_file_bytes=50)
        result = scan(tmp_path, config)
        assert _skip_reasons(result).get("big.txt") == "too_large"

    def test_file_at_limit_allowed(self, tmp_path: Path) -> None:
        exact = tmp_path / "exact.txt"
        exact.write_bytes(b"a" * 50)
        config = ScanConfig(max_file_bytes=50)
        result = scan(tmp_path, config)
        assert "exact.txt" in _rel_paths(result)

    def test_custom_limit_respected(self, tmp_path: Path) -> None:
        _write(tmp_path / "small.txt", "tiny\n")
        big = tmp_path / "big.txt"
        big.write_bytes(b"b" * 1024 * 1024)  # 1 MB
        config = ScanConfig(max_file_bytes=512)
        result = scan(tmp_path, config)
        assert "small.txt" in _rel_paths(result)
        assert _skip_reasons(result).get("big.txt") == "too_large"

    def test_large_lockfile_skipped_by_size_limit(self, tmp_path: Path) -> None:
        (tmp_path / "package-lock.json").write_bytes(b"{" + b'"x":1,' * 200 + b'"z":0}')
        config = ScanConfig(max_file_bytes=64)
        result = scan(tmp_path, config)
        assert _skip_reasons(result).get("package-lock.json") == "too_large"


class TestScanSkipEncoding:
    def test_non_utf8_file_skipped(self, tmp_path: Path) -> None:
        # latin-1 encoded content that isn't valid UTF-8
        _write_bytes(tmp_path / "latin.txt", "café".encode("latin-1"))
        result = scan(tmp_path)
        reasons = _skip_reasons(result)
        assert reasons.get("latin.txt") == "encoding_error"

    def test_invalid_utf8_bytes_skipped(self, tmp_path: Path) -> None:
        _write_bytes(tmp_path / "bad.txt", b"\xff\xfe" + b"hello")
        result = scan(tmp_path)
        assert _skip_reasons(result).get("bad.txt") == "encoding_error"

    def test_valid_utf8_multibyte_passes(self, tmp_path: Path) -> None:
        _write(tmp_path / "unicode.py", "# こんにちは\nx = 1\n")
        result = scan(tmp_path)
        assert "unicode.py" in _rel_paths(result)


class TestScanIgnoredDirectories:
    @pytest.mark.parametrize("dirname", sorted(ALWAYS_EXCLUDE))
    def test_always_excluded_dir_not_descended(self, tmp_path: Path, dirname: str) -> None:
        excluded_file = tmp_path / dirname / "secret.py"
        excluded_file.parent.mkdir(parents=True, exist_ok=True)
        excluded_file.write_text("# inside excluded dir\n", encoding="utf-8")
        _write(tmp_path / "visible.py", "# visible\n")
        result = scan(tmp_path)
        rel_paths = _rel_paths(result)
        assert "visible.py" in rel_paths
        assert not any(dirname in p for p in rel_paths)

    def test_extra_exclude_respected(self, tmp_path: Path) -> None:
        (tmp_path / "custom_dir").mkdir()
        _write(tmp_path / "custom_dir" / "file.py", "# hidden\n")
        _write(tmp_path / "visible.py", "# visible\n")
        config = ScanConfig(extra_exclude=frozenset({"custom_dir"}))
        result = scan(tmp_path, config)
        assert "visible.py" in _rel_paths(result)
        assert not any("custom_dir" in p for p in _rel_paths(result))

    def test_nested_excluded_dir(self, tmp_path: Path) -> None:
        # node_modules nested inside src/ — should still be pruned
        (tmp_path / "src" / "node_modules").mkdir(parents=True)
        _write(tmp_path / "src" / "node_modules" / "lib.js", "module.exports = {}\n")
        _write(tmp_path / "src" / "index.js", "const x = 1;\n")
        result = scan(tmp_path)
        assert "src/index.js" in _rel_paths(result)
        assert not any("node_modules" in p for p in _rel_paths(result))

    def test_excluded_dir_files_not_in_skipped(self, tmp_path: Path) -> None:
        # Pruned directories are never visited — files inside should not appear in skipped either
        (tmp_path / "__pycache__").mkdir()
        _write_bytes(tmp_path / "__pycache__" / "foo.pyc", b"compiled bytecode")
        result = scan(tmp_path)
        assert not any("__pycache__" in s.rel_path for s in result.skipped)

    def test_contextos_directory_not_scanned(self, tmp_path: Path) -> None:
        _write(tmp_path / ".contextos" / "context_pack.md", "# generated\nSECRET=value\n")
        _write(tmp_path / "main.py", "def main(): pass\n")
        result = scan(tmp_path)
        assert "main.py" in _rel_paths(result)
        assert not any(p.startswith(".contextos/") for p in _rel_paths(result))

    def test_nested_git_metadata_not_scanned(self, tmp_path: Path) -> None:
        _write(tmp_path / "third_party" / "lib.py", "def lib(): pass\n")
        _write(tmp_path / "third_party" / ".git" / "config", "[core]\n")
        result = scan(tmp_path)
        assert "third_party/lib.py" in _rel_paths(result)
        assert not any("/.git/" in p or p.startswith(".git/") for p in _rel_paths(result))


class TestScanIgnoredFiles:
    def test_notebook_skipped_as_generated_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "analysis.ipynb", '{"cells": [], "metadata": {}}\n')
        result = scan(tmp_path)
        assert _skip_reasons(result).get("analysis.ipynb") == "ignored"

    def test_minified_js_skipped_as_generated_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.min.js", "function x(){return 1};" * 100)
        result = scan(tmp_path)
        assert _skip_reasons(result).get("app.min.js") == "ignored"

    def test_source_js_next_to_minified_js_still_scanned(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.js", "export function x() { return 1; }\n")
        _write(tmp_path / "app.min.js", "function x(){return 1};")
        result = scan(tmp_path)
        assert "app.js" in _rel_paths(result)
        assert "app.min.js" not in _rel_paths(result)


class TestScanMaxFiles:
    def test_max_files_limits_indexed_files(self, tmp_path: Path) -> None:
        for idx in range(10):
            _write(tmp_path / f"{idx:02d}.py", "x = 1\n")
        result = scan(tmp_path, ScanConfig(max_files=3))
        assert [f.rel_path for f in result.files] == ["00.py", "01.py", "02.py"]

    def test_max_files_none_indexes_all_files(self, tmp_path: Path) -> None:
        for idx in range(4):
            _write(tmp_path / f"{idx}.py", "x = 1\n")
        result = scan(tmp_path, ScanConfig(max_files=None))
        assert result.total_files == 4


class TestScanGitignore:
    def test_gitignore_pattern_skips_file(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
        _write(tmp_path / "app.log", "log content\n")
        _write(tmp_path / "main.py", "# main\n")
        result = scan(tmp_path)
        assert "main.py" in _rel_paths(result)
        assert "app.log" not in _rel_paths(result)
        assert _skip_reasons(result).get("app.log") == "gitignore"

    def test_gitignore_disabled(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
        _write(tmp_path / "app.log", "log content\n")
        config = ScanConfig(respect_gitignore=False)
        result = scan(tmp_path, config)
        assert "app.log" in _rel_paths(result)

    def test_absent_gitignore_ok(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        result = scan(tmp_path)
        assert "main.py" in _rel_paths(result)

    def test_gitignore_directory_pattern(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("logs/\n", encoding="utf-8")
        (tmp_path / "logs").mkdir()
        _write(tmp_path / "logs" / "out.txt", "log line\n")
        _write(tmp_path / "main.py", "pass\n")
        result = scan(tmp_path)
        assert "main.py" in _rel_paths(result)
        assert not any("logs" in p for p in _rel_paths(result))


class TestScanSymlinks:
    def test_safe_symlink_included(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        _write(root / "real.py", "x = 1\n")
        (root / "link.py").symlink_to(root / "real.py")
        result = scan(root)
        assert "link.py" in _rel_paths(result)

    def test_unsafe_symlink_skipped(self, tmp_path: Path) -> None:
        outside = _write(tmp_path / "outside.txt", "secret\n")
        root = tmp_path / "repo"
        root.mkdir()
        (root / "evil.txt").symlink_to(outside)
        result = scan(root)
        assert _skip_reasons(result).get("evil.txt") == "symlink_unsafe"

    def test_safe_symlink_not_in_skipped(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        _write(root / "real.py", "pass\n")
        (root / "alias.py").symlink_to(root / "real.py")
        result = scan(root)
        assert "alias.py" not in _skip_reasons(result)


class TestScanPermissions:
    @pytest.mark.skipif(os.name == "nt", reason="chmod semantics differ on Windows")
    def test_unreadable_file_skipped(self, tmp_path: Path) -> None:
        secret = tmp_path / "secret.py"
        secret.write_text("password = 'hunter2'\n", encoding="utf-8")
        os.chmod(secret, 0o000)
        try:
            # Skip test when running as root (root can read any file)
            if os.getuid() == 0:
                pytest.skip("root user can read all files")
            result = scan(tmp_path)
            assert _skip_reasons(result).get("secret.py") == "permission_error"
        finally:
            os.chmod(secret, 0o644)


class TestScanConfig:
    def test_default_config_reasonable(self) -> None:
        config = ScanConfig()
        assert config.max_file_bytes == 524288
        assert config.max_files is None
        assert config.respect_gitignore is True
        assert ".git" in config.exclude
        assert ".contextos" in config.exclude
        assert "node_modules" in config.exclude

    def test_always_exclude_immutable(self) -> None:
        config = ScanConfig()
        assert ".git" in config.exclude
        # extra_exclude doesn't remove always-excluded entries
        config2 = ScanConfig(extra_exclude=frozenset({".git"}))
        assert ".git" in config2.exclude
