# Антидетект и маскировка браузеров (antidetect)

Модуль `browser_stealth.antidetect` отвечает за устранение всех известных маркеров автоматизации в рантайме браузера.

---

## 1. Конфигурация `AntidetectConfig`

Центральный класс настроек антидетекта:

```python
from browser_stealth import AntidetectConfig

config = AntidetectConfig(
    hide_webdriver=True,  # navigator.webdriver = undefined
    patch_permissions=True,  # Notification / Permissions API spoofing
    patch_plugins=True,  # Эмуляция PDF Viewer и стандартных плагинов
    patch_screen=True,  # Согласованность window.screen и window.outerWidth
    screen_width=1920,
    screen_height=1080,
    patch_webgl=True,  # Вендор и рендерер WebGL (например, NVIDIA/ANGLE)
    webgl_vendor="Google Inc. (NVIDIA)",
    webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)",
    patch_audio=True,  # Аудио-джиттер WebAudio API
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
    languages=["ru-RU", "ru", "en-US", "en"],
    platform="Win32",
)
```

### Готовые пресеты

* `AntidetectConfig.preset_stealth_playwright()`
* `AntidetectConfig.preset_stealth_nodriver()`
* `AntidetectConfig.preset_stealth_selenium()`
* `AntidetectConfig.preset_mobile_android()`

---

## 2. Адаптеры интеграции

### Playwright

```python
from browser_stealth import apply_antidetect_playwright, AntidetectConfig

config = AntidetectConfig.preset_stealth_playwright()
await apply_antidetect_playwright(page_or_context, config)
```

### nodriver

```python
from browser_stealth import launch_nodriver, AntidetectConfig

# Фабрика сама применяет нужные флаги командной строки и CDP-инъекции
browser = await launch_nodriver(
    config=AntidetectConfig.preset_stealth_nodriver(),
    headless=False,
)
```

### Selenium WebDriver

```python
from browser_stealth import apply_antidetect_selenium, AntidetectConfig

config = AntidetectConfig.preset_stealth_selenium()
apply_antidetect_selenium(driver, config)
```

### WebDriver BiDi

Поддержка W3C WebDriver BiDi протокола для двунаправленного управления через WebSockets:

```python
from browser_stealth.bidi import BiDiClient, apply_antidetect_bidi

async with BiDiClient("ws://localhost:9222/session") as client:
    await apply_antidetect_bidi(client, config)
```

---

## 3. Мост авторизации (Clearance Bridge)

Связка браузерной сессии с легковесным TLS HTTP-клиентом:
После прохождения Cloudflare Turnstile в браузере вы можете извлечь cookies и User-Agent и продолжить работу через `TLSAsyncClient` из `chutils.http`:

```python
from browser_stealth.antidetect import extract_clearance_cookies

# Извлечение cf_clearance и User-Agent
credentials = await extract_clearance_cookies(page)
print(credentials["cookies"])  # [{'name': 'cf_clearance', 'value': '...'}]
print(credentials["user_agent"])  # 'Mozilla/5.0 ...'
```
