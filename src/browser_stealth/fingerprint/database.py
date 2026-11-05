"""Базы данных и матрицы физической совместимости оборудования (Hardware Tiers)."""

from __future__ import annotations

from typing import NamedTuple


class GPUTier(NamedTuple):
    """Описание тира оборудования с допустимыми диапазонами характеристик."""

    tier_name: str
    gpus: list[tuple[str, str]]  # (Vendor, FullRendererName)
    memory_options: list[int]  # RAM в ГБ
    cpu_cores_options: list[int]  # Логические ядра CPU
    screen_options: list[tuple[int, int, float]]  # (width, height, devicePixelRatio)
    has_webcam_probability: float


TIER_ENTHUSIAST = GPUTier(
    tier_name="enthusiast",
    gpus=[
        ("NVIDIA", "NVIDIA GeForce RTX 4090"),
        ("NVIDIA", "NVIDIA GeForce RTX 4080"),
        ("NVIDIA", "NVIDIA GeForce RTX 4070 Ti"),
        ("NVIDIA", "NVIDIA GeForce RTX 3090"),
        ("NVIDIA", "NVIDIA GeForce RTX 3080"),
        ("AMD", "AMD Radeon RX 7900 XTX"),
        ("AMD", "AMD Radeon RX 6900 XT"),
    ],
    memory_options=[32, 64],
    cpu_cores_options=[12, 16, 20, 24, 32],
    screen_options=[
        (2560, 1440, 1.0),
        (2560, 1440, 1.25),
        (3840, 2160, 1.5),
        (3840, 2160, 2.0),
        (1920, 1080, 1.0),
    ],
    has_webcam_probability=0.35,
)
"""Аппаратный тир для энтузиастов и высокопроизводительных ПК."""

TIER_MAINSTREAM = GPUTier(
    tier_name="mainstream",
    gpus=[
        ("NVIDIA", "NVIDIA GeForce RTX 4060 Ti"),
        ("NVIDIA", "NVIDIA GeForce RTX 4060"),
        ("NVIDIA", "NVIDIA GeForce RTX 3070"),
        ("NVIDIA", "NVIDIA GeForce RTX 3060"),
        ("NVIDIA", "NVIDIA GeForce RTX 2070"),
        ("NVIDIA", "NVIDIA GeForce RTX 2060"),
        ("AMD", "AMD Radeon RX 7700 XT"),
        ("AMD", "AMD Radeon RX 6700 XT"),
        ("AMD", "AMD Radeon RX 6600"),
    ],
    memory_options=[16, 32],
    cpu_cores_options=[8, 12, 16],
    screen_options=[
        (1920, 1080, 1.0),
        (1920, 1080, 1.25),
        (2560, 1440, 1.0),
        (2560, 1440, 1.25),
    ],
    has_webcam_probability=0.45,
)
"""Аппаратный тир массовых игровых и рабочих ПК."""

TIER_BUDGET_DESKTOP = GPUTier(
    tier_name="budget_desktop",
    gpus=[
        ("NVIDIA", "NVIDIA GeForce GTX 1660 SUPER"),
        ("NVIDIA", "NVIDIA GeForce GTX 1650"),
        ("NVIDIA", "NVIDIA GeForce GTX 1060 6GB"),
        ("NVIDIA", "NVIDIA GeForce GTX 1050 Ti"),
        ("AMD", "Radeon RX 580 Series"),
        ("AMD", "Radeon RX 570 Series"),
        ("Intel", "Intel(R) Arc(TM) A750 Graphics"),
        ("Intel", "Intel(R) Arc(TM) A770 Graphics"),
    ],
    memory_options=[8, 16],
    cpu_cores_options=[6, 8, 12],
    screen_options=[
        (1920, 1080, 1.0),
        (1600, 900, 1.0),
        (1920, 1080, 1.25),
    ],
    has_webcam_probability=0.30,
)
"""Аппаратный тир бюджетных и офисных десктопов."""

TIER_LAPTOP = GPUTier(
    tier_name="laptop",
    gpus=[
        ("Intel", "Intel(R) Iris(R) Xe Graphics"),
        ("Intel", "Intel(R) UHD Graphics 770"),
        ("Intel", "Intel(R) UHD Graphics 630"),
        ("AMD", "AMD Radeon(TM) Graphics"),
        ("AMD", "AMD Radeon 680M"),
    ],
    memory_options=[8, 16],
    cpu_cores_options=[4, 6, 8, 12, 16],
    screen_options=[
        (1920, 1080, 1.0),
        (1920, 1080, 1.25),
        (1536, 864, 1.25),
        (1366, 768, 1.0),
        (1440, 900, 1.0),
        (2880, 1800, 2.0),
    ],
    has_webcam_probability=0.95,
)
"""Аппаратный тир ноутбуков и ультрабуков."""

ALL_TIERS = [TIER_MAINSTREAM, TIER_ENTHUSIAST, TIER_BUDGET_DESKTOP, TIER_LAPTOP]
"""Список всех доступных аппаратных конфигураций для Windows."""

