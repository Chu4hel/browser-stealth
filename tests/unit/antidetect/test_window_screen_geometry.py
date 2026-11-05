"""Тесты физической эмуляции геометрии окна и экрана (Issue #03)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.antidetect.scripts import _get_antidetect_js
from browser_stealth.fingerprint.models import ScreenFingerprint
from browser_stealth.fingerprint.procedural import ProceduralSynthesizer


def test_screen_fingerprint_model_defaults() -> None:
    """Проверяет значения по умолчанию и поля геометрии ScreenFingerprint."""
    screen = ScreenFingerprint()
    assert screen.avail_top == 0
    assert screen.avail_left == 0
    assert screen.avail_height == 1040
    assert screen.height == 1080


def test_procedural_synthesizer_geometry_by_os() -> None:
    """Проверяет корректность расчета панелей задач и меню для разных ОС."""
    # macOS: строка меню сверху занимает 25px
    synth_mac = ProceduralSynthesizer(os_target="macos")
    fp_mac = synth_mac.synthesize("seed_mac_geo")
    assert fp_mac.screen.avail_top == 25
    assert fp_mac.screen.avail_left == 0
    assert fp_mac.screen.avail_height == fp_mac.screen.height - 25

    # Windows: панель задач снизу (avail_top = 0)
    synth_win = ProceduralSynthesizer(os_target="windows")
    fp_win = synth_win.synthesize("seed_win_geo")
    assert fp_win.screen.avail_top == 0
    assert fp_win.screen.avail_left == 0
    assert fp_win.screen.avail_height < fp_win.screen.height

    # Linux: панель окружения (32px)
    synth_linux = ProceduralSynthesizer(os_target="linux")
    fp_linux = synth_linux.synthesize("seed_linux_geo")
    assert fp_linux.screen.avail_top == 32
    assert fp_linux.screen.avail_left == 0
    assert fp_linux.screen.avail_height == fp_linux.screen.height - 32


def test_antidetect_config_geometry_propagation() -> None:
    """Проверяет передачу расширенных параметров геометрии в JS-скрипт."""
    cfg = AntidetectConfig(
        screen_width=2560,
        screen_height=1440,
        screen_avail_height=1415,
        screen_avail_width=2560,
        screen_avail_top=25,
        screen_avail_left=0,
    )
    js = cfg.get_init_script()
    assert "2560" in js
    assert "1440" in js
    assert "1415" in js
    assert "availTop" in js
    assert "Screen.prototype" in js or "screenProto" in js


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_window_screen_geometry_node_runtime() -> None:
    """Проверяет исполнение эмуляции геометрии окна и экрана в Node.js runtime."""
    js = _get_antidetect_js(
        session_seed="geometry_test_seed",
        screen_width=1920,
        screen_height=1080,
        screen_avail_height=1055,
        screen_avail_width=1920,
        screen_avail_top=25,
        screen_avail_left=0,
        device_pixel_ratio=2.0,
    )

    node_runner = f"""
    const assert = require('assert');

    const window = globalThis;
    window.window = window;
    window.innerWidth = 1200;
    window.innerHeight = 800;

    class MockScreen {{}}
    globalThis.Screen = MockScreen;
    globalThis.screen = new MockScreen();

    globalThis.document = {{ createElement: () => ({{}}) }};
    globalThis.navigator = {{ webdriver: true, plugins: [] }};

    {js}

    // 1. Проверяем, что outerHeight всегда больше innerHeight
    assert.ok(window.outerHeight > window.innerHeight, 'outerHeight должен быть строго больше innerHeight');
    const diffH = window.outerHeight - window.innerHeight;
    assert.ok(diffH >= 75 && diffH <= 95, `Разница оконной рамки должна быть в диапазоне 75..95px, получено ${{diffH}}`);

    // 2. Проверяем outerWidth
    assert.ok(window.outerWidth >= window.innerWidth, 'outerWidth должен быть не меньше innerWidth');

    // 3. Проверяем характеристики экрана
    assert.strictEqual(screen.width, 1920);
    assert.strictEqual(screen.height, 1080);
    assert.strictEqual(screen.availHeight, 1055);
    assert.strictEqual(screen.availWidth, 1920);
    assert.strictEqual(screen.availTop, 25);
    assert.strictEqual(screen.availLeft, 0);
    assert.strictEqual(screen.colorDepth, 24);
    assert.strictEqual(screen.pixelDepth, 24);
    assert.strictEqual(window.devicePixelRatio, 2.0);

    // 4. Проверяем прототип Screen.prototype
    const desc = Object.getOwnPropertyDescriptor(Screen.prototype, 'availHeight');
    assert.ok(desc && typeof desc.get === 'function', 'Screen.prototype.availHeight должен быть геттером');

    // 5. Проверяем маскировку Function.prototype.toString на геттере
    assert.strictEqual(
        Function.prototype.toString.call(desc.get),
        'function get availHeight() {{ [native code] }}'
    );

    // 6. Попытка удаления свойства из объекта не ломает возвращаемое значение (наследуется из прототипа)
    delete screen.availHeight;
    assert.strictEqual(screen.availHeight, 1055);

    console.log('GEOMETRY_TESTS_PASSED');
    """

    res = subprocess.run(
        ["node"],
        input=node_runner,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert res.returncode == 0, f"Node.js script failed:\n{res.stderr}\n{res.stdout}"
    assert "GEOMETRY_TESTS_PASSED" in res.stdout
