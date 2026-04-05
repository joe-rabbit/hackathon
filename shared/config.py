"""Configuration management for Mochi UI.

Uses pydantic-settings for environment variable loading with .env file support.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Backend connection
    backend_url: str = Field(
        default="http://127.0.0.1:8000",
        alias="MOCHI_BACKEND_URL",
        description="Backend REST API URL",
    )
    ws_url: str = Field(
        default="ws://127.0.0.1:8000/ws/telemetry",
        alias="MOCHI_WS_URL",
        description="Backend WebSocket URL",
    )

    # Local LLM settings
    ollama_host: str = Field(
        default="http://127.0.0.1:11434",
        alias="OLLAMA_HOST",
        description="Ollama server URL",
    )
    model_name: str = Field(
        default="gemma3:1b",
        alias="MOCHI_MODEL",
        description="LLM model to use",
    )

    # Mock mode
    use_mocks: bool = Field(
        default=True,
        alias="MOCHI_USE_MOCKS",
        description="Use mock backend instead of real API",
    )

    # Dashboard
    dashboard_url: str = Field(
        default="http://127.0.0.1:8501",
        alias="MOCHI_DASHBOARD_URL",
        description="Streamlit dashboard URL",
    )

    # Device info
    device_name: str = Field(
        default="edge-01",
        alias="MOCHI_DEVICE_NAME",
        description="Device name shown in header",
    )

    # Polling
    poll_interval: float = Field(
        default=2.0,
        alias="MOCHI_POLL_INTERVAL",
        description="Polling interval in seconds",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        alias="MOCHI_LOG_LEVEL",
        description="Log level",
    )

    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return self.use_mocks

    @property
    def ollama_api_url(self) -> str:
        """Get Ollama API endpoint."""
        return f"{self.ollama_host}/api"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience function for quick access
def settings() -> Settings:
    """Get application settings."""
    return get_settings()
