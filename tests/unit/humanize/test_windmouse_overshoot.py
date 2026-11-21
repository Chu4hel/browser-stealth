"""Репродукция ISSUE-20261120-B7A1: занос WindMouse в соседний пункт меню."""

from __future__ import annotations

import random
from typing import NamedTuple

import pytest

from browser_stealth import WindMouseGenerator


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


@pytest.mark.xfail(
    strict=True,
    reason="ISSUE-20261120-B7A1: WindMouse заносит курсор в «Пожаловаться»",
)
def test_windmouse_does_not_overshoot_into_complain_item() -> None:
    """Курсор по пути к «Скрыть эту вакансию» не должен попадать в «Пожаловаться».

    В меню hh.ru пункт «Скрыть эту вакансию» (y: 135..165) находится прямо над
    пунктом «Пожаловаться» (y: 165..195). Инерция и случайный ветер WindMouse
    могут вынести траекторию за нижнюю границу «Скрыть» — тогда наведение или
    клик срабатывает на соседнем пункте.

    Тест детерминирован: для каждого seed генерируется одна и та же траектория
    при текущей реализации WindMouse. Сейчас он падает (xfail); после
    исправления бага маркер нужно снять.
    """
    more_button_pos = (200, 100)
    hide_item = BoundingBox(x=100, y=135, width=200, height=30)
    hide_target = (200, 150)
    complain_item = BoundingBox(x=100, y=165, width=200, height=30)

    generator = WindMouseGenerator(gravity=9.0, wind=3.0, max_step=15.0, target_area=8.0)
    violations: list[tuple[int, int, int]] = []

    for seed in range(100):
        random.seed(seed)
        trajectory = generator.generate(more_button_pos, hide_target, with_delays=False)
        violations.extend(
            (seed, x, y)
            for x, y in trajectory
            if complain_item.contains(x, y) and not hide_item.contains(x, y)
        )

    assert not violations, (
        f"ISSUE-20261120-B7A1: курсор WindMouse заходит в пункт «Пожаловаться»: {violations[:5]}"
    )
