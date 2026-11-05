"""Тесты локализации и W3C-разрешений эмуляции navigator.mediaDevices.enumerateDevices."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.antidetect.scripts import _get_antidetect_js
from browser_stealth.fingerprint import FingerprintSynthesizer


def test_media_devices_locale_script_templates() -> None:
    """Проверяет наличие англоязычных и русскоязычных шаблонов медиаустройств в JS."""
    js_en = _get_antidetect_js(locale="en-US")
    assert "Internal Microphone (Realtek High Definition Audio)" in js_en
    assert "Speakers (Realtek High Definition Audio)" in js_en
    assert '"en-US"' in js_en

    js_ru = _get_antidetect_js(locale="ru-RU")
    assert "Встроенный микрофон (Realtek Audio)" in js_ru
    assert "Динамики (Realtek Audio)" in js_ru
    assert '"ru-RU"' in js_ru


def test_antidetect_config_locale_propagation() -> None:
    """Проверяет корректный проброс locale из AntidetectConfig и FingerprintProfile."""
    cfg_en = AntidetectConfig(locale="en-US")
    assert cfg_en.locale == "en-US"
    assert '"en-US"' in cfg_en.get_init_script()

    cfg_ru = AntidetectConfig(locale="ru-RU")
    assert cfg_ru.locale == "ru-RU"
    assert '"ru-RU"' in cfg_ru.get_init_script()

    fp_profile = FingerprintSynthesizer(mode="procedural", locale="en-US").synthesize(
        seed="test_seed_42"
    )
    cfg_from_fp = fp_profile.to_antidetect_config()
    assert cfg_from_fp.locale == "en-US"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_media_devices_w3c_permissions_and_labels_node() -> None:
    """Проверяет соблюдение стандарта W3C: скрытие label и deviceId до получения разрешений getUserMedia."""
    js_en = _get_antidetect_js(locale="en-US")

    node_runner = f"""
    const window = globalThis;
    const document = {{ createElement: () => ({{}}) }};
    const navigator = {{
        language: 'en-US',
        languages: ['en-US', 'en'],
        mediaDevices: {{
            enumerateDevices: async () => [],
            getUserMedia: async () => ({{}})
        }}
    }};
    const screen = {{ width: 1920, height: 1080 }};

    {js_en}

    const assert = require('assert');

    (async () => {{
        // 1. До вызова getUserMedia устройства должны быть без меток и идентификаторов
        const initialDevices = await navigator.mediaDevices.enumerateDevices();
        assert.strictEqual(initialDevices.length, 2);
        assert.strictEqual(initialDevices[0].kind, 'audioinput');
        assert.strictEqual(initialDevices[0].label, '', 'Метка микрофона должна быть пустой до получения разрешения');
        assert.strictEqual(initialDevices[0].deviceId, '', 'Идентификатор устройства должен быть пустым');
        assert.strictEqual(initialDevices[1].kind, 'audiooutput');
        assert.strictEqual(initialDevices[1].label, '', 'Метка динамиков должна быть пустой до получения разрешения');

        // 2. После успешного вызова getUserMedia разрешения считаются выданными
        await navigator.mediaDevices.getUserMedia({{ audio: true }});

        const grantedDevices = await navigator.mediaDevices.enumerateDevices();
        assert.strictEqual(grantedDevices.length, 2);
        assert.strictEqual(grantedDevices[0].kind, 'audioinput');
        assert.strictEqual(grantedDevices[0].label, 'Internal Microphone (Realtek High Definition Audio)');
        assert.strictEqual(grantedDevices[0].deviceId, 'default');
        assert.strictEqual(grantedDevices[1].kind, 'audiooutput');
        assert.strictEqual(grantedDevices[1].label, 'Speakers (Realtek High Definition Audio)');
        assert.strictEqual(grantedDevices[1].deviceId, 'default');
    }})();
    """

    res = subprocess.run(
        ["node"],
        input=node_runner,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Ошибка исполнения JS в Node.js:\n{res.stderr}"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_media_devices_russian_locale_in_node() -> None:
    """Проверяет адаптивный выбор русских названий при русской локали navigator.language."""
    js_ru = _get_antidetect_js(locale="ru-RU")

    node_runner = f"""
    const window = globalThis;
    const document = {{ createElement: () => ({{}}) }};
    const navigator = {{
        language: 'ru-RU',
        languages: ['ru-RU', 'ru'],
        mediaDevices: {{
            enumerateDevices: async () => [],
            getUserMedia: async () => ({{}})
        }}
    }};
    const screen = {{ width: 1920, height: 1080 }};

    {js_ru}

    const assert = require('assert');

    (async () => {{
        await navigator.mediaDevices.getUserMedia({{ audio: true }});
        const devices = await navigator.mediaDevices.enumerateDevices();
        assert.strictEqual(devices[0].label, 'Встроенный микрофон (Realtek Audio)');
        assert.strictEqual(devices[1].label, 'Динамики (Realtek Audio)');
    }})();
    """

    res = subprocess.run(
        ["node"],
        input=node_runner,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Ошибка исполнения JS в Node.js:\n{res.stderr}"
