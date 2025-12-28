#!/usr/bin/env python3
"""
Vectorizer.AI MCP Server - Minimal Python implementation

Exposes three tools:
- vectorize_image: Convert bitmap to vector graphics
- save_file: Download and save vectorized output
- check_account: Verify API credentials and subscription status

API Reference: https://vectorizer.ai/api
"""

import asyncio
import base64
from pathlib import Path
from typing import Any, Literal

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from vectorizer_ai_mcp.settings import Settings, get_settings

# --- Type Aliases ---

OutputFormat = Literal["svg", "pdf", "eps", "dxf", "png"]
ProcessingMode = Literal["production", "preview", "test"]
CurveType = Literal["all", "beziers_only", "lines_only", "arcs_and_lines"]


# --- Tool Schemas ---

VECTORIZE_IMAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "image": {
            "type": "string",
            "description": "Image source: local file path, URL, or base64-encoded data",
        },
        "output_format": {
            "type": "string",
            "description": "Output format (default: svg)",
            "enum": ["svg", "pdf", "eps", "dxf", "png"],
            "default": "svg",
        },
        "mode": {
            "type": "string",
            "description": (
                "Processing mode: production (1 credit, full quality), "
                "preview (0.2 credits, watermarked), test (free, watermarked)"
            ),
            "enum": ["production", "preview", "test"],
            "default": "production",
        },
        "output_path": {
            "type": "string",
            "description": (
                "Optional: Save output directly to this path. "
                "If not provided, returns base64 content."
            ),
        },
        "max_colors": {
            "type": "integer",
            "description": "Limit output colors (0=unlimited, 1-256)",
            "minimum": 0,
            "maximum": 256,
        },
        "curves": {
            "type": "string",
            "description": "Curve types to use",
            "enum": ["all", "beziers_only", "lines_only", "arcs_and_lines"],
        },
        "palette": {
            "type": "string",
            "description": (
                "Color palette mapping. Format: '[color][-> remapped][~ tolerance];' "
                "Use #RRGGBB for opaque, #RRGGBBAA for transparent. "
                "Example to make dark background transparent: '#0d1117 -> #00000000;' "
                "Fully transparent colors (#RRGGBB00) are omitted from result."
            ),
        },
    },
    "required": ["image"],
}

SAVE_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "content_base64": {
            "type": "string",
            "description": "Base64-encoded file content",
        },
        "path": {
            "type": "string",
            "description": "Destination file path (e.g., /path/to/output.svg)",
        },
    },
    "required": ["content_base64", "path"],
}

CHECK_ACCOUNT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
}

TOOL_DEFINITIONS = [
    Tool(
        name="vectorize_image",
        description=(
            "Convert a bitmap image (PNG, JPG, WEBP, BMP, GIF) to vector format "
            "(SVG, PDF, EPS, DXF). Uses AI-powered vectorization with sub-pixel precision. "
            "Modes: production (1 credit), preview (0.2 credits, watermarked), "
            "test (free, watermarked). Returns the vectorized content."
        ),
        inputSchema=VECTORIZE_IMAGE_SCHEMA,
    ),
    Tool(
        name="save_file",
        description=(
            "Save binary content (from vectorize_image) to a local file. "
            "Use when you have base64-encoded vector data to save."
        ),
        inputSchema=SAVE_FILE_SCHEMA,
    ),
    Tool(
        name="check_account",
        description=(
            "Check your Vectorizer.AI account status and remaining credits. "
            "Use this to verify your API credentials are configured correctly."
        ),
        inputSchema=CHECK_ACCOUNT_SCHEMA,
    ),
]

# --- API Option Mapping ---

OPTION_MAPPING = {
    "max_colors": "processing.max_colors",
    "curves": "output.curves",
    "palette": "processing.palette",
}


# --- API Client ---


class VectorizerClient:
    """Async client for the Vectorizer.AI API."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.api_base_url,
            auth=(settings.api_id, settings.api_secret.get_secret_value()),
            timeout=settings.timeout,
        )

    async def vectorize(
        self,
        image_data: bytes,
        output_format: OutputFormat = "svg",
        mode: ProcessingMode = "production",
        **options: Any,
    ) -> httpx.Response:
        """Vectorize an image."""
        files = {"image": ("image", image_data)}
        data: dict[str, Any] = {
            "output.file_format": output_format,
            "mode": mode,
        }
        for key, value in options.items():
            if value is not None:
                data[key] = str(value) if not isinstance(value, str) else value

        response = await self._client.post("/vectorize", files=files, data=data)
        response.raise_for_status()
        return response

    async def get_account(self) -> dict[str, Any]:
        """Get account status and credits."""
        response = await self._client.get("/account")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


# --- MCP Server ---

server = Server("vectorizer-ai")


def get_client() -> VectorizerClient:
    """Get API client using settings from environment."""
    return VectorizerClient(get_settings())


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a tool."""
    if name == "save_file":
        return await _save_file(arguments)

    client = get_client()
    try:
        if name == "vectorize_image":
            return await _vectorize_image(client, arguments)
        if name == "check_account":
            return await _check_account(client)
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    finally:
        await client.close()


# --- Helper Functions ---


def _error_response(message: str) -> list[TextContent]:
    """Create a standardized error response."""
    return [TextContent(type="text", text=message)]


def _success_response(text: str) -> list[TextContent]:
    """Create a standardized success response."""
    return [TextContent(type="text", text=text)]


def _validate_parent_dir(path: Path) -> list[TextContent] | None:
    """Return error response if parent directory doesn't exist, else None."""
    if not path.parent.exists():
        return _error_response(f"Error: Parent directory does not exist: {path.parent}")
    return None


