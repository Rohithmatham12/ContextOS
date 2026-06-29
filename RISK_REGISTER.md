# ContextOS — Risk Register

Format: **ID | Risk | Likelihood | Impact | Mitigation | Status**

---

## Technical Risks

### R-001 | Token count inaccuracy causes budget overruns

**Likelihood:** High  
**Impact:** Medium — agent receives more tokens than expected, context window exceeded  
**Mitigation:**
- Priority chain: tiktoken model-specific → tiktoken cl100k_base → len//4
- Report `counter_method` in all output so consumers know accuracy level
- Add 5% safety margin option (`--budget-margin 0.05`)
- Benchmark fallback method against tiktoken on fixture repos; document max error rate

**Status:** Open — implement in T-021

---

### R-002 | Binary file detection fails, large binary injected into context

**Likelihood:** Medium  
**Impact:** High — corrupted output, agent errors, wasted tokens  
**Mitigation:**
- Null-byte check on first 8 KB of every file before reading full content
- Extension blocklist: `.png`, `.jpg`, `.pdf`, `.zip`, `.whl`, `.so`, `.dylib`, etc.
- Size limit: skip files > 512 KB regardless of type
- Test with fixture containing a binary file — assert it is excluded

**Status:** Open — implement in T-011

---

### R-003 | `.gitignore` parsing diverges from Git spec, includes/excludes wrong files

**Likelihood:** Medium  
**Impact:** Medium — wrong files in context, secrets potentially included  
**Mitigation:**
- Use `gitignore-parser` library (battle-tested) when available
- Fallback simple parser: only handles prefix globs and exact paths
- Always exclude `.git/`, `.env`, `.env.*` as hardcoded rules (belt-and-suspenders)
- Document parser limitations in MVP; full spec in v0.2

**Status:** Open — implement in T-011

---

### R-004 | Ranker keyword scoring is too naive, irrelevant chunks selected

**Likelihood:** High  
**Impact:** Medium — context pack is less useful, user trust erodes  
**Mitigation:**
- Stop-word stripping reduces noise (common words like "the", "add", "in")
- Symbol name matching adds precision signal
- Import centrality rewards files that are structurally important
- User can adjust weights via `--strategy-file` in v0.3
- Ship benchmark: compare keyword-ranked vs. random vs. full-file on real tasks

**Status:** Accepted for MVP — improve in v0.2 with AST symbols, v0.3 with embeddings

---

### R-005 | Determinism broken by OS-specific file ordering

**Likelihood:** Low  
**Impact:** High — output diffs on every run, caching useless, CI flaky  
**Mitigation:**
- Always `sorted(path.rglob(...))` — lexicographic, uses `str(rel_path)` as key
- Score tie-break: `(rel_path, start_line)` — stable across runs
- Determinism integration test (T-064): run twice, diff output bytes

**Status:** Open — enforce in T-011, verify in T-064

---

### R-006 | Headroom proxy unreachable causes silent empty output

**Likelihood:** Medium  
**Impact:** High — user gets empty or uncommunicated failure  
**Mitigation:**
- `HeadroomCompressor` checks proxy health before sending (GET `/livez`)
- On failure: log warning, return original bundle unchanged — never silently empty
- `--compress` flag explicitly opts in; absence means compression is never attempted
- Report `compression_ratio: 1.0` and `compressed: false` in JSON output when fallback

**Status:** Open — implement in T-102

---

### R-007 | Path traversal: `--out` writes outside declared repo root

**Likelihood:** Low  
**Impact:** High — arbitrary file write vulnerability  
**Mitigation:**
- `--out` accepts any path (writing outside repo is legitimate use case)
- Source repo is read-only: never write inside `repo_root` unless explicitly `--out` points there
- Resolve all `--out` paths to absolute before opening for write
- No `..` traversal in internal chunk paths

**Status:** Open — validate in T-050

---

## Adoption Risks

### R-008 | Competitors with embedding-based selection make keyword ranking obsolete

**Likelihood:** Medium  
**Impact:** Medium — ContextOS perceived as less accurate  
**Mitigation:**
- Roadmap includes embedding ranking (v1.0, opt-in, local model)
- Keyword ranking is transparent and debuggable — a feature, not a bug
- Determinism is a competitive advantage that embedding-based tools lack
- Ship benchmark showing keyword ranking is "good enough" for common tasks

**Status:** Accepted — monitor ecosystem

---

### R-009 | Output format drift: Claude/Codex change their expected context format

**Likelihood:** Medium  
**Impact:** Low–Medium — exported context no longer optimal for agent  
**Mitigation:**
- Exporter layer is thin and easy to update
- Each exporter has tests; format changes caught by test failures
- JSON format is format-agnostic — power users can transform it themselves
- Track upstream format docs in ROADMAP.md

**Status:** Accepted — update exporters as needed

---

### R-010 | Open-source repo contains a `.env` or secret in fixture files

**Likelihood:** Low  
**Impact:** High — public exposure of credentials  
**Mitigation:**
- Fixture repos in `tests/fixtures/` contain only synthetic data
- Pre-commit hook: `gitleaks` or `detect-secrets` scan
- CI step: secret scanning before publish
- `.gitignore` in project root excludes `.env`, `.env.*`, `*.pem`, `*.key`

**Status:** Open — add to CI in T-005

---

### R-011 | `tree-sitter` grammar licensing incompatible with MIT

**Likelihood:** Low  
**Impact:** High — legal blocker for v0.2  
**Mitigation:**
- Audit tree-sitter language grammar licenses before v0.2
- Most are MIT or Apache 2.0; document findings in `LICENSES/`
- If incompatible, implement regex-based symbol extraction as fallback

**Status:** Open — audit before v0.2

---

## Operational Risks

### R-012 | Large repos (100k+ files) make scanning too slow for interactive use

**Likelihood:** Medium  
**Impact:** Medium — poor UX for monorepos  
**Mitigation:**
- Default `--max-files 5000` limit (configurable)
- Progress bar via Typer's Rich integration
- Bundle caching (mtime-based) in v0.3 eliminates re-scan cost
- Document expected performance: target < 5 seconds for 1000-file repo

**Status:** Open — benchmark in T-063, cache in T-104

---

### R-013 | Windows path separator breaks rel_path comparisons

**Likelihood:** Medium (if Windows users exist)  
**Impact:** Medium — determinism broken, path lookups fail  
**Mitigation:**
- Always use `pathlib.Path` — never string concatenation
- Use `rel_path.as_posix()` for sorting and display
- CI matrix includes Windows runner in v1.0

**Status:** Deferred — Windows pass in v1.0
