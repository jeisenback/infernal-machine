"""A permanent's current power and toughness: its card's printed values plus counters."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game import Permanent

PLUS = "+1/+1"
MINUS = "-1/-1"


def _number(value: str | None) -> int | None:
    return int(value) if value and value.lstrip("-").isdigit() else None


def _counter_bonus(permanent: Permanent) -> int:
    return permanent.counters.get(PLUS, 0) - permanent.counters.get(MINUS, 0)


def power(permanent: Permanent) -> int:
    """Current power; printed "*" counts as 0. Can be negative (it then deals no damage)."""
    return (_number(permanent.card.power) or 0) + _counter_bonus(permanent)


def toughness(permanent: Permanent) -> int | None:
    """Current toughness, or None if it isn't a creature or its printed toughness isn't a number ("*")."""
    if "Creature" not in permanent.card.type_line:
        return None
    base = _number(permanent.card.toughness)
    return None if base is None else base + _counter_bonus(permanent)
