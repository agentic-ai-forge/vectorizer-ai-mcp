"""Tests for the vectorizer-ai-mcp server."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from vectorizer_ai_mcp.server import _load_image, _save_file


class TestLoadImage:
    """Tests for _load_image function."""

    @pytest.mark.asyncio
    async def test_load_from_file(self, tmp_path: Path):
        """Test loading image from local file."""
        # Create test file
        test_file = tmp_path / "test.png"
        test_content = b"fake png content"
        test_file.write_bytes(test_content)

        result = await _load_image(str(test_file))
        assert result == test_content

    @pytest.mark.asyncio
    async def test_load_from_base64(self):
        """Test loading image from base64 string."""
        original = b"test image data"
        b64_input = base64.b64encode(original).decode("utf-8")

        result = await _load_image(b64_input)
        assert result == original

    @pytest.mark.asyncio
    async def test_load_from_url(self):
        """Test loading image from URL."""
        test_content = b"remote image content"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.content = test_content
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await _load_image("https://example.com/image.png")
            assert result == test_content

    @pytest.mark.asyncio
    async def test_invalid_input_raises_error(self):
        """Test that invalid input raises ValueError for non-existent file."""
        with pytest.raises(ValueError, match="Could not load image"):
            # Use invalid base64 that will fail decoding (odd length, invalid chars)
            await _load_image("~~~not~valid~base64~~~")


class TestSaveFile:
    """Tests for _save_file function."""

    @pytest.mark.asyncio
    async def test_save_file_success(self, tmp_path: Path):
        """Test saving file successfully."""
        content = b"svg content here"
        b64_content = base64.b64encode(content).decode("utf-8")
        output_path = tmp_path / "output.svg"

        result = await _save_file(
            {
                "content_base64": b64_content,
                "path": str(output_path),
            }
        )

        assert "saved successfully" in result[0].text
        assert output_path.read_bytes() == content

    @pytest.mark.asyncio
    async def test_save_file_missing_parent(self, tmp_path: Path):
        """Test error when parent directory doesn't exist."""
        result = await _save_file(
            {
                "content_base64": base64.b64encode(b"test").decode(),
                "path": str(tmp_path / "nonexistent" / "file.svg"),
            }
        )

        assert "Parent directory does not exist" in result[0].text
