import math
import random
from typing import Literal, overload

from .typo import KeyboardTypoGenerator, TypoAction

__all__ = [
    "BezierCurveGenerator",
    "JitterDelayGenerator",
    "KeyboardTypoGenerator",
    "TypoAction",
    "WindMouseGenerator",
]


class WindMouseGenerator:
    """Генератор траекторий перемещения мыши на основе физической модели WindMouse (гравитация, ветер, инерция)."""

    def __init__(
        self,
        gravity: float = 9.0,
        wind: float = 3.0,
        min_wait: float = 0.002,
        max_wait: float = 0.005,
        max_step: float = 15.0,
        target_area: float = 8.0,
    ) -> None:
        """Инициализирует генератор WindMouse.

        Args:
            gravity: Сила притяжения курсора к целевой точке.
            wind: Величина случайного отклонения (ветра/мышечных микроколебаний).
            min_wait: Минимальная пауза между смещениями (в секундах).
            max_wait: Максимальная пауза между смещениями (в секундах).
            max_step: Максимальное расстояние одного шага (скорость).
            target_area: Радиус целевой зоны, при входе в которую уменьшается влияние ветра и падает скорость.
        """
        self.gravity = gravity
        self.wind = wind
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.max_step = max_step
        self.target_area = target_area

    @overload
    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        gravity: float | None = None,
        wind: float | None = None,
        min_wait: float | None = None,
        max_wait: float | None = None,
        max_step: float | None = None,
        target_area: float | None = None,
        *,
        with_delays: Literal[True] = ...,
    ) -> list[tuple[int, int, float]]: ...

    @overload
    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        gravity: float | None = None,
        wind: float | None = None,
        min_wait: float | None = None,
        max_wait: float | None = None,
        max_step: float | None = None,
        target_area: float | None = None,
        *,
        with_delays: Literal[False],
    ) -> list[tuple[int, int]]: ...

    @overload
    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        gravity: float | None = None,
        wind: float | None = None,
        min_wait: float | None = None,
        max_wait: float | None = None,
        max_step: float | None = None,
        target_area: float | None = None,
        *,
        with_delays: bool,
    ) -> list[tuple[int, int, float]] | list[tuple[int, int]]: ...

    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        gravity: float | None = None,
        wind: float | None = None,
        min_wait: float | None = None,
        max_wait: float | None = None,
        max_step: float | None = None,
        target_area: float | None = None,
        *,
        with_delays: bool = True,
    ) -> list[tuple[int, int, float]] | list[tuple[int, int]]:
        """Генерирует последовательность точек от start к end.

        Args:
            start: Начальные координаты (x, y).
            end: Конечные координаты (x, y).
            gravity: Переопределение силы гравитации.
            wind: Переопределение силы ветра.
            min_wait: Переопределение минимальной задержки шага.
            max_wait: Переопределение максимальной задержки шага.
            max_step: Переопределение максимального размера шага.
            target_area: Переопределение радиуса целевой зоны.
            with_delays: Если True, возвращает кортежи (x, y, delay). Если False, возвращает (x, y).

        Returns:
            Список точек пути с задержками или без них.
        """
        g = self.gravity if gravity is None else gravity
        w = self.wind if wind is None else wind
        min_w = self.min_wait if min_wait is None else min_wait
        max_w = self.max_wait if max_wait is None else max_wait
        max_s = self.max_step if max_step is None else max_step
        t_area = self.target_area if target_area is None else target_area

        start_x, start_y = start
        dest_x, dest_y = end

        if start_x == dest_x and start_y == dest_y:
            if with_delays:
                return [(dest_x, dest_y, random.uniform(min_w, max_w))]
            return [(dest_x, dest_y)]

        current_x, current_y = float(start_x), float(start_y)
        v_x, v_y = 0.0, 0.0
        w_x, w_y = 0.0, 0.0

        sqrt3 = math.sqrt(3.0)
        sqrt5 = math.sqrt(5.0)

        cur_gravity = g
        cur_wind = w

        max_iterations = 2000
        iteration = 0

        # Начальная точка траектории
        if with_delays:
            points_with_delay: list[tuple[int, int, float]] = [
                (start_x, start_y, random.uniform(min_w, max_w))
            ]
        else:
            points_no_delay: list[tuple[int, int]] = [(start_x, start_y)]

        while iteration < max_iterations:
            iteration += 1
            dist = math.hypot(dest_x - current_x, dest_y - current_y)
            if dist < 2.0:
                break

            # В целевой зоне снижаем воздействие случайного ветра, гравитации и скорости шага
            # для моделирования естественного притормаживания руки перед нажатием клавиши
            cur_max_s = max_s
            if dist < t_area:
                factor = dist / max(1.0, t_area)
                cur_wind = max(0.5, cur_wind * 0.8)
                cur_gravity = max(1.5, cur_gravity * 0.85)
                cur_max_s = max(2.0, max_s * factor)

            # Вектор случайного ветра (дрейф / мышечные микроколебания)
            w_x = w_x / sqrt3 + (random.random() * (cur_wind * 2.0 + 1.0) - cur_wind) / sqrt5
            w_y = w_y / sqrt5 + (random.random() * (cur_wind * 2.0 + 1.0) - cur_wind) / sqrt5

            # Сила гравитационного притяжения к цели
            v_x += w_x + cur_gravity * (dest_x - current_x) / dist
            v_y += w_y + cur_gravity * (dest_y - current_y) / dist

            # Ограничение максимальной скорости с динамическим затуханием
            v_mag = math.hypot(v_x, v_y)
            if v_mag > cur_max_s:
                v_clip = cur_max_s / 2.0 + random.random() * (cur_max_s / 2.0)
                v_x = (v_x / v_mag) * v_clip
                v_y = (v_y / v_mag) * v_clip

            # Не позволяем шагу проскочить цель: у финиша длина шага
            # ограничена оставшимся расстоянием, иначе инерция WindMouse
            # выносит курсор в соседний пункт компактного меню
            # (ISSUE-20261120-B7A1).
            step_len = math.hypot(v_x, v_y)
            if step_len > dist:
                scale = dist / step_len
                v_x *= scale
                v_y *= scale

            current_x += v_x
            current_y += v_y

            # Не выпускаем курсор за цель по осям движения: боковой снос
            # не должен позволить обойти точку и уйти в соседний пункт
            # компактного меню (ISSUE-20261120-B7A1).
            if dest_x > start_x:
                current_x = min(current_x, float(dest_x))
            elif dest_x < start_x:
                current_x = max(current_x, float(dest_x))
            if dest_y > start_y:
                current_y = min(current_y, float(dest_y))
            elif dest_y < start_y:
                current_y = max(current_y, float(dest_y))

            pt_x = round(current_x)
            pt_y = round(current_y)

            # Исключаем добавление дублирующихся подряд экранных координат
            if with_delays:
                last_x, last_y = points_with_delay[-1][0], points_with_delay[-1][1]
                if (pt_x, pt_y) != (last_x, last_y):
                    points_with_delay.append((pt_x, pt_y, random.uniform(min_w, max_w)))
            else:
                last_x, last_y = points_no_delay[-1][0], points_no_delay[-1][1]
                if (pt_x, pt_y) != (last_x, last_y):
                    points_no_delay.append((pt_x, pt_y))

        # Гарантируем попадание в конечную точку
        post_delay = random.uniform(0.04, 0.12)
        if with_delays:
            if (points_with_delay[-1][0], points_with_delay[-1][1]) != (dest_x, dest_y):
                points_with_delay.append((dest_x, dest_y, post_delay))
            else:
                points_with_delay[-1] = (dest_x, dest_y, post_delay)
            return points_with_delay

        if (points_no_delay[-1][0], points_no_delay[-1][1]) != (dest_x, dest_y):
            points_no_delay.append((dest_x, dest_y))
        return points_no_delay

    def generate_points(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        gravity: float | None = None,
        wind: float | None = None,
        max_step: float | None = None,
        target_area: float | None = None,
    ) -> list[tuple[int, int]]:
        """Генерирует последовательность координат (x, y) без задержек.

        Args:
            start: Начальные координаты (x, y).
            end: Конечные координаты (x, y).
            gravity: Переопределение силы гравитации.
            wind: Переопределение силы ветра.
            max_step: Переопределение максимального размера шага.
            target_area: Переопределение радиуса целевой зоны.

        Returns:
            Список координат (x, y).
        """
        return self.generate(
            start,
            end,
            gravity=gravity,
            wind=wind,
            max_step=max_step,
            target_area=target_area,
            with_delays=False,
        )


