"""Does every card the report calls fully playable actually play? (the second half of the coverage audit)

    python tools/play_smoke.py [--pool .cache/commander_pool.json] [--limit N]

For each Commander-legal card whose lines the engine understands, builds a small game (twelve lands, a creature of each side,
something in each graveyard), casts or plays the card, runs the stack, then activates up to three of its abilities, always taking
the first option the game offers. A card that raises an exception, or takes more than a few seconds, is listed with the error.
"Plays" means the engine does not crash and does not hang: whether each effect is right is for the card's tests.
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
from infernal_machine.combat import Attack  # noqa: E402
from infernal_machine.effects import foretell_of, is_aftermath, morph_of, ninjutsu_of  # noqa: E402
from infernal_machine.game import ACTIVATE, CAST, CAST_EXILE, CAST_FACE_DOWN, CAST_FORETOLD, CAST_GRAVEYARD, FORETELL, NINJUTSU, PLAY_LAND, TURN_UP, Game, Permanent  # noqa: E402
from infernal_machine.report import unsupported_lines  # noqa: E402
from tests.test_effects import BEAR, COMMANDER, FOREST, OGRE, RAINBOW  # noqa: E402
from tests.test_game import ScriptedPlayer  # noqa: E402
from tests.test_more_triggers import run_stack  # noqa: E402

TIMEOUT_SECONDS = 5


class Hung(Exception):
    pass


def first_option(prompt: str, options: list[str]) -> int:
    return 0


def table(card: Card) -> tuple[Game, object]:
    """Seat 0 has `card` and a land in hand, twelve lands and an untapped creature; seat 1 a couple of creatures."""
    players = [ScriptedPlayer("A", first_option), ScriptedPlayer("B", first_option)]
    deck = Deck(commanders=[COMMANDER], main=[FOREST] * 20, sideboard=[])
    game = Game([(player, deck) for player in players], seed=1)
    game.turn, game.active, game.step = 2, 0, "main1"
    for seat in game.seats:
        seat.hand, seat.command_zone = [], []
    mine, theirs = game.seats
    mine.battlefield = [Permanent(RAINBOW) for _ in range(12)] + [Permanent(BEAR, sick=False)]
    theirs.battlefield = [Permanent(OGRE), Permanent(BEAR)]
    mine.hand = [card, FOREST]
    mine.graveyard, theirs.graveyard = [BEAR], [OGRE]
    return game, mine


def play(card: Card) -> bool:
    """Cast or play the card and use some of its abilities; True if there was a way to cast or play it."""
    game, mine = table(card)
    name = card.name.split(" // ")[0]
    ways = [x for x in game.legal_actions(mine) if name in x and x.startswith((CAST, PLAY_LAND))]
    if ways:
        game._perform(mine, ways[0])
        run_stack(game)
    game._check_state()
    for _ in range(3):
        abilities = [x for x in game.legal_actions(mine) if x.startswith(ACTIVATE) and name in x]
        if not abilities:
            break
        game._perform(mine, abilities[0])
        run_stack(game)
    return bool(ways) | play_other_half(card) | play_face_down(card) | play_transformed(card) | play_ninjutsu(card) | play_foretell(card)


def play_other_half(card: Card) -> bool:
    """Cast the card's other half (an Adventure, a split half) and, if it went on an adventure, the creature from exile."""
    if card.alternate is None:
        return False
    game, mine = table(card)
    if is_aftermath(card.alternate):  # cast from the graveyard, where the card goes first
        mine.hand.remove(card)
        mine.graveyard.append(card)
        way = CAST_GRAVEYARD + card.alternate.name
    else:
        way = CAST + card.alternate.name
    if way not in game.legal_actions(mine):
        return False
    game._perform(mine, way)
    run_stack(game)
    game._check_state()
    if CAST_EXILE + card.name in game.legal_actions(mine):
        game._perform(mine, CAST_EXILE + card.name)
        run_stack(game)
        game._check_state()
    return True


