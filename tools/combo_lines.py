"""Does a combo's loop run in the engine, and what does it come to? (issue #534; a measurement beside combo_smoke, it never fails)

    python tools/combo_lines.py [--cards .cache/oracle_bulk.json] [--rounds 12] [--card NAME]

`combo_smoke` takes the first action the game offers, which never runs a loop. Here each combo that a tracked deck holds and the
engine plays has a line: where Commander Spellbook says its pieces start (battlefield, hand, graveyard, command zone), the few real
cards the loop needs besides them, and the loop itself as the list of actions Spellbook's steps name, taken in order, round after
round. The result of a line is one of:

    wins        the opponent lost the game (life, cards)
    runs        every round was offered and paid; the number shows what a round leaves behind
    stops       an action Spellbook's steps name was not offered, at this round, and which
    raises      an exception

A line that "runs" says only that the engine can repeat the loop. What the loop produces (infinite mana, infinite ETB triggers) has
no payoff in the engine, so the table says which resource grew and by how much per round, not that the combo "works".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Callable

sys.path.insert(0, os.getcwd())

from infernal_machine.cards import Card  # noqa: E402
from infernal_machine.effects.outcomes import SQUIRREL, TREASURE  # noqa: E402
from infernal_machine.game import BoardLimitReached, Game, LoopDraw, Permanent, Seat  # noqa: E402
from infernal_machine.shortcut import Shortcut, pick, take  # noqa: E402
from tools.combo_smoke import table  # noqa: E402

Measure = Callable[[Game, Seat], int]


@dataclass
class Line:
    combo: str  # the pieces, " + "-joined as Commander Spellbook names them
    result: str  # what Spellbook says it produces, in a few words
    battlefield: tuple[str, ...] = ()
    hand: tuple[str, ...] = ()
    graveyard: tuple[str, ...] = ()
    attach: tuple[tuple[str, str], ...] = ()  # (aura, the permanent it is on), both on the battlefield
    opponents: int = 1
    lands: int = 0  # City of Brass the table starts with: none unless the loop needs mana to start
    library: int = 0  # cards in the library of the player running the loop (the table's is 20)
    setup: Callable[[Game, Seat], None] | None = None  # extra tokens or counters, put on the table before the loop
    commander: str = ""  # a piece that is the player's commander
    start: Callable[[Game, Seat], None] | None = None  # what sets the loop going, when no action does
    loop: tuple[str, ...] = ()  # one action per entry: the first legal action containing it
    answers: tuple[str, ...] = ("Player: B",)  # for every other question: the first option containing one of these ("about~wanted": only in a question containing "about"), else the first
    measure: Measure | None = None
    unit: str = ""
    cost: int | None = None  # a mana loop: what each round pays, against the measure (what one tap of its sources yields)
    rounds: int | None = None
    note: str = ""


def lose_a_life(game: Game, mine: Seat) -> None:
    game.change_life(game.seats[1], -1)


def draw_a_card(game: Game, mine: Seat) -> None:
    game.draw(mine, 1)


def opponent_life(game: Game, mine: Seat) -> int:
    return game.seats[1].life


def mana_yield(game: Game, mine: Seat) -> int:
    return len(game._mana_sources(mine))


def my_library(game: Game, mine: Seat) -> int:
    return len(mine.library)


def squirrels(game: Game, mine: Seat) -> None:
    game.create_tokens(mine, SQUIRREL, 1)


def goblins(count: int) -> Callable[[Game, Seat], None]:
    def make(game: Game, mine: Seat) -> None:
        game.create_tokens(mine, Card(name="Goblin", type_line="Token Creature \u2014 Goblin", colors=("R",), power="1", toughness="1"), count)
    return make


def board(game: Game, mine: Seat) -> int:
    return sum(1 for p in mine.battlefield if p.card.name != "City of Brass")


def my_life(game: Game, mine: Seat) -> int:
    return mine.life


SKELETON = "Activate from graveyard: Reassembling Skeleton"


LINES: list[Line] = [
    Line("Sanguine Bond + Exquisite Blood", "infinite life loss", ("Sanguine Bond", "Exquisite Blood"), start=lose_a_life, measure=opponent_life, unit="opponent life"),
    Line("Vito, Thorn of the Dusk Rose + Exquisite Blood", "infinite life loss", ("Vito, Thorn of the Dusk Rose", "Exquisite Blood"), start=lose_a_life, measure=opponent_life, unit="opponent life"),
    Line("Vito, Thorn of the Dusk Rose + Bloodthirsty Conqueror", "infinite life loss", ("Vito, Thorn of the Dusk Rose", "Bloodthirsty Conqueror"), start=lose_a_life, measure=opponent_life, unit="opponent life"),
    Line("Sanguine Bond + Bloodthirsty Conqueror", "infinite life loss", ("Sanguine Bond", "Bloodthirsty Conqueror"), start=lose_a_life, measure=opponent_life, unit="opponent life"),
    Line("Curiosity + Niv-Mizzet, Parun", "infinite draws and damage", ("Niv-Mizzet, Parun", "Curiosity"), attach=(("Curiosity", "Niv-Mizzet, Parun"),), library=80, start=draw_a_card, measure=opponent_life, unit="opponent life"),
    Line("Niv-Mizzet, Parun + Ophidian Eye", "infinite draws and damage", ("Niv-Mizzet, Parun", "Ophidian Eye"), attach=(("Ophidian Eye", "Niv-Mizzet, Parun"),), library=80, start=draw_a_card, measure=opponent_life, unit="opponent life"),
    Line("Niv-Mizzet, the Firemind + Curiosity", "infinite draws and damage", ("Niv-Mizzet, the Firemind", "Curiosity"), attach=(("Curiosity", "Niv-Mizzet, the Firemind"),), library=80, start=draw_a_card, measure=opponent_life, unit="opponent life"),
    Line("Niv-Mizzet, the Firemind + Ophidian Eye", "infinite draws and damage", ("Niv-Mizzet, the Firemind", "Ophidian Eye"), attach=(("Ophidian Eye", "Niv-Mizzet, the Firemind"),), library=80, start=draw_a_card, measure=opponent_life, unit="opponent life"),
    Line("Kinnan, Bonder Prodigy + Basalt Monolith", "infinite colorless mana", ("Kinnan, Bonder Prodigy", "Basalt Monolith"), loop=("{3}: Untap this artifact",), measure=mana_yield, cost=3),
    Line("Basalt Monolith + Nyxbloom Ancient", "infinite colorless mana", ("Basalt Monolith", "Nyxbloom Ancient"), loop=("{3}: Untap this artifact",), measure=mana_yield, cost=3),
    Line("Bloom Tender + Freed from the Real", "infinite mana of the deck's colors", ("Bloom Tender", "Freed from the Real"), attach=(("Freed from the Real", "Bloom Tender"),), loop=("Untap enchanted creature",), measure=mana_yield, cost=1),
    Line("Kinnan, Bonder Prodigy + Freed from the Real", "infinite blue mana", ("Kinnan, Bonder Prodigy", "Birds of Paradise", "Freed from the Real"), attach=(("Freed from the Real", "Birds of Paradise"),), loop=("Untap enchanted creature",), measure=mana_yield, cost=1, note="Birds of Paradise is the mana dork"),
    Line("Nyxbloom Ancient + Freed from the Real", "infinite blue mana", ("Nyxbloom Ancient", "Birds of Paradise", "Freed from the Real"), attach=(("Freed from the Real", "Birds of Paradise"),), loop=("Untap enchanted creature",), measure=mana_yield, cost=1, note="Birds of Paradise is the mana dork"),
    Line("Kinnan, Bonder Prodigy + Delighted Halfling + Freed from the Real", "infinite mana for legendary spells", ("Kinnan, Bonder Prodigy", "Delighted Halfling", "Freed from the Real"), attach=(("Freed from the Real", "Delighted Halfling"),), loop=("Untap enchanted creature",), measure=mana_yield, cost=1),
    Line("Derevi, Empyrial Tactician + Emiel the Blessed + Gaea's Cradle", "infinite untaps, blinks and ETBs", ("Derevi, Empyrial Tactician", "Emiel the Blessed", "Gaea's Cradle", "Memnite"), loop=("{3}: Exile another target",), answers=("Pay the cost~Don't pay", "for Emiel~Derevi", "Tap or untap~Untap", "for Derevi~Gaea's Cradle"), measure=mana_yield, cost=3),
    Line("Derevi, Empyrial Tactician + Emiel the Blessed + Bloom Tender", "infinite untaps, blinks and ETBs", ("Derevi, Empyrial Tactician", "Emiel the Blessed", "Bloom Tender"), loop=("{3}: Exile another target",), answers=("Pay the cost~Don't pay", "for Emiel~Derevi", "Tap or untap~Untap", "for Derevi~Bloom Tender"), measure=mana_yield, cost=3),
    Line("Derevi, Empyrial Tactician + Emiel the Blessed + Mana Vault", "infinite creature ETB and LTB", ("Derevi, Empyrial Tactician", "Emiel the Blessed", "Mana Vault"), loop=("{3}: Exile another target",), answers=("Pay the cost~Don't pay", "for Emiel~Derevi", "Tap or untap~Untap", "for Derevi~Mana Vault"), measure=mana_yield, cost=3),
    Line("Derevi, Empyrial Tactician + Emiel the Blessed + Faeburrow Elder", "infinite untaps, blinks and ETBs", ("Derevi, Empyrial Tactician", "Emiel the Blessed", "Faeburrow Elder"), loop=("{3}: Exile another target",), answers=("Pay the cost~Don't pay", "for Emiel~Derevi", "Tap or untap~Untap", "for Derevi~Faeburrow Elder"), measure=mana_yield, cost=3),
    Line("Derevi, Empyrial Tactician + Emiel the Blessed + Selvala, Heart of the Wilds", "infinite untaps, blinks and ETBs", ("Derevi, Empyrial Tactician", "Emiel the Blessed", "Selvala, Heart of the Wilds"), lands=1, loop=("{3}: Exile another target",), answers=("Pay the cost~Don't pay", "for Emiel~Derevi", "Tap or untap~Untap", "for Derevi~Selvala")),
    Line("Selvala, Heart of the Wilds + Emiel the Blessed + Tyvar, Jubilant Brawler", "infinite ETBs and mana", ("Selvala, Heart of the Wilds", "Emiel the Blessed", "Tyvar, Jubilant Brawler"), lands=1, loop=("{3}: Exile another target",), answers=("Pay the cost~Don't pay", "for Emiel~Selvala",)),

    Line("Pitiless Plunderer + Ashnod's Altar + Reassembling Skeleton", "infinite colorless mana and death triggers", ("Pitiless Plunderer", "Ashnod's Altar", "Reassembling Skeleton"), loop=("Ashnod's Altar", SKELETON), answers=("Reassembling Skeleton",), measure=lambda g, m: len(m.mana_pool), unit="mana left over", rounds=6),
    Line("Pitiless Plunderer + Reassembling Skeleton + Phyrexian Altar", "infinite death triggers", ("Pitiless Plunderer", "Reassembling Skeleton", "Phyrexian Altar"), loop=("Phyrexian Altar", SKELETON), answers=("Reassembling Skeleton",), measure=lambda g, m: len(m.mana_pool), unit="mana left over", rounds=6),
    Line("Warren Soultrader + Pitiless Plunderer + Reassembling Skeleton + Blood Artist", "infinite drain", ("Warren Soultrader", "Pitiless Plunderer", "Reassembling Skeleton", "Blood Artist"), loop=("Warren Soultrader", SKELETON), answers=("Reassembling Skeleton", "Player: B"), measure=opponent_life, unit="opponent life", rounds=60),
    Line("Warren Soultrader + Pitiless Plunderer + Zulaport Cutthroat + Reassembling Skeleton", "infinite drain", ("Warren Soultrader", "Pitiless Plunderer", "Zulaport Cutthroat", "Reassembling Skeleton"), loop=("Warren Soultrader", SKELETON), answers=("Reassembling Skeleton", "Player: B"), measure=opponent_life, unit="opponent life", rounds=60),
    Line("Warren Soultrader + Zulaport Cutthroat + Chatterfang, Squirrel General", "infinite drain", ("Warren Soultrader", "Zulaport Cutthroat", "Chatterfang, Squirrel General", "Memnite"), loop=("Warren Soultrader",), answers=("Squirrel 1/1", "Memnite", "Player: B"), measure=opponent_life, unit="opponent life", rounds=60),
    Line("Warren Soultrader + Blood Artist + Chatterfang, Squirrel General", "infinite drain", ("Warren Soultrader", "Blood Artist", "Chatterfang, Squirrel General", "Memnite"), loop=("Warren Soultrader",), answers=("Squirrel 1/1", "Memnite", "Player: B"), measure=opponent_life, unit="opponent life", rounds=60),
    Line("Chatterfang, Squirrel General + Warren Soultrader + Academy Manufactor", "infinite tokens", ("Chatterfang, Squirrel General", "Warren Soultrader", "Academy Manufactor", "Memnite"), loop=("Warren Soultrader",), answers=("Squirrel 1/1", "Memnite"), measure=board, unit="permanents", rounds=8),
    Line("Chatterfang, Squirrel General + Pitiless Plunderer", "infinite artifact ETB and LTB", ("Chatterfang, Squirrel General", "Pitiless Plunderer"), lands=1, setup=squirrels, loop=("Chatterfang",), answers=("Choose X~1", "Ogre", "Squirrel 1/1"), measure=board, unit="permanents", rounds=8),
    Line("Krenko, Mob Boss + Skirk Prospector + Goblin Warchief", "infinite goblins", ("Krenko, Mob Boss", "Skirk Prospector", "Goblin Warchief"), commander="Krenko, Mob Boss", setup=goblins(4), loop=("{T}: Create X 1/1 red Goblin", "Skirk Prospector until Cast commander: Krenko", "Cast commander: Krenko"), answers=("Yes", "Krenko, Mob Boss", "Goblin 1/1", "Goblin 2/2"), measure=board, unit="permanents", rounds=4),
    Line("Krenko, Mob Boss + Skirk Prospector + Goblin Chieftain", "infinite goblins", ("Krenko, Mob Boss", "Skirk Prospector", "Goblin Chieftain"), commander="Krenko, Mob Boss", setup=goblins(4), loop=("{T}: Create X 1/1 red Goblin", "Skirk Prospector until Cast commander: Krenko", "Cast commander: Krenko"), answers=("Yes", "Krenko, Mob Boss", "Goblin 1/1", "Goblin 2/2"), measure=board, unit="permanents", rounds=4),
    Line("Krenko, Mob Boss + Skirk Prospector + Thousand-Year Elixir", "infinite goblins", ("Krenko, Mob Boss", "Skirk Prospector", "Thousand-Year Elixir"), commander="Krenko, Mob Boss", setup=goblins(4), loop=("{T}: Create X 1/1 red Goblin", "Skirk Prospector until Cast commander: Krenko", "Cast commander: Krenko"), answers=("Yes", "Krenko, Mob Boss", "Goblin 1/1", "Goblin 2/2"), measure=board, unit="permanents", rounds=4),
    Line("Skirk Prospector + Krenko, Mob Boss + Staff of Domination", "infinite goblins", ("Skirk Prospector", "Krenko, Mob Boss", "Staff of Domination"), setup=goblins(4), loop=("{T}: Create X 1/1 red Goblin", "Skirk Prospector", "Skirk Prospector", "Skirk Prospector", "Skirk Prospector", "{3}, {T}: Untap target creature", "{1}: Untap this artifact"), answers=("for Staff~Krenko, Mob Boss", "Goblin 1/1"), measure=board, unit="permanents", rounds=4),
    Line("Hullbreaker Horror + Sol Ring", "infinite colorless mana and storm", ("Hullbreaker Horror", "Sol Ring"), hand=("Metallic Sliver",), loop=("Cast: Metallic Sliver", "Cast: Sol Ring"), answers=("Sol Ring", "Metallic Sliver"), measure=lambda g, m: len(m.mana_pool), unit="mana left over", rounds=4, note="Metallic Sliver is the permanent cast for {C}"),
    Line("Hullbreaker Horror + Mana Vault", "infinite colorless mana and storm", ("Hullbreaker Horror", "Mana Vault"), hand=("Viridian Claw",), loop=("Cast: Viridian Claw", "Cast: Mana Vault"), answers=("Mana Vault", "Viridian Claw"), measure=lambda g, m: len(m.mana_pool), unit="mana left over", rounds=4, note="Viridian Claw is the permanent cast for {C}{C}"),
    Line("Hullbreaker Horror + Mox Amber", "infinite ETB, LTB and colored mana", ("Hullbreaker Horror", "Mox Amber", "Kinnan, Bonder Prodigy"), hand=("Kraken Hatchling",), loop=("Cast: Kraken Hatchling", "Cast: Mox Amber"), answers=("Mox Amber", "Kraken Hatchling"), rounds=4, note="Kinnan is the colored legendary creature; Kraken Hatchling costs {U}"),
    Line("Hullbreaker Horror", "infinite ETB and LTB", ("Hullbreaker Horror", "Ornithopter"), hand=("Memnite",), loop=("Cast: Memnite", "Cast: Ornithopter"), answers=("Memnite", "Ornithopter"), measure=board, unit="permanents", rounds=4, note="Memnite and Ornithopter are the two permanents cast for {0}"),
    Line("Tidespout Tyrant + Sol Ring", "infinite colorless mana and storm", ("Tidespout Tyrant", "Metallic Sliver"), hand=("Sol Ring",), lands=1, loop=("Cast: Sol Ring", "Cast: Metallic Sliver"), answers=("Sol Ring", "Metallic Sliver"), measure=lambda g, m: len(m.mana_pool), unit="mana left over", rounds=4, note="Metallic Sliver is the permanent cast for {C}"),
    Line("Tidespout Tyrant + Mana Vault", "infinite colorless mana and storm", ("Tidespout Tyrant", "Viridian Claw"), hand=("Mana Vault",), lands=1, loop=("Cast: Mana Vault", "Cast: Viridian Claw"), answers=("Mana Vault", "Viridian Claw"), measure=lambda g, m: len(m.mana_pool), unit="mana left over", rounds=4, note="Viridian Claw is the permanent cast for {C}{C}"),
    Line("Tidespout Tyrant + Mox Amber", "infinite storm", ("Tidespout Tyrant", "Kraken Hatchling", "Kinnan, Bonder Prodigy"), hand=("Mox Amber",), lands=1, loop=("Cast: Mox Amber", "Cast: Kraken Hatchling"), answers=("Mox Amber", "Kraken Hatchling"), measure=board, unit="permanents", rounds=4, note="Kinnan is the colored legendary creature; Kraken Hatchling costs {U}"),
    Line("Tidespout Tyrant + Mox Opal", "infinite storm", ("Tidespout Tyrant", "Kraken Hatchling", "Metallic Sliver", "Sol Ring"), hand=("Mox Opal",), loop=("Cast: Mox Opal", "Cast: Kraken Hatchling"), answers=("Mox Opal", "Kraken Hatchling"), measure=board, unit="permanents", rounds=4, note="Metallic Sliver and Sol Ring with Mox Opal make three artifacts"),
    Line("Faerie Mastermind + Smothering Tithe + Kinnan, Bonder Prodigy", "infinite draws and Treasures", ("Faerie Mastermind", "Smothering Tithe", "Kinnan, Bonder Prodigy"), opponents=3, lands=4, library=80, loop=("{3}{U}: Each player draws",), answers=("No",), measure=lambda g, m: sum(1 for p in m.battlefield if p.card.name == "Treasure"), unit="Treasures", rounds=6, note="three opponents who cannot pay {2}"),
]


def build(line: Line, cards: dict[str, Card]) -> tuple[Game, Seat]:
    game, mine = table([], line.opponents)
    mine.battlefield = [p for p in mine.battlefield if line.lands > 0 and p.card.name == "City of Brass"][:line.lands]
    placed: dict[str, Permanent] = {}
    for name in line.battlefield:
        placed[name] = Permanent(cards[name], sick=False)
        mine.battlefield.append(placed[name])
    for aura, onto in line.attach:
        placed[aura].attached_to = placed[onto]
    mine.hand = [cards[name] for name in line.hand]
    mine.graveyard = [cards[name] for name in line.graveyard]
    if line.commander:
        mine.commander_names = {line.commander}
    if line.setup:
        line.setup(game, mine)
    if line.library:
        mine.library = [cards["Memnite"]] * line.library
    for seat in game.seats:
        seat.player.policy = answer(line.answers)
    game.resolve_stack()
    return game, mine


def answer(preferred: tuple[str, ...]) -> Callable[[str, list[str]], int]:
    """A policy for a scripted player: the shortcut's own way of picking, else the first option."""
    def policy(prompt: str, options: list[str]) -> int:
        chosen = pick(preferred, prompt, options)
        return 0 if chosen is None else chosen
    return policy


