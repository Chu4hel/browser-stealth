"""Тесты портативного шифрования (browser_stealth.crypto)."""

from __future__ import annotations

import base64

import pytest

import browser_stealth.crypto as crypto_module
from browser_stealth.crypto import decrypt_portable, encrypt_portable
from browser_stealth.exceptions import OptionalDependencyError


def test_round_trip_returns_original_text() -> None:
    """Проверяет, что шифрование и расшифровка возвращают исходную строку."""
    data = '{"cookies": [{"name": "sid", "value": "abc"}]}'

    token = encrypt_portable(data, seed="profile-a")

    assert token != data
    assert decrypt_portable(token, seed="profile-a") == data


def test_same_seed_decrypts_tokens_with_random_iv() -> None:
    """Проверяет, что Fernet использует случайный IV, но ключ от seed стабилен."""
    first = encrypt_portable("payload", seed="stable")
    second = encrypt_portable("payload", seed="stable")

    assert first != second
    assert decrypt_portable(first, seed="stable") == "payload"
    assert decrypt_portable(second, seed="stable") == "payload"


def test_different_seed_produces_different_token_and_fails_to_decrypt() -> None:
    """Проверяет, что чужой seed не расшифровывает данные."""
    token = encrypt_portable("payload", seed="seed-a")

    assert token != encrypt_portable("payload", seed="seed-b")
    assert decrypt_portable(token, seed="seed-b") is None


def test_unicode_and_empty_string_round_trip() -> None:
    """Проверяет Unicode и пустую строку."""
    assert (
        decrypt_portable(encrypt_portable("Привет, мир 👋", seed="s"), seed="s") == "Привет, мир 👋"
    )
    assert decrypt_portable(encrypt_portable("", seed="s"), seed="s") == ""


def test_decrypt_corrupted_token_returns_none_by_default() -> None:
    """Проверяет мягкую обработку повреждённого токена."""
    assert decrypt_portable("not-a-token", seed="s") is None


def test_decrypt_corrupted_token_raises_when_requested() -> None:
    """Проверяет строгий режим расшифровки."""
    with pytest.raises(ValueError, match="Не удалось расшифровать"):
        decrypt_portable("not-a-token", seed="s", raise_on_error=True)


def test_key_is_32_bytes_urlsafe_base64() -> None:
    """Проверяет формат детерминированного ключа Fernet."""
    key = crypto_module._get_fernet_key("seed")
    raw = base64.urlsafe_b64decode(key)

    assert isinstance(key, bytes)
    assert len(raw) == 32
    assert crypto_module._get_fernet_key("seed") == key


def test_missing_cryptography_raises_optional_dependency_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет понятную ошибку без установленной cryptography."""
    monkeypatch.setattr(crypto_module, "_HAS_CRYPTOGRAPHY", False)
    monkeypatch.setattr(crypto_module, "Fernet", None)

    with pytest.raises(OptionalDependencyError, match="cryptography"):
        encrypt_portable("data", seed="s")

    with pytest.raises(OptionalDependencyError, match="cryptography"):
        decrypt_portable("token", seed="s")
