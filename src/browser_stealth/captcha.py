"""Снимки графической капчи и HITL-ожидание её ручного решения.

Изображение читается из уже загруженного DOM через Canvas и `toDataURL`, поэтому
повторный HTTP-запрос не создаётся и сервер не аннулирует токен капчи. Модуль не
распознаёт текст капчи: он готовит снимок для человека или внешнего OCR-сервиса и
умеет ждать, пока пользователь решит капчу вручную.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import inspect
import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, Field

from browser_stealth.fs import atomic_write, ensure_dir
from browser_stealth.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CAPTCHA_SELECTORS: tuple[str, ...] = (
    'img[data-qa="account-captcha-picture"]',
    'img[src*="/captcha/picture"]',
    'img[src*="/captcha"]',
    'img[class*="hhcaptcha-picture"]',
    'img[class*="captcha"]',
)


class CaptchaSnapshot(BaseModel):
    """Снимок графической капчи, полученный без повторного HTTP-запроса."""

    found: bool = False
    loaded: bool = False
    src: str = ""
    captcha_key: str = ""
    data_url: str = ""
    image_bytes: bytes = b""
    sha256: str = ""
    width: int = 0
    height: int = 0
    selectors: list[str] = Field(default_factory=list)


def extract_captcha_key(src: str) -> str:
    """Извлекает параметр ``key`` из URL изображения капчи."""
    if not src:
        return ""
    values = parse_qs(urlsplit(src).query).get("key", [])
    return str(values[0]).strip() if values else ""


def _captcha_js(selectors: Sequence[str]) -> str:
    """Создаёт JavaScript для поиска и Canvas-снимка капчи."""
    selectors_json = json.dumps(list(selectors), ensure_ascii=False)
    return f"""
    (() => {{
      const selectors = {selectors_json};
      let img = null;
      for (const selector of selectors) {{
        try {{
          const candidate = document.querySelector(selector);
          if (candidate) {{ img = candidate; break; }}
        }} catch (e) {{}}
      }}
      const fallback = !img && document.querySelector(
        'iframe[src*="captcha"], [data-qa*="captcha"], [class*="captcha"]'
      );
      if (!img) {{
        return JSON.stringify({{
          found: Boolean(fallback),
          loaded: false,
          image: false,
          src: '',
          width: 0,
          height: 0,
          data_url: ''
        }});
      }}
      const src = String(img.currentSrc || img.src || img.getAttribute('src') || '');
      const loaded = Boolean(img.complete && img.naturalWidth > 0 && img.naturalHeight > 0);
      let dataUrl = '';
      if (loaded) {{
        try {{
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          const context = canvas.getContext('2d');
          if (context) {{
            context.fillStyle = '#FFFFFF';
            context.fillRect(0, 0, canvas.width, canvas.height);
            context.drawImage(img, 0, 0);
            dataUrl = canvas.toDataURL('image/png');
          }}
        }} catch (e) {{}}
      }}
      return JSON.stringify({{
        found: true,
        loaded: loaded,
        image: true,
        src: src,
        width: loaded ? img.naturalWidth : 0,
        height: loaded ? img.naturalHeight : 0,
        data_url: dataUrl
      }});
    }})()
    """


def _parse_captcha_payload(raw: Any) -> dict[str, Any] | None:
    """Приводит ответ evaluate к словарю снимка."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None
    return raw if isinstance(raw, dict) else None


async def _read_captcha_payload(
    tab: Any,
    selectors: Sequence[str],
    *,
    timeout: float,
) -> dict[str, Any] | None:
    """Выполняет JavaScript капчи и возвращает разобранный ответ."""
    evaluate = getattr(tab, "evaluate", None)
    if not callable(evaluate):
        return None
    try:
        raw = await asyncio.wait_for(evaluate(_captcha_js(selectors)), timeout=timeout)
    except TimeoutError:
        logger.debug("Таймаут снимка капчи")
        return None
    except Exception as exc:
        logger.debug("Не удалось прочитать капчу: %s", exc)
        return None
    return _parse_captcha_payload(raw)


def _snapshot_from_payload(
    payload: dict[str, Any],
    selectors: Sequence[str],
) -> CaptchaSnapshot:
    """Создаёт модель снимка и декодирует Canvas PNG."""
    src = str(payload.get("src") or "")
    data_url = str(payload.get("data_url") or "")
    image_bytes = b""
    if payload.get("loaded") and data_url:
        encoded = data_url.split(",", 1)[1] if "," in data_url else data_url
        try:
            image_bytes = base64.b64decode(encoded, validate=False)
        except (ValueError, binascii.Error):
            image_bytes = b""
    return CaptchaSnapshot(
        found=bool(payload.get("found", False)),
        loaded=bool(payload.get("loaded", False) and image_bytes),
        src=src,
        captcha_key=extract_captcha_key(src),
        data_url=data_url,
        image_bytes=image_bytes,
        sha256=hashlib.sha256(image_bytes).hexdigest() if image_bytes else "",
        width=int(payload.get("width") or 0),
        height=int(payload.get("height") or 0),
        selectors=list(selectors),
    )


