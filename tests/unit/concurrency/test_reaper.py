"""Тесты сторожа простоя IdleBrowserReaper и его конфигурации."""

from __future__ import annotations

import time

import pytest

from browser_stealth.concurrency.reaper import IdleBrowserReaper, IdleReaperConfig


class _FakeWorkers:
    """Управляет состоянием фейковых воркеров для тестов reaper'а."""

    def __init__(self, last_used: dict[str, float], busy: set[str] | None = None) -> None:
        self.last_used = last_used
        self.busy = busy or set()
        self.closed: list[str] = []

    def active(self) -> list[str]:
        """Возвращает список идентификаторов воркеров."""
        return list(self.last_used)

    def is_busy(self, key: str) -> bool:
        """Возвращает признак занятости воркера."""
        return key in self.busy

    def last_used_at(self, key: str) -> float:
        """Возвращает время последнего использования."""
        return self.last_used[key]

    def close(self, key: str) -> None:
        """Синхронно закрывает воркер и запоминает вызов."""
        self.closed.append(key)
        self.last_used.pop(key, None)


def _reaper(
    workers: _FakeWorkers,
    *,
    idle: float = 10.0,
    scale_to_zero: float = 1000.0,
    enabled: bool = True,
) -> IdleBrowserReaper[str]:
    """Создаёт reaper с фейковыми колбэками."""
    return IdleBrowserReaper(
        close_worker_fn=workers.close,
        is_worker_busy_fn=workers.is_busy,
        get_active_workers_fn=workers.active,
        get_last_used_fn=workers.last_used_at,
        idle_timeout_seconds=idle,
        scale_to_zero_seconds=scale_to_zero,
        enabled=enabled,
    )


@pytest.mark.asyncio
async def test_disabled_reaper_does_nothing() -> None:
    """Проверяет, что выключенный reaper не закрывает воркеры."""
    workers = _FakeWorkers({"a": time.time() - 1000})
    reaper = _reaper(workers, enabled=False)

    assert await reaper.reap() == 0
    assert workers.closed == []


@pytest.mark.asyncio
async def test_busy_worker_is_skipped() -> None:
    """Проверяет, что занятый воркер не закрывается."""
    workers = _FakeWorkers({"a": time.time() - 1000, "b": time.time() - 1000}, busy={"a"})
    reaper = _reaper(workers, idle=1.0)

    closed = await reaper.reap()

    assert closed == 1
    assert workers.closed == ["b"]


@pytest.mark.asyncio
async def test_idle_worker_above_idle_timeout_is_closed_when_pool_has_many() -> None:
    """Проверяет закрытие самого старого простаивающего воркера из нескольких."""
    now = time.time()
    workers = _FakeWorkers({"old": now - 500, "fresh": now - 1})
    reaper = _reaper(workers, idle=10.0, scale_to_zero=1000.0)

    closed = await reaper.reap()

    assert closed == 1
    assert workers.closed == ["old"]
    assert "fresh" in workers.last_used


@pytest.mark.asyncio
async def test_single_worker_is_closed_only_by_scale_to_zero() -> None:
    """Проверяет, что последний воркер закрывается только по scale-to-zero."""
    now = time.time()
    workers = _FakeWorkers({"only": now - 50})
    reaper = _reaper(workers, idle=10.0, scale_to_zero=100.0)

    assert await reaper.reap() == 0
    assert workers.closed == []

    workers.last_used["only"] = now - 500
    assert await reaper.reap() == 1
    assert workers.closed == ["only"]


@pytest.mark.asyncio
async def test_scale_to_zero_disabled_keeps_last_worker() -> None:
    """Проверяет, что при scale_to_zero=0 последний воркер не закрывается."""
    workers = _FakeWorkers({"only": time.time() - 10000})
    reaper = _reaper(workers, idle=1.0, scale_to_zero=0.0)

    assert await reaper.reap() == 0
    assert workers.closed == []


@pytest.mark.asyncio
async def test_async_closer_is_awaited() -> None:
    """Проверяет поддержку асинхронного колбэка закрытия."""
    now = time.time()
    closed: list[str] = []

    async def close(key: str) -> None:
        closed.append(key)

    reaper = IdleBrowserReaper(
        close_worker_fn=close,
        is_worker_busy_fn=lambda key: False,
        get_active_workers_fn=lambda: ["only"],
        get_last_used_fn=lambda key: now - 500,
        idle_timeout_seconds=10.0,
        scale_to_zero_seconds=100.0,
    )

    assert await reaper.reap() == 1
    assert closed == ["only"]


def test_config_presets_disable_or_tune_scale_to_zero() -> None:
    """Проверяет пресеты конфигурации."""
    assert IdleReaperConfig.preset_keep_warm().scale_to_zero_seconds == 0.0
    assert IdleReaperConfig.preset_aggressive().idle_timeout_seconds == 30.0
    assert IdleReaperConfig.preset_relaxed().scale_to_zero_seconds == 900.0