def run(line: Line, cards: dict[str, Card], rounds: int) -> str:
    game, mine = build(line, cards)
    opponent = game.seats[1]
    before = line.measure(game, mine) if line.measure else 0
    try:
        if line.start:
            line.start(game, mine)
            game.resolve_stack()
        if opponent.lost or game.winner() is not None:
            return "wins once started"
        played = take(game, mine, Shortcut(line.loop, line.answers), rounds)
        if played.over and (opponent.lost or game.winner() is not None):
            return f"wins in round {played.rounds}"
        if played.stopped:
            return f"stops in {played.stopped}"
    except BoardLimitReached:
        return "runs to the board limit"
    except LoopDraw:
        return "ends as a draw by a loop"
    if not line.loop:  # the start sets it going and the triggers do the rest
        after = line.measure(game, mine) if line.measure else 0
        return f"ends on its own, {line.unit} {before} to {after}"
    after = line.measure(game, mine) if line.measure else 0
    if line.cost is not None:  # read before the loop: the pool pays first, so what is left after it depends on the round
        return f"runs {rounds} rounds; one tap yields {before} mana, a round pays {line.cost} ({before - line.cost:+d})"
    gain = f", {line.unit} {before} to {after}" if line.measure else ""
    return f"runs {rounds} rounds{gain}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", default=".cache/oracle_bulk.json")
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--card", help="only the combos that use this card")
    args = parser.parse_args(argv)
    with open(args.cards, encoding="utf-8") as f:
        cards = {name: Card.from_dict(data) for name, data in json.load(f)["cards"].items()}
    print("| combo | Spellbook says | the engine |\n|---|---|---|")
    for line in LINES:
        if args.card and args.card not in line.combo:
            continue
        try:
            outcome = run(line, cards, line.rounds or args.rounds)
        except Exception as error:  # noqa: BLE001 - any failure is what this looks for
            outcome = f"raises {type(error).__name__}: {str(error)[:80]}"
        print(f"| {line.combo} | {line.result} | {outcome} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
