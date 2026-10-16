"""Mana base advice: how many sources of each color a deck needs, and how many it has.

    python -m infernal_machine.manabase DECKLIST [--target 0.9] [--coverage 0.8] [--slack N] [--play | --draw]

The number needed for one spell is the smallest count of sources `S` for which the chance of holding at least as many colored sources
as the spell has pips of that color, among the cards seen by the turn it should be cast, is at least `target`. That is the
hypergeometric distribution: the deck's library has `N` cards, `S` of them sources, and `seen` are drawn (the opening seven plus a
card a turn, one fewer on the play). The turn is the spell's mana value plus `slack`, or its pip count if that is higher. A mana base is
built around what most of a color's spells ask for, not its single hardest card, so the number a color needs is the one that covers
`coverage` (80%) of its spells; the hardest spells are named beside it, and a color that has fewer sources than they ask for can expect
to cast those late. X spells are left out of the numbers: they are cast whenever there is mana enough.

Assumptions, all printed with the result: no mulligans, only lands are counted as sources (the mana rocks and mana creatures are
listed apart), a land that fetches a basic counts for the colors of the basics in the deck, hybrid and Phyrexian symbols are left
out, X is 0, and a commander counts like any spell (cast from the command zone, but it still needs the sources). Published tables
(such as Frank Karsten's) make further assumptions, such as how mulligans are chosen, so their numbers can differ from these. Commander
decks default to cards seen on the draw and two turns of slack, since 90% on the exact turn of the mana value is out of reach for
three colors; a Standard deck defaults to the play and no slack. This is advice to weigh, not a verdict.
"""

from __future__ import annotations

import io
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from math import comb

from .analysis import is_land
from .cards import Card, Deck
from .mana import parse_cost
from .simulate import fetch_land, mana_sources

COLORS = "WUBRG"
NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
OPENING_HAND = 7
DEFAULT_TARGET = 0.90
DEFAULT_COVERAGE = 0.80
COMMANDER_SLACK = 2


def p_at_least(library: int, sources: int, seen: int, needed: int) -> float:
    """The chance of at least `needed` sources among `seen` cards drawn from `library` cards of which `sources` are sources."""
    if needed <= 0:
        return 1.0
    seen = min(seen, library)
    total = comb(library, seen)
    return sum(comb(sources, k) * comb(library - sources, seen - k) for k in range(needed, min(sources, seen) + 1)) / total


def sources_needed(library: int, seen: int, needed: int, target: float = DEFAULT_TARGET) -> int | None:
    """The fewest sources that give `target` odds of `needed` of them among `seen` cards; None if `seen` cannot hold that many."""
    if needed > min(seen, library):
        return None
    return next((s for s in range(needed, library + 1) if p_at_least(library, s, seen, needed) >= target), None)


def cards_seen(turn: int, on_the_play: bool) -> int:
    """The opening seven plus a draw each turn (none on turn one when on the play)."""
    return OPENING_HAND + (turn - 1 if on_the_play else turn)


def pips(card: Card) -> dict[str, int]:
    """Single-color symbols in the cost; a hybrid or Phyrexian symbol can be paid another way, so it is not counted."""
    cost = parse_cost(card.mana_cost)
    counts: dict[str, int] = {}
    for symbol in (cost.colored if cost else ()):
        if len(symbol) == 1 and next(iter(symbol)) in COLORS:
            color = next(iter(symbol))
            counts[color] = counts.get(color, 0) + 1
    return counts


@dataclass
class SpellNeed:
    card: str
    cost: str
    color: str
    pips: int
    turn: int  # the turn it should be cast by
    sources: int | None  # sources needed; None if the cards seen by then cannot hold that many


@dataclass
class ColorLine:
    color: str
    pips: int  # single-color symbols of this color across the deck
    have: int  # lands that make it
    needed: int  # what the spells covering `coverage` of this color's spells ask for
    spells: int  # how many spells (copies, and not counting X spells) have a pip of this color
    driver: SpellNeed | None  # the most demanding spell
    others: list[SpellNeed] = field(default_factory=list)  # the next most demanding
    rocks: int = 0  # mana rocks and creatures that also make it (not in `have`)

    @property
    def short(self) -> int:
        return max(0, self.needed - self.have)

    @property
    def hardest_short(self) -> int:
        """How far the lands are from what the most demanding spell asks for."""
        return max(0, self.driver.sources - self.have) if self.driver and self.driver.sources is not None else 0


@dataclass
class ManaBase:
    library: int
    lands: int
    on_the_play: bool
    target: float
    coverage: float
    slack: int
    colors: list[ColorLine]
    stuck: dict[int, float] = field(default_factory=dict)  # turn -> share of goldfish games with a spell stuck on colors


def land_sources(deck: Deck) -> dict[str, int]:
    """Lands (not the commanders) that make each color. A commander's color identity limits what a land that makes any color makes."""
    identity = {color for c in deck.commanders for color in c.color_identity}
    basics = {color for c in deck.main if is_land(c) and "Basic" in c.type_line for color in c.produced_mana}
    counts = {color: 0 for color in COLORS}
    for land in (c for c in deck.main if is_land(c)):
        made = set(land.produced_mana) & set(COLORS)
        if fetch_land(land) is not None:
            made = basics & set(COLORS)
        if identity:
            made &= identity
        for color in made:
            counts[color] += 1
    return counts


