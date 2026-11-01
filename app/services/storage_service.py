"""Storage service with file signature, MIME validation, and provider abstraction."""

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import InvalidAttachmentError
from app.services.storage.base import StorageProvider
from app.services.storage.local import LocalStorageProvider
from app.services.storage.s3 import S3StorageProvider

# Magic bytes table
MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
    (b"OggS", "audio/ogg"),
    (b"ID3", "audio/mpeg"),
    (b"PK\x03\x04", "application/zip"),
]


def detect_mime_from_content(header: bytes, declared_mime: str) -> str:
    """Validate and detect MIME type from initial file header bytes."""
    # Check known fixed signatures
    for sig, mime in MAGIC_SIGNATURES:
        if header.startswith(sig):
            return mime

    # WebP: RIFF....WEBP
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"

    # WAV: RIFF....WAVE
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio/wav"

    # MP4 / M4A / WebM Audio: ftyp or matroska
    if len(header) >= 8 and header[4:8] == b"ftyp":
        if "audio" in declared_mime:
            return "audio/mp4"
        return "application/octet-stream"

    # WebM: 1A 45 DF A3
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        if "audio" in declared_mime:
            return "audio/webm"

    # MP3 without ID3 header (sync frames \xff\xfb, \xff\xf3, \xff\xf2)
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return "audio/mpeg"

    # Plain text
    if declared_mime == "text/plain":
        try:
            header[:1024].decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            pass

    # Default to declared MIME if recognized by whitelist
    return declared_mime


class StorageService:
    def __init__(self, provider: StorageProvider | None = None):
        if provider is not None:
            self.provider = provider
        elif settings.STORAGE_BACKEND == "s3":
            self.provider = S3StorageProvider(
                bucket_name=settings.S3_BUCKET_NAME,
                endpoint_url=settings.S3_ENDPOINT_URL,
                access_key=settings.S3_ACCESS_KEY,
                secret_key=settings.S3_SECRET_KEY,
                region=settings.S3_REGION,
            )
        else:
            self.provider = LocalStorageProvider(base_dir=settings.LOCAL_STORAGE_DIR)

    def validate_file(
        self,
        filename: str,
        declared_mime: str,
        content: bytes,
    ) -> tuple[str, str]:
        """Validate filename, magic bytes signature, size limits, and determine media_type.

        Returns (detected_mime, media_type).
        """
        # 1. Filename & Extension Checks
        clean_ext = Path(filename).suffix.lower()
        if clean_ext in settings.DANGEROUS_EXTENSIONS:
            raise InvalidAttachmentError(f"File type {clean_ext} is strictly prohibited")

        # 2. Content & Header Signature Check
        if not content:
            raise InvalidAttachmentError("Uploaded file cannot be empty")

        header = content[:32]
        detected_mime = detect_mime_from_content(header, declared_mime)

        # 3. Categorize Media Type & Validate Allowed Whitelist
        if detected_mime in settings.ALLOWED_IMAGE_MIMES:
            media_type = "image"
            max_size = settings.MAX_IMAGE_SIZE_BYTES
        elif detected_mime in settings.ALLOWED_AUDIO_MIMES:
            media_type = "audio"
            max_size = settings.MAX_AUDIO_SIZE_BYTES
        elif detected_mime in settings.ALLOWED_FILE_MIMES:
            media_type = "file"
            max_size = settings.MAX_FILE_SIZE_BYTES
        else:
            raise InvalidAttachmentError(
                f"Unsupported file format: {detected_mime}. Allowed types: images, audio, documents."
            )

        # 4. Check Size Limit
        if len(content) > max_size:
            max_mb = max_size // (1024 * 1024)
            raise InvalidAttachmentError(
                f"{media_type.capitalize()} exceeds maximum allowed size of {max_mb} MB"
            )

        return detected_mime, media_type

    def generate_storage_key(self, room_id: uuid.UUID, original_filename: str) -> str:
        """Generate random, unguessable storage key scoped by room UUID."""
        ext = Path(original_filename).suffix.lower()
        random_name = f"{uuid.uuid4().hex}{ext}"
        return f"{room_id}/{random_name}"

    async def save_media(
        self,
        storage_key: str,
        content: bytes,
        mime_type: str,
    ) -> int:
        return await self.provider.save(content, storage_key, mime_type)

    async def stream_media(self, storage_key: str) -> AsyncGenerator[bytes, None]:
        async for chunk in self.provider.get_stream(storage_key):
            yield chunk

    async def delete_media(self, storage_key: str) -> bool:
        return await self.provider.delete(storage_key)

    async def delete_many(self, storage_keys: list[str]) -> tuple[int, list[str]]:
        return await self.provider.delete_many(storage_keys)


default_storage_service = StorageService()
