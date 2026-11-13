# Конкурентность и пулы (concurrency)

Модуль `browser_stealth.concurrency` — это очередь задач, пул воркеров, пул
браузерных процессов и сессионных вкладок, ограничитель частоты запросов и
фоновый reaper простаивающих браузеров.

```python
from browser_stealth.concurrency import (
    InMemoryTaskQueue,
    ScrapingTask,
    WorkerPool,
    DomainRateLimiter,
)
```

## 1. Очереди задач

`ScrapingTask` — dataclass с полями `url`, `priority`, `payload`, `attempts`,
`max_attempts`, `task_id`, `dedup_key`, `created_at`, `last_error`.

| Очередь | Хранение | Особенности |
|---|---|---|
| `InMemoryTaskQueue(name="default")` | память | приоритетная, дедупликация по `dedup_key` |
| `PersistentTaskQueue(db_path="scraping_queue.db")` | SQLite | переживает перезапуск процесса |
| `RedisTaskQueue(redis_url=...)` | Redis ZSET | распределённая, требует extra `redis` |

```python
queue = InMemoryTaskQueue()
await queue.push(ScrapingTask(url="https://example.com/1", priority=10))
task = await queue.pop()
await queue.complete(task)
```

Для `RedisTaskQueue` установите extra:

```bash
uv add "browser-stealth[redis]"
```

## 2. Пул воркеров

`WorkerPool` забирает задачи из очереди и вызывает sync/async-обработчик,
повторяя неудачные задачи с backoff.

```python
async def handle(task: ScrapingTask) -> None: ...


pool = WorkerPool(
    queue=queue,
    handler=handle,
    limiter=DomainRateLimiter(default_delay=1.0),
    max_workers=5,
    retry_backoff=2.0,
)
await pool.start()
await pool.run_until_complete()  # или await pool.stop()
```

`completed_count` и `failed_count` доступны как свойства.

## 3. Пул браузерных процессов

`BrowserProcessPool` — супервизор тяжёлых воркеров (браузеров): по одному на
ключ, с LRU-вытеснением при превышении `max_parallel_workers` и интеграцией с
`IdleBrowserReaper`.

```python
pool = BrowserProcessPool(
    worker_factory=lambda profile: launch_nodriver(profile=profile),
    worker_closer=lambda browser: browser.stop(),
    max_parallel_workers=2,
    idle_timeout_seconds=120,
    scale_to_zero_seconds=300,
)

browser = await pool.get_or_create_worker("profile-a")
```

## 4. Пул сессионных вкладок

`SessionTabPool` удерживает вкладки по `session_id` с TTL и LRU-вытеснением:

```python
tabs = SessionTabPool(max_tabs=5, session_ttl_seconds=600)
tab = await tabs.get_or_create_tab("session-1", factory=open_tab)
await tabs.close_session("session-1")
```

Метод `is_tab_alive` проверяет отзывчивость вкладки, `close_all_sessions` —
закрывает всё при завершении.

## 5. Ограничитель частоты

`DomainRateLimiter` ограничивает частоту и параллельность по домену:

```python
limiter = DomainRateLimiter(
    default_delay=1.0,
    domain_rules={"*.wikipedia.org": 2.0},
    max_domain_concurrency={"example.com": 2},
)
await limiter.acquire("https://example.com/page")
```

## 6. Reaper простоя

`IdleBrowserReaper` в фоне закрывает лишние воркеры после `idle_timeout_seconds`
и все воркеры после `scale_to_zero_seconds`. Используется внутри
`BrowserProcessPool`, но может подключаться отдельно:

```python
from browser_stealth.concurrency import IdleBrowserReaper, IdleReaperConfig

async with IdleBrowserReaper(
    close_worker_fn=close_browser,
    is_worker_busy_fn=lambda key: False,
    get_active_workers_fn=lambda: ["profile-a"],
    get_last_used_fn=lambda key: time.time(),
    config=IdleReaperConfig(),
) as reaper:
    await reaper.reap()
```

`QueueMetricsCollector` собирает метрики очередей (`QueueMetricsCollector` в
`concurrency/metrics.py`), если `enable_metrics=True`.
