"""Фабрики и контекстные менеджеры для запуска браузера nodriver с антидетектом."""

from __future__ import annotations

import asyncio
import inspect
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from browser_stealth.antidetect import get_browser_launch_args
from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.antidetect.flags import FlagPolicy, sanitize_browser_args
from browser_stealth.connection import BROWSER_DETACHED_ATTR
from browser_stealth.env import ensure_local_no_proxy
from browser_stealth.launchers._browser_paths import (
    discover_browser_executable,
    resolve_profile_dir,
)
from browser_stealth.launchers._cdp_discovery import discover_active_cdp_endpoint
from browser_stealth.launchers._cdp_startup import (
    STARTUP_TIMEOUT,
    await_cdp_ready,
    pick_pending_browser,
    registered_browsers,
)
from browser_stealth.launchers._cdp_values import safe_extract_dict, unpack_cdp_value
from browser_stealth.launchers._nodriver_tabs import (
    _pick_primary_tab,
    cleanup_duplicate_empty_tabs,
    close_tab,
    safe_get_or_open_tab,
)
from browser_stealth.lifecycle import register_cleanup
from browser_stealth.logging import get_logger as setup_logger
from browser_stealth.profiles.hygiene import (
    is_profile_locked,
    sanitize_profile,
    sanitize_profile_crash_state,
)
from browser_stealth.proxy.adapters import get_nodriver_proxy_args
from browser_stealth.proxy.models import ProxyConfig

logger = setup_logger(__name__)

_REATTACHED_ATTR = "_browser_stealth_reattached"


def _get_nodriver_module() -> Any:
    """Безопасно импортирует библиотеку nodriver.

    Returns:
        Модуль nodriver.

    Raises:
        ImportError: Если nodriver не установлен.
    """
    try:
        import nodriver as uc

        return uc
    except ImportError as err:
        raise ImportError(
            "Для использования nodriver необходимо установить библиотеку: "
            "pip install nodriver или pip install chutils[scraping]"
        ) from err


async def _configure_browser(
    browser: Any,
    config: AntidetectConfig,
    *,
    apply_config_to_tab: bool,
    patch_tab_find: bool,
    reattached: bool,
) -> None:
    """Регистрирует очистку и применяет настройки антидетекта к вкладке.

    Args:
        browser: Экземпляр nodriver.Browser.
        config: Конфигурация антидетекта.
        apply_config_to_tab: Применять ли конфигурацию к основной вкладке.
        patch_tab_find: Устанавливать ли безопасную обёртку ``Tab.find``.
        reattached: True, если браузер уже был запущен и не принадлежит сессии.
    """

    def _cleanup_browser() -> Any:
        try:
            if getattr(browser, BROWSER_DETACHED_ATTR, False) is True:
                return None
            if reattached:
                close_method = getattr(browser, "aclose", None)
                if callable(close_method):
                    return close_method()
                return None

            stop_method = getattr(browser, "stop", None)
            if callable(stop_method):
                return stop_method()
        except Exception:
            pass
        return None

    register_cleanup(_cleanup_browser)

    await cleanup_duplicate_empty_tabs(browser)
    tab = _pick_primary_tab(browser)
    if tab is None and (apply_config_to_tab or patch_tab_find):
        tab = getattr(browser, "main_tab", None)
        if tab is None:
            tabs = getattr(browser, "tabs", [])
            if tabs:
                tab = tabs[0]

    if patch_tab_find and tab is not None:
        try:
            from browser_stealth.humanize.safe_find import install_safe_find

            install_safe_find(tab)
        except Exception as exc:
            logger.debug(f"Не удалось установить безопасный Tab.find: {exc}")

    if apply_config_to_tab and tab is not None:
        try:
            await config.apply_to_nodriver(tab)
        except Exception as exc:
            logger.debug(f"Не удалось применить AntidetectConfig к вкладке nodriver: {exc}")


