"""Tests for security and cryptography utilities."""

from app.core.security import (
    INVITE_CODE_ALPHABET,
    generate_event_id,
    generate_guest_token,
    generate_invite_code,
    generate_ticket,
    hash_guest_token,
    hash_password,
    verify_guest_token,
    verify_password,
)


def test_argon2_password_hashing():
    password = "secret_room_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_guest_token_generation_and_verification():
    token = generate_guest_token()
    assert len(token) >= 32

    token_hash = hash_guest_token(token)
    assert len(token_hash) == 64  # SHA-256 hex string

    assert verify_guest_token(token, token_hash) is True
    assert verify_guest_token("different_token", token_hash) is False


def test_invite_code_generation():
    code1 = generate_invite_code(6)
    code2 = generate_invite_code(6)

    assert len(code1) == 6
    assert len(code2) == 6
    assert code1 != code2  # Unpredictable
    for char in code1:
        assert char in INVITE_CODE_ALPHABET


def test_ticket_and_event_id_generation():
    ticket = generate_ticket()
    event_id = generate_event_id()

    assert len(ticket) >= 32
    assert event_id.startswith("evt_")
