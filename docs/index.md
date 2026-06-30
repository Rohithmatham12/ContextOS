# ContextOS

**A context operating system for AI coding agents.**

[![CI](https://github.com/Rohithmatham12/ContextOS/actions/workflows/ci.yml/badge.svg)](https://github.com/Rohithmatham12/ContextOS/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/rm-contextos.svg)](https://pypi.org/project/rm-contextos/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/Rohithmatham12/ContextOS/blob/master/LICENSE)

ContextOS solves the context-window problem for AI coding agents. Instead of dumping your entire codebase into the prompt, it intelligently selects, ranks, and packages the files most relevant to your current task — under a token budget you control.

## Install

```bash
pip install rm-contextos              # base CLI
pip install "rm-contextos[mcp]"       # + MCP server for AI agents
pip install "rm-contextos[all]"       # everything (MCP + AST + headroom)
```

## Quick Start

```bash
cd your-project
contextos init
contextos scan
contextos task "add rate limiting to the auth endpoint"
contextos pack --budget 8000
contextos export --format claude
```

## Why ContextOS?

Most repos are too large to fit in a context window. Naive approaches (dump everything, truncate randomly) waste tokens on irrelevant files and miss critical ones.

ContextOS builds an intelligence layer on top of your repo:

- **Keyword + import graph ranking** — files relevant to your task float to the top
- **AST-level symbol extraction** — matches function/class names, not just grep strings
- **Secret redaction** — 14 pattern types, value-only redaction, never exposes credentials
- **Token-budget enforcement** — greedy selection that fills the budget exactly
- **Multi-format export** — Claude, Codex, Cursor, Aider, JSON

## Features

| Feature | Status |
|---------|--------|
| Gitignore-aware file walk | Shipped |
| Secret detection (14 patterns) | Shipped |
| Keyword + import-graph ranking | Shipped |
| AST symbol extraction (Python, TS, JS) | Shipped |
| Git churn scoring | Shipped |
| Incremental scan cache (hash-based) | Shipped |
| Token budget enforcement | Shipped |
| Token savings report | Shipped |
| Claude / Codex / Cursor / Aider export | Shipped |
| MCP server (6 tools) | Shipped |
| Headroom compression | Shipped |
| tiktoken accurate counting | v0.4 |
| Embedding-based ranking | v1.0 |

## How It Works

```
your repo
    │
    ▼
RepoWalker          ← gitignore-aware, binary detection
    │
    ▼
Summarizer          ← symbols, imports, exports per file
    │
    ▼
DependencyGraph     ← import centrality scores
    │
    ▼
ContextSelector     ← keyword match + centrality → greedy budget fill
    │
    ▼
SecretDetector      ← redact before any output
    │
    ▼
PackBuilder         ← Markdown or JSON context pack
    │
    ▼
Exporter            ← claude / codex / cursor / aider
```

## Links

- [PyPI](https://pypi.org/project/rm-contextos/)
- [GitHub](https://github.com/Rohithmatham12/ContextOS)
- [Issues](https://github.com/Rohithmatham12/ContextOS/issues)
- [Roadmap](ROADMAP.md)
