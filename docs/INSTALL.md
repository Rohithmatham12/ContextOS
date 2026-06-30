# Installation

## Requirements

- Python 3.11 or later
- pip

## PyPI (recommended)

```bash
pip install rm-contextos
```

Verify:

```bash
contextos --version
```

## From Source

```bash
git clone https://github.com/Rohithmatham12/ContextOS
cd ContextOS
pip install -e ".[dev]"
```

`.[dev]` includes pytest, ruff, and mypy. For production use only:

```bash
pip install -e .
```

## Virtual Environment

Recommended for all installs:

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

pip install rm-contextos
```

## Optional Feature Sets

Install optional extras with pip's bracket syntax:

```bash
pip install "rm-contextos[ast]"       # tree-sitter symbol extraction (better ranking)
pip install "rm-contextos[tokens]"    # tiktoken for accurate token counting
pip install "rm-contextos[headroom]"  # Headroom compression support
pip install "rm-contextos[all]"       # everything above
```

## Optional Dependencies

### tiktoken (accurate token counting)

Without tiktoken, ContextOS uses a regex approximation (~10–20% error for code).
With tiktoken, token counts use the `cl100k_base` BPE encoding.

```bash
pip install tiktoken
```

No configuration needed — ContextOS detects and uses it automatically.

### headroom-ai (local compression)

Required only if you use `--compress headroom`.

```bash
pip install headroom-ai
```

Then start the local proxy before running ContextOS:

```bash
headroom serve          # default: http://127.0.0.1:8787
```

See [`docs/HEADROOM.md`](HEADROOM.md) for full setup instructions.

## CI / Docker

```dockerfile
FROM python:3.12-slim
RUN pip install rm-contextos
```

Or pin a version:

```bash
pip install "rm-contextos==0.1.0"
```

## Upgrading

```bash
pip install --upgrade rm-contextos
```

## Uninstall

```bash
pip uninstall contextos
```

ContextOS writes nothing outside `.contextos/` directories in your project folders. No config files are created in your home directory.
