"""Secret detection and redaction for file content and filenames."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SecretMatch:
    """One detected secret in a piece of text."""

    pattern_name: str
    line_number: int  # 1-based
    redacted_snippet: str  # short excerpt with secret already replaced


# ---------------------------------------------------------------------------
# Internal pattern registry
# ---------------------------------------------------------------------------


@dataclass
class _SecretPattern:
    name: str
    regex: re.Pattern[str]
    label: str  # replacement token e.g. "[REDACTED_OPENAI_KEY]"
    # If True, the regex must contain a named group 'value'; only that group
    # is replaced, leaving any 'key' prefix intact.
    value_group: bool = False


_CONTENT_PATTERNS: tuple[_SecretPattern, ...] = (
    # ---- OpenAI ---------------------------------------------------------
    # sk-proj-... (new format) or sk-... (classic) — at least 20 alphanum chars
    _SecretPattern(
        "openai_api_key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
        "[REDACTED_OPENAI_KEY]",
    ),
    # ---- Anthropic -------------------------------------------------------
    _SecretPattern(
        "anthropic_api_key",
        re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
        "[REDACTED_ANTHROPIC_KEY]",
    ),
    # ---- AWS -------------------------------------------------------------
    # Access Key ID: always AKIA + 16 uppercase alphanumeric
    _SecretPattern(
        "aws_access_key_id",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY_ID]",
    ),
    # Secret Access Key: commonly assigned to known variable names
    _SecretPattern(
        "aws_secret_access_key",
        re.compile(
            r"(?i)(?P<key>(?:aws_secret_access_key|AWS_SECRET(?:_ACCESS_KEY)?)\s*[=:]\s*)"
            r"(?P<value>[A-Za-z0-9/+=]{20,})"
        ),
        "[REDACTED_AWS_SECRET]",
        value_group=True,
    ),
    # ---- GitHub ----------------------------------------------------------
    # Classic PATs and fine-grained tokens
    _SecretPattern(
        "github_token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    _SecretPattern(
        "github_fine_grained",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    # ---- JWT -------------------------------------------------------------
    # Three base64url segments separated by dots; starts with eyJ ({"  base64)
    _SecretPattern(
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}\b"),
        "[REDACTED_JWT]",
    ),
    # ---- Private keys (PEM) ---------------------------------------------
    _SecretPattern(
        "private_key_pem",
        re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----"),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # ---- Slack -----------------------------------------------------------
    _SecretPattern(
        "slack_token",
        re.compile(r"\bxox[bpoar]-[0-9A-Za-z\-]{10,}\b"),
        "[REDACTED_SLACK_TOKEN]",
    ),
    # ---- Stripe ----------------------------------------------------------
    _SecretPattern(
        "stripe_secret_key",
        re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b"),
        "[REDACTED_STRIPE_SECRET]",
    ),
    _SecretPattern(
        "stripe_restricted_key",
        re.compile(r"\brk_live_[A-Za-z0-9]{24,}\b"),
        "[REDACTED_STRIPE_SECRET]",
    ),
    # ---- Database URLs with embedded credentials ------------------------
    _SecretPattern(
        "database_url",
        re.compile(
            r"(?i)(?P<key>(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)"
            r"://[^:@/\s]+:)"
            r"(?P<value>[^@\s]{4,})"
            r"(?=@)"
        ),
        "[REDACTED_DB_PASSWORD]",
        value_group=True,
    ),
    # ---- HTTP Bearer tokens ---------------------------------------------
    _SecretPattern(
        "bearer_token",
        re.compile(
            r"(?i)(?P<key>Authorization\s*:\s*Bearer\s+)"
            r"(?P<value>[A-Za-z0-9_\-\.]{10,})"
        ),
        "[REDACTED_BEARER_TOKEN]",
        value_group=True,
    ),
    # ---- Generic env-style key=value assignments ------------------------
    # Matches: PASSWORD=hunter2, SECRET_KEY=abc123, API_KEY=xyz789
    # Uses = only (not :) to avoid false positives on Python type annotations
    # like `password: str` — those use colon but are NOT secrets.
    _SecretPattern(
        "env_secret_assignment",
        re.compile(
            r"(?i)(?P<key>"
            r"(?:password|passwd|secret(?:_key)?|api[_\-]?key|access[_\-]?token"
            r"|auth[_\-]?token|private[_\-]?key|db[_\-]?pass(?:word)?|database[_\-]?password"
            r"|encryption[_\-]?key|signing[_\-]?key)"
            r"\s*=\s*)"
            r'(?P<value>(?!\$\{)(?!["\']\s*$)[^\s\n#"\']{4,})',
        ),
        "[REDACTED_SECRET]",
        value_group=True,
    ),
)

# ---------------------------------------------------------------------------
# Filename-based detection
# ---------------------------------------------------------------------------

_FILENAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\.env$", re.IGNORECASE),
    re.compile(r"^\.env\.[^.]+$", re.IGNORECASE),  # .env.local, .env.prod
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"\.pfx$", re.IGNORECASE),
    re.compile(r"\.crt$", re.IGNORECASE),
    re.compile(r"id_rsa", re.IGNORECASE),
    re.compile(r"id_ecdsa", re.IGNORECASE),
    re.compile(r"id_ed25519", re.IGNORECASE),
)

# Template/example env files — safe to include despite matching filename patterns
_SAFE_FILENAMES: frozenset[str] = frozenset(
    {".env.example", ".env.sample", ".env.template", ".env.dist"}
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _redact_line(line: str, sp: _SecretPattern) -> str:
    """Return *line* with matches from pattern *sp* replaced by *sp.label*."""
    if sp.value_group:
        return sp.regex.sub(lambda m: m.group("key") + sp.label, line)
    return sp.regex.sub(sp.label, line)


def is_secret_file(rel_path: str) -> bool:
    """Return True if the file should be excluded based on its name alone."""
    name = Path(rel_path).name.lower()
    if name in _SAFE_FILENAMES:
        return False
    return any(pat.search(name) for pat in _FILENAME_PATTERNS)


def detect_in_content(text: str) -> list[SecretMatch]:
    """Scan *text* for secret patterns. Returns a list of matches (empty if clean)."""
    matches: list[SecretMatch] = []
    lines = text.splitlines()

    for sp in _CONTENT_PATTERNS:
        for m in sp.regex.finditer(text):
            # Compute 1-based line number from character offset
            line_no = text[: m.start()].count("\n") + 1
            # Build a short redacted snippet for the warning message
            raw_line = lines[line_no - 1] if line_no <= len(lines) else ""
            snippet = _redact_line(raw_line, sp)[:80]
            matches.append(
                SecretMatch(
                    pattern_name=sp.name,
                    line_number=line_no,
                    redacted_snippet=snippet,
                )
            )

    return matches


def redact_content(text: str) -> tuple[str, list[SecretMatch]]:
    """Replace all detected secrets with ``[REDACTED_*]`` tokens.

    Returns ``(redacted_text, matches)``.  *matches* is empty when nothing
    was found.
    """
    if not text:
        return text, []

    warnings: list[SecretMatch] = []
    redacted = text

    for sp in _CONTENT_PATTERNS:
        if not sp.regex.search(redacted):
            continue

        if sp.value_group:

            def _make_repl(pattern: _SecretPattern) -> re.Pattern[str]:
                return pattern  # capture in closure

            p = sp  # closure capture

            def _repl(m: re.Match[str], _p: _SecretPattern = p) -> str:
                return m.group("key") + _p.label

            redacted = sp.regex.sub(_repl, redacted)
        else:
            redacted = sp.regex.sub(sp.label, redacted)

    # Collect warnings from the redacted text's perspective against original text
    warnings = detect_in_content(text)
    return redacted, warnings


def format_warning(match: SecretMatch) -> str:
    """Return a human-readable warning string for one secret match."""
    return f"[secret:{match.pattern_name}] line {match.line_number}: {match.redacted_snippet!r}"
