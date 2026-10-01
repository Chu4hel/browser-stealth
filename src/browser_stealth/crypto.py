"""Модуль для портативного детерминированного шифрования данных профилей."""

from __future__ import annotations

import base64
import hashlib

from browser_stealth.exceptions import OptionalDependencyError

try:
    from cryptography.fernet import Fernet, InvalidToken

    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[assignment,misc]
    InvalidToken = None  # type: ignore[assignment,misc]
    _HAS_CRYPTOGRAPHY = False

__all__ = ["decrypt_portable", "encrypt_portable"]


def _get_fernet_key(seed: str) -> bytes:
    """Генерирует детерминированный 32-байтный URL-safe Base64 ключ из seed-строки."""
    hash_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(hash_bytes)


def encrypt_portable(data: str, seed: str) -> str:
    """Шифрует строку с использованием детерминированного ключа, полученного из seed."""
    if not _HAS_CRYPTOGRAPHY or Fernet is None:
        raise OptionalDependencyError(
            "Для использования шифрования установите библиотеку cryptography:\n"
            "pip install browser-stealth[crypto]",
            dependency="cryptography",
            hint="Выполните pip install browser-stealth[crypto]",
        )

    key = _get_fernet_key(seed)
    f = Fernet(key)
    encrypted_bytes = f.encrypt(data.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_portable(
    encrypted_data: str, seed: str, raise_on_error: bool = False
) -> str | None:
    """Дешифрует строку с использованием детерминированного ключа, полученного из seed."""
    if not _HAS_CRYPTOGRAPHY or Fernet is None:
        raise OptionalDependencyError(
            "Для использования шифрования установите библиотеку cryptography:\n"
            "pip install browser-stealth[crypto]",
            dependency="cryptography",
            hint="Выполните pip install browser-stealth[crypto]",
        )

    key = _get_fernet_key(seed)
    f = Fernet(key)
    try:
        decrypted_bytes = f.decrypt(encrypted_data.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception) as exc:
        if raise_on_error:
            raise ValueError(
                f"Не удалось расшифровать данные: неверный ключ или повреждённый токен ({exc})"
            ) from exc
        return None