async def _reattach_browser(
    uc: Any,
    endpoint: tuple[str, int],
    *,
    config: AntidetectConfig,
    apply_config_to_tab: bool,
    patch_tab_find: bool,
    kwargs: dict[str, Any],
) -> Any:
    """Подключается к уже запущенному Chromium по CDP и настраивает вкладку.

    Args:
        uc: Модуль nodriver.
        endpoint: Пара ``(host, port)`` активного CDP-эндпоинта.
        config: Конфигурация антидетекта.
        apply_config_to_tab: Применять ли конфигурацию к основной вкладке.
        patch_tab_find: Устанавливать ли безопасную обёртку ``Tab.find``.
        kwargs: Дополнительные параметры для ``uc.start``.

    Returns:
        Подключённый экземпляр nodriver.Browser.

    Raises:
        RuntimeError: Если подключиться к найденному эндпоинту не удалось.
    """
    host, port = endpoint
    start_kwargs = dict(kwargs)
    start_kwargs.pop("host", None)
    start_kwargs.pop("port", None)
    try:
        browser = await uc.start(host=host, port=port, **start_kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"Не удалось переподключиться к активному Chromium на {host}:{port}: {exc}"
        ) from exc

    setattr(browser, _REATTACHED_ATTR, True)
    logger.info("Подключение к уже запущенному Chromium на %s:%d", host, port)
    await _configure_browser(
        browser,
        config,
        apply_config_to_tab=apply_config_to_tab,
        patch_tab_find=patch_tab_find,
        reattached=True,
    )
    return browser


async def _close_browser(browser: Any, *, timeout: float) -> None:
    """Закрывает соединение с браузером, не останавливая чужой процесс.

    Args:
        browser: Экземпляр nodriver.Browser.
        timeout: Максимальное время ожидания закрытия.
    """
    if getattr(browser, BROWSER_DETACHED_ATTR, False) is True:
        return
    if getattr(browser, _REATTACHED_ATTR, False) is True:
        close_method = getattr(browser, "aclose", None)
        if callable(close_method):
            res = close_method()
            if inspect.isawaitable(res):
                try:
                    await asyncio.wait_for(res, timeout=timeout)
                except TimeoutError:
                    logger.debug(
                        "Таймаут (%.1fс) при закрытии CDP-соединения, принудительное завершение.",
                        timeout,
                    )
                except Exception as exc:
                    logger.debug(f"Ошибка при закрытии CDP-соединения: {exc}")
        return

    stop_method = getattr(browser, "stop", None)
    if callable(stop_method):
        res = stop_method()
        if inspect.isawaitable(res):
            try:
                await asyncio.wait_for(res, timeout=timeout)
            except TimeoutError:
                logger.debug(
                    "Таймаут (%.1fс) при остановке браузера nodriver, принудительное завершение.",
                    timeout,
                )
            except Exception as exc:
                logger.debug(f"Ошибка при остановке браузера nodriver: {exc}")


