from unittest.mock import AsyncMock, MagicMock
import pytest

from browser_stealth.concurrency.tabs import SessionTabPool


@pytest.mark.asyncio
async def test_session_tab_pool_lifecycle() -> None:
    close_mock = AsyncMock()
    pool = SessionTabPool(max_tabs=2, session_ttl_seconds=100.0, close_tab_fn=close_mock)

    browser = MagicMock()
    tab1 = MagicMock()
    tab2 = MagicMock()
    tab3 = MagicMock()

    browser.get = AsyncMock(side_effect=[tab1, tab2, tab3])

    # 1. Создание первой сессии
    t1, is_new = await pool.get_or_create_tab(browser, "session-1")
    assert t1 == tab1
    assert is_new is True
    assert pool.active_session_count == 1

    # 2. Повторное обращение возвращает ту же вкладку
    tab1.evaluate = AsyncMock(return_value=2)
    t1_again, is_new = await pool.get_or_create_tab(browser, "session-1")
    assert t1_again == tab1
    assert is_new is False

    # 3. Создание второй сессии
    t2, is_new = await pool.get_or_create_tab(browser, "session-2")
    assert t2 == tab2
    assert is_new is True
    assert pool.active_session_count == 2

    # 4. Создание третьей сессии превышает max_tabs=2, вытесняя session-1 по LRU
    tab2.evaluate = AsyncMock(return_value=2)
    t3, is_new = await pool.get_or_create_tab(browser, "session-3")
    assert t3 == tab3
    assert is_new is True
    assert pool.active_session_count == 2
    assert pool.get_session("session-1") is None
    close_mock.assert_awaited_with(tab1)

    # 5. Ручное закрытие сессии
    closed = await pool.close_session("session-2")
    assert closed is True
    assert pool.active_session_count == 1


@pytest.mark.asyncio
async def test_session_tab_pool_ttl_eviction() -> None:
    close_mock = AsyncMock()
    pool = SessionTabPool(max_tabs=5, session_ttl_seconds=0.01, close_tab_fn=close_mock)

    browser = MagicMock()
    tab1 = MagicMock()
    tab2 = MagicMock()
    browser.get = AsyncMock(side_effect=[tab1, tab2])

    await pool.get_or_create_tab(browser, "s1")
    assert pool.active_session_count == 1

    import asyncio
    await asyncio.sleep(0.02)

    # При создании s2, сессия s1 должна закрыться по TTL
    await pool.get_or_create_tab(browser, "s2")
    assert pool.get_session("s1") is None
    assert pool.active_session_count == 1
    close_mock.assert_awaited_with(tab1)
