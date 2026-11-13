"""Снимок экрана вкладки для визуальной проверки вёрстки."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from browser_stealth.exceptions import InspectionError
from browser_stealth.fs import ensure_dir


async def screenshot(
    tab: Any,
    path: Path | str | None = None,
    *,
    full_page: bool = False,
    image_format: str = "png",
    as_base64: bool = False,
    timeout: float = 15.0,
) -> str:
    """Делает снимок экрана вкладки и возвращает путь к файлу или base64.

    Используется для визуальной проверки вёрстки, когда семантического снимка
    недостаточно: изображения, canvas, сложные сетки. Снимок делается штатным
    CDP-методом браузера и не меняет фингерпринт страницы.

    Args:
        tab: Вкладка nodriver с методом ``save_screenshot``.
        path: Путь к файлу; None — браузер выберет имя автоматически.
        full_page: Захватывать ли страницу целиком, а не только видимую область.
        image_format: Формат изображения (``png`` или ``jpeg``).
        as_base64: Вернуть base64-строку вместо пути к файлу.
        timeout: Таймаут снимка в секундах.

    Returns:
        Путь к сохранённому файлу или base64-строка.

    Raises:
        InspectionError: Если вкладка не поддерживает снимки, запись завершилась
            ошибкой или превышен таймаут.

    Example:
        >>> from browser_stealth import inspect
        >>> png_path = await inspect.screenshot(tab, "page.png")
    """
    save_screenshot = getattr(tab, "save_screenshot", None)
    if not callable(save_screenshot):
        raise InspectionError("Вкладка не поддерживает save_screenshot.")

    target: str = "auto"
    if path is not None:
        target_path = Path(path)
        if target_path.parent and str(target_path.parent) not in ("", "."):
            ensure_dir(target_path.parent)
        target = str(target_path)

    try:
        result = save_screenshot(
            target,
            format=image_format,
            full_page=full_page,
            as_base64=as_base64,
        )
        if asyncio.iscoroutine(result):
            result = await asyncio.wait_for(result, timeout=timeout)
    except TimeoutError as exc:
        raise InspectionError(f"Таймаут снимка экрана за {timeout} с.") from exc
    except Exception as exc:
        raise InspectionError(f"Не удалось сделать снимок экрана: {exc}") from exc

    if not isinstance(result, str):
        raise InspectionError(f"Неожиданный ответ save_screenshot: {type(result).__name__}.")
    return result


__all__ = ["screenshot"]
