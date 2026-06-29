"""Safe repository file scanner."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from contextos.core.safety import (
    ALWAYS_EXCLUDE,
    detect_language,
    is_binary,
    is_safe_symlink,
    load_gitignore_patterns,
    matches_gitignore,
)

DEFAULT_MAX_FILE_BYTES: int = 524288  # 512 KB


@dataclass
class ScanConfig:
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    extra_exclude: frozenset[str] = field(default_factory=frozenset)
    respect_gitignore: bool = True

    @property
    def exclude(self) -> frozenset[str]:
        return ALWAYS_EXCLUDE | self.extra_exclude


@dataclass
class FileEntry:
    """Metadata for a successfully scanned text file."""

    path: Path
    rel_path: str
    extension: str
    size: int
    line_count: int
    language: str
    content_hash: str


@dataclass
class SkippedEntry:
    """Record of a file that was found but not indexed."""

    path: Path
    rel_path: str
    # Reasons: "ignored" | "gitignore" | "too_large" | "binary" |
    #          "encoding_error" | "permission_error" | "symlink_unsafe"
    reason: str


@dataclass
class ScanResult:
    root: Path
    files: list[FileEntry] = field(default_factory=list)
    skipped: list[SkippedEntry] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_skipped(self) -> int:
        return len(self.skipped)

    def language_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.files:
            counts[f.language] = counts.get(f.language, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def scan(root: Path, config: ScanConfig | None = None) -> ScanResult:
    """Walk *root* and return metadata for every text file that passes safety checks.

    Directories in ``config.exclude`` and their entire subtrees are never
    visited.  Files are processed in deterministic (sorted) order.
    """
    if config is None:
        config = ScanConfig()

    root = root.resolve()

    if not root.is_dir():
        raise ValueError(f"root is not a directory: {root}")

    result = ScanResult(root=root)
    gitignore = load_gitignore_patterns(root) if config.respect_gitignore else []

    for dirpath_str, dirnames, filenames in os.walk(str(root), topdown=True, followlinks=False):
        dir_path = Path(dirpath_str)

        # Prune excluded directories in-place — prevents os.walk from descending.
        kept: list[str] = []
        for d in dirnames:
            if d in config.exclude:
                continue
            if config.respect_gitignore:
                rel = str((dir_path / d).relative_to(root))
                if matches_gitignore(rel, gitignore) or matches_gitignore(rel + "/", gitignore):
                    continue
            kept.append(d)
        dirnames[:] = sorted(kept)

        for filename in sorted(filenames):
            path = dir_path / filename
            rel_path = str(path.relative_to(root))
            entry = _classify_file(path, rel_path, root, config, gitignore)
            if isinstance(entry, FileEntry):
                result.files.append(entry)
            else:
                result.skipped.append(entry)

    return result


def _classify_file(
    path: Path,
    rel_path: str,
    root: Path,
    config: ScanConfig,
    gitignore: list[str],
) -> FileEntry | SkippedEntry:
    def skip(reason: str) -> SkippedEntry:
        return SkippedEntry(path=path, rel_path=rel_path, reason=reason)

    # Per-file gitignore check (directories are pruned earlier, but file patterns still apply)
    if config.respect_gitignore and matches_gitignore(rel_path, gitignore):
        return skip("gitignore")

    # Symlink safety — reject links that escape the repo root
    if path.is_symlink() and not is_safe_symlink(path, root):
        return skip("symlink_unsafe")

    # File size
    try:
        size = path.stat().st_size
    except OSError:
        return skip("permission_error")

    if size > config.max_file_bytes:
        return skip("too_large")

    # Read raw bytes once — used for binary detection, hashing, and decoding
    try:
        raw = path.read_bytes()
    except OSError:
        return skip("permission_error")

    if is_binary(raw):
        return skip("binary")

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return skip("encoding_error")

    return FileEntry(
        path=path,
        rel_path=rel_path,
        extension=path.suffix.lower(),
        size=size,
        line_count=len(content.splitlines()),
        language=detect_language(path),
        content_hash=hashlib.sha256(raw).hexdigest(),
    )
