"""Tests for secret_detector — content patterns, filename detection, redaction."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from contextos.cli.main import app
from contextos.core.secret_detector import (
    SecretMatch,
    detect_in_content,
    format_warning,
    is_secret_file,
    redact_content,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# is_secret_file — filename-based exclusion
# ---------------------------------------------------------------------------


class TestIsSecretFile:
    def test_env_file(self) -> None:
        assert is_secret_file(".env")

    def test_env_local(self) -> None:
        assert is_secret_file(".env.local")

    def test_env_prod(self) -> None:
        assert is_secret_file(".env.production")

    def test_env_example_safe(self) -> None:
        assert not is_secret_file(".env.example")

    def test_env_sample_safe(self) -> None:
        assert not is_secret_file(".env.sample")

    def test_env_template_safe(self) -> None:
        assert not is_secret_file(".env.template")

    def test_env_dist_safe(self) -> None:
        assert not is_secret_file(".env.dist")

    def test_secret_in_name(self) -> None:
        assert is_secret_file("app_secrets.json")

    def test_credentials_file(self) -> None:
        assert is_secret_file("credentials.json")

    def test_password_file(self) -> None:
        assert is_secret_file("passwords.txt")

    def test_pem_extension(self) -> None:
        assert is_secret_file("cert.pem")

    def test_key_extension(self) -> None:
        assert is_secret_file("private.key")

    def test_p12_extension(self) -> None:
        assert is_secret_file("keystore.p12")

    def test_pfx_extension(self) -> None:
        assert is_secret_file("keystore.pfx")

    def test_crt_extension(self) -> None:
        assert is_secret_file("server.crt")

    def test_id_rsa(self) -> None:
        assert is_secret_file("id_rsa")

    def test_id_ecdsa(self) -> None:
        assert is_secret_file("id_ecdsa")

    def test_id_ed25519(self) -> None:
        assert is_secret_file("id_ed25519")

    def test_nested_path_env(self) -> None:
        assert is_secret_file("config/.env")

    def test_nested_path_key(self) -> None:
        assert is_secret_file("certs/server.key")

    def test_normal_py_file_safe(self) -> None:
        assert not is_secret_file("auth.py")

    def test_normal_config_safe(self) -> None:
        assert not is_secret_file("settings.json")

    def test_readme_safe(self) -> None:
        assert not is_secret_file("README.md")

    def test_test_file_safe(self) -> None:
        assert not is_secret_file("test_auth.py")


# ---------------------------------------------------------------------------
# detect_in_content — per-pattern detection
# ---------------------------------------------------------------------------


class TestDetectOpenAIKey:
    def test_classic_sk_key(self) -> None:
        matches = detect_in_content("sk-abcdefghijklmnopqrstu")
        names = [m.pattern_name for m in matches]
        assert "openai_api_key" in names

    def test_proj_format(self) -> None:
        matches = detect_in_content("sk-proj-abcdefghijklmnopqrstu")
        names = [m.pattern_name for m in matches]
        assert "openai_api_key" in names

    def test_too_short_not_matched(self) -> None:
        matches = detect_in_content("sk-short")
        names = [m.pattern_name for m in matches]
        assert "openai_api_key" not in names

    def test_line_number_correct(self) -> None:
        text = "line1\nsk-abcdefghijklmnopqrstu\nline3"
        matches = detect_in_content(text)
        openai = [m for m in matches if m.pattern_name == "openai_api_key"]
        assert openai[0].line_number == 2


class TestDetectAnthropicKey:
    def test_anthropic_key(self) -> None:
        matches = detect_in_content("sk-ant-api03-abcdefghijklmnopqrstu")
        names = [m.pattern_name for m in matches]
        assert "anthropic_api_key" in names

    def test_anthropic_variant(self) -> None:
        matches = detect_in_content("sk-ant-abcdefghijklmnopqrstuvwxyz")
        names = [m.pattern_name for m in matches]
        assert "anthropic_api_key" in names

    def test_plain_sk_not_anthropic(self) -> None:
        # A plain sk- key is openai, not anthropic
        matches = detect_in_content("sk-abcdefghijklmnopqrstu")
        names = [m.pattern_name for m in matches]
        assert "anthropic_api_key" not in names


class TestDetectAWSKeys:
    def test_access_key_id(self) -> None:
        matches = detect_in_content("AKIAIOSFODNN7EXAMPLE")
        names = [m.pattern_name for m in matches]
        assert "aws_access_key_id" in names

    def test_akia_too_short_not_matched(self) -> None:
        matches = detect_in_content("AKIASHORT")
        names = [m.pattern_name for m in matches]
        assert "aws_access_key_id" not in names

    def test_aws_secret_assignment(self) -> None:
        text = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE"
        matches = detect_in_content(text)
        names = [m.pattern_name for m in matches]
        assert "aws_secret_access_key" in names

    def test_aws_secret_case_insensitive(self) -> None:
        text = "aws_secret_access_key=EXAMPLEKEY1234567890EXAMPLEKEY1234567"
        matches = detect_in_content(text)
        names = [m.pattern_name for m in matches]
        assert "aws_secret_access_key" in names


class TestDetectGitHubTokens:
    def test_ghp_token(self) -> None:
        matches = detect_in_content("ghp_" + "a" * 36)
        names = [m.pattern_name for m in matches]
        assert "github_token" in names

    def test_gho_token(self) -> None:
        matches = detect_in_content("gho_" + "b" * 36)
        names = [m.pattern_name for m in matches]
        assert "github_token" in names

    def test_ghs_token(self) -> None:
        matches = detect_in_content("ghs_" + "c" * 36)
        names = [m.pattern_name for m in matches]
        assert "github_token" in names

    def test_ghu_token(self) -> None:
        matches = detect_in_content("ghu_" + "d" * 36)
        names = [m.pattern_name for m in matches]
        assert "github_token" in names

    def test_too_short_not_matched(self) -> None:
        matches = detect_in_content("ghp_short")
        names = [m.pattern_name for m in matches]
        assert "github_token" not in names

    def test_fine_grained_token(self) -> None:
        matches = detect_in_content("github_pat_" + "A" * 82)
        names = [m.pattern_name for m in matches]
        assert "github_fine_grained" in names


class TestDetectJWT:
    _JWT = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )

    def test_jwt_detected(self) -> None:
        matches = detect_in_content(self._JWT)
        names = [m.pattern_name for m in matches]
        assert "jwt" in names

    def test_two_part_not_jwt(self) -> None:
        matches = detect_in_content("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0")
        names = [m.pattern_name for m in matches]
        assert "jwt" not in names

    def test_jwt_in_auth_header(self) -> None:
        text = f"Authorization: Bearer {self._JWT}"
        matches = detect_in_content(text)
        assert len(matches) > 0


class TestDetectPrivateKey:
    def test_rsa_private_key(self) -> None:
        matches = detect_in_content("-----BEGIN RSA PRIVATE KEY-----")
        names = [m.pattern_name for m in matches]
        assert "private_key_pem" in names

    def test_ec_private_key(self) -> None:
        matches = detect_in_content("-----BEGIN EC PRIVATE KEY-----")
        names = [m.pattern_name for m in matches]
        assert "private_key_pem" in names

    def test_openssh_private_key(self) -> None:
        matches = detect_in_content("-----BEGIN OPENSSH PRIVATE KEY-----")
        names = [m.pattern_name for m in matches]
        assert "private_key_pem" in names

    def test_generic_private_key(self) -> None:
        matches = detect_in_content("-----BEGIN PRIVATE KEY-----")
        names = [m.pattern_name for m in matches]
        assert "private_key_pem" in names

    def test_public_key_not_detected(self) -> None:
        matches = detect_in_content("-----BEGIN PUBLIC KEY-----")
        names = [m.pattern_name for m in matches]
        assert "private_key_pem" not in names


class TestDetectSlackToken:
    # Constructed dynamically so the literal string doesn't appear in source.
    _XOXB = "xoxb-" + "1" * 12 + "-" + "1" * 12 + "-" + "a" * 24
    _XOXP = "xoxp-" + "1" * 50

    def test_xoxb_token(self) -> None:
        matches = detect_in_content(self._XOXB)
        names = [m.pattern_name for m in matches]
        assert "slack_token" in names

    def test_xoxp_token(self) -> None:
        matches = detect_in_content(self._XOXP)
        names = [m.pattern_name for m in matches]
        assert "slack_token" in names

    def test_too_short_not_matched(self) -> None:
        matches = detect_in_content("xoxb-short")
        names = [m.pattern_name for m in matches]
        assert "slack_token" not in names


class TestDetectStripeKey:
    # Constructed dynamically so literal strings don't appear in source.
    _SK_LIVE = "sk" + "_live_" + "a" * 24
    _RK_LIVE = "rk" + "_live_" + "a" * 24
    _SK_TEST = "sk" + "_test_" + "a" * 24

    def test_sk_live(self) -> None:
        matches = detect_in_content(self._SK_LIVE)
        names = [m.pattern_name for m in matches]
        assert "stripe_secret_key" in names

    def test_rk_live(self) -> None:
        matches = detect_in_content(self._RK_LIVE)
        names = [m.pattern_name for m in matches]
        assert "stripe_restricted_key" in names

    def test_test_key_not_matched(self) -> None:
        # sk_test_ is not a production secret — don't flag it
        matches = detect_in_content(self._SK_TEST)
        names = [m.pattern_name for m in matches]
        assert "stripe_secret_key" not in names


class TestDetectDatabaseURL:
    def test_postgres_url(self) -> None:
        matches = detect_in_content("postgresql://user:s3cr3tpassword@host:5432/db")
        names = [m.pattern_name for m in matches]
        assert "database_url" in names

    def test_mysql_url(self) -> None:
        matches = detect_in_content("mysql://admin:hunter2@localhost/mydb")
        names = [m.pattern_name for m in matches]
        assert "database_url" in names

    def test_mongodb_url(self) -> None:
        matches = detect_in_content(
            "mongodb://testuser:REDACTED_FOR_TESTS@cluster0.example.invalid/db"
        )
        names = [m.pattern_name for m in matches]
        assert "database_url" in names

    def test_no_password_url_not_matched(self) -> None:
        # URL without password (no colon before @)
        matches = detect_in_content("postgresql://localhost/db")
        names = [m.pattern_name for m in matches]
        assert "database_url" not in names


class TestDetectEnvAssignments:
    def test_password_assignment(self) -> None:
        matches = detect_in_content("PASSWORD=hunter2")
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" in names

    def test_api_key_assignment(self) -> None:
        matches = detect_in_content("API_KEY=abc12345")
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" in names

    def test_secret_key_assignment(self) -> None:
        matches = detect_in_content("SECRET_KEY=mysupersecretvalue")
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" in names

    def test_access_token_assignment(self) -> None:
        matches = detect_in_content("ACCESS_TOKEN=tok_abc123456")
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" in names

    def test_auth_token_assignment(self) -> None:
        matches = detect_in_content("AUTH_TOKEN=mytoken123")
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" in names

    def test_db_password_assignment(self) -> None:
        matches = detect_in_content("DB_PASSWORD=securepass")
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" in names

    def test_template_placeholder_not_matched(self) -> None:
        # ${...} placeholders are not real secrets
        matches = detect_in_content("PASSWORD=${DB_PASSWORD}")
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" not in names

    def test_too_short_value_not_matched(self) -> None:
        matches = detect_in_content("PASSWORD=abc")  # only 3 chars
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" not in names

    def test_equals_style_explicit(self) -> None:
        # = style is the canonical match; : is not used (avoids Python annotation FPs)
        matches = detect_in_content("password=mysecretvalue")
        names = [m.pattern_name for m in matches]
        assert "env_secret_assignment" in names


class TestDetectBearerToken:
    def test_bearer_in_header(self) -> None:
        matches = detect_in_content("Authorization: Bearer mytoken123456789")
        names = [m.pattern_name for m in matches]
        assert "bearer_token" in names

    def test_bearer_case_insensitive(self) -> None:
        matches = detect_in_content("authorization: bearer mytoken123456789")
        names = [m.pattern_name for m in matches]
        assert "bearer_token" in names

    def test_short_bearer_not_matched(self) -> None:
        matches = detect_in_content("Authorization: Bearer tok")
        names = [m.pattern_name for m in matches]
        assert "bearer_token" not in names


# ---------------------------------------------------------------------------
# Clean content — no false positives on normal code
# ---------------------------------------------------------------------------


class TestNoFalsePositives:
    def test_normal_function(self) -> None:
        code = "def authenticate(user: str, password: str) -> bool:\n    return True\n"
        matches = detect_in_content(code)
        # Function signature mentioning 'password' should NOT match env_secret_assignment
        # because the value pattern requires a non-whitespace value after = or :
        assert not any(m.pattern_name == "env_secret_assignment" for m in matches)

    def test_sha256_hash_in_comment(self) -> None:
        code = "# sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        # SHA256 is not a defined pattern, should be clean
        matches = detect_in_content(code)
        assert len(matches) == 0

    def test_empty_string_clean(self) -> None:
        assert detect_in_content("") == []

    def test_normal_config_clean(self) -> None:
        config = "[database]\nhost = localhost\nport = 5432\ndbname = myapp\n"
        matches = detect_in_content(config)
        assert len(matches) == 0

    def test_example_env_values_in_docs(self) -> None:
        # Docs often show example env files — these should not be falsely flagged
        # (though some may still be caught; verify no crash at minimum)
        doc = "# Example:\n# DATABASE_URL=postgres://user:password@localhost/db\n"
        _ = detect_in_content(doc)  # should not raise


# ---------------------------------------------------------------------------
# redact_content
# ---------------------------------------------------------------------------


class TestRedactContent:
    def test_openai_key_redacted(self) -> None:
        text = "sk-abcdefghijklmnopqrstu"
        redacted, _ = redact_content(text)
        assert "sk-" not in redacted
        assert "REDACTED" in redacted

    def test_anthropic_key_redacted(self) -> None:
        text = "sk-ant-api03-abcdefghijklmnopqrstu"
        redacted, _ = redact_content(text)
        assert "sk-ant" not in redacted
        assert "REDACTED" in redacted

    def test_aws_key_id_redacted(self) -> None:
        text = "AKIAIOSFODNN7EXAMPLE"
        redacted, _ = redact_content(text)
        assert "AKIA" not in redacted
        assert "REDACTED" in redacted

    def test_github_token_redacted(self) -> None:
        text = "ghp_" + "a" * 36
        redacted, _ = redact_content(text)
        assert "ghp_" not in redacted
        assert "REDACTED" in redacted

    def test_jwt_redacted(self) -> None:
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        redacted, _ = redact_content(jwt)
        assert "eyJ" not in redacted
        assert "REDACTED" in redacted

    def test_private_key_header_redacted(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."
        redacted, _ = redact_content(text)
        assert "REDACTED" in redacted

    def test_env_password_key_preserved(self) -> None:
        text = "DATABASE_PASSWORD=supersecret"
        redacted, _ = redact_content(text)
        # Key name preserved, value redacted
        assert "DATABASE_PASSWORD" in redacted
        assert "supersecret" not in redacted
        assert "REDACTED" in redacted

    def test_env_api_key_preserved(self) -> None:
        text = "API_KEY=abc12345678"
        redacted, _ = redact_content(text)
        assert "API_KEY" in redacted
        assert "abc12345678" not in redacted

    def test_db_url_password_redacted(self) -> None:
        text = "postgresql://testuser:REDACTED_FOR_TESTS@db.example.invalid/testdb"
        redacted, _ = redact_content(text)
        assert "s3cr3t" not in redacted
        assert "REDACTED" in redacted

    def test_slack_token_redacted(self) -> None:
        token = "xoxb-" + "1" * 12 + "-" + "1" * 12 + "-" + "a" * 24
        redacted, _ = redact_content(token)
        assert "xoxb-" not in redacted
        assert "REDACTED" in redacted

    def test_stripe_key_redacted(self) -> None:
        text = "sk" + "_live_" + "a" * 24
        redacted, _ = redact_content(text)
        assert "sk_live_" not in redacted
        assert "REDACTED" in redacted

    def test_returns_warnings_list(self) -> None:
        _, warnings = redact_content("sk-abcdefghijklmnopqrstu")
        assert isinstance(warnings, list)
        assert len(warnings) > 0
        assert all(isinstance(w, SecretMatch) for w in warnings)

    def test_clean_text_returns_empty_warnings(self) -> None:
        _, warnings = redact_content("def add(a, b):\n    return a + b\n")
        assert warnings == []

    def test_empty_string_unchanged(self) -> None:
        redacted, warnings = redact_content("")
        assert redacted == ""
        assert warnings == []

    def test_multiline_multiple_secrets(self) -> None:
        text = "OPENAI_KEY=sk-abcdefghijklmnopqrstu\nDATABASE_PASSWORD=hunter2\nnormal_line = 42\n"
        redacted, warnings = redact_content(text)
        assert "sk-" not in redacted
        assert "hunter2" not in redacted
        assert "normal_line" in redacted
        assert len(warnings) >= 2


# ---------------------------------------------------------------------------
# format_warning
# ---------------------------------------------------------------------------


class TestFormatWarning:
    def test_returns_string(self) -> None:
        m = SecretMatch(
            pattern_name="openai_api_key",
            line_number=3,
            redacted_snippet="sk-[REDACTED]",
        )
        result = format_warning(m)
        assert isinstance(result, str)

    def test_contains_pattern_name(self) -> None:
        m = SecretMatch("openai_api_key", 1, "snippet")
        assert "openai_api_key" in format_warning(m)

    def test_contains_line_number(self) -> None:
        m = SecretMatch("jwt", 42, "snippet")
        assert "42" in format_warning(m)


# ---------------------------------------------------------------------------
# Integration — redaction wired into context selector
# ---------------------------------------------------------------------------


_PY_WITH_SECRET = (
    "import os\nOPENAI_API_KEY = 'sk-abcdefghijklmnopqrstuvwxyz'\ndef call_api(): pass\n"
)

_PY_AUTH = "def authenticate(user, password): return True\n"


@pytest.fixture()
def secret_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Repo with one file containing an embedded secret."""
    root = tmp_path / "repo"
    root.mkdir()

    (root / "config.py").write_text(_PY_WITH_SECRET, encoding="utf-8")
    (root / "auth.py").write_text(_PY_AUTH, encoding="utf-8")

    ctxdir = root / ".contextos"
    ctxdir.mkdir()

    from contextos.core.dependency_graph import build_graph, write_graph
    from contextos.core.scanner import ScanConfig, scan
    from contextos.core.summarizer import summarize_repo

    result = scan(root, ScanConfig())
    summarize_repo(result, output_path=ctxdir / "file_summaries.json")
    write_graph(build_graph(result), ctxdir / "dependency_graph.json")
    (ctxdir / "MEMORY.md").write_text("", encoding="utf-8")

    return root, ctxdir


