Стабильный релиз `0.4.0`: точечное обновление humanize, инспекции страниц
и запуска nodriver. Ветка исправляет два воспроизведённых дефекта — занос
WindMouse в соседний пункт компактного меню и поиск поля ввода в nodriver —
добавляет сохранение страницы в MHTML, переподключение к уже открытому
Chromium по CDP и устойчивость сессии при рестарте сервиса.

## Основные изменения

### Humanize: WindMouse больше не проскакивает цель

- Длина шага у финиша ограничивается оставшимся расстоянием до цели.
- Добавлен покоординатный запрет на пересечение цели по осям движения:
  боковой снос ветра больше не позволяет обойти точку и уйти ниже неё.
- Исправлен занос курсора из пункта «Скрыть эту вакансию» в соседний
  пункт «Пожаловаться» в компактном меню (ISSUE-20261120-B7A1).
- Регрессионный тест проверяет 1000 seed на исходной геометрии.

### Humanize: ограничение дрейфа при тач-тапе

- `TouchGestureGenerator.generate_tap()` принимает необязательный
  `bounds=(x_min, y_min, x_max, y_max)`.
- Если границы переданы, микросдвиг пальца остаётся внутри целевого
  прямоугольника и не уходит в соседний пункт.
- Без `bounds` поведение не изменилось.

### Inspect: MHTML-архив страницы

- Добавлена `await inspect.save_mhtml(tab, path, timeout=30.0)` для вкладки nodriver.
- Архив сохраняется через CDP `Page.captureSnapshot(format="mhtml")` и
  включает HTML, стили, изображения и вложенные фреймы.
- Функция экспортирована из `browser_stealth.inspect` и описана в
  `docs/inspection.md`; при ошибках выбрасывает `InspectionError`.
- Ограничение: видео, аудио и lazy-load галереи в MHTML не попадают.

### nodriver: надёжный поиск поля ввода

- Основной поиск идёт через `Tab.select()` по CSS-селектору.
- Если `select()` вернул `None` или выбросил исключение, используется
  `Tab.find()` как fallback для поиска по видимому тексту.
- Исправление применено в `_async_type_nodriver()` и `_cdp_native_paste()`
  (ISSUE-20261119-BSTE).

### nodriver: переподключение к уже запущенному Chromium

- `launch_nodriver()` и `nodriver_session()` получили `auto_reattach=True`.
- `discover_active_cdp_endpoint(profile_dir)` читает порт из `DevToolsActivePort`
  в корне профиля и в `Default/`, затем при блокировке профиля ищет процесс
  Chromium через `Win32_Process` (Windows) или `ps` (POSIX) по
  `--remote-debugging-port` и `--user-data-dir`.
- Найденный эндпоинт проверяется HTTP-запросом к `/json/version` в обход
  локальных прокси.
- При переподключении сессия закрывает только CDP-соединение и не завершает
  чужой процесс Chromium; `auto_reattach=False` возвращает прежний запуск.
- После подключения закрываются лишние пустые вкладки (`about:blank`,
  `chrome://newtab`), а основная рабочая страница сохраняется.

### Graceful detach и диагностика соединения

- Новый модуль `browser_stealth.connection`.
- `detach_for_restart(browser)` закрывает WebSocket и помечает сессию
  отвязанной, не вызывая `browser.stop()`: окно Chromium переживает рестарт
  управляющего процесса.
- `extract_cdp_endpoint(browser)` возвращает `host` и `port` для повторного
  подключения.
- `check_browser_alive()` корректно проверяет и локальный процесс, и внешнее
  CDP-подключение, где `browser._process is None`.
- Добавлены `is_ws_closed`, `is_browser_connection_error`,
  `get_browser_main_tab` и `ping_browser_tab` для диагностики падений
  Renderer Crash и разрывов WebSocket.

### Кроссплатформенный поиск браузера и UNC-профили

- `discover_browser_executable()` ищет Chrome, Chrome x86, Edge/EdgeCore,
  Yandex Browser и Brave в стандартных каталогах Windows, Linux и macOS.
- `resolve_profile_dir()` перенаправляет UNC-профили Windows (`\\server\share`)
  в `%LOCALAPPDATA%/browser-stealth`, предотвращая сбои SQLite/LevelDB.
- `launch_nodriver()` и `ChromiumProcessManager` используют эти функции
  автоматически.