def play_transformed(card: Card) -> bool:
    """Put a transforming card onto the battlefield, turn it over, use its back face's abilities and turn it back."""
    if card.flip is None or "Land" in card.type_line:
        return False
    game, mine = table(card)
    game._enter(mine, Permanent(card, sick=False))
    run_stack(game)
    permanent = next(p for p in mine.battlefield if p.card is card)
    game.transform(permanent, by_day_night=True)
    run_stack(game)
    game._check_state()
    for _ in range(3):
        abilities = [x for x in game.legal_actions(mine) if x.startswith(ACTIVATE) and card.flip.name in x]
        if not abilities:
            break
        game._perform(mine, abilities[0])
        run_stack(game)
    if game.on_battlefield(permanent):
        game.transform(permanent, by_day_night=True)
        game._check_state()
    return True


def play_foretell(card: Card) -> bool:
    """Foretell the card, and cast it from exile on the next turn when it can be."""
    if foretell_of(card) is None:
        return False
    game, mine = table(card)
    if FORETELL + card.name not in game.legal_actions(mine):
        return False
    game._perform(mine, FORETELL + card.name)
    game.turn += 1
    for permanent in mine.battlefield:
        permanent.tapped = False
    if CAST_FORETOLD + card.name in game.legal_actions(mine):
        game._perform(mine, CAST_FORETOLD + card.name)
        run_stack(game)
        game._check_state()
    return True


def play_ninjutsu(card: Card) -> bool:
    """Attack with a creature, and once blockers are declared use the card's ninjutsu in its place."""
    if ninjutsu_of(card) is None:
        return False
    game, mine = table(card)
    attacker = next(p for p in mine.battlefield if p.card is BEAR)
    game.combat.attacks.append(Attack(attacker, mine, game.seats[1]))
    game.step = "declare_blockers"
    if NINJUTSU + card.name not in game.legal_actions(mine):
        return False
    game._perform(mine, NINJUTSU + card.name)
    run_stack(game)
    game._check_state()
    game.step = "combat_damage"
    game.combat.deal_damage(first_strike_step=False)
    run_stack(game)
    game._check_state()
    return True


def play_face_down(card: Card) -> bool:
    """Cast a morph card face down, and turn it face up when it can be."""
    if morph_of(card) is None:
        return False
    game, mine = table(card)
    if CAST_FACE_DOWN + card.name not in game.legal_actions(mine):
        return False
    game._perform(mine, CAST_FACE_DOWN + card.name)
    run_stack(game)
    game._check_state()
    for permanent in mine.battlefield:
        permanent.tapped = False
    up = [x for x in game.legal_actions(mine) if x.startswith(TURN_UP)]
    if up:
        game._perform(mine, up[0])
        run_stack(game)
        game._check_state()
    return True


def check(pool: list[dict], limit: int | None = None) -> tuple[int, int, dict[str, list[str]]]:
    """(cards tried, cards that could be cast or played, errors -> the cards that raised them)."""
    errors: dict[str, list[str]] = collections.defaultdict(list)
    tried = cast = 0
    can_time_out = hasattr(signal, "SIGALRM")
    if can_time_out:
        def hang(signum, frame):
            raise Hung()
        signal.signal(signal.SIGALRM, hang)
    for data in pool:
        card = Card.from_scryfall(data)
        if unsupported_lines(card):
            continue
        if limit is not None and tried >= limit:
            break
        tried += 1
        if can_time_out:
            signal.alarm(TIMEOUT_SECONDS)
        try:
            cast += play(card)
        except Hung:
            errors["took more than %d seconds" % TIMEOUT_SECONDS].append(card.name)
        except Exception as error:  # noqa: BLE001 - any failure is what this looks for
            errors[f"{type(error).__name__}: {str(error)[:80]}"].append(card.name)
        finally:
            if can_time_out:
                signal.alarm(0)
    return tried, cast, errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default=".cache/commander_pool.json")
    parser.add_argument("--limit", type=int, help="only the first N playable cards")
    args = parser.parse_args(argv[1:])
    with open(args.pool) as f:
        pool = json.load(f)
    tried, cast, errors = check(pool, args.limit)
    failed = sum(len(cards) for cards in errors.values())
    print(f"## Play smoke test: {tried - failed} of {tried} fully playable cards played without an error ({cast} could be cast or played)")
    for message, cards in sorted(errors.items(), key=lambda kv: -len(kv[1])):
        print(f"- {len(cards)} x `{message}`: {', '.join(sorted(cards)[:6])}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
