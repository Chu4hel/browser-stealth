"""Генератор JavaScript-инъекций антидетекта для браузеров."""

from __future__ import annotations

import json
from typing import Any

from .mobile import get_ios_js, get_motion_js, get_orientation_js, get_touch_js

DEFAULT_WEBGL_VENDOR = "Google Inc. (NVIDIA)"
DEFAULT_WEBGL_RENDERER = "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
DEFAULT_HARDWARE_CONCURRENCY = 8
DEFAULT_DEVICE_MEMORY = 8


def _get_antidetect_js(
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    stealth_minimal: bool = False,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
    screen_width: int | None = None,
    screen_height: int | None = None,
    screen_avail_height: int | None = None,
    device_pixel_ratio: float | None = None,
    media_devices: list[dict[str, Any]] | None = None,
    is_mobile: bool = False,
    has_touch: bool = False,
    max_touch_points: int = 0,
    is_ios: bool = False,
    orientation: dict[str, Any] | None = None,
    locale: str = "en-US",
    user_agent: str | None = None,
) -> str:
    """Генерирует JavaScript-инъекцию для скрытия признаков автоматизации браузера с заданными параметрами."""
    vendor_js = json.dumps(webgl_vendor)
    renderer_js = json.dumps(webgl_renderer)
    concurrency_js = int(hardware_concurrency)
    memory_js = int(device_memory)
    minimal_js = "true" if stealth_minimal else "false"
    seed_js = json.dumps(str(session_seed))
    hints_js = json.dumps(client_hints) if client_hints is not None else "null"
    screen_w_js = json.dumps(screen_width)
    screen_h_js = json.dumps(screen_height)
    screen_avail_h_js = json.dumps(screen_avail_height)
    dpr_js = json.dumps(device_pixel_ratio)
    devices_js = json.dumps(media_devices) if media_devices is not None else "null"
    locale_js = json.dumps(locale)
    ua_js = json.dumps(user_agent) if user_agent is not None else "null"
    is_mobile_js = "true" if is_mobile else "false"
    max_touch_points_val = int(max_touch_points if (max_touch_points > 0 or not is_mobile) else 5)
    orientation_js = json.dumps(orientation) if orientation is not None else "null"

    touch_block = get_touch_js(max_touch_points_val) if (has_touch or is_mobile) else ""
    motion_block = get_motion_js() if (has_touch or is_mobile) else ""
    orientation_block = get_orientation_js(orientation_js, is_mobile_js)
    ios_block = get_ios_js() if is_ios else ""

    if user_agent is not None:
        worker_ua_block = f"""
            try {{
                Object.defineProperty(navigator, 'userAgent', {{
                    get: () => {ua_js},
                    enumerable: true,
                    configurable: true
                }});
            }} catch(e) {{}}
        """
        main_ua_block = f"""
        try {{
            Object.defineProperty(navProto, 'userAgent', {{
                get: makeNative(() => {ua_js}, 'get userAgent'),
                enumerable: true,
                configurable: true,
            }});
        }} catch (e) {{}}
        try {{
            Object.defineProperty(navigator, 'userAgent', {{
                get: makeNative(() => {ua_js}, 'get userAgent'),
                enumerable: true,
                configurable: true,
            }});
        }} catch (e) {{}}
        """
    else:
        worker_ua_block = ""
        main_ua_block = ""

    return f"""(function() {{
    // 0. Реестр маскировки функций под нативные [native code] через WeakMap и Proxy над Function.prototype.toString
    const customToStringMap = new WeakMap();
    const nativeToString = Function.prototype.toString;

    const patchedToString = new Proxy(nativeToString, {{
        apply(target, thisArg, args) {{
            if (typeof thisArg === 'function') {{
                if (customToStringMap.has(thisArg)) {{
                    const fnName = customToStringMap.get(thisArg);
                    return `function ${{fnName}}() {{ [native code] }}`;
                }}
                if (thisArg === Function.prototype.toString || thisArg === patchedToString || thisArg === nativeToString) {{
                    return 'function toString() {{ [native code] }}';
                }}
            }}
            return Reflect.apply(target, thisArg, args);
        }}
    }});

    try {{
        Object.defineProperty(Function.prototype, 'toString', {{
            value: patchedToString,
            writable: true,
            configurable: true,
            enumerable: false
        }});
    }} catch (e) {{
        try {{
            Function.prototype.toString = patchedToString;
        }} catch (e2) {{}}
    }}

    // Изоляция V8 Error stack traces
    try {{
        if (Error.captureStackTrace) {{
            const origCapture = Error.captureStackTrace;
            Error.captureStackTrace = function(targetObj, constructorOpt) {{
                origCapture(targetObj, constructorOpt);
                if (targetObj && targetObj.stack && typeof targetObj.stack === 'string') {{
                    targetObj.stack = targetObj.stack.replace(/at patched.*\\(eval at.*?\\)/g, 'at <anonymous>');
                }}
            }};
        }}
    }} catch (e) {{}}

    // Утилита для маскировки функций под нативные [native code] с чистым V8 stack trace
    const makeNative = (fn, name) => {{
        try {{
            Object.defineProperty(fn, 'name', {{
                value: name,
                configurable: true,
                writable: false,
                enumerable: false
            }});
            customToStringMap.set(fn, name);
        }} catch (e) {{}}
        return fn;
    }};

    // 0.1. Полноценная эмуляция объекта window.chrome
    try {{
        if (typeof window !== 'undefined') {{
            const chromeObj = window.chrome || {{}};
            if (!chromeObj.app) {{
                chromeObj.app = {{
                    isInstalled: false,
                    InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }},
                    RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }},
                    getDetails: makeNative(function() {{ return null; }}, 'getDetails'),
                    getIsInstalled: makeNative(function() {{ return false; }}, 'getIsInstalled'),
                    installState: makeNative(function() {{ return 'not_installed'; }}, 'installState'),
                    runningState: makeNative(function() {{ return 'cannot_run'; }}, 'runningState')
                }};
            }}
            if (!chromeObj.runtime) {{
                chromeObj.runtime = {{
                    OnInstalledReason: {{ CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' }},
                    OnRestartRequiredReason: {{ APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }},
                    PlatformArch: {{ ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }},
                    PlatformNaclArch: {{ ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }},
                    PlatformOs: {{ ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' }},
                    RequestUpdateCheckStatus: {{ NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' }},
                    connect: makeNative(function() {{}}, 'connect'),
                    sendMessage: makeNative(function() {{}}, 'sendMessage')
                }};
            }}
            if (!chromeObj.loadTimes) {{
                chromeObj.loadTimes = makeNative(function loadTimes() {{
                    const now = Date.now() / 1000;
                    return {{
                        commitLoadTime: now,
                        connectionInfo: 'h2',
                        finishDocumentLoadTime: now,
                        finishLoadTime: now,
                        firstPaintAfterLoadTime: 0,
                        firstPaintTime: now,
                        navigationType: 'Other',
                        npnNegotiatedProtocol: 'h2',
                        requestTime: now - 0.2,
                        startLoadTime: now - 0.2,
                        wasAlternateProtocolAvailable: false,
                        wasFetchedViaSpdy: true,
                        wasNpnNegotiated: true
                    }};
                }}, 'loadTimes');
            }}
            if (!chromeObj.csi) {{
                chromeObj.csi = makeNative(function csi() {{
                    const now = Date.now();
                    return {{
                        onloadT: now,
                        pageT: 250.0,
                        startE: now - 250,
                        tran: 15
                    }};
                }}, 'csi');
            }}
            window.chrome = chromeObj;
        }}
    }} catch (e) {{}}

    // 0.2. Защита от утечек IP через WebRTC (RTCPeerConnection)
    try {{
        if (typeof window !== 'undefined' && window.RTCPeerConnection) {{
            const OrigPeerConnection = window.RTCPeerConnection;
            const filterCandidateSdp = (sdp) => {{
                if (typeof sdp !== 'string') return sdp;
                return sdp.replace(/a=candidate.* typ host .*\\r\\n/g, '');
            }};

            const PatchedPeerConnection = function RTCPeerConnection(config) {{
                const pc = new OrigPeerConnection(config);
                const origCreateOffer = pc.createOffer;
                pc.createOffer = function createOffer(options) {{
                    return origCreateOffer.apply(this, arguments).then((offer) => {{
                        if (offer && offer.sdp) {{
                            return new RTCSessionDescription({{
                                type: offer.type,
                                sdp: filterCandidateSdp(offer.sdp)
                            }});
                        }}
                        return offer;
                    }});
                }};
                makeNative(pc.createOffer, 'createOffer');

                const origCreateAnswer = pc.createAnswer;
                pc.createAnswer = function createAnswer(options) {{
                    return origCreateAnswer.apply(this, arguments).then((answer) => {{
                        if (answer && answer.sdp) {{
                            return new RTCSessionDescription({{
                                type: answer.type,
                                sdp: filterCandidateSdp(answer.sdp)
                            }});
                        }}
                        return answer;
                    }});
                }};
                makeNative(pc.createAnswer, 'createAnswer');
                return pc;
            }};
            PatchedPeerConnection.prototype = OrigPeerConnection.prototype;
            window.RTCPeerConnection = makeNative(PatchedPeerConnection, 'RTCPeerConnection');
        }}
    }} catch (e) {{}}

    // 0.3. Защита изолированных Web Workers и SharedWorkers
    try {{
        const workerPreamble = `
            try {{
                const navProto = (typeof Navigator !== 'undefined' && Navigator.prototype) || (typeof navigator !== 'undefined' && Object.getPrototypeOf(navigator));
                if (navProto) {{
                    try {{ delete navProto.webdriver; }} catch(e) {{}}
                    try {{
                        Object.defineProperty(navProto, 'webdriver', {{
                            get: () => undefined,
                            enumerable: true,
                            configurable: true
                        }});
                    }} catch(e) {{}}
                }}
                if (typeof navigator !== 'undefined') {{
                    try {{ delete navigator.webdriver; }} catch(e) {{}}
                    try {{
                        Object.defineProperty(navigator, 'webdriver', {{
                            get: () => undefined,
                            enumerable: true,
                            configurable: true
                        }});
                    }} catch(e) {{}}
                    try {{
                        Object.defineProperty(navigator, 'hardwareConcurrency', {{
                            get: () => {concurrency_js},
                            enumerable: true,
                            configurable: true
                        }});
                    }} catch(e) {{}}
                    try {{
                        Object.defineProperty(navigator, 'deviceMemory', {{
                            get: () => {memory_js},
                            enumerable: true,
                            configurable: true
                        }});
                    }} catch(e) {{}}
                    {worker_ua_block}
                }}
            }} catch (e) {{}}
        `;
        if (typeof window !== 'undefined' && window.Worker) {{
            const OriginalWorker = window.Worker;
            const PatchedWorker = function Worker(scriptURL, options) {{
                try {{
                    const urlStr = (typeof scriptURL === 'object' && scriptURL !== null && 'href' in scriptURL)
                        ? scriptURL.href
                        : String(scriptURL);
                    const isModule = Boolean(options && options.type === 'module');
                    const loaderCode = isModule
                        ? `${{workerPreamble}}\\nimport "${{urlStr}}";`
                        : `${{workerPreamble}}\\nimportScripts("${{urlStr}}");`;
                    const blob = new Blob([loaderCode], {{ type: 'application/javascript' }});
                    const blobURL = URL.createObjectURL(blob);
                    return new OriginalWorker(blobURL, options);
                }} catch (e) {{
                    return new OriginalWorker(scriptURL, options);
                }}
            }};
            PatchedWorker.prototype = OriginalWorker.prototype;
            window.Worker = makeNative(PatchedWorker, 'Worker');
        }}
        if (typeof window !== 'undefined' && window.SharedWorker) {{
            const OriginalSharedWorker = window.SharedWorker;
            const PatchedSharedWorker = function SharedWorker(scriptURL, options) {{
                try {{
                    const urlStr = (typeof scriptURL === 'object' && scriptURL !== null && 'href' in scriptURL)
                        ? scriptURL.href
                        : String(scriptURL);
                    const isModule = Boolean(options && options.type === 'module');
                    const loaderCode = isModule
                        ? `${{workerPreamble}}\\nimport "${{urlStr}}";`
                        : `${{workerPreamble}}\\nimportScripts("${{urlStr}}");`;
                    const blob = new Blob([loaderCode], {{ type: 'application/javascript' }});
                    const blobURL = URL.createObjectURL(blob);
                    return new OriginalSharedWorker(blobURL, options);
                }} catch (e) {{
                    return new OriginalSharedWorker(scriptURL, options);
                }}
            }};
            PatchedSharedWorker.prototype = OriginalSharedWorker.prototype;
            window.SharedWorker = makeNative(PatchedSharedWorker, 'SharedWorker');
        }}
    }} catch (e) {{}}

    // 0.4. Синхронная каскадная изоляция дочерних контекстов (Iframe Cross-realm inspection)
    const patchedWindows = new WeakSet();
    const webdriverGetter = makeNative(() => undefined, 'get webdriver');
    const pluginsList = [
        {{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
        {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdmgglogagaboenashesapgbbbi', description: 'Google Chrome PDF Viewer' }}
    ];
    const pluginsGetter = makeNative(() => pluginsList, 'get plugins');

    const patchSubWindow = (subWin) => {{
        if (!subWin) return;
        try {{
            if (patchedWindows.has(subWin)) return;
            patchedWindows.add(subWin);
        }} catch (e) {{}}

        try {{
            if (subWin.Function && subWin.Function.prototype) {{
                try {{
                    Object.defineProperty(subWin.Function.prototype, 'toString', {{
                        value: patchedToString,
                        writable: true,
                        configurable: true,
                        enumerable: false
                    }});
                }} catch (e) {{
                    try {{ subWin.Function.prototype.toString = patchedToString; }} catch (e2) {{}}
                }}
            }}

            const subNavProto = (subWin.Navigator && subWin.Navigator.prototype) || (subWin.navigator && Object.getPrototypeOf(subWin.navigator));
            if (subNavProto) {{
                try {{ delete subNavProto.webdriver; }} catch (e) {{}}
                try {{
                    Object.defineProperty(subNavProto, 'webdriver', {{
                        get: webdriverGetter,
                        enumerable: true,
                        configurable: true
                    }});
                }} catch (e) {{}}
            }}
            if (subWin.navigator) {{
                try {{ delete subWin.navigator.webdriver; }} catch (e) {{}}
                try {{
                    Object.defineProperty(subWin.navigator, 'webdriver', {{
                        get: webdriverGetter,
                        enumerable: true,
                        configurable: true
                    }});
                }} catch (e) {{}}

                try {{
                    Object.defineProperty(subWin.navigator, 'hardwareConcurrency', {{
                        get: makeNative(() => {concurrency_js}, 'get hardwareConcurrency'),
                        enumerable: true,
                        configurable: true
                    }});
                }} catch (e) {{}}
                try {{
                    Object.defineProperty(subWin.navigator, 'deviceMemory', {{
                        get: makeNative(() => {memory_js}, 'get deviceMemory'),
                        enumerable: true,
                        configurable: true
                    }});
                }} catch (e) {{}}
                try {{
                    Object.defineProperty(subWin.navigator, 'plugins', {{
                        get: pluginsGetter,
                        enumerable: true,
                        configurable: true
                    }});
                }} catch (e) {{}}

                if ({ua_js}) {{
                    try {{
                        Object.defineProperty(subWin.navigator, 'userAgent', {{
                            get: makeNative(() => {ua_js}, 'get userAgent'),
                            enumerable: true,
                            configurable: true
                        }});
                    }} catch (e) {{}}
                }}
            }}

            if (typeof window !== 'undefined' && window.chrome) {{
                try {{
                    subWin.chrome = window.chrome;
                }} catch (e) {{}}
            }}

            if (!isMinimal) {{
                const subContexts = [];
                if (subWin.WebGLRenderingContext) subContexts.push(subWin.WebGLRenderingContext);
                if (subWin.WebGL2RenderingContext) subContexts.push(subWin.WebGL2RenderingContext);
                for (const ctx of subContexts) {{
                    try {{
                        const origGetParam = ctx.prototype.getParameter;
                        const patchedGetParam = function getParameter(parameter) {{
                            if (parameter === 37445) return {vendor_js};
                            if (parameter === 37446) return {renderer_js};
                            return origGetParam.apply(this, arguments);
                        }};
                        ctx.prototype.getParameter = makeNative(patchedGetParam, 'getParameter');
                    }} catch (e) {{}}
                }}
            }}
        }} catch (err) {{}}
    }};

    // Перехват дескрипторов contentWindow и contentDocument у HTMLIFrameElement.prototype
    try {{
        if (typeof HTMLIFrameElement !== 'undefined' && HTMLIFrameElement.prototype) {{
            const iframeProto = HTMLIFrameElement.prototype;

            const origContentWindowDesc = Object.getOwnPropertyDescriptor(iframeProto, 'contentWindow');
            if (origContentWindowDesc && typeof origContentWindowDesc.get === 'function') {{
                const origGetContentWindow = origContentWindowDesc.get;
                const patchedGetContentWindow = function contentWindow() {{
                    const win = Reflect.apply(origGetContentWindow, this, []);
                    if (win) {{
                        patchSubWindow(win);
                    }}
                    return win;
                }};
                Object.defineProperty(iframeProto, 'contentWindow', {{
                    get: makeNative(patchedGetContentWindow, 'get contentWindow'),
                    set: origContentWindowDesc.set,
                    configurable: true,
                    enumerable: true
                }});
            }}

            const origContentDocumentDesc = Object.getOwnPropertyDescriptor(iframeProto, 'contentDocument');
            if (origContentDocumentDesc && typeof origContentDocumentDesc.get === 'function') {{
                const origGetContentDocument = origContentDocumentDesc.get;
                const patchedGetContentDocument = function contentDocument() {{
                    const doc = Reflect.apply(origGetContentDocument, this, []);
                    if (doc && doc.defaultView) {{
                        patchSubWindow(doc.defaultView);
                    }}
                    return doc;
                }};
                Object.defineProperty(iframeProto, 'contentDocument', {{
                    get: makeNative(patchedGetContentDocument, 'get contentDocument'),
                    set: origContentDocumentDesc.set,
                    configurable: true,
                    enumerable: true
                }});
            }}
        }}
    }} catch (e) {{}}

    // Синхронный перехват методов вставки iframe в DOM
    try {{
        if (typeof Node !== 'undefined' && Node.prototype) {{
            const origAppendChild = Node.prototype.appendChild;
            Node.prototype.appendChild = function appendChild(node) {{
                const res = origAppendChild.apply(this, arguments);
                if (node && (node.nodeName === 'IFRAME' || node.tagName === 'IFRAME')) {{
                    try {{
                        if (node.contentWindow) {{
                            patchSubWindow(node.contentWindow);
                        }}
                    }} catch (e) {{}}
                }}
                return res;
            }};
            makeNative(Node.prototype.appendChild, 'appendChild');

            const origInsertBefore = Node.prototype.insertBefore;
            Node.prototype.insertBefore = function insertBefore(newNode, refNode) {{
                const res = origInsertBefore.apply(this, arguments);
                if (newNode && (newNode.nodeName === 'IFRAME' || newNode.tagName === 'IFRAME')) {{
                    try {{
                        if (newNode.contentWindow) {{
                            patchSubWindow(newNode.contentWindow);
                        }}
                    }} catch (e) {{}}
                }}
                return res;
            }};
            makeNative(Node.prototype.insertBefore, 'insertBefore');
        }}
    }} catch (e) {{}}

    // Детерминированный LCG PRNG для Canvas шума
    const sessionSeed = {seed_js};
    let seedNum = 0;
    for (let i = 0; i < sessionSeed.length; i++) {{
        seedNum = ((seedNum << 5) - seedNum + sessionSeed.charCodeAt(i)) & 0xffffffff;
    }}
    const pseudoRandom = (offset) => {{
        const x = Math.sin(seedNum + offset) * 10000;
        return x - Math.floor(x);
    }};

    // 1. Скрытие и очистка navigator.webdriver
    const navProto = Navigator.prototype || Object.getPrototypeOf(navigator);
    try {{
        delete navProto.webdriver;
    }} catch (e) {{}}
    try {{
        delete navigator.webdriver;
    }} catch (e) {{}}
    try {{
        Object.defineProperty(navProto, 'webdriver', {{
            get: webdriverGetter,
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    {main_ua_block}

    const isMinimal = {minimal_js};

    if (!isMinimal) {{
        // 2. Рандомизация отпечатка Canvas с детерминированным шумом
        try {{
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            const patchedGetImageData = function getImageData(x, y, w, h) {{
                const imageData = originalGetImageData.apply(this, arguments);
                if (imageData && imageData.data && imageData.data.length >= 4) {{
                    const delta = pseudoRandom(x + y * 57) > 0.5 ? 1 : -1;
                    imageData.data[0] = (imageData.data[0] + delta) % 256;
                }}
                return imageData;
            }};
            CanvasRenderingContext2D.prototype.getImageData = makeNative(patchedGetImageData, 'getImageData');
        }} catch (e) {{}}

        // 3. Подмена WebGL параметров видеокарты (WebGL 1 и WebGL 2)
        const webglContexts = [];
        if (typeof WebGLRenderingContext !== 'undefined') webglContexts.push(WebGLRenderingContext);
        if (typeof WebGL2RenderingContext !== 'undefined') webglContexts.push(WebGL2RenderingContext);

        for (const ctx of webglContexts) {{
            try {{
                const originalGetParameter = ctx.prototype.getParameter;
                const patchedGetParameter = function getParameter(parameter) {{
                    // UNMASKED_VENDOR_WEBGL
                    if (parameter === 37445) {{
                        return {vendor_js};
                    }}
                    // UNMASKED_RENDERER_WEBGL
                    if (parameter === 37446) {{
                        return {renderer_js};
                    }}
                    return originalGetParameter.apply(this, arguments);
                }};
                ctx.prototype.getParameter = makeNative(patchedGetParameter, 'getParameter');
            }} catch (e) {{}}
        }}

        // 3.1. Детерминированный микрошум для AudioContext / OfflineAudioContext
        try {{
            const AudioBufferProto = typeof AudioBuffer !== 'undefined' ? AudioBuffer.prototype : null;
            if (AudioBufferProto && AudioBufferProto.getChannelData) {{
                const origGetChannelData = AudioBufferProto.getChannelData;
                AudioBufferProto.getChannelData = makeNative(function getChannelData(channel) {{
                    const data = origGetChannelData.apply(this, arguments);
                    if (data && data.length > 0) {{
                        const sampleIndex = Math.floor(pseudoRandom(channel * 101) * Math.min(data.length, 500));
                        const noise = (pseudoRandom(sampleIndex + 7) - 0.5) * 0.0000001;
                        data[sampleIndex] += noise;
                    }}
                    return data;
                }}, 'getChannelData');
            }}
        }} catch (e) {{}}
    }}

    // 4. Эмуляция navigator.plugins
    try {{
        Object.defineProperty(navigator, 'plugins', {{
            get: pluginsGetter,
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    // 5. Эмуляция hardwareConcurrency и deviceMemory
    try {{
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: makeNative(() => {concurrency_js}, 'get hardwareConcurrency'),
            enumerable: true,
            configurable: true,
        }});
        Object.defineProperty(navigator, 'deviceMemory', {{
            get: makeNative(() => {memory_js}, 'get deviceMemory'),
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    // 5.1. Эмуляция размеров окна и экрана (outerWidth, outerHeight, availHeight)
    try {{
        if (typeof window !== 'undefined') {{
            if (window.outerWidth === 0 || window.outerHeight === 0 || window.outerHeight === window.innerHeight) {{
                const innerH = window.innerHeight || 800;
                const innerW = window.innerWidth || 1280;
                Object.defineProperty(window, 'outerWidth', {{
                    get: makeNative(() => innerW, 'get outerWidth'),
                    configurable: true,
                    enumerable: true
                }});
                Object.defineProperty(window, 'outerHeight', {{
                    get: makeNative(() => innerH + 85, 'get outerHeight'),
                    configurable: true,
                    enumerable: true
                }});
            }}
            if (typeof screen !== 'undefined') {{
                if (!screen.availHeight || screen.availHeight === screen.height) {{
                    Object.defineProperty(screen, 'availHeight', {{
                        get: makeNative(() => (screen.height ? screen.height - 40 : 1040), 'get availHeight'),
                        configurable: true,
                        enumerable: true
                    }});
                }}
            }}
        }}
    }} catch (e) {{}}

    // 5.2. Эмуляция navigator.connection и navigator.getBattery
    try {{
        if (!navigator.connection) {{
            const connectionObj = {{
                downlink: 10,
                effectiveType: '4g',
                rtt: 50,
                saveData: false,
                onchange: null
            }};
            Object.defineProperty(navigator, 'connection', {{
                get: makeNative(() => connectionObj, 'get connection'),
                enumerable: true,
                configurable: true
            }});
        }}
        if (!navigator.getBattery) {{
            const batteryManager = {{
                charging: true,
                chargingTime: 0,
                dischargingTime: Infinity,
                level: 1.0,
                onchargingchange: null,
                onchargingtimechange: null,
                ondischargingtimechange: null,
                onlevelchange: null
            }};
            navigator.getBattery = makeNative(function getBattery() {{
                return Promise.resolve(batteryManager);
            }}, 'getBattery');
        }}
    }} catch (e) {{}}

    // 6. Синхронизация Permissions API и Notification
    try {{
        if (navigator.permissions && navigator.permissions.query) {{
            const origQuery = navigator.permissions.query;
            const patchedQuery = function query(parameters) {{
                if (parameters && parameters.name === 'notifications' && typeof Notification !== 'undefined') {{
                    return Promise.resolve({{
                        state: Notification.permission === 'default' ? 'prompt' : Notification.permission,
                        onchange: null
                    }});
                }}
                return origQuery.apply(this, arguments);
            }};
            navigator.permissions.query = makeNative(patchedQuery, 'query');
        }}
    }} catch (e) {{}}

    // 7. Защита от извлечения прототипов через скрытый iframe (Cross-realm prototype inspection)
    try {{
        const originalCreateElement = Document.prototype.createElement;
        Document.prototype.createElement = makeNative(function createElement(tagName, options) {{
            const element = originalCreateElement.apply(this, arguments);
            if (element && typeof tagName === 'string' && tagName.toLowerCase() === 'iframe') {{
                element.addEventListener('load', function() {{
                    try {{
                        if (element.contentWindow) {{
                            patchSubWindow(element.contentWindow);
                        }}
                    }} catch (err) {{}}
                }});
            }}
            return element;
        }}, 'createElement');
    }} catch (e) {{}}

    // 8. Эмуляция Client Hints (navigator.userAgentData) при наличии hints
    const clientHintsData = {hints_js};
    if (clientHintsData) {{
        try {{
            const uaData = {{
                brands: clientHintsData.brands || [],
                mobile: Boolean(clientHintsData.mobile),
                platform: clientHintsData.platform || 'Windows',
                getHighEntropyValues: makeNative(function getHighEntropyValues(hints) {{
                    return Promise.resolve({{
                        brands: clientHintsData.brands || [],
                        mobile: Boolean(clientHintsData.mobile),
                        platform: clientHintsData.platform || 'Windows',
                        architecture: 'x86',
                        bitness: '64',
                        model: '',
                        platformVersion: '15.0.0',
                        uaFullVersion: (clientHintsData.brands && clientHintsData.brands[2] ? clientHintsData.brands[2].version : '120') + '.0.0.0'
                    }});
                }}, 'getHighEntropyValues')
            }};
            Object.defineProperty(navigator, 'userAgentData', {{
                get: makeNative(() => uaData, 'get userAgentData'),
                enumerable: true,
                configurable: true
            }});
        }} catch (e) {{}}
    }}

    // 9. Эмуляция характеристик дисплея (screen.width, screen.height, screen.availHeight, window.devicePixelRatio)
    try {{
        if (typeof window !== 'undefined') {{
            if ({screen_w_js} !== null) {{
                Object.defineProperty(screen, 'width', {{
                    get: makeNative(() => {screen_w_js}, 'get width'),
                    configurable: true,
                    enumerable: true
                }});
                Object.defineProperty(screen, 'availWidth', {{
                    get: makeNative(() => {screen_w_js}, 'get availWidth'),
                    configurable: true,
                    enumerable: true
                }});
            }}
            if ({screen_h_js} !== null) {{
                Object.defineProperty(screen, 'height', {{
                    get: makeNative(() => {screen_h_js}, 'get height'),
                    configurable: true,
                    enumerable: true
                }});
            }}
            if ({screen_avail_h_js} !== null) {{
                Object.defineProperty(screen, 'availHeight', {{
                    get: makeNative(() => {screen_avail_h_js}, 'get availHeight'),
                    configurable: true,
                    enumerable: true
                }});
            }}
            if ({dpr_js} !== null) {{
                Object.defineProperty(window, 'devicePixelRatio', {{
                    get: makeNative(() => {dpr_js}, 'get devicePixelRatio'),
                    configurable: true,
                    enumerable: true
                }});
            }}
        }}
    }} catch (e) {{}}

    // 10. Эмуляция медиа-устройств (navigator.mediaDevices.enumerateDevices) с учетом локали и разрешений
    try {{
        if (typeof navigator !== 'undefined') {{
            if (!navigator.mediaDevices) {{
                navigator.mediaDevices = {{}};
            }}

            let mediaAccessGranted = false;

            // Отслеживаем предоставление разрешений через getUserMedia
            if (navigator.mediaDevices.getUserMedia) {{
                const origGetUserMedia = navigator.mediaDevices.getUserMedia;
                navigator.mediaDevices.getUserMedia = makeNative(function getUserMedia(constraints) {{
                    mediaAccessGranted = true;
                    if (origGetUserMedia) {{
                        return origGetUserMedia.apply(this, arguments);
                    }}
                    return Promise.reject(new DOMException('Permission denied', 'NotAllowedError'));
                }}, 'getUserMedia');
            }}

            const rawDevices = {devices_js};
            const defaultDevicesEn = [
                {{
                    deviceId: 'default',
                    kind: 'audioinput',
                    label: 'Internal Microphone (Realtek High Definition Audio)',
                    groupId: 'group_audio_default'
                }},
                {{
                    deviceId: 'default',
                    kind: 'audiooutput',
                    label: 'Speakers (Realtek High Definition Audio)',
                    groupId: 'group_audio_default'
                }}
            ];
            const defaultDevicesRu = [
                {{
                    deviceId: 'default',
                    kind: 'audioinput',
                    label: 'Встроенный микрофон (Realtek Audio)',
                    groupId: 'group_audio_default'
                }},
                {{
                    deviceId: 'default',
                    kind: 'audiooutput',
                    label: 'Динамики (Realtek Audio)',
                    groupId: 'group_audio_default'
                }}
            ];

            const activeLocale = ({locale_js} || (navigator.language || (navigator.languages && navigator.languages[0]) || 'en-US')).toLowerCase();
            const isRuLocale = activeLocale.startsWith('ru');
            const defaultFakeDevices = isRuLocale ? defaultDevicesRu : defaultDevicesEn;

            const targetDevices = Array.isArray(rawDevices) && rawDevices.length > 0 ? rawDevices : defaultFakeDevices;

            const makeMediaDeviceInfo = (d, granted) => {{
                return {{
                    deviceId: granted ? (d.deviceId || d.device_id || 'default') : '',
                    kind: d.kind || 'audiooutput',
                    label: granted ? (d.label || '') : '',
                    groupId: granted ? (d.groupId || d.group_id || 'default') : '',
                    toJSON: function toJSON() {{
                        return {{
                            deviceId: this.deviceId,
                            kind: this.kind,
                            label: this.label,
                            groupId: this.groupId
                        }};
                    }}
                }};
            }};

            const origEnumerate = navigator.mediaDevices.enumerateDevices;
            const fakeEnumerateDevices = function enumerateDevices() {{
                if (origEnumerate) {{
                    return origEnumerate.apply(this, arguments).then((devices) => {{
                        if (Array.isArray(devices) && devices.length > 0) {{
                            const hasRealLabels = devices.some((d) => d && typeof d.label === 'string' && d.label.length > 0);
                            if (hasRealLabels) {{
                                mediaAccessGranted = true;
                                return devices;
                            }}
                            return targetDevices.map((d) => makeMediaDeviceInfo(d, mediaAccessGranted));
                        }}
                        return targetDevices.map((d) => makeMediaDeviceInfo(d, mediaAccessGranted));
                    }}).catch(() => {{
                        return targetDevices.map((d) => makeMediaDeviceInfo(d, mediaAccessGranted));
                    }});
                }}
                return Promise.resolve(targetDevices.map((d) => makeMediaDeviceInfo(d, mediaAccessGranted)));
            }};

            navigator.mediaDevices.enumerateDevices = makeNative(fakeEnumerateDevices, 'enumerateDevices');
        }}
    }} catch (e) {{}}

    {touch_block}

    {motion_block}

    {orientation_block}

    {ios_block}
}})();"""
