# Автотестирование и моки (testing)

Модуль `browser_stealth.testing` содержит инструменты для тестирования скриптов автоматизации без необходимости поднимать внешнюю инфраструктуру.

---

## 1. Локальный тестовый сервер (`LocalTestServer`)

Быстрый легковесный HTTP-сервер для изолированного тестирования страниц и API в рамках тестов:

```python
from browser_stealth.testing.server import LocalTestServer

with LocalTestServer() as server:
    # Публикация статического HTML
    url = server.serve_html("/login", "<h1>Вход в систему</h1><button id='btn'>OK</button>")
    
    # Теперь можно переходить по url в браузере или через HTTP-клиент
    print("Адрес тестовой страницы:", url)
```

---

## 2. Моки браузерных объектов

Позволяют тестировать пайплайны обработки без запуска тяжелых бинарников браузеров:
* `MockPlaywrightPage` — мок объекта страницы Playwright.
* `MockNodriverTab` — мок вкладки nodriver.
* `MockSeleniumDriver` — мок Selenium WebDriver.

```python
from browser_stealth.testing.mocks.playwright import MockPlaywrightPage

mock_page = MockPlaywrightPage()
mock_page.set_content("<div class='item'>Данные</div>")
```

---

## 3. Спецификация экстракций (`assert_extraction_complete`)

Утилиты проверки качества извлеченных данных:

```python
from browser_stealth.testing.assertions import (
    assert_extraction_complete,
    assert_schema_match,
    assert_valid_url,
)

data = {"title": "Товар", "price": 1200, "url": "https://example.com/p1"}

assert_extraction_complete(data, required_fields=["title", "price", "url"])
assert_valid_url(data["url"])
```

---

## 4. Готовые pytest-фикстуры (`browser_stealth.testing.fixtures`)

Модуль поставляется как pytest-плагин и требует `pytest` — установите extra:

```bash
uv add "browser-stealth[testing]"
```

Подключение в `conftest.py` проекта:

```python
pytest_plugins = ["browser_stealth.testing.fixtures"]
```

Доступные фикстуры: `local_test_server`, `live_browser_session`,
`html_snapshot_recorder`, `mock_nodriver_tab`, `mock_playwright_page`,
`mock_selenium_driver`. Модуль также регистрирует маркеры `e2e` и `heavy`
через `pytest_configure`.

Сетевые тесты помечены `e2e` (часть из них дополнительно `heavy`), поэтому их
можно отделить от быстрых:

```bash
uv run pytest -m "not e2e"   # быстрые тесты
uv run pytest -m e2e        # сетевые E2E-стенды
```

В CI эти наборы запускаются отдельными job: `test` — без e2e на матрице ОС и
Python, `e2e` — один прогон на Linux.

---

## 5. Снапшоты HTML (`SnapshotRecorder`, `use_html_snapshot`)

`SnapshotRecorder` сохраняет/читает HTML страницы и избавляет тесты от похода в сеть:

```python
from browser_stealth.testing import SnapshotRecorder

recorder = SnapshotRecorder("tests/snapshots")
path = recorder.save("login", "<html><body>...</body></html>")
html = recorder.load("login")
```

`use_html_snapshot` — контекстный менеджер и декоратор, который подменяет
страницу мок-объектом:

```python
from browser_stealth.testing import use_html_snapshot

with use_html_snapshot("login", as_mock="nodriver") as page:
    ...

with use_html_snapshot("login", as_mock="playwright", record=True, fetcher=fetch_page) as page:
    ...  # запись и обновление снапшота
```

Параметр `as_mock` принимает `raw`, `nodriver`, `playwright` или `selenium`.

---

## 6. Запись действий (`DOMActionRecorder`)

Регистратор показывает в странице плавающий HUD с чек-листом, собирает клики,
ввод, скроллы и мутации DOM, а затем отдаёт структурированный отчёт:

```python
from browser_stealth.testing import DOMActionRecorder

recorder = DOMActionRecorder(
    checklist_items=[{"id": "login", "label": "Войти в аккаунт"}],
    widget_title="Запись сценария",
)
await recorder.inject(tab)
report = await recorder.wait_for_finish(tab, timeout=120)
print(report.actions)
```

`inject` возвращает `bool` — удалось ли внедрить перехватчик; `poll` забирает
накопленные действия без ожидания.

---

## 7. Сессия живого браузера (`LiveBrowserSession`)

Изолированный профиль во временном каталоге с гарантированным уничтожением
процессов и очисткой:

```python
from browser_stealth.testing import LiveBrowserSession

with LiveBrowserSession(browser_name="chromium") as session:
    print(session.user_data_dir)
```

Параметры: `user_data_dir`, `auto_cleanup_dir`, `keep_profile_on_failure`
(сохранить профиль упавшего теста для отладки).
