"""A permanent's current power and toughness: its card's printed values plus
counters plus modifiers (static abilities like anthems, and "until end of turn"
effects like Giant Growth). The game collects the modifiers; see Game.modifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .game import Permanent

PLUS = "+1/+1"
MINUS = "-1/-1"


@dataclass(frozen=True)
class Modifier:
    power: int = 0
    toughness: int = 0
    keywords: frozenset[str] = frozenset()  # lowercase, e.g. {"flying"}
    set_pt: tuple[int, int] | None = None  # "becomes a 4/4": its base power and toughness (counters and bonuses still apply)


def _number(value: str | None) -> int | None:
    return int(value) if value and value.lstrip("-").isdigit() else None


def _counter_bonus(permanent: Permanent) -> int:
    return permanent.counters.get(PLUS, 0) - permanent.counters.get(MINUS, 0)


def _base(printed: str | None, modifiers: list[Modifier], index: int) -> int | None:
    """The base value: the latest "becomes N/N" if there is one, otherwise what is printed."""
    for modifier in reversed(modifiers):
        if modifier.set_pt is not None:
            return modifier.set_pt[index]
    return _number(printed)


def power(permanent: Permanent, modifiers: Iterable[Modifier] = ()) -> int:
    """Current power; printed "*" counts as 0. Can be negative (it then deals no damage)."""
    modifiers = list(modifiers)
    return (_base(permanent.card.power, modifiers, 0) or 0) + _counter_bonus(permanent) + sum(m.power for m in modifiers)


def toughness(permanent: Permanent, modifiers: Iterable[Modifier] = ()) -> int | None:
    """Current toughness, or None if it isn't a creature or its printed toughness isn't a number ("*")."""
    if "Creature" not in permanent.card.type_line:
        return None
    modifiers = list(modifiers)
    base = _base(permanent.card.toughness, modifiers, 1)
    return None if base is None else base + _counter_bonus(permanent) + sum(m.toughness for m in modifiers)
