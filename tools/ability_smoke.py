"""Can the activated abilities of the fully playable cards be paid for? (the third half of the coverage audit, beside play_smoke)

    python tools/ability_smoke.py [--pool .cache/commander_pool.json] [--limit N] [--card NAME]

`unsupported_lines(card) == []` says a card's text is read, not that it can be played: a cost the engine reads but cannot pay (a plural
"Sacrifice two Goblins" that matched no creature, a "Sacrifice a Food" that cost nothing, a cost with no mana that raised) goes unseen by
`play_smoke`, whose table has no Goblins and no Food. For each activated ability of each fully playable card whose cost is made of mana,
{T}, life, and the card costs below, this builds a table that can pay it, checks the game offers the activation, performs it, resolves the
stack and checks the cost was paid: the permanents sacrificed, the cards discarded or exiled from the graveyard, the counters removed, the
creatures tapped, the life paid. It lists abilities that are not offered, raise, hang or leave a cost unpaid. A cost it cannot build a table
for is counted and named, never skipped quietly. A measurement: it never fails the run.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import signal
import sys
from dataclasses import dataclass

sys.path.insert(0, os.getcwd())

from infernal_machine.cards import Card, Deck  # noqa: E402
from infernal_machine.effects import ActivatedAbility, activated_abilities  # noqa: E402
from infernal_machine.game import ACTIVATE, ACTIVATE_GRAVEYARD, X_PROMPT, Game, Permanent, _permanent_matches  # noqa: E402
from infernal_machine.report import unsupported_lines  # noqa: E402
from tests.helpers import BEAR, COMMANDER, OGRE, ScriptedPlayer  # noqa: E402

TIMEOUT_SECONDS = 5
LAND = Card(name="City of Brass", type_line="Land", produced_mana=tuple("WUBRGC"))
SPARE = 2  # sacrifice, discard or exile this many for an "X"
PERMANENT_TYPES = ("Creature", "Artifact", "Enchantment", "Planeswalker", "Land", "Battle")
COLORS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
# cost fields this tool pays; an ability with any other cost field set is counted under that field's name and not tried
CONDITIONS = ("loyalty", "condition", "discard_self", "exile_from_hand", "from_command_zone", "crew", "reconfigure", "exile_source",
              "bounce_source", "discard_hand", "discount_each", "exile_from_graveyard", "tap_legendary", "tap_type", "life_identity",
              "put_counter")


class Hung(Exception):
    pass


def run_stack(game: Game) -> None:
    while game.pending or game.stack:
        game._put_triggers_on_stack()
        while game.stack:
            game._resolve(game.stack.pop())
            game._check_state()


def policy(prompt: str, options: list[str]) -> int:
    """The first option, except that an X is as large as it can be."""
    return len(options) - 1 if X_PROMPT.matches(prompt) else 0


def probe(kind: str, name: str) -> Card | None:
    """A card that `kind` ("creature", "Squirrel", "artifact or creature", "white creature") matches; None if none of these does."""
    colors = tuple(symbol for word, symbol in COLORS.items() if word in kind.lower().split())
    subtype = kind.split()[-1].capitalize().removesuffix("s")
    for base in ("Creature", "Artifact", "Land", "Enchantment", "Artifact Creature"):
        for type_line in (base, f"{base} — {subtype}"):
            power, toughness = ("1", "1") if "Creature" in base else (None, None)
            card = Card(name=name, type_line=type_line, colors=colors, power=power, toughness=toughness)
            if _permanent_matches(kind, card):
                return card
    return None


def spare(ability: ActivatedAbility) -> int:
    return SPARE if ability.sacrifice_x else ability.sacrifice_count


_ABSENT_TARGET = re.compile(r"\btarget (?:attacking |blocking )|\btarget [\w ,/-]*?(?:spell|ability)\b", re.I)  # a spell, or a creature in combat


def untried(ability: ActivatedAbility) -> str | None:
    """Why this tool does not try the ability, or None if it can build a table for its cost."""
    for field in CONDITIONS:
        if getattr(ability, field):
            return field
    if _ABSENT_TARGET.search(ability.text.partition(":")[2]):
        return "a target on the stack or in combat"
    if ability.sacrifice_other and probe(ability.sacrifice_other, "Fodder") is None:
        return "sacrifice kind " + ability.sacrifice_other
    if ability.exile_graveyard and probe(ability.exile_graveyard_kind or "creature", "Fodder") is None:
        return "exile kind " + ability.exile_graveyard_kind
    return None


@dataclass
class Setup:
    game: Game
    mine: object
    source: Permanent | None
    fodder: list  # the permanents to sacrifice or tap
    lands: list
    hand: int  # the cards in hand to discard
    graveyard: int  # the cards in the graveyard to exile
    life: int


def build(card: Card, ability: ActivatedAbility) -> Setup:
    """Seat 0 has the card, twelve lands and what the cost needs; seat 1 a few permanents to aim at."""
    players = [ScriptedPlayer("A", policy), ScriptedPlayer("B", policy)]
    deck = Deck(commanders=[COMMANDER], main=[LAND] * 20, sideboard=[])
    game = Game([(player, deck) for player in players], seed=1)
    game.turn, game.active, game.step = 2, 0, "main1"
    for seat in game.seats:
        seat.hand, seat.command_zone = [], []
    mine, theirs = game.seats
    fodder: list = []
    on_table = []
    if ability.sacrifice_other:
        on_table += [Permanent(probe(ability.sacrifice_other, f"Fodder {n}"), sick=False) for n in range(spare(ability))]
    if ability.tap_creatures:
        on_table += [Permanent(probe("creature", f"Tapper {n}"), sick=False) for n in range(ability.tap_creatures)]
    fodder = list(on_table)
    source = None
    if any(kind in card.type_line.split(" // ")[0] for kind in PERMANENT_TYPES) and not ability.from_graveyard:
        source = Permanent(card, sick=False)
        if ability.remove_counter:
            source.counters[ability.remove_counter] = ability.remove_count
    lands = [Permanent(LAND) for _ in range(12)]
    # (the permanents the cost uses come first, so the first option the game offers is one of them; then a creature to aim at)
    relic = Permanent(Card(name="My Relic", type_line="Artifact"))
    mine.battlefield = on_table + [Permanent(BEAR, sick=False), relic] + lands + ([source] if source else [])
    theirs.battlefield = [Permanent(OGRE), Permanent(BEAR), Permanent(Card(name="Their Relic", type_line="Artifact")),
                          Permanent(Card(name="Their Shrine", type_line="Enchantment"))]
    mine.graveyard, theirs.graveyard = [BEAR, Card(name="Old Relic", type_line="Artifact"), Card(name="Old Shrine", type_line="Enchantment")], [OGRE]
    mine.life = 100 if ability.life else mine.life  # "Pay 50 life"
    if ability.from_graveyard:
        mine.graveyard.append(card)
    hand = ability.discard
    mine.hand = [Card(name=f"Spare {n}", type_line="Instant") for n in range(hand)]
    graveyard = ability.exile_graveyard
    if graveyard:
        kind = ability.exile_graveyard_kind or "creature"
        mine.graveyard = [probe(kind, f"Spent {n}") for n in range(graveyard)] + mine.graveyard  # type: ignore[misc]  # (first, to be exiled first)
    return Setup(game, mine, source, fodder, lands, hand, graveyard, mine.life)


def unpaid(setup: Setup, ability: ActivatedAbility) -> str | None:
    """Which part of the cost is still unpaid after the activation resolved, or None."""
    mine = setup.mine
    on_battlefield = lambda p: any(p is q for q in mine.battlefield)  # noqa: E731
    if ability.sacrifice_other:
        gone = sum(not on_battlefield(p) for p in setup.fodder[:spare(ability)])
        if gone < (1 if ability.sacrifice_x else ability.sacrifice_count):
            return f"sacrifice ({gone} of {ability.sacrifice_count} sacrificed)"
    if ability.sacrifice and setup.source is not None and on_battlefield(setup.source):
        return "sacrifice this"
    if ability.discard and sum(c.name.startswith("Spare") for c in mine.hand) > setup.hand - ability.discard:
        return "discard"  # (a card the ability returns to the hand is not one of the spares)
    if ability.exile_graveyard and sum(c.name.startswith("Spent") for c in mine.graveyard) >= setup.graveyard:
        return "exile from the graveyard"
    if ability.remove_counter and setup.source is not None and setup.source.counters.get(ability.remove_counter, 0) > 0:
        return "remove counters"
    if ability.tap_creatures and sum(p.tapped for p in setup.fodder) < ability.tap_creatures:
        return "tap creatures"
    if ability.life and mine.life > setup.life - ability.life:
        return "pay life"
    if ability.mana_cost and "{X}" not in ability.mana_cost and not any(p.tapped or not on_battlefield(p) for p in setup.lands):
        return "pay mana"
    return None


def action_for(setup: Setup, card: Card, ability: ActivatedAbility) -> str | None:
    actions = setup.game.legal_actions(setup.mine)
    if ability.from_graveyard:
        wanted = ACTIVATE_GRAVEYARD + card.name
        return wanted if wanted in actions else None
    text = ability.text.replace("CARDNAME", card.name)
    return next((a for a in actions if a.startswith(ACTIVATE) and a.endswith(f": {text}") and card.name in a), None)


def try_ability(card: Card, ability: ActivatedAbility) -> tuple[str, str]:
    """('paid' | 'not offered' | 'unpaid', detail); an exception propagates."""
    setup = build(card, ability)
    action = action_for(setup, card, ability)
    if action is None:
        return "not offered", ""
    setup.game._perform(setup.mine, action)
    run_stack(setup.game)
    setup.game._check_state()
    problem = unpaid(setup, ability)
    return ("unpaid", problem) if problem else ("paid", "")


def check(pool: list[dict], limit: int | None = None, only: str | None = None):
    """(abilities tried, abilities paid, problems -> [card (ability)], untried cost kinds -> abilities)."""
    problems: dict[str, list[str]] = collections.defaultdict(list)
    skipped: collections.Counter = collections.Counter()
    tried = paid = 0
    can_time_out = hasattr(signal, "SIGALRM")
    if can_time_out:
        def hang(signum, frame):
            raise Hung()
        signal.signal(signal.SIGALRM, hang)
    for data in pool:
        card = Card.from_scryfall(data)
        if (only is not None and card.name != only) or unsupported_lines(card):
            continue
        for ability in activated_abilities(card):
            if reason := untried(ability):
                skipped[reason] += 1
                continue
            if not (ability.sacrifice_other or ability.discard or ability.exile_graveyard or ability.remove_counter or ability.tap_creatures
                    or ability.life):
                continue  # a plain mana or {T} ability: its cost is play_smoke's
            if limit is not None and tried >= limit:
                return tried, paid, problems, skipped
            tried += 1
            label = f"{card.name} ({ability.text[:60]})"
            if can_time_out:
                signal.alarm(TIMEOUT_SECONDS)
            try:
                outcome, detail = try_ability(card, ability)
                if outcome == "paid":
                    paid += 1
                else:
                    problems[outcome + (f": {detail}" if detail else "")].append(label)
            except Hung:
                problems["took more than %d seconds" % TIMEOUT_SECONDS].append(label)
            except Exception as error:  # noqa: BLE001 - any failure is what this looks for
                problems[f"{type(error).__name__}: {str(error)[:80]}"].append(label)
            finally:
                if can_time_out:
                    signal.alarm(0)
    return tried, paid, problems, skipped


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default=".cache/commander_pool.json")
    parser.add_argument("--limit", type=int, help="only the first N abilities with a cost it can build")
    parser.add_argument("--card", help="only this card")
    args = parser.parse_args(argv[1:])
    with open(args.pool) as f:
        pool = json.load(f)
    tried, paid, problems, skipped = check(pool, args.limit, args.card)
    print(f"## Ability smoke test: {paid} of {tried} abilities with a sacrifice, discard, exile, counter, tap or life cost were offered and paid")
    for message, labels in sorted(problems.items(), key=lambda kv: -len(kv[1])):
        print(f"- {len(labels)} x `{message}`: {', '.join(sorted(labels)[:6])}")
    if skipped:
        print("- not tried, for a cost it builds no table for: " + ", ".join(f"{reason} {n}" for reason, n in skipped.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
