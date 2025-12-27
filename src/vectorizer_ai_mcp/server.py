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
import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# --- Configuration ---

API_BASE_URL = "https://api.vectorizer.ai/api/v1"
DEFAULT_TIMEOUT = 180.0  # Vectorization can take time


# --- API Client ---


class VectorizerClient:
    """Async client for the Vectorizer.AI API."""

    def __init__(self, api_id: str, api_secret: str):
        self.api_id = api_id
        self.api_secret = api_secret
        self.client = httpx.AsyncClient(
            base_url=API_BASE_URL,
            auth=(api_id, api_secret),
            timeout=DEFAULT_TIMEOUT,
        )

    async def vectorize(
        self,
        image_data: bytes,
        output_format: str = "svg",
        mode: str = "production",
        **options: Any,
    ) -> httpx.Response:
        """
        Vectorize an image.

        Args:
            image_data: Raw image bytes
            output_format: svg, pdf, eps, dxf, or png
            mode: production (1 credit), preview (0.2), test (free, watermarked)
            **options: Additional API options (processing.*, output.*, etc.)

        Returns:
            Response with vectorized content
        """
        files = {"image": ("image", image_data)}
        data: dict[str, Any] = {
            "output.file_format": output_format,
            "mode": mode,
        }

        # Add optional parameters
        for key, value in options.items():
            if value is not None:
                data[key] = str(value) if not isinstance(value, str) else value

        response = await self.client.post("/vectorize", files=files, data=data)
        response.raise_for_status()
        return response

    async def get_account(self) -> dict[str, Any]:
        """Get account status and credits."""
        response = await self.client.get("/account")
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()


# --- MCP Server ---

server = Server("vectorizer-ai")


