"""Утилиты для безопасной атомарной работы с файловой системой."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("browser_stealth.fs")


def ensure_dir(path: str | Path) -> Path:
    """Гарантирует существование директории."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write(
    target_path: str | Path,
    content: str | bytes | None = None,
    *,
    data: str | bytes | None = None,
    mode: str = "w",
    encoding: str = "utf-8",
    **kwargs: Any,
) -> None:
    """Атомарно записывает данные в файл через временный файл и rename."""
    dest = Path(target_path).resolve()
    ensure_dir(dest.parent)

    actual_content = content if content is not None else data
    if actual_content is None:
        raise ValueError("Не передано содержимое для записи (content или data)")

    is_bytes = "b" in mode or isinstance(actual_content, (bytes, bytearray))
    write_mode = "wb" if is_bytes else "w"

    with tempfile.NamedTemporaryFile(
        mode=write_mode,
        dir=dest.parent,
        delete=False,
        encoding=None if is_bytes else encoding,
    ) as temp_file:
        temp_name = temp_file.name
        temp_file.write(actual_content)  # type: ignore[arg-type]
        temp_file.flush()
        os.fsync(temp_file.fileno())

    os.replace(temp_name, dest)


def remove_path(
    path: str | Path,
    *,
    retries: int = 3,
    delay: float = 0.1,
    on_locked: Literal["raise", "rename_orphan", "warn"] = "warn",
    orphan_collision: Literal["raise", "overwrite", "unique"] = "raise",
) -> bool:
    """Безопасно удаляет файл или директорию."""
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return True

    for attempt in range(retries):
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return True
        except OSError as exc:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                if on_locked == "raise":
                    raise
                logger.warning("Не удалось удалить путь %s после %d попыток: %s", p, retries, exc)
                return False
    return False


def cleanup_paths(*paths: str | Path) -> None:
    """Пакетное удаление путей."""
    for p in paths:
        remove_path(p, on_locked="warn")
