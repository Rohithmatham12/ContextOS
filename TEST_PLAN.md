# ContextOS — Test Plan

## Philosophy

- Every public function has at least one unit test
- Integration tests use real fixture repos on disk — no mocking of file system
- No network calls in any test
- Tests must be deterministic: same seed → same output every run
- Coverage gate: 80% minimum for merge; target 90% before v1.0

## Test Layout

```
tests/
├── conftest.py              # shared fixtures (tmp_path, fixture repo paths)
├── fixtures/
│   ├── simple_py/           # 3–5 Python files, known import structure
│   │   ├── main.py
│   │   ├── utils.py
│   │   ├── models.py
│   │   ├── .gitignore       # excludes *.pyc, __pycache__
│   │   └── README.md
│   └── mixed/               # Python + JS + binary, nested dirs
│       ├── src/
│       │   ├── app.py
│       │   └── helpers.js
│       ├── assets/
│       │   └── logo.png     # binary — must be excluded
│       ├── .gitignore       # excludes assets/
│       └── package.json
├── scanner/
│   ├── test_classifier.py
│   ├── test_walker.py
│   └── test_index.py
├── intelligence/
│   ├── test_chunker.py
│   └── test_token_counter.py
├── selector/
│   ├── test_ranker.py
│   ├── test_budget.py
│   └── test_strategy.py
├── exporter/
│   ├── test_markdown.py
│   ├── test_xml.py
│   ├── test_claude.py
│   └── test_json.py
├── cli/
│   ├── test_scan_command.py
│   └── test_pack_command.py
└── integration/
    ├── test_full_pipeline.py
    └── test_determinism.py
```

## Unit Tests

### `scanner/test_classifier.py`

| Test | Assertion |
|------|-----------|
| `.py` → `"python"` | exact match |
| `.ts` → `"typescript"` | exact match |
| `.go` → `"go"` | exact match |
| `.rs` → `"rust"` | exact match |
| `.md` → `"markdown"` | exact match |
| `.xyz` → `"unknown"` | unknown extension |
| `#!/usr/bin/env python3` shebang → `"python"` | shebang detection |
| empty file, no extension → `"unknown"` | graceful fallback |

### `scanner/test_walker.py`

| Test | Assertion |
|------|-----------|
| walks `simple_py/` | returns 5 `FileNode` objects |
| `.gitignore` excludes `*.pyc` | no `.pyc` files in result |
| `assets/logo.png` excluded | binary files excluded |
| `node_modules/` excluded | hardcoded skip |
| file > 512 KB | excluded |
| result order | `sorted(by rel_path)` — stable on repeated calls |
| empty directory | returns empty list, no error |
| non-existent directory | raises `FileNotFoundError` |

### `scanner/test_index.py`

| Test | Assertion |
|------|-----------|
| `by_language("python")` on `mixed/` | returns only `.py` files |
| `by_glob("*.md")` | returns only `.md` files |
| `stats()` | correct file count, correct language breakdown |

### `intelligence/test_chunker.py`

| Test | Assertion |
|------|-----------|
| file ≤ 60 lines → 1 chunk | single chunk, `start_line=0`, `end_line=len(lines)` |
| file 200 lines, window=50, overlap=10 → correct count | `ceil((200-10) / (50-10))` chunks |
| chunk token counts sum to ≈ file tokens | within 15% tolerance (overlap causes duplication) |
| chunks are ordered by `start_line` | ascending |
| every chunk has `tokens > 0` | no empty chunks |
| `chunk_type == "block"` in line mode | always |

### `intelligence/test_token_counter.py`

| Test | Assertion |
|------|-----------|
| same text → same count on repeated calls | deterministic |
| empty string → 0 | edge case |
| `COUNTER_METHOD` is a string and not empty | metadata present |
| without tiktoken (mock import failure) → fallback | `len(text) // 4` |

### `selector/test_ranker.py`

| Test | Assertion |
|------|-----------|
| chunk containing all task words scores higher than chunk with none | strict ordering |
| all scores in [0.0, 1.0] | normalization |
| equal-score chunks broken by `(rel_path, start_line)` | stable tie-break |
| task = `""` → all scores equal | graceful empty task |
| single chunk → score = 1.0 (or 0.0 if no match) | normalization handles edge case |

### `selector/test_budget.py`

