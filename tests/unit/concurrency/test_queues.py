"""Тесты очередей задач: InMemoryTaskQueue и PersistentTaskQueue."""

from __future__ import annotations

from pathlib import Path

import pytest

from browser_stealth.concurrency.models import ScrapingTask
from browser_stealth.concurrency.queues import InMemoryTaskQueue, PersistentTaskQueue


def _task(url: str, *, priority: int = 0, **kwargs: object) -> ScrapingTask:
    """Создаёт задачу с уникальным URL по умолчанию."""
    return ScrapingTask(url=url, priority=priority, **kwargs)


@pytest.mark.asyncio
async def test_in_memory_queue_orders_by_priority_then_creation() -> None:
    """Проверяет приоритетную выдачу задач."""
    queue = InMemoryTaskQueue()

    await queue.push(_task("https://a/1", priority=0))
    await queue.push(_task("https://a/2", priority=10))
    await queue.push(_task("https://a/3", priority=5))

    assert (await queue.pop()).url == "https://a/2"
    assert (await queue.pop()).url == "https://a/3"
    assert (await queue.pop()).url == "https://a/1"
    assert await queue.pop() is None


@pytest.mark.asyncio
async def test_in_memory_queue_deduplicates_and_clear_resets() -> None:
    """Проверяет дедупликацию по dedup_key и сброс через clear."""
    queue = InMemoryTaskQueue()
    task = _task("https://example.com/page")

    assert await queue.push(task) is True
    assert await queue.push(task) is False
    assert await queue.size() == 1

    await queue.clear()
    assert await queue.size() == 0
    assert await queue.push(task) is True


@pytest.mark.asyncio
async def test_in_memory_queue_retries_until_max_attempts() -> None:
    """Проверяет повторную постановку задачи и прекращение после лимита."""
    queue = InMemoryTaskQueue()
    await queue.push(_task("https://example.com/fail", max_attempts=2))

    first = await queue.pop()
    assert first is not None
    await queue.fail(first, "timeout")

    assert first.attempts == 1
    assert first.last_error == "timeout"
    assert await queue.size() == 1

    retried = await queue.pop()
    assert retried is not None
    await queue.fail(retried, "timeout again")

    assert retried.attempts == 2
    assert await queue.size() == 0


@pytest.mark.asyncio
async def test_in_memory_queue_complete_is_noop() -> None:
    """Проверяет, что complete не возвращает задачу в очередь."""
    queue = InMemoryTaskQueue()
    task = _task("https://example.com/ok")
    await queue.push(task)
    popped = await queue.pop()

    assert popped is not None
    await queue.complete(popped)
    assert await queue.size() == 0


@pytest.mark.asyncio
async def test_persistent_queue_survives_reopen(tmp_path: Path) -> None:
    """Проверяет сохранение задач в SQLite между экземплярами очереди."""
    db_path = tmp_path / "queue.db"
    first = PersistentTaskQueue(db_path)
    try:
        await first.push(_task("https://example.com/persisted", priority=3, payload={"k": "v"}))
    finally:
        await first.close()

    second = PersistentTaskQueue(db_path)
    try:
        assert await second.size() == 1
        task = await second.pop()
        assert task is not None
        assert task.url == "https://example.com/persisted"
        assert task.priority == 3
        assert task.payload == {"k": "v"}
    finally:
        await second.close()


@pytest.mark.asyncio
async def test_persistent_queue_dedup_across_instances(tmp_path: Path) -> None:
    """Проверяет дедупликацию через общую базу данных."""
    db_path = tmp_path / "queue.db"
    first = PersistentTaskQueue(db_path)
    second = PersistentTaskQueue(db_path)
    try:
        assert await first.push(_task("https://example.com/dup")) is True
        assert await second.push(_task("https://example.com/dup")) is False
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_persistent_queue_priority_and_complete(tmp_path: Path) -> None:
    """Проверяет приоритет, complete и фильтрацию по статусу."""
    queue = PersistentTaskQueue(tmp_path / "queue.db")
    try:
        await queue.push(_task("https://example.com/low", priority=1))
        await queue.push(_task("https://example.com/high", priority=9))

        high = await queue.pop()
        assert high is not None and high.url == "https://example.com/high"
        await queue.complete(high)

        assert await queue.size() == 1
        low = await queue.pop()
        assert low is not None and low.url == "https://example.com/low"
        assert await queue.pop() is None
    finally:
        await queue.close()


@pytest.mark.asyncio
async def test_persistent_queue_retries_until_max_attempts(tmp_path: Path) -> None:
    """Проверяет повторную выдачу после fail и перевод в failed."""
    queue = PersistentTaskQueue(tmp_path / "queue.db")
    try:
        await queue.push(_task("https://example.com/retry", max_attempts=2))

        first = await queue.pop()
        assert first is not None
        await queue.fail(first, "boom")
        assert await queue.size() == 1

        second = await queue.pop()
        assert second is not None
        await queue.fail(second, "boom again")
        assert await queue.size() == 0
    finally:
        await queue.close()


@pytest.mark.asyncio
async def test_persistent_queue_clear_allows_same_key_again(tmp_path: Path) -> None:
    """Проверяет очистку задач и истории дедупликации."""
    queue = PersistentTaskQueue(tmp_path / "queue.db")
    try:
        task = _task("https://example.com/reuse")
        assert await queue.push(task) is True
        await queue.clear()

        assert await queue.size() == 0
        assert await queue.push(task) is True
    finally:
        await queue.close()
