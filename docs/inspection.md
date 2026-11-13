# Инспекция страницы (inspect)

Модуль `browser_stealth.inspect` даёт ИИ-агенту и разработчику «глаза» на
антидетект-браузер: компактное описание того, что находится на странице, без
передачи сырого HTML. Все функции только читают состояние — клики и ввод
остаются за [`humanize`](humanize.md), чтобы события были настоящими
(`isTrusted=true`) и не выдавали автоматизацию.

```python
from browser_stealth import inspect, nodriver_session

async with nodriver_session() as browser:
    tab = await browser.get("https://example.com/login")
    page = await inspect.snapshot(tab, max_nodes=50)
    buttons = await inspect.find(tab, role="button", text="Войти")
```

## Зачем не `outerHTML`

Полный HTML занимает десятки тысяч токенов, содержит скрипты, стили и служебную
разметку. Для агента полезны только интерактивные и структурные узлы: роль,
доступное имя, селектор, координаты и видимость. Такой снимок в 50–200 раз
компактнее и стабильнее: модель оперирует кнопками и полями, а не дивами.

## `snapshot`

```python
page = await inspect.snapshot(
    tab,
    max_nodes=200,       # ограничение размера ответа
    include_hidden=False, # невидимые элементы по умолчанию скрыты
    text_limit=120,       # обрезка текста узла
)
```

Возвращает словарь:

```python
{
    "url": "https://example.com/login",
    "title": "Вход",
    "viewport": {"width": 1280, "height": 720, "scrollX": 0, "scrollY": 0},
    "total": 2,
    "truncated": False,
    "nodes": [
        {
            "tag": "button",
            "role": "button",
            "name": "Войти",
            "text": "Войти",
            "selector": "#login",
            "attrs": {"id": "login", "type": "submit"},
            "box": [940, 512, 120, 40],
            "visible": True,
            "enabled": True,
        },
    ],
}
```

* `role` — явная роль (`role=`) или вычисленная по тегу и `type`.
* `name` — доступное имя: `aria-label`, `alt`, `title`, `placeholder`,
  подпись кнопки или текст ссылки.
* `selector` — CSS-путь: `#id`, если он безопасен, иначе цепочка тегов с
  `:nth-child` до 4 уровней. Его можно сразу передать в `tab.select` или
  `humanize.async_click(tab, selector=...)`.
* `box` — `[x, y, width, height]` в координатах viewport.
* `visible`, `enabled` — видимость и доступность элемента.

В снимок попадают ссылки, кнопки, поля ввода, `select`, `textarea`, `summary`,
`label`, элементы с `role`/`onclick`/`contenteditable`, заголовки `h1`–`h6` и
`iframe[src]`.

## `find`

Поиск по тексту, роли или CSS-селектору. Текст сравнивается без учёта регистра
по `name` и `text`; `exact=True` требует полного совпадения.

```python
buttons = await inspect.find(tab, role="button", text="Войти")
await async_click(tab, selector=buttons[0]["selector"])

links = await inspect.find(tab, selector="nav", text="Каталог", limit=5)
```

Без критериев (`text`, `role`, `selector`) функция поднимает `ValueError` —
для полного обзора используйте `snapshot`.

## `screenshot`

```python
png_path = await inspect.screenshot(tab, "artifacts/login.png")
full = await inspect.screenshot(tab, "artifacts/full.jpeg", full_page=True, image_format="jpeg")
```

Снимок делается штатным CDP-методом `Page.captureScreenshot`, не меняет
фингерпринт страницы и полезен, когда семантика не описывает вёрстку:
изображения, canvas, сложные сетки. Для визуальной проверки лучше запускать
браузер в headed-режиме: `headless=True` меняет поверхность фингерпринта.

## `frames`

```python
tree = await inspect.frames(tab)
for frame in tree:
    print(frame["depth"], frame["url"], frame["security_origin"])
```

Возвращает плоское дерево фреймов с `id`, `parent_id`, `url`, `name`,
`security_origin` и `depth`. Обход содержимого фреймов не выполняется: как и в
`safe_find`, кросс-доменные iframe не опрашиваются, чтобы не ловить CDP-ошибку
`'DOM.getDocument' wasn't found`. Наличие `depth > 0` подсказывает агенту, что
часть интерфейса (оплата, вход, виджет) находится за пределами основного
документа.

## Ошибки

Все функции поднимают `browser_stealth.InspectionError`, если вкладка
недоступна, CDP-вызов завершился ошибкой или вернул неожиданный формат. Это
позволяет агенту отличить «на странице нет кнопки» от «браузер умер».
