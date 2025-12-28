"""Integration tests for vectorizer-ai-mcp.

These tests require valid API credentials and make real API calls.
Run with: uv run pytest tests/test_integration.py -v

Note: vectorize_image tests are marked as 'expensive' because they consume credits.
Skip with: uv run pytest tests/test_integration.py -v -m 'not expensive'
"""

import os
import struct
import zlib
from pathlib import Path

import pytest

from vectorizer_ai_mcp.server import _check_account, _vectorize_image, get_client
from vectorizer_ai_mcp.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache before each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def credentials_available() -> bool:
    """Check if API credentials are available."""
    return bool(os.environ.get("VECTORIZER_API_ID") and os.environ.get("VECTORIZER_API_SECRET"))


@pytest.mark.skipif(not credentials_available(), reason="API credentials not available")
class TestIntegration:
    """Integration tests that require real API credentials."""

    @pytest.mark.asyncio
    async def test_check_account_real(self):
        """Test check_account with real API credentials."""
        client = get_client()
        try:
            result = await _check_account(client)
            assert len(result) == 1
            text = result[0].text
            assert "Vectorizer.AI Account Status" in text
            assert "Credits:" in text
            assert "Plan:" in text
            assert "Status:" in text
        finally:
            await client.close()

    @pytest.mark.asyncio
    @pytest.mark.expensive
    async def test_vectorize_image_test_mode(self, tmp_path: Path):
        """Test vectorize_image with test mode (free, watermarked).

        This test uses 'test' mode which is free but produces watermarked output.
        """
        # Create a simple 10x10 red/blue checkerboard PNG
        width, height = 10, 10

        def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
            chunk_len = struct.pack(">I", len(data))
            chunk_crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
            return chunk_len + chunk_type + data + chunk_crc

        # Create simple RGB pixel data (checkerboard pattern)
        rows = []
        for y in range(height):
            row = b"\x00"  # Filter byte
            for x in range(width):
                if (x + y) % 2 == 0:
                    row += b"\xff\x00\x00"  # Red
                else:
                    row += b"\x00\x00\xff"  # Blue
            rows.append(row)
        raw_data = b"".join(rows)
        compressed = zlib.compress(raw_data)

        # Build PNG
        png_signature = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
        ihdr = png_chunk(b"IHDR", ihdr_data)
        idat = png_chunk(b"IDAT", compressed)
        iend = png_chunk(b"IEND", b"")

        png_data = png_signature + ihdr + idat + iend

        test_image = tmp_path / "test.png"
        test_image.write_bytes(png_data)
        output_path = tmp_path / "output.svg"

        client = get_client()
        try:
            result = await _vectorize_image(
                client,
                {
                    "image": str(test_image),
                    "output_format": "svg",
                    "mode": "test",  # Free, watermarked
                    "output_path": str(output_path),
                },
            )
            assert len(result) == 1
            text = result[0].text
            assert "vectorized successfully" in text
            assert output_path.exists()
            assert output_path.stat().st_size > 0
        finally:
            await client.close()
