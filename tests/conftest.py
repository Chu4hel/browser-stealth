"""Конфигурация pytest для browser-stealth."""

from __future__ import annotations

import os

# Предотвращаем маршрутизацию локального тестового трафика через внешние прокси
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

from browser_stealth.testing.fixtures import get_e2e_proxy, load_env_file

# Автоматическая загрузка .env при инициализации сессии тестов
load_env_file()

pytest_plugins = ["browser_stealth.testing.fixtures"]

__all__ = ["get_e2e_proxy", "load_env_file"]
