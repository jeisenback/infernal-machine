"""Commander game: setup, mulligans and the turn/priority loop.

Players act only through the Player protocol, so TCP and local players are
interchangeable. Actions so far: play a land, cast a spell (including your
commander, with commander tax) paying with lands, and pass priority. Spells
use the stack; permanents enter the battlefield when they resolve, but spell
effects and rules text are not implemented yet.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from .analysis import is_land
from .cards import Card, Deck
from .mana import parse_cost, pay
from .player import Player

STARTING_LIFE = 40
HAND_SIZE = 7
STEPS = [
    "untap",
    "upkeep",
    "draw",
    "main1",
    "beginning_of_combat",
    "declare_attackers",
    "declare_blockers",
    "combat_damage",
    "end_of_combat",
    "main2",
    "end",
    "cleanup",
]
NO_PRIORITY_STEPS = {"untap", "cleanup"}  # CR 502.4, 514.3
PASS = "Pass"
PLAY_LAND = "Play land: "
CAST = "Cast: "
CAST_COMMANDER = "Cast commander: "
COMMANDER_TAX = 2  # CR 903.8
PERMANENT_TYPES = ("Artifact", "Battle", "Creature", "Enchantment", "Land", "Planeswalker")
KEEP_PROMPT = "Keep this hand?"
BOTTOM_PROMPT = "Put a card on the bottom of your library"
DISCARD_PROMPT = "Discard down to hand size"


@dataclass
class Permanent:
    card: Card
    tapped: bool = False


@dataclass
class StackItem:
    card: Card
    controller: "Seat"


@dataclass
class Seat:
    player: Player
    index: int
    life: int = STARTING_LIFE
    library: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
    command_zone: list[Card] = field(default_factory=list)
    commander_casts: dict[str, int] = field(default_factory=dict)
    lands_played: int = 0
    drew_from_empty: bool = False
    lost: bool = False

    @property
    def name(self) -> str:
        return self.player.name


class Game:
    def __init__(self, seats: list[tuple[Player, Deck]], seed: int | None = None):
        if len(seats) < 2:
            raise ValueError("Commander needs at least two players")
        self.rng = random.Random(seed)
        self.seats = [
            Seat(player, i, library=list(deck.main), command_zone=list(deck.commanders))
            for i, (player, deck) in enumerate(seats)
        ]
        self.turn = 0
        self.active = 0
        self.step = STEPS[0]
        self.stack: list[StackItem] = []

    @property
    def multiplayer(self) -> bool:
        return len(self.seats) > 2

    def live_seats(self) -> list[Seat]:
        return [s for s in self.seats if not s.lost]

    def winner(self) -> Seat | None:
        alive = self.live_seats()
        return alive[0] if len(alive) == 1 else None

    # --- setup ---------------------------------------------------------------

    def setup(self) -> None:
        self.active = self.rng.randrange(len(self.seats))
        for seat in self.seats:
            self.rng.shuffle(seat.library)
            self._broadcast({"event": "seat", "seat": seat.index, "name": seat.name,
                             "life": seat.life, "commanders": [c.name for c in seat.command_zone]})
        self._broadcast({"event": "starting_player", "seat": self.active})
        for seat in self._turn_order(self.active):
            self._mulligan(seat)

    def _mulligan(self, seat: Seat) -> None:
        """London mulligan (CR 103.5); the first one is free in multiplayer (103.5c)."""
        taken = 0
        while True:
            seat.library += seat.hand
            seat.hand = []
            self.rng.shuffle(seat.library)
            self._draw(seat, HAND_SIZE, announce=False)
            seat.player.notify({"event": "opening_hand", "cards": [c.name for c in seat.hand], "mulligans": taken})
            to_bottom = max(0, taken - (1 if self.multiplayer else 0))
            if to_bottom >= HAND_SIZE or seat.player.choose(KEEP_PROMPT, ["Keep", "Mulligan"]) == 0:
                break
            taken += 1
        for _ in range(min(to_bottom, HAND_SIZE)):
            i = seat.player.choose(BOTTOM_PROMPT, [c.name for c in seat.hand])
            seat.library.append(seat.hand.pop(i))
        self._broadcast({"event": "kept", "seat": seat.index, "mulligans": taken, "hand_size": len(seat.hand)})

    # --- turn loop -----------------------------------------------------------

    def play(self, max_turns: int = 100) -> Seat | None:
        """Run setup and turns until one player is left or `max_turns` is reached."""
        self.setup()
        while self.winner() is None and self.turn < max_turns:
            self.turn += 1
            self._take_turn(self.seats[self.active])
            self.active = self._next_live_seat(self.active)
        winner = self.winner()
        self._broadcast({"event": "game_over", "winner": winner.index if winner else None, "turn": self.turn})
        return winner

    def _take_turn(self, seat: Seat) -> None:
        seat.lands_played = 0
        self._broadcast({"event": "turn", "turn": self.turn, "seat": seat.index})
        for step in STEPS:
            self.step = step
            self._turn_based_actions(seat)
            if self.winner() is not None or seat.lost:
                return
            if step not in NO_PRIORITY_STEPS:
                self._priority_round(seat)

    def _turn_based_actions(self, seat: Seat) -> None:
        if self.step == "untap":
            for permanent in seat.battlefield:
                permanent.tapped = False
        elif self.step == "draw":
            # CR 103.8: only a two-player game skips the first player's first draw.
            if not (self.turn == 1 and not self.multiplayer):
                self._draw(seat, 1)
        elif self.step == "cleanup":
            excess = len(seat.hand) - HAND_SIZE
            for _ in range(max(0, excess)):
                i = seat.player.choose(DISCARD_PROMPT, [c.name for c in seat.hand])
                card = seat.hand.pop(i)
                seat.graveyard.append(card)
                self._broadcast({"event": "discard", "seat": seat.index, "card": card.name})
        self._check_state()

    def _priority_round(self, active: Seat) -> None:
        """Pass priority around the table (CR 117.4).

        When every live player passes in a row, the top of the stack resolves
        and the active player gets priority again; with an empty stack the step ends.
        """
        passes = 0
        holder = active
        while True:
            if passes >= len(self.live_seats()):
                if not self.stack:
                    return
                self._resolve(self.stack.pop())
                passes, holder = 0, active
                continue
            actions = self.legal_actions(holder)
            choice = actions[holder.player.choose(f"Priority: {self.step}", actions)]
            if choice == PASS:
                passes += 1
                holder = self.seats[self._next_live_seat(holder.index)]
                continue
            self._perform(holder, choice)
            self._check_state()
            if self.winner() is not None or active.lost:
                return
            passes = 0  # the acting player gets priority again (CR 117.3c)

    def legal_actions(self, seat: Seat) -> list[str]:
        actions = [PASS]
        sorcery_timing = seat.index == self.active and self.step in ("main1", "main2") and not self.stack
        if sorcery_timing and seat.lands_played < 1:
            actions += [PLAY_LAND + c.name for c in _unique(seat.hand) if is_land(c)]
        for card in _unique(seat.hand):
            if not is_land(card) and (sorcery_timing or _instant_speed(card)) and self._payment(seat, card) is not None:
                actions.append(CAST + card.name)
        for card in seat.command_zone:
            if (sorcery_timing or _instant_speed(card)) and self._payment(seat, card, from_command_zone=True) is not None:
                actions.append(CAST_COMMANDER + card.name)
        return actions

    def commander_tax(self, seat: Seat, card: Card) -> int:
        return COMMANDER_TAX * seat.commander_casts.get(card.name, 0)

    def _payment(self, seat: Seat, card: Card, from_command_zone: bool = False) -> list[Permanent] | None:
        """The untapped lands to tap for `card`, or None if it can't be cast now."""
        cost = parse_cost(card.mana_cost)
        if cost is None:
            return None
        if from_command_zone:
            cost = cost.plus_generic(self.commander_tax(seat, card))
        lands = [p for p in seat.battlefield if not p.tapped and is_land(p.card)]
        chosen = pay(cost, [frozenset(p.card.produced_mana) for p in lands])
        return None if chosen is None else [lands[i] for i in chosen]

    def _perform(self, seat: Seat, action: str) -> None:
        if action.startswith(PLAY_LAND):
            card = _take(seat.hand, action.removeprefix(PLAY_LAND))
            seat.battlefield.append(Permanent(card))
            seat.lands_played += 1
            self._broadcast({"event": "play_land", "seat": seat.index, "card": card.name})
        elif action.startswith(CAST_COMMANDER):
            name = action.removeprefix(CAST_COMMANDER)
            card = next(c for c in seat.command_zone if c.name == name)
            self._cast(seat, card, seat.command_zone, from_command_zone=True)
            seat.commander_casts[name] = seat.commander_casts.get(name, 0) + 1
        elif action.startswith(CAST):
            card = next(c for c in seat.hand if c.name == action.removeprefix(CAST))
            self._cast(seat, card, seat.hand)

    def _cast(self, seat: Seat, card: Card, zone: list[Card], from_command_zone: bool = False) -> None:
        lands = self._payment(seat, card, from_command_zone)
        for land in lands:
            land.tapped = True
        zone.remove(card)
        self.stack.append(StackItem(card, seat))
        self._broadcast({"event": "cast", "seat": seat.index, "card": card.name,
                         "from": "command_zone" if from_command_zone else "hand",
                         "tapped": [land.card.name for land in lands]})

    def _resolve(self, item: StackItem) -> None:
        seat = item.controller
        if any(t in item.card.type_line for t in PERMANENT_TYPES):
            seat.battlefield.append(Permanent(item.card))
            destination = "battlefield"
        else:
            seat.graveyard.append(item.card)
            destination = "graveyard"
        self._broadcast({"event": "resolve", "seat": seat.index, "card": item.card.name, "to": destination})

    # --- helpers -------------------------------------------------------------

    def _draw(self, seat: Seat, count: int, announce: bool = True) -> None:
        for _ in range(count):
            if not seat.library:
                seat.drew_from_empty = True
                return
            card = seat.library.pop(0)
            seat.hand.append(card)
            if announce:
                seat.player.notify({"event": "draw", "card": card.name})
                self._broadcast({"event": "drew", "seat": seat.index, "hand_size": len(seat.hand)}, skip=seat)

    def _check_state(self) -> None:
        """State-based actions that apply so far (CR 704.5a, 704.5b)."""
        for seat in self.live_seats():
            reason = None
            if seat.life <= 0:
                reason = "life"
            elif seat.drew_from_empty:
                reason = "empty_library"
            if reason:
                seat.lost = True
                self.stack = [item for item in self.stack if item.controller is not seat]  # CR 800.4a
                self._broadcast({"event": "player_lost", "seat": seat.index, "reason": reason})

    def _turn_order(self, start: int) -> list[Seat]:
        return [self.seats[(start + i) % len(self.seats)] for i in range(len(self.seats))]

    def _next_live_seat(self, index: int) -> int:
        for seat in self._turn_order(index)[1:]:
            if not seat.lost:
                return seat.index
        return index

    def _broadcast(self, event: dict, skip: Seat | None = None) -> None:
        for seat in self.seats:
            if seat is not skip:
                seat.player.notify(event)


def _instant_speed(card: Card) -> bool:
    if "Instant" in card.type_line:
        return True
    # Keyword lines look like "Flash" or "Flying, flash", possibly with reminder text.
    for line in card.oracle_text.splitlines():
        keywords = re.sub(r"\s*\([^)]*\)", "", line).lower().split(", ")
        if "flash" in keywords:
            return True
    return False


def _take(cards: list[Card], name: str) -> Card:
    card = next(c for c in cards if c.name == name)
    cards.remove(card)
    return card


def _unique(cards: list[Card]) -> list[Card]:
    return list({c.name: c for c in cards}.values())
