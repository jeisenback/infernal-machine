"""Mana costs and paying them from mana sources."""

from __future__ import annotations

import re
from dataclasses import dataclass

MANA_TYPES = frozenset("WUBRGC")
_SYMBOL = re.compile(r"\{([^}]+)\}")


@dataclass(frozen=True)
class Cost:
    generic: int = 0
    # Each colored symbol is the set of mana types that can pay it: {G} is {"G"}, {G/W} is {"G", "W"}.
    colored: tuple[frozenset[str], ...] = ()
    x: int = 0  # how many {X} symbols; the caster chooses X, then each adds X generic

    def plus_generic(self, amount: int) -> "Cost":
        return Cost(self.generic + amount, self.colored, self.x)

    def with_x(self, value: int) -> "Cost":
        """The cost to pay once X is chosen."""
        return Cost(self.generic + self.x * value, self.colored)

    def __add__(self, other: "Cost") -> "Cost":
        return Cost(self.generic + other.generic, self.colored + other.colored, self.x + other.x)


def parse_cost(mana_cost: str) -> Cost | None:
    """Parse a Scryfall mana cost like "{2}{G}{G/W}".

    X symbols are counted in `x` and Phyrexian symbols must be paid with mana. Returns None
    for symbols not supported yet ({S} snow, {2/W} twobrid) and for cards with
    no mana cost, which can't be cast normally.
    """
    if not mana_cost:
        return None
    generic = x = 0
    colored: list[frozenset[str]] = []
    for symbol in _SYMBOL.findall(mana_cost):
        if symbol.isdigit():
            generic += int(symbol)
        elif symbol == "X":
            x += 1
        elif symbol in MANA_TYPES:
            colored.append(frozenset(symbol))
        elif symbol.endswith("/P") and symbol[0] in MANA_TYPES:
            colored.append(frozenset(symbol[0]))
        elif "/" in symbol and set(symbol.split("/")) <= MANA_TYPES:
            colored.append(frozenset(symbol.split("/")))
        else:
            return None
    return Cost(generic, tuple(colored), x)


def pay(cost: Cost, sources: list[frozenset[str]]) -> list[int] | None:
    """Pick which sources to tap for `cost`; each source makes one mana of one of its types.

    Returns source indices, or None if the cost can't be paid. Sources that
    make fewer colors are used first, keeping flexible ones untapped.
    """
    order = sorted((i for i, s in enumerate(sources) if s), key=lambda i: len(sources[i]))
    symbols = sorted(cost.colored, key=len)

    def assign(k: int, used: frozenset[int]) -> list[int] | None:
        if k == len(symbols):
            rest = [i for i in order if i not in used]
            return sorted(used) + rest[: cost.generic] if len(rest) >= cost.generic else None
        for i in order:
            if i not in used and sources[i] & symbols[k]:
                found = assign(k + 1, used | {i})
                if found is not None:
                    return found
        return None

    return assign(0, frozenset())
