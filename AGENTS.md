# AGENTS.md

Манифест для ИИ-агентов, работающих в репозитории **browser-stealth**.

## Назначение проекта

Библиотека антидетекта и человеко-подобной автоматизации браузера для Playwright,
nodriver и Selenium: маскировка фингерпринта, эмуляция ввода (WindMouse), прогрев
профилей и интеграция с экосистемой chutils.

## Стек и окружение

- Python >= 3.11; управление зависимостями — `uv` (`uv.lock`).
- Обязательная зависимость: `pydantic>=2.10`; браузерные бэкенды — опциональные
  extra-группы (`playwright`, `nodriver`, `selenium`, `camoufox`, `bidi`, `crypto`).
- Инструменты разработки: `ruff`, `mypy` (strict), `pytest`, `chutils dev ai-lint`.

## Команды

```bash
uv sync                                   # установить зависимости разработки
uv run pytest tests/unit -q               # быстрые юнит-тесты
uv run ruff check src tests               # линтер и форматирование
uv run ruff format --check src tests
uv run mypy src/browser_stealth           # типы (strict)
uv run chutils dev ai-lint --soft-mode    # аудит AI-готовности
uv run chutils dev sync-env               # синхронизировать .env с .env.example
```

## Структура

- `src/browser_stealth/antidetect/` — конфигурация, флаги Chromium, JS-инъекции
  (крупные JS-шаблоны вынесены в `_scripts_*.py`), работа с мобильными эмуляциями.
- `src/browser_stealth/fingerprint/` — модели фингерпринта, процедурная генерация,
  согласованность ОС/GPU/шрифтов.
- `src/browser_stealth/humanize/` — человекоподобные действия: мышь, клавиатура,
  тач, безопасный поиск элементов (`safe_find.py`), движок ввода (`_typing_engine.py`).
- `src/browser_stealth/launchers/` — фабрики запуска Playwright, nodriver, Selenium,
  camoufox и BiDi.
- `src/browser_stealth/profiles/` — профили, гигиена, ротация и прогрев.
- `src/browser_stealth/proxy/` — модели, парсер, адаптеры, кэш и хранилище секретов.
- `src/browser_stealth/inspect/` — read-only инспекция страницы: снимок DOM, поиск
  элементов, дерево фреймов и снимки экрана для ИИ-агентов и отладки.
- `src/browser_stealth/testing/` — фикстуры и моки для тестов потребителей.
- `tests/unit/` — быстрые тесты без реального браузера; E2E помечены отдельно.
- `docs/` — документация MkDocs (`mkdocs.yml`).

## Соглашения

- Публичный API экспортируется через `__all__` в `__init__.py` затронутого пакета.
- Docstring — Google Style с разделами `Args:`, `Returns:`, `Raises:`.
- Логирование — только `browser_stealth.logging.get_logger`, без `print`.
- Файловые операции — через `browser_stealth.fs` (обёртка над `chutils.fs`).
- Секреты и переменные окружения — через `chutils` (`SecretManager`, `EnvProvider`),
  без прямого чтения `os.environ` в новом коде.
- Типизация обязательна: `mypy --strict` должен проходить без новых `type: ignore`.
- Комментарии и сообщения — на русском языке, как в существующем коде.

## Правила изменений

- Правки делаются минимальными и локальными; новые зависимости не добавляются без
  явной необходимости (проверяйте, что нужное уже есть в `chutils`).
- Любая логика должна сопровождаться тестом в `tests/unit/`, если она не покрыта.
- Перед коммитом: `ruff check`, `ruff format --check`, `mypy`, `pytest tests/unit`.
- Коммиты атомарные, сообщения в стиле Conventional Commits на русском языке.
