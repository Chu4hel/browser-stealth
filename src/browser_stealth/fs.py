"""Утилиты для безопасной атомарной работы с файловой системой."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from chutils.fs import atomic_write as _atomic_write
from chutils.fs import cleanup_paths as _cleanup_paths
from chutils.fs import ensure_dir as _ensure_dir
from chutils.fs import remove_path as _remove_path

from browser_stealth.logging import get_logger

logger = get_logger(__name__)


def ensure_dir(path: str | Path) -> Path:
    """Гарантирует существование директории.

    Args:
        path: Путь к директории, которую нужно создать при отсутствии.

    Returns:
        Объект Path созданной или уже существующей директории.
    """
    return Path(_ensure_dir(path))


def atomic_write(
    target_path: str | Path,
    content: str | bytes | None = None,
    *,
    data: str | bytes | None = None,
    mode: str = "w",
    encoding: str = "utf-8",
    **kwargs: Any,
) -> None:
    """Атомарно записывает данные в файл через временный файл и rename.

    Args:
        target_path: Путь к целевому файлу.
        content: Записываемое содержимое (альтернатива data).
        data: Записываемое содержимое (альтернатива content).
        mode: Режим записи 'w' для текста или 'wb' для байтов.
        encoding: Кодировка текстового режима.
        **kwargs: Дополнительные аргументы сериализации JSON/YAML.

    Raises:
        ValueError: Если не передано ни content, ни data.
    """
    actual_content = content if content is not None else data
    if actual_content is None:
        raise ValueError("Не передано содержимое для записи (content или data)")

    is_bytes = "b" in mode or isinstance(actual_content, (bytes, bytearray))
    write_mode = "wb" if is_bytes else "w"
    _atomic_write(
        target_path,
        actual_content,
        mode=write_mode,
        encoding=encoding,
        **kwargs,
    )


def remove_path(
    path: str | Path,
    *,
    retries: int = 3,
    delay: float = 0.1,
    on_locked: Literal["raise", "rename_orphan", "warn"] = "warn",
    orphan_collision: Literal["raise", "overwrite", "unique"] = "raise",
) -> bool:
    """Безопасно удаляет файл или директорию.

    Args:
        path: Путь к удаляемому файлу, директории или символической ссылке.
        retries: Количество попыток удаления.
        delay: Задержка между попытками в секундах.
        on_locked: Поведение при блокировке: 'raise', 'rename_orphan' или 'warn'.
        orphan_collision: Поведение при коллизии orphan-файла.

    Returns:
        True, если путь удален или переименован, иначе False.
    """
    return bool(
        _remove_path(
            path,
            retries=retries,
            delay=delay,
            on_locked=on_locked,
            orphan_collision=orphan_collision,
        )
    )


def cleanup_paths(*paths: str | Path) -> None:
    """Пакетное удаление путей.

    Args:
        *paths: Пути, которые нужно удалить; ошибки логируются и не прерывают обход.
    """
    _cleanup_paths(*paths, on_locked="warn")
