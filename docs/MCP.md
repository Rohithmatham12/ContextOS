# MCP Server

ContextOS can run as a **Model Context Protocol (MCP) server**, exposing its repo intelligence as callable tools that AI agents can use directly — no CLI commands needed.

## Install

```bash
pip install "rm-contextos[mcp]"
```

## Start the server

**Stdio mode** (for Claude Desktop / Claude Code):
```bash
contextos serve --stdio /path/to/your/project
```

**HTTP mode** (for testing or custom integrations):
```bash
contextos serve --port 8000 /path/to/your/project
```

## Connect to Claude Desktop

Edit `~/.claude/claude_desktop_config.json` (create it if it doesn't exist):

```json
{
  "mcpServers": {
    "contextos": {
      "command": "contextos",
      "args": ["serve", "--stdio", "/absolute/path/to/your/project"]
    }
  }
}
```

Restart Claude Desktop. ContextOS tools will appear automatically.

## Connect to Claude Code (CLI)

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "contextos": {
      "command": "contextos",
      "args": ["serve", "--stdio", "."]
    }
  }
}
```

## Available Tools

### `scan_repo`
Scan a repository and build the intelligence index. Run this first on a new project.

| Argument | Default | Description |
|----------|---------|-------------|
| `repo` | `.` | Path to the repository root |

Subsequent scans are fast — only changed files are re-summarized (incremental cache).

---

### `pack_context`
Select and return a task-relevant context pack. The main tool — use this instead of copying files manually.

| Argument | Default | Description |
|----------|---------|-------------|
| `task` | *(required)* | Plain-English description of what you're working on |
| `budget` | `8000` | Maximum tokens to include |
| `repo` | `.` | Path to the repository root |
| `format` | `md` | Output format: `md` or `json` |

**Example response header:**
```
<!-- ContextOS Pack | task: fix auth bug | 12 files | ~7,998 tokens | saved ~276,000 tokens (97%) vs full repo -->
```

---

### `list_files`
Rank all files by relevance to a task. Useful when you want to understand what's relevant before packing.

| Argument | Default | Description |
|----------|---------|-------------|
| `task` | *(required)* | Task description |
| `top_n` | `20` | Number of files to show |
| `repo` | `.` | Repository root |

**Example output:**
```
#    Score  File                          Reasons
1     2.94  app/auth/middleware.py        path:auth, symbol:verify_token, churn:4commits
2     2.10  app/auth/models.py            path:auth, symbol:User, imports:jwt
```

---

### `get_file`
Read a single file with automatic secret redaction.

| Argument | Default | Description |
|----------|---------|-------------|
| `rel_path` | *(required)* | Relative path from repo root |
| `repo` | `.` | Repository root |

Secret files (`.env`, `*.pem`, `id_rsa`, etc.) are blocked entirely.

---

### `get_summary`
Get the static analysis summary of a file — language, imports, exports, symbols. Much cheaper than reading the full file when you just need to understand what it does.

| Argument | Default | Description |
|----------|---------|-------------|
| `rel_path` | *(required)* | Relative path from repo root |
| `repo` | `.` | Repository root |

---

### `churn_report`
Show the most frequently modified files in recent git history. High-churn files are usually the most actively developed.

| Argument | Default | Description |
|----------|---------|-------------|
| `days` | `30` | How many days of git history to scan |
| `top_n` | `15` | How many files to show |
| `repo` | `.` | Repository root |

---

## Which AI tools support MCP?

MCP is an open protocol — not Claude-only.

| Tool | MCP Support |
|------|-------------|
| Claude Desktop | Native |
| Claude Code | Native |
| Cursor | Built-in |
| Windsurf | Built-in |
| Any MCP SDK client | Compatible |

## Typical agent workflow

Without ContextOS MCP, an agent has to guess which files to read. With it:

```
Agent: "Fix the rate limiting on the auth endpoint"
  → calls pack_context(task="fix rate limiting on auth endpoint")
  → receives: 12 relevant files, secrets redacted, 7,998 tokens
  → gives accurate answer immediately
```
