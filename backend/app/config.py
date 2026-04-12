"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration."""

    data_dir: Path = Field(default=Path("/data"))
    port: int = Field(default=8009)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    log_level: str = Field(default="info")


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    cors_raw = os.environ.get("CORS_ORIGINS", "*")
    return AppConfig(
        data_dir=Path(os.environ.get("DATA_DIR", "/data")),
        port=int(os.environ.get("PORT", "8009")),
        cors_origins=[o.strip() for o in cors_raw.split(",")],
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
