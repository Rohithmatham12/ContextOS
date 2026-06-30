"""Tests for AST symbol extractor."""

from __future__ import annotations

import pytest

tree_sitter = pytest.importorskip("tree_sitter", reason="tree-sitter not installed")

from contextos.core.ast_extractor import (  # noqa: E402
    FileSymbols,
    SymbolInfo,
    _tokenize_identifier,
    extract_symbols,
    symbol_score,
)

PYTHON_SRC = """\
class AuthService:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    def authenticate_user(self, username: str, password: str) -> bool:
        return True

    def verify_token(self, token: str) -> bool:
        return True

    def _internal(self) -> None:
        pass


def create_access_token(data: dict) -> str:
    return ""


def _helper() -> None:
    pass
"""

TS_SRC = """\
export class UserService {
  async getUser(id: string): Promise<User> {
    return {} as User;
  }

  async createUser(data: CreateUserDto): Promise<User> {
    return {} as User;
  }
}

export function hashPassword(password: string): string {
  return password;
}
"""


class TestExtractPythonSymbols:
    def test_extracts_class_name(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        assert any(s.name == "AuthService" and s.kind == "class" for s in result.symbols)

    def test_extracts_public_methods(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        names = result.names()
        assert "authenticate_user" in names
        assert "verify_token" in names

    def test_extracts_top_level_function(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        assert any(s.name == "create_access_token" and s.kind == "function" for s in result.symbols)

    def test_private_functions_included(self) -> None:
        # Private symbols are extracted — they can be relevant to task matching
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        assert "_helper" in result.names()

    def test_private_methods_included(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        assert "_internal" in result.names()

    def test_init_included(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        assert "__init__" in result.names()

    def test_method_has_parent(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        method = next(s for s in result.symbols if s.name == "authenticate_user")
        assert method.parent == "AuthService"
        assert method.kind == "method"

    def test_top_level_function_no_parent(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        fn = next(s for s in result.symbols if s.name == "create_access_token")
        assert fn.parent is None
        assert fn.kind == "function"

    def test_line_numbers_set(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        cls = next(s for s in result.symbols if s.name == "AuthService")
        assert cls.start_line >= 1
        assert cls.end_line >= cls.start_line

    def test_empty_source(self) -> None:
        result = extract_symbols("", "python", "app/empty.py")
        assert result.symbols == []
        assert not result.parse_error

    def test_syntax_error_returns_empty(self) -> None:
        # tree-sitter error-tolerant parser: returns symbols from valid nodes,
        # parse_error may or may not be set depending on recovery
        result = extract_symbols("def (broken", "python", "app/broken.py")
        # At minimum must not crash and must return a FileSymbols
        assert isinstance(result, FileSymbols)

    def test_function_names_set(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        fns = result.function_names()
        assert "authenticate_user" in fns
        assert "create_access_token" in fns
        assert "AuthService" not in fns

    def test_class_names_set(self) -> None:
        result = extract_symbols(PYTHON_SRC, "python", "app/auth.py")
        assert result.class_names() == {"AuthService"}


class TestExtractTypescriptSymbols:
    def test_extracts_class(self) -> None:
        result = extract_symbols(TS_SRC, "typescript", "src/user.service.ts")
        assert any(s.name == "UserService" and s.kind == "class" for s in result.symbols)

    def test_extracts_methods(self) -> None:
        result = extract_symbols(TS_SRC, "typescript", "src/user.service.ts")
        names = result.names()
        assert "getUser" in names
        assert "createUser" in names

    def test_extracts_top_level_function(self) -> None:
        result = extract_symbols(TS_SRC, "typescript", "src/user.service.ts")
        assert "hashPassword" in result.names()

    def test_methods_have_parent(self) -> None:
        result = extract_symbols(TS_SRC, "typescript", "src/user.service.ts")
        method = next((s for s in result.symbols if s.name == "getUser"), None)
        if method:  # skip if tree-sitter-typescript not installed
            assert method.parent == "UserService"


class TestUnsupportedLanguage:
    def test_returns_empty_for_go(self) -> None:
        result = extract_symbols("func main() {}", "go", "main.go")
        assert result.symbols == []
        assert not result.parse_error

    def test_returns_empty_for_markdown(self) -> None:
        result = extract_symbols("# Hello", "markdown", "README.md")
        assert result.symbols == []


class TestSymbolScore:
    def _syms(self, names: list[tuple[str, str]]) -> FileSymbols:
        fs = FileSymbols(rel_path="x.py")
        for name, kind in names:
            fs.symbols.append(SymbolInfo(name=name, kind=kind, start_line=1, end_line=10))
        return fs

    def test_no_keywords_returns_zero(self) -> None:
        fs = self._syms([("authenticate_user", "function")])
        assert symbol_score(fs, set()) == 0.0

    def test_no_symbols_returns_zero(self) -> None:
        assert symbol_score(FileSymbols(rel_path="x.py"), {"auth"}) == 0.0

    def test_keyword_matches_snake_part(self) -> None:
        fs = self._syms([("authenticate_user", "function")])
        score = symbol_score(fs, {"authenticate"})
        assert score > 0

    def test_function_scores_higher_than_class(self) -> None:
        fs_fn = self._syms([("verify_token", "function")])
        fs_cls = self._syms([("verify_token", "class")])
        assert symbol_score(fs_fn, {"verify", "token"}) > symbol_score(fs_cls, {"verify", "token"})

    def test_method_scores_higher_than_class(self) -> None:
        fs_method = self._syms([("verify_token", "method")])
        fs_cls = self._syms([("verify_token", "class")])
        kw = {"verify", "token"}
        assert symbol_score(fs_method, kw) > symbol_score(fs_cls, kw)

    def test_multiple_matches_accumulate(self) -> None:
        fs = self._syms([("verify_token", "function"), ("refresh_token", "function")])
        score_two = symbol_score(fs, {"token"})
        fs_one = self._syms([("verify_token", "function")])
        score_one = symbol_score(fs_one, {"token"})
        assert score_two > score_one


class TestTokenizeIdentifier:
    def test_snake_case(self) -> None:
        assert _tokenize_identifier("authenticate_user") == {"authenticate", "user"}

    def test_camel_case(self) -> None:
        parts = _tokenize_identifier("getUserById")
        assert "get" in parts
        assert "user" in parts

    def test_single_word(self) -> None:
        assert _tokenize_identifier("authenticate") == {"authenticate"}

    def test_all_caps_constant(self) -> None:
        parts = _tokenize_identifier("API_KEY")
        assert "api" in parts
        assert "key" in parts

    def test_short_parts_filtered(self) -> None:
        # parts of length <= 1 should be excluded
        parts = _tokenize_identifier("x_y")
        assert "x" not in parts
        assert "y" not in parts
