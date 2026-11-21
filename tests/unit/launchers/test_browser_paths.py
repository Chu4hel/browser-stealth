"""Тесты поиска браузерных бинарников и разрешения профиля."""

from __future__ import annotations

from pathlib import Path

from pytest_mock import MockerFixture

from browser_stealth.launchers import _browser_paths
from browser_stealth.launchers._browser_paths import (
    discover_browser_executable,
    resolve_profile_dir,
)


def test_resolve_profile_dir_returns_absolute_local_path(tmp_path: Path) -> None:
    """Обычный локальный профиль разрешается без перенаправления."""
    profile = tmp_path / "profile"

    result = resolve_profile_dir(profile)

    assert result == profile.resolve()


def test_resolve_profile_dir_redirects_unc(tmp_path: Path, mocker: MockerFixture) -> None:
    """UNC-путь перенаправляется в локальную базу с сохранением структуры."""
    mocker.patch.object(_browser_paths.sys, "platform", "win32")
    local_base = tmp_path / "local"

    result = resolve_profile_dir("//server/share/profile", local_base=local_base)

    assert result == (local_base / "server" / "share" / "profile").resolve()
    assert result.is_dir()


def test_discover_browser_executable_uses_custom_path(tmp_path: Path) -> None:
    """Существующий custom_path возвращается без поиска."""
    executable = tmp_path / "chrome.exe"
    executable.write_text("", encoding="utf-8")

    assert discover_browser_executable(executable) == str(executable)


def test_discover_browser_executable_uses_candidates(tmp_path: Path, mocker: MockerFixture) -> None:
    """Первый существующий кандидат возвращается как путь к браузеру."""
    executable = tmp_path / "browser.exe"
    executable.write_text("", encoding="utf-8")
    mocker.patch.object(_browser_paths, "_candidate_paths", return_value=[executable])

    assert discover_browser_executable() == str(executable)


def test_discover_browser_executable_returns_none_without_candidates(
    mocker: MockerFixture,
) -> None:
    """Если кандидатов нет, возвращается None."""
    mocker.patch.object(_browser_paths, "_candidate_paths", return_value=[])

    assert discover_browser_executable() is None


def test_windows_candidates_include_chrome_edge_yandex_brave(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Windows-поиск покрывает Chrome, Edge/EdgeCore, Yandex и Brave."""
    program_files = tmp_path / "Program Files"
    program_files_x86 = tmp_path / "Program Files (x86)"
    local_appdata = tmp_path / "LocalAppData"
    for root in (program_files, program_files_x86, local_appdata):
        root.mkdir()

    edge_core = program_files_x86 / "Microsoft" / "EdgeCore" / "157.0" / "msedge.exe"
    edge_core.parent.mkdir(parents=True)
    edge_core.write_text("", encoding="utf-8")

    mocker.patch.object(_browser_paths.sys, "platform", "win32")
    mocker.patch.dict(
        _browser_paths.os.environ,
        {
            "PROGRAMFILES": str(program_files),
            "PROGRAMFILES(X86)": str(program_files_x86),
            "LOCALAPPDATA": str(local_appdata),
        },
    )

    candidates = _browser_paths._candidate_paths()
    rendered = {str(path) for path in candidates}

    assert str(program_files / "Google/Chrome/Application/chrome.exe") in rendered
    assert str(program_files / "Microsoft/Edge/Application/msedge.exe") in rendered
    assert str(edge_core) in rendered
    assert str(program_files / "Yandex/YandexBrowser/Application/browser.exe") in rendered
    assert str(program_files / "BraveSoftware/Brave-Browser/Application/brave.exe") in rendered
