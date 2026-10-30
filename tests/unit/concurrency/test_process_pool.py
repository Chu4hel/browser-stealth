import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from browser_stealth.concurrency.pool import BrowserProcessPool


@pytest.mark.asyncio
async def test_process_pool_create_and_reuse() -> None:
    factory = AsyncMock(side_effect=lambda name: MagicMock(name=f"worker_{name}"))
    closer = AsyncMock()

    pool = BrowserProcessPool(
        worker_factory=factory,
        worker_closer=closer,
        max_parallel_workers=2,
    )

    w1 = await pool.get_or_create_worker("p1")
    assert w1 is not None
    assert factory.call_count == 1

    # Повторный вызов возвращает тот же экземпляр
    w1_again = await pool.get_or_create_worker("p1")
    assert w1_again is w1
    assert factory.call_count == 1

    await pool.close_all()


@pytest.mark.asyncio
async def test_process_pool_lru_eviction() -> None:
    factory = AsyncMock(side_effect=lambda name: MagicMock(name=f"worker_{name}"))
    closer = AsyncMock()

    pool = BrowserProcessPool(
        worker_factory=factory,
        worker_closer=closer,
        max_parallel_workers=2,
    )

    await pool.get_or_create_worker("p1")
    await asyncio.sleep(0.01)
    await pool.get_or_create_worker("p2")

    assert len(pool.workers) == 2

    # Создание 3-го должно вытеснить p1 (как самый старый)
    await asyncio.sleep(0.01)
    w3 = await pool.get_or_create_worker("p3")

    assert w3 is not None
    assert "p1" not in pool.workers
    assert "p2" in pool.workers
    assert "p3" in pool.workers
    assert closer.call_count == 1

    await pool.close_all()


@pytest.mark.asyncio
async def test_process_pool_busy_worker_protection() -> None:
    factory = AsyncMock(side_effect=lambda name: MagicMock(name=f"worker_{name}"))
    closer = AsyncMock()

    pool = BrowserProcessPool(
        worker_factory=factory,
        worker_closer=closer,
        max_parallel_workers=2,
    )

    await pool.get_or_create_worker("p1")
    await pool.get_or_create_worker("p2")

    # Блокируем p1
    p1_lock = pool.get_worker_lock("p1")
    await p1_lock.acquire()
    try:
        assert pool.is_worker_busy("p1") is True
        # Запуск p3 должен вытеснить p2 (так как p1 занят!)
        await pool.get_or_create_worker("p3")
        assert "p1" in pool.workers
        assert "p2" not in pool.workers
        assert "p3" in pool.workers
    finally:
        p1_lock.release()

    await pool.close_all()
