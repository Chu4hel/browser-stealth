"""Тесты защиты локальных CDP-адресов от системного прокси."""

from __future__ import annotations

import os

from browser_stealth.env import LOCAL_NO_PROXY_HOSTS, ensure_local_no_proxy


def test_ensure_local_no_proxy_sets_both_variables(monkeypatch) -> None:
    """Функция создаёт обе переменные с loopback-адресами."""
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    ensure_local_no_proxy()

    expected = ",".join(LOCAL_NO_PROXY_HOSTS)
    assert os.environ["NO_PROXY"] == expected
    assert os.environ["no_proxy"] == expected


def test_ensure_local_no_proxy_preserves_and_deduplicates_entries(monkeypatch) -> None:
    """Существующие записи сохраняются, дубликаты не добавляются."""
    monkeypatch.setenv("NO_PROXY", "example.com, LOCALHOST, 10.0.0.0/8")

    ensure_local_no_proxy()

    # На Windows имена переменных регистронезависимы, поэтому обе записи
    # указывают на одно и то же значение.
    expected = "example.com,LOCALHOST,10.0.0.0/8,127.0.0.1,::1"
    assert os.environ["NO_PROXY"] == expected
    assert os.environ["no_proxy"] == expected


def test_ensure_local_no_proxy_is_idempotent(monkeypatch) -> None:
    """Повторный вызов не меняет уже подготовленное окружение."""
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost,::1")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost,::1")

    ensure_local_no_proxy()
    ensure_local_no_proxy()

    assert os.environ["NO_PROXY"] == "127.0.0.1,localhost,::1"
    assert os.environ["no_proxy"] == "127.0.0.1,localhost,::1"
