"""Моки страниц браузеров для автономного тестирования скраперов."""

from browser_stealth.testing.mocks.dom import DOMNode, parse_html_dom
from browser_stealth.testing.mocks.nodriver import (
    MockNodriverElement,
    MockNodriverTab,
)
from browser_stealth.testing.mocks.playwright import (
    MockPlaywrightLocator,
    MockPlaywrightPage,
)
from browser_stealth.testing.mocks.selenium import (
    MockSeleniumDriver,
    MockSeleniumElement,
)

__all__ = [
    "DOMNode",
    "MockNodriverElement",
    "MockNodriverTab",
    "MockPlaywrightLocator",
    "MockPlaywrightPage",
    "MockSeleniumDriver",
    "MockSeleniumElement",
    "parse_html_dom",
]
