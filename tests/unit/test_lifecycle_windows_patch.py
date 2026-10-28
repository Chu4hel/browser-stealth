from unittest.mock import MagicMock, patch

from browser_stealth.lifecycle import patch_windows_asyncio_transport_cleanup


def test_patch_windows_asyncio_transport_cleanup_non_win32() -> None:
    with patch("sys.platform", "linux"):
        # Должен завершиться без исключений
        patch_windows_asyncio_transport_cleanup()


def test_patch_windows_asyncio_transport_cleanup_win32() -> None:
    with patch("sys.platform", "win32"):
        patch_windows_asyncio_transport_cleanup()
        # Повторный вызов безопасен (идемпотентность)
        patch_windows_asyncio_transport_cleanup()