TIER_MACOS_APPLE_SILICON = GPUTier(
    tier_name="macos_apple_silicon",
    gpus=[
        ("Apple", "Apple M1"),
        ("Apple", "Apple M2"),
        ("Apple", "Apple M3"),
        ("Apple", "Apple M1 Pro"),
        ("Apple", "Apple M2 Pro"),
        ("Apple", "Apple M3 Pro"),
    ],
    memory_options=[8, 16, 24, 32, 36, 48],
    cpu_cores_options=[8, 10, 11, 12, 14, 16],
    screen_options=[
        (1440, 900, 2.0),
        (1680, 1050, 2.0),
        (1728, 1117, 2.0),
        (1512, 982, 2.0),
        (2560, 1440, 2.0),
    ],
    has_webcam_probability=0.99,
)
"""Аппаратный тир macOS на чипах Apple Silicon (M1/M2/M3)."""

TIER_MACOS_INTEL = GPUTier(
    tier_name="macos_intel",
    gpus=[
        ("Intel", "Intel(R) Iris(TM) Plus Graphics 645"),
        ("AMD", "AMD Radeon Pro 5300M"),
        ("AMD", "AMD Radeon Pro 5500M"),
    ],
    memory_options=[8, 16, 32],
    cpu_cores_options=[4, 6, 8],
    screen_options=[
        (1440, 900, 2.0),
        (1680, 1050, 2.0),
        (1792, 1120, 2.0),
    ],
    has_webcam_probability=0.95,
)
"""Аппаратный тир macOS на процессорах Intel."""

MACOS_TIERS = [TIER_MACOS_APPLE_SILICON, TIER_MACOS_INTEL]
"""Список конфигураций macOS."""

TIER_LINUX_DESKTOP = GPUTier(
    tier_name="linux_desktop",
    gpus=[
        ("Mesa", "Mesa Intel(R) UHD Graphics 630 (CFL GT2)"),
        ("Mesa", "AMD Radeon RX 6600 (radeonsi, navi23, LLVM 15.0.7, DRM 3.49)"),
        ("NVIDIA", "NVIDIA GeForce RTX 3060/PCIe/SSE2"),
        ("NVIDIA", "NVIDIA GeForce RTX 4060/PCIe/SSE2"),
    ],
    memory_options=[8, 16, 32, 64],
    cpu_cores_options=[4, 6, 8, 12, 16, 24],
    screen_options=[
        (1920, 1080, 1.0),
        (2560, 1440, 1.0),
        (3840, 2160, 1.5),
        (1920, 1080, 1.25),
    ],
    has_webcam_probability=0.40,
)
"""Аппаратный тир для десктопных дистрибутивов Linux."""

LINUX_TIERS = [TIER_LINUX_DESKTOP]
"""Список конфигураций Linux."""

AUDIO_INPUTS_RU = [
    "Микрофон (Realtek(R) Audio)",
    "Микрофон (Realtek High Definition Audio)",
    "Микрофон (USB Audio Device)",
    "Массив микрофонов (Intel(R) Smart Sound Technology)",
]
"""Список русскоязычных названий микрофонов."""

AUDIO_INPUTS_EN = [
    "Microphone (Realtek(R) Audio)",
    "Microphone (Realtek High Definition Audio)",
    "Microphone (USB Audio Device)",
    "Microphone Array (Intel(R) Smart Sound Technology)",
]
"""Список англоязычных названий микрофонов."""

AUDIO_INPUTS_MAC = [
    "MacBook Pro Microphone",
    "MacBook Air Microphone",
    "Internal Microphone",
    "Built-in Microphone",
]
"""Список названий микрофонов macOS."""

AUDIO_INPUTS_LINUX = [
    "Built-in Audio Analog Stereo (PulseAudio)",
    "HD Audio Controller Digital Stereo (HDMI)",
    "Default Audio Device (ALSA)",
]
"""Список названий микрофонов Linux."""

AUDIO_OUTPUTS_RU = [
    "Динамики (Realtek(R) Audio)",
    "Динамики (Realtek High Definition Audio)",
    "Наушники (Realtek(R) Audio)",
    "Динамики (High Definition Audio Device)",
]
"""Список русскоязычных названий аудиовыходов."""

AUDIO_OUTPUTS_EN = [
    "Speakers (Realtek(R) Audio)",
    "Speakers (Realtek High Definition Audio)",
    "Headphones (Realtek(R) Audio)",
    "Speakers (High Definition Audio Device)",
]
"""Список англоязычных названий аудиовыходов."""

AUDIO_OUTPUTS_MAC = [
    "MacBook Pro Speakers",
    "MacBook Air Speakers",
    "Internal Speakers",
    "Built-in Output",
]
"""Список названий динамиков macOS."""

AUDIO_OUTPUTS_LINUX = [
    "Built-in Audio Analog Stereo (PulseAudio)",
    "Line Out (ALSA)",
    "Default Audio Device (ALSA)",
]
"""Список названий аудиовыходов Linux."""

VIDEO_INPUTS = [
    "Integrated Camera (04f2:b6d9)",
    "HD User Facing Webcam",
    "USB Video Device",
    "FHD Webcam",
]
"""Список названий веб-камер."""
