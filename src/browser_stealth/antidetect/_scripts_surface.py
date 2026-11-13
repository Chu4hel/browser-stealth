"""Поверхностные JS-эмуляции: webdriver, plugins, экран, Client Hints, Permissions и mediaDevices."""

from __future__ import annotations

__all__ = ["_JS_SURFACE_PART"]

_JS_SURFACE_PART = """    // 1. Скрытие и очистка navigator.webdriver
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

    // 5.1. Эмуляция размеров окна (outerWidth, outerHeight, screenX, screenY)
    try {{
        if (typeof window !== 'undefined') {{
            const windowFrameHeight = 75 + (Math.abs(seedNum) % 18);
            const windowFrameWidth = (Math.abs(seedNum) % 3) * 8;

            Object.defineProperty(window, 'outerWidth', {{
                get: makeNative(() => (window.innerWidth || 1280) + windowFrameWidth, 'get outerWidth'),
                configurable: true,
                enumerable: true
            }});
            Object.defineProperty(window, 'outerHeight', {{
                get: makeNative(() => (window.innerHeight || 800) + windowFrameHeight, 'get outerHeight'),
                configurable: true,
                enumerable: true
            }});

            const defaultScreenTop = {screen_avail_top_js} !== null ? {screen_avail_top_js} : 0;
            const defaultScreenLeft = {screen_avail_left_js} !== null ? {screen_avail_left_js} : 0;
            Object.defineProperty(window, 'screenX', {{
                get: makeNative(() => defaultScreenLeft, 'get screenX'),
                configurable: true,
                enumerable: true
            }});
            Object.defineProperty(window, 'screenLeft', {{
                get: makeNative(() => defaultScreenLeft, 'get screenLeft'),
                configurable: true,
                enumerable: true
            }});
            Object.defineProperty(window, 'screenY', {{
                get: makeNative(() => defaultScreenTop, 'get screenY'),
                configurable: true,
                enumerable: true
            }});
            Object.defineProperty(window, 'screenTop', {{
                get: makeNative(() => defaultScreenTop, 'get screenTop'),
                configurable: true,
                enumerable: true
            }});
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

    // 9. Эмуляция характеристик дисплея и панели задач на Screen.prototype и объекте screen
    try {{
        if (typeof window !== 'undefined') {{
            const screenProto = typeof Screen !== 'undefined' ? Screen.prototype : null;

            const targetWidth = {screen_w_js} !== null ? {screen_w_js} : (typeof screen !== 'undefined' ? screen.width : 1920);
            const targetHeight = {screen_h_js} !== null ? {screen_h_js} : (typeof screen !== 'undefined' ? screen.height : 1080);
            const targetAvailWidth = {screen_avail_w_js} !== null ? {screen_avail_w_js} : targetWidth;
            const targetAvailHeight = {screen_avail_h_js} !== null ? {screen_avail_h_js} : (targetHeight > 40 ? targetHeight - 40 : targetHeight);
            const targetAvailTop = {screen_avail_top_js} !== null ? {screen_avail_top_js} : 0;
            const targetAvailLeft = {screen_avail_left_js} !== null ? {screen_avail_left_js} : 0;

            const screenProps = {{
                width: targetWidth,
                height: targetHeight,
                availWidth: targetAvailWidth,
                availHeight: targetAvailHeight,
                availTop: targetAvailTop,
                availLeft: targetAvailLeft,
                colorDepth: 24,
                pixelDepth: 24,
            }};

            for (const [propName, propVal] of Object.entries(screenProps)) {{
                const getterFn = makeNative(() => propVal, `get ${{propName}}`);
                if (screenProto) {{
                    try {{
                        Object.defineProperty(screenProto, propName, {{
                            get: getterFn,
                            configurable: true,
                            enumerable: true
                        }});
                    }} catch (e) {{}}
                }}
                if (typeof screen !== 'undefined') {{
                    try {{
                        Object.defineProperty(screen, propName, {{
                            get: getterFn,
                            configurable: true,
                            enumerable: true
                        }});
                    }} catch (e) {{}}
                }}
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
