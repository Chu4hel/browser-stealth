# Синтез цифровой личности (fingerprint)

Модуль `browser_stealth.fingerprint` обеспечивает генерацию физически непротиворечивых параметров оборудования и окружения.

---

## 1. Синтезатор отпечатков (`FingerprintSynthesizer`)

Генерирует согласованный профиль, где все параметры соответствуют реальному сочетанию железа и ОС:
* Видеокарта (WebGL Vendor, Renderer, ANGLE D3D11 строки для Windows, Metal для macOS, Mesa для Linux).
* Разрешение экрана и доступная область (с учетом высоты панели задач Windows / macOS Dock).
* Субпиксельный шум WebAudio API и Canvas.
* Реалистичные списки аудио- и видеоустройств (`navigator.mediaDevices`).

```python
from browser_stealth.fingerprint.synthesizer import FingerprintSynthesizer

synthesizer = FingerprintSynthesizer()

# Детерминированная генерация по сиду (или случайная)
profile = synthesizer.generate(seed="my_stable_seed_123")

print(profile.os)              # "windows"
print(profile.webgl.vendor)    # "Google Inc. (NVIDIA)"
print(profile.webgl.renderer)  # "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11...)"
print(profile.screen.width)    # 1920
print(profile.screen.height)   # 1080
print(profile.screen.avail_height) # 1040 (минус панель задач)
```

---

## 2. Экспорт в `AntidetectConfig`

Сгенерированный отпечаток легко преобразуется в конфигурацию антидетекта:

```python
config = profile.to_antidetect_config()
await apply_antidetect_playwright(page, config)
```

---

## 3. Интеграция с BrowserForge (ML-моделирование)

При установке опционального пакета `pip install "browser-stealth[fingerprint]"` библиотека может использовать байесовскую модель распределения реальных отпечатков:

```python
from browser_stealth.fingerprint.external import BrowserForgeProvider

provider = BrowserForgeProvider()
profile = provider.get_fingerprint(browser="chrome", os="windows")
```
