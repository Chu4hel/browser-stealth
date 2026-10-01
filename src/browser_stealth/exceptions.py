"""Исключения библиотеки browser-stealth."""

from __future__ import annotations


class BrowserStealthError(Exception):
    """Базовое исключение для всех ошибок browser-stealth."""


try:
    from chutils.exceptions.base import OptionalDependencyError as _ChutilsOptionalDependencyError
    _BaseOptionalDependencyError = _ChutilsOptionalDependencyError
except ImportError:
    _BaseOptionalDependencyError = ImportError


class OptionalDependencyError(BrowserStealthError, _BaseOptionalDependencyError):
    """Исключение, возникающее при отсутствии опциональной зависимости библиотеки."""

    def __init__(
        self,
        message: str | None = None,
        *,
        dependency: str = "",
        hint: str | None = None,
    ) -> None:
        """Инициализирует исключение отсутствующей зависимости.

        Args:
            message: Сообщение об ошибке.
            dependency: Имя отсутствующей библиотеки (например, 'playwright', 'nodriver').
            hint: Подсказка по установке (например, 'pip install browser-stealth[playwright]').
        """
        self.dependency = dependency
        self.hint = hint
        if not message:
            message = f"Требуется опциональная зависимость '{dependency}'."
            if hint:
                message += f" {hint}"
        super().__init__(message)