async def launch_nodriver(
    config: AntidetectConfig | None = None,
    *,
    user_data_dir: Path | str | None = None,
    browser_executable_path: Path | str | None = None,
    proxy: ProxyConfig | str | dict[str, object] | None = None,
    headless: bool = False,
    browser_args: list[str] | None = None,
    browser_args_policy: FlagPolicy | str = FlagPolicy.SANITIZE,
    apply_config_to_tab: bool = True,
    sanitize_profile_dir: bool = True,
    auto_reattach: bool = True,
    patch_tab_find: bool = True,
    sandbox: bool | None = None,
    **kwargs: Any,
) -> Any:
    """Запускает браузер nodriver с рекомендуемыми стелс-аргументами и AntidetectConfig.

    Args:
        config: Экземпляр AntidetectConfig. Если None, используется AntidetectConfig.preset_stealth_nodriver().
        user_data_dir: Путь к постоянному каталогу профиля браузера (куки, сессии, история).
        browser_executable_path: Пользовательский путь к бинарному файлу Chromium/Chrome/Brave.
        proxy: Настройки прокси (строка, ProxyConfig или dict). Если требуется авторизация,
            автоматически создается временное Manifest v3 расширение.
        headless: Флаг запуска в фоновом (headless) режиме.
        browser_args: Дополнительные аргументы командной строки Chromium.
        browser_args_policy: Политика обработки неподдерживаемых флагов Chromium
            (например, ``--disable-blink-features=AutomationControlled``).
            По умолчанию опасные флаги удаляются с предупреждением в лог.
            Передайте ``FlagPolicy.ERROR`` для строгой валидации.
        apply_config_to_tab: Если True, автоматически применяет конфигурацию антидетекта к первой вкладке.
        sanitize_profile_dir: Если True и передан user_data_dir, перед запуском браузера сбрасывает флаги
            аварийного завершения (exit_type="Normal") и очищает остаточные сессии/вкладки,
            предотвращая инфобар восстановления вкладок и детекты антифрода.
        auto_reattach: Если True и профиль уже используется запущенным Chromium, ищет его
            CDP-эндпоинт и подключается к существующему окну вместо повторного запуска.
        patch_tab_find: Если True, заменяет ``Tab.find`` безопасной обёрткой, которая ищет текст
            только в основном документе и не опрашивает сторонние iframe (ошибка -32601).
        **kwargs: Дополнительные параметры для передачи в nodriver.start().

    Returns:
        Экземпляр nodriver.Browser.

    Raises:
        RuntimeError: Если найденный CDP-эндпоинт не удалось подключить.
    """
    ensure_local_no_proxy()
    uc = _get_nodriver_module()

    if config is None:
        config = AntidetectConfig.preset_stealth_nodriver()

    if user_data_dir is not None:
        user_data_dir = resolve_profile_dir(user_data_dir)

    # Переподключение к уже запущенному Chromium до санитизации профиля
    if auto_reattach and user_data_dir is not None:
        try:
            endpoint = discover_active_cdp_endpoint(user_data_dir)
        except Exception as exc:
            logger.debug(f"Не удалось найти активный CDP-эндпоинт: {exc}")
            endpoint = None
        if endpoint is not None:
            return await _reattach_browser(
                uc,
                endpoint,
                config=config,
                apply_config_to_tab=apply_config_to_tab,
                patch_tab_find=patch_tab_find,
                kwargs=kwargs,
            )

    # Сборка базовых стелс-аргументов запуска
    recommended_args = get_browser_launch_args()

    merged_args: list[str] = list(recommended_args)

    # Интеграция прокси
    if proxy is not None:
        proxy_args = get_nodriver_proxy_args(proxy)
        for p_arg in proxy_args:
            if p_arg not in merged_args:
                merged_args.append(p_arg)

    # Пользовательские аргументы
    if browser_args:
        for b_arg in browser_args:
            if b_arg not in merged_args:
                merged_args.append(b_arg)

    # Синхронизация User-Agent флага запуска с AntidetectConfig
    if config.user_agent and not any(a.startswith("--user-agent=") for a in merged_args):
        merged_args.append(f"--user-agent={config.user_agent}")

    # Защита от неподдерживаемых и скомпрометированных флагов Chromium
    merged_args = sanitize_browser_args(merged_args, policy=browser_args_policy)

    # Очистка профиля от следов падений и сброс crash flags перед запуском
    if sanitize_profile_dir and user_data_dir is not None:
        try:
            sanitize_profile(user_data_dir)
        except Exception as exc:
            logger.debug(f"Не удалось выполнить sanitize_profile для {user_data_dir}: {exc}")

    # Кроссплатформенный поиск браузера: Chrome, Edge/EdgeCore, Yandex, Brave.
    if browser_executable_path is None:
        env_path = os.environ.get(  # chutils: ignore[ChutilsIntegrationRule]
            "BROWSER_EXECUTABLE_PATH"
        ) or os.environ.get(  # chutils: ignore[ChutilsIntegrationRule]
            "CHROME_BIN"  # chutils: ignore[ChutilsIntegrationRule]
        )
        browser_executable_path = discover_browser_executable(env_path)

    # Запуск браузера
    start_kwargs: dict[str, Any] = dict(kwargs)
    if user_data_dir is not None:
        start_kwargs["user_data_dir"] = str(user_data_dir)
    if browser_executable_path is not None:
        start_kwargs["browser_executable_path"] = str(browser_executable_path)
    if sandbox is None:
        sandbox = not any(
            arg == "--no-sandbox" or arg.startswith("--no-sandbox=") for arg in merged_args
        )
    start_kwargs["sandbox"] = sandbox

    known_browsers = registered_browsers(uc)
    try:
        browser = await uc.start(
            browser_args=merged_args,
            headless=headless,
            **start_kwargs,
        )
    except Exception as exc:
        pending = pick_pending_browser(uc, known_browsers)
        if pending is None:
            raise
        logger.warning(
            "nodriver не дождался порта CDP (%s), продолжаем ожидание до %.0f с",
            exc,
            STARTUP_TIMEOUT,
        )
        browser = await await_cdp_ready(uc, pending, timeout=STARTUP_TIMEOUT)

    await _configure_browser(
        browser,
        config,
        apply_config_to_tab=apply_config_to_tab,
        patch_tab_find=patch_tab_find,
        reattached=False,
    )

    return browser


