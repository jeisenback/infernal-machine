"""Commander Brackets: what a deck's cards say about the power level it has to be played at.

    python -m infernal_machine.brackets DECKLIST

The Brackets (1 Exhibition, 2 Core, 3 Upgraded, 4 Optimized, 5 cEDH) are partly a conversation about intent and partly a set of
hard limits on what a deck may hold. This reads the hard limits off the cards, in the published guidance as of this writing:
- Game Changers (Scryfall's `game_changer` flag, so the list follows Scryfall): none in Brackets 1 and 2, up to three in Bracket 3,
  any number in 4 and 5.
- Mass land denial: not in Brackets 1 to 3 (found by its Oracle text: it destroys, exiles or returns all lands or sacrifices them).
- Extra turns: chains of them are out below Bracket 4. A deck's extra-turn cards are listed, not counted against it.
It can't see two-card infinite combos or how a deck is played, and it can't tell Bracket 1 from 2 or 4 from 5, so `floor` is the
lowest bracket a deck can be played at, never a rating. Treat it as the first thing to check before choosing opponents.
"""

from __future__ import annotations

import io
import re
import sys
from dataclasses import dataclass

from .cards import Card, Deck

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

    def summary(self) -> str:
        parts = [f"plays at Bracket {self.floor} or higher" if self.floor > 1 else "no hard limit above Bracket 1"]
        if self.game_changers:
            parts.append(f"{len(self.game_changers)} Game Changer{'s' if len(self.game_changers) != 1 else ''}: {', '.join(self.game_changers)}")
        if self.mass_land_denial:
            parts.append(f"mass land denial: {', '.join(self.mass_land_denial)}")
        if self.extra_turns:
            parts.append(f"extra turns: {', '.join(self.extra_turns)}")
        return "; ".join(parts)


def is_mass_land_denial(card: Card) -> bool:
    text = re.sub(r"\s*\([^)]*\)", "", card.oracle_text)  # (reminder text)
    return bool(MASS_LAND_DENIAL.search(text)) and "Land" not in card.type_line


def has_extra_turn(card: Card) -> bool:
    return bool(EXTRA_TURN.search(card.oracle_text))


def bracket_floor(game_changers: int, mass_land_denial: int) -> int:
    """4 for a deck with mass land denial or more than three Game Changers, 3 for one to three Game Changers, else 1."""
    if mass_land_denial or game_changers > MAX_GAME_CHANGERS_BRACKET_3:
        return 4
    return 3 if game_changers else 1


def analyze(deck: Deck) -> BracketReport:
    """The Bracket facts of a deck's cards, commanders included."""
    cards = deck.commanders + deck.main
    changers = sorted(c.name for c in cards if c.game_changer)
    denial = sorted({c.name for c in cards if is_mass_land_denial(c)})
    extra = sorted({c.name for c in cards if has_extra_turn(c)})
    return BracketReport(changers, denial, extra, bracket_floor(len(changers), len(denial)))


def main(argv: list[str]) -> int:
    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) != 2:
        print("usage: python -m infernal_machine.brackets DECKLIST", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(".cache/oracle_bulk.json"))
    print(analyze(deck).summary())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
