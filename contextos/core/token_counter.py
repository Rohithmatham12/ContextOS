"""Token estimation. Uses tiktoken (cl100k_base) if installed; regex fallback otherwise."""

from __future__ import annotations

import re
from pathlib import Path

# Splits text into approximate token units: identifiers/words OR individual punctuation.
# Mirrors BPE tokenization without requiring the actual tokenizer (~10-20% error for code).
_TOKEN_RE: re.Pattern[str] = re.compile(r"\w+|[^\w\s]")


def estimate_tokens(text: str) -> int:
    """Return estimated token count for *text*.

    Tries tiktoken (cl100k_base) first; falls back to :func:`_fallback` on any error.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:  # noqa: BLE001
        return _fallback(text)


def estimate_file_tokens(path: Path) -> int:
    """Estimate token count for the file at *path*. Returns 0 on read error."""
    try:
        return estimate_tokens(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return 0


def estimate_pack_tokens(pack: str | Path) -> int:
    """Estimate token count for a context pack given as a string or file path."""
    if isinstance(pack, Path):
        return estimate_file_tokens(pack)
    return estimate_tokens(pack)


def estimate_from_bytes(byte_count: int) -> int:
    """Fast size-based estimate when file content isn't available.

    Assumes ~3.5 bytes per token (typical for mixed code + prose).
    """
    return max(0, int(byte_count / 3.5))


def _fallback(text: str) -> int:
    """Regex-based token count approximation without tiktoken."""
    return len(_TOKEN_RE.findall(text))