@asynccontextmanager
async def nodriver_session(
    config: AntidetectConfig | None = None,
    *,
    user_data_dir: Path | str | None = None,
    browser_executable_path: Path | str | None = None,
    proxy: ProxyConfig | str | dict[str, object] | None = None,
    headless: bool = False,
    browser_args: list[str] | None = None,
    browser_args_policy: FlagPolicy | str = FlagPolicy.SANITIZE,
    apply_config_to_tab: bool = True,
    sanitize_profile_dir: bool = True,
    auto_reattach: bool = True,
    patch_tab_find: bool = True,
    sandbox: bool | None = None,
    **kwargs: Any,
) -> AsyncIterator[Any]:
    """Асинхронный контекстный менеджер сессии браузера nodriver с гарантированным закрытием.

    Args:
        config: Экземпляр AntidetectConfig. Если None, используется AntidetectConfig.preset_stealth_nodriver().
        user_data_dir: Путь к постоянному каталогу профиля браузера (куки, сессии, история).
        browser_executable_path: Пользовательский путь к бинарному файлу Chromium/Chrome/Brave.
        proxy: Настройки прокси.
        headless: Флаг запуска в headless режиме.
        browser_args: Дополнительные флаги Chromium.
        browser_args_policy: Политика обработки неподдерживаемых флагов Chromium.
        apply_config_to_tab: Автоматически применить AntidetectConfig к вкладке.
        sanitize_profile_dir: Выполнить санитайзинг профиля перед запуском.
        auto_reattach: Подключаться к уже запущенному Chromium, использующему профиль.
        patch_tab_find: Заменить ``Tab.find`` безопасной обёрткой без обхода сторонних iframe.
        **kwargs: Дополнительные параметры nodriver.start().

    Yields:
        Экземпляр nodriver.Browser.
    """
    browser = await launch_nodriver(
        config=config,
        user_data_dir=user_data_dir,
        browser_executable_path=browser_executable_path,
        proxy=proxy,
        headless=headless,
        browser_args=browser_args,
        browser_args_policy=browser_args_policy,
        apply_config_to_tab=apply_config_to_tab,
        sanitize_profile_dir=sanitize_profile_dir,
        auto_reattach=auto_reattach,
        patch_tab_find=patch_tab_find,
        sandbox=sandbox,
        **kwargs,
    )
    try:
        yield browser
    finally:
        await _close_browser(browser, timeout=5.0)


