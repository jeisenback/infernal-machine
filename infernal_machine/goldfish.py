"""Goldfish through the real engine: the deck alone against a seat that does nothing (issue #390).

    python -m infernal_machine.goldfish DECKLIST [--games 100] [--turns 8] [--seed 0] [--play] [--workers N] [--model-games 1000]

`simulate.py` models mana and creature bodies only; a spell is cast when its cost can be paid and nothing it says is played. This
plays the deck for real: `BotPlayer` plays it in `Game` against an idle second seat (a player who keeps every hand, passes every
priority, never attacks and never plays a card; its life is so high that nothing kills it), and the report is built from what the
engine did, in the same shape as the model's (`simulate.SimStats`), so the two can be shown side by side and the gap between them is
the part of the deck the model cannot see:

- **damage** is the life the idle seat lost by each turn: real combat damage, with removal, tricks, blockers it does not have and
  everything a card's text does, where the model sums every creature's power;
- **mana available and spent**, **land drops**, **colour-stuck**, **on curve** and the per-card table mean what they mean in the model,
  measured at the first main phase of each of the deck's own turns and from the casts the engine made;
- **cards drawn** and **permanents** by turn, which the model has no way to say.

The engine is slow (a game takes seconds, the model's takes milliseconds), so this runs a hundred or so games where the model runs
thousands; `tune` keeps using the model. A card the engine can't read is still cast and its text ignored, so a deck with such cards
gets the same warning as everywhere else. Game `n` has the same seed and shuffles the same way for the same deck, so two builds can
be compared, and `--play` puts the deck on the play (the first player skips their first draw).
"""

from __future__ import annotations

import io
from collections import Counter
import random
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

from .analysis import is_land
from .bot import BotPlayer
from .cards import Card, Deck
from .formats import format_of
from .combat import ATTACK_PROMPT
from .bot import FEATURES, _cast_name
from .game import CAST, CAST_COMMANDER, CAST_EXILE, CAST_GRAVEYARD, CAST_PREPARED, PASS, PLAY_LAND, STEPS, Game, Seat
from .report import unplayable_cards, unplayable_note
from .simulate import SimStats, _blocked_on_colors, _taxed, format_simulation, simulate, summarize

IDLE_LIFE = 10 ** 6  # the idle seat's life: it is never the one that ends the game
TIME_LIMIT = 120.0  # seconds a game may take before it is given up on
FIRST_MAIN = next(step for step in STEPS if "main" in step)
CASTS = (CAST, CAST_COMMANDER, CAST_GRAVEYARD, CAST_EXILE, CAST_PREPARED)



class IdlePlayer(BotPlayer):
    """Keeps its hand and does nothing else: it passes whenever it can and never attacks. (What it is asked about by force, such as a
    discard to hand size, the bot answers.)"""

    def choose(self, prompt: str, options):
        if prompt.startswith(ATTACK_PROMPT):
            return 0
        if PASS in options:
            return list(options).index(PASS)
        return super().choose(prompt, options)


class Pilot(BotPlayer):
    """The bot playing the deck, telling the recorder before each decision it makes (so the recorder can look at the board)."""

    def __init__(self, name: str, deck: Deck, features: frozenset[str] = FEATURES):
        super().__init__(name, deck, features)
        self.before_choice = lambda prompt, options: None
        self.after_choice = lambda prompt, options, choice: None

    def choose(self, prompt: str, options):
        self.before_choice(prompt, options)
        choice = super().choose(prompt, options)
        self.after_choice(prompt, options, choice)
        return choice


class _Done(Exception):
    """The deck has had its turns."""


class _TimedOut(Exception):
    pass


@dataclass
class _Run:
    """What one game records, turn by turn (a turn is one of the deck's own, not a game turn: the idle seat takes the others)."""
    turn: int = 0  # the deck's own turns begun
    missed: bool = False
    landed: bool = False
    spent_now: int = 0
    available_now: int = 0
    available_now_taken: bool = False
    stuck_now: bool = False
    offered_now: set = field(default_factory=set)  # the spells the game offered to cast this turn
    cast_now: list = field(default_factory=list)  # the spells cast this turn


def _idle_deck(like: Deck) -> Deck:
    """The idle seat's deck: as many basic lands as the deck has cards, so that it never runs out of library."""
    wastes = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
    return Deck([], [wastes] * len(like.main), [])


