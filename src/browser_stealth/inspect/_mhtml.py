"""Сохранение MHTML-снимка страницы для оффлайн-архива."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from browser_stealth.exceptions import InspectionError
from browser_stealth.fs import atomic_write, ensure_dir


def _capture_snapshot_command() -> Any:
    """Создаёт CDP-команду ``Page.captureSnapshot`` в формате MHTML.

    Returns:
        Генератор CDP-команды для ``Tab.send``.

    Raises:
        InspectionError: Если пакет ``nodriver`` не установлен.
    """
    try:
        from nodriver.cdp import page as cdp_page
    except ImportError as exc:
        raise InspectionError("Для MHTML-снимка требуется установленный nodriver.") from exc
    return cdp_page.capture_snapshot(format_="mhtml")


def _snapshot_data(result: Any) -> str:
    """Извлекает сериализованную страницу из ответа CDP.

    Args:
        result: Ответ ``Tab.send``: строка, объект с ``data`` или словарь.

    Returns:
        Строка MHTML или пустая строка, если ответ не содержит данных.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        data = result.get("data")
    else:
        data = getattr(result, "data", None)
    return data if isinstance(data, str) else ""


async def capture_page_snapshot_mhtml(
    tab: Any,
    *,
    timeout: float = 30.0,
) -> bytes:
    """Возвращает MHTML-снимок страницы как байты.

    Использует CDP ``Page.captureSnapshot(format="mhtml")`` и не выполняет
    повторных HTTP-запросов к ресурсам страницы.

    Args:
        tab: Вкладка nodriver с методом ``send``.
        timeout: Таймаут CDP-вызова в секундах.

    Returns:
        Байты MHTML-документа.

    Raises:
        InspectionError: Если вкладка не поддерживает CDP-вызов, браузер
            вернул пустой снимок или CDP завершился ошибкой.
    """
    send = getattr(tab, "send", None)
    if not callable(send):
        raise InspectionError("Вкладка не поддерживает CDP-метод send.")

    command = _capture_snapshot_command()
    try:
        result = send(command)
        if asyncio.iscoroutine(result):
            result = await asyncio.wait_for(result, timeout=timeout)
    except TimeoutError as exc:
        raise InspectionError(f"Таймаут MHTML-снимка за {timeout} с.") from exc
    except Exception as exc:
        raise InspectionError(f"Не удалось получить MHTML-снимок: {exc}") from exc

    data = _snapshot_data(result)
    if not data:
        raise InspectionError("Браузер вернул пустой MHTML-снимок.")
    return data.encode("utf-8")


async def save_mhtml(
    tab: Any,
    path: Path | str,
    *,
    timeout: float = 30.0,
) -> str:
    """Сохраняет страницу в MHTML-архив и возвращает путь к файлу.

    Архив включает HTML, стили, изображения и вложенные фреймы, поэтому его
    достаточно для оффлайн-просмотра и разбора инцидентов. Снимок делается
    штатным CDP-методом ``Page.captureSnapshot`` и не меняет фингерпринт
    страницы. Выгрузка медиа (``<video>``, аудио, lazy-load галереи) в архив
    не входит: для неё нужна отдельная логика под конкретный сайт.

    Args:
        tab: Вкладка nodriver с методом ``send``.
        path: Путь к сохраняемому файлу (обычно с расширением ``.mhtml``).
        timeout: Таймаут CDP-вызова в секундах.

    Returns:
        Путь к сохранённому файлу в виде строки.

    Raises:
        InspectionError: Если вкладка не поддерживает CDP-вызов, браузер
            вернул пустой снимок или запись файла завершилась ошибкой.

    Example:
        >>> from browser_stealth import inspect
        >>> mhtml_path = await inspect.save_mhtml(tab, "artifacts/page.mhtml")
    """
    data = await capture_page_snapshot_mhtml(tab, timeout=timeout)
    target = Path(path)
    if str(target.parent) not in ("", "."):
        ensure_dir(target.parent)

    try:
        # Бинарная запись сохраняет исходные переводы строк MHTML:
        # текстовый режим на Windows превращает CRLF в CRCRLF.
        atomic_write(target, data, mode="wb")
    except Exception as exc:
        raise InspectionError(f"Не удалось записать MHTML-снимок: {exc}") from exc

    return str(target)


__all__ = ["capture_page_snapshot_mhtml", "save_mhtml"]
