"""Конфигурация pytest для browser-stealth."""

import os

# Предотвращаем маршрутизацию локального трафика через внешние системные прокси
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

pytest_plugins = ["browser_stealth.testing.fixtures"]
