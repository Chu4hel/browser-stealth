from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from browser_stealth.launchers.nodriver import ChromiumProcessManager


@pytest.mark.asyncio
async def test_chromium_process_manager_launch_and_stop(tmp_path: Path) -> None:
    profile_dir = tmp_path / "test_prof"
    mgr = ChromiumProcessManager()

    mock_browser = MagicMock()
    mock_browser.tabs = [MagicMock()]
    mock_browser.update_targets = AsyncMock()
    mock_browser.aclose = AsyncMock()
    mock_browser.stop = MagicMock()

    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_proc._transport = MagicMock()
    mock_browser._process = mock_proc

    with patch("nodriver.start", new=AsyncMock(return_value=mock_browser)) as mock_start:
        browser, tunnel = await mgr.launch(
            profile_path=profile_dir,
            headless=True,
            profile_name="test_prof",
        )
        assert browser is mock_browser
        assert tunnel is None
        assert mock_start.called
        call_kwargs = mock_start.call_args.kwargs
        args = call_kwargs.get("browser_args", [])
        assert "--disable-session-crashed-bubble" in args
        assert "--hide-crash-restore-bubble" in args

    # Проверяем остановку
    await mgr.stop(browser=mock_browser, profile_path=profile_dir)
    assert mock_browser.aclose.called
    assert mock_browser.stop.called
    assert mock_proc.stdin.close.called
