"""E2E-тест инспекции реальной страницы в антидетект-браузере.

Проверяет, что snapshot/find/frames/screenshot работают не только на моках:
браузер открывает локальную страницу, модуль inspect описывает её элементы,
находит кнопку, видит вложенный фрейм и сохраняет скриншот.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

# Локальный тестовый сервер не должен уходить в системный прокси
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

from browser_stealth import inspect
from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.launchers.nodriver import nodriver_session, safe_get_or_open_tab
from browser_stealth.testing.server import LocalTestServer

_PAGE_HTML = """
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>Inspect E2E</title></head>
<body>
  <h1>Проверка инспекции</h1>
  <form id="login">
    <label for="email">Почта</label>
    <input id="email" name="email" type="email" placeholder="you@example.com">
    <button id="submit" type="submit">Войти</button>
  </form>
  <a href="/catalog">Каталог</a>
  <button id="hidden" style="display:none">Скрытая кнопка</button>
  <iframe id="widget" title="Виджет" src="{frame_url}"></iframe>
</body>
</html>
"""

_FRAME_HTML = """
<!doctype html>
<html><head><meta charset="utf-8"><title>Frame</title></head>
<body><button id="frame-button">Оплатить</button></body></html>
"""


def _node_by_name(page: dict[str, object], name: str) -> dict[str, object]:
    """Возвращает первый узел снимка с заданным доступным именем."""
    nodes = page.get("nodes", [])
    assert isinstance(nodes, list)
    for node in nodes:
        if isinstance(node, dict) and node.get("name") == name:
            return node
    raise AssertionError(f"В снимке нет узла с именем {name!r}: {nodes}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_inspect_snapshot_find_frames_screenshot_e2e(
    tmp_path: Path,
    e2e_proxy: str | None,
) -> None:
    """Проверяет инспекцию локальной страницы в реальном браузере."""
    with LocalTestServer() as server:
        frame_url = server.serve_html("/frame", _FRAME_HTML)
        page_url = server.serve_html("/page", _PAGE_HTML.format(frame_url=frame_url))

        config = AntidetectConfig.preset_stealth_nodriver()
        async with nodriver_session(config=config, headless=True, proxy=e2e_proxy) as browser:
            tab = await safe_get_or_open_tab(browser, page_url, timeout=10.0)
            await config.apply_to_nodriver(tab)

            # Ждём появления кнопки после загрузки документа
            for _ in range(20):
                if await inspect.find(tab, role="button", text="Войти", limit=1):
                    break
                await asyncio.sleep(0.25)

            page = await inspect.snapshot(tab, max_nodes=100)
            assert page["title"] == "Inspect E2E"
            assert page["url"].startswith(server.url_for("/page"))
            assert page["nodes"]

            submit = _node_by_name(page, "Войти")
            assert submit["role"] == "button"
            assert submit["selector"]
            assert submit["box"][2] > 0 and submit["box"][3] > 0

            email = _node_by_name(page, "you@example.com")
            assert email["role"] == "textbox"
            assert email.get("attrs", {}).get("type") == "email"

            iframe = next(node for node in page["nodes"] if node["role"] == "iframe")
            assert "Виджет" == iframe["name"]

            assert not await inspect.find(tab, text="Скрытая кнопка")

            found = await inspect.find(tab, role="button", text="Войти")
            assert len(found) == 1
            assert found[0]["selector"] == submit["selector"]

            tree = await inspect.frames(tab)
            assert tree[0]["depth"] == 0
            assert tree[0]["url"].startswith(server.url_for("/page"))
            assert any(frame.get("depth", 0) > 0 for frame in tree)

            shot = await inspect.screenshot(tab, tmp_path / "page.png")
            shot_path = Path(shot)
            if not shot_path.is_absolute():
                shot_path = Path.cwd() / shot_path
            assert shot_path.exists()
            assert shot_path.stat().st_size > 0
