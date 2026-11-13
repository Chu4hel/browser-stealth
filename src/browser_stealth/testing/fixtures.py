"""
Pytest плагин и фикстуры для автотестирования парсеров и скраперов.

Автоматически регистрируется pytest через entry_point `pytest11`
и предоставляет готовые фикстуры для мок- и live-тестирования.
Все тяжелые зависимости импортируются лениво внутри фикстур.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from chutils import SecretManager
from chutils.config.getters import get_config_value
from chutils.secret_manager.providers import DotEnvProvider, EnvProvider

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
    """Загружает переменные из .env файла в окружение процесса (без перезаписи существующих).

    Позволяет использовать секреты локально в файле .env или в CI/CD через GitHub Secrets.

    Args:
        path: Путь к .env файлу. Если None, используется .env в текущем рабочем каталоге.
    """
    target = path if path is not None else Path.cwd() / ".env"
    if not target.is_file():
        return
    try:
        # DotEnvProvider внутри вызывает load_dotenv(override=False) и заполняет окружение процесса.
        DotEnvProvider(dotenv_path=str(target)).get("__browser_stealth_probe__", "browser_stealth")
    except Exception:
        pass


def get_e2e_proxy() -> str | None:
    """Возвращает адрес прокси для E2E тестов из переменных окружения или .env файла.

    Returns:
        Строка прокси из TEST_PROXY/E2E_PROXY/PROXY_URL или None, если она не задана.
    """
    load_env_file()
    manager = SecretManager(
        service_name="browser_stealth_e2e",
        providers=[EnvProvider()],
    )
    for var_name in ("TEST_PROXY", "E2E_PROXY", "PROXY_URL"):
        val = manager.get_secret(var_name)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def get_e2e_browser_args() -> list[str]:
    """Возвращает дополнительные флаги Chromium для E2E-тестов.

    На Linux в CI и под root Chrome не может использовать sandbox:
    Ubuntu 23.10+ ограничивает unprivileged user namespaces через AppArmor,
    из-за чего браузер завершается до подключения по CDP. Отключение
    управляется настройкой ``testing.no_sandbox`` или переменной
    ``CH_TESTING_NO_SANDBOX=1``; под root sandbox отключается автоматически.

    Returns:
        Список флагов; ``--no-sandbox`` только для Linux при необходимости.
    """
    configured = get_config_value("testing", "no_sandbox", fallback=False)
    no_sandbox = str(configured).lower() in {"1", "true", "yes", "on"}
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    if sys.platform.startswith("linux") and (no_sandbox or is_root):
        return ["--no-sandbox", "--disable-setuid-sandbox"]
    return []


@pytest.fixture(scope="session")
def e2e_proxy() -> str | None:
    """Сессионная фикстура прокси для E2E и Heavy тестов.

    Returns:
        Строка прокси для E2E-тестов или None, если она не задана.
    """
    return get_e2e_proxy()


@pytest.fixture(scope="session")
def e2e_browser_args() -> list[str]:
    """Сессионная фикстура дополнительных флагов Chromium для E2E-тестов.

    Returns:
        Флаги, необходимые для запуска Chrome на Linux в CI.
    """
    return get_e2e_browser_args()