def play_engine_game(deck: Deck, n: int, turns: int, seed: int, on_the_play: bool = False, time_limit: float = TIME_LIMIT,
                     features: frozenset[str] = FEATURES) -> dict:
    """Game number `n` through the engine: a dict like the model's `simulate._play` returns, plus "drawn" and "permanents"."""
    game_seed = zlib.crc32(f"{seed}-{n}".encode())
    first = random.Random(game_seed).randrange(2)  # the engine picks the first player with its first draw from this generator
    focus = first if on_the_play else 1 - first
    pilot = Pilot("deck", deck, features)
    makers: list[BotPlayer] = [IdlePlayer("idle", _idle_deck(deck)), IdlePlayer("idle", _idle_deck(deck))]
    makers[focus] = pilot
    decks = [_idle_deck(deck), _idle_deck(deck)]
    decks[focus] = deck
    game = Game(list(zip(makers, decks)), seed=game_seed, format=format_of([deck]))
    seat, idle = game.seats[focus], game.seats[1 - focus]
    idle.life = IDLE_LIFE
    run = _Run()
    result: dict = {"mulligans": 0, "opening_lands": 0, "land_drops": [], "available": [], "spent": [], "stuck": [], "damage": [],
                    "drawn": [], "permanents": [], "seen": {}, "cast": {}, "casts": {}, "recast": {},
                    "held": {}, "offered": {}, "passed": {}, "passed_turns": {}}
    seen_turn, cast_turn, casts, recast = result["seen"], result["cast"], result["casts"], result["recast"]
    commanders = {c.name for c in deck.commanders}
    for card in deck.commanders:
        seen_turn[card.name] = 0
    drawn = [0]
    held, offered, passed, passed_turns = result["held"], result["offered"], result["passed"], result["passed_turns"]
    deadline = time.monotonic() + time_limit
    forward, take_turn = game.broadcast, game._take_turn

    def tap(event: dict, skip=None) -> None:
        kind = event.get("event")
        if kind == "starting_player" and event["seat"] != first:
            raise RuntimeError("the engine chose a different first player than the goldfish expected")
        if event.get("seat") == focus:
            if kind == "kept":
                result["mulligans"] = event["mulligans"]
                result["opening_lands"] = sum(1 for c in seat.hand if is_land(c))
                for card in seat.hand:
                    if not is_land(card):
                        seen_turn.setdefault(card.name, 0)
            elif kind == "play_land" and event.get("from") is None and game.active == focus:
                run.landed = True
            elif kind == "drew":
                drawn[0] += 1
            elif kind == "cast" and run.turn:
                item = game.stack[-1] if game.stack else None
                paid = item.mana_spent if item is not None and item.card.name == event["card"] else 0
                run.spent_now += paid
                run.cast_now.append(event["card"])
                cast_turn.setdefault(event["card"], run.turn)
                casts[event["card"]] = casts.get(event["card"], 0) + 1
                if casts[event["card"]] == 2 and event["card"] in commanders:
                    recast[event["card"]] = run.turn
        if time.monotonic() > deadline:
            raise _TimedOut
        forward(event, skip)

    def before_choice(prompt: str, options) -> None:
        """At the first decision of the first main phase once the land drop is done (or if there is none to make): the mana the deck
        has this turn, as the model counts it."""
        if game.active == focus and game.step == FIRST_MAIN and PASS in options and not run.available_now_taken \
                and (run.landed or not any(str(option).startswith(PLAY_LAND) for option in options)):
            run.available_now_taken = True
            sources = game.payer._mana_sources(seat)
            run.available_now = len(sources)
            spells = [c for c in seat.hand if not is_land(c)] + [_taxed(c, game.commander_tax(seat, c)) for c in seat.command_zone]
            run.stuck_now = _blocked_on_colors(spells, [source.types for source in sources])
            for card in spells:
                seen_turn.setdefault(card.name, run.turn)
                held[card.name] = held.get(card.name, 0) + 1

    def after_choice(prompt: str, options, choice: int) -> None:
        """On the deck's own turns, every spell the game offers to cast (once a turn each: a spell offered at instant speed is offered in
        the main phase too)."""
        if game.active != focus:
            return
        for option in options:
            if str(option).startswith(CASTS):
                name = _cast_name(str(option))
                offered.setdefault(name, set()).add(run.turn)
                run.offered_now.add(name)

    def turn_taken(active: Seat) -> None:
        if active is seat:
            run.turn += 1
            run.landed = False
            run.spent_now = 0
            run.available_now_taken = False
            run.offered_now, run.cast_now = set(), []
        try:
            take_turn(active)
        finally:
            if active is seat:
                for name in run.offered_now - set(run.cast_now):  # offered this turn and not cast: what it cast instead
                    passed_turns[name] = passed_turns.get(name, 0) + 1
                    for other in set(run.cast_now) or {None}:
                        passed.setdefault(name, Counter())[f"cast {other}" if other else "cast nothing"] += 1
                run.missed = run.missed or not run.landed
                result["land_drops"].append(not run.missed)
                result["available"].append(run.available_now)
                result["spent"].append(run.spent_now)
                result["stuck"].append(run.stuck_now)
                result["damage"].append(IDLE_LIFE - idle.life)
                result["drawn"].append(drawn[0])
                result["permanents"].append(len(seat.battlefield))
        if active is seat and run.turn >= turns:
            raise _Done

    game.broadcast = tap  # type: ignore[method-assign]
    game._take_turn = turn_taken  # type: ignore[method-assign]
    pilot.before_choice = before_choice
    pilot.after_choice = after_choice
    try:
        game.play(max_turns=10 ** 6)
    except _Done:
        pass
    while len(result["damage"]) < turns:  # the deck's game ended before its last turn (it lost, or the board limit): nothing more happens
        result["land_drops"].append(not run.missed)
        for key in ("available", "spent"):
            result[key].append(0)
        result["stuck"].append(False)
        result["damage"].append(result["damage"][-1] if result["damage"] else 0)
        result["drawn"].append(drawn[0])
        result["permanents"].append(len(seat.battlefield))
    return result


