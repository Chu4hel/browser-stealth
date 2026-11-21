"""Кроссплатформенный поиск браузеров и разрешение каталога профиля."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from browser_stealth.fs import ensure_dir
from browser_stealth.logging import get_logger

logger = get_logger(__name__)

_LINUX_BROWSER_NAMES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    "brave-browser",
    "microsoft-edge",
    "microsoft-edge-stable",
    "yandex-browser",
)


def resolve_profile_dir(
    user_data_dir: str | Path,
    *,
    local_base: Path | None = None,
) -> Path:
    """Разрешает путь профиля, перенаправляя UNC-пути Windows на локальный диск.

    Chromium не может надёжно работать с SQLite/LevelDB на сетевых путях
    ``\\\\server\\share``. Такие профили переносятся в
    ``%LOCALAPPDATA%/browser-stealth`` с сохранением относительного пути.

    Args:
        user_data_dir: Исходный каталог профиля.
        local_base: Базовый локальный каталог для UNC-профилей. По умолчанию
            используется ``%LOCALAPPDATA%/browser-stealth``.

    Returns:
        Абсолютный локальный путь к каталогу профиля.
    """
    raw_path = Path(user_data_dir).expanduser()
    if sys.platform.startswith("win") and _is_unc_path(raw_path):
        base = local_base
        if base is None:
            local_appdata = os.environ.get(  # chutils: ignore[ChutilsIntegrationRule]
                "LOCALAPPDATA",
                str(Path.home()),
            )
            base = Path(local_appdata) / "browser-stealth"
        relative = str(raw_path).lstrip("\\/").replace(":", "")
        profile_dir = (base / relative).resolve()
        ensure_dir(profile_dir)
        logger.info("Сетевой UNC-профиль перенаправлен на локальный диск: %s", profile_dir)
        return profile_dir

    return raw_path.resolve()


def discover_browser_executable(
    custom_path: str | Path | None = None,
) -> str | None:
    """Находит установленный Chromium-совместимый браузер.

    Поддерживает Google Chrome, Chrome x86, Microsoft Edge, EdgeCore,
    Yandex Browser и Brave в стандартных каталогах Windows, Linux и macOS.

    Args:
        custom_path: Пользовательский путь к браузеру. Если файл существует,
            возвращается он, иначе выполняется поиск установленных браузеров.

    Returns:
        Путь к исполняемому файлу браузера или None.
    """
    if custom_path is not None:
        custom = Path(custom_path).expanduser()
        if custom.is_file():
            return str(custom)

    for candidate in _candidate_paths():
        try:
            if candidate.is_file():
                logger.info("Обнаружен исполняемый файл браузера: %s", candidate)
                return str(candidate)
        except OSError:
            continue
    return None


def _candidate_paths() -> list[Path]:
    """Возвращает кандидатов браузеров для текущей платформы."""
    if sys.platform.startswith("win"):
        candidates = _windows_candidates()
    elif sys.platform == "darwin":
        candidates = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
            Path("/Applications/Yandex.app/Contents/MacOS/Yandex"),
        ]
    else:
        candidates = _which_candidates()

    return list(dict.fromkeys(candidates))


def _windows_candidates() -> list[Path]:
    """Собирает пути Chrome, Edge, Yandex и Brave в Windows."""
    program_files = Path(
        os.environ.get(  # chutils: ignore[ChutilsIntegrationRule]
            "PROGRAMFILES",
            r"C:\Program Files",
        )
    )
    program_files_x86 = Path(
        os.environ.get(  # chutils: ignore[ChutilsIntegrationRule]
            "PROGRAMFILES(X86)",
            r"C:\Program Files (x86)",
        )
    )
    local_appdata = Path(
        os.environ.get(  # chutils: ignore[ChutilsIntegrationRule]
            "LOCALAPPDATA",
            str(Path.home() / "AppData" / "Local"),
        )
    )

    candidates = [
        program_files / "Google/Chrome/Application/chrome.exe",
        program_files_x86 / "Google/Chrome/Application/chrome.exe",
        local_appdata / "Google/Chrome/Application/chrome.exe",
        program_files / "Microsoft/Edge/Application/msedge.exe",
        program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
        program_files / "Yandex/YandexBrowser/Application/browser.exe",
        program_files_x86 / "Yandex/YandexBrowser/Application/browser.exe",
        local_appdata / "Yandex/YandexBrowser/Application/browser.exe",
        program_files / "BraveSoftware/Brave-Browser/Application/brave.exe",
        program_files_x86 / "BraveSoftware/Brave-Browser/Application/brave.exe",
        local_appdata / "BraveSoftware/Brave-Browser/Application/brave.exe",
    ]

    for root in (program_files, program_files_x86):
        candidates.extend(sorted(root.glob("Microsoft/EdgeCore/*/msedge.exe")))
    return candidates


def _which_candidates() -> list[Path]:
    """Ищет браузеры в PATH на Linux и других POSIX-системах."""
    candidates: list[Path] = []
    for name in _LINUX_BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    return candidates


def _is_unc_path(path: Path) -> bool:
    """Проверяет, начинается ли путь с UNC-префикса."""
    raw = str(path)
    return raw.startswith("\\\\") or raw.startswith("//")


__all__ = [
    "discover_browser_executable",
    "resolve_profile_dir",
]
