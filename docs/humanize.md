# Биомеханика и действия человека (humanize)

Модуль `browser_stealth.humanize` предназначен для генерации физиологически достоверных действий человека при автоматизации браузеров.

---

## 1. Модель движения мыши WindMouse (`WindMouseGenerator`)

В отличие от простых прямых линий или примитивных сплайнов, `WindMouseGenerator` моделирует физику реальной кисти руки:
* **Гравитация (`gravity`):** Сила притяжения курсора к целевой точке.
* **Мышечный шум (`wind`):** Случайные колебания и микродрожания мышц руки.
* **Инерция и максимальный шаг (`max_step`):** Ограничение максимальной скорости перемещения.
* **Зона замедления (`target_area`):** Физиологическое притормаживание кисти при приближении к элементу.

```python
from browser_stealth.humanize.math_utils import WindMouseGenerator

generator = WindMouseGenerator(
    gravity=9.0,
    wind=3.0,
    max_step=12.0,
    target_area=8.0,
)

# Генерация точек траектории с задержками между ними
start = (100, 100)
end = (800, 500)
trajectory = generator.generate(start, end)

for x, y, delay in trajectory:
    # x, y - экранные координаты
    # delay - микропауза перед следующим шагом (в секундах)
    pass
```

---

## 2. Кубические кривые Безье (`BezierCurveGenerator`)

Альтернативный генератор гладких сглаженных кривых с динамическим разбросом контрольных точек.

```python
from browser_stealth.humanize.math_utils import BezierCurveGenerator

bezier = BezierCurveGenerator(deviation=50, num_points=35)
points = bezier.generate((50, 50), (600, 400))
```

---

## 3. Человекоподобный ввод текста (`type_text`, `async_type_text`)

Симулирует реальный набор текста человеком:
* Переменная пауза между клавишами по Гауссову распределению (`JitterDelayGenerator`).
* Случайные опечатки на соседних клавишах раскладки клавиатуры (`KeyboardTypoGenerator`).
* Естественная реакция на опечатку: пауза осознания, стирание клавишей `Backspace` и ввод верного символа.

```python
from browser_stealth.humanize.actions import async_type_text

# Асинхронный набор текста в Playwright / nodriver
await async_type_text(
    target=page,
    selector="input[name='q']",
    text="Купить авиабилеты онлайн",
    with_typos=True,
    typo_chance=0.08,
)
```

---

## 4. Мобильные тач-жесты (`TouchGestureGenerator`)

Поддержка мобильной автоматизации:
* `async_touch_tap` — тап пальцем с учетом пятна контакта и микросмещения.
* `async_touch_swipe` — свайп по экрану с ускорением и замедлением (инерция тачпада).

```python
from browser_stealth.humanize.actions import async_touch_swipe, async_touch_tap

# Тап пальцем по экрану
await async_touch_tap(page, (200, 450))

# Свайп снизу вверх (скролл ленты)
await async_touch_swipe(page, start=(250, 700), end=(250, 200), duration=0.6)
```

---

## 5. Обход Cloudflare Turnstile (`solve_cf_turnstile`)

Интеллектуальный механизм обнаружения и решения интерактивных капч Cloudflare:
1. Поиск iframe с виджетом `challenges.cloudflare.com`.
2. Ожидание готовности чекбокса.
3. Плавное наведение курсора через `WindMouseGenerator`.
4. Естественный клик и подтверждение прохождения проверки (`is_cf_turnstile_solved`).

```python
from browser_stealth.humanize.turnstile import solve_cf_turnstile

# Решение Turnstile на странице
solved = await solve_cf_turnstile(page, timeout=15.0)
if solved:
    print("Turnstile успешно пройден!")
```
