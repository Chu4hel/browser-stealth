"""
Пул асинхронных и синхронных воркеров для параллельной обработки задач скрапинга.
"""

from __future__ import annotations

import asyncio
import concurrent.futures.thread  # noqa: F401
import inspect
import random
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from browser_stealth.concurrency.reaper import IdleBrowserReaper
from browser_stealth.logging import get_logger as setup_logger

if TYPE_CHECKING:
    from .base import BaseTaskQueue
    from .limiter import DomainRateLimiter
    from .models import ScrapingTask


class WorkerPool:
    """Управляющий пул воркеров с поддержкой асинхронных и синхронных обработчиков."""

    def __init__(
        self,
        queue: BaseTaskQueue,
        handler: Callable[[ScrapingTask], Any],
        limiter: DomainRateLimiter | None = None,
        max_workers: int = 5,
        retry_backoff: float = 2.0,
    ) -> None:
        """Инициализирует пул воркеров.

        Args:
            queue: Очередь задач скрапинга.
            handler: Синхронная или асинхронная функция-обработчик задач.
            limiter: Опциональный DomainRateLimiter для контроля нагрузки.
            max_workers: Количество параллельных воркеров.
            retry_backoff: Коэффициент повторного вызова (backoff).
        """
        self.queue = queue
        self.handler = handler
        self.limiter = limiter
        self.max_workers = max_workers
        self.retry_backoff = retry_backoff

        self._running = False
        self._workers: list[asyncio.Task[None]] = []
        self._active_workers_count = 0
        self._lock = asyncio.Lock()
        self._completed_count = 0
        self._failed_count = 0

    @property
    def completed_count(self) -> int:
        """Количество успешно выполненных задач."""
        return self._completed_count

    @property
    def failed_count(self) -> int:
        """Количество проваленных задач."""
        return self._failed_count

    async def _execute_handler(self, task: ScrapingTask) -> None:
        if inspect.iscoroutinefunction(self.handler):
            await self.handler(task)
        else:
            await asyncio.to_thread(self.handler, task)

    async def _worker_loop(self) -> None:
        while self._running:
            task = await self.queue.pop()
            if task is None:
                await asyncio.sleep(random.uniform(0.04, 0.09))
                continue

            async with self._lock:
                self._active_workers_count += 1
                metrics_collector = getattr(self.queue, "metrics", None)
                if metrics_collector:
                    metrics_collector.set_active_workers(self._active_workers_count)

            start_time = time.monotonic()
            status = "completed"
            try:
                if self.limiter:
                    await self.limiter.acquire(task.url)

                await self._execute_handler(task)
                await self.queue.complete(task)
                self._completed_count += 1
            except Exception as e:
                status = "failed"
                await self.queue.fail(task, str(e))
                self._failed_count += 1
            finally:
                duration = time.monotonic() - start_time
                metrics_collector = getattr(self.queue, "metrics", None)
                if metrics_collector:
                    metrics_collector.observe_execution_duration(duration, status=status)
                    metrics_collector.inc_tasks_processed(status=status)

                if self.limiter:
                    self.limiter.release(task.url)
                async with self._lock:
                    self._active_workers_count -= 1
                    if metrics_collector:
                        metrics_collector.set_active_workers(self._active_workers_count)

    async def start(self) -> None:
        """Запускает фоновые задачи воркеров."""
        if self._running:
            return
        self._running = True
        self._workers = [asyncio.create_task(self._worker_loop()) for _ in range(self.max_workers)]

    async def stop(self) -> None:
        """Останавливает все воркеры."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def run_until_complete(self, poll_interval: float = 0.05) -> None:
        """Запускает пул и выполняет задачи до полного опустошения очереди.

        Args:
            poll_interval: Интервал проверки состояния очереди в секундах.
        """
        await self.start()
        try:
            while True:
                size = await self.queue.size()
                async with self._lock:
                    active = self._active_workers_count

                if size == 0 and active == 0:
                    break
                await asyncio.sleep(poll_interval)
        finally:
            await self.stop()


logger = setup_logger(__name__)

TKey = TypeVar("TKey")
TWorker = TypeVar("TWorker")


class BrowserProcessPool(Generic[TKey, TWorker]):
    """Универсальный супервизор пула процессов/сессий браузера.

    Обеспечивает:
    - Гранулярный доступ к браузерным воркерам через индивидуальные блокировки (asyncio.Lock);
    - Потокобезопасный запуск и LRU-вытеснение при превышении лимита max_parallel_workers;
    - Учет времени последней активности (last_used) и проверку занятости (is_busy);
    - Интеграцию с IdleBrowserReaper для фонового закрытия простаивающих экземпляров (Scale-to-Zero).
    """

    def __init__(
        self,
        worker_factory: Callable[[TKey], Awaitable[TWorker]],
        worker_closer: Callable[[TWorker], Awaitable[None]] | None = None,
        max_parallel_workers: int = 2,
        idle_timeout_seconds: float = 120.0,
        scale_to_zero_seconds: float = 300.0,
        check_interval_seconds: float = 15.0,
    ) -> None:
        """Инициализирует супервизор процессов браузеров.

        Args:
            worker_factory: Асинхронная фабрика создания экземпляра воркера по ключу.
            worker_closer: Опциональная асинхронная функция закрытия воркера.
            max_parallel_workers: Максимальное количество одновременно запущенных браузеров.
            idle_timeout_seconds: Таймаут простоя для избыточных браузеров (>1).
            scale_to_zero_seconds: Таймаут простоя до полного закрытия всех браузеров.
            check_interval_seconds: Периодичность проверки простоя в секундах.
        """
        self._worker_factory = worker_factory
        self._worker_closer = worker_closer
        self._max_parallel_workers = max(1, max_parallel_workers)
        self._idle_timeout_seconds = idle_timeout_seconds
        self._scale_to_zero_seconds = scale_to_zero_seconds
        self._check_interval_seconds = check_interval_seconds

        self._workers: dict[TKey, TWorker] = {}
        self._worker_locks: dict[TKey, asyncio.Lock] = {}
        self._worker_last_used: dict[TKey, float] = {}
        self._pool_lock = asyncio.Lock()

        self._idle_reaper = IdleBrowserReaper(
            close_worker_fn=self._close_worker_silently,
            is_worker_busy_fn=self.is_worker_busy,
            get_active_workers_fn=lambda: list(self._workers.keys()),
            get_last_used_fn=lambda k: self._worker_last_used.get(k, time.time()),
            idle_timeout_seconds=idle_timeout_seconds,
            scale_to_zero_seconds=scale_to_zero_seconds,
            check_interval_seconds=check_interval_seconds,
        )

    @property
    def workers(self) -> dict[TKey, TWorker]:
        """Словарь активных запущенных экземпляров воркеров."""
        return self._workers

    @property
    def worker_locks(self) -> dict[TKey, asyncio.Lock]:
        """Словарь индивидуальных блокировок воркеров."""
        return self._worker_locks

    @property
    def worker_last_used(self) -> dict[TKey, float]:
        """Временные метки последнего использования воркеров."""
        return self._worker_last_used

    @property
    def max_parallel_workers(self) -> int:
        """Лимит одновременно работающих процессов."""
        return self._max_parallel_workers

    @max_parallel_workers.setter
    def max_parallel_workers(self, value: int) -> None:
        self._max_parallel_workers = max(1, value)

    def get_worker_lock(self, key: TKey) -> asyncio.Lock:
        """Возвращает индивидуальный лок для воркера, создавая его при необходимости.

        Args:
            key: Идентификатор воркера.

        Returns:
            Экземпляр asyncio.Lock, привязанный к указанному воркеру.
        """
        if key not in self._worker_locks:
            self._worker_locks[key] = asyncio.Lock()
        return self._worker_locks[key]

    def is_worker_busy(self, key: TKey) -> bool:
        """Проверяет, выполняет ли воркер задачу в данный момент.

        Args:
            key: Идентификатор воркера.

        Returns:
            True, если лок воркера захвачен, иначе False.
        """
        lock = self._worker_locks.get(key)
        return lock.locked() if lock is not None else False

    def touch_worker(self, key: TKey) -> None:
        """Обновляет метку времени активности воркера.

        Args:
            key: Идентификатор воркера.
        """
        self._worker_last_used[key] = time.time()

    async def get_or_create_worker(self, key: TKey) -> TWorker:
        """Возвращает существующий или запускает новый экземпляр воркера с LRU-вытеснением.

        Args:
            key: Уникальный ключ воркера (например, имя профиля).

        Returns:
            Экземпляр воркера TWorker.
        """
        async with self._pool_lock:
            if key in self._workers:
                self.touch_worker(key)
                return self._workers[key]

            # Проверяем лимит параллельных процессов и при необходимости вытесняем самый старый
            if len(self._workers) >= self._max_parallel_workers:
                evicted = await self.evict_lru_worker(exclude_key=key)
                if evicted:
                    logger.info(
                        "LRU-вытеснен неактивный воркер %s для освобождения ресурсов", evicted
                    )

            logger.info("Запуск воркера %s в пуле процессов...", key)
            worker = await self._worker_factory(key)
            self._workers[key] = worker
            self.touch_worker(key)
            if key not in self._worker_locks:
                self._worker_locks[key] = asyncio.Lock()

            self.start_reaper()
            return worker

    async def evict_lru_worker(self, exclude_key: TKey | None = None) -> TKey | None:
        """Вытесняет и закрывает наименее недавно использованный свободный воркер.

        Args:
            exclude_key: Ключ воркера, который нельзя вытеснять (например, только что запрошенный).

        Returns:
            Ключ вытесненного воркера или None, если свободных воркеров не нашлось.
        """
        candidates: list[tuple[TKey, float]] = []
        for k, last_used in self._worker_last_used.items():
            if k == exclude_key or k not in self._workers:
                continue
            if not self.is_worker_busy(k):
                candidates.append((k, last_used))

        if not candidates:
            logger.warning("Все активные воркеры заняты, LRU-вытеснение невозможно.")
            return None

        candidates.sort(key=lambda x: x[1])
        victim_key = candidates[0][0]
        await self._close_worker_internal(victim_key)
        return victim_key

    async def _close_worker_internal(self, key: TKey) -> bool:
        """Внутреннее закрытие воркера без захвата _pool_lock (предполагает, что лок уже взят)."""
        worker = self._workers.pop(key, None)
        self._worker_last_used.pop(key, None)
        self._worker_locks.pop(key, None)

        if worker is not None:
            try:
                if self._worker_closer is not None:
                    await self._worker_closer(worker)
                elif hasattr(worker, "close") and callable(worker.close):
                    res = worker.close()
                    if inspect.isawaitable(res):
                        await res
            except Exception as exc:
                logger.debug("Ошибка при закрытии воркера %s: %s", key, exc)
            return True
        return False

    async def close_worker(self, key: TKey) -> bool:
        """Корректно закрывает и удаляет воркер из пула.

        Args:
            key: Идентификатор воркера.

        Returns:
            True, если воркер был найден и закрыт, иначе False.
        """
        async with self._pool_lock:
            return await self._close_worker_internal(key)

    async def _close_worker_silently(self, key: TKey) -> None:
        """Закрывает воркер для reaper'а простоя, отбрасывая результат.

        Args:
            key: Идентификатор воркера.
        """
        await self.close_worker(key)

    async def close_all(self) -> None:
        """Останавливает мониторинг простоя и закрывает все активные воркеры."""
        await self.stop_reaper()
        async with self._pool_lock:
            keys = list(self._workers.keys())
        for k in keys:
            await self.close_worker(k)

    def start_reaper(self) -> None:
        """Запускает фоновую задачу обнаружения и закрытия простаивающих воркеров."""
        self._idle_reaper.start()

    async def stop_reaper(self) -> None:
        """Останавливает фоновую задачу сборщика простоя."""
        await self._idle_reaper.stop()

    async def reap_idle_workers(self) -> int:
        """Ручной триггер закрытия простаивающих воркеров.

        Returns:
            Количество закрытых простаивающих воркеров.
        """
        return await self._idle_reaper.reap()


__all__ = ["BrowserProcessPool", "WorkerPool"]
