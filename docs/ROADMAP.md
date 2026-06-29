# Roadmap

## v0.1 — MVP (shipped)

Goal: working CLI that produces useful context packs, no optional dependencies required.

- [x] `FileResult`, `ContextSelection` data models
- [x] `RepoWalker` — gitignore-aware directory walk, binary detection
- [x] `LanguageClassifier` — extension-based, Python + JS/TS + Go + Rust priority
- [x] File summarizer → `file_summaries.json`
- [x] `DependencyGraph` — static import analysis → `dependency_graph.json`
- [x] `ContextSelector` — keyword + import-centrality ranking, greedy budget fill
- [x] `PackBuilder` — Markdown and JSON output
- [x] Exporters: `claude`, `codex`, `cursor`, `aider`
- [x] `SecretDetector` — 14 content patterns, filename exclusion, value-only redaction
- [x] Headroom integration (`--compress headroom`, `HeadroomCompressionProvider`)
- [x] Typer CLI: `init`, `scan`, `task`, `pack`, `export`, `memory` commands
- [x] Example projects: `python_fastapi`, `react_typescript`, `monorepo`
- [x] Test suite: 930 tests, 96% coverage
- [x] `pyproject.toml`, Apache-2.0 license, GitHub Actions CI

---

## v0.2 — AST Intelligence (planned)

Goal: chunk and rank at symbol level, not file level.

- [ ] `tree-sitter` integration (Python, TypeScript, Go)
- [ ] `SymbolExtractor` — function/class/method names from AST
- [ ] `GraphBuilder` — import graph with symbol-level edges
- [ ] AST-mode chunker — function/class chunks, not fixed windows
- [ ] Import centrality weighted by symbol call frequency
- [ ] `contextos graph` CLI command — visualise dependency graph
- [ ] Budget enforcement per-chunk instead of per-file

**Why this matters:** File-level ranking includes the entire file even when only one function is relevant. Symbol-level chunking lets ContextOS include `auth.verify_token()` without pulling in the rest of `auth.py`.

---

## v0.3 — Multi-Format and DX (planned)

Goal: complete the exporter set, add `--diff` mode, and project-level config.

- [ ] `--diff <commit>` — include only changed files + their dependents
- [ ] `--format all` — export all formats in one pass
- [ ] `contextos init` — create `.contextos.toml` with project-level defaults
- [ ] Project-level config: default budget, default format, exclude patterns
- [ ] Bundle caching: skip re-scan if repo unchanged (mtime-based)
- [ ] `balanced` budget mode — spread tokens across more files at lower depth
- [ ] Pre-commit hook template

---

## v0.4 — Token Accuracy and CI (planned)

Goal: accurate token counting by model, CI integration, VS Code extension stub.

- [ ] `tiktoken` integration with model-specific tokenizers (gpt-4o, claude-3-5, etc.)
- [ ] `--model <name>` flag — select tokenizer for budget computation
- [ ] GitHub Action: `contextos pack` on PR open, post summary as comment
- [ ] VS Code extension stub: calls `contextos pack` on save, shows token count in status bar
- [ ] Windows compatibility pass
- [ ] Benchmark suite: token efficiency vs. naive full-repo dump

---

## v1.0 — Stable API (future)

Goal: stable public API, plugin system, broad adoption.

- [ ] Python SDK: `from contextos import pack` — importable, not only CLI
- [ ] Plugin system for exporters and rankers (entry points)
- [ ] Embedding-based ranking (local model, opt-in, no cloud)
- [ ] `--watch` mode — re-pack on file change
- [ ] Comprehensive docs site (MkDocs Material)
- [ ] 1.0 release announcement, changelog, migration guide

---

## Out of Scope (Explicit Non-Goals)

These will not be added regardless of demand. They contradict the core design.

| Non-goal | Reason |
|----------|--------|
| Cloud context storage | Contexts may contain sensitive code |
| Context sharing between users | Same concern |
| LLM calls during selection | Defeats the point; adds cost and latency |
| Executing repo code during analysis | Safety risk, unpredictable side effects |
| Paid features | ContextOS is Apache-2.0 and will stay that way |
| Telemetry or analytics | No accounts, no tracking |
| IDE integration beyond VS Code stub | Scope creep; community can build plugins |

---

## Contributing to the Roadmap

Open an issue or start a discussion at https://github.com/Rohithmatham12/ContextOS/issues.

Feature requests that align with a planned milestone are the most likely to be accepted. Requests that contradict the non-goals listed above will be declined clearly.