async def detect_hh_captcha(
    tab: Any,
    *,
    selectors: Sequence[str] | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Определяет наличие графической капчи HH.ru на открытой вкладке.

    Args:
        tab: Вкладка nodriver или совместимый объект с ``evaluate``.
        selectors: Дополнительные CSS-селекторы изображения капчи.
        timeout: Таймаут чтения DOM в секундах.

    Returns:
        Словарь с ``found``, ``loaded``, ``src``, ``captcha_key``, ``width``,
        ``height`` и ``reason``.
    """
    chosen = tuple(selectors) if selectors is not None else DEFAULT_CAPTCHA_SELECTORS
    payload = await _read_captcha_payload(tab, chosen, timeout=timeout)
    if payload is None:
        return {
            "found": False,
            "loaded": False,
            "src": "",
            "captcha_key": "",
            "width": 0,
            "height": 0,
            "reason": "unavailable",
        }
    snapshot = _snapshot_from_payload(payload, chosen)
    reason = "image" if snapshot.loaded else ("container" if snapshot.found else "absent")
    return {
        "found": snapshot.found,
        "loaded": snapshot.loaded,
        "src": snapshot.src,
        "captcha_key": snapshot.captcha_key,
        "width": snapshot.width,
        "height": snapshot.height,
        "reason": reason,
    }


async def captcha_snapshot(
    tab: Any,
    *,
    selectors: Sequence[str] | None = None,
    timeout: float = 5.0,
) -> CaptchaSnapshot:
    """Возвращает снимок капчи из уже загруженного DOM.

    Используется Canvas и ``toDataURL('image/png')``, поэтому картинка не
    запрашивается повторно у сервера. Если капча не найдена или изображение ещё
    не загрузилось, возвращается модель с ``found``/``loaded = False``.

    Args:
        tab: Вкладка nodriver или совместимый объект с ``evaluate``.
        selectors: Дополнительные CSS-селекторы изображения капчи.
        timeout: Таймаут JavaScript в секундах.

    Returns:
        :class:`CaptchaSnapshot` с PNG-байтами и SHA-256.
    """
    chosen = tuple(selectors) if selectors is not None else DEFAULT_CAPTCHA_SELECTORS
    payload = await _read_captcha_payload(tab, chosen, timeout=timeout)
    if payload is None:
        return CaptchaSnapshot(selectors=list(chosen))
    return _snapshot_from_payload(payload, chosen)


capture_captcha_snapshot = captcha_snapshot
"""Алиас :func:`captcha_snapshot` для снимка текущей капчи."""


async def save_captcha_snapshot(
    tab: Any,
    path: Path | str,
    *,
    selectors: Sequence[str] | None = None,
    timeout: float = 5.0,
) -> str | None:
    """Сохраняет PNG-снимок капчи на диск.

    Args:
        tab: Вкладка nodriver.
        path: Путь к PNG-файлу.
        selectors: Дополнительные CSS-селекторы капчи.
        timeout: Таймаут JavaScript в секундах.

    Returns:
        Путь к файлу или ``None``, если капча не найдена/не загрузилась.
    """
    snapshot = await captcha_snapshot(tab, selectors=selectors, timeout=timeout)
    if not snapshot.image_bytes:
        return None
    target = Path(path)
    ensure_dir(target.parent)
    atomic_write(target, snapshot.image_bytes, mode="wb")
    return str(target)


async def wait_for_manual_captcha_resolution(
    tab: Any,
    *,
    timeout: float = 180.0,
    poll_interval: float = 1.0,
    on_status: Callable[[dict[str, Any]], Any] | None = None,
    selectors: Sequence[str] | None = None,
) -> bool:
    """Ждёт, пока пользователь решит капчу вручную.

    Функция опрашивает DOM и возвращает ``True``, когда капча исчезла или
    изображение перестало отображаться. Колбэк ``on_status`` может быть sync или
    async и получает текущий статус с прошедшим временем.

    Args:
        tab: Вкладка nodriver.
        timeout: Максимальное время ожидания в секундах.
        poll_interval: Интервал опроса DOM в секундах.
        on_status: Необязательный колбэк статуса для UI/бота.
        selectors: Дополнительные CSS-селекторы капчи.

    Returns:
        True, если капча решена до таймаута, иначе False.
    """
    if tab is None or timeout <= 0:
        return False
    started = time.monotonic()
    while True:
        status = await detect_hh_captcha(tab, selectors=selectors)
        elapsed = round(time.monotonic() - started, 2)
        status["elapsed"] = elapsed
        status["remaining"] = max(0.0, round(timeout - elapsed, 2))
        if callable(on_status):
            try:
                callback_result = on_status(status)
                if inspect.isawaitable(callback_result):
                    await callback_result
            except Exception as exc:
                logger.debug("Ошибка on_status для капчи: %s", exc)

        if not status.get("found"):
            logger.info("Капча решена вручную за %.1f с", elapsed)
            return True
        if elapsed >= timeout:
            logger.warning("Ручное решение капчи не завершено за %.1f с", timeout)
            return False
        await asyncio.sleep(min(poll_interval, max(0.0, timeout - elapsed)))


__all__ = [
    "DEFAULT_CAPTCHA_SELECTORS",
    "CaptchaSnapshot",
    "captcha_snapshot",
    "capture_captcha_snapshot",
    "detect_hh_captcha",
    "extract_captcha_key",
    "save_captcha_snapshot",
    "wait_for_manual_captcha_resolution",
]
