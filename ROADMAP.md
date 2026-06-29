# ContextOS Roadmap

## MVP — v0.1 (current target)

Goal: working CLI that produces useful context packs from Python repos, no optional deps required.

- [ ] `FileNode`, `ChunkNode`, `ContextBundle` data models
- [ ] `RepoWalker` — gitignore-aware directory walk, binary detection
- [ ] `LanguageClassifier` — extension-based, Python + JS/TS + Go + Rust priority
- [ ] `FileIndex` — ordered, lookup helpers
- [ ] `Chunker` (line mode only) — fixed-window with overlap
- [ ] `Ranker` — keyword + symbol weight scoring, no embeddings
- [ ] `BudgetEnforcer` — greedy fill, token count from fallback chain
- [ ] `MarkdownExporter` — fenced code blocks
- [ ] `JSONExporter` — structured metadata + chunks
- [ ] `ClaudeExporter` — XML blocks with task preamble
- [ ] Typer CLI: `scan`, `pack` commands
- [ ] `pytest` suite with fixture repos (Python, mixed)
- [ ] `pyproject.toml`, MIT license, GitHub Actions CI

## v0.2 — AST Intelligence

Goal: chunk and rank at symbol level, not line level.

- [ ] `tree-sitter` integration (Python, TypeScript, Go)
- [ ] `SymbolExtractor` — function/class/method names, imports
- [ ] `GraphBuilder` — static import graph, no execution
- [ ] AST-mode `Chunker` — function/class-level chunks
- [ ] Import centrality signal in `Ranker`
- [ ] `contextos graph` CLI command
- [ ] Exporter: `CodexExporter` (AGENTS.md format)
- [ ] Exporter: `AiderExporter`

## v0.3 — Headroom Compression + Multi-Format

Goal: integrate Headroom, complete exporter set, custom strategies.

- [ ] `HeadroomCompressor` — local proxy integration, graceful fallback
- [ ] `CursorExporter` (`.cursorrules` + `context.md`)
- [ ] `--compress` flag wired to `HeadroomCompressor`
- [ ] Custom strategy TOML config (`--strategy-file`)
- [ ] `balanced` budget mode (multi-file spread)
- [ ] Token counting via `tiktoken` with model-specific tokenizer
- [ ] `--format all` — export all formats in one pass
- [ ] Bundle caching: skip re-scan if repo unchanged (mtime-based)

## v0.4 — Developer Experience

Goal: make ContextOS the default context tool for open-source projects.

- [ ] `contextos init` — creates `.contextos.toml` in repo with defaults
- [ ] Project-level config (exclude patterns, default budget, default format)
- [ ] `--diff <commit>` — include only changed files + their dependents
- [ ] Pre-commit hook template
- [ ] VS Code extension stub (calls `contextos pack` on save)
- [ ] GitHub Action: `contextos pack` on PR open, post summary as comment

## v1.0 — Stable API

Goal: stable public API, plugin system, adoption.

- [ ] Python SDK (`from contextos import pack`) — importable, not just CLI
- [ ] Plugin system for exporters and rankers (entry points)
- [ ] Embedding-based ranking (local model, opt-in)
- [ ] `--watch` mode — re-pack on file change
- [ ] Windows compatibility pass
- [ ] Comprehensive docs site (MkDocs)
- [ ] Benchmark suite: token efficiency vs. naive full-repo dump
- [ ] 1.0 release announcement

## Out of Scope (Explicit Non-Goals)

- Cloud context storage or sharing
- Executing repo code during analysis
- LLM calls during context selection (by default)
- IDE integration beyond VS Code stub
- Paid features or telemetry
