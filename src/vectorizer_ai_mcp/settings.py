"""Configuration settings using pydantic-settings."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Vectorizer.AI MCP Server settings.

    Loads configuration from environment variables with the VECTORIZER_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="VECTORIZER_",
        case_sensitive=False,
        frozen=True,
    )

    api_id: str = Field(
        min_length=1,
        description="Vectorizer.AI API ID",
    )
    api_secret: SecretStr = Field(
        description="Vectorizer.AI API Secret",
    )
    api_base_url: str = Field(
        default="https://api.vectorizer.ai/api/v1",
        description="Base URL for Vectorizer.AI API",
    )
    timeout: float = Field(
        default=180.0,
        gt=0,
        le=600,
        description="Request timeout in seconds (vectorization can take time)",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings from environment variables.

    Raises:
        ValidationError: If required environment variables are missing.

    Returns:
        Settings instance with validated configuration.
    """
    return Settings()  # type: ignore[call-arg]
