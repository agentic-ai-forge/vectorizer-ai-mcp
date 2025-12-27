# 🎨 vectorizer-ai-mcp

[![Pipeline Status](https://gitlab.com/agentic.ai.forge/vectorizer-ai-mcp/badges/main/pipeline.svg)](https://gitlab.com/agentic.ai.forge/vectorizer-ai-mcp/-/pipelines)
[![Coverage](https://gitlab.com/agentic.ai.forge/vectorizer-ai-mcp/badges/main/coverage.svg)](https://gitlab.com/agentic.ai.forge/vectorizer-ai-mcp/-/commits/main)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Minimal MCP server for [Vectorizer.AI](https://vectorizer.ai) - AI-powered bitmap to vector conversion.

## ✨ Features

- 🖼️ **vectorize_image**: Convert PNG/JPG/WEBP/BMP/GIF to SVG/PDF/EPS/DXF
- 💾 **save_file**: Save vectorized output to local files
- 📊 **check_account**: Verify API credentials and credit balance

## 📦 Installation

```bash
# With uv (recommended)
uv pip install .

# With pip
pip install .
```

## ⚙️ Configuration

Set environment variables:

```bash
export VECTORIZER_API_ID="your-api-id"
export VECTORIZER_API_SECRET="your-api-secret"
```

🔑 Get your credentials at [vectorizer.ai/api](https://vectorizer.ai/api).

### Using direnv (recommended)

Create a `.envrc` file in the project directory:

```bash
export VECTORIZER_API_ID="your-api-id"
export VECTORIZER_API_SECRET="your-api-secret"
```

Then run `direnv allow` to load the environment.

## 🚀 Running the Server

### Standalone

```bash
# With uv
uv run vectorizer-ai-mcp

# Or if installed
vectorizer-ai-mcp
```

### With Claude Code

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "vectorizer-ai": {
      "command": "vectorizer-ai-mcp",
      "env": {
        "VECTORIZER_API_ID": "your-api-id",
        "VECTORIZER_API_SECRET": "your-api-secret"
      }
    }
  }
}
```

Or with uv (no global install needed):

```json
{
  "mcpServers": {
    "vectorizer-ai": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/vectorizer-ai-mcp", "vectorizer-ai-mcp"],
      "env": {
        "VECTORIZER_API_ID": "your-api-id",
        "VECTORIZER_API_SECRET": "your-api-secret"
      }
    }
  }
}
```

## 🛠️ Tools

### vectorize_image

Convert bitmap to vector graphics.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | string | ✅ | Local file path, URL, or base64-encoded image |
| `output_format` | string | | svg (default), pdf, eps, dxf, png |
| `mode` | string | | production (1 credit), preview (0.2), test (free) |
| `output_path` | string | | Save output directly to this path |
| `max_colors` | int | | Limit colors (0-256, 0=unlimited) |
| `curves` | string | | all, beziers_only, lines_only, arcs_and_lines |
| `palette` | string | | Color palette mapping (see below) |

**Example:**
```python
vectorize_image(
  image="/path/to/logo.png",
  output_format="svg",
  mode="production",
  output_path="/path/to/logo.svg"
)
```

#### Palette Parameter

The `palette` parameter allows you to map or remove specific colors during vectorization. This is useful for:
- Making backgrounds transparent
- Remapping colors to a specific palette
- Removing unwanted colors from the output

**Format:** `[color][-> remapped][~ tolerance];`

| Syntax | Description |
|--------|-------------|
| `#RRGGBB` | Opaque color |
| `#RRGGBBAA` | Color with alpha (00 = transparent) |
| `-> #color` | Remap to different color |
| `~ 0.02` | Tolerance (0-2.0, default 2.0) |

**Examples:**

```python
# Remove dark background (make transparent)
vectorize_image(
  image="/path/to/logo.png",
  palette="#0d1117 -> #00000000;",
  output_path="/path/to/logo-transparent.svg"
)

# Snap colors to specific palette
vectorize_image(
  image="/path/to/logo.png",
  palette="#FF0000 ~ 0.02; #00FF00 ~ 0.02; #0000FF ~ 0.02; #00000000;",
  output_path="/path/to/logo-limited.svg"
)
```

### check_account

Verify API credentials and check credit balance. No parameters required.

### save_file

Save base64-encoded content to a local file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content_base64` | string | ✅ | Base64-encoded file content |
| `path` | string | ✅ | Destination file path |

## 💰 Pricing

| Mode | Credits | Quality |
|------|---------|---------|
| 🧪 **Test** | Free | Watermarked |
| 👁️ **Preview** | 0.2 | Watermarked, lower res |
| ✅ **Production** | 1.0 | Full quality |

Credits start at $0.20/credit (50 credits for $9.99/month).

## 🧑‍💻 Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Lint & format
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

## 📄 License

MIT
