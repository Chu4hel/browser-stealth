from unittest.mock import AsyncMock, MagicMock

import pytest

from browser_stealth.humanize.search import unwrap_redirect_url
from browser_stealth.humanize.warmer import ProfileWarmer


def test_unwrap_redirect_url() -> None:
    # Обычный URL
    assert unwrap_redirect_url("https://example.com") == "https://example.com"

    # Редирект Google /url?q=
    google_redirect = "https://www.google.com/url?q=https://target.com/page&sa=U&ved=0"
    assert unwrap_redirect_url(google_redirect) == "https://target.com/page"

    # Редирект /url?url=
    redirect_url = "https://example.com/url?url=https://target.com/test"
    assert unwrap_redirect_url(redirect_url) == "https://target.com/test"


@pytest.mark.asyncio
async def test_profile_warmer_safe_evaluate_links_json_string() -> None:
    mock_tab = MagicMock()
    # Эмуляция nodriver, вернувшего JSON-строку массива ссылок с редиректами
    json_links = '["https://site.org", "https://www.google.com/url?q=https://real.org"]'
    mock_tab.evaluate = AsyncMock(return_value=json_links)

    warmer = ProfileWarmer(mock_tab)
    links = await warmer._safe_evaluate_links("() => ['https://site.org']")

    assert links == ["https://site.org", "https://real.org"]


@pytest.mark.asyncio
async def test_profile_warmer_safe_evaluate_links_list() -> None:
    mock_tab = MagicMock()
    # Эмуляция Playwright, вернувшего готовый list
    mock_tab.evaluate = AsyncMock(return_value=["https://page1.com", "https://page2.com"])

    warmer = ProfileWarmer(mock_tab)
    links = await warmer._safe_evaluate_links("() => { return [] }")

    assert links == ["https://page1.com", "https://page2.com"]
