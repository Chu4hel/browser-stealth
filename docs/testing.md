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
