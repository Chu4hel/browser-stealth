"""Тесты ограничителя частоты запросов DomainRateLimiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from browser_stealth.concurrency.limiter import DomainRateLimiter


def test_get_domain_normalizes_host_and_strips_port() -> None:
    """Проверяет извлечение домена в нижнем регистре без порта."""
    limiter = DomainRateLimiter()

    assert limiter.get_domain("https://Example.COM:8443/path?q=1") == "example.com"
    assert limiter.get_domain("http://sub.example.com/") == "sub.example.com"
    assert limiter.get_domain("not-a-url") == "default"


def test_rule_lookup_supports_wildcards_and_fallbacks() -> None:
    """Проверяет выбор правила по маске и задержку по умолчанию."""
    limiter = DomainRateLimiter(
        default_delay=1.5,
        domain_rules={"*.wikipedia.org": 2.0, "example.com": 3.0},
    )

    assert limiter.get_rule_key_and_delay("en.wikipedia.org") == ("*.wikipedia.org", 2.0)
    assert limiter.get_rule_key_and_delay("example.com") == ("example.com", 3.0)
    assert limiter.get_rule_key_and_delay("other.org") == ("other.org", 1.5)


@pytest.mark.asyncio
async def test_acquire_delays_requests_to_same_domain() -> None:
    """Проверяет паузу между последовательными запросами к домену."""
    limiter = DomainRateLimiter(default_delay=0.08)
    url = "https://example.com/page"

    await limiter.acquire(url)
    started = time.monotonic()
    await limiter.acquire(url)
    elapsed = time.monotonic() - started

    assert elapsed >= 0.06


@pytest.mark.asyncio
async def test_different_domains_do_not_block_each_other() -> None:
    """Проверяет независимость задержек для разных доменов."""
    limiter = DomainRateLimiter(default_delay=0.2)

    await limiter.acquire("https://a.example/page")
    started = time.monotonic()
    await limiter.acquire("https://b.example/page")
    elapsed = time.monotonic() - started

    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_max_domain_concurrency_blocks_until_release() -> None:
    """Проверяет ограничение одновременных подключений к домену."""
    limiter = DomainRateLimiter(
        default_delay=0.0,
        max_domain_concurrency={"example.com": 1},
    )
    url = "https://example.com/page"

    await limiter.acquire(url)
    waiting = asyncio.create_task(limiter.acquire(url))
    await asyncio.sleep(0.05)

    assert not waiting.done()

    limiter.release(url)
    await asyncio.wait_for(waiting, timeout=1.0)
    assert waiting.done()


@pytest.mark.asyncio
async def test_release_without_acquire_does_not_go_negative() -> None:
    """Проверяет безопасный release без предварительного acquire."""
    limiter = DomainRateLimiter(default_delay=0.0)
    url = "https://example.com/page"

    limiter.release(url)
    limiter.release(url)

    assert limiter._active_connections.get("example.com", 0) == 0


@pytest.mark.asyncio
async def test_second_concurrent_acquire_releases_semaphore_after_use() -> None:
    """Проверяет, что семафор не блокирует домен после освобождения слота."""
    limiter = DomainRateLimiter(
        default_delay=0.0,
        max_domain_concurrency={"example.com": 1},
    )
    url = "https://example.com/page"

    await limiter.acquire(url)
    limiter.release(url)

    await asyncio.wait_for(limiter.acquire(url), timeout=1.0)
    limiter.release(url)
