"""Тесты Canvas-снимков капчи и HITL-ожидания."""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from browser_stealth.captcha import (
    CaptchaSnapshot,
    captcha_snapshot,
    detect_hh_captcha,
    extract_captcha_key,
    save_captcha_snapshot,
    wait_for_manual_captcha_resolution,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-captcha"
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode("ascii")


class FakeCaptchaTab:
    """Вкладка, возвращающая последовательность ответов evaluate."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.index = 0
        self.scripts: list[str] = []

    async def evaluate(self, script: str) -> Any:
        self.scripts.append(script)
        if self.index >= len(self.responses):
            return json.dumps({"found": False, "loaded": False, "data_url": ""})
        value = self.responses[self.index]
        self.index += 1
        return value


def _payload(**overrides: Any) -> dict[str, Any]:
    """Создаёт ответ JS с изображением капчи."""
    data = {
        "found": True,
        "loaded": True,
        "image": True,
        "src": "https://hh.ru/captcha/picture?key=abc123",
        "width": 120,
        "height": 40,
        "data_url": PNG_DATA_URL,
    }
    data.update(overrides)
    return data


def test_extract_captcha_key_from_url() -> None:
    """Ключ извлекается из query-параметра key."""
    assert extract_captcha_key("https://hh.ru/captcha/picture?key=abc123") == "abc123"
    assert extract_captcha_key("https://hh.ru/captcha/picture") == ""


@pytest.mark.asyncio
async def test_captcha_snapshot_decodes_canvas_png_without_http() -> None:
    """Снимок берёт base64 из Canvas и считает SHA-256."""
    tab = FakeCaptchaTab([json.dumps(_payload())])

    snapshot = await captcha_snapshot(tab)

    assert isinstance(snapshot, CaptchaSnapshot)
    assert snapshot.found is True
    assert snapshot.loaded is True
    assert snapshot.image_bytes == PNG_BYTES
    assert snapshot.captcha_key == "abc123"
    assert len(snapshot.sha256) == 64
    assert "toDataURL" in tab.scripts[0]
    assert "fetch(" not in tab.scripts[0]


@pytest.mark.asyncio
async def test_detect_hh_captcha_distinguishes_container_and_absent() -> None:
    """Детектор различает загруженную, контейнерную и отсутствующую капчу."""
    image_tab = FakeCaptchaTab([json.dumps(_payload())])
    container_tab = FakeCaptchaTab(
        [json.dumps({"found": True, "loaded": False, "src": "", "data_url": ""})]
    )
    absent_tab = FakeCaptchaTab([json.dumps({"found": False, "loaded": False})])

    assert (await detect_hh_captcha(image_tab))["reason"] == "image"
    assert (await detect_hh_captcha(container_tab))["reason"] == "container"
    assert (await detect_hh_captcha(absent_tab))["reason"] == "absent"


@pytest.mark.asyncio
async def test_save_captcha_snapshot_writes_png(tmp_path) -> None:
    """Снимок сохраняется на диск атомарно."""
    tab = FakeCaptchaTab([json.dumps(_payload())])
    target = tmp_path / "captcha" / "current.png"

    saved = await save_captcha_snapshot(tab, target)

    assert saved == str(target)
    assert target.read_bytes() == PNG_BYTES


@pytest.mark.asyncio
async def test_wait_for_manual_captcha_resolution_polls_until_absent() -> None:
    """Ожидание возвращает True после исчезновения капчи и зовёт callback."""
    tab = FakeCaptchaTab(
        [
            json.dumps(_payload()),
            json.dumps({"found": False, "loaded": False}),
        ]
    )
    statuses: list[dict[str, Any]] = []

    resolved = await wait_for_manual_captcha_resolution(
        tab,
        timeout=2.0,
        poll_interval=0.0,
        on_status=statuses.append,
    )

    assert resolved is True
    assert len(statuses) == 2
    assert statuses[0]["found"] is True
    assert statuses[1]["found"] is False
    assert "elapsed" in statuses[0]


@pytest.mark.asyncio
async def test_wait_for_manual_captcha_resolution_returns_false_on_timeout() -> None:
    """При неустранённой капче ожидание завершается False."""
    tab = FakeCaptchaTab([json.dumps(_payload()) for _ in range(100)])

    resolved = await wait_for_manual_captcha_resolution(
        tab,
        timeout=0.01,
        poll_interval=0.005,
    )

    assert resolved is False
