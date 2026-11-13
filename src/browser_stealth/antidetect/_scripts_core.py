"""Ядро JS-инъекции антидетекта: маскировка нативных функций, window.chrome, WebRTC и изоляция контекстов."""

from __future__ import annotations

__all__ = ["_JS_CORE_PART"]

_JS_CORE_PART = """(function() {{
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

                let customOnIceCandidate = null;
                Object.defineProperty(pc, 'onicecandidate', {{
                    get: () => customOnIceCandidate,
                    set: function(handler) {{
                        if (typeof handler === 'function') {{
                            customOnIceCandidate = function(evt) {{
                                if (evt && evt.candidate && evt.candidate.candidate && evt.candidate.candidate.includes('typ host')) {{
                                    return;
                                }}
                                return handler.apply(this, arguments);
                            }};
                        }} else {{
                            customOnIceCandidate = handler;
                        }}
                    }},
                    configurable: true,
                    enumerable: true
                }});

                const origAddEventListener = pc.addEventListener;
                pc.addEventListener = function(type, listener, options) {{
                    if (type === 'icecandidate' && typeof listener === 'function') {{
                        const wrapped = function(evt) {{
                            if (evt && evt.candidate && evt.candidate.candidate && evt.candidate.candidate.includes('typ host')) {{
                                return;
                            }}
                            return listener.apply(this, arguments);
                        }};
                        return origAddEventListener.call(this, type, wrapped, options);
                    }}
                    return origAddEventListener.apply(this, arguments);
                }};
                makeNative(pc.addEventListener, 'addEventListener');

                return pc;
            }};
            PatchedPeerConnection.prototype = OrigPeerConnection.prototype;
            window.RTCPeerConnection = makeNative(PatchedPeerConnection, 'RTCPeerConnection');
        }}
    }} catch (e) {{}}

    // 0.25. Синхронизация Intl API и таймзоны
    const targetTimezone = {tz_js};
    if (targetTimezone) {{
        try {{
            if (typeof Intl !== 'undefined' && Intl.DateTimeFormat) {{
                const origResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
                Intl.DateTimeFormat.prototype.resolvedOptions = makeNative(function resolvedOptions() {{
                    const res = origResolvedOptions.apply(this, arguments);
                    if (res) {{
                        res.timeZone = targetTimezone;
                    }}
                    return res;
                }}, 'resolvedOptions');
            }}
        }} catch (e) {{}}
    }}

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
                // navigator.plugins в дочерних окнах тоже оставляем нативным:
                // фейковый массив ломает instanceof PluginArray и палится детекторами.

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

"""
