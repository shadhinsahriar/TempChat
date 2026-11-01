"""Security and cryptography utilities."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

# Argon2id password hasher with secure memory-hard defaults
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# Unambiguous characters for readable invitation codes (no 0, O, 1, I, L)
INVITE_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def hash_password(password: str) -> str:
    """Hash a plaintext room password using Argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext room password against its Argon2id hash."""
    try:
        return _hasher.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError):
        return False


def generate_guest_token() -> str:
    """Generate a cryptographically secure 256-bit guest token."""
    return secrets.token_urlsafe(32)


def hash_guest_token(token: str) -> str:
    """Compute the SHA-256 hex digest of a guest token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_guest_token(raw_token: str, token_hash: str) -> bool:
    """Constant-time verification of a raw token against its stored hash."""
    computed_hash = hash_guest_token(raw_token)
    return secrets.compare_digest(computed_hash, token_hash)


def generate_invite_code(length: int = 6) -> str:
    """Generate a cryptographically random, human-friendly invitation code."""
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(length))


def generate_event_id() -> str:
    """Generate a unique event identifier for WebSocket events."""
    return f"evt_{secrets.token_hex(8)}"


def generate_ticket() -> str:
    """Generate a single-use WebSocket ticket."""
    return secrets.token_urlsafe(32)
