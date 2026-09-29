"""A simple computer player, plus goldfishing: playing a deck alone to see how it opens."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from .analysis import is_land
from .cards import Card, Deck
from .game import BOTTOM_PROMPT, DISCARD_PROMPT, HAND_SIZE, KEEP_PROMPT, PASS

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
    """Keeps 2-5 land hands, plays a land whenever it can, and otherwise passes."""

    def __init__(self, name: str, deck: Deck):
        self.name = name
        self._cards = {c.name: c for c in deck.commanders + deck.main}
        self._hand: list[Card] = []
        self._mulligans = 0

    def notify(self, event: dict) -> None:
        if event.get("event") == "opening_hand":
            self._hand = [self._cards[name] for name in event["cards"]]
            self._mulligans = event["mulligans"]

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        if prompt == KEEP_PROMPT:
            return 0 if keep_hand(self._hand, self._mulligans) else 1
        if prompt in (BOTTOM_PROMPT, DISCARD_PROMPT):
            return worst_card([self._cards[name] for name in options])
        for i, option in enumerate(options):
            if option.startswith("Play land"):
                return i
        return options.index(PASS) if PASS in options else 0


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
