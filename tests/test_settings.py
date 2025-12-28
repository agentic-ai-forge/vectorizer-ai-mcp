"""Tests for the Settings configuration module."""

import pytest
from pydantic import ValidationError

from vectorizer_ai_mcp.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache before each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestSettings:
    """Tests for Settings class."""

    def test_settings_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """Test settings are loaded from environment variables."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")

        settings = get_settings()

        assert settings.api_id == "test-id"
        assert settings.api_secret.get_secret_value() == "test-secret"
        assert settings.api_base_url == "https://api.vectorizer.ai/api/v1"
        assert settings.timeout == 180.0

    def test_settings_custom_timeout(self, monkeypatch: pytest.MonkeyPatch):
        """Test custom timeout from environment."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")
        monkeypatch.setenv("VECTORIZER_TIMEOUT", "300.0")

        settings = get_settings()

        assert settings.timeout == 300.0

    def test_settings_custom_base_url(self, monkeypatch: pytest.MonkeyPatch):
        """Test custom base URL from environment."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")
        monkeypatch.setenv("VECTORIZER_API_BASE_URL", "https://custom.api.com")

        settings = get_settings()

        assert settings.api_base_url == "https://custom.api.com"

    def test_settings_missing_api_id(self, monkeypatch: pytest.MonkeyPatch):
        """Test validation error when API ID is missing."""
        monkeypatch.delenv("VECTORIZER_API_ID", raising=False)
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")

        with pytest.raises(ValidationError):
            get_settings()

    def test_settings_missing_api_secret(self, monkeypatch: pytest.MonkeyPatch):
        """Test validation error when API secret is missing."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.delenv("VECTORIZER_API_SECRET", raising=False)

        with pytest.raises(ValidationError):
            get_settings()

    def test_secret_is_masked(self, monkeypatch: pytest.MonkeyPatch):
        """Test that API secret is properly masked when converted to string."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "super-secret-key")

        settings = get_settings()

        # SecretStr should mask the value in string representation
        assert "super-secret-key" not in str(settings)
        assert "super-secret-key" not in repr(settings)

    def test_settings_empty_api_id_fails(self, monkeypatch: pytest.MonkeyPatch):
        """Test that empty API ID is rejected (min_length=1)."""
        monkeypatch.setenv("VECTORIZER_API_ID", "")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")

        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            get_settings()

    def test_settings_timeout_must_be_positive(self, monkeypatch: pytest.MonkeyPatch):
        """Test that timeout must be positive (gt=0)."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")
        monkeypatch.setenv("VECTORIZER_TIMEOUT", "0")

        with pytest.raises(ValidationError, match="greater than 0"):
            get_settings()

    def test_settings_timeout_max_limit(self, monkeypatch: pytest.MonkeyPatch):
        """Test that timeout has a maximum limit (le=600)."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")
        monkeypatch.setenv("VECTORIZER_TIMEOUT", "601")

        with pytest.raises(ValidationError, match="less than or equal to 600"):
            get_settings()

    def test_settings_is_frozen(self, monkeypatch: pytest.MonkeyPatch):
        """Test that settings are immutable (frozen=True)."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")

        settings = get_settings()

        with pytest.raises(ValidationError):
            settings.api_id = "new-id"

    def test_settings_caching(self, monkeypatch: pytest.MonkeyPatch):
        """Test that get_settings uses lru_cache."""
        monkeypatch.setenv("VECTORIZER_API_ID", "test-id")
        monkeypatch.setenv("VECTORIZER_API_SECRET", "test-secret")

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance due to caching
        assert settings1 is settings2
