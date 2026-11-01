"""Application configuration using Pydantic Settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    PROJECT_NAME: str = "TempChat"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    SECRET_KEY: str = Field(default="tempchat-super-secret-key-change-me-in-production")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/tempchat"
    )
    TEST_DATABASE_URL: str = Field(default="sqlite+aiosqlite:///:memory:")

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Room Duration & Member Limits
    MIN_ROOM_DURATION_MINUTES: int = 1
    MAX_ROOM_DURATION_MINUTES: int = 10080  # 7 days
    ALLOWED_DURATION_PRESETS: list[int] = [10, 30, 60, 360, 1440, 10080]
    DEFAULT_MAX_MEMBERS_GROUP: int = 50
    MAX_MEMBERS_GROUP_LIMIT: int = 100

    # Rate Limiting (in-memory sliding window)
    RATE_LIMIT_CREATE_ROOM: int = 10  # per minute per IP
    RATE_LIMIT_JOIN_ROOM: int = 30  # per minute per IP
    RATE_LIMIT_MESSAGES: int = 60  # per minute per participant
    RATE_LIMIT_UPLOADS: int = 20  # per minute per participant

    # WebSocket Configuration
    WS_TICKET_TTL_SECONDS: int = 60
    WS_HEARTBEAT_INTERVAL_SECONDS: int = 30
    WS_TYPING_TIMEOUT_SECONDS: int = 5
    WS_MAX_MESSAGE_SIZE: int = 65536  # 64 KB

    # Storage Configuration
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    LOCAL_STORAGE_DIR: Path = Path("storage/media")
    S3_BUCKET_NAME: str = "tempchat-media"
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_REGION: str = "us-east-1"

    # Upload Limits (bytes)
    MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    MAX_AUDIO_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

    # Allowed MIME Types
    ALLOWED_IMAGE_MIMES: set[str] = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
    ALLOWED_AUDIO_MIMES: set[str] = {
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "audio/mp4",
    }
    ALLOWED_FILE_MIMES: set[str] = {
        "application/pdf",
        "text/plain",
        "application/zip",
        "application/x-zip-compressed",
    }

    # Prohibited dangerous file extensions
    DANGEROUS_EXTENSIONS: set[str] = {
        ".exe",
        ".bat",
        ".cmd",
        ".sh",
        ".php",
        ".js",
        ".html",
        ".htm",
        ".svg",
        ".jar",
        ".vbs",
        ".msi",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".com",
    }

    # Workers
    EXPIRATION_WORKER_INTERVAL_SECONDS: int = 15
    STORAGE_CLEANUP_INTERVAL_SECONDS: int = 60


settings = Settings()