def _run_one(task: tuple) -> dict | None:
    deck, n, turns, seed, on_the_play, time_limit, features = task
    try:
        return play_engine_game(deck, n, turns, seed, on_the_play, time_limit, features)
    except (_TimedOut, Exception):  # a game the engine could not finish is left out, and counted
        return None


def play_runs(deck: Deck, games: int = 100, turns: int = 8, seed: int = 0, on_the_play: bool = False, workers: int = 1,
              time_limit: float = TIME_LIMIT, features: frozenset[str] = FEATURES) -> list[dict | None]:
    """The engine games themselves, one record each (None for a game that could not be finished). `features` are the bot's judgments."""
    tasks = [(deck, n, turns, seed, on_the_play, time_limit, features) for n in range(games)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(_run_one, tasks, chunksize=1))
    return [_run_one(task) for task in tasks]


def goldfish(deck: Deck, games: int = 100, turns: int = 8, seed: int = 0, on_the_play: bool = False, workers: int = 1,
             time_limit: float = TIME_LIMIT, features: frozenset[str] = FEATURES) -> SimStats:
    """Play `deck` alone through the engine `games` times for `turns` of its own turns and report like `simulate`."""
    runs = play_runs(deck, games, turns, seed, on_the_play, workers, time_limit, features)
    finished = [run for run in runs if run is not None]
    stats = summarize(deck, finished, turns)
    stats.dropped = len(runs) - len(finished)
    return stats


def format_gap(model: SimStats, engine: SimStats) -> str:
    """The model and the engine goldfish side by side: where they differ is what the model cannot see."""
    last = engine.turns
    rows = [("mulligan rate", f"{model.mulligan_rate:.1%}", f"{engine.mulligan_rate:.1%}"),
            ("mana spent / available", f"{model.mana_efficiency:.0%}", f"{engine.mana_efficiency:.0%}"),
            ("on curve", _percent(model.on_curve), _percent(engine.on_curve)),
            (f"land drops through turn {last // 2}", f"{model.land_drop_rate[last // 2]:.1%}", f"{engine.land_drop_rate[last // 2]:.1%}")]
    rows += [(f"damage by turn {turn}", f"{model.damage[turn]:.1f}", f"{engine.damage[turn]:.1f}") for turn in sorted({last // 2, last})]
    lines = [f"{'':<28}{'model':>10}  {'engine':>10}"] + [f"{name:<28}{a:>10}  {b:>10}" for name, a, b in rows]
    lines += ["", f"The model ({model.games} games) sums every creature's power from the turn after it enters; the engine ({engine.games} games) "
                  "is the damage that got through, with every card's text played as far as the engine reads it."]
    return "\n".join(lines)


def unreadable_warning(deck: Deck) -> str | None:
    """The sentence that warns about cards the engine can't fully play (their text is ignored), or None."""
    unplayable = unplayable_cards(deck)
    return unplayable_note(unplayable, "This deck") if unplayable else None


def _percent(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else "-"


def format_goldfish(stats: SimStats) -> str:
    text = format_simulation(stats)
    text = text.replace("Card text is not played here, only mana and creature bodies: removal, card draw and the like show up as mana spent.",
                        "Played through the engine against a seat that does nothing: damage is what the idle seat lost.")
    extra = ["", "turn  cards drawn  permanents"] + [f"{turn:>4}  {stats.drawn[turn]:>11.1f}  {stats.permanents[turn]:>10.1f}" for turn in range(1, stats.turns + 1)]
    notes = [f"{stats.dropped} game(s) could not be finished and are left out."] if stats.dropped else []
    head, _, tail = text.partition("\ncard ")
    return "\n".join([head, *extra, "", "card " + tail, *([""] + notes if notes else [])]) if tail else "\n".join([text, *extra, *notes])


def main(argv: list[str]) -> int:
    import argparse
    import os

    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--play", action="store_true", help="be on the play (no draw on turn 1)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--model-games", type=int, default=1000, help="games of the fast model to show beside it (0 to skip)")
    parser.add_argument("--time-limit", type=float, default=TIME_LIMIT, help="seconds per game")
    parser.add_argument("--features", help="the bot's judgments, comma separated (default: all; see bots.md), to see what one of them does")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv[1:])
    with open(args.decklist, encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(args.bulk))
    engine = goldfish(deck, args.games, args.turns, args.seed, args.play, args.workers, args.time_limit,
                      frozenset(part for part in args.features.split(",") if part) if args.features is not None else FEATURES)
    print(format_goldfish(engine))
    if args.model_games:
        print("\n" + format_gap(simulate(deck, args.model_games, args.turns, args.seed, args.play), engine))
    if warning := unreadable_warning(deck):
        print("\n" + warning)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
