"""Тесты флагов запуска E2E-браузера."""

from __future__ import annotations

import os
import sys

import pytest

from browser_stealth.testing.fixtures import get_e2e_browser_args


def test_no_sandbox_is_not_added_on_non_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что вне Linux sandbox не отключается."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("CH_TESTING_NO_SANDBOX", "1")

    assert get_e2e_browser_args() == []


def test_no_sandbox_is_added_on_linux_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет CH_TESTING_NO_SANDBOX=1 на Linux."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("CH_TESTING_NO_SANDBOX", "1")

    assert get_e2e_browser_args() == ["--no-sandbox", "--disable-setuid-sandbox"]


def test_no_sandbox_is_not_added_on_linux_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что без настройки и без root флаг не добавляется."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("CH_TESTING_NO_SANDBOX", raising=False)
    if hasattr(os, "geteuid"):
        monkeypatch.setattr(os, "geteuid", lambda: 1000)

    assert get_e2e_browser_args() == []
