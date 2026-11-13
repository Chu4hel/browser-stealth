"""Генератор JavaScript-инъекций антидетекта для браузеров."""

from __future__ import annotations

import json
from typing import Any

from ._scripts_core import _JS_CORE_PART
from ._scripts_surface import _JS_SURFACE_PART
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
    screen_avail_width: int | None = None,
    screen_avail_top: int | None = None,
    screen_avail_left: int | None = None,
    device_pixel_ratio: float | None = None,
    media_devices: list[dict[str, Any]] | None = None,
    is_mobile: bool = False,
    has_touch: bool = False,
    max_touch_points: int = 0,
    is_ios: bool = False,
    orientation: dict[str, Any] | None = None,
    locale: str = "en-US",
    user_agent: str | None = None,
    timezone: str | None = None,
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
    screen_avail_w_js = json.dumps(screen_avail_width)
    screen_avail_top_js = json.dumps(screen_avail_top)
    screen_avail_left_js = json.dumps(screen_avail_left)
    dpr_js = json.dumps(device_pixel_ratio)
    devices_js = json.dumps(media_devices) if media_devices is not None else "null"
    locale_js = json.dumps(locale)
    ua_js = json.dumps(user_agent) if user_agent is not None else "null"
    tz_js = json.dumps(timezone) if timezone is not None else "null"
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

    return (_JS_CORE_PART + _JS_SURFACE_PART).format(
        concurrency_js=concurrency_js,
        devices_js=devices_js,
        dpr_js=dpr_js,
        hints_js=hints_js,
        ios_block=ios_block,
        locale_js=locale_js,
        main_ua_block=main_ua_block,
        memory_js=memory_js,
        minimal_js=minimal_js,
        motion_block=motion_block,
        orientation_block=orientation_block,
        renderer_js=renderer_js,
        screen_avail_h_js=screen_avail_h_js,
        screen_avail_left_js=screen_avail_left_js,
        screen_avail_top_js=screen_avail_top_js,
        screen_avail_w_js=screen_avail_w_js,
        screen_h_js=screen_h_js,
        screen_w_js=screen_w_js,
        seed_js=seed_js,
        touch_block=touch_block,
        tz_js=tz_js,
        ua_js=ua_js,
        vendor_js=vendor_js,
        worker_ua_block=worker_ua_block,
    )
