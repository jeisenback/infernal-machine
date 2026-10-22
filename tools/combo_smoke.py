"""Do the pieces of a combo play together? (a measurement beside play_smoke: that one tries a card alone, this one a combo's cards)

    python tools/combo_smoke.py [--cards .cache/oracle_bulk.json] [--combos .cache/combos.json] [--steps N] [--card NAME]

For each combo in the Commander Spellbook cache whose pieces the engine fully plays, builds a small game (twelve lands; a creature
on the opponent's side), puts the permanents among the pieces onto the battlefield and the rest into hand, then takes the first
cast or activation the game offers, up to a bounded number of steps. A combo that raises an exception, or runs more than a few seconds,
is listed with the error. "Plays together" means the engine does not crash and does not hang: whether the combo reaches its result is
listed beside it when the game ended or the loop ran to the engine's board limit (--all lists every combo with the opponent's life and library), not asserted. A gap never fails the run.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import signal
import sys

sys.path.insert(0, os.getcwd())

from infernal_machine.cards import Card, Deck  # noqa: E402
from infernal_machine.game import ACTIVATE, CAST, BoardLimitReached, Game, Permanent  # noqa: E402
from infernal_machine.report import unsupported_lines  # noqa: E402
from tests.helpers import BEAR, COMMANDER, OGRE, RAINBOW, ScriptedPlayer  # noqa: E402

TIMEOUT_SECONDS = 60
PERMANENT_TYPES = ("Creature", "Artifact", "Enchantment", "Planeswalker", "Land", "Battle")


class Hung(Exception):
    pass


def first_option(prompt: str, options: list[str]) -> int:
    return 0


def run_stack(game: Game) -> None:
    while game.pending or game.stack:
        game._put_triggers_on_stack()
        while game.stack:
            game._resolve(game.stack.pop())
            game._check_state()


def table(pieces: list[Card]) -> tuple[Game, object]:
    players = [ScriptedPlayer("A", first_option), ScriptedPlayer("B", first_option)]
    deck = Deck(commanders=[COMMANDER], main=[RAINBOW] * 20, sideboard=[])
    game = Game([(player, deck) for player in players], seed=1)
    game.turn, game.active, game.step = 2, 0, "main1"
    for seat in game.seats:
        seat.hand, seat.command_zone = [], []
    mine, theirs = game.seats
    mine.battlefield = [Permanent(RAINBOW) for _ in range(12)]
    theirs.battlefield = [Permanent(OGRE), Permanent(BEAR)]
    for card in pieces:
        if any(kind in card.type_line.split(" // ")[0] for kind in PERMANENT_TYPES):
            mine.battlefield.append(Permanent(card, sick=False))
        else:
            mine.hand.append(card)
    return game, mine


def play(pieces: list[Card], steps: int) -> str:
    """Take up to `steps` casts and activations; what the opponent was left with."""
    game, mine = table(pieces)
    theirs = game.seats[1]
    run_stack(game)
    game._check_state()
    taken = 0
    try:
        for _ in range(steps):
            actions = [x for x in game.legal_actions(mine) if x.startswith((CAST, ACTIVATE))]
            if not actions or game.winner() is not None:
                break
            game._perform(mine, actions[0])
            run_stack(game)
            game._check_state()
            taken += 1
    except BoardLimitReached:  # the loop ran away until the engine's own limit ended the game (as a draw, in Game.play)
        return f"{taken} actions, ran to the board limit"
    ended = "game over" if game.winner() is not None else f"opponent at {theirs.life} life, {len(theirs.library)} cards in library"
    return f"{taken} actions, {ended}"


def check(combos: list[dict], cards: dict[str, Card], steps: int, only: str | None = None):
    """(combos tried, [(combo, what happened)], errors -> the combos that raised them)."""
    errors: dict[str, list[str]] = collections.defaultdict(list)
    results = []
    can_time_out = hasattr(signal, "SIGALRM")
    if can_time_out:
        def hang(signum, frame):
            raise Hung()
        signal.signal(signal.SIGALRM, hang)
    for combo in combos:
        pieces = [cards.get(name) for name in combo["cards"]]
        if not all(pieces) or any(unsupported_lines(card) for card in pieces if card):
            continue
        if only is not None and only not in combo["cards"]:
            continue
        label = " + ".join(combo["cards"])
        if can_time_out:
            signal.alarm(TIMEOUT_SECONDS)
        try:
            results.append((combo, play([card for card in pieces if card], steps)))
        except Hung:
            errors["took more than %d seconds" % TIMEOUT_SECONDS].append(label)
        except Exception as error:  # noqa: BLE001 - any failure is what this looks for
            errors[f"{type(error).__name__}: {str(error)[:80]}"].append(label)
        finally:
            if can_time_out:
                signal.alarm(0)
    return len(results) + sum(len(v) for v in errors.values()), results, errors


def cached_combos(path: str) -> list[dict]:
    """Every combo the cache holds, once each (the same combo turns up in several decks)."""
    with open(path, encoding="utf-8") as f:
        decks = json.load(f).get("decks", {})
    seen: dict[str, dict] = {}
    for report in decks.values():
        for combo in report["included"] + report["almost"]:
            seen.setdefault(combo["id"], combo)
    return list(seen.values())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", default=".cache/oracle_bulk.json")
    parser.add_argument("--combos", default=".cache/combos.json")
    parser.add_argument("--steps", type=int, default=40, help="casts and activations to take (default 40)")
    parser.add_argument("--all", action="store_true", help="list every combo, not only those that ended the game or ran to the board limit")
    parser.add_argument("--card", help="only the combos that use this card")
    args = parser.parse_args(argv[1:])
    with open(args.cards, encoding="utf-8") as f:
        cards = {name: Card.from_dict(data) for name, data in json.load(f)["cards"].items()}
    tried, results, errors = check(cached_combos(args.combos), cards, args.steps, args.card)
    failed = sum(len(v) for v in errors.values())
    print(f"## Combo smoke test: {tried - failed} of {tried} combos with every piece playable ran without an error")
    for combo, outcome in results:
        if args.all or outcome.endswith(("game over", "board limit")):
            print(f"- {' + '.join(combo['cards'])} ({', '.join(combo['produces'][:2])}): {outcome}")
    for message, labels in sorted(errors.items(), key=lambda kv: -len(kv[1])):
        print(f"- {len(labels)} x `{message}`: {', '.join(sorted(labels)[:6])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
