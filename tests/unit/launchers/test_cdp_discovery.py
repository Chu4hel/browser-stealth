"""Тесты поиска активного CDP-эндпоинта Chromium по каталогу профиля."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from browser_stealth.launchers import _cdp_discovery
from browser_stealth.launchers._cdp_discovery import (
    discover_active_cdp_endpoint,
    verify_cdp_endpoint,
)


def _mock_cdp_response(
    mocker: MockerFixture,
    *,
    status: int = 200,
    body: bytes = b'{"webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/1"}',
) -> MagicMock:
    """Создаёт мок HTTP-соединения для проверки CDP-эндпоинта."""
    connection = MagicMock()
    response = MagicMock()
    response.status = status
    response.read.return_value = body
    connection.getresponse.return_value = response
    mocker.patch(
        "browser_stealth.launchers._cdp_discovery.http.client.HTTPConnection",
        return_value=connection,
    )
    return connection


def test_verify_cdp_endpoint_success(mocker: MockerFixture) -> None:
    """HTTP 200 с webSocketDebuggerUrl считается рабочим CDP-эндпоинтом."""
    connection = _mock_cdp_response(mocker)

    assert verify_cdp_endpoint("127.0.0.1", 9222) is True
    connection.request.assert_called_once()
    connection.close.assert_called_once()


def test_verify_cdp_endpoint_rejects_non_200(mocker: MockerFixture) -> None:
    """Не-200 ответ не считается рабочим CDP-эндпоинтом."""
    connection = _mock_cdp_response(mocker, status=404)

    assert verify_cdp_endpoint("127.0.0.1", 9222) is False
    connection.close.assert_called_once()


def test_verify_cdp_endpoint_rejects_invalid_json(mocker: MockerFixture) -> None:
    """Невалидный JSON в ответе не считается рабочим CDP-эндпоинтом."""
    _mock_cdp_response(mocker, body=b"not-json")

    assert verify_cdp_endpoint("127.0.0.1", 9222) is False


def test_verify_cdp_endpoint_rejects_invalid_port() -> None:
    """Некорректный порт отклоняется без сетевого запроса."""
    assert verify_cdp_endpoint("127.0.0.1", 0) is False
    assert verify_cdp_endpoint("127.0.0.1", 70000) is False


def test_discover_reads_port_from_profile_root(tmp_path: Path, mocker: MockerFixture) -> None:
    """Порт берётся из DevToolsActivePort в корне профиля."""
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("9222\n/devtools/browser/test\n", encoding="utf-8")
    mocker.patch(
        "browser_stealth.launchers._cdp_discovery.verify_cdp_endpoint",
        return_value=True,
    )

    assert discover_active_cdp_endpoint(profile) == ("127.0.0.1", 9222)


def test_discover_reads_port_from_default_subdir(tmp_path: Path, mocker: MockerFixture) -> None:
    """Порт берётся из DevToolsActivePort в подпапке Default."""
    profile = tmp_path / "profile"
    default = profile / "Default"
    default.mkdir(parents=True)
    (default / "DevToolsActivePort").write_text("9333\n", encoding="utf-8")
    mocker.patch(
        "browser_stealth.launchers._cdp_discovery.verify_cdp_endpoint",
        return_value=True,
    )

    assert discover_active_cdp_endpoint(profile) == ("127.0.0.1", 9333)


def test_discover_ignores_stale_port_and_scans_processes(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Устаревший DevToolsActivePort не мешает найти живой процесс Chromium."""
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("9222\n", encoding="utf-8")

    mocker.patch(
        "browser_stealth.launchers._cdp_discovery.is_profile_locked",
        return_value=True,
    )
    mocker.patch(
        "browser_stealth.launchers._cdp_discovery._iter_process_command_lines",
        return_value=[
            f'chrome.exe --remote-debugging-port=9444 --user-data-dir="{profile}"',
        ],
    )
    mocker.patch(
        "browser_stealth.launchers._cdp_discovery.verify_cdp_endpoint",
        side_effect=lambda _host, port: port == 9444,
    )

    assert discover_active_cdp_endpoint(profile) == ("127.0.0.1", 9444)


def test_discover_ignores_processes_of_other_profiles(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Процесс с другим user-data-dir не считается эндпоинтом профиля."""
    profile = tmp_path / "profile"
    other = tmp_path / "other"
    profile.mkdir()
    other.mkdir()

    mocker.patch(
        "browser_stealth.launchers._cdp_discovery.is_profile_locked",
        return_value=True,
    )
    mocker.patch(
        "browser_stealth.launchers._cdp_discovery._iter_process_command_lines",
        return_value=[
            f'chrome --remote-debugging-port=9555 --user-data-dir="{other}"',
        ],
    )
    verify = mocker.patch(
        "browser_stealth.launchers._cdp_discovery.verify_cdp_endpoint",
        return_value=True,
    )

    assert discover_active_cdp_endpoint(profile) is None
    verify.assert_not_called()


def test_discover_does_not_scan_processes_for_unlocked_profile(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Без признака блокировки профиля скан процессов не выполняется."""
    profile = tmp_path / "profile"
    profile.mkdir()
    mocker.patch(
        "browser_stealth.launchers._cdp_discovery.is_profile_locked",
        return_value=False,
    )
    scan = mocker.patch(
        "browser_stealth.launchers._cdp_discovery._iter_process_command_lines",
    )

    assert discover_active_cdp_endpoint(profile) is None
    scan.assert_not_called()


def test_discover_returns_none_for_missing_profile(tmp_path: Path, mocker: MockerFixture) -> None:
    """Для несуществующего профиля поиск сразу возвращает None."""
    scan = mocker.patch(
        "browser_stealth.launchers._cdp_discovery._iter_process_command_lines",
    )

    assert discover_active_cdp_endpoint(tmp_path / "missing") is None
    scan.assert_not_called()


def test_windows_process_scan_parses_powershell_json(mocker: MockerFixture) -> None:
    """Win32_Process через PowerShell разбирается в список командных строк."""
    mocker.patch.object(_cdp_discovery.shutil, "which", return_value="pwsh")
    run = mocker.patch.object(
        _cdp_discovery.subprocess,
        "run",
        return_value=SimpleNamespace(
            returncode=0,
            stdout='[{"CommandLine": "chrome --remote-debugging-port=9222"}]',
        ),
    )

    assert _cdp_discovery._windows_process_command_lines() == [
        "chrome --remote-debugging-port=9222"
    ]
    assert "Win32_Process" in run.call_args.args[0][-1]
