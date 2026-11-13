from dataclasses import dataclass

from browser_stealth.profiles.rotation import (
    LeastUsedRotation,
    RoundRobinRotation,
    StickyAffinityRotation,
)


@dataclass
class DummyProfile:
    name: str
    success_count: int = 0
    last_used_at: float = 0.0


def test_round_robin_rotation() -> None:
    strat = RoundRobinRotation[DummyProfile]()
    profs = [DummyProfile("p1"), DummyProfile("p2"), DummyProfile("p3")]

    assert strat.select(profs, key_fn=lambda p: p.name).name == "p1"
    assert strat.select(profs, key_fn=lambda p: p.name).name == "p2"
    assert strat.select(profs, key_fn=lambda p: p.name).name == "p3"
    assert strat.select(profs, key_fn=lambda p: p.name).name == "p1"

    # Исключение
    assert strat.select(profs, exclude={"p2"}, key_fn=lambda p: p.name).name == "p3"


def test_least_used_rotation() -> None:
    strat = LeastUsedRotation[DummyProfile]()
    profs = [
        DummyProfile("p1", success_count=10, last_used_at=100.0),
        DummyProfile("p2", success_count=2, last_used_at=50.0),
        DummyProfile("p3", success_count=5, last_used_at=80.0),
    ]

    chosen = strat.select(profs, key_fn=lambda p: p.name)
    assert chosen is not None
    assert chosen.name == "p2"


def test_sticky_affinity_rotation() -> None:
    strat = StickyAffinityRotation[DummyProfile](RoundRobinRotation[DummyProfile]())
    profs = [DummyProfile("p1"), DummyProfile("p2")]

    # Сессия sess_A закрепляется за p1
    chosen_a = strat.select(profs, session_id="sess_A", key_fn=lambda p: p.name)
    assert chosen_a.name == "p1"

    # Сессия sess_B получает p2
    chosen_b = strat.select(profs, session_id="sess_B", key_fn=lambda p: p.name)
    assert chosen_b.name == "p2"

    # Повторный запрос sess_A снова возвращает p1!
    repeat_a = strat.select(profs, session_id="sess_A", key_fn=lambda p: p.name)
    assert repeat_a.name == "p1"
