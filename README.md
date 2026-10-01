# browser-stealth 🥷

> Библиотека браузерного антидетекта нового поколения, биомеханической эмуляции поведения человека (**WindMouse**) и прогрева профилей для **nodriver**, **Playwright**, **Selenium** и **WebDriver BiDi**.

---

## Ключевые возможности

* **Кросс-движковый антидетект**:
  * Скрытие признаков автоматизации (`navigator.webdriver`, флаги automation CDP).
  * Полифилы и согласованный спуфинг WebGL (`UNMASKED_VENDOR_WEBGL`, `UNMASKED_RENDERER_WEBGL`), Canvas (субпиксельный детерминированный шум), AudioContext и WebRTC.
  * Защита от детекта через Web Workers и чистые трассировки стека V8 без утечек patched evaluation.
  * Поддержка Client Hints (`navigator.userAgentData`), сенсорных событий Touch API и гироскопа.
* **Биомеханика движений человека (Humanize)**:
  * Алгоритм движения мыши **WindMouse** с физической моделью гравитации, инерции и кривых Безье.
  * Имитация опечаток на клавиатуре и вариативной скорости набора текста.
  * Реалистичные сенсорные жесты: тапы, свайпы и пинч-зум.
  * Марковские цепи для эмуляции случайного блуждания и серфинга по сайтам.
* **Прогрев сессий и решение проверок (Warmers & Solvers)**:
  * `ProfileWarmer` — автоматический органический прогрев браузерных сессий через поисковые системы (Google, Yandex, Bing).
  * Автоматический обход модальных окон согласия Google Consent / GDPR.
  * Встроенный инспектор и интеграционный мост для токенов Cloudflare Turnstile.
* **Синтез и управление профилями**:
  * Синтез консистентных цифровых личностей по seed-ключу (`FingerprintSynthesizer`).
  * Защищенный экспорт/импорт профилей (`.chprofile`) с опциональным AES/Fernet-шифрованием.
  * Автоматическая гигиена и санитизация профилей (сброс флагов сбоя `exit_type`, очистка временного мусора Chromium).
* **Сетевая инфраструктура**:
  * Пул прокси с скорингом задержки, ротацией и health-check.
  * Динамическая генерация Chrome Extension для базовой аутентификации прокси.
  * Локальный TCP/SOCKS авторизационный туннель.
* **Протокол WebDriver BiDi**:
  * Кроссбраузерное внедрение антидетект скриптов через `script.addPreloadScript` поверх WebSocket-соединения.

---

## Установка

Установка ядра с нулевыми тяжелыми зависимостями:

```bash
uv add browser-stealth
# или
pip install browser-stealth
```

Установка с поддержкой конкретных браузерных движков:

```bash
uv add "browser-stealth[playwright]"  # Для Playwright
uv add "browser-stealth[nodriver]"    # Для nodriver
uv add "browser-stealth[selenium]"    # Для Selenium
uv add "browser-stealth[bidi]"        # Для протокола WebDriver BiDi
uv add "browser-stealth[all]"         # Все компоненты
```

---

## Быстрый старт

### 1. Декларативная маскировка nodriver (Zero-Footprint)

```python
import asyncio
from browser_stealth import AntidetectConfig, launch_nodriver

async def main():
    config = AntidetectConfig.preset_stealth_nodriver(
        session_seed="user_account_42",
    )
    browser = await launch_nodriver(antidetect_config=config, headless=False)
    page = await browser.get("https://bot.sannysoft.com")
    await asyncio.sleep(5)
    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Человекоподобные движения мыши (WindMouse)

```python
import asyncio
from browser_stealth.humanize import async_move_mouse, async_type_text

async def interact(tab):
    # Плавное биомеханическое перемещение мыши в координаты кнопки
    await async_move_mouse(tab, target_x=450, target_y=320)
    # Ввод текста с естественными задержками и опечатками
    await async_type_text(tab, "#search-input", "browser antidetect python")
```

### 3. Интеграция с Playwright

```python
import asyncio
from playwright.async_api import async_playwright
from browser_stealth import AntidetectConfig, apply_antidetect_playwright

async def main():
    config = AntidetectConfig.preset_aggressive(
        webgl_vendor="Google Inc. (NVIDIA)",
        webgl_renderer="ANGLE (NVIDIA, GeForce RTX 4080 Direct3D11)",
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await apply_antidetect_playwright(context, config=config)
        page = await context.new_page()
        await page.goto("https://nowecure.com")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Лицензия

Распространяется под лицензией MIT.
