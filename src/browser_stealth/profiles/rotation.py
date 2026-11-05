"""Универсальные алгоритмы и стратегии ротации профилей браузера."""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Generic, TypeVar

TProfile = TypeVar("TProfile")


class ProfileRotationStrategy(ABC, Generic[TProfile]):
    """Абстрактный базовый класс стратегии ротации профилей."""

    @abstractmethod
    def select(
        self,
        profiles: Sequence[TProfile],
        *,
        exclude: set[str] | None = None,
        key_fn: Callable[[TProfile], str] | None = None,
        session_id: str | None = None,
    ) -> TProfile | None:
        """Выбирает наиболее подходящий профиль из списка кандидатов.

        Args:
            profiles: Список доступных профилей.
            exclude: Опциональное множество идентификаторов профилей, исключаемых из выбора.
            key_fn: Функция извлечения уникального строкового ключа (имени) профиля.
            session_id: Опциональный идентификатор пользовательской сессии/задачи для affinity.

        Returns:
            Выбранный профиль или None, если кандидатов нет.
        """
        ...


class RoundRobinRotation(ProfileRotationStrategy[TProfile]):
    """Циклическая стратегия ротации профилей (Round-Robin)."""

    def __init__(self) -> None:
        self._last_index: int = -1

    def select(
        self,
        profiles: Sequence[TProfile],
        *,
        exclude: set[str] | None = None,
        key_fn: Callable[[TProfile], str] | None = None,
        session_id: str | None = None,
    ) -> TProfile | None:
        k_fn = key_fn or str
        candidates = [p for p in profiles if not exclude or k_fn(p) not in exclude]
        if not candidates:
            return None

        self._last_index = (self._last_index + 1) % len(candidates)
        return candidates[self._last_index]


class LeastUsedRotation(ProfileRotationStrategy[TProfile]):
    """Стратегия выбора наименее используемого профиля (Least Recently / Frequently Used)."""

    def __init__(
        self,
        score_fn: Callable[[TProfile], tuple[object, ...]] | None = None,
    ) -> None:
        """Инициализирует стратегию.

        Args:
            score_fn: Функция вычисления веса профиля (чем меньше значение, тем выше приоритет выбора).
                      По умолчанию: `(getattr(p, 'success_count', 0), getattr(p, 'last_used_at', 0.0))`.
        """
        self._score_fn = score_fn or (
            lambda p: (
                getattr(p, "success_count", 0),
                getattr(p, "last_used_at", 0.0),
            )
        )

    def select(
        self,
        profiles: Sequence[TProfile],
        *,
        exclude: set[str] | None = None,
        key_fn: Callable[[TProfile], str] | None = None,
        session_id: str | None = None,
    ) -> TProfile | None:
        k_fn = key_fn or str
        candidates = [p for p in profiles if not exclude or k_fn(p) not in exclude]
        if not candidates:
            return None

        candidates.sort(key=self._score_fn)
        return candidates[0]


class RandomRotation(ProfileRotationStrategy[TProfile]):
    """Стратегия случайного выбора профиля."""

    def select(
        self,
        profiles: Sequence[TProfile],
        *,
        exclude: set[str] | None = None,
        key_fn: Callable[[TProfile], str] | None = None,
        session_id: str | None = None,
    ) -> TProfile | None:
        k_fn = key_fn or str
        candidates = [p for p in profiles if not exclude or k_fn(p) not in exclude]
        if not candidates:
            return None
        return random.choice(candidates)


class StickyAffinityRotation(ProfileRotationStrategy[TProfile]):
    """Стратегия привязки профиля к сессии (Session Affinity) с fallback на базовую стратегию."""

    def __init__(
        self,
        fallback_strategy: ProfileRotationStrategy[TProfile] | None = None,
        ttl_seconds: float = 3600.0,
    ) -> None:
        self._fallback_strategy = fallback_strategy or RoundRobinRotation[TProfile]()
        self._ttl_seconds = ttl_seconds
        self._affinity_map: dict[str, tuple[str, float]] = {}

    def bind(self, session_id: str, profile_key: str) -> None:
        """Явно закрепляет сессию за профилем."""
        self._affinity_map[session_id] = (profile_key, time.time())

    def unbind(self, session_id: str) -> None:
        """Снимает закрепление сессии."""
        self._affinity_map.pop(session_id, None)

    def select(
        self,
        profiles: Sequence[TProfile],
        *,
        exclude: set[str] | None = None,
        key_fn: Callable[[TProfile], str] | None = None,
        session_id: str | None = None,
    ) -> TProfile | None:
        k_fn = key_fn or str
        now = time.time()

        if session_id and session_id in self._affinity_map:
            bound_key, bound_time = self._affinity_map[session_id]
            if now - bound_time <= self._ttl_seconds:
                if not exclude or bound_key not in exclude:
                    for p in profiles:
                        if k_fn(p) == bound_key:
                            # Обновляем timestamp использования привязки
                            self._affinity_map[session_id] = (bound_key, now)
                            return p
            else:
                self.unbind(session_id)

        # Выбираем новый профиль через fallback
        chosen = self._fallback_strategy.select(
            profiles,
            exclude=exclude,
            key_fn=key_fn,
            session_id=session_id,
        )
        if chosen and session_id:
            self.bind(session_id, k_fn(chosen))
        return chosen


__all__ = [
    "LeastUsedRotation",
    "ProfileRotationStrategy",
    "RandomRotation",
    "RoundRobinRotation",
    "StickyAffinityRotation",
]