def _build_vectorize_options(args: dict[str, Any]) -> dict[str, Any]:
    """Build API options from tool arguments."""
    return {
        api_key: args[arg_key] for arg_key, api_key in OPTION_MAPPING.items() if arg_key in args
    }


def _format_file_result(
    path: Path, output_format: str, mode: str, credits: str, size_kb: float
) -> str:
    """Format result message for file output."""
    return (
        f"Image vectorized successfully!\n\n"
        f"**Output:** {path}\n"
        f"**Format:** {output_format.upper()}\n"
        f"**Size:** {size_kb:.1f} KB\n"
        f"**Mode:** {mode}\n"
        f"**Credits charged:** {credits}"
    )


def _format_base64_result(
    output_format: str, mode: str, credits: str, size_kb: float, content_b64: str
) -> str:
    """Format result message for base64 output."""
    truncated = content_b64[:500] + ("..." if len(content_b64) > 500 else "")
    return (
        f"Image vectorized successfully!\n\n"
        f"**Format:** {output_format.upper()}\n"
        f"**Size:** {size_kb:.1f} KB\n"
        f"**Mode:** {mode}\n"
        f"**Credits charged:** {credits}\n\n"
        f"**Content (base64):**\n```\n{truncated}\n```\n\n"
        f"Use `save_file` tool to save this content, or provide `output_path` parameter."
    )


# --- Tool Handlers ---


async def _check_account(client: VectorizerClient) -> list[TextContent]:
    """Check account status."""
    try:
        result = await client.get_account()
        return _success_response(
            f"**Vectorizer.AI Account Status**\n\n"
            f"Credits: {result.get('credits', 0)}\n"
            f"Plan: {result.get('subscriptionPlan', 'Unknown')}\n"
            f"Status: {result.get('subscriptionStatus', 'Unknown')}\n\n"
            f"Pricing reference:\n"
            f"- Production: 1 credit per image\n"
            f"- Preview: 0.2 credits (watermarked)\n"
            f"- Test: Free (watermarked)"
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return _error_response(
                "Error: Invalid API credentials. Check VECTORIZER_API_ID and VECTORIZER_API_SECRET."
            )
        return _error_response(f"Error checking account: HTTP {e.response.status_code}")
    except httpx.TimeoutException:
        return _error_response("Error: Request timed out. Check your network connection.")
    except httpx.ConnectError:
        return _error_response("Error: Could not connect to Vectorizer.AI API.")


async def _vectorize_image(client: VectorizerClient, args: dict[str, Any]) -> list[TextContent]:
    """Handle vectorize_image tool."""
    output_format = args.get("output_format", "svg")
    mode = args.get("mode", "production")
    output_path = args.get("output_path")

    try:
        image_data = await _load_image(args["image"])
    except ValueError as e:
        return _error_response(str(e))

    try:
        response = await client.vectorize(
            image_data=image_data,
            output_format=output_format,
            mode=mode,
            **_build_vectorize_options(args),
        )
        credits = response.headers.get("X-Credits-Charged", "N/A")
        return _handle_vectorize_response(response, output_format, mode, credits, output_path)
    except httpx.HTTPStatusError as e:
        return _error_response(_format_http_error("Vectorization failed", e))
    except httpx.TimeoutException:
        return _error_response("Error: Vectorization timed out. Try a smaller image.")
    except httpx.ConnectError:
        return _error_response("Error: Could not connect to Vectorizer.AI API.")


def _handle_vectorize_response(
    response: httpx.Response,
    output_format: str,
    mode: str,
    credits: str,
    output_path: str | None,
) -> list[TextContent]:
    """Handle successful vectorization response."""
    if output_path:
        path = Path(output_path)
        if error := _validate_parent_dir(path):
            return error
        path.write_bytes(response.content)
        size_kb = path.stat().st_size / 1024
        return _success_response(_format_file_result(path, output_format, mode, credits, size_kb))

    content_b64 = base64.b64encode(response.content).decode("utf-8")
    size_kb = len(response.content) / 1024
    result = _format_base64_result(output_format, mode, credits, size_kb, content_b64)
    return _success_response(result)


def _format_http_error(prefix: str, error: httpx.HTTPStatusError) -> str:
    """Format HTTP error with details from response."""
    try:
        error_json = error.response.json()
        detail = error_json.get("message", str(error_json))
    except Exception:
        detail = error.response.text[:200]
    return f"{prefix} (HTTP {error.response.status_code}): {detail}"


async def _save_file(args: dict[str, Any]) -> list[TextContent]:
    """Save base64-encoded content to a file."""
    path = Path(args["path"])

    if error := _validate_parent_dir(path):
        return error

    try:
        content = base64.b64decode(args["content_base64"])
        path.write_bytes(content)
        size_kb = path.stat().st_size / 1024
        msg = f"File saved successfully!\n\n**Path:** {path}\n**Size:** {size_kb:.1f} KB"
        return _success_response(msg)
    except Exception as e:
        return _error_response(f"Error saving file: {e!s}")


async def _load_image(image_input: str) -> bytes:
    """Load image from file path, URL, or base64 string."""
    if image_input.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(image_input)
            response.raise_for_status()
            return response.content

    path = Path(image_input)
    if path.exists():
        return path.read_bytes()

    try:
        return base64.b64decode(image_input)
    except Exception:
        raise ValueError(
            f"Could not load image: '{image_input[:50]}...' "
            "is not a valid file path, URL, or base64 string"
        ) from None


# --- Entry Point ---


def main() -> None:
    """Run the MCP server."""
    asyncio.run(_run_server())


async def _run_server() -> None:
    """Async server runner."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
