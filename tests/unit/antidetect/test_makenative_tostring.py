"""Тесты маскировки функций makeNative и защиты Function.prototype.toString."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from browser_stealth.antidetect.scripts import _get_antidetect_js


def test_makenative_script_structure() -> None:
    """Проверяет структуру инъекции makeNative и перехвата Function.prototype.toString."""
    js = _get_antidetect_js()

    assert "customToStringMap = new WeakMap()" in js
    assert "patchedToString = new Proxy(nativeToString" in js
    assert "Function.prototype.toString" in js
    assert "customToStringMap.set(fn, name)" in js
    # Проверяем отсутствие старой утечки через собственное свойство
    assert "fn.toString = fnToString" not in js
    assert "fn.toString.toString =" not in js


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_makenative_v8_node_runtime_cloaking() -> None:
    """Проверяет исполнение makeNative в V8 (Node.js): отсутствие утечки прототипа и сигнатур патчинга."""
    js = _get_antidetect_js()

    node_runner = f"""
    const window = globalThis;
    const document = {{
        createElement: () => ({{}}),
    }};
    const navigator = {{
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        plugins: [],
        languages: ['en-US', 'en'],
        mediaDevices: {{ enumerateDevices: async () => [] }}
    }};
    const screen = {{ width: 1920, height: 1080 }};

    {js}

    const assert = require('assert');

    // 1. Прототипный вызов обходит локальные свойства, но перехватывается нашим Proxy
    assert.strictEqual(
        Function.prototype.toString.call(window.chrome.app.getDetails),
        'function getDetails() {{ [native code] }}'
    );
    assert.strictEqual(
        window.chrome.app.getDetails.toString(),
        'function getDetails() {{ [native code] }}'
    );

    // 2. У нативных функций V8 отсутствует собственное свойство toString
    assert.strictEqual(window.chrome.app.getDetails.hasOwnProperty('toString'), false);

    // 3. Проверка navigator.mediaDevices.enumerateDevices
    assert.strictEqual(
        Function.prototype.toString.call(navigator.mediaDevices.enumerateDevices),
        'function enumerateDevices() {{ [native code] }}'
    );
    assert.strictEqual(navigator.mediaDevices.enumerateDevices.hasOwnProperty('toString'), false);

    // 4. Поведение самого Function.prototype.toString
    assert.strictEqual(
        Function.prototype.toString.toString(),
        'function toString() {{ [native code] }}'
    );
    assert.strictEqual(
        Function.prototype.toString.call(Function.prototype.toString),
        'function toString() {{ [native code] }}'
    );
    assert.strictEqual(Function.prototype.toString.hasOwnProperty('toString'), false);
    assert.strictEqual(Function.prototype.hasOwnProperty('toString'), true);
    assert.strictEqual(Function.prototype.toString.name, 'toString');

    // 5. Вызовы на не-функциях вызывают нативный TypeError
    assert.throws(() => {{
        Function.prototype.toString.call({{}});
    }}, TypeError);
    assert.throws(() => {{
        Function.prototype.toString.call(12345);
    }}, TypeError);

    // 6. Пользовательские незамаскированные функции сохраняют исходный код
    function unmaskedFunction() {{ return 'original_code'; }}
    assert.strictEqual(
        Function.prototype.toString.call(unmaskedFunction).includes('original_code'),
        true
    );
    """

    res = subprocess.run(["node", "-e", node_runner], capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"Ошибка исполнения JS в Node.js:\n{res.stderr}"
