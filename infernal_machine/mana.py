"""Mana costs and paying them from mana sources."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from itertools import product

MANA_TYPES = frozenset("WUBRGC")
GENERIC_ONLY = "1"  # a source that can pay only for generic mana (a colorless creature tapped for Convoke, an artifact for Improvise)
SNOW = "S"  # a snow permanent's mana also counts as snow mana: its types include this, and {S} wants it
_SYMBOL = re.compile(r"\{([^}]+)\}")


@dataclass(frozen=True)
class Cost:
    generic: int = 0
    # Each colored symbol is the set of mana types that can pay it: {G} is {"G"}, {G/W} is {"G", "W"}.
    colored: tuple[frozenset[str], ...] = ()
    x: int = 0  # how many {X} symbols; the caster chooses X, then each adds X generic
    twobrid: tuple[frozenset[str], ...] = ()  # {2/W}: one white mana or two mana of any type
    phyrexian: tuple[frozenset[str], ...] = ()  # {W/P}: one white mana or 2 life

    def plus_generic(self, amount: int) -> "Cost":
        return replace(self, generic=self.generic + amount)

    def reduced(self, amount: int) -> "Cost":
        """Cost reductions only lower the generic part (CR 601.2f)."""
        return replace(self, generic=max(0, self.generic - amount))

    def with_x(self, value: int) -> "Cost":
        """The cost to pay once X is chosen."""
        return replace(self, generic=self.generic + self.x * value, x=0)

    def __add__(self, other: "Cost") -> "Cost":
        return Cost(self.generic + other.generic, self.colored + other.colored, self.x + other.x,
                    self.twobrid + other.twobrid, self.phyrexian + other.phyrexian)


def parse_cost(mana_cost: str) -> Cost | None:
    """Parse a Scryfall mana cost like "{2}{G}{G/W}".

    X symbols are counted in `x`; {S} is snow mana, {2/W} twobrid and {W/P} Phyrexian symbols are kept apart
    (see Cost). Returns None for symbols not supported and for cards with no mana cost, which can't be
    cast normally.
    """
    if not mana_cost:
        return None
    generic = x = 0
    colored: list[frozenset[str]] = []
    twobrid: list[frozenset[str]] = []
    phyrexian: list[frozenset[str]] = []
    for symbol in _SYMBOL.findall(mana_cost):
        parts = symbol.split("/")
        if symbol.isdigit():
            generic += int(symbol)
        elif symbol == "X":
            x += 1
        elif symbol in MANA_TYPES or symbol == SNOW:
            colored.append(frozenset(symbol))
        elif parts[-1] == "P" and len(parts) > 1 and set(parts[:-1]) <= MANA_TYPES:
            phyrexian.append(frozenset(parts[:-1]))
        elif parts[0] == "2" and len(parts) == 2 and parts[1] in MANA_TYPES:
            twobrid.append(frozenset(parts[1]))
        elif "/" in symbol and set(parts) <= MANA_TYPES:
            colored.append(frozenset(parts))
        else:
            return None
    return Cost(generic, tuple(colored), x, tuple(twobrid), tuple(phyrexian))


def pay(cost: Cost, sources: list[frozenset[str]], paid_for: dict[int, frozenset[str]] | None = None) -> list[int] | None:
    """Pick which sources to tap for `cost`; each source makes one mana of one of its types.
    A Phyrexian symbol is paid with mana here (the caller may pay life for some of them first); a twobrid
    symbol is paid with one mana of its color if that works, else with two of any.
    """
    for halves in product((True, False), repeat=len(cost.twobrid)):
        flat = Cost(cost.generic + 2 * halves.count(False), cost.colored + cost.phyrexian
                    + tuple(c for c, half in zip(cost.twobrid, halves) if half), cost.x)
        found = _pay_flat(flat, sources, paid_for)
        if found is not None:
            return found
    return None


def _pay_flat(cost: Cost, sources: list[frozenset[str]], paid_for: dict[int, frozenset[str]] | None = None) -> list[int] | None:
    """`pay` for a cost that is only generic and colored mana.

    Returns source indices, or None if the cost can't be paid. Sources that
    make fewer colors are used first, keeping flexible ones untapped. If `paid_for`
    is given it's filled with source index -> the colored symbol that source pays
    (sources paying generic mana aren't listed).
    """
    order = sorted((i for i, s in enumerate(sources) if s), key=lambda i: len(sources[i]))
    symbols = sorted(cost.colored, key=len)
    if len(symbols) + cost.generic > len(order):
        return None  # more mana than sources: no assignment can work (and trying them all takes forever: Replicate with many lands)
    failed: set[tuple[int, frozenset[int]]] = set()  # (symbols matched so far, sources used) that lead nowhere, in any order

    def assign(k: int, used: tuple[int, ...]) -> list[int] | None:
        if (k, frozenset(used)) in failed:
            return None
        if k == len(symbols):
            rest = [i for i in order if i not in used]
            if len(rest) < cost.generic:
                return None
            if paid_for is not None:
                paid_for.clear()
                paid_for.update({i: symbols[n] for n, i in enumerate(used)})
            return sorted(used) + rest[: cost.generic]
        for i in order:
            if i not in used and sources[i] & symbols[k]:
                found = assign(k + 1, used + (i,))
                if found is not None:
                    return found
        failed.add((k, frozenset(used)))
        return None

    return assign(0, ())
