Релиз `0.4.0`: два точечных исправления поведения, новый инструмент инспекции,
переподключение к уже запущенному Chromium и устойчивость сессии при рестарте.
Ветка закрывает занос WindMouse в соседний пункт компактного меню, чинит поиск
поля ввода в nodriver, добавляет сохранение страницы в MHTML, автоматический
reattach по CDP и graceful detach без закрытия окна браузера.

## Основные изменения

- **WindMouse (`humanize`)**: длина шага у финиша ограничивается оставшимся
  расстоянием, а покоординатный запрет не позволяет траектории пересечь цель
  по осям движения. Устранён занос курсора из пункта «Скрыть эту вакансию»
  в соседний пункт «Пожаловаться» (ISSUE-20261120-B7A1).
- **Тач-тап (`humanize`)**: `TouchGestureGenerator.generate_tap()` принимает
  необязательный `bounds`; при его передаче микросдвиг пальца остаётся внутри
  целевого прямоугольника. Без `bounds` поведение прежнее.
- **Инспекция (`inspect`)**: добавлена `save_mhtml()` для вкладки nodriver —
  сохранение через CDP `Page.captureSnapshot(format="mhtml")` в один файл с HTML, стилями,
  изображениями и вложенными фреймами. Функция экспортирована из
  `browser_stealth.inspect`, документирована и выбрасывает `InspectionError`
  при сбоях.
- **nodriver**: поиск поля ввода теперь начинается с `Tab.select()` по
  CSS-селектору, а `Tab.find()` используется как fallback. Исправление
  применено в `_async_type_nodriver()` и `_cdp_native_paste()`
  (ISSUE-20261119-BSTE).
- **Переподключение (`launchers`)**: `launch_nodriver()` и `nodriver_session()`
  получили `auto_reattach=True`. Новая `discover_active_cdp_endpoint()` читает
  порт из `DevToolsActivePort` в корне профиля и `Default/`, затем при
  блокировке профиля сканирует `Win32_Process` (Windows) или `ps` (POSIX)
  по `--remote-debugging-port` и `--user-data-dir`. Кандидат проверяется
  HTTP-запросом к `/json/version` в обход локальных прокси. Сессия,
  подключённая к чужому Chromium, при выходе закрывает только CDP-соединение.
- **Переподключение и вкладки (`launchers`)**: после reattach закрываются
  лишние пустые вкладки (`about:blank`, `chrome://newtab`), рабочая страница
  сохраняется.
- **Graceful detach (`connection`)**: новый модуль `browser_stealth.connection`.
  `detach_for_restart(browser)` закрывает WebSocket и помечает сессию
  отвязанной без `browser.stop()`; `extract_cdp_endpoint(browser)` возвращает
  `host`/`port` для повторного подключения. Добавлены `check_browser_alive`,
  `is_ws_closed`, `is_browser_connection_error`, `get_browser_main_tab` и
  `ping_browser_tab`.
- **Поиск браузера и UNC (`launchers`)**: `discover_browser_executable()` ищет
  Chrome, Chrome x86, Edge/EdgeCore, Yandex Browser и Brave в стандартных
  каталогах Windows, Linux и macOS. `resolve_profile_dir()` перенаправляет
  UNC-профили Windows в `%LOCALAPPDATA%/browser-stealth`.
- **No-Proxy Guard (`env`)**: новый `ensure_local_no_proxy()` добавляет
  `127.0.0.1`, `localhost`, `::1` в `NO_PROXY`/`no_proxy` и вызывается из
  `launch_nodriver()` и `ChromiumProcessManager.launch()`.
- **Controlled inputs (`humanize`)**: `safe_dom_insert_text()` и
  `async_safe_insert_text()` используют нативный setter, `beforeinput`,
  `input` и `change`. `async_type_text()` получил `react_fallback=True`.
- **Каскад и диагностика (`inspect`)**: `async_find_cascade()` выполняет
  атомарный JS-поиск, `audit_selectors()` даёт отчёт Selector Doctor,
  `collect_page_failure_context()` собирает контекст сбоя, а
  `capture_page_snapshot_mhtml()` возвращает сырой MHTML.
- **Формы (`forms`)**: `extract_form_questions()` и `fill_form()` для Google
  Forms, Яндекс.Форм, Typeform, Tally и обычных форм; поддержаны `text`,
  `textarea`, `choice`, `number`, `select` и согласия на обработку ПД.
- **Капча (`captcha`)**: Canvas-снимок без повторного HTTP-запроса,
  `detect_hh_captcha`, `save_captcha_snapshot` и
  `wait_for_manual_captcha_resolution` для HITL.
- **Релиз**: версия поднята до `0.4.0` в `pyproject.toml`, `__version__`
  и `uv.lock`; новых обязательных зависимостей нет.

## Проверки

- `pytest tests/unit`: 458 passed
- `mypy src/browser_stealth`: 0 ошибок (109 файлов)
- `ruff check` / `ruff format --check`: чисто
- Дополнительно проверено: 10 000 seed исходной геометрии и 500 случайных
  маршрутов WindMouse без выхода за цель
- E2E-тесты локально не запускались: изменения в `inspect` покрыты unit- и
  e2e-тестами, запуск остаётся за CI

## Риски и совместимость

Несовместимых изменений публичного API не заявлено. `bounds` в
`generate_tap()` — необязательный параметр, поэтому существующий код сохраняет
прежнее поведение. Для защиты тапа по компактному элементу границы нужно
передавать явно: высокоуровневый `async_touch_tap()` пока не пробрасывает
`bounds`. WindMouse больше не пересекает цель по осям движения, из-за чего
финальный участок траектории может быть прямее, чем в `0.3.0`. MHTML не
включает видео, аудио и lazy-load галереи.

`auto_reattach=True` меняет поведение по умолчанию для занятого профиля:
вместо запуска нового процесса библиотека подключается к существующему окну.
Отключается через `auto_reattach=False`. Переподключённая сессия не завершает
чужой Chromium при выходе; закрывается только CDP-соединение. Если эндпоинт
найден, но подключение не удалось, выбрасывается `RuntimeError` с адресом
эндпоинта, а не выполняется повторный запуск поверх занятого профиля.

`resolve_profile_dir()` теперь всегда возвращает абсолютный путь, а UNC-профили
перенаправляет в локальный `%LOCALAPPDATA%`. `detach_for_restart()` асинхронный:
после него нельзя вызывать `browser.stop()`, иначе окно Chromium закроется.
Автопоиск браузера может выбрать установленный Chrome/Edge/Yandex/Brave, если
`browser_executable_path` не задан явно. `react_fallback=True` включает
финальную DOM-сверку controlled input; для чистого посимвольного ввода
передайте `react_fallback=False`. `async_find_cascade()` возвращает кортеж
`(element, matched_by)`, а `captcha_snapshot()` отдаёт PNG-байты через Canvas,
поэтому для неё не нужен повторный HTTP-запрос.

## Связанные issues

- ISSUE-20261120-B7A1 — занос WindMouse в пункт «Пожаловаться».
- ISSUE-20261119-BSTE — поиск поля ввода в nodriver через `find` вместо
  `select`.

**Full Changelog**: https://github.com/Chu4hel/browser-stealth/compare/v0.3.0...v0.4.0
