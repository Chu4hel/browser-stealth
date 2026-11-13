"""Валидация и санация аргументов командной строки Chromium.

Модуль защищает от передачи устаревших и скомпрометированных флагов запуска,
которые в современных версиях Chromium:

* показывают системный инфобар «Вы используете неподдерживаемый флаг командной
  строки»;
* мгновенно демаскируют автоматизацию перед антибот-системами;
* нарушают геометрию видимой области (viewport) из-за плашки предупреждения.

Скрытие признаков автоматизации в ``browser-stealth`` реализовано через
CDP-инъекции, поэтому перечисленные флаги не нужны и подлежат удалению.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from browser_stealth.exceptions import UnsupportedBrowserFlagError
from browser_stealth.logging import get_logger

logger = get_logger(__name__)


class FlagPolicy(enum.StrEnum):
    """Поведение при обнаружении неподдерживаемых флагов Chromium."""

    SANITIZE = "sanitize"
    """Удалить опасные флаги (или их токены) и записать предупреждение в лог."""

    ERROR = "error"
    """Прервать запуск, выбросив :class:`UnsupportedBrowserFlagError`."""

    IGNORE = "ignore"
    """Передать аргументы как есть, только записав предупреждение.

    Режим предназначен для диагностики и не рекомендуется в production.
    """


@dataclass(frozen=True, slots=True)
class UnsupportedFlagRule:
    """Правило обнаружения неподдерживаемого флага Chromium.

    Attributes:
        flag: Каноническое имя флага (без значения).
        reason: Причина, по которой флаг считается опасным.
        feature: Имя токена Blink-фичи, если флаг принимает список фич
            (например, ``AutomationControlled`` для ``--disable-blink-features``).
    """

    flag: str
    reason: str
    feature: str | None = None


@dataclass(frozen=True, slots=True)
class UnsupportedFlag:
    """Обнаруженный неподдерживаемый аргумент запуска.

    Attributes:
        argument: Исходный аргумент в том виде, в котором он был передан.
        rule: Правило, которое сработало при проверке.
    """

    argument: str
    rule: UnsupportedFlagRule

    @property
    def flag(self) -> str:
        """Возвращает каноническое имя обнаруженного флага."""
        return self.rule.flag


#: Реестр известных неподдерживаемых и скомпрометированных флагов Chromium.
UNSUPPORTED_CHROMIUM_FLAGS: tuple[UnsupportedFlagRule, ...] = (
    UnsupportedFlagRule(
        flag="--disable-blink-features",
        feature="AutomationControlled",
        reason=(
            "Флаг --disable-blink-features=AutomationControlled вызывает системный "
            "инфобар Chromium, демаскирует автоматизацию и нарушает геометрию viewport. "
            "navigator.webdriver уже скрывается CDP-инъекцией browser-stealth."
        ),
    ),
    UnsupportedFlagRule(
        flag="--use-fake-ui-for-media-stream",
        reason=(
            "Автоматическое согласие на доступ к камере и микрофону создаёт аномалии "
            "Permissions API и детектируется антибот-системами."
        ),
    ),
    UnsupportedFlagRule(
        flag="--use-fake-device-for-media-stream",
        reason=(
            "Подмена устройств захвата медиа оставляет характерные артефакты "
            "в enumerateDevices() и WebRTC-отпечатке."
        ),
    ),
    UnsupportedFlagRule(
        flag="--enable-automation",
        reason=(
            "Флаг включает инфобар «Chrome управляется автоматизированным ПО» "
            "и выставляет маркеры автоматизации."
        ),
    ),
    UnsupportedFlagRule(
        flag="--headless=old",
        reason=(
            "Старый headless-режим удалён из современных версий Chromium; "
            "используйте --headless=new или параметр headless=True."
        ),
    ),
    UnsupportedFlagRule(
        flag="--headless=chrome",
        reason=(
            "Псевдорежим --headless=chrome удалён из современных версий Chromium; "
            "используйте --headless=new или параметр headless=True."
        ),
    ),
)


def _split_flag(argument: str) -> tuple[str, str | None]:
    """Разделяет аргумент на имя флага и его значение.

    Args:
        argument: Аргумент командной строки Chromium.

    Returns:
        Кортеж ``(имя, значение)``; значение равно ``None``, если оно не указано.
    """
    name, separator, value = argument.partition("=")
    return name, value if separator else None


def _find_matching_rule(argument: str) -> UnsupportedFlagRule | None:
    """Возвращает первое правило, которому соответствует аргумент.

    Args:
        argument: Аргумент командной строки Chromium.

    Returns:
        Совпавшее правило или ``None``.
    """
    for rule in UNSUPPORTED_CHROMIUM_FLAGS:
        name, value = _split_flag(argument)
        if rule.feature is None:
            if argument == rule.flag or name == rule.flag:
                return rule
            continue
        if name != rule.flag:
            continue
        if value is None:
            continue
        tokens = {token.strip() for token in value.split(",")}
        if rule.feature in tokens:
            return rule
    return None


def find_unsupported_flags(arguments: Sequence[str]) -> tuple[UnsupportedFlag, ...]:
    """Находит неподдерживаемые флаги Chromium в списке аргументов.

    Функция не изменяет аргументы и подходит для статического анализа
    и диагностики конфигурации запуска.

    Args:
        arguments: Аргументы командной строки Chromium.

    Returns:
        Кортеж обнаруженных нарушений в порядке передачи аргументов.
    """
    violations: list[UnsupportedFlag] = []
    for argument in arguments:
        rule = _find_matching_rule(argument)
        if rule is not None:
            violations.append(UnsupportedFlag(argument=argument, rule=rule))
    return tuple(violations)


def _sanitize_argument(argument: str, rule: UnsupportedFlagRule) -> str | None:
    """Удаляет опасный флаг или его токен из аргумента.

    Для флагов со списком Blink-фич удаляется только опасный токен, чтобы
    сохранить остальные запрошенные пользователем фичи.

    Args:
        argument: Исходный аргумент командной строки.
        rule: Сработавшее правило.

    Returns:
        Очищенный аргумент или ``None``, если аргумент нужно удалить целиком.
    """
    if rule.feature is None:
        return None
    prefix = f"{rule.flag}="
    if not argument.startswith(prefix):
        return None
    tokens = [token.strip() for token in argument[len(prefix) :].split(",")]
    kept = [token for token in tokens if token and token != rule.feature]
    if not kept:
        return None
    return f"{prefix}{','.join(kept)}"


def _log_violations(violations: Sequence[UnsupportedFlag], *, sanitize: bool) -> None:
    """Записывает обнаруженные нарушения в лог.

    Args:
        violations: Обнаруженные неподдерживаемые аргументы.
        sanitize: ``True``, если аргументы будут очищены; ``False`` — если переданы как есть.
    """
    for violation in violations:
        action = "будет очищен" if sanitize else "передан без изменений"
        logger.warning(
            "Неподдерживаемый аргумент Chromium %r %s: %s",
            violation.argument,
            action,
            violation.rule.reason,
        )


def sanitize_browser_args(
    arguments: Sequence[str],
    *,
    policy: FlagPolicy | str = FlagPolicy.SANITIZE,
) -> list[str]:
    """Проверяет и очищает аргументы запуска Chromium.

    Args:
        arguments: Аргументы командной строки Chromium.
        policy: Поведение при обнаружении неподдерживаемых флагов:

            * :attr:`FlagPolicy.SANITIZE` (по умолчанию) — удалить опасные флаги
              и записать предупреждение;
            * :attr:`FlagPolicy.ERROR` — выбросить
              :class:`~browser_stealth.exceptions.UnsupportedBrowserFlagError`;
            * :attr:`FlagPolicy.IGNORE` — оставить аргументы без изменений,
              записав предупреждение (диагностика).

    Returns:
        Новый список безопасных аргументов запуска.

    Raises:
        UnsupportedBrowserFlagError: Если ``policy=FlagPolicy.ERROR`` и найдены
            неподдерживаемые флаги.
        ValueError: Если передано неизвестное значение ``policy``.
    """
    mode = FlagPolicy(policy)
    source = list(arguments)
    violations = find_unsupported_flags(source)
    if not violations:
        return source

    if mode is FlagPolicy.ERROR:
        raise UnsupportedBrowserFlagError(
            flags=[violation.argument for violation in violations],
        )

    _log_violations(violations, sanitize=mode is FlagPolicy.SANITIZE)
    if mode is FlagPolicy.IGNORE:
        return source

    sanitized: list[str] = []
    for argument in source:
        rule = _find_matching_rule(argument)
        if rule is None:
            sanitized.append(argument)
            continue
        cleaned = _sanitize_argument(argument, rule)
        if cleaned is not None:
            sanitized.append(cleaned)
    return sanitized


def raise_for_unsupported_flags(arguments: Iterable[str]) -> None:
    """Выбрасывает исключение, если найдены неподдерживаемые флаги Chromium.

    Удобно для строгой валидации в тестах и линтерах конфигурации запуска.

    Args:
        arguments: Аргументы командной строки Chromium.

    Raises:
        UnsupportedBrowserFlagError: Если обнаружен хотя бы один опасный флаг.
    """
    violations = find_unsupported_flags(list(arguments))
    if violations:
        raise UnsupportedBrowserFlagError(
            flags=[violation.argument for violation in violations],
        )


__all__ = [
    "UNSUPPORTED_CHROMIUM_FLAGS",
    "FlagPolicy",
    "UnsupportedFlag",
    "UnsupportedFlagRule",
    "find_unsupported_flags",
    "raise_for_unsupported_flags",
    "sanitize_browser_args",
]
