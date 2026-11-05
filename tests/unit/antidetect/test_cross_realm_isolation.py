"""Тесты изоляции дочерних контекстов (Iframe Cross-realm inspection и Web Workers)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.antidetect.scripts import _get_antidetect_js


def test_cross_realm_script_structure() -> None:
    """Проверяет наличие механизмов синхронного перехвата iframes и расширенной преамбулы воркеров."""
    js = _get_antidetect_js(
        hardware_concurrency=12,
        device_memory=16,
        user_agent="Custom-Agent-007",
    )

    # 1. Проверяем каскадный перехват прототипа HTMLIFrameElement
    assert "patchSubWindow" in js
    assert "Object.getOwnPropertyDescriptor(iframeProto, 'contentWindow')" in js
    assert "Object.getOwnPropertyDescriptor(iframeProto, 'contentDocument')" in js
    assert "patchedWindows = new WeakSet()" in js

    # 2. Проверяем перехват методов вставки DOM
    assert "Node.prototype.appendChild" in js
    assert "Node.prototype.insertBefore" in js

    # 3. Проверяем преамбулу воркеров
    assert "workerPreamble" in js
    assert "hardwareConcurrency" in js
    assert "12" in js
    assert "deviceMemory" in js
    assert "16" in js
    assert "Custom-Agent-007" in js


def test_antidetect_config_user_agent_propagation() -> None:
    """Проверяет проброс user_agent из AntidetectConfig в JS-скрипт."""
    cfg = AntidetectConfig(
        user_agent="Mozilla/5.0 (Test-Agent/1.0)",
        hardware_concurrency=6,
        device_memory=4,
    )
    script = cfg.get_init_script()
    assert "Mozilla/5.0 (Test-Agent/1.0)" in script
    assert "hardwareConcurrency" in script


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_iframe_content_window_synchronous_isolation_node() -> None:
    """Проверяет синхронный перехват contentWindow при динамическом создании iframe в runtime."""
    js = _get_antidetect_js(
        hardware_concurrency=14,
        device_memory=32,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    )

    node_runner = f"""
    const assert = require('assert');

    // Эмуляция базового окружения браузера перед выполнением скрипта
    const window = globalThis;
    window.window = window;

    class MockNode {{
        appendChild(child) {{
            return child;
        }}
        insertBefore(child, ref) {{
            return child;
        }}
    }}
    globalThis.Node = MockNode;

    class MockHTMLIFrameElement extends MockNode {{
        constructor() {{
            super();
            this.nodeName = 'IFRAME';
            this.tagName = 'IFRAME';
            // Внутренний контекст фрейма
            this._subWin = {{
                navigator: {{
                    webdriver: true,
                    hardwareConcurrency: 4,
                    deviceMemory: 2
                }},
                Function: Function
            }};
        }}
    }}
    Object.defineProperty(MockHTMLIFrameElement.prototype, 'contentWindow', {{
        get: function() {{
            return this._subWin;
        }},
        configurable: true,
        enumerable: true
    }});
    Object.defineProperty(MockHTMLIFrameElement.prototype, 'contentDocument', {{
        get: function() {{
            return {{ defaultView: this._subWin }};
        }},
        configurable: true,
        enumerable: true
    }});
    globalThis.HTMLIFrameElement = MockHTMLIFrameElement;

    globalThis.document = {{
        createElement: (tag) => {{
            if (tag.toLowerCase() === 'iframe') {{
                const el = new MockHTMLIFrameElement();
                el.addEventListener = (evt, cb) => {{}};
                return el;
            }}
            return {{}};
        }}
    }};

    globalThis.navigator = {{
        webdriver: true,
        hardwareConcurrency: 4,
        deviceMemory: 2,
        plugins: []
    }};
    globalThis.screen = {{ width: 1920, height: 1080 }};

    // Выполняем скрипт антидетекта
    {js}

    // ТЕСТ 1: Синхронное создание iframe и немедленный опрос contentWindow
    const iframe = document.createElement('iframe');
    const win = iframe.contentWindow;

    // Проверяем, что webdriver в дочернем окне скрыт (undefined)
    assert.strictEqual(win.navigator.webdriver, undefined, 'webdriver в iframe должен быть undefined');

    // Проверяем согласованность аппаратных параметров
    assert.strictEqual(win.navigator.hardwareConcurrency, 14, 'hardwareConcurrency в iframe должен быть 14');
    assert.strictEqual(win.navigator.deviceMemory, 32, 'deviceMemory в iframe должен быть 32');
    assert.ok(win.navigator.userAgent.includes('Macintosh'), 'userAgent в iframe должен соответствовать профилю');

    // ТЕСТ 2: Доступ через contentDocument.defaultView
    const docWin = iframe.contentDocument.defaultView;
    assert.strictEqual(docWin.navigator.webdriver, undefined);

    // ТЕСТ 3: Добавление через appendChild синхронно патчит
    const iframe2 = new MockHTMLIFrameElement();
    const parentNode = new MockNode();
    parentNode.appendChild(iframe2);
    assert.strictEqual(iframe2.contentWindow.navigator.webdriver, undefined);
    assert.strictEqual(iframe2.contentWindow.navigator.hardwareConcurrency, 14);

    console.log('IFRAME_ISOLATION_PASSED');
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
    assert "IFRAME_ISOLATION_PASSED" in res.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_worker_preamble_and_constructor_node() -> None:
    """Проверяет патчинг конструктора Worker и поддержку URL-объектов."""
    js = _get_antidetect_js(
        hardware_concurrency=10,
        device_memory=16,
    )

    node_runner = f"""
    const assert = require('assert');
    const window = globalThis;
    window.window = window;

    let capturedScriptURL = null;
    let capturedOptions = null;

    class MockWorker {{
        constructor(scriptURL, options) {{
            capturedScriptURL = scriptURL;
            capturedOptions = options;
        }}
    }}
    globalThis.Worker = MockWorker;
    globalThis.Blob = class Blob {{
        constructor(parts, opts) {{
            this.content = parts.join('');
            this.opts = opts;
        }}
    }};
    globalThis.URL = {{
        createObjectURL: (blob) => 'blob://mock-blob-url-123'
    }};

    globalThis.document = {{ createElement: () => ({{}}) }};
    globalThis.navigator = {{ webdriver: true, hardwareConcurrency: 2, deviceMemory: 2 }};
    globalThis.screen = {{ width: 1920, height: 1080 }};

    {js}

    // Проверяем создание Worker со строкой
    const w1 = new window.Worker('/scripts/worker.js');
    assert.strictEqual(capturedScriptURL, 'blob://mock-blob-url-123');

    // Проверяем создание Worker с объектом URL
    const urlObj = {{ href: 'https://cdn.example.com/worker.js' }};
    const w2 = new window.Worker(urlObj, {{ type: 'module' }});
    assert.strictEqual(capturedScriptURL, 'blob://mock-blob-url-123');

    console.log('WORKER_ISOLATION_PASSED');
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
    assert "WORKER_ISOLATION_PASSED" in res.stdout
