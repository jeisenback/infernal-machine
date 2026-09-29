"""Deck statistics used when building or tuning a deck."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .cards import Card

CURVE_CAP = 7  # mana values of 7 or more share the top bucket
_SYMBOL = re.compile(r"\{([^}]+)\}")


@dataclass
class DeckStats:
    card_count: int
    land_count: int
    average_mana_value: float  # nonland cards only
    curve: dict[int, int]  # mana value -> nonland card count; key 7 means 7+
    color_pips: dict[str, int]  # W/U/B/R/G -> colored mana symbols across all costs


def is_land(card: Card) -> bool:
    return "Land" in card.type_line


def color_pips(mana_cost: str) -> Counter:
    """Count colored symbols in a cost; hybrid and Phyrexian symbols count each color."""
    pips: Counter = Counter()
    for symbol in _SYMBOL.findall(mana_cost):
        for part in symbol.split("/"):
            if part in ("W", "U", "B", "R", "G"):
                pips[part] += 1
    return pips


def analyze(cards: list[Card]) -> DeckStats:
    """Stats for a list of cards; for Commander pass deck.commanders + deck.main."""
    spells = [c for c in cards if not is_land(c)]
    curve = Counter(min(int(c.cmc), CURVE_CAP) for c in spells)
    pips: Counter = Counter()
    for card in cards:
        pips += color_pips(card.mana_cost)
    return DeckStats(
        card_count=len(cards),
        land_count=len(cards) - len(spells),
        average_mana_value=round(sum(c.cmc for c in spells) / len(spells), 2) if spells else 0.0,
        curve={mv: curve.get(mv, 0) for mv in range(CURVE_CAP + 1)},
        color_pips={color: pips[color] for color in "WUBRG" if pips[color]},
    )