def get_client() -> VectorizerClient:
    """Get API client, raising helpful error if credentials are missing."""
    api_id = os.environ.get("VECTORIZER_API_ID")
    api_secret = os.environ.get("VECTORIZER_API_SECRET")

    if not api_id or not api_secret:
        raise ValueError(
            "VECTORIZER_API_ID and VECTORIZER_API_SECRET environment variables are required. "
            "Get your credentials at https://vectorizer.ai/api"
        )
    return VectorizerClient(api_id, api_secret)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="vectorize_image",
            description=(
                "Convert a bitmap image (PNG, JPG, WEBP, BMP, GIF) to vector format "
                "(SVG, PDF, EPS, DXF). Uses AI-powered vectorization with sub-pixel precision. "
                "Modes: production (1 credit), preview (0.2 credits, watermarked), "
                "test (free, watermarked). Returns the vectorized content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "image": {
                        "type": "string",
                        "description": (
                            "Image source: local file path, URL, or base64-encoded data"
                        ),
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
                },
                "required": ["image"],
            },
        ),
        Tool(
            name="save_file",
            description=(
                "Save binary content (from vectorize_image) to a local file. "
                "Use when you have base64-encoded vector data to save."
            ),
            inputSchema={
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
            },
        ),
        Tool(
            name="check_account",
            description=(
                "Check your Vectorizer.AI account status and remaining credits. "
                "Use this to verify your API credentials are configured correctly."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a tool."""
    if name == "save_file":
        return await _save_file(arguments)

    client = get_client()

    try:
        if name == "vectorize_image":
            return await _vectorize_image(client, arguments)
        elif name == "check_account":
            return await _check_account(client)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    finally:
        await client.close()


async def _check_account(client: VectorizerClient) -> list[TextContent]:
    """Check account status."""
    try:
        result = await client.get_account()

        credits = result.get("credits", 0)
        subscription = result.get("subscriptionPlan", "Unknown")
        status = result.get("subscriptionStatus", "Unknown")

        return [
            TextContent(
                type="text",
                text=(
                    f"**Vectorizer.AI Account Status**\n\n"
                    f"Credits: {credits}\n"
                    f"Plan: {subscription}\n"
                    f"Status: {status}\n\n"
                    f"Pricing reference:\n"
                    f"- Production: 1 credit per image\n"
                    f"- Preview: 0.2 credits (watermarked)\n"
                    f"- Test: Free (watermarked)"
                ),
            )
        ]
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return [
                TextContent(
                    type="text",
                    text=(
                        "Error: Invalid API credentials. "
                        "Check VECTORIZER_API_ID and VECTORIZER_API_SECRET."
                    ),
                )
            ]
        return [TextContent(type="text", text=f"Error checking account: {e!s}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error checking account: {e!s}")]


async def _vectorize_image(client: VectorizerClient, args: dict[str, Any]) -> list[TextContent]:
    """Handle vectorize_image tool."""
    image_input = args["image"]
    output_format = args.get("output_format", "svg")
    mode = args.get("mode", "production")
    output_path = args.get("output_path")

    # Load image data
    try:
        image_data = await _load_image(image_input)
    except Exception as e:
        return [TextContent(type="text", text=f"Error loading image: {e!s}")]

    # Build options
    options: dict[str, Any] = {}
    if "max_colors" in args:
        options["processing.max_colors"] = args["max_colors"]
    if "curves" in args:
        options["output.curves"] = args["curves"]

    try:
        response = await client.vectorize(
            image_data=image_data,
            output_format=output_format,
            mode=mode,
            **options,
        )

        # Get response info
        credits_charged = response.headers.get("X-Credits-Charged", "N/A")

        # Handle output
        if output_path:
            # Save directly to file
            path = Path(output_path)
            if not path.parent.exists():
                return [
                    TextContent(
                        type="text",
                        text=f"Error: Parent directory does not exist: {path.parent}",
                    )
                ]
            path.write_bytes(response.content)
            file_size = path.stat().st_size / 1024

            return [
                TextContent(
                    type="text",
                    text=(
                        f"Image vectorized successfully!\n\n"
                        f"**Output:** {path}\n"
                        f"**Format:** {output_format.upper()}\n"
                        f"**Size:** {file_size:.1f} KB\n"
                        f"**Mode:** {mode}\n"
                        f"**Credits charged:** {credits_charged}"
                    ),
                )
            ]
        else:
            # Return base64-encoded content
            content_b64 = base64.b64encode(response.content).decode("utf-8")
            content_size = len(response.content) / 1024

            return [
                TextContent(
                    type="text",
                    text=(
                        f"Image vectorized successfully!\n\n"
                        f"**Format:** {output_format.upper()}\n"
                        f"**Size:** {content_size:.1f} KB\n"
                        f"**Mode:** {mode}\n"
                        f"**Credits charged:** {credits_charged}\n\n"
                        f"**Content (base64):**\n```\n{content_b64[:500]}"
                        f"{'...' if len(content_b64) > 500 else ''}\n```\n\n"
                        f"Use `save_file` tool to save this content, "
                        f"or provide `output_path` parameter."
                    ),
                )
            ]

    except httpx.HTTPStatusError as e:
        error_detail = ""
        try:
            error_json = e.response.json()
            error_detail = f": {error_json.get('message', str(error_json))}"
        except Exception:
            error_detail = f": {e.response.text[:200]}"
        return [
            TextContent(
                type="text",
                text=f"Vectorization failed (HTTP {e.response.status_code}){error_detail}",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error vectorizing image: {e!s}")]


async def _save_file(args: dict[str, Any]) -> list[TextContent]:
    """Save base64-encoded content to a file."""
    content_b64 = args["content_base64"]
    path = Path(args["path"])

    try:
        if not path.parent.exists():
            return [
                TextContent(
                    type="text",
                    text=f"Error: Parent directory does not exist: {path.parent}",
                )
            ]

        content = base64.b64decode(content_b64)
        path.write_bytes(content)

        file_size = path.stat().st_size / 1024

        return [
            TextContent(
                type="text",
                text=f"File saved successfully!\n\n**Path:** {path}\n**Size:** {file_size:.1f} KB",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error saving file: {e!s}")]


async def _load_image(image_input: str) -> bytes:
    """Load image from file path, URL, or base64 string."""
    # Check if it's a URL
    if image_input.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(image_input)
            response.raise_for_status()
            return response.content

    # Check if it's a local file
    path = Path(image_input)
    if path.exists():
        return path.read_bytes()

    # Assume it's base64
    try:
        return base64.b64decode(image_input)
    except Exception:
        raise ValueError(
            f"Could not load image: '{image_input[:50]}...' "
            "is not a valid file path, URL, or base64 string"
        )


def main():
    """Run the MCP server."""
    asyncio.run(_run_server())


async def _run_server():
    """Async server runner."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
