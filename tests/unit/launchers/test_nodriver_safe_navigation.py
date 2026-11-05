from unittest.mock import AsyncMock, MagicMock

import pytest

from browser_stealth.launchers.nodriver import (
    safe_extract_dict,
    safe_get_or_open_tab,
    unpack_cdp_value,
)


@pytest.mark.asyncio
async def test_safe_get_or_open_tab_normal() -> None:
    browser = MagicMock()
    mock_target = MagicMock()
    mock_target.target.type_ = "page"
    browser.targets = [mock_target]
    mock_tab = MagicMock()
    browser.get = AsyncMock(return_value=mock_tab)

    tab = await safe_get_or_open_tab(browser, "https://example.com", timeout=1.0)
    assert tab == mock_tab
    browser.get.assert_awaited_once_with("https://example.com")


@pytest.mark.asyncio
async def test_safe_get_or_open_tab_stop_iteration_fallback() -> None:
    browser = MagicMock()
    browser.targets = []
    mock_tab = MagicMock()

    async def _mock_get(url: str, new_tab: bool = False):
        if not new_tab:
            raise RuntimeError("coroutine raised StopIteration")
        return mock_tab

    browser.get = AsyncMock(side_effect=_mock_get)

    tab = await safe_get_or_open_tab(browser, "https://example.com", timeout=0.1)
    assert tab == mock_tab
    assert browser.get.await_count == 2


def test_safe_extract_dict_variants() -> None:
    # 1. Dict
    assert safe_extract_dict({"a": 1}) == {"a": 1}

    # 2. JSON str
    assert safe_extract_dict('{"b": 2}') == {"b": 2}

    # 3. Invalid str
    assert safe_extract_dict("invalid json") == {}

    # 4. List of key-value pairs
    pairs = [["key1", {"value": "val1"}], ["key2", "val2"]]
    extracted = safe_extract_dict(pairs)
    assert extracted == {"key1": "val1", "key2": "val2"}


def test_unpack_cdp_value() -> None:
    nested = {"value": {"a": {"value": 123}}}
    assert unpack_cdp_value(nested) == {"a": 123}
