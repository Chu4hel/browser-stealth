# Issue 03: Реалистичная эмуляция геометрии окна и системной панели задач в Headless режиме

## Описание
В headless-режиме Chromium (даже при использовании `--headless=new`) внутренние метрики размеров окна и экрана часто имеют идеальные «квадратные» или синтетические соотношения, которые не встречаются у реальных пользователей десктопных ОС.

## Уязвимость для антифрод-систем
1. **Тождество `outerHeight === innerHeight`:**
   - В обычном браузере `window.outerHeight` всегда больше `window.innerHeight` на высоту системного заголовка окна, строки вкладок и адресной строки (обычно разница составляет 70–95 пикселей).
   - В headless-режиме без оконного менеджера браузер возвращает `window.outerHeight === window.innerHeight` и `window.outerWidth === window.innerWidth`, что является однозначным триггером headless-скрипта для CreepJS и Pixelscan.
2. **Отсутствие системной панели задач (`screen.availHeight === screen.height`):**
   - У живого пользователя Windows почти всегда включена панель задач (Taskbar снизу, высотой около 40–48 px), поэтому `screen.availHeight < screen.height` (например, при `1920x1080` доступная высота `availHeight = 1040`).
   - На macOS присутствует верхняя строка меню (25 px) и Dock (dock offset).
   - Тождество `availHeight === height` и `availWidth === width` означает отсутствие GUI/Taskbar или полноэкранный режим Kiosk.

## Требуемые изменения
1. **Эмуляция оконной рамки:**
   - В скриптах маскировки геометрии экрана рассчитывать:
     - `window.outerHeight = window.innerHeight + random.randint(75, 90)`
     - `window.outerWidth = window.innerWidth + random.randint(0, 16)`
2. **Эмуляция системной панели задач в зависимости от ОС:**
   - Для Windows: `screen.availHeight = screen.height - 40`, `screen.availTop = 0`.
   - Для macOS: `screen.availHeight = screen.height - 25`, `screen.availTop = 25`.
   - Защитить свойства от прямого переопределения и инспекции прототипов `Screen.prototype`.
3. **Тестирование:**
   - Добавить юнит-тесты на проверку `screen.availHeight < screen.height` и `window.outerHeight > window.innerHeight`.