class BezierCurveGenerator:
    """Генератор траекторий перемещения на основе кривых Безье."""

    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        steps: int = 30,
        deviation: float = 0.2,
    ) -> list[tuple[int, int]]:
        """Генерирует сглаженную траекторию от start к end.

        Args:
            start: Начальная координата (x, y).
            end: Конечная координата (x, y).
            steps: Количество шагов (точек) в траектории.
            deviation: Максимальное отклонение контрольных точек от прямой линии.

        Returns:
            Список координат точек траектории движения.
        """
        if steps < 2:
            return [start, end]

        x0, y0 = start
        x3, y3 = end

        # Вычисляем расстояние
        dx = x3 - x0
        dy = y3 - y0
        dist = math.hypot(dx, dy)

        if dist < 10:
            return [start, end]

        # Генерируем случайные контрольные точки P1 и P2, отклоненные от прямой
        # Перпендикулярный вектор
        if dist == 0:
            nx, ny = 0.0, 0.0
        else:
            nx = -dy / dist
            ny = dx / dist

        offset_magnitude = dist * deviation

        # Первая контрольная точка P1 на 1/3 пути
        t1 = 0.33
        p1_base_x = x0 + dx * t1
        p1_base_y = y0 + dy * t1
        offset1 = random.uniform(-offset_magnitude, offset_magnitude)
        x1 = int(p1_base_x + nx * offset1)
        y1 = int(p1_base_y + ny * offset1)

        # Вторая контрольная точка P2 на 2/3 пути
        t2 = 0.66
        p2_base_x = x0 + dx * t2
        p2_base_y = y0 + dy * t2
        offset2 = random.uniform(-offset_magnitude, offset_magnitude)
        x2 = int(p2_base_x + nx * offset2)
        y2 = int(p2_base_y + ny * offset2)

        points = []
        for i in range(steps):
            # Используем нелинейное распределение t для имитации ускорения и замедления (ease-in-out)
            raw_t = i / (steps - 1)
            # Кубический ease-in-out
            if raw_t < 0.5:
                t = 4 * raw_t * raw_t * raw_t
            else:
                f = 2 * raw_t - 2
                t = 0.5 * f * f * f + 1

            # Кубическая кривая Безье
            mt = 1.0 - t
            mt2 = mt * mt
            mt3 = mt2 * mt
            t2_val = t * t
            t3 = t2_val * t

            x = int(mt3 * x0 + 3 * mt2 * t * x1 + 3 * mt * t2_val * x2 + t3 * x3)
            y = int(mt3 * y0 + 3 * mt2 * t * y1 + 3 * mt * t2_val * y2 + t3 * y3)

            points.append((x, y))

        return points


class JitterDelayGenerator:
    """Генератор реалистичных задержек."""

    def __init__(self, strategy: str = "lognormal", jitter: float = 0.15) -> None:
        """Инициализирует генератор задержек.

        Args:
            strategy: Стратегия ('lognormal' или 'normal').
            jitter: Коэффициент разброса (джиттер).
        """
        self.strategy = strategy
        self.jitter = max(0.01, jitter)

    def generate(self, base_delay: float) -> float:
        """Возвращает сгенерированную задержку на основе базовой.

        Args:
            base_delay: Базовая величина задержки (в секундах).

        Returns:
            Полученное случайное значение задержки с учетом джиттера.
        """
        if base_delay <= 0.0:
            return 0.0

        if self.strategy == "lognormal":
            # Логнормальное распределение: большинство значений близки к base, но бывают длинные хвосты
            # mu и sigma подбираются так, чтобы среднее значение было близко к base_delay
            sigma = self.jitter
            mu = math.log(base_delay) - (sigma**2) / 2
            val = random.lognormvariate(mu, sigma)
            return max(0.001, val)
        else:
            # Нормальное распределение
            val = random.gauss(base_delay, base_delay * self.jitter)
            return max(0.001, val)
