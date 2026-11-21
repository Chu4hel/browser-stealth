# Манифест ИИ: browser_stealth

Пакет антидетекта и человекоподобной автоматизации браузера для Playwright,
nodriver и Selenium. Корневые правила репозитория находятся в `AGENTS.md`.

## Публичный API

- Корневые функции и классы экспортируются из `browser_stealth/__init__.py`.
- Для каждой предметной области есть подпакет:
  - `antidetect` — конфигурация, флаги Chromium и JS-инъекции;
  - `fingerprint` — модели и генерация согласованного фингерпринта;
  - `humanize` — мышь, клавиатура, тач, `safe_find` и `typo`;
  - `launchers` — запуск Playwright, nodriver, Selenium, camoufox и BiDi;
  - `profiles` — профили, гигиена, ротация и прогрев;
  - `proxy` — модели, парсер, адаптеры и хранилище секретов;
  - `concurrency` — очереди, пулы, лимитеры и reaper простоя;
  - `inspect` — read-only снимки DOM, поиск, фреймы и диагностика;
  - `testing` — фикстуры и моки для тестов потребителей.
- Модули `env`, `forms` и `captcha` решают точечные задачи верхнего уровня.

## Соглашения

- Python >= 3.11, типизация обязательна: `mypy --strict`.
- Docstring — Google Style с `Args:`, `Returns:` и `Raises:`.
- Логирование — только `browser_stealth.logging.get_logger`.
- Файловые операции — через `browser_stealth.fs`, секреты — через `chutils`.
- Новые зависимости добавляются только при явной необходимости.
- Комментарии и пользовательские сообщения — на русском языке.
- Правки минимальны и локальны; поведение покрывается тестом в `tests/unit/`.

## Проверки

```bash
uv run pytest tests/unit -q
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/browser_stealth
uv run chutils dev ai-lint --strict
```

## Важные инварианты

- `launch_nodriver()` и `ChromiumProcessManager.launch()` вызывают
  `ensure_local_no_proxy()` до подключения к CDP.
- `async_type_text()` по умолчанию использует `react_fallback=True`.
- `inspect.async_find_cascade()` возвращает `(element, matched_by)`.
- `inspect.collect_page_failure_context()` не выбрасывает ошибки браузера и
  всегда возвращает словарь.
- `captcha_snapshot()` читает уже загруженное изображение через Canvas и не
  делает повторный HTTP-запрос.