def analyze_mana_base(deck: Deck, target: float = DEFAULT_TARGET, slack: int | None = None, on_the_play: bool | None = None,
                      coverage: float = DEFAULT_COVERAGE) -> ManaBase | None:
    """The sources each color needs and has, or None if the deck has no colored symbols. By default a Commander deck is on the draw with
    two turns of slack and a Standard deck on the play with none."""
    commander = bool(deck.commanders)
    slack = (COMMANDER_SLACK if commander else 0) if slack is None else slack
    on_the_play = (not commander) if on_the_play is None else on_the_play
    library = len(deck.main)
    spells = {c.name: c for c in deck.commanders + deck.main if not is_land(c)}
    copies = Counter(c.name for c in deck.commanders + deck.main if not is_land(c))
    total_pips: dict[str, int] = {}
    for card in deck.commanders + deck.main:
        if not is_land(card):
            for color, n in pips(card).items():
                total_pips[color] = total_pips.get(color, 0) + n
    have = land_sources(deck)
    rocks = {color: sum(1 for c in deck.main if color in {m for made in mana_sources(c) for m in made}) for color in COLORS}
    lines = []
    for color in COLORS:
        if color not in total_pips:
            continue
        needs = []
        for card in spells.values():
            n = pips(card).get(color)
            if n and "{X}" not in card.mana_cost:
                turn = max(int(card.cmc), n, 1) + slack
                needs.append(SpellNeed(card.name, card.mana_cost, color, n, turn, sources_needed(library, cards_seen(turn, on_the_play), n, target)))
        # a spell the cards seen could never pay for counts as asking for the whole library, so that it sorts first
        ranked = sorted(needs, key=lambda s: (-(s.sources if s.sources is not None else library + 1), -s.pips, s.card))
        asks = sorted(ask for s in needs for ask in [s.sources if s.sources is not None else library] * copies[s.card])  # (a card counts once for each copy)
        covered = asks[max(0, math.ceil(coverage * len(asks)) - 1)] if asks else 0
        lines.append(ColorLine(color, total_pips[color], have[color], covered, len(asks), ranked[0] if ranked else None, ranked[1:3], rocks[color]))
    if not lines:
        return None
    return ManaBase(library, sum(1 for c in deck.main if is_land(c)), on_the_play, target, coverage, slack, lines)


def format_mana_base(base: ManaBase) -> str:
    seen = "on the play" if base.on_the_play else "on the draw"
    lines = [f"Mana base: sources of each color for {base.target:.0%} odds of casting each spell by its mana value"
             + (f" plus {base.slack} turn{'s' if base.slack != 1 else ''}" if base.slack else "")
             + f", {seen}, from a {base.library}-card library with {base.lands} lands (no mulligans). 'Needed' covers {base.coverage:.0%} of a color's spells.",
             "color   pips  sources  needed  verdict                         hardest spells"]
    for line in base.colors:
        verdict = f"short by {line.short}" if line.short else "enough"
        if line.hardest_short:
            verdict += f" (hardest: {line.hardest_short})" if line.short else f" (hardest short by {line.hardest_short})"
        hardest = ", ".join(f"{d.card} ({d.cost}, by turn {d.turn}) needs {d.sources if d.sources is not None else 'more than there are cards'}"
                            for d in ([line.driver] if line.driver else []) + line.others[:1])
        lines.append(f"{NAMES[line.color]:<7} {line.pips:>4}  {line.have:>7}  {line.needed:>6}  {verdict:<30}  {hardest or 'only X spells'}")
    rocks = [f"{NAMES[line.color]} {line.rocks}" for line in base.colors if line.rocks]
    if rocks:
        lines.append(f"Not counted as sources: mana rocks and creatures that make {', '.join(rocks)}.")
    if base.stuck:
        lines.append("In the goldfish a spell was stuck on colors in " + ", ".join(f"{share:.0%} of games on turn {turn}" for turn, share in base.stuck.items()) + ".")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import argparse

    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("--target", type=float, default=DEFAULT_TARGET, help="the odds to reach (default 0.9)")
    parser.add_argument("--coverage", type=float, default=DEFAULT_COVERAGE, help="the share of a color's spells the number must cover (default 0.8)")
    parser.add_argument("--slack", type=int, help="turns after the mana value (default 2 for Commander, 0 otherwise)")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    when = parser.add_mutually_exclusive_group()
    when.add_argument("--play", dest="on_the_play", action="store_true", default=None, help="count cards seen on the play")
    when.add_argument("--draw", dest="on_the_play", action="store_false", help="count cards seen on the draw")
    args = parser.parse_args(argv[1:])
    with open(args.decklist, encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(args.bulk))
    base = analyze_mana_base(deck, args.target, args.slack, args.on_the_play, args.coverage)
    print(format_mana_base(base) if base else "This deck has no colored mana symbols.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
