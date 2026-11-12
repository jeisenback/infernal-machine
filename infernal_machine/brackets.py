"""Commander Brackets: what a deck's cards say about the power level it has to be played at.

    python -m infernal_machine.brackets DECKLIST

The Brackets (1 Exhibition, 2 Core, 3 Upgraded, 4 Optimized, 5 cEDH) are partly a conversation about intent and partly a set of
hard limits on what a deck may hold. This reads the hard limits off the cards, in the Commander Format Panel's beta guidance as updated
on 21 October 2025 and 9 February 2026 (magic.wizards.com, "Commander Brackets Beta Update"):
- Game Changers (Scryfall's `game_changer` flag, so the list follows Scryfall and is as current as the card cache; 53 cards after the
  February 2026 update, which added Farewell and Biorhythm): none in Brackets 1 and 2, up to three in Bracket 3, any number in 4 and 5.
- Mass land denial: not in Brackets 1 to 3 (found by its Oracle text: it destroys, exiles or returns all lands or sacrifices them).
- Extra turns: chains of them are out below Bracket 4. A deck's extra-turn cards are listed, not counted against it.
- Combos, when the caller asked Commander Spellbook (combos.py): each combo the deck holds carries Spellbook's bracket tag, and the
  floor is at least the highest of them (a Ruthless combo, a two-card one that wins early, is not below Bracket 4).
- Tutors: no limit of their own since the October 2025 update; the most efficient ones are Game Changers.
It can't see how a deck is played, and it can't tell Bracket 1 from 2 or 4 from 5, so `floor` is the lowest bracket a deck can be played
at, never a rating. The guidance also gives each bracket a game length to expect (at least nine turns in Bracket 1, eight in 2, six in
3, four in 4, any in 5), which no card count shows. Treat it as the first thing to check before choosing opponents.

    python -m infernal_machine.brackets DECKLIST --combos    # ask Commander Spellbook too (one request per deck, then cached)
    python -m infernal_machine.brackets DECKLIST --pace      # and how fast the deck kills alone (engine goldfish games)

The pace is the one check that looks at how the deck plays rather than what it holds: the engine plays it alone against a seat that does
nothing (goldfish.py) for 10 of its own turns, and the turn by which it has dealt 40 damage (one opponent's life) in half the games is
compared with the game length each bracket expects (EXPECTED_TURNS). Unopposed, the deck is at its fastest, so a deck that kills sooner
than a bracket's games last is above that bracket's pace; a slower one is not shown to be below anything (real games have blockers,
removal and three opponents). `pace_floor` is reported beside `floor`, never folded into it.
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
EXPECTED_TURNS = {1: 9, 2: 8, 3: 6, 4: 4}  # "play at least N turns before you win or lose" (October 2025 update); Bracket 5: any turn
PACE_TURNS = 10  # one more than Bracket 1's nine
PACE_LIFE = 40  # one opponent's starting life
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


@dataclass
class Pace:
    games: int  # engine games finished
    turns: int  # of the deck's own turns each
    kill_turn: int | None  # the turn by which half the games had dealt PACE_LIFE damage; None: not within `turns`
    dropped: int = 0  # games the engine could not finish, left out

    @property
    def pace_floor(self) -> int:
        """The lowest bracket whose expected game length the deck does not beat alone: 1 when it kills no sooner than nine turns."""
        if self.kill_turn is None:
            return 1
        return min((b for b, expected in EXPECTED_TURNS.items() if self.kill_turn >= expected), default=5)

    def summary(self) -> str:
        if not self.games:
            return "pace: no goldfish game could be finished"
        alone = f"alone and unopposed, {self.games} games of {self.turns} turns"
        if self.kill_turn is None:
            return f"pace: it does not deal {PACE_LIFE} damage within {self.turns} turns in half its games ({alone})"
        faster = [b for b, expected in EXPECTED_TURNS.items() if self.kill_turn < expected]
        verdict = (f"faster than Bracket {', '.join(map(str, faster))} games are expected to last (at least "
                   f"{', '.join(str(EXPECTED_TURNS[b]) for b in faster)} turns)" if faster else "no faster than any bracket expects")
        return f"pace: it deals {PACE_LIFE} damage by turn {self.kill_turn} in half its games ({alone}): {verdict}"


def pace_from_runs(runs: list[dict | None], turns: int = PACE_TURNS) -> Pace:
    """The pace of engine goldfish games (goldfish.play_runs): each finished run's "damage" is the total dealt by each of its turns."""
    finished = [run for run in runs if run is not None]
    kills = sorted(next((turn for turn, dealt in enumerate(run["damage"], 1) if dealt >= PACE_LIFE), turns + 1) for run in finished)
    half = kills[(len(kills) - 1) // 2] if kills else turns + 1  # the median, rounded to the earlier game when the count is even
    return Pace(len(finished), turns, half if half <= turns else None, len(runs) - len(finished))


def pace(deck: Deck, games: int = 40, seed: int = 0, workers: int = 1) -> Pace:
    from .goldfish import play_runs

    return pace_from_runs(play_runs(deck, games, PACE_TURNS, seed, workers=workers))


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
    import argparse

    parser = argparse.ArgumentParser(prog="python -m infernal_machine.brackets", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("decklist")
    parser.add_argument("--combos", action="store_true", help="ask Commander Spellbook which combos the deck holds (then cached)")
    parser.add_argument("--pace", action="store_true", help="play it alone through the engine and set its kill turn against the brackets")
    args = parser.parse_args(argv[1:])
    ask, timed = args.combos, args.pace
    with open(args.decklist, encoding="utf-8") as f:
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
    if timed:
        print(pace(deck).summary())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
