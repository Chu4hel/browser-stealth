"""Исключения библиотеки browser-stealth."""

from __future__ import annotations

from collections.abc import Iterable


class BrowserStealthError(Exception):
    """Базовое исключение для всех ошибок browser-stealth."""


class UnsupportedBrowserFlagError(BrowserStealthError):
    """Исключение, возникающее при передаче неподдерживаемых флагов Chromium.

    Такие флаги вызывают системный инфобар, демаскируют автоматизацию
    и нарушают геометрию viewport.

    Attributes:
        flags: Аргументы запуска, которые были признаны неподдерживаемыми.
    """

    def __init__(
        self,
        flags: Iterable[str] = (),
        *,
        message: str | None = None,
    ) -> None:
        """Инициализирует исключение неподдерживаемых флагов.

        Args:
            flags: Аргументы запуска, которые были признаны неподдерживаемыми.
            message: Пользовательское сообщение об ошибке.
        """
        self.flags = tuple(flags)
        if message is None:
            listed = ", ".join(self.flags) or "<неизвестно>"
            message = (
                f"Обнаружены неподдерживаемые аргументы Chromium: {listed}. "
                "Такие флаги показывают системный инфобар, демаскируют автоматизацию "
                "и нарушают геометрию viewport. Удалите их из browser_args: скрытие "
                "автоматизации уже реализовано через CDP-инъекции browser-stealth."
            )
        super().__init__(message)


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
