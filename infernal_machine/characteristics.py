"""A permanent's current power and toughness: its card's printed values plus
counters plus modifiers (static abilities like anthems, and "until end of turn"
effects like Giant Growth). The game collects the modifiers; see Game.modifiers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .game import Permanent

PLUS = "+1/+1"
MINUS = "-1/-1"


LOSES = "loses "  # a pseudo-keyword prefix: "loses flying" (Colossus Hammer), "loses indestructible" (Shadowspear)
LOSES_HEXPROOF = "loses hexproof and shroud"  # a pseudo-keyword: "creatures your opponents control lose hexproof and shroud"


@dataclass(frozen=True)
class Modifier:
    power: int = 0
    toughness: int = 0
    keywords: frozenset[str] = frozenset()  # lowercase, e.g. {"flying"}
    set_pt: tuple[int, int] | None = None  # "becomes a 4/4": its base power and toughness (counters and bonuses still apply)
    your_turn: bool = False  # only counts during its controller's turn ("During your turn, this creature has first strike.")


def source_qualities(card) -> frozenset[str]:
    """What protection can be from about a source: its color letters, its card types in lowercase ("creature",
    "instant"), and "monocolored", "multicolored" or "colorless"."""
    types = {word.lower() for word in card.type_line.partition("\u2014")[0].split()}
    kind = "colorless" if not card.colors else "multicolored" if len(card.colors) > 1 else "monocolored"
    return frozenset(card.colors) | types | {kind}


def _number(value: str | None) -> int | None:
    return int(value) if value and value.lstrip("-").isdigit() else None


@lru_cache(maxsize=None)
def _counter_pt(name: str) -> tuple[int, int] | None:
    """What a counter named like "+1/+1", "-1/-1" or "-0/-1" (Wall of Roots) adds to power and toughness (CR 122.1a)."""
    m = re.fullmatch(r"([+\-])(\d+)/([+\-])(\d+)", name)
    return (int(m[1] + m[2]), int(m[3] + m[4])) if m else None


def _counter_bonus(permanent: Permanent, index: int) -> int:
    return sum(pt[index] * n for name, n in permanent.counters.items() if (pt := _counter_pt(name)))


def _base(printed: str | None, modifiers: list[Modifier], index: int) -> int | None:
    """The base value: the latest "becomes N/N" if there is one, otherwise what is printed."""
    for modifier in reversed(modifiers):
        if modifier.set_pt is not None:
            return modifier.set_pt[index]
    return _number(printed)


def power(permanent: Permanent, modifiers: Iterable[Modifier] = ()) -> int:
    """Current power; printed "*" counts as 0. Can be negative (it then deals no damage)."""
    modifiers = list(modifiers)
    return (_base(permanent.card.power, modifiers, 0) or 0) + _counter_bonus(permanent, 0) + sum(m.power for m in modifiers)


def toughness(permanent: Permanent, modifiers: Iterable[Modifier] = ()) -> int | None:
    """Current toughness, or None if it isn't a creature or its printed toughness isn't a number ("*")."""
    if "Creature" not in permanent.card.type_line:
        return None
    modifiers = list(modifiers)
    base = _base(permanent.card.toughness, modifiers, 1)
    return None if base is None else base + _counter_bonus(permanent, 1) + sum(m.toughness for m in modifiers)
