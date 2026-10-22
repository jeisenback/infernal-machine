"""Commander Brackets: what a deck's cards say about the power level it has to be played at.

    python -m infernal_machine.brackets DECKLIST

The Brackets (1 Exhibition, 2 Core, 3 Upgraded, 4 Optimized, 5 cEDH) are partly a conversation about intent and partly a set of
hard limits on what a deck may hold. This reads the hard limits off the cards, in the published guidance as of this writing:
- Game Changers (Scryfall's `game_changer` flag, so the list follows Scryfall): none in Brackets 1 and 2, up to three in Bracket 3,
  any number in 4 and 5.
- Mass land denial: not in Brackets 1 to 3 (found by its Oracle text: it destroys, exiles or returns all lands or sacrifices them).
- Extra turns: chains of them are out below Bracket 4. A deck's extra-turn cards are listed, not counted against it.
- Combos, when the caller asked Commander Spellbook (combos.py): each combo the deck holds carries Spellbook's bracket tag, and the
  floor is at least the highest of them (a Ruthless combo, a two-card one that wins early, is not below Bracket 4).
It can't see how a deck is played, and it can't tell Bracket 1 from 2 or 4 from 5, so `floor` is the lowest bracket a deck can be played
at, never a rating. Treat it as the first thing to check before choosing opponents.

    python -m infernal_machine.brackets DECKLIST --combos    # ask Commander Spellbook too (one request per deck, then cached)
"""

from __future__ import annotations

import io
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field

from .cards import Card, Deck
from .combos import Combo

MAX_GAME_CHANGERS_BRACKET_3 = 3
MASS_LAND_DENIAL = re.compile(
    r"\b(destroy|exile) all (nonbasic )?lands\b|\b(destroy|exile) all [a-z, ]+(and|or) lands\b|\breturn all lands\b|"
    r"\beach player sacrifices (all|four|five|six|seven|x) (of their )?lands\b|\bsacrifices all lands\b", re.IGNORECASE)
EXTRA_TURN = re.compile(r"\b(takes?|gets?) (an|two|three|x) extra turns?\b|\bextra turn after this one\b", re.IGNORECASE)


@dataclass
class BracketReport:
    game_changers: list[str]  # names, one entry per copy
    mass_land_denial: list[str]
    extra_turns: list[str]
    floor: int  # the lowest bracket the deck can be played at
    combos: list[Combo] = field(default_factory=list)  # the combos it holds, when Commander Spellbook was asked

    def summary(self) -> str:
        parts = [f"plays at Bracket {self.floor} or higher" if self.floor > 1 else "no hard limit above Bracket 1"]
        if self.game_changers:
            parts.append(f"{len(self.game_changers)} Game Changer{'s' if len(self.game_changers) != 1 else ''}: {', '.join(self.game_changers)}")
        if self.mass_land_denial:
            parts.append(f"mass land denial: {', '.join(self.mass_land_denial)}")
        if self.extra_turns:
            parts.append(f"extra turns: {', '.join(self.extra_turns)}")
        if self.combos:
            parts.append(f"{len(self.combos)} combo{'s' if len(self.combos) != 1 else ''}: "
                         + ", ".join(f"{c.label()} ({c.tag_name})" for c in self.combos))
        return "; ".join(parts)


def is_mass_land_denial(card: Card) -> bool:
    text = re.sub(r"\s*\([^)]*\)", "", card.oracle_text)  # (reminder text)
    return bool(MASS_LAND_DENIAL.search(text)) and "Land" not in card.type_line


def has_extra_turn(card: Card) -> bool:
    return bool(EXTRA_TURN.search(card.oracle_text))


def bracket_floor(game_changers: int, mass_land_denial: int, combos: Iterable[Combo] = ()) -> int:
    """4 for a deck with mass land denial or more than three Game Changers, 3 for one to three Game Changers, else 1; and never below
    what Spellbook's tag on a combo the deck holds allows (combos.TAG_BRACKET)."""
    floor = 1
    if mass_land_denial or game_changers > MAX_GAME_CHANGERS_BRACKET_3:
        floor = 4
    elif game_changers:
        floor = 3
    return max([floor] + [c.bracket for c in combos if c.bracket is not None])


def analyze(deck: Deck, combos: Iterable[Combo] = ()) -> BracketReport:
    """The Bracket facts of a deck's cards, commanders included, and of the `combos` it holds (combos.py) when the caller found them."""
    cards = deck.commanders + deck.main
    changers = sorted(c.name for c in cards if c.game_changer)
    denial = sorted({c.name for c in cards if is_mass_land_denial(c)})
    extra = sorted({c.name for c in cards if has_extra_turn(c)})
    held = list(combos)
    return BracketReport(changers, denial, extra, bracket_floor(len(changers), len(denial), held), held)


def main(argv: list[str]) -> int:
    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    ask = "--combos" in argv
    paths = [a for a in argv[1:] if a != "--combos"]
    if len(paths) != 1:
        print("usage: python -m infernal_machine.brackets DECKLIST [--combos]", file=sys.stderr)
        return 2
    with open(paths[0], encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(".cache/oracle_bulk.json"))
    combos: list[Combo] = []
    if ask:
        from .combos import SpellbookSource

        try:
            combos = SpellbookSource().find(deck).included
        except OSError as error:
            print(f"Error: Commander Spellbook could not be reached and the cache has no answer for this deck ({error}).", file=sys.stderr)
            return 2
    print(analyze(deck, combos).summary())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
