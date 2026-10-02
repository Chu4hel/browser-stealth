# Быстрый старт

## Установка

Библиотека разделена на опциональные группы зависимостей в зависимости от используемого браузерного стека.

```bash
# Базовая установка (математические генераторы WindMouse, парсер прокси, модели)
pip install browser-stealth

# Для работы с Playwright
pip install "browser-stealth[playwright]"

# Для работы с nodriver
pip install "browser-stealth[nodriver]"

# Для работы с Selenium
pip install "browser-stealth[selenium]"

# Для работы с Camoufox (Firefox-антидетект)
pip install "browser-stealth[camoufox]"

# Установка всех интеграций
pip install "browser-stealth[all]"
```

---

## 1. Запуск nodriver с маскировкой

`nodriver` запускает Chromium напрямую через протокол Chrome DevTools (CDP), минуя WebDriver-бинарники.

```python
import asyncio
from browser_stealth import launch_nodriver, nodriver_session
from browser_stealth.humanize.actions import async_click, async_type_text

async def main():
    async with nodriver_session(headless=False) as browser:
        page = await browser.get("https://bot.sannysoft.com")
        
        # Эмуляция естественного клика
        await async_click(page, "#some-button", use_windmouse=True)
        
        # Биомеханический ввод текста с опечатками
        await async_type_text(page, "#input-field", "Hello world!", with_typos=True)
        
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 2. Использование с Playwright

```python
import asyncio
from playwright.async_api import async_playwright
from browser_stealth import AntidetectConfig, apply_antidetect_playwright
from browser_stealth.humanize.actions import async_click, async_type_text

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Применяем полную маскировку рантайма
        config = AntidetectConfig.preset_stealth_playwright()
        await apply_antidetect_playwright(page, config)

        await page.goto("https://nowecure.com")
        
        # Естественные действия
        await async_click(page, "button#login")
        await async_type_text(page, "input#email", "user@example.com")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 3. Использование с Selenium

```python
from selenium import webdriver
from browser_stealth import AntidetectConfig, apply_antidetect_selenium
from browser_stealth.humanize.actions import click, type_text

driver = webdriver.Chrome()

# Применяем CDP скрипты маскировки
config = AntidetectConfig.preset_stealth_selenium()
apply_antidetect_selenium(driver, config)

driver.get("https://bot.sannysoft.com")

# Синхронные человекоподобные действия
click(driver, "#submit-btn", use_windmouse=True)
type_text(driver, "#search-query", "Синхронный поиск", with_typos=True)

driver.quit()
```
