# Справочник API

Краткий справочник основных классов и модулей библиотеки `browser-stealth`.

---

## 1. Модуль `browser_stealth.antidetect`

| Имя | Описание |
|---|---|
| `AntidetectConfig` | Конфигурационный класс антидетекта (navigator, WebGL, Audio, Screen, Plugins) |
| `apply_antidetect_playwright` | Внедрение CDP-скриптов и настроек в Playwright Page / Context |
| `apply_antidetect_nodriver` | Применение антидетекта к вкладке Chromium через nodriver |
| `apply_antidetect_selenium` | Применение CDP-маскировки в Selenium WebDriver |
| `extract_clearance_cookies` | Извлечение cookies и User-Agent для авторизованных TLS-запросов |
| `get_browser_launch_args` | Набор обязательных аргументов командной строки Chromium для обхода детектов |

---

## 2. Модуль `browser_stealth.humanize`

| Имя | Описание |
|---|---|
| `WindMouseGenerator` | Физическая модель перемещения курсора (гравитация, шум ветра, замедление) |
| `BezierCurveGenerator` | Генератор кубических кривых Безье |
| `JitterDelayGenerator` | Генератор случайных задержек по Гауссову распределению |
| `KeyboardTypoGenerator` | Генератор клавиатурных опечаток и промахов по соседним клавишам |
| `BehavioralProfile` | Поведенческий профиль (скорость реакции, темп набора, агрессивность) |
| `click`, `async_click` | Клик по элементу или координатам с предварительным наведением |
| `type_text`, `async_type_text` | Печать текста с симуляцией опечаток и стиранием через Backspace |
| `scroll_to`, `async_scroll_to` | Плавная прокрутка страницы с переменной скоростью |
| `human_sleep`, `async_human_sleep` | Случайная пауза в заданном диапазоне |
| `async_touch_tap`, `async_touch_swipe` | Эмуляция мобильных тач-событий |
| `solve_cf_turnstile` | Поиск и решение интерактивного чекбокса Cloudflare Turnstile |

---

## 3. Модуль `browser_stealth.launchers`

| Имя | Описание |
|---|---|
| `launch_nodriver` | Фабрика запуска nodriver с санитайзингом профиля и флагами маскировки |
| `nodriver_session` | Асинхронный контекстный менеджер безопасной сессии nodriver |
| `close_tab` | Безопасное закрытие вкладки nodriver с таймаутом |
| `launch_camoufox` | Запуск антидетект-браузера Camoufox (Firefox) |

---

## 4. Модуль `browser_stealth.profiles`

| Имя | Описание |
|---|---|
| `ProfileManager` | Менеджер постоянных директорий профилей |
| `BrowserProfile` | Модель профиля с метаданными и путями к хранилищу |
| `is_profile_locked` | Проверка наличия блокирующих lock-файлов в директории профиля |
| `sanitize_profile` | Полная очистка lock-файлов, кэша шейдеров и крэш-маркеров |
| `sanitize_profile_crash_state` | Сброс статуса `Crashed` в JSON-файлах Preferences браузера |

---

## 5. Модуль `browser_stealth.proxy`

| Имя | Описание |
|---|---|
| `parse_proxy` | Парсер различных строковых и словарных форматов прокси |
| `ProxyConfig` | Pydantic-модель конфигурации прокси |
| `SmartProxyResolver` | Активный анализатор протоколов (HTTP/SOCKS5) с дисковым кэшем |
| `ProxyPool` | Пул адресов прокси со стратегиями ротации |
| `AsyncProxyTunnel` | Локальный TCP-туннель для маршрутизации трафика |

---

## 6. Модуль `browser_stealth.fingerprint`

| Имя | Описание |
|---|---|
| `FingerprintSynthesizer` | Процедурный генератор непротиворечивых аппаратных профилей |
| `FingerprintProfile` | Структурированная модель цифровой личности |
| `BrowserForgeProvider` | Интеграция с ML-генератором `browserforge` |
