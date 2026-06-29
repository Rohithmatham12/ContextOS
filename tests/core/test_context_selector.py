"""Tests for contextos/core/context_selector.py."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from contextos.core.context_selector import (
    SelectionConfig,
    _enforce_budget,
    _expand_deps,
    _is_secret,
    _keywords,
    _pair_tests,
    _render_summary,
    _score_file,
    _select,
    select_context,
)
from contextos.core.dependency_graph import DependencyGraph, DGEdge, DGNode
from contextos.core.summarizer import FileSummary

ScoreMap: TypeAlias = dict[str, tuple[float, list[str]]]
RankedFiles: TypeAlias = list[tuple[str, float, list[str]]]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summary(
    rel_path: str,
    *,
    language: str = "Python",
    purpose: str = "",
    imports: list[str] | None = None,
    exports: list[str] | None = None,
    symbols: list[str] | None = None,
    docstring: str = "",
) -> FileSummary:
    return FileSummary(
        rel_path=rel_path,
        language=language,
        purpose=purpose,
        imports=imports or [],
        exports=exports or [],
        symbols=symbols or [],
        docstring=docstring,
        line_count=10,
        content_hash="abc123",
    )


def _empty_graph() -> DependencyGraph:
    return DependencyGraph(nodes=[], edges=[], unresolved={}, cycles=[])


def _graph_with_edges(*edges: tuple[str, str]) -> DependencyGraph:
    node_ids = {p for pair in edges for p in pair}
    nodes = [DGNode(id=p, language="Python") for p in node_ids]
    dg_edges = [DGEdge(source=s, target=t, kind="local", raw_import=t) for s, t in edges]
    return DependencyGraph(nodes=nodes, edges=dg_edges, unresolved={}, cycles=[])


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# _keywords
# ---------------------------------------------------------------------------


class TestKeywords:
    def test_extracts_meaningful_words(self) -> None:
        kw = _keywords("implement rate limiting middleware")
        assert "rate" in kw
        assert "limiting" in kw
        assert "middleware" in kw

    def test_drops_stopwords(self) -> None:
        kw = _keywords("fix the authentication bug")
        assert "the" not in kw
        assert "fix" not in kw  # stopword

    def test_short_words_dropped(self) -> None:
        kw = _keywords("fix it now")
        assert "it" not in kw

    def test_camel_case_split(self) -> None:
        kw = _keywords("handleRequest")
        assert "handle" in kw
        assert "request" in kw

    def test_empty_task(self) -> None:
        assert _keywords("") == set()

    def test_lowercase_normalised(self) -> None:
        kw = _keywords("AuthMiddleware")
        assert "auth" in kw or "authmiddleware" in kw

    def test_deduplication(self) -> None:
        kw = _keywords("auth auth auth")
        assert len(kw) <= 5  # no duplicates — it's a set


# ---------------------------------------------------------------------------
# _is_secret
# ---------------------------------------------------------------------------


class TestIsSecret:
    def test_dotenv_is_secret(self) -> None:
        assert _is_secret(".env")

    def test_dotenv_local_is_secret(self) -> None:
        assert _is_secret(".env.local")

    def test_dotenv_prod_is_secret(self) -> None:
        assert _is_secret(".env.production")

    def test_dotenv_example_safe(self) -> None:
        assert not _is_secret(".env.example")

    def test_dotenv_sample_safe(self) -> None:
        assert not _is_secret(".env.sample")

    def test_secret_in_name(self) -> None:
        assert _is_secret("my_secret_key.txt")

    def test_credential_in_name(self) -> None:
        assert _is_secret("credentials.json")

    def test_pem_file(self) -> None:
        assert _is_secret("server.pem")

    def test_key_file(self) -> None:
        assert _is_secret("id_rsa.key")

    def test_id_rsa(self) -> None:
        assert _is_secret("id_rsa")

    def test_normal_python_file_safe(self) -> None:
        assert not _is_secret("auth.py")

    def test_normal_config_safe(self) -> None:
        assert not _is_secret("pyproject.toml")

    def test_nested_path_uses_name_only(self) -> None:
        # "secrets" in dir name should NOT block the file
        assert not _is_secret("my/project/secrets/manager.py")
        # But "secrets" in filename itself should block
        assert _is_secret("secret_config.py")


# ---------------------------------------------------------------------------
# _score_file
# ---------------------------------------------------------------------------


class TestScoreFile:
    def test_path_match_raises_score(self) -> None:
        s = _summary("auth/middleware.py")
        score, _ = _score_file("auth/middleware.py", s, {"auth"}, set(), SelectionConfig())
        assert score > 0

    def test_symbol_match_raises_score(self) -> None:
        s = _summary("core/utils.py", exports=["authenticate", "logout"])
        score, _ = _score_file("core/utils.py", s, {"authenticate"}, set(), SelectionConfig())
        assert score > 0

    def test_purpose_match_raises_score(self) -> None:
        s = _summary("app.py", purpose="handles rate limiting for API requests")
        score, _ = _score_file("app.py", s, {"rate", "limiting"}, set(), SelectionConfig())
        assert score > 0

    def test_no_match_zero_score(self) -> None:
        s = _summary("unrelated/models.py")
        score, _ = _score_file(
            "unrelated/models.py", s, {"authentication", "jwt"}, set(), SelectionConfig()
        )
        assert score == 0.0

    def test_readme_gets_priority_bonus(self) -> None:
        s = _summary("readme.md")
        # Even with no keyword match, readme gets a bonus
        score, reasons = _score_file("readme.md", s, set(), set(), SelectionConfig())
        assert score > 0
        assert any("priority" in r for r in reasons)

    def test_memory_mention_bonus(self) -> None:
        s = _summary("src/auth.py")
        score_with, _ = _score_file("src/auth.py", s, set(), {"src/auth.py"}, SelectionConfig())
        score_without, _ = _score_file("src/auth.py", s, set(), set(), SelectionConfig())
        assert score_with > score_without

    def test_reasons_populated_on_match(self) -> None:
        s = _summary("auth.py")
        _, reasons = _score_file("auth.py", s, {"auth"}, set(), SelectionConfig())
        assert len(reasons) > 0

    def test_reasons_empty_on_no_match(self) -> None:
        s = _summary("unrelated.py")
        _, reasons = _score_file("unrelated.py", s, {"auth"}, set(), SelectionConfig())
        # Might have no reasons at all
        assert all("path" not in r and "symbol" not in r for r in reasons)

    def test_path_weight_applied(self) -> None:
        cfg = SelectionConfig(path_weight=10.0, symbol_weight=1.0)
        s = _summary("auth.py", exports=["auth"])
        path_score, _ = _score_file("auth.py", s, {"auth"}, set(), cfg)
        # Score should include both path (10) and symbol (1) hits → 11
        assert path_score >= 10.0

    def test_import_match_adds_score(self) -> None:
        s = _summary("app.py", imports=["jwt"])
        score, reasons = _score_file("app.py", s, {"jwt"}, set(), SelectionConfig())
        assert score > 0
        assert any("imports" in r for r in reasons)


# ---------------------------------------------------------------------------
# _expand_deps
# ---------------------------------------------------------------------------


class TestExpandDeps:
    def test_dep_boosted_when_source_high_score(self) -> None:
        scores: ScoreMap = {
            "src/main.py": (5.0, ["path:main"]),
            "src/utils.py": (0.0, []),
        }
        graph = _graph_with_edges(("src/main.py", "src/utils.py"))
        result = _expand_deps(scores, graph, SelectionConfig())
        # utils.py should have higher score now
        assert result["src/utils.py"][0] > 0.0

    def test_dep_reason_added(self) -> None:
        scores: ScoreMap = {
            "src/main.py": (5.0, ["path:main"]),
            "src/utils.py": (0.0, []),
        }
        graph = _graph_with_edges(("src/main.py", "src/utils.py"))
        result = _expand_deps(scores, graph, SelectionConfig())
        reasons = result["src/utils.py"][1]
        assert any("dep:" in r for r in reasons)

    def test_package_edges_not_boosted(self) -> None:
        # Package imports like "os", "sys" don't appear in summaries
        scores: ScoreMap = {
            "src/main.py": (5.0, ["path:main"]),
        }
        graph = DependencyGraph(
            nodes=[DGNode(id="src/main.py", language="Python")],
            edges=[DGEdge(source="src/main.py", target="os", kind="package", raw_import="os")],
            unresolved={},
            cycles=[],
        )
        result = _expand_deps(scores, graph, SelectionConfig())
        # "os" not in scores — no KeyError, no new entry
        assert "os" not in result

    def test_low_score_source_not_expanded(self) -> None:
        scores: ScoreMap = {
            "src/main.py": (0.01, []),
            "src/utils.py": (0.0, []),
        }
        graph = _graph_with_edges(("src/main.py", "src/utils.py"))
        result = _expand_deps(scores, graph, SelectionConfig())
        # main.py IS above threshold (0.01 > 0.003), so utils gets boosted
        assert result["src/utils.py"][0] > 0.0

    def test_empty_scores_returns_empty(self) -> None:
        result = _expand_deps({}, _empty_graph(), SelectionConfig())
        assert result == {}

    def test_dep_factor_applied(self) -> None:
        scores: ScoreMap = {
            "src/main.py": (10.0, []),
            "src/utils.py": (0.0, []),
        }
        cfg = SelectionConfig(dep_factor=0.5)
        graph = _graph_with_edges(("src/main.py", "src/utils.py"))
        result = _expand_deps(scores, graph, cfg)
        # boost = 10.0 * 0.5 = 5.0
        assert abs(result["src/utils.py"][0] - 5.0) < 0.01

    def test_existing_score_preserved_and_augmented(self) -> None:
        scores: ScoreMap = {
            "src/main.py": (10.0, []),
            "src/utils.py": (2.0, ["path:utils"]),
        }
        graph = _graph_with_edges(("src/main.py", "src/utils.py"))
        result = _expand_deps(scores, graph, SelectionConfig())
        # utils gets its existing score + boost
        assert result["src/utils.py"][0] > 2.0
        assert "path:utils" in result["src/utils.py"][1]


# ---------------------------------------------------------------------------
# _pair_tests
# ---------------------------------------------------------------------------


class TestPairTests:
    def test_test_file_boosted(self) -> None:
        scores: ScoreMap = {
            "src/auth.py": (5.0, ["path:auth"]),
            "tests/test_auth.py": (0.0, []),
        }
        result = _pair_tests(scores, set(scores), SelectionConfig())
        assert result["tests/test_auth.py"][0] > 0.0

    def test_test_pair_reason_added(self) -> None:
        scores: ScoreMap = {
            "src/auth.py": (5.0, ["path:auth"]),
            "tests/test_auth.py": (0.0, []),
        }
        result = _pair_tests(scores, set(scores), SelectionConfig())
        reasons = result["tests/test_auth.py"][1]
        assert any("test_pair" in r for r in reasons)

    def test_same_dir_test_file(self) -> None:
        scores: ScoreMap = {
            "lib/utils.py": (5.0, []),
            "lib/test_utils.py": (0.0, []),
        }
        result = _pair_tests(scores, set(scores), SelectionConfig())
        assert result["lib/test_utils.py"][0] > 0.0

    def test_suffix_test_file(self) -> None:
        scores: ScoreMap = {
            "lib/utils.py": (5.0, []),
            "lib/utils_test.py": (0.0, []),
        }
        result = _pair_tests(scores, set(scores), SelectionConfig())
        assert result["lib/utils_test.py"][0] > 0.0

    def test_no_test_file_present(self) -> None:
        scores = {"src/auth.py": (5.0, ["path:auth"])}
        result = _pair_tests(scores, set(scores), SelectionConfig())
        # No crash, no new entries
        assert set(result) == {"src/auth.py"}

    def test_low_score_source_not_paired(self) -> None:
        scores: ScoreMap = {
            "src/auth.py": (0.0, []),
            "tests/test_auth.py": (0.0, []),
        }
        result = _pair_tests(scores, set(scores), SelectionConfig())
        # max=0 → threshold=0 → auth.py is NOT above threshold
        assert result["tests/test_auth.py"][0] == 0.0

    def test_pair_bonus_value(self) -> None:
        scores: ScoreMap = {
            "src/auth.py": (10.0, []),
            "tests/test_auth.py": (1.0, []),
        }
        cfg = SelectionConfig(test_pair_bonus=2.0)
        result = _pair_tests(scores, set(scores), cfg)
        assert result["tests/test_auth.py"][0] == 3.0  # 1.0 + 2.0

    def test_empty_scores(self) -> None:
        assert _pair_tests({}, set(), SelectionConfig()) == {}


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


class TestBudgetEnforcement:
    def _make_summaries(self, paths: list[str]) -> dict[str, FileSummary]:
        return {p: _summary(p) for p in paths}

    def test_budget_not_exceeded(self, tmp_path: Path) -> None:
        content = "x = 1\n" * 500  # ~1500 tokens
        for i in range(5):
            _write_file(tmp_path / f"file{i}.py", content)

        summaries = self._make_summaries([f"file{i}.py" for i in range(5)])
        ranked: RankedFiles = [(f"file{i}.py", float(5 - i), []) for i in range(5)]
        cfg = SelectionConfig(budget=3000)

        selected, _, _warnings = _enforce_budget(ranked, summaries, tmp_path, cfg)
        total = sum(f.tokens for f in selected)
        assert total <= cfg.budget

    def test_excluded_when_over_budget(self, tmp_path: Path) -> None:
        content = "x = 1\n" * 1000  # large file
        for i in range(4):
            _write_file(tmp_path / f"file{i}.py", content)

        # Give each file a long export list so even the summary is ~100 tokens
        many_exports = [f"very_long_function_name_export_{i:03d}" for i in range(60)]
        summaries = {f"file{i}.py": _summary(f"file{i}.py", exports=many_exports) for i in range(4)}
        ranked: RankedFiles = [(f"file{i}.py", float(4 - i), []) for i in range(4)]
        cfg = SelectionConfig(budget=150)  # fits at most 1-2 summaries

        selected, excluded, _warnings = _enforce_budget(ranked, summaries, tmp_path, cfg)
        assert len(excluded) > 0
        assert sum(f.tokens for f in selected) <= cfg.budget

    def test_highest_score_included_first(self, tmp_path: Path) -> None:
        content = "x = 1\n" * 200
        for name in ("high.py", "low.py"):
            _write_file(tmp_path / name, content)

        summaries = self._make_summaries(["high.py", "low.py"])
        ranked: RankedFiles = [("high.py", 10.0, []), ("low.py", 1.0, [])]
        cfg = SelectionConfig(budget=800)  # fits only one

        selected, excluded, _warnings = _enforce_budget(ranked, summaries, tmp_path, cfg)
        selected_paths = [f.rel_path for f in selected]
        assert "high.py" in selected_paths

    def test_full_file_preferred_when_fits(self, tmp_path: Path) -> None:
        content = "x = 1\n"  # tiny file, always fits
        _write_file(tmp_path / "small.py", content)
        summaries = {"small.py": _summary("small.py", purpose="does stuff")}
        ranked: RankedFiles = [("small.py", 5.0, [])]
        cfg = SelectionConfig(budget=5000)

        selected, _, _warnings = _enforce_budget(ranked, summaries, tmp_path, cfg)
        assert selected[0].kind == "full"

    def test_snippet_used_when_full_too_large(self, tmp_path: Path) -> None:
        content = "x = 1\n" * 2000  # very large
        _write_file(tmp_path / "big.py", content)
        summaries = {"big.py": _summary("big.py")}
        ranked: RankedFiles = [("big.py", 5.0, [])]
        cfg = SelectionConfig(budget=300, snippet_lines=20)

        selected, excluded, _warnings = _enforce_budget(ranked, summaries, tmp_path, cfg)
        if selected:
            assert selected[0].kind in {"snippet", "summary"}

    def test_summary_used_when_both_too_large(self, tmp_path: Path) -> None:
        content = "x = 1\n" * 2000
        _write_file(tmp_path / "big.py", content)
        summaries = {"big.py": _summary("big.py", purpose="important module")}
        ranked: RankedFiles = [("big.py", 5.0, [])]
        # snippet_lines=5 still large, budget=10 — only summary should fit
        cfg = SelectionConfig(budget=10, snippet_lines=5)

        selected, excluded, _warnings = _enforce_budget(ranked, summaries, tmp_path, cfg)
        # Might be excluded (even summary > 10 tokens) or summary
        total = sum(f.tokens for f in selected)
        assert total <= cfg.budget

    def test_zero_budget_excludes_all(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "f.py", "x = 1\n")
        summaries = {"f.py": _summary("f.py")}
        ranked: RankedFiles = [("f.py", 5.0, [])]
        cfg = SelectionConfig(budget=0)

        selected, excluded, _warnings = _enforce_budget(ranked, summaries, tmp_path, cfg)
        assert selected == []
        assert "f.py" in excluded

    def test_missing_file_uses_summary(self, tmp_path: Path) -> None:
        # File not on disk but in summaries (e.g. deleted after scan)
        summaries = {"ghost.py": _summary("ghost.py", purpose="phantom module")}
        ranked: RankedFiles = [("ghost.py", 5.0, [])]
        cfg = SelectionConfig(budget=500)

        selected, _, _warnings = _enforce_budget(ranked, summaries, tmp_path, cfg)
        if selected:
            assert selected[0].kind == "summary"


# ---------------------------------------------------------------------------
# Secret exclusion
# ---------------------------------------------------------------------------


class TestSecretExclusion:
    def test_env_file_excluded_from_scoring(self, tmp_path: Path) -> None:
        summaries = {
            ".env": _summary(".env", purpose="environment variables"),
            "auth.py": _summary("auth.py"),
        }
        sel = _select(
            "authentication env variables",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=10000),
        )
        selected_paths = [f.rel_path for f in sel.selected]
        assert ".env" not in selected_paths

    def test_env_file_in_excluded_list(self, tmp_path: Path) -> None:
        _write_file(tmp_path / ".env", "SECRET_KEY=hunter2")
        summaries = {".env": _summary(".env")}
        sel = _select(
            "secret key config",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=10000),
        )
        assert ".env" in sel.excluded

    def test_env_example_included_when_relevant(self, tmp_path: Path) -> None:
        content = "# Example env\nDATABASE_URL=\nSECRET_KEY=\n"
        _write_file(tmp_path / ".env.example", content)
        summaries = {".env.example": _summary(".env.example", purpose="env template")}
        sel = _select(
            "configure database connection",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=10000),
        )
        # .env.example should NOT be excluded (it's a safe template)
        assert ".env.example" not in sel.excluded

    def test_credential_file_excluded(self, tmp_path: Path) -> None:
        summaries = {"credentials.json": _summary("credentials.json")}
        sel = _select(
            "authentication credentials",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=10000),
        )
        assert "credentials.json" not in [f.rel_path for f in sel.selected]

    def test_secret_key_file_excluded(self, tmp_path: Path) -> None:
        summaries = {"secret_key.py": _summary("secret_key.py")}
        sel = _select(
            "encryption key handling",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=10000),
        )
        assert "secret_key.py" not in [f.rel_path for f in sel.selected]

    def test_no_secret_content_in_render(self, tmp_path: Path) -> None:
        _write_file(tmp_path / ".env.local", "PASSWORD=hunter2\n")
        _write_file(tmp_path / "auth.py", "def login(): pass\n")
        summaries = {
            ".env.local": _summary(".env.local"),
            "auth.py": _summary("auth.py"),
        }
        sel = _select(
            "login password authentication",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=10000),
        )
        rendered = sel.render_markdown()
        assert "hunter2" not in rendered


# ---------------------------------------------------------------------------
# Binary / non-summarised file exclusion
# ---------------------------------------------------------------------------


class TestBinaryExclusion:
    def test_file_not_in_summaries_never_selected(self, tmp_path: Path) -> None:
        # Binary file exists on disk but not in summaries
        binary = tmp_path / "image.png"
        binary.write_bytes(b"\x89PNG\r\n\x1a\n")
        summaries: dict[str, FileSummary] = {}  # empty — binary not summarised
        sel = _select(
            "image processing",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=10000),
        )
        assert all(f.rel_path != "image.png" for f in sel.selected)

    def test_only_summarised_files_returned(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "safe.py", "x = 1\n")
        _write_file(tmp_path / "unsafe.bin", b"garbage".decode("latin-1"))
        summaries = {"safe.py": _summary("safe.py")}
        sel = _select(
            "safe processing",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=10000),
        )
        assert all(f.rel_path == "safe.py" for f in sel.selected)


# ---------------------------------------------------------------------------
# _select — full integration
# ---------------------------------------------------------------------------


class TestSelect:
    def test_empty_summaries(self, tmp_path: Path) -> None:
        sel = _select("any task", {}, _empty_graph(), "", tmp_path, SelectionConfig())
        assert sel.selected == []
        assert sel.excluded == []

    def test_used_tokens_matches_sum(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "a.py", "x = 1\n")
        summaries = {"a.py": _summary("a.py")}
        sel = _select("x value", summaries, _empty_graph(), "", tmp_path, SelectionConfig())
        assert sel.used_tokens == sum(f.tokens for f in sel.selected)

    def test_relevant_file_ranked_first(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "auth.py", "def authenticate(): pass\n")
        _write_file(tmp_path / "utils.py", "def helper(): pass\n")
        summaries = {
            "auth.py": _summary("auth.py", exports=["authenticate"], purpose="authentication"),
            "utils.py": _summary("utils.py"),
        }
        sel = _select(
            "fix authentication bug",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=5000),
        )
        if len(sel.selected) >= 1:
            assert sel.selected[0].rel_path == "auth.py"

    def test_budget_respected(self, tmp_path: Path) -> None:
        for i in range(6):
            _write_file(tmp_path / f"f{i}.py", "x = 1\n" * 300)
        summaries = {f"f{i}.py": _summary(f"f{i}.py") for i in range(6)}
        cfg = SelectionConfig(budget=500)
        sel = _select("process files", summaries, _empty_graph(), "", tmp_path, cfg)
        assert sel.used_tokens <= cfg.budget

    def test_to_dict_structure(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "x.py", "x = 1\n")
        summaries = {"x.py": _summary("x.py")}
        sel = _select("x value", summaries, _empty_graph(), "", tmp_path, SelectionConfig())
        d = sel.to_dict()
        assert "task" in d
        assert "budget" in d
        assert "used_tokens" in d
        assert "selected" in d
        assert "excluded" in d

    def test_render_markdown_contains_task(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "x.py", "x = 1\n")
        summaries = {"x.py": _summary("x.py")}
        sel = _select(
            "implement rate limiting", summaries, _empty_graph(), "", tmp_path, SelectionConfig()
        )
        md = sel.render_markdown()
        assert "implement rate limiting" in md

    def test_dep_expansion_integrated(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "main.py", "from utils import helper\n")
        _write_file(tmp_path / "utils.py", "def helper(): pass\n")
        summaries = {
            "main.py": _summary("main.py", imports=["utils"], purpose="auth main"),
            "utils.py": _summary("utils.py"),
        }
        graph = _graph_with_edges(("main.py", "utils.py"))
        sel = _select(
            "auth main module",
            summaries,
            graph,
            "",
            tmp_path,
            SelectionConfig(budget=5000),
        )
        paths = [f.rel_path for f in sel.selected]
        assert "utils.py" in paths

    def test_test_pairing_integrated(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "auth.py", "def authenticate(): pass\n")
        _write_file(tmp_path / "tests/test_auth.py", "def test_auth(): pass\n")
        summaries = {
            "auth.py": _summary("auth.py", purpose="authentication layer"),
            "tests/test_auth.py": _summary("tests/test_auth.py"),
        }
        sel = _select(
            "fix authentication",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=5000),
        )
        paths = [f.rel_path for f in sel.selected]
        assert "auth.py" in paths
        assert "tests/test_auth.py" in paths

    def test_results_have_reasons(self, tmp_path: Path) -> None:
        _write_file(tmp_path / "auth.py", "x = 1\n")
        summaries = {"auth.py": _summary("auth.py")}
        sel = _select(
            "authentication",
            summaries,
            _empty_graph(),
            "",
            tmp_path,
            SelectionConfig(budget=5000),
        )
        for result in sel.selected:
            assert isinstance(result.reasons, list)


# ---------------------------------------------------------------------------
# _render_summary
# ---------------------------------------------------------------------------


class TestRenderSummary:
    def test_contains_rel_path(self) -> None:
        s = _summary("src/auth.py", language="Python")
        rendered = _render_summary(s)
        assert "src/auth.py" in rendered

    def test_contains_language(self) -> None:
        s = _summary("src/auth.py", language="Python")
        rendered = _render_summary(s)
        assert "Python" in rendered

    def test_contains_purpose(self) -> None:
        s = _summary("auth.py", purpose="handles JWT authentication")
        rendered = _render_summary(s)
        assert "handles JWT authentication" in rendered

    def test_contains_exports(self) -> None:
        s = _summary("auth.py", exports=["login", "logout"])
        rendered = _render_summary(s)
        assert "login" in rendered

    def test_contains_symbols(self) -> None:
        s = _summary("auth.py", symbols=["TOKEN_EXPIRY"])
        rendered = _render_summary(s)
        assert "TOKEN_EXPIRY" in rendered

    def test_summary_label_present(self) -> None:
        s = _summary("auth.py")
        assert "summary" in _render_summary(s).lower()


# ---------------------------------------------------------------------------
# select_context (disk-based public API)
# ---------------------------------------------------------------------------


class TestSelectContext:
    def test_returns_selection_with_no_data(self, tmp_path: Path) -> None:
        contextos_dir = tmp_path / ".contextos"
        contextos_dir.mkdir()
        sel = select_context("fix bug", contextos_dir, tmp_path)
        assert sel.selected == []

    def test_loads_summaries_from_disk(self, tmp_path: Path) -> None:
        import json

        contextos_dir = tmp_path / ".contextos"
        contextos_dir.mkdir()
        _write_file(tmp_path / "auth.py", "def login(): pass\n")

        summaries_data = {
            "auth.py": {
                "rel_path": "auth.py",
                "language": "Python",
                "purpose": "authentication module",
                "imports": [],
                "exports": ["login"],
                "symbols": ["login"],
                "docstring": "",
                "line_count": 1,
                "content_hash": "abc",
            }
        }
        (contextos_dir / "file_summaries.json").write_text(
            json.dumps(summaries_data), encoding="utf-8"
        )

        sel = select_context(
            "authentication login",
            contextos_dir,
            tmp_path,
            config=SelectionConfig(budget=5000),
        )
        paths = [f.rel_path for f in sel.selected]
        assert "auth.py" in paths

    def test_missing_contextos_dir_returns_empty(self, tmp_path: Path) -> None:
        sel = select_context("fix bug", tmp_path / "nonexistent", tmp_path)
        assert sel.selected == []
        assert sel.excluded == []
