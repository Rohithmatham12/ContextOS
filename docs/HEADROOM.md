# Headroom Integration

## What is Headroom?

Headroom is a local compression proxy that reduces the token count of text while preserving semantic content. It runs locally on your machine — no text is sent to external servers.

ContextOS and Headroom are complementary:

- **ContextOS** selects the right files from your repo
- **Headroom** compresses what was selected

Together they give the agent maximum signal per token.

## Installation

```bash
pip install headroom-ai
```

Or in a dedicated virtual environment (recommended to avoid dependency conflicts):

```bash
python -m venv ~/.headroom-venv
~/.headroom-venv/bin/pip install headroom-ai
```

## Starting the Proxy

```bash
headroom serve
```

By default this binds to `http://127.0.0.1:8787`. Keep this running in a terminal or background process while using ContextOS with `--compress headroom`.

```bash
# Background (macOS/Linux):
headroom serve &

# Or as a system service — see headroom-ai documentation
```

## Using Compression with ContextOS

```bash
contextos pack . --task "fix auth bug" --budget 8000 --compress headroom
```

The pipeline:

1. ContextOS selects files within the 8000-token budget
2. ContextOS renders the full context pack Markdown
3. The rendered text is sent to Headroom at `http://127.0.0.1:8787`
4. Headroom returns a compressed version
5. The compressed text is written to disk

The `--budget` flag controls ContextOS selection, not the post-compression size. After compression, the pack will be smaller than the budget.

## Custom Proxy URL

```bash
# Environment variable (persists across commands)
export HEADROOM_BASE_URL=http://10.0.0.5:8787

# All subsequent pack/export commands use this URL
contextos pack . --task "fix auth" --budget 8000 --compress headroom
```

`HEADROOM_BASE_URL` overrides the default. Useful if the proxy runs on a different machine or port.

## Error Handling

If `headroom-ai` is not installed:

```
Error: headroom-ai is not installed.
Run: pip install headroom-ai
Then: headroom serve

To proceed without compression, omit --compress.
```

If the proxy is unreachable (not running, wrong port):

```
Error: Headroom proxy at http://127.0.0.1:8787 is not responding.
Ensure headroom serve is running.
HEADROOM_BASE_URL to override proxy URL.

To proceed without compression, omit --compress.
```

ContextOS never silently falls back to no-op compression. If `--compress headroom` is passed and Headroom is unavailable, the command fails with a clear error.

## Running ContextOS Without Headroom

Headroom is entirely optional. All commands work without it:

```bash
# No --compress flag = no compression, no dependency on headroom-ai
contextos pack . --task "fix auth" --budget 8000
```

## Architecture

The compression layer uses a provider abstraction:

```python
class CompressionProvider(ABC):
    def compress(self, text: str, *, budget: int) -> str: ...
    def name(self) -> str: ...
```

`HeadroomCompressionProvider` lazy-imports `headroom_ai` only when `--compress headroom` is passed. If the import fails, `HeadroomUnavailableError` is raised with install instructions. If the proxy call fails, the same error type is raised with proxy instructions.

This design means ContextOS has zero startup cost from the Headroom dependency, and no import-time failures for users who don't use compression.

## MCP Integration (Advanced)

Headroom also supports an MCP (Model Context Protocol) server mode, which enables direct integration with Claude Code:

```bash
pip install 'headroom-ai[mcp]'
headroom mcp install --agent claude
```

This registers Headroom as an MCP tool in Claude Code. The ContextOS `--compress headroom` flag uses the HTTP proxy interface, not MCP — both can coexist.

See `docs/MCP_SETUP.md` for the full MCP configuration used in this project.
