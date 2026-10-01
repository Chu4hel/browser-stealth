"""Настройка логирования для browser-stealth."""

from __future__ import annotations

import logging

_ROOT_LOGGER_NAME = "browser_stealth"


def get_logger(name: str | None = None) -> logging.Logger:
    """Возвращает логгер библиотеки browser-stealth.

    Args:
        name: Имя подмодуля (если указано, формируется browser_stealth.<name>).

    Returns:
        Экземпляр logging.Logger.
    """
    if not name:
        return logging.getLogger(_ROOT_LOGGER_NAME)
    if name.startswith(_ROOT_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