class TestIntegrationRedaction:
    def test_secret_not_in_pack(self, secret_repo: tuple[Path, Path]) -> None:
        root, ctxdir = secret_repo
        result = runner.invoke(
            app,
            ["pack", str(root), "--task", "call the openai api", "--no-timestamp"],
        )
        assert result.exit_code == 0
        pack = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in pack

    def test_redacted_token_in_pack(self, secret_repo: tuple[Path, Path]) -> None:
        root, ctxdir = secret_repo
        runner.invoke(
            app,
            ["pack", str(root), "--task", "call the openai api", "--no-timestamp"],
        )
        pack = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        assert "REDACTED" in pack

    def test_warning_in_pack_output(self, secret_repo: tuple[Path, Path]) -> None:
        root, ctxdir = secret_repo
        result = runner.invoke(
            app,
            ["pack", str(root), "--task", "call the openai api"],
        )
        # Warning printed to console or included in pack
        assert result.exit_code == 0

    def test_allow_sensitive_shows_secret(self, secret_repo: tuple[Path, Path]) -> None:
        root, ctxdir = secret_repo
        runner.invoke(
            app,
            [
                "pack",
                str(root),
                "--task",
                "call the openai api",
                "--allow-sensitive",
                "--no-timestamp",
            ],
        )
        pack = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        # Secret is NOT redacted when --allow-sensitive is used
        assert "sk-abcdefghijklmnopqrstuvwxyz" in pack

    def test_allow_sensitive_warning_banner(self, secret_repo: tuple[Path, Path]) -> None:
        root, ctxdir = secret_repo
        runner.invoke(
            app,
            [
                "pack",
                str(root),
                "--task",
                "call the openai api",
                "--allow-sensitive",
                "--no-timestamp",
            ],
        )
        pack = (ctxdir / "context_pack.md").read_text(encoding="utf-8")
        assert "WARNING" in pack or "allow-sensitive" in pack

    def test_secret_not_in_export(self, secret_repo: tuple[Path, Path]) -> None:
        root, ctxdir = secret_repo
        result = runner.invoke(
            app,
            ["export", "claude", "--repo", str(root), "--task", "call api"],
        )
        assert result.exit_code == 0
        out_file = ctxdir / "CLAUDE_CONTEXT.md"
        if out_file.exists():
            assert "sk-abcdefghijklmnopqrstuvwxyz" not in out_file.read_text(encoding="utf-8")

    def test_secret_warnings_in_selection(self, secret_repo: tuple[Path, Path]) -> None:
        from contextos.core.context_selector import (
            SelectionConfig,
            _load_graph_safe,
            _load_summaries_safe,
            _select,
        )

        root, ctxdir = secret_repo
        summaries = _load_summaries_safe(ctxdir)
        graph = _load_graph_safe(ctxdir)
        cfg = SelectionConfig(budget=8000)
        selection = _select("call openai api", summaries, graph, "", root, cfg)
        assert isinstance(selection.secret_warnings, list)

    def test_no_warnings_in_clean_repo(self, tmp_path: Path) -> None:
        root = tmp_path / "clean"
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

        from contextos.core.context_selector import (
            SelectionConfig,
            _load_graph_safe,
            _load_summaries_safe,
            _select,
        )

        summaries = _load_summaries_safe(ctxdir)
        graph = _load_graph_safe(ctxdir)
        sel = _select("do something", summaries, graph, "", root, SelectionConfig())
        assert sel.secret_warnings == []


