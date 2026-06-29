# MCP Setup — ContextOS

## Installed MCP Servers

| Server | Command | Scope | Purpose |
|--------|---------|-------|---------|
| `headroom` | `/Users/rohithmatam/.headroom-venv/bin/headroom mcp serve` | User-global (`~/.mcp.json`) | Token compression / CCR retrieve |
| `filesystem-contextos` | `node .../server-filesystem/dist/index.js /Users/rohithmatam/ContextOS` | User-global (`~/.mcp.json`) | Filesystem access for ContextOS only |

## Exact Commands Used

### Headroom MCP (token savings)

```bash
# 1. Create venv (Homebrew Python blocks system-wide pip)
python3 -m venv ~/.headroom-venv

# 2. Install base package
~/.headroom-venv/bin/pip install headroom-ai

# 3. Install MCP extra (adds mcp, uvicorn, starlette, etc.)
~/.headroom-venv/bin/pip install 'headroom-ai[mcp]'

# 4. Run headroom's installer (writes via `claude mcp add` CLI)
~/.headroom-venv/bin/headroom mcp install --agent claude
# → installs with bare `headroom mcp serve` (no full path)
# This CONFLICTS with the full-path entry in ~/.mcp.json — remove it:
claude mcp remove headroom -s user

# 5. Filesystem MCP server (requires Node >= 18)
source ~/.nvm/nvm.sh && nvm use 22
npm install -g @modelcontextprotocol/server-filesystem
# Binary: ~/.nvm/versions/node/v22.14.0/bin/mcp-server-filesystem
```

### Config files written

**`~/.mcp.json`** — both servers (user-global, picked up in all projects):
```json
{
  "mcpServers": {
    "headroom": {
      "type": "stdio",
      "command": "/Users/rohithmatam/.headroom-venv/bin/headroom",
      "args": ["mcp", "serve"]
    },
    "filesystem-contextos": {
      "type": "stdio",
      "command": "/Users/rohithmatam/.nvm/versions/node/v22.14.0/bin/node",
      "args": [
        "/Users/rohithmatam/.nvm/versions/node/v22.14.0/lib/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js",
        "/Users/rohithmatam/ContextOS"
      ]
    }
  }
}
```

**`~/.claude/settings.json`** — pre-approves both servers (skips interactive prompt):
```json
{
  "enabledMcpjsonServers": ["headroom", "filesystem-contextos"]
}
```

## Allowed Directories

`filesystem-contextos` is granted access to **exactly one directory**:

```
/Users/rohithmatam/ContextOS
```

Not accessible via this MCP server:
- `~` (home directory)
- `~/Downloads`, `~/Desktop`, `~/Documents`
- `~/.ssh`, `~/.aws`, `~/.env` files
- `/` or any other path

## Available MCP Tools

### Headroom tools (require proxy running)

These tools appear as `mcp__headroom__<name>` in Claude Code:

| Tool | When available | Purpose |
|------|---------------|---------|
| `headroom_retrieve` | Proxy running | Retrieve compressed content by hash |
| `headroom_compress` | Proxy running | Compress a block of text manually |
| `headroom_stats` | Proxy running | Show proxy compression stats |

> **Note:** Headroom tools only function when the proxy is active:
> `~/.headroom-venv/bin/headroom proxy`
> The MCP server itself starts without the proxy but retrieve calls will fail.

### Filesystem tools (always available)

These tools appear as `mcp__filesystem-contextos__<name>`:

| Tool | Description |
|------|-------------|
| `read_file` | Read a file inside ContextOS |
| `write_file` | Write a file inside ContextOS |
| `list_directory` | List directory contents |
| `create_directory` | Create a directory |
| `move_file` | Move/rename a file |
| `search_files` | Search by pattern |
| `get_file_info` | Stat a file |

All paths are validated by the server — requests outside `/Users/rohithmatam/ContextOS` are rejected with ENOENT.

## Verifying the Setup

```bash
# Authoritative check — shows all MCP servers and health:
claude mcp list

# Expected output includes:
#   headroom: ... - ✓ Connected  (only when proxy is running)
#   filesystem-contextos: ... - ✓ Connected
```

> `headroom mcp status` is unreliable for this setup. It only checks `~/.claude/mcp.json`
> and `~/.claude/.claude.json`, not `~/.mcp.json`. Use `claude mcp list` instead.

## Security Risks

### filesystem-contextos
- **Write access to ContextOS:** The MCP server can create, overwrite, and delete files in `/Users/rohithmatam/ContextOS`. A compromised or malicious Claude session could overwrite project files.
- **Path traversal:** The official `@modelcontextprotocol/server-filesystem` rejects paths outside the allowed directory, but this relies on the correctness of that library.
- **Mitigation:** Access is limited to a single project directory with no sensitive data. Do not add `~`, `/`, or credential directories.

### headroom MCP
- **Proxy traffic:** When the proxy is running, all Anthropic API requests route through it. Headroom reads and rewrites conversation content to compress tokens.
- **Local only:** Proxy binds to `127.0.0.1:8787` by default — not exposed to the network.
- **Log risk:** `headroom proxy --log-messages` logs full request content. Default is off; do not enable without understanding this.

### General MCP risks
- MCP servers run as child processes with the same OS user as Claude Code.
- `enabledMcpjsonServers` auto-approves servers on start — removing a server name from this list re-triggers the approval prompt.

## How to Disable MCP

### Disable a single server

```bash
# Remove from ~/.mcp.json by editing it, then remove from approval list:
# In ~/.claude/settings.json, remove the server name from enabledMcpjsonServers
```

### Disable all MCP

```bash
# Remove or rename ~/.mcp.json
mv ~/.mcp.json ~/.mcp.json.disabled

# Or run claude with --no-mcp flag (if supported)
```

### Disable headroom proxy only (keep MCP tools)

Stop the proxy process. The MCP server will still start but `headroom_retrieve` calls will fail gracefully.

## How ContextOS Will Use MCP Safely

1. **`filesystem-contextos`** — used for file I/O operations within the project. No path outside `/Users/rohithmatam/ContextOS` is ever passed.

2. **`headroom` MCP** — used passively. The proxy intercepts and compresses large tool outputs (file listings, search results). Claude calls `headroom_retrieve` only when it needs full content that was compressed.

3. **No secrets in ContextOS:** Credentials, API keys, and `.env` files must not be placed in `/Users/rohithmatam/ContextOS`. Use environment variables or a secrets manager.

4. **Proxy optional:** All ContextOS functionality works without the Headroom proxy. Run `ANTHROPIC_BASE_URL=http://127.0.0.1:8787 claude` or `headroom wrap claude` only when token savings are needed.

## Known Limitations

| Issue | Detail |
|-------|--------|
| `headroom-ai[all]` fails | `hnswlib` won't compile against Xcode clang on arm64/Python 3.13. Vector semantic caching unavailable. |
| `headroom mcp status` false negative | Checks `~/.claude/mcp.json` only; our config is in `~/.mcp.json`. Ignore it. |
| Node version | System default is Node 16. Filesystem MCP requires Node 18+. Must use NVM v22 binary path explicitly in config. |