class ChromiumProcessManager:
    """Управляет жизненным циклом процесса Chromium через nodriver, сетевым окружением и сессиями."""

    def __init__(self) -> None:
        """Инициализирует менеджер процессов."""

    async def launch(
        self,
        profile_path: Path | str,
        headless: bool = False,
        proxy_server: str | None = None,
        profile_name: str | None = None,
        tunnel_cls: type | None = None,
        extra_args: list[str] | None = None,
        browser_executable_path: Path | str | None = None,
        sandbox: bool = True,
        flag_policy: FlagPolicy | str = FlagPolicy.SANITIZE,
    ) -> tuple[Any, Any | None]:
        """Запускает процесс Chromium через nodriver с изоляцией профиля и поддержкой прокси.

        Args:
            profile_path: Путь к директории пользовательских данных Chromium (user-data-dir).
            headless: Флаг запуска браузера в фоновом (headless) режиме.
            proxy_server: Строка подключения к прокси (URL или host:port[:user:pass]).
            profile_name: Человекочитаемое имя профиля для информационного логирования.
            tunnel_cls: Опциональный класс создания прокси-туннеля (по умолчанию AsyncProxyTunnel).
            extra_args: Дополнительные флаги командной строки браузера.
            browser_executable_path: Пользовательский путь к бинарнику Chromium.
            sandbox: Использовать ли песочницу Chrome (по умолчанию True).
            flag_policy: Политика обработки неподдерживаемых флагов Chromium.
                По умолчанию опасные флаги удаляются с предупреждением в лог.

        Returns:
            Кортеж из (nodriver.Browser, AsyncProxyTunnel | None).
        """
        ensure_local_no_proxy()
        p_path = resolve_profile_dir(profile_path)
        user_data_str = str(p_path)
        if browser_executable_path is None:
            browser_executable_path = discover_browser_executable()

        recommended_args = get_browser_launch_args()
        browser_args: list[str] = [
            arg
            for arg in recommended_args
            if arg not in ("--disable-blink-features=AutomationControlled", "--no-sandbox")
        ]

        for flag in (
            "--disable-session-crashed-bubble",
            "--hide-crash-restore-bubble",
            "--restore-last-session=false",
            "--no-first-run",
            "--no-default-browser-check",
        ):
            if flag not in browser_args:
                browser_args.append(flag)

        if not headless and "--start-maximized" not in browser_args:
            browser_args.append("--start-maximized")

        if extra_args:
            for e_arg in extra_args:
                if e_arg not in browser_args:
                    browser_args.append(e_arg)

        # Защита от неподдерживаемых и скомпрометированных флагов Chromium
        browser_args = sanitize_browser_args(browser_args, policy=flag_policy)

        proxy_tunnel = None
        if proxy_server:
            from browser_stealth.proxy.tunnel import setup_browser_proxy

            proxy_tunnel = await setup_browser_proxy(
                proxy=proxy_server,
                browser_args=browser_args,
                purpose=profile_name or p_path.name,
                fail_on_dead=False,
                tunnel_cls=tunnel_cls,
            )

        if is_profile_locked(p_path):
            logger.warning(
                "Каталог профиля '%s' заблокирован существующим процессом Chromium. Санитизация...",
                profile_name or p_path.name,
            )
        sanitize_profile_crash_state(p_path)

        logger.info(
            "Запуск Chromium через nodriver (профиль: %s, headless=%s)...",
            profile_name or p_path.name,
            headless,
        )
        uc = _get_nodriver_module()
        try:
            start_kwargs: dict[str, Any] = {
                "user_data_dir": user_data_str,
                "headless": headless,
                "browser_args": browser_args,
                "sandbox": sandbox,
            }
            if browser_executable_path is not None:
                start_kwargs["browser_executable_path"] = str(browser_executable_path)

            browser = await uc.start(**start_kwargs)

            # Синхронизация targets
            for _ in range(15):
                try:
                    if hasattr(browser, "update_targets") and callable(browser.update_targets):
                        await browser.update_targets()
                    tabs = getattr(browser, "tabs", None)
                    if isinstance(tabs, list) and len(tabs) > 0:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.1)

            # Очистка избыточных вкладок от прошлых сессий
            current_tabs = [t for t in getattr(browser, "tabs", []) if hasattr(t, "close")]
            if len(current_tabs) > 1:
                logger.info(
                    "Обнаружено %d открытых вкладок при запуске. Очистка старых сессионных вкладок...",
                    len(current_tabs),
                )
                for extra_tab in current_tabs[1:]:
                    await close_tab(extra_tab, timeout=3.0)

            return browser, proxy_tunnel
        except Exception:
            sanitize_profile_crash_state(p_path)
            if proxy_tunnel is not None:
                try:
                    await proxy_tunnel.stop()
                except Exception:
                    pass
            raise

    async def stop(
        self,
        browser: Any | None,
        proxy_tunnel: Any | None = None,
        profile_path: Path | str | None = None,
    ) -> None:
        """Корректно завершает работу процесса Chromium и сопутствующего прокси-туннеля.

        Args:
            browser: Активный экземпляр nodriver Browser.
            proxy_tunnel: Активный туннель прокси (если использовался).
            profile_path: Директория профиля для пост-санитизации состояния краша.
        """
        p_path = Path(profile_path).resolve() if profile_path is not None else None
        if browser is not None:
            logger.info("Закрытие сеанса Chromium...")
            try:
                # 1. Корректно закрываем CDP WebSocket соединение
                if hasattr(browser, "aclose") and callable(browser.aclose):
                    try:
                        await asyncio.wait_for(browser.aclose(), timeout=2.0)
                    except Exception:
                        pass

                # 2. Безопасно закрываем пайпы сабпроцесса до вызова stop()
                proc = getattr(browser, "_process", None)
                if proc is not None:
                    for pipe in (
                        getattr(proc, "stdin", None),
                        getattr(proc, "stdout", None),
                        getattr(proc, "stderr", None),
                    ):
                        if pipe is not None and hasattr(pipe, "close"):
                            try:
                                pipe.close()
                            except Exception:
                                pass
                    transport = getattr(proc, "_transport", None)
                    if transport is not None and hasattr(transport, "close"):
                        try:
                            transport.close()
                        except Exception:
                            pass

                stop_fn = getattr(browser, "stop", None)
                if callable(stop_fn):
                    stop_fn()
            except Exception as exc:
                logger.debug("Ошибка при вызове browser.stop(): %s", exc)
            finally:
                if p_path is not None:
                    sanitize_profile_crash_state(p_path)
                await asyncio.sleep(0.1)

        if proxy_tunnel is not None:
            logger.info("Остановка туннеля аутентификации прокси...")
            try:
                await proxy_tunnel.stop()
            except Exception as exc:
                logger.debug("Ошибка остановки прокси-туннеля: %s", exc)


from browser_stealth.concurrency.reaper import (
    IdleBrowserReaper,
    IdleBrowserReaperConfig,
    IdleReaper,
    IdleReaperConfig,
)

__all__ = [
    "ChromiumProcessManager",
    "IdleBrowserReaper",
    "IdleBrowserReaperConfig",
    "IdleReaper",
    "IdleReaperConfig",
    "cleanup_duplicate_empty_tabs",
    "close_tab",
    "discover_active_cdp_endpoint",
    "discover_browser_executable",
    "is_profile_locked",
    "launch_nodriver",
    "nodriver_session",
    "resolve_profile_dir",
    "safe_extract_dict",
    "safe_get_or_open_tab",
    "sanitize_profile",
    "sanitize_profile_crash_state",
    "unpack_cdp_value",
]
