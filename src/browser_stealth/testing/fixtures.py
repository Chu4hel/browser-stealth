"""
Pytest плагин и фикстуры для автотестирования парсеров и скраперов.

Автоматически регистрируется pytest через entry_point `pytest11`
и предоставляет готовые фикстуры для мок- и live-тестирования.
Все тяжелые зависимости импортируются лениво внутри фикстур.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from browser_stealth.testing.mocks import (
        MockNodriverTab,
        MockPlaywrightPage,
        MockSeleniumDriver,
    )
    from browser_stealth.testing.server import LocalTestServer
    from browser_stealth.testing.session import LiveBrowserSession
    from browser_stealth.testing.snapshot import SnapshotRecorder


def pytest_configure(config: Any) -> None:
    """Регистрирует кастомные маркеры chutils для pytest.

    Args:
        config: Объект конфигурации pytest.
    """
    config.addinivalue_line(
        "markers",
        "live_scraping: маркер для интеграционных тестов со сквозным запуском реального браузера",
    )


@pytest.fixture
def local_test_server() -> Generator[LocalTestServer, None, None]:
    """Предоставляет запущенный локальный тестовый HTTP-сервер песочницы.

    Yields:
        Запущенный экземпляр LocalTestServer.
    """
    from browser_stealth.testing.server import LocalTestServer

    with LocalTestServer() as server:
        yield server


@pytest.fixture
def live_browser_session() -> Generator[LiveBrowserSession, None, None]:
    """Предоставляет сессию реального браузера с гарантированным teardown зомби-процессов.

    Yields:
        Активный экземпляр LiveBrowserSession.
    """
    from browser_stealth.testing.session import LiveBrowserSession

    with LiveBrowserSession() as session:
        yield session


@pytest.fixture
def html_snapshot_recorder(tmp_path: Path) -> SnapshotRecorder:
    """Предоставляет менеджер снапшотов SnapshotRecorder во временном каталоге.

    Args:
        tmp_path: Временная папка теста от pytest.

    Returns:
        Экземпляр SnapshotRecorder.
    """
    from browser_stealth.testing.snapshot import SnapshotRecorder

    return SnapshotRecorder(snapshot_dir=tmp_path)


@pytest.fixture
def mock_nodriver_tab() -> Callable[..., MockNodriverTab]:
    """Фабрика для создания легковесного мока вкладки nodriver.

    Returns:
        Функция, принимающая HTML строку и возвращающая MockNodriverTab.
    """

    def _factory(html: str = "") -> MockNodriverTab:
        from browser_stealth.testing.mocks import MockNodriverTab

        return MockNodriverTab(html)

    return _factory


@pytest.fixture
def mock_playwright_page() -> Callable[..., MockPlaywrightPage]:
    """Фабрика для создания мока страницы Playwright.

    Returns:
        Функция, принимающая HTML строку и возвращающая MockPlaywrightPage.
    """

    def _factory(html: str = "") -> MockPlaywrightPage:
        from browser_stealth.testing.mocks import MockPlaywrightPage

        return MockPlaywrightPage(html)

    return _factory


@pytest.fixture
def mock_selenium_driver() -> Callable[..., MockSeleniumDriver]:
    """Фабрика для создания мока драйвера Selenium.

    Returns:
        Функция, принимающая HTML строку и возвращающая MockSeleniumDriver.
    """

    def _factory(html: str = "") -> MockSeleniumDriver:
        from browser_stealth.testing.mocks import MockSeleniumDriver

        return MockSeleniumDriver(html)

    return _factory


def load_env_file(path: Path | None = None) -> None:
    """Загружает переменные из .env файла в os.environ (без перезаписи существующих).

    Позволяет использовать секреты локально в файле .env или в CI/CD через GitHub Secrets.
    """
    if path is None:
        path = Path.cwd() / ".env"
    if not path.is_file():
        return
    try:
        with open(path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass


def get_e2e_proxy() -> str | None:
    """Возвращает адрес прокси для E2E тестов из переменных окружения или .env файла."""
    load_env_file()
    for var_name in ("TEST_PROXY", "E2E_PROXY", "PROXY_URL"):
        val = os.environ.get(var_name)
        if val and val.strip():
            return val.strip()
    return None


@pytest.fixture(scope="session")
def e2e_proxy() -> str | None:
    """Сессионная фикстура прокси для E2E и Heavy тестов."""
    return get_e2e_proxy()
