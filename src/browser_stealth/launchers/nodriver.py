"""Фабрики и контекстные менеджеры для запуска браузера nodriver с антидетектом."""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from chutils.fs import ensure_dir

from browser_stealth.antidetect import get_browser_launch_args
from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.antidetect.flags import FlagPolicy, sanitize_browser_args
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


async def close_tab(tab: Any, *, timeout: float = 3.0) -> None:
    """Безопасно закрывает вкладку nodriver с защитой от зависания CDP-сокета.

    Если вкладка потерпела крах (Renderer Crash) или CDP не отвечает,
    операция прерывается по истечении таймаута без зависания вызывающего потока.

    Args:
        tab: Объект вкладки nodriver (nodriver.Tab).
        timeout: Максимальное время ожидания закрытия вкладки в секундах.
    """
    close_method = getattr(tab, "close", None)
    if callable(close_method):
        res = close_method()
        if inspect.isawaitable(res):
            try:
                await asyncio.wait_for(res, timeout=timeout)
            except TimeoutError:
                logger.debug(
                    f"Таймаут ({timeout}с) при закрытии вкладки nodriver, принудительное завершение."
                )
            except Exception as exc:
                logger.debug(f"Ошибка при закрытии вкладки nodriver: {exc}")


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
    patch_tab_find: bool = True,
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
        patch_tab_find: Если True, заменяет ``Tab.find`` безопасной обёрткой, которая ищет текст
            только в основном документе и не опрашивает сторонние iframe (ошибка -32601).
        **kwargs: Дополнительные параметры для передачи в nodriver.start().

    Returns:
        Экземпляр nodriver.Browser.
    """
    uc = _get_nodriver_module()

    if config is None:
        config = AntidetectConfig.preset_stealth_nodriver()

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

    # Запуск браузера
    start_kwargs: dict[str, Any] = dict(kwargs)
    if user_data_dir is not None:
        start_kwargs["user_data_dir"] = str(user_data_dir)
    if browser_executable_path is not None:
        start_kwargs["browser_executable_path"] = str(browser_executable_path)

    browser = await uc.start(
        browser_args=merged_args,
        headless=headless,
        **start_kwargs,
    )

    # Регистрация очистки в жизненном цикле
    def _cleanup_browser() -> None:
        try:
            stop_method = getattr(browser, "stop", None)
            if callable(stop_method):
                res = stop_method()
                if inspect.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass

        except Exception:
            pass

    register_cleanup(_cleanup_browser)

    # Разрешение основной вкладки для патча find и применения AntidetectConfig
    tab = None
    if apply_config_to_tab or patch_tab_find:
        tab = getattr(browser, "main_tab", None)
        if tab is None:
            tabs = getattr(browser, "tabs", [])
            if tabs:
                tab = tabs[0]

    # Безопасный Tab.find без обхода недоверенных iframe
    if patch_tab_find and tab is not None:
        try:
            from browser_stealth.humanize.safe_find import install_safe_find

            install_safe_find(tab)
        except Exception as exc:
            logger.debug(f"Не удалось установить безопасный Tab.find: {exc}")

    # Применение AntidetectConfig к открытой вкладке
    if apply_config_to_tab and tab is not None:
        try:
            await config.apply_to_nodriver(tab)
        except Exception as exc:
            logger.debug(f"Не удалось применить AntidetectConfig к вкладке nodriver: {exc}")

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
    patch_tab_find: bool = True,
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
        patch_tab_find=patch_tab_find,
        **kwargs,
    )
    try:
        yield browser
    finally:
        stop_method = getattr(browser, "stop", None)
        if callable(stop_method):
            res = stop_method()
            if inspect.isawaitable(res):
                try:
                    await asyncio.wait_for(res, timeout=5.0)
                except TimeoutError:
                    logger.debug(
                        "Таймаут (5.0с) при остановке браузера nodriver, принудительное завершение."
                    )
                except Exception as exc:
                    logger.debug(f"Ошибка при остановке браузера nodriver: {exc}")


async def safe_get_or_open_tab(
    browser: Any,
    url: str,
    timeout: float = 10.0,
) -> Any:
    """Безопасно переходит по URL или открывает новую вкладку с защитой от race conditions nodriver.

    Предотвращает RuntimeError('coroutine raised StopIteration'), возникающий в nodriver,
    когда browser.get(new_tab=False) вызывается до момента регистрации начального page target.

    Args:
        browser: Экземпляр nodriver Browser.
        url: Целевой URL веб-страницы.
        timeout: Таймаут ожидания появления открытой страницы (сек).

    Returns:
        Объект активной вкладки Tab.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if hasattr(browser, "update_targets") and callable(browser.update_targets):
                res_upd = browser.update_targets()
                if inspect.isawaitable(res_upd):
                    await res_upd
            targets = getattr(browser, "targets", None)
            if isinstance(targets, list):
                page_tabs = [
                    t
                    for t in targets
                    if getattr(getattr(t, "target", None), "type_", None) == "page"
                ]
                if page_tabs:
                    break
            elif targets is not None:
                break
        except Exception:
            pass
        await asyncio.sleep(0.15)

    try:
        return await browser.get(url)
    except (StopIteration, RuntimeError, Exception) as exc:
        if "StopIteration" in str(exc) or isinstance(exc, StopIteration):
            logger.warning(
                "nodriver browser.get() вызвал ошибку race condition (%s), принудительно открываем через new_tab=True...",
                exc,
            )
            return await browser.get(url, new_tab=True)
        raise


def unpack_cdp_value(v: object) -> object:
    """Рекурсивно извлекает примитивные значения из структур CDP.

    Args:
        v: Значение CDP: dict, list, пара key/value или примитив.

    Returns:
        Развернутое значение: dict, list или примитив без оберток CDP.
    """
    if isinstance(v, dict):
        if "value" in v:
            return unpack_cdp_value(v["value"])
        return {str(k): unpack_cdp_value(val) for k, val in v.items()}
    if isinstance(v, list):
        if v and all(
            isinstance(i, (list, tuple)) and len(i) == 2 and isinstance(i[0], str) for i in v
        ):
            return safe_extract_dict(v)
        return [unpack_cdp_value(i) for i in v]
    return v


def safe_extract_dict(val: object) -> dict[str, object]:
    """Безопасно извлекает словарь из результата evaluate (строка JSON, список пар или dict).

    Args:
        val: Сырой результат вызова tab.evaluate.

    Returns:
        Распакованный словарь с данными.
    """
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:
            logger.debug(
                "Ошибка десериализации JSON из CDP evaluate: %s (val[:100]=%r)",
                exc,
                val[:100] if isinstance(val, str) else val,
            )
            return {}
    if isinstance(val, list):
        res: dict[str, object] = {}
        for item in val:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                k, v = item
                if isinstance(k, str):
                    res[k] = unpack_cdp_value(v)
            elif isinstance(item, dict) and "name" in item and "value" in item:
                res[str(item["name"])] = unpack_cdp_value(item["value"])
        return res
    return {}


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
        p_path = ensure_dir(Path(profile_path).resolve())
        user_data_str = str(p_path)

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
    "close_tab",
    "is_profile_locked",
    "launch_nodriver",
    "nodriver_session",
    "safe_extract_dict",
    "safe_get_or_open_tab",
    "sanitize_profile",
    "sanitize_profile_crash_state",
    "unpack_cdp_value",
]
