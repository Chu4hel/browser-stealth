"""Репродукция ISSUE-20261120-B7A1: занос WindMouse в соседний пункт меню."""

from __future__ import annotations

import random
from typing import NamedTuple

from browser_stealth import BezierCurveGenerator, TouchGestureGenerator, WindMouseGenerator


class BoundingBox(NamedTuple):
    """Прямоугольная область элемента в экранных координатах."""

    x: float
    y: float
    width: float
    height: float

    def contains(self, px: float, py: float) -> bool:
        """Проверяет попадание точки в пределы элемента.

        Args:
            px: Координата X.
            py: Координата Y.

        Returns:
            True, если точка лежит внутри прямоугольника или на его границе.
        """
        return self.x <= px <= (self.x + self.width) and self.y <= py <= (self.y + self.height)


MORE_BUTTON_POS = (200, 100)
HIDE_ITEM = BoundingBox(x=100, y=135, width=200, height=30)
HIDE_TARGET = (200, 150)
COMPLAIN_ITEM = BoundingBox(x=100, y=165, width=200, height=30)


def test_windmouse_does_not_overshoot_into_complain_item() -> None:
    """Курсор по пути к «Скрыть эту вакансию» не должен попадать в «Пожаловаться».

    В меню hh.ru пункт «Скрыть эту вакансию» (y: 135..165) находится прямо над
    пунктом «Пожаловаться» (y: 165..195). Инерция и случайный ветер WindMouse
    могут вынести траекторию за нижнюю границу «Скрыть» — тогда наведение или
    клик срабатывает на соседнем пункте.

    Тест детерминирован: для каждого seed генерируется одна и та же траектория
    при текущей реализации WindMouse.
    """
    generator = WindMouseGenerator(gravity=9.0, wind=3.0, max_step=15.0, target_area=8.0)
    violations: list[tuple[int, int, int]] = []

    for seed in range(1000):
        random.seed(seed)
        trajectory = generator.generate(MORE_BUTTON_POS, HIDE_TARGET, with_delays=False)
        violations.extend(
            (seed, x, y)
            for x, y in trajectory
            if COMPLAIN_ITEM.contains(x, y) and not HIDE_ITEM.contains(x, y)
        )

    assert not violations, (
        f"ISSUE-20261120-B7A1: курсор WindMouse заходит в пункт «Пожаловаться»: {violations[:5]}"
    )


def test_touch_tap_drift_stays_inside_hide_item() -> None:
    """Микросдвиг пальца при тапе не должен выносить касание в соседний пункт.

    Тап выполняется по нижней части пункта «Скрыть эту вакансию» (y = 163).
    Амплитуда дрожания пальца задана так, чтобы сдвиг достигал 5 px, как в
    отчёте об ISSUE: генератор умножает jitter на случайное значение до 1.5.
    Границы пункта «Скрыть» передаются явно, поэтому дрейф не выходит в зону
    «Пожаловаться».
    """
    tap_y = 163.0
    drift_amplitude = 5.0
    generator = TouchGestureGenerator(jitter=drift_amplitude / 1.5)
    bounds = (
        HIDE_ITEM.x,
        HIDE_ITEM.y,
        HIDE_ITEM.x + HIDE_ITEM.width,
        HIDE_ITEM.y + HIDE_ITEM.height,
    )
    violations: list[tuple[int, float, float]] = []

    for seed in range(100):
        random.seed(seed)
        for point in generator.generate_tap(200, tap_y, bounds=bounds):
            if COMPLAIN_ITEM.contains(point.x, point.y) and not HIDE_ITEM.contains(
                point.x, point.y
            ):
                violations.append((seed, point.x, point.y))

    assert not violations, (
        f"ISSUE-20261120-B7A1: дрейф тапа уводит касание в «Пожаловаться»: {violations[:5]}"
    )


def test_bezier_does_not_overshoot_into_complain_item() -> None:
    """Bezier на той же геометрии не заходит в «Пожаловаться».

    Кривая Безье не накапливает инерцию, поэтому её контрольные точки удерживают
    траекторию в пределах пункта «Скрыть». Тест служит ориентиром при выборе
    algorithm="bezier" для компактных меню.
    """
    generator = BezierCurveGenerator()
    violations: list[tuple[int, int, int]] = []

    for seed in range(200):
        random.seed(seed)
        trajectory = generator.generate(MORE_BUTTON_POS, HIDE_TARGET, steps=30, deviation=0.1)
        violations.extend(
            (seed, x, y)
            for x, y in trajectory
            if COMPLAIN_ITEM.contains(x, y) and not HIDE_ITEM.contains(x, y)
        )

    assert not violations, f"Bezier вышел за пункт «Скрыть» в «Пожаловаться»: {violations[:5]}"