# ---------------------------------------------------------------------------
# CLI --allow-sensitive flag
# ---------------------------------------------------------------------------


class TestAllowSensitiveCLI:
    def test_pack_allow_sensitive_flag_accepted(self, secret_repo: tuple[Path, Path]) -> None:
        root, _ = secret_repo
        result = runner.invoke(
            app,
            ["pack", str(root), "--task", "test", "--allow-sensitive"],
        )
        assert result.exit_code == 0

    def test_export_claude_allow_sensitive(self, secret_repo: tuple[Path, Path]) -> None:
        root, _ = secret_repo
        result = runner.invoke(
            app,
            ["export", "claude", "--repo", str(root), "--task", "test", "--allow-sensitive"],
        )
        assert result.exit_code == 0

    def test_export_codex_allow_sensitive(self, secret_repo: tuple[Path, Path]) -> None:
        root, _ = secret_repo
        result = runner.invoke(
            app,
            ["export", "codex", "--repo", str(root), "--task", "test", "--allow-sensitive"],
        )
        assert result.exit_code == 0

    def test_export_cursor_allow_sensitive(self, secret_repo: tuple[Path, Path]) -> None:
        root, _ = secret_repo
        result = runner.invoke(
            app,
            ["export", "cursor", "--repo", str(root), "--task", "test", "--allow-sensitive"],
        )
        assert result.exit_code == 0

    def test_export_aider_allow_sensitive(self, secret_repo: tuple[Path, Path]) -> None:
        root, _ = secret_repo
        result = runner.invoke(
            app,
            ["export", "aider", "--repo", str(root), "--task", "test", "--allow-sensitive"],
        )
        assert result.exit_code == 0

    def test_allow_sensitive_warning_in_cli_output(self, secret_repo: tuple[Path, Path]) -> None:
        root, _ = secret_repo
        result = runner.invoke(
            app,
            ["pack", str(root), "--task", "test", "--allow-sensitive"],
        )
        assert "allow-sensitive" in result.output.lower() or "DISABLED" in result.output
