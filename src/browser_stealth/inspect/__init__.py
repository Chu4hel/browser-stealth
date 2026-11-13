"""Read-only инспекция страницы для ИИ-агентов и отладки.

Модуль даёт агенту «глаза» на антидетект-браузер: компактный семантический
снимок страницы, поиск элементов по тексту и роли, снимок экрана и дерево
фреймов. Все функции только читают состояние страницы и не выполняют кликов
или ввода — действия остаются за :mod:`browser_stealth.humanize`, чтобы
события оставались настоящими (``isTrusted=true``).

Example:
    >>> from browser_stealth import inspect, nodriver_session
    >>> async with nodriver_session() as browser:
    ...     tab = await browser.get("https://example.com")
    ...     page = await inspect.snapshot(tab)
    ...     buttons = await inspect.find(tab, role="button", text="Войти")
"""

from __future__ import annotations

from browser_stealth.inspect._find import DEFAULT_LIMIT, find
from browser_stealth.inspect._frames import frames
from browser_stealth.inspect._screenshot import screenshot
from browser_stealth.inspect._snapshot import DEFAULT_MAX_NODES, snapshot

__all__ = [
    "DEFAULT_LIMIT",
    "DEFAULT_MAX_NODES",
    "find",
    "frames",
    "screenshot",
    "snapshot",
]
