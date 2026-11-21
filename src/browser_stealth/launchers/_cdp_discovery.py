"""Поиск активного CDP-эндпоинта Chromium, использующего каталог профиля.

Chromium пишет порт отладки в ``DevToolsActivePort``, но файл может отсутствовать
или быть устаревшим. Дополнительно командная строка запущенных процессов
сканируется через ``Win32_Process`` на Windows и ``ps`` на POSIX. Найденный
эндпоинт проверяется HTTP-запросом к ``/json/version`` в обход локальных прокси.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from browser_stealth.logging import get_logger
from browser_stealth.profiles.hygiene import is_profile_locked

logger = get_logger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_PROCESS_SCAN_TIMEOUT = 3.0

_DEBUG_PORT_RE = re.compile(
    r"--remote-debugging-port(?:=|\s+)(?P<port>\d{2,5})",
)
_USER_DATA_RE = re.compile(
    r"--user-data-dir(?:=|\s+)(?P<path>\"[^\"]+\"|'[^']+'|.+?)(?=\s+--[A-Za-z]|$)",
)
_DEBUG_ADDRESS_RE = re.compile(
    r"--remote-debugging-address(?:=|\s+)(?P<host>[^\s]+)",
)

_WINDOWS_PROCESS_SCRIPT = (
    "$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "Get-CimInstance Win32_Process | "
    "Where-Object { $_.CommandLine -like '*--remote-debugging-port*' } | "
    "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
)


def verify_cdp_endpoint(host: str, port: int, *, timeout: float = 1.0) -> bool:
    """Проверяет, отвечает ли CDP-эндпоинт по HTTP.

    Используется ``http.client``, поэтому локальные прокси из переменных
    окружения не применяются.

    Args:
        host: Хост CDP-эндпоинта.
        port: Порт CDP-эндпоинта.
        timeout: Таймаут подключения и чтения ответа в секундах.

    Returns:
        True, если ``/json/version`` вернул 200 и URL WebSocket-отладчика.
    """
    if not 0 < port <= 65535:
        return False

    normalized_host = _normalize_host(host)
    host_header = (
        f"[{normalized_host}]:{port}" if ":" in normalized_host else f"{normalized_host}:{port}"
    )
    connection = http.client.HTTPConnection(normalized_host, port, timeout=timeout)
    try:
        connection.request(
            "GET",
            "/json/version",
            headers={"Host": host_header, "Connection": "close"},
        )
        response = connection.getresponse()
        if response.status != 200:
            return False
        payload = response.read()
        data = json.loads(payload)
        return isinstance(data, dict) and bool(data.get("webSocketDebuggerUrl"))
    except (OSError, http.client.HTTPException, ValueError):
        return False
    finally:
        connection.close()


def discover_active_cdp_endpoint(profile_dir: str | Path) -> tuple[str, int] | None:
    """Находит активный CDP-эндпоинт Chromium для указанного профиля.

    Сначала читает ``DevToolsActivePort`` в корне профиля и в ``Default/``,
    затем, если профиль заблокирован, сканирует командные строки процессов.
    Каждый найденный кандидат проверяется через :func:`verify_cdp_endpoint`.

    Args:
        profile_dir: Корневой каталог ``user-data-dir`` Chromium.

    Returns:
        Пара ``(host, port)`` или None, если активный CDP-эндпоинт не найден.
    """
    root = _resolve_path(profile_dir)
    if not root.exists():
        return None

    for candidate in (root / "DevToolsActivePort", root / "Default" / "DevToolsActivePort"):
        endpoint = _read_active_port(candidate)
        if endpoint is not None:
            logger.info(
                "Найден CDP-эндпоинт из DevToolsActivePort: %s:%d (профиль: %s)",
                endpoint[0],
                endpoint[1],
                root,
            )
            return endpoint

    if not is_profile_locked(root):
        return None

    for command_line in _iter_process_command_lines():
        parsed = _parse_process_command_line(command_line)
        if parsed is None:
            continue
        host, port, process_profile = parsed
        if not _same_profile(root, process_profile):
            continue
        if not verify_cdp_endpoint(host, port):
            continue
        logger.info(
            "Найден CDP-эндпоинт в процессе Chromium: %s:%d (профиль: %s)",
            host,
            port,
            root,
        )
        return host, port

    return None


def _read_active_port(path: Path) -> tuple[str, int] | None:
    """Читает порт из файла DevToolsActivePort и проверяет эндпоинт."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not lines:
        return None

    try:
        port = int(lines[0].strip())
    except ValueError:
        return None
    if not verify_cdp_endpoint(_DEFAULT_HOST, port):
        return None
    return _DEFAULT_HOST, port


def _parse_process_command_line(command_line: str) -> tuple[str, int, str] | None:
    """Извлекает хост, порт и путь профиля из командной строки процесса."""
    port_match = _DEBUG_PORT_RE.search(command_line)
    profile_match = _USER_DATA_RE.search(command_line)
    if port_match is None or profile_match is None:
        return None

    try:
        port = int(port_match.group("port"))
    except ValueError:
        return None
    if not 0 < port <= 65535:
        return None

    profile = profile_match.group("path").strip().strip('"').strip("'")
    if not profile:
        return None

    address_match = _DEBUG_ADDRESS_RE.search(command_line)
    host = _normalize_host(address_match.group("host") if address_match else _DEFAULT_HOST)
    return host, port, profile


def _same_profile(root: Path, candidate: str) -> bool:
    """Сравнивает путь из командной строки с корнем профиля."""
    candidate_path = _resolve_path(candidate)
    root_path = _resolve_path(root)
    normalized_candidate = os.path.normcase(str(candidate_path))
    normalized_root = os.path.normcase(str(root_path))
    if normalized_candidate == normalized_root:
        return True
    return normalized_candidate == os.path.normcase(str(root_path / "Default"))


def _resolve_path(path: str | Path) -> Path:
    """Разрешает путь, не требуя его существования."""
    try:
        return Path(path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return Path(path).expanduser().absolute()


def _normalize_host(host: str) -> str:
    """Приводит адрес прослушивания к хосту, доступному для подключения."""
    normalized = host.strip().strip("[]")
    if normalized in {"", "*", "0.0.0.0", "::"}:
        return _DEFAULT_HOST
    return normalized


def _iter_process_command_lines() -> list[str]:
    """Возвращает командные строки процессов с включённым remote debugging."""
    if sys.platform.startswith("win"):
        return _windows_process_command_lines()
    return _posix_process_command_lines()


def _windows_process_command_lines() -> list[str]:
    """Сканирует процессы через Win32_Process и PowerShell."""
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        return []

    try:
        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _WINDOWS_PROCESS_SCRIPT,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_PROCESS_SCAN_TIMEOUT,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    raw = (result.stdout or "").lstrip("\ufeff").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []

    records = data if isinstance(data, list) else [data]
    commands: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        command_line = record.get("CommandLine")
        if isinstance(command_line, str) and command_line.strip():
            commands.append(command_line)
    return commands


def _posix_process_command_lines() -> list[str]:
    """Сканирует процессы через ps на POSIX-системах."""
    for args in (
        ["ps", "-eo", "pid=,args="],
        ["ps", "-axo", "pid=,args="],
    ):
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=_PROCESS_SCAN_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return []


__all__ = [
    "discover_active_cdp_endpoint",
    "verify_cdp_endpoint",
]
