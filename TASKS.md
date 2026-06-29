# ContextOS — MVP Tasks

Ordered by dependency. Complete in sequence within each phase.

## Phase 0 — Project Skeleton

- [ ] **T-001** Create `pyproject.toml` with Typer + pytest dependencies, MIT license, Python 3.11+ constraint
- [ ] **T-002** Create `contextos/__init__.py` with version string
- [ ] **T-003** Create `contextos/models.py` with `FileNode`, `ChunkNode`, `RepoGraph`, `ContextBundle`, `CompressedBundle`
- [ ] **T-004** Create `tests/` directory with `conftest.py` and two fixture repos:
  - `tests/fixtures/simple_py/` — 3–5 Python files with known import structure
  - `tests/fixtures/mixed/` — Python + JS files, includes `.gitignore`
- [ ] **T-005** Set up GitHub Actions CI: lint (ruff), type check (mypy), test (pytest)

## Phase 1 — Scanner

- [ ] **T-010** `scanner/classifier.py` — `LanguageClassifier.classify(path) -> str`
  - Extension map: `.py` → python, `.ts/.tsx` → typescript, `.js/.jsx` → javascript, `.go` → go, `.rs` → rust, `.md` → markdown
  - Shebang fallback for extensionless files
  - Tests: known extensions, unknown extension returns `"unknown"`, shebang detection

- [ ] **T-011** `scanner/walker.py` — `RepoWalker.walk(root: Path) -> list[FileNode]`
  - Reads `.gitignore` in root (simple prefix/glob matching; full spec in v0.2)
  - Skips: `.git/`, `__pycache__/`, `node_modules/`, `*.pyc`, binary files (null byte detection)
  - Skips files > 512 KB
  - Returns `sorted(files, key=lambda f: f.rel_path)` for determinism
  - Tests: gitignore respected, binary skipped, large file skipped, sort order stable

- [ ] **T-012** `scanner/index.py` — `FileIndex` wrapper
  - `by_language(lang) -> list[FileNode]`
  - `by_glob(pattern) -> list[FileNode]`
  - `stats() -> dict` — file count, total tokens, language breakdown
  - Tests: lookup by language, glob filtering, stats accuracy

- [ ] **T-013** Wire `scanner/` into `cli.py` — `contextos scan <repo>` prints stats table

## Phase 2 — Chunker

- [ ] **T-020** `intelligence/chunker.py` — `Chunker.chunk(file: FileNode) -> list[ChunkNode]`
  - Line mode only (AST in v0.2)
  - Window size: 50 lines, overlap: 10 lines, min chunk: 5 lines
  - Whole-file chunk if file ≤ 60 lines
  - `chunk_type = "block"`, `name = None` in line mode
  - Tests: small file → 1 chunk, large file → multiple overlapping chunks, token sum ≈ file tokens

- [ ] **T-021** `intelligence/token_counter.py` — `count_tokens(text: str) -> int`
  - Try `tiktoken.encoding_for_model("gpt-4o")` → use `cl100k_base` if model unknown → fallback `len(text) // 4`
  - Exposes `COUNTER_METHOD: str` constant describing which method is active
  - Tests: determinism (same input → same count), fallback activates without tiktoken

## Phase 3 — Selector

- [ ] **T-030** `selector/ranker.py` — `Ranker.rank(chunks: list[ChunkNode], task: str) -> list[ChunkNode]`
  - Keyword signal: tokenize task, count overlapping words in chunk content (case-insensitive, stop-word stripped)
  - Symbol signal: check if any task word matches a known symbol name (stub: extract capitalized identifiers from content via regex)
  - Normalize scores to [0.0, 1.0]
  - Return sorted descending by score; tie-break: `(rel_path, start_line)`
  - Tests: higher score for chunks containing task keywords, tie-break is stable

- [ ] **T-031** `selector/budget.py` — `BudgetEnforcer.select(ranked: list[ChunkNode], budget: int) -> list[ChunkNode]`
  - Greedy fill: add chunks in score order until `total_tokens + chunk.tokens > budget`
  - Never truncates a chunk (partial chunks not allowed in MVP)
  - Raises `ValueError` if even the highest-scored chunk exceeds budget
  - Tests: token sum ≤ budget, no partial chunks, ValueError on impossible budget

- [ ] **T-032** `selector/strategy.py` — `SelectionStrategy` enum + `apply(strategy, chunks, task, budget) -> ContextBundle`
  - `DEFAULT`: Ranker + greedy BudgetEnforcer
  - Returns `ContextBundle` with metadata

## Phase 4 — Exporters

- [ ] **T-040** `exporter/base.py` — `BaseExporter` abstract class with `render(bundle) -> str` and `filename() -> str`

- [ ] **T-041** `exporter/markdown.py` — `MarkdownExporter`
  - Header: task + token stats
  - Each chunk: ` ```language\n<path>:<start>-<end>\n<content>\n``` `
  - Footer: counter method note
  - Tests: valid markdown structure, all chunks present, token count in header

- [ ] **T-042** `exporter/xml.py` — `XmlExporter`
  - `<context task="..." tokens="..." budget="...">`
  - `<file path="..." language="..." lines="start-end">...</file>`
  - Well-formed XML (validate with `xml.etree.ElementTree.fromstring`)
  - Tests: parseable, all chunks present

- [ ] **T-043** `exporter/claude.py` — `ClaudeExporter`
  - Task preamble in plain text above XML blocks
  - XML block per chunk (same as XmlExporter)
  - Appends `<counter_method>` note
  - Tests: preamble present, XML parseable

- [ ] **T-044** `exporter/json_.py` — `JsonExporter`
  - `json.dumps` with `indent=2`, `sort_keys=True` for determinism
  - Schema: `{task, repo_root, strategy, total_tokens, budget, counter_method, chunks: [{path, language, start_line, end_line, tokens, score, content}]}`
  - Tests: valid JSON, schema fields present, `sort_keys=True` makes output deterministic

## Phase 5 — CLI Integration

- [ ] **T-050** `cli.py` — `contextos pack` command
  - Args: `repo: Path`, `--task: str`, `--budget: int = 8000`, `--format: str = "md"`, `--out: Path | None`
  - Runs full pipeline: walk → chunk → rank → select → export
  - Prints to stdout if no `--out`; writes file if `--out` given
  - Tests: CLI invocation via `typer.testing.CliRunner`, output contains task string

- [ ] **T-051** Help text and `--version` flag

- [ ] **T-052** Error handling: repo not found, budget too small, format unknown — all exit 1 with clean message

## Phase 6 — Quality

- [ ] **T-060** Coverage gate: `pytest --cov=contextos --cov-fail-under=80`
- [ ] **T-061** `ruff check` + `ruff format --check` in CI — zero tolerance
- [ ] **T-062** `mypy --strict contextos/` in CI
- [ ] **T-063** End-to-end test: run `contextos pack tests/fixtures/simple_py --task "add logging" --budget 4000` — assert output is valid markdown and token count ≤ 4000
- [ ] **T-064** Determinism test: run same command twice, assert byte-identical output (with `--no-timestamp`)

## Blocked / Future

- **T-100** AST chunker (needs tree-sitter) — v0.2
- **T-101** Import graph builder — v0.2
- **T-102** Headroom compressor integration — v0.3
- **T-103** Cursor + Aider exporters — v0.3
- **T-104** Bundle caching — v0.3
