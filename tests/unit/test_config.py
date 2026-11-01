"""Tests for application settings and configuration."""

from app.core.config import Settings


def test_settings_default_values():
    settings = Settings()
    assert settings.PROJECT_NAME == "TempChat"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.MIN_ROOM_DURATION_MINUTES == 1
    assert settings.MAX_ROOM_DURATION_MINUTES == 10080
    assert 60 in settings.ALLOWED_DURATION_PRESETS
    assert settings.DEFAULT_MAX_MEMBERS_GROUP == 50
    assert settings.MAX_MEMBERS_GROUP_LIMIT == 100
    assert ".exe" in settings.DANGEROUS_EXTENSIONS
    assert "image/png" in settings.ALLOWED_IMAGE_MIMES
