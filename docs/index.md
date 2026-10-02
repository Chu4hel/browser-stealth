# browser-stealth

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**browser-stealth** — специализированная библиотека глубокой маскировки рантайма браузеров, биомеханики поведения человека (WindMouse, кривые Безье, тач-события), управления профилями и умной маршрутизации прокси.

Разработана для надежной автоматизации и парсинга современных веб-приложений под защитой антифрод-систем (Cloudflare Turnstile, DataDome, Akamai, reCAPTCHA, FingerprintJS Pro).

---

## Ключевые возможности

* 🐭 **Физическая модель движения курсора (WindMouse):** Непрерывная симуляция движений кисти человека с гравитационным притяжением, мышечным шумом и физиологическим замедлением перед кликом.
* ✍️ **Биомеханический ввод текста:** Естественные интервалы между нажатиями клавиш (Jitter Delay), симуляция опечаток и их последующее стирание клавишей Backspace.
* 📱 **Мобильные тач-жесты:** Эмуляция `touch_tap` и `touch_swipe` с микроколебаниями контакта и сглаженной физикой скролла.
* 🛡️ **Мульти-движковый антидетект:**
    * **Playwright:** Скрытые runtime CDP-инъекции, патчинг `navigator.webdriver`, плагинов, разрешений экрана и WebGL.
    * **nodriver:** Автономный Chrome без классического WebDriver протокола и флаги глубокой маскировки.
    * **Selenium:** Патчинг CDP через Page.addScriptToEvaluateOnNewDocument.
    * **WebDriver BiDi:** Прямая маскировка через современный двунаправленный протокол W3C BiDi.
    * **Camoufox:** Встроенная поддержка патченного C++ Firefox с защитой на уровне бинарника.
* 🧩 **Решение Cloudflare Turnstile:** Автоматическое обнаружение виджета, наведение курсора по траектории WindMouse и естественный клик.
* 🎭 **Синтезатор цифровой личности (Fingerprint Synthesizer):** Детерминированная процедурная генерация непротиворечивых аппаратных профилей (GPU, ANGLE D3D11, дисплеи, аудио-джиттер) и поддержка байесовской ML-модели `browserforge`.
* 📁 **Менеджер изолированных профилей:** Поддержка постоянных сессий (cookies, IndexedDB, localStorage), детекция зависших lock-файлов и санитайзинг crash-состояний (`Preferences`, `Local State`).
* 🌐 **Умный резолвер прокси:** Автоматический разбор колоночных и URL форматов, предварительное активное TCP/HTTP зондирование и дисковый кэш.
* 🧪 **Автономное тестирование:** Локальный mock HTTP-сервер, верификация экстракций и заглушки для запуска тестов без реального браузера.

---

## Архитектура модулей

```mermaid
graph TD
    BS[browser-stealth]
    BS --> H[humanize - Биомеханика]
    BS --> A[antidetect - Маскировка рантайма]
    BS --> P[profiles - Менеджер профилей]
    BS --> PR[proxy - Резолвер и пул прокси]
    BS --> F[fingerprint - Синтез личностей]
    BS --> L[launchers - Фабрики браузеров]
    BS --> T[testing - Моки и верификация]

    H --> H1[WindMouse / Безье]
    H --> H2[Опечатки и паузы]
    H --> H3[Turnstile Solver]

    A --> A1[Playwright Adapter]
    A --> A2[nodriver Adapter]
    A --> A3[Selenium Adapter]
    A --> A4[WebDriver BiDi]
```
