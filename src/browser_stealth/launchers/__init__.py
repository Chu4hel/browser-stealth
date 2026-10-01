"""Фабрики быстрого запуска браузеров с встроенным антидетектом."""

from __future__ import annotations

from .nodriver import launch_nodriver

__all__ = ["launch_nodriver"]