### Сетевое окружение: No-Proxy Guard

- Новый `browser_stealth.env` с `ensure_local_no_proxy()`.
- Функция добавляет `127.0.0.1`, `localhost` и `::1` в `NO_PROXY` и `no_proxy`,
  сохраняя существующие записи.
- `launch_nodriver()` и `ChromiumProcessManager.launch()` вызывают защиту до
  поиска CDP и запуска браузера, поэтому VPN и корпоративный прокси больше не
  перехватывают локальный WebSocket.

### Controlled inputs: React/Vue/Angular

- Добавлены `safe_dom_insert_text()` и алиас `async_safe_insert_text()`.
- Вставка использует дескриптор `value` из прототипа и отправляет
  `beforeinput` с `insertFromPaste`, `input` и `change`.
- `async_type_text()` получил `react_fallback=True`: после посимвольного ввода
  выполняется DOM-сверка controlled input; флаг можно отключить.

### Каскадный поиск и диагностика

- `inspect.async_find_cascade()` проверяет все CSS-селекторы одним
  `document.querySelector` и получает Element только для сработавшего варианта.
- Текстовые маркеры ищутся через `safe_find` без обхода кросс-доменных iframe.
- `inspect.audit_selectors()` (Selector Doctor) возвращает `ok`, `fallback` или
  `missing` с latency в миллисекундах.
- `inspect.collect_page_failure_context()` собирает URL, заголовок, h1,
  модалки, капчу, архивный маркер и сниппет текста.
- MHTML можно получить сырыми байтами через
  `inspect.capture_page_snapshot_mhtml()`.

### Формы и графическая капча

- Новый `browser_stealth.forms`: `extract_form_questions()` и `fill_form()`
  для Google Forms, Яндекс.Форм, Typeform, Tally и обычных HTML-форм.
- Поддерживаются типы `text`, `textarea`, `choice`, `number`, `select`,
  обязательность, кастомные `[role="radio"]` и согласия на обработку ПД.
- Новый `browser_stealth.captcha`: Canvas-снимок капчи без повторного
  HTTP-запроса, `detect_hh_captcha`, `save_captcha_snapshot` и
  `wait_for_manual_captcha_resolution` для HITL.

### Релизная инфраструктура

- Версия поднята до `0.4.0` в `pyproject.toml`, `__version__` и `uv.lock`.
- Новых обязательных зависимостей нет.

## Установка

```bash
pip install browser-stealth==0.4.0
```

Дополнительные компоненты:

```bash
pip install "browser-stealth[testing,fingerprint,redis]==0.4.0"
```

## Совместимость

Несовместимых изменений публичного API не заявлено. `bounds` в
`generate_tap()` — необязательный параметр: без него поведение прежнее.
Чтобы защитить тап по компактному элементу, границы нужно передать явно;
высокоуровневый `async_touch_tap()` пока их не пробрасывает. WindMouse теперь
не пересекает цель по осям движения, поэтому финальный участок траектории
может быть прямее, чем в `0.3.0`.

`auto_reattach=True` меняет сценарий для занятого профиля: вместо повторного
запуска библиотека подключается к существующему окну. Если это не нужно,
передайте `auto_reattach=False`. Сессия, подключённая к чужому Chromium, при
выходе закрывает только CDP-соединение и не завершает браузер.

`resolve_profile_dir()` теперь возвращает абсолютный путь, а UNC-профили
перенаправляет на локальный диск. `detach_for_restart()` — асинхронная
функция; после неё сессия не должна вызывать `browser.stop()` повторно.

`react_fallback=True` — новое поведение по умолчанию для `async_type_text()`:
после набора выполняется DOM-сверка. Она не должна менять корректно введённый
текст; при необходимости отключите её через `react_fallback=False`.
`async_find_cascade()` возвращает `(element, matched_by)`, а не один элемент.

## Проверки

- `pytest tests/unit`: `458 passed`.
- `mypy src/browser_stealth`: 0 ошибок (109 файлов).
- `ruff check` / `ruff format --check`: чисто.
- Дополнительно: 10 000 seed исходной геометрии и 500 случайных маршрутов
  WindMouse без выхода за цель.

**Full Changelog**: https://github.com/Chu4hel/browser-stealth/compare/v0.3.0...v0.4.0
