"""Тесты кросс-атрибутной согласованности ОС, GPU рендерера и Client Hints."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from browser_stealth.fingerprint.models import FingerprintProfile, WebGLFingerprint
from browser_stealth.fingerprint.procedural import ProceduralSynthesizer


def test_windows_fingerprint_cross_consistency() -> None:
    """Проверяет генерацию непротиворечивого профиля для Windows."""
    synth = ProceduralSynthesizer(os_target="windows")

    for i in range(20):
        fp = synth.synthesize(f"seed_win_{i}")
        assert fp.os == "windows"
        assert "Direct3D11" in fp.webgl.renderer
        assert "Windows NT 10.0; Win64; x64" in fp.user_agent
        assert fp.client_hints.get("platform") == "Windows"
        assert fp.client_hints.get("architecture") == "x86"
        assert fp.client_hints.get("bitness") == "64"
        assert fp.screen.avail_height < fp.screen.height


def test_macos_fingerprint_cross_consistency() -> None:
    """Проверяет генерацию непротиворечивого профиля для macOS."""
    synth = ProceduralSynthesizer(os_target="macos")

    for i in range(20):
        fp = synth.synthesize(f"seed_mac_{i}")
        assert fp.os == "macos"
        assert "Direct3D" not in fp.webgl.renderer
        assert "D3D" not in fp.webgl.renderer
        assert "OpenGL 4.1" in fp.webgl.renderer
        assert fp.webgl.vendor in (
            "Google Inc. (Apple)",
            "Google Inc. (Intel)",
            "Google Inc. (AMD)",
        )
        assert "Macintosh; Intel Mac OS X" in fp.user_agent
        assert fp.client_hints.get("platform") == "macOS"
        assert fp.client_hints.get("bitness") == "64"
        if "Apple M" in fp.webgl.renderer:
            assert fp.client_hints.get("architecture") == "arm"
        else:
            assert fp.client_hints.get("architecture") == "x86"

        assert fp.screen.avail_height == fp.screen.height - 25

        # Проверка периферии macOS
        labels = [d.label for d in fp.media_devices]
        assert any("MacBook" in lbl or "Internal" in lbl or "Built-in" in lbl for lbl in labels)


def test_linux_fingerprint_cross_consistency() -> None:
    """Проверяет генерацию непротиворечивого профиля для Linux."""
    synth = ProceduralSynthesizer(os_target="linux")

    for i in range(20):
        fp = synth.synthesize(f"seed_linux_{i}")
        assert fp.os == "linux"
        assert "Direct3D" not in fp.webgl.renderer
        assert "D3D" not in fp.webgl.renderer
        assert "OpenGL 4.5.0" in fp.webgl.renderer
        assert "X11; Linux x86_64" in fp.user_agent
        assert fp.client_hints.get("platform") == "Linux"
        assert fp.client_hints.get("architecture") == "x86"
        assert fp.client_hints.get("bitness") == "64"
        assert fp.screen.avail_height == fp.screen.height - 32

        # Проверка периферии Linux
        labels = [d.label for d in fp.media_devices]
        assert any("PulseAudio" in lbl or "ALSA" in lbl or "HD Audio" in lbl for lbl in labels)


def test_pydantic_validator_rejects_direct3d_on_macos() -> None:
    """Проверяет валидацию Pydantic при попытке создать macOS с Direct3D."""
    with pytest.raises(ValidationError, match="не может использовать Direct3D"):
        FingerprintProfile(
            os="macos",
            webgl=WebGLFingerprint(
                renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"
            ),
            client_hints={"platform": "macOS"},
        )


def test_pydantic_validator_rejects_direct3d_on_linux() -> None:
    """Проверяет валидацию Pydantic при попытке создать Linux с Direct3D."""
    with pytest.raises(ValidationError, match="не может использовать Direct3D"):
        FingerprintProfile(
            os="linux",
            webgl=WebGLFingerprint(
                renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"
            ),
            client_hints={"platform": "Linux"},
        )


def test_pydantic_validator_rejects_mismatched_client_hints() -> None:
    """Проверяет валидацию Pydantic при несовпадении platform в Client Hints с ОС."""
    with pytest.raises(ValidationError, match="ожидается platform 'macOS'"):
        FingerprintProfile(
            os="macos",
            webgl=WebGLFingerprint(renderer="ANGLE (Apple, Apple M1, OpenGL 4.1)"),
            client_hints={"platform": "Windows"},
        )

    with pytest.raises(ValidationError, match="ожидается platform 'Windows'"):
        FingerprintProfile(
            os="windows",
            webgl=WebGLFingerprint(
                renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"
            ),
            client_hints={"platform": "Linux"},
        )


@pytest.mark.parametrize(
    ("os_target", "foreign_font"),
    [
        ("macos", "Segoe UI"),
        ("macos", "DejaVu Sans"),
        ("linux", "Calibri"),
        ("linux", "Menlo"),
        ("windows", "SF Pro Text"),
        ("windows", "Ubuntu Mono"),
    ],
)
def test_pydantic_validator_rejects_foreign_os_fonts(
    os_target: str, foreign_font: str
) -> None:
    """Проверяет отклонение шрифтов чужой платформы для каждой ОС."""
    renderers = {
        "macos": "ANGLE (Apple, Apple M1, OpenGL 4.1)",
        "linux": "ANGLE (Mesa, Mesa Intel(R) UHD Graphics 630 (CFL GT2), OpenGL 4.5.0)",
        "windows": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
    }
    platforms = {"macos": "macOS", "linux": "Linux", "windows": "Windows"}

    with pytest.raises(ValidationError, match="шрифты чужой платформы"):
        FingerprintProfile(
            os=os_target,
            webgl=WebGLFingerprint(renderer=renderers[os_target]),
            client_hints={"platform": platforms[os_target]},
            fonts=["Arial", foreign_font],
        )


def test_procedural_synthesizer_fonts_match_os() -> None:
    """Проверяет, что синтезированные шрифты принадлежат пулу целевой ОС."""
    from browser_stealth.fingerprint.database import (
        FONTS_LINUX,
        FONTS_MACOS,
        FONTS_WINDOWS,
    )

    pools = {"windows": FONTS_WINDOWS, "macos": FONTS_MACOS, "linux": FONTS_LINUX}

    for os_target, pool in pools.items():
        synth = ProceduralSynthesizer(os_target=os_target)
        for i in range(10):
            fp = synth.synthesize(f"seed_fonts_{os_target}_{i}")
            assert fp.fonts, "Список шрифтов не должен быть пустым"
            assert set(fp.fonts).issubset(set(pool))
            assert len(fp.fonts) == len(set(fp.fonts)), "Шрифты не должны дублироваться"
