# FAQ

## Installation

### How do I install ContextOS?

```bash
pip install rm-contextos
```

For all features including MCP server and AST analysis:

```bash
pip install "rm-contextos[all]"
```

---

### What does each install option include?

| Install | What you get |
|---------|-------------|
| `pip install rm-contextos` | Core CLI — pack, scan, export, secret detection |
| `pip install "rm-contextos[mcp]"` | + MCP server (`contextos serve`) |
| `pip install "rm-contextos[ast]"` | + AST symbol extraction for smarter ranking |
| `pip install "rm-contextos[tokens]"` | + tiktoken for accurate token counting |
| `pip install "rm-contextos[headroom]"` | + Headroom compression (shrinks context ~40%) |
| `pip install "rm-contextos[all]"` | Everything above |

---

## Token Budget

### Do I have to manually set 8000 tokens every time?

**No.** 8000 is the default. Just run:

```bash
contextos pack --task "fix the login bug"
```

That's it. You never need to specify `--budget` unless you want more or less context.

---

### When should I change the token budget?

| Situation | Budget |
|-----------|--------|
| Small bug fix, single file | `4000` |
| Default — most tasks | `8000` (automatic) |
| Large feature across many files | `16000` |
| Full refactor of a whole module | `32000` |

```bash
contextos pack --task "refactor the entire auth module" --budget 16000
```

---

### What is a token? How does this affect my Claude/ChatGPT usage?

A token is roughly 4 characters or ¾ of a word. Claude and ChatGPT charge usage by tokens.

Without ContextOS, you paste all your files → might use 200,000+ tokens → exhausts your quota in hours.

With ContextOS, only the relevant files are sent → ~8,000 tokens → your quota lasts 3-4x longer.

---

### How much does ContextOS save?

It shows you every time you run `contextos pack`:

```
  Token savings vs no ContextOS
    Without ContextOS : ~284,000 tokens  (entire repo, 126 files)
    With ContextOS    : ~8,000 tokens  (15 files)
    Saved             : ~276,000 tokens (97% reduction)
```

---

## Usage

### What's the basic workflow?

```bash
cd your-project
contextos scan                              # index the repo (one time)
contextos pack --task "what you want to do" # get context
```

Open the generated `CLAUDE_CONTEXT.md` and paste it into your AI tool.

---

### Do I need to re-scan every time?

No. Run `contextos scan` once when you start a project. After that, `contextos pack` automatically re-scans only if needed. Changed files are detected by content hash — unchanged files load from cache instantly.

---

### Does ContextOS send my code anywhere?

**No.** Everything runs locally. No network calls, no cloud, no accounts. Your code never leaves your machine.

---

### Does ContextOS expose my passwords or API keys?

No. ContextOS automatically detects and redacts 14 types of secrets before any output:

- API keys (OpenAI, Anthropic, AWS, GitHub, Stripe, etc.)
- Database connection strings
- JWT tokens
- SSH private keys
- `.env` files are blocked entirely

---

## MCP Server

### What is the MCP server and do I need it?

The MCP server (`contextos serve`) lets AI agents call ContextOS directly as a tool. Instead of you running `contextos pack` and copying the output, Claude calls `pack_context()` automatically when it needs repo context.

You don't need it for basic use. It's for power users who want seamless AI agent integration.

---

### Is the MCP server Claude-only?

No. MCP is an open protocol. Works with Claude Desktop, Claude Code, Cursor, Windsurf, and any MCP-compatible client.

---

### How do I connect ContextOS to Claude Desktop?

```bash
pip install "rm-contextos[mcp]"
```

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "contextos": {
      "command": "contextos",
      "args": ["serve", "--stdio", "/path/to/your/project"]
    }
  }
}
```

Restart Claude Desktop. Done.

---

## Headroom Integration

### What does Headroom do?

Headroom compresses context after ContextOS selects it. Same information, fewer tokens — typically 30-40% reduction. Useful when you're near the budget limit.

```bash
pip install "rm-contextos[headroom]"
headroom serve &   # start the local proxy
contextos pack --task "your task" --compress headroom
```

See [Headroom docs](HEADROOM.md) for full setup.

---

## Errors

### "No scan data found" error

Run `contextos scan` first:

```bash
contextos scan
contextos pack --task "your task"
```

---

### "Budget must be a positive integer" error

The `--budget` flag must be a number greater than zero:

```bash
contextos pack --task "fix the bug" --budget 8000
```

---

### The output has `[REDACTED_API_KEY]` in it — is that a problem?

No, that's correct behavior. ContextOS found a secret in that file and replaced the value with a placeholder so it's safe to share with an AI. The key name is preserved so the AI still understands the code structure.
