"""Процедурный детерминированный генератор цифрового отпечатка (Tier-Based Synthesizer)."""

from __future__ import annotations

import hashlib
import random

from .database import (
    ALL_TIERS,
    AUDIO_INPUTS_EN,
    AUDIO_INPUTS_LINUX,
    AUDIO_INPUTS_MAC,
    AUDIO_INPUTS_RU,
    AUDIO_OUTPUTS_EN,
    AUDIO_OUTPUTS_LINUX,
    AUDIO_OUTPUTS_MAC,
    AUDIO_OUTPUTS_RU,
    LINUX_TIERS,
    MACOS_TIERS,
    VIDEO_INPUTS,
    GPUTier,
)
from .models import (
    AudioFingerprint,
    FingerprintProfile,
    HardwareFingerprint,
    MediaDeviceItem,
    ScreenFingerprint,
    WebGLFingerprint,
)


class ProceduralSynthesizer:
    """Генератор консистентных цифровых отпечатков на основе физических матриц оборудования."""

    def __init__(
        self,
        os_target: str = "windows",
        locale: str = "ru-RU",
    ) -> None:
        """Инициализирует процедурный синтезатор.

        Args:
            os_target: Целевая операционная система ('windows', 'macos', 'linux').
            locale: Локаль системы для именования периферийных устройств.
        """
        self.os_target = os_target.lower()
        self.locale = locale

    def synthesize(self, seed: int | str | None = None) -> FingerprintProfile:
        """Синтезирует физически согласованный профиль цифрового отпечатка по сиду.

        Args:
            seed: Исходный сид для детерминированного воспроизведения отпечатка.

        Returns:
            Экземпляр FingerprintProfile с непротиворечивым набором характеристик.
        """
        rng = random.Random(seed)
        os_lower = self.os_target
        is_macos = os_lower in ("macos", "darwin", "mac")
        is_linux = os_lower in ("linux",)

        # 1. Выбираем Tier оборудования с учетом целевой ОС и рыночного распределения
        if is_macos:
            chosen_tier: GPUTier = rng.choice(MACOS_TIERS)
        elif is_linux:
            chosen_tier = rng.choice(LINUX_TIERS)
        else:
            tier_weights = [0.40, 0.20, 0.20, 0.20]
            chosen_tier = rng.choices(ALL_TIERS, weights=tier_weights, k=1)[0]

        # 2. Выбираем GPU и строим согласованную строку рендерера ANGLE
        vendor, full_renderer = rng.choice(chosen_tier.gpus)

        if is_macos:
            if vendor == "Apple":
                webgl_vendor = "Google Inc. (Apple)"
                webgl_renderer_str = f"ANGLE (Apple, {full_renderer}, OpenGL 4.1)"
            elif vendor == "Intel":
                webgl_vendor = "Google Inc. (Intel)"
                webgl_renderer_str = f"ANGLE (Intel Inc., {full_renderer}, OpenGL 4.1)"
            elif vendor == "AMD":
                webgl_vendor = "Google Inc. (AMD)"
                webgl_renderer_str = (
                    f"ANGLE (ATI Technologies Inc., {full_renderer} OpenGL Engine, OpenGL 4.1)"
                )
            else:
                webgl_vendor = f"Google Inc. ({vendor})"
                webgl_renderer_str = f"ANGLE ({vendor}, {full_renderer}, OpenGL 4.1)"
        elif is_linux:
            if vendor == "Mesa":
                webgl_vendor = "Google Inc. (Mesa)"
                webgl_renderer_str = f"ANGLE (Mesa, {full_renderer}, OpenGL 4.5.0)"
            elif vendor == "NVIDIA":
                webgl_vendor = "Google Inc. (NVIDIA)"
                webgl_renderer_str = f"ANGLE (NVIDIA, {full_renderer}, OpenGL 4.5.0)"
            else:
                webgl_vendor = f"Google Inc. ({vendor})"
                webgl_renderer_str = f"ANGLE ({vendor}, {full_renderer}, OpenGL 4.5.0)"
        else:  # Windows (Direct3D11)
            if vendor == "NVIDIA":
                webgl_vendor = "Google Inc. (NVIDIA)"
                build_num = rng.randint(3600, 6550)
                driver_ver = f"D3D11-31.0.15.{build_num}"
            elif vendor == "AMD":
                webgl_vendor = "Google Inc. (AMD)"
                build_num = rng.randint(1000, 9999)
                driver_ver = f"D3D11-31.0.21.{build_num}"
            else:  # Intel
                webgl_vendor = "Google Inc. (Intel)"
                build_num = rng.randint(4500, 5800)
                driver_ver = f"D3D11-31.0.101.{build_num}"

            webgl_renderer_str = (
                f"ANGLE ({vendor}, {full_renderer} Direct3D11 vs_5_0 ps_5_0, {driver_ver})"
            )

        # 3. Аппаратный профиль (CPU Cores и RAM)
        memory_gb = rng.choice(chosen_tier.memory_options)
        cpu_cores = rng.choice(chosen_tier.cpu_cores_options)

        # 4. Дисплей и геометрия окна (с учетом особенностей панели задач конкретной ОС)
        screen_w, screen_h, pixel_ratio = rng.choice(chosen_tier.screen_options)

        if is_macos:
            taskbar_height = 25  # Верхняя строка меню macOS
            avail_top = 25
            avail_left = 0
        elif is_linux:
            taskbar_height = 32  # Панель дистрибутивов Linux
            avail_top = 32
            avail_left = 0
        else:
            # Высота панели задач Taskbar на Windows
            if pixel_ratio > 1.0:
                taskbar_height = rng.choice([48, 60])
            else:
                taskbar_height = 40
            avail_top = 0
            avail_left = 0

        avail_h = screen_h - taskbar_height
        avail_w = screen_w

        # 5. Аудиоподсистема и субпиксельный шум
        noise_factor = round(rng.uniform(1e-7, 9e-7), 8)

        # 6. Периферия: MediaDevices с учетом платформы и локали
        media_devices: list[MediaDeviceItem] = []
        if is_macos:
            mic_pool = AUDIO_INPUTS_MAC
            speakers_pool = AUDIO_OUTPUTS_MAC
        elif is_linux:
            mic_pool = AUDIO_INPUTS_LINUX
            speakers_pool = AUDIO_OUTPUTS_LINUX
        else:
            is_ru = "ru" in self.locale.lower()
            mic_pool = AUDIO_INPUTS_RU if is_ru else AUDIO_INPUTS_EN
            speakers_pool = AUDIO_OUTPUTS_RU if is_ru else AUDIO_OUTPUTS_EN

        mic_name = rng.choice(mic_pool)
        speakers_name = rng.choice(speakers_pool)

        def make_id(name: str, idx: int) -> str:
            raw = f"{seed or 'default'}:{name}:{idx}".encode()
            return hashlib.sha256(raw).hexdigest()

        group_audio = make_id("audio_group", 0)
        media_devices.append(
            MediaDeviceItem(
                kind="audioinput",
                label=mic_name,
                device_id=make_id(mic_name, 1),
                group_id=group_audio,
            )
        )
        media_devices.append(
            MediaDeviceItem(
                kind="audiooutput",
                label=speakers_name,
                device_id=make_id(speakers_name, 2),
                group_id=group_audio,
            )
        )

        if rng.random() < chosen_tier.has_webcam_probability:
            cam_name = rng.choice(VIDEO_INPUTS)
            media_devices.append(
                MediaDeviceItem(
                    kind="videoinput",
                    label=cam_name,
                    device_id=make_id(cam_name, 3),
                    group_id=make_id("video_group", 4),
                )
            )

        # 7. User-Agent и Client Hints
        chrome_major = rng.randint(124, 131)
        chrome_patch = rng.randint(100, 999)
        chrome_ver = f"{chrome_major}.0.{chrome_patch}.0"

        if is_macos:
            user_agent = (
                f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{chrome_ver} Safari/537.36"
            )
            client_hints = {
                "platform": "macOS",
                "mobile": False,
                "brands": [
                    {"brand": "Not/A)Brand", "version": "8"},
                    {"brand": "Chromium", "version": str(chrome_major)},
                    {"brand": "Google Chrome", "version": str(chrome_major)},
                ],
                "platformVersion": "14.5.0",
                "architecture": "arm" if vendor == "Apple" else "x86",
                "bitness": "64",
                "model": "",
            }
        elif is_linux:
            user_agent = (
                f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{chrome_ver} Safari/537.36"
            )
            client_hints = {
                "platform": "Linux",
                "mobile": False,
                "brands": [
                    {"brand": "Not/A)Brand", "version": "8"},
                    {"brand": "Chromium", "version": str(chrome_major)},
                    {"brand": "Google Chrome", "version": str(chrome_major)},
                ],
                "platformVersion": "6.5.0",
                "architecture": "x86",
                "bitness": "64",
                "model": "",
            }
        else:
            user_agent = (
                f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{chrome_ver} Safari/537.36"
            )
            client_hints = {
                "platform": "Windows",
                "mobile": False,
                "brands": [
                    {"brand": "Not/A)Brand", "version": "8"},
                    {"brand": "Chromium", "version": str(chrome_major)},
                    {"brand": "Google Chrome", "version": str(chrome_major)},
                ],
                "platformVersion": "10.0.0",
                "architecture": "x86",
                "bitness": "64",
                "model": "",
            }

        return FingerprintProfile(
            seed=seed,
            os=self.os_target,
            browser="chrome",
            locale=self.locale,
            user_agent=user_agent,
            webgl=WebGLFingerprint(vendor=webgl_vendor, renderer=webgl_renderer_str),
            screen=ScreenFingerprint(
                width=screen_w,
                height=screen_h,
                avail_width=avail_w,
                avail_height=avail_h,
                avail_top=avail_top,
                avail_left=avail_left,
                device_pixel_ratio=pixel_ratio,
                color_depth=24,
            ),
            hardware=HardwareFingerprint(
                concurrency=cpu_cores,
                memory_gb=memory_gb,
            ),
            audio=AudioFingerprint(
                noise_factor=noise_factor,
            ),
            media_devices=media_devices,
            client_hints=client_hints,
            source="procedural",
        )
