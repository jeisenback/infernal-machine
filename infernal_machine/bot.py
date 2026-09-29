"""A simple computer player, plus goldfishing: playing a deck alone to see how it opens."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Sequence

from .analysis import is_land
from .cards import Card, Deck
from .combat import ATTACK_PROMPT, BLOCK_PROMPT
from .game import (BOTTOM_PROMPT, CAST, CAST_COMMANDER, DISCARD_PROMPT, HAND_SIZE, KEEP_PROMPT, PASS,
                   PLAY_LAND, TARGET_PROMPT)

MIN_LANDS = 2
MAX_LANDS = 5
MAX_MULLIGANS = 2  # after this many, keep whatever comes


def keep_hand(hand: list[Card], mulligans: int = 0) -> bool:
    lands = sum(1 for c in hand if is_land(c))
    return mulligans >= MAX_MULLIGANS or MIN_LANDS <= lands <= MAX_LANDS


def worst_card(hand: list[Card]) -> int:
    """Index of the card to put on the bottom or discard: a land if over half
    the hand is lands, otherwise the most expensive spell."""
    lands = [i for i, c in enumerate(hand) if is_land(c)]
    spells = [i for i, c in enumerate(hand) if not is_land(c)]
    if lands and (len(lands) * 2 > len(hand) or not spells):
        return lands[0]
    return max(spells, key=lambda i: hand[i].cmc)


class BotPlayer:
    """Keeps 2-5 land hands, plays a land whenever it can, then casts its most
    expensive affordable spell (its commander first), and otherwise passes.

    It targets opponents' things when it can, never responds to its own
    spell, and always sends its commander back to the command zone.
    In combat it attacks the opponent with the lowest life with every creature
    that has power, blocks when its blocker survives, and chump-blocks the
    biggest attacker once its life is at CHUMP_LIFE or below.
    """

    CHUMP_LIFE = 10

    def __init__(self, name: str, deck: Deck):
        self.name = name
        self._cards = {c.name: c for c in deck.commanders + deck.main}
        self._hand: list[Card] = []
        self._mulligans = 0
        self._seat: int | None = None
        self._stack: list[int] = []  # seat of each spell on the stack, bottom first
        self._life: dict[int, int] = {}

    def notify(self, event: dict) -> None:
        kind = event.get("event")
        if kind == "opening_hand":
            self._hand = [self._cards[name] for name in event["cards"]]
            self._mulligans = event["mulligans"]
        elif kind == "seat":
            self._life[event["seat"]] = event["life"]
            if event["name"] == self.name:
                self._seat = event["seat"]
        elif kind == "life":
            self._life[event["seat"]] = event["life"]
        elif kind in ("cast", "trigger"):
            self._stack.append(event["seat"])
        elif kind in ("resolve", "fizzle") and self._stack:
            self._stack.pop()
        elif kind == "countered" and event["seat"] in self._stack:
            self._stack.reverse()
            self._stack.remove(event["seat"])
            self._stack.reverse()

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        if prompt == KEEP_PROMPT:
            return 0 if keep_hand(self._hand, self._mulligans) else 1
        if prompt in (BOTTOM_PROMPT, DISCARD_PROMPT):
            return worst_card([self._cards[name] for name in options])
        if prompt.startswith(ATTACK_PROMPT):
            if _stats(prompt)[0] <= 0:
                return 0
            return min(range(1, len(options)), key=lambda i: self._life.get(_seat_of(options[i]), 0))
        if prompt.startswith(BLOCK_PROMPT):
            return self._block(prompt, options)
        if prompt.startswith(TARGET_PROMPT):
            theirs = [i for i, option in enumerate(options) if _seat_of(option) != self._seat]
            return theirs[0] if theirs else 0
        if PASS not in options:
            return 0  # search, command zone and other yes/no choices: take the first option
        if self._stack and self._stack[-1] == self._seat:
            return options.index(PASS)
        for i, option in enumerate(options):
            if option.startswith(PLAY_LAND):
                return i
        for i, option in enumerate(options):
            if option.startswith(CAST_COMMANDER):
                return i
        casts = [i for i, option in enumerate(options) if option.startswith(CAST)]
        if casts:
            return max(casts, key=lambda i: self._cards[options[i].removeprefix(CAST)].cmc)
        return options.index(PASS)


    def _block(self, prompt: str, options: Sequence[str]) -> int:
        toughness = _stats(prompt)[1]
        powers = {i: _stats(options[i])[0] for i in range(1, len(options))}
        survivable = [i for i, p in powers.items() if p < toughness]
        if survivable:
            return max(survivable, key=powers.get)
        if self._life.get(self._seat, 0) <= self.CHUMP_LIFE:
            return max(powers, key=powers.get)
        return 0


def _stats(label: str) -> tuple[int, int]:
    """Power and toughness from a label like "Grizzly Bears 2/2 (seat 1, #3)"; unknowns count as 0."""
    match = re.search(r" (\S+)/(\S+) \(seat", label)
    if not match:
        return 0, 0
    return tuple(int(v) if v.isdigit() else 0 for v in match.groups())


def _seat_of(label: str) -> int | None:
    match = re.search(r"\(seat (\d+)", label)
    return int(match[1]) if match else None


@dataclass
class GoldfishStats:
    games: int
    mulligan_rate: float  # share of games with at least one mulligan
    average_opening_lands: float  # lands in the kept hand, after bottoming
    land_drop_rate: dict[int, float]  # turn -> share of games with a land on every turn so far


def goldfish(deck: Deck, games: int = 1000, turns: int = 5, seed: int = 0, free_mulligan: bool = True) -> GoldfishStats:
    """Play `deck` alone `games` times with the bot's mulligan rules and one land a turn.

    Draws every turn, as in a multiplayer game; `free_mulligan` matches the
    multiplayer free first mulligan.
    """
    mulliganed = 0
    opening_lands = 0
    on_curve = {turn: 0 for turn in range(1, turns + 1)}
    for game in range(games):
        rng = random.Random(f"{seed}-{game}")
        library, hand = list(deck.main), []
        mulligans = 0
        while True:
            library += hand
            rng.shuffle(library)
            hand, library = library[:HAND_SIZE], library[HAND_SIZE:]
            if keep_hand(hand, mulligans):
                break
            mulligans += 1
        for _ in range(max(0, mulligans - (1 if free_mulligan else 0))):
            library.append(hand.pop(worst_card(hand)))
        mulliganed += mulligans > 0
        opening_lands += sum(1 for c in hand if is_land(c))

        for turn in range(1, turns + 1):
            if library:
                hand.append(library.pop(0))
            land = next((c for c in hand if is_land(c)), None)
            if land is None:
                break
            hand.remove(land)
            on_curve[turn] += 1
    return GoldfishStats(
        games=games,
        mulligan_rate=round(mulliganed / games, 3),
        average_opening_lands=round(opening_lands / games, 2),
        land_drop_rate={turn: round(hits / games, 3) for turn, hits in on_curve.items()},
    )
