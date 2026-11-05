"""Тесты механизма чтения прокси для E2E тестов из переменных окружения и .env файлов."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from browser_stealth.testing.fixtures import get_e2e_proxy, load_env_file


def test_get_e2e_proxy_from_env_vars() -> None:
    """Проверяет приоритетное извлечение прокси из TEST_PROXY и E2E_PROXY."""
    with patch.dict(os.environ, {"TEST_PROXY": "http://user:pass@1.2.3.4:8080"}, clear=False):
        assert get_e2e_proxy() == "http://user:pass@1.2.3.4:8080"

    with patch.dict(
        os.environ, {"TEST_PROXY": "", "E2E_PROXY": "socks5://proxy.host:1080"}, clear=False
    ):
        assert get_e2e_proxy() == "socks5://proxy.host:1080"


def test_load_env_file_parsing(tmp_path: Path) -> None:
    """Проверяет парсинг формата .env файла с комментариями и кавычками."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
        # Тестовый комментарий
        TEST_PROXY="http://secret_user:secret_pass@proxy.net:3128"
        SOME_OTHER_KEY='value'
        export EXPORTED_VAR=exported_val
        EMPTY_LINE=
        """,
        encoding="utf-8",
    )

    clean_env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("TEST_PROXY", "SOME_OTHER_KEY", "EXPORTED_VAR")
    }
    with patch.dict(os.environ, clean_env, clear=True):
        load_env_file(env_file)
        assert os.environ.get("TEST_PROXY") == "http://secret_user:secret_pass@proxy.net:3128"
        assert os.environ.get("SOME_OTHER_KEY") == "value"
        assert os.environ.get("EXPORTED_VAR") == "exported_val"
