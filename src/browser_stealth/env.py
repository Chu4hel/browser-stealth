"""Управление сетевым окружением для локальных соединений с браузером.

Chromium DevTools Protocol и WebSocket nodriver работают через loopback-адреса.
Если в системе задан `HTTP_PROXY`/`HTTPS_PROXY`, часть HTTP-клиентов может
отправить запрос к CDP через корпоративный прокси и заблокировать подключение.
Функция :func:`ensure_local_no_proxy` гарантирует, что loopback-адреса исключены
из проксирования в обеих переменных — `NO_PROXY` и `no_proxy`.
"""

from __future__ import annotations

import os

LOCAL_NO_PROXY_HOSTS: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")
"""Локальные адреса, которые всегда должны обходить системный прокси."""


def ensure_local_no_proxy() -> None:
    """Добавляет loopback-адреса в `NO_PROXY` и `no_proxy`.

    Существующие записи сохраняются, лишние пробелы удаляются, дубликаты не
    добавляются. Функция идемпотентна и безопасна при повторных вызовах.

    Note:
        Прямая запись в `os.environ` необходима: переменные влияют на сетевые
        клиенты процесса, а не только на код библиотеки.
    """
    for key in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(key, "")  # chutils: ignore[ChutilsIntegrationRule]
        entries = [part.strip() for part in current.split(",") if part.strip()]
        known = {part.casefold() for part in entries}
        for host in LOCAL_NO_PROXY_HOSTS:
            if host.casefold() not in known:
                entries.append(host)
                known.add(host.casefold())
        os.environ[key] = ",".join(entries)  # chutils: ignore[ChutilsIntegrationRule]


__all__ = ["LOCAL_NO_PROXY_HOSTS", "ensure_local_no_proxy"]
