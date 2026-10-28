import sys
from unittest.mock import AsyncMock, MagicMock
import pytest

from browser_stealth.antidetect.clipboard import (
    INSTALL_CLIPBOARD_HOOK_JS,
    apply_clipboard_isolation,
    get_isolated_clipboard_text,
)


@pytest.mark.asyncio
async def test_apply_clipboard_isolation_none() -> None:
    assert await apply_clipboard_isolation(None) is False
    assert await get_isolated_clipboard_text(None) is None


@pytest.mark.asyncio
async def test_apply_clipboard_isolation_playwright() -> None:
    page = MagicMock()
    del page.send
    page.add_init_script = AsyncMock()
    page.evaluate = AsyncMock(return_value=True)

    result = await apply_clipboard_isolation(page)
    assert result is True
    page.add_init_script.assert_awaited_once_with(INSTALL_CLIPBOARD_HOOK_JS)
    page.evaluate.assert_awaited_once_with(INSTALL_CLIPBOARD_HOOK_JS)


@pytest.mark.asyncio
async def test_apply_clipboard_isolation_nodriver(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_cdp_page = MagicMock()
    mock_cdp_page.add_script_to_evaluate_on_new_document.return_value = "cdp_cmd"
    monkeypatch.setitem(sys.modules, "nodriver.cdp", MagicMock(page=mock_cdp_page))
    monkeypatch.setitem(sys.modules, "nodriver.cdp.page", mock_cdp_page)

    tab = MagicMock()
    tab.send = AsyncMock()
    tab.evaluate = AsyncMock(return_value=True)
    del tab.add_init_script

    result = await apply_clipboard_isolation(tab)
    assert result is True
    assert tab.send.await_count == 1
    assert tab.evaluate.await_count == 1



@pytest.mark.asyncio
async def test_get_isolated_clipboard_text() -> None:
    tab = MagicMock()
    tab.evaluate = AsyncMock(return_value="copied text content")
    text = await get_isolated_clipboard_text(tab)
    assert text == "copied text content"
