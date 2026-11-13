from unittest.mock import AsyncMock, patch

import pytest

from browser_stealth.proxy.cache import BoundedMemoryCacheBackend
from browser_stealth.proxy.resolver import SmartProxyResolver


def test_bounded_memory_cache_backend_lru_and_max_entries() -> None:
    cache = BoundedMemoryCacheBackend(max_entries=3)

    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")

    assert cache.get("k1") == "v1"
    assert cache.get("k2") == "v2"
    assert cache.get("k3") == "v3"

    # Доступ к k1 перемещает его в конец (недавний)
    _ = cache.get("k1")

    # Добавление k4 должно вытеснить k2 (как самый старый)
    cache.set("k4", "v4")

    assert cache.get("k1") == "v1"
    assert cache.get("k2") is None  # вытеснен
    assert cache.get("k3") == "v3"
    assert cache.get("k4") == "v4"


def test_bounded_memory_cache_backend_ttl() -> None:
    cache = BoundedMemoryCacheBackend(max_entries=10)
    cache.set("k_expire", "val", ttl=-1)
    assert cache.get("k_expire") is None
    assert cache.exists("k_expire") is False


def test_bounded_memory_cache_clear_and_delete() -> None:
    cache = BoundedMemoryCacheBackend(max_entries=10)
    cache.set("k1", "v1", tags=["t1"])
    cache.set("k2", "v2", tags=["t2"])
    assert cache.exists("k1") is True

    cache.delete("k1")
    assert cache.exists("k1") is False

    cache.invalidate_tag("t2")
    assert cache.exists("k2") is False


@pytest.mark.asyncio
async def test_smart_proxy_resolver_memory_cache() -> None:
    resolver = SmartProxyResolver(use_memory_cache=True, max_cache_entries=50)
    assert isinstance(resolver.cache, BoundedMemoryCacheBackend)

    with patch.object(resolver, "probe_proxy", new=AsyncMock(return_value=True)):
        res1 = await resolver.resolve("127.0.0.1:8080")
        assert res1 == "http://127.0.0.1:8080"
        # Проверяем, что результат закешировался в памяти
        assert resolver.cache.exists("127.0.0.1:8080")
