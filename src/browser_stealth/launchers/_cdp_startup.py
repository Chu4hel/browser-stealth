"""Ожидание готовности CDP-порта Chromium, запущенного через nodriver.

nodriver ждет порт отладки не более ~2.75 с и на медленных CI-раннерах сдается
раньше, чем Chromium успевает его открыть. Здесь ожидание продлевается, а при
реальном падении процесса в ошибку попадает stderr Chromium.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from browser_stealth.logging import get_logger

logger = get_logger(__name__)

STARTUP_TIMEOUT = 20.0
_POLL_INTERVAL = 0.25


def registered_browsers(uc: Any) -> set[Any]:
    """Возвращает зарегистрированные nodriver экземпляры браузера.

    Args:
        uc: Модуль nodriver.

    Returns:
        Множество зарегистрированных экземпляров; пустое, если API недоступно.
    """
    getter = getattr(getattr(uc, "util", None), "get_registered_instances", None)
    if not callable(getter):
        return set()
    try:
        return set(getter())
    except Exception:
        return set()


def pick_pending_browser(uc: Any, known: set[Any]) -> Any | None:
    """Находит экземпляр браузера, созданный неудачной попыткой ``uc.start``.

    Args:
        uc: Модуль nodriver.
        known: Экземпляры, существовавшие до попытки запуска.

    Returns:
        Новый экземпляр браузера или ``None``, если его нет.
    """
    pending = [b for b in registered_browsers(uc) - known if getattr(b, "info", None) is None]
    if not pending:
        return None
    with_process = [b for b in pending if getattr(b, "_process", None) is not None]
    return (with_process or pending)[-1]


async def collect_process_stderr(process: Any) -> str:
    """Завершает процесс Chromium и читает накопленный stderr для диагностики.

    Args:
        process: Процесс Chromium (``asyncio.subprocess.Process``).

    Returns:
        Текст stderr без обрезки; пустая строка, если прочитать не удалось.
    """
    if process is None:
        return ""
    if getattr(process, "returncode", None) is None:
        kill = getattr(process, "kill", None)
        if callable(kill):
            try:
                kill()
            except Exception:
                pass
        wait = getattr(process, "wait", None)
        if callable(wait):
            try:
                await asyncio.wait_for(wait(), timeout=2.0)
            except Exception:
                pass
    stderr = getattr(process, "stderr", None)
    reader = getattr(stderr, "read", None)
    if not callable(reader):
        return ""
    try:
        raw = await asyncio.wait_for(reader(), timeout=2.0)
    except Exception:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace").strip()
    return str(raw).strip()


async def await_cdp_ready(uc: Any, browser: Any, *, timeout: float | None = None) -> Any:
    """Дожидается порта CDP уже запущенного Chromium и завершает подключение.

    Повторяет завершающую часть ``nodriver.Browser.start``, но с собственным
    таймаутом ожидания и диагностикой причин неудачи.

    Args:
        uc: Модуль nodriver.
        browser: Экземпляр браузера, созданный ``uc.start`` до ошибки подключения.
        timeout: Максимальное время ожидания порта CDP в секундах.

    Returns:
        Подключенный экземпляр браузера.

    Raises:
        RuntimeError: Если порт CDP не открылся или процесс Chromium завершился.
    """
    limit = STARTUP_TIMEOUT if timeout is None else timeout
    http = getattr(browser, "_http", None)
    if http is None:
        raise RuntimeError("nodriver не создал HTTP-клиент CDP для запущенного Chromium")

    process = getattr(browser, "_process", None)
    deadline = time.monotonic() + limit
    info: Any = None
    while time.monotonic() < deadline:
        returncode = getattr(process, "returncode", None)
        if returncode is not None:
            break
        try:
            info = uc.ContraDict(
                await asyncio.wait_for(http.get("version"), timeout=2.0), silent=True
            )
        except Exception:
            info = None
        if info:
            break
        await asyncio.sleep(_POLL_INTERVAL)

    if not info:
        returncode = getattr(process, "returncode", None)
        stderr_text = await collect_process_stderr(process)
        reason = (
            f"Chromium завершился с кодом {returncode}"
            if returncode is not None
            else "порт CDP не открылся"
        )
        message = f"Chromium не открыл порт отладки за {limit:.0f} с: {reason}."
        if stderr_text:
            message += f"\nstderr Chromium:\n{stderr_text[-4000:]}"
        raise RuntimeError(message)

    browser.info = info
    browser.websocket_url = info.webSocketDebuggerUrl
    await browser.attach()
    await browser.update_targets()
    logger.info("Chromium открыл порт CDP после штатного таймаута nodriver, подключение завершено")
    return browser


__all__ = [
    "STARTUP_TIMEOUT",
    "await_cdp_ready",
    "collect_process_stderr",
    "pick_pending_browser",
    "registered_browsers",
]