| Test | Assertion |
|------|-----------|
| sum of selected chunk tokens ≤ budget | hard budget constraint |
| no partial chunks | chunk either fully included or excluded |
| highest-scoring chunk always selected first | greedy property |
| budget = 0 → empty selection | edge case |
| budget < smallest chunk → `ValueError` | explicit error |
| all chunks fit within budget → all selected | no unnecessary exclusion |

### `selector/test_strategy.py`

| Test | Assertion |
|------|-----------|
| `DEFAULT` strategy returns `ContextBundle` | type check |
| `ContextBundle.total_tokens ≤ budget` | budget enforced |
| `ContextBundle.task` matches input task | metadata propagated |

### `exporter/test_markdown.py`

| Test | Assertion |
|------|-----------|
| output contains task string | task in header |
| output contains each chunk's content | all chunks present |
| fenced code block for each chunk | ` ```lang ` present |
| token count in header matches bundle | accurate reporting |
| `filename()` returns `"context.md"` | correct filename |

### `exporter/test_xml.py`

| Test | Assertion |
|------|-----------|
| output is parseable XML | `ET.fromstring()` succeeds |
| `<context>` root element present | schema |
| one `<file>` element per chunk | all chunks present |
| `path` attribute on `<file>` is a string | attributes present |

### `exporter/test_claude.py`

| Test | Assertion |
|------|-----------|
| preamble (plain text) appears before first XML element | ordering |
| XML is parseable (same as xml exporter test) | valid XML |
| `<counter_method>` element present | metadata |

### `exporter/test_json.py`

| Test | Assertion |
|------|-----------|
| output is valid JSON | `json.loads()` succeeds |
| `chunks` array length = bundle chunk count | all chunks present |
| each chunk has `path`, `tokens`, `score`, `content` | schema |
| `sort_keys=True` makes output byte-identical | determinism |

## CLI Tests

Uses `typer.testing.CliRunner` — no subprocess, no disk I/O outside `tmp_path`.

### `cli/test_scan_command.py`

| Test | Assertion |
|------|-----------|
| `contextos scan tests/fixtures/simple_py` exits 0 | success |
| stdout contains file count | output present |
| `contextos scan /nonexistent` exits 1 | error handling |

### `cli/test_pack_command.py`

| Test | Assertion |
|------|-----------|
| `contextos pack simple_py --task "add logging" --budget 4000` exits 0 | success |
| `--format json` produces valid JSON on stdout | format flag |
| `--out /tmp/out.md` writes file, stdout empty | file output |
| `--budget 1` exits 1 with message about budget too small | budget error |
| `--format invalid` exits 1 with known-formats message | format error |
| `--version` prints version string | version flag |

## Integration Tests

### `integration/test_full_pipeline.py`

Full pipeline run on `simple_py/` fixture:

```python
def test_full_pipeline_simple_py(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, [
        "pack", "tests/fixtures/simple_py",
        "--task", "add error handling",
        "--budget", "4000",
        "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tokens"] <= 4000
    assert data["task"] == "add error handling"
    assert len(data["chunks"]) >= 1
    for chunk in data["chunks"]:
        assert chunk["tokens"] > 0
        assert 0.0 <= chunk["score"] <= 1.0
```

Full pipeline run on `mixed/` fixture:
- Asserts binary file (`logo.png`) not in output
- Asserts gitignored files not in output

### `integration/test_determinism.py`

```python
def test_determinism(tmp_path):
    args = ["pack", "tests/fixtures/simple_py",
            "--task", "add logging",
            "--budget", "4000",
            "--format", "json",
            "--no-timestamp"]
    result1 = runner.invoke(app, args)
    result2 = runner.invoke(app, args)
    assert result1.output == result2.output  # byte-identical
```

## Coverage

Run with:
```bash
pytest --cov=contextos --cov-report=term-missing --cov-fail-under=80
```

Excluded from coverage:
- `contextos/cli.py` main guard (`if __name__ == "__main__"`)
- Optional import fallback branches (tiktoken, tree-sitter) — marked with `# pragma: no cover`

## CI Matrix

```yaml
python-version: ["3.11", "3.12", "3.13"]
os: ["ubuntu-latest", "macos-latest"]
```

Windows added in v1.0.

## Manual Test Checklist (before each release)

- [ ] Run `contextos scan` on this repo (ContextOS itself)
- [ ] Run `contextos pack` with each supported `--format`
- [ ] Verify `--out` writes exactly one file with correct name
- [ ] Run with `--budget 100` and confirm graceful error
- [ ] Run with Headroom proxy running and `--compress` (v0.3+)
- [ ] Diff two identical runs with `--no-timestamp` — confirm zero diff
