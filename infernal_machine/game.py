"""Commander game: setup, mulligans and the turn/priority loop.

Players act only through the Player protocol, so TCP and local players are
interchangeable. So far the only actions are playing a land and passing
priority; the stack is always empty.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .analysis import is_land
from .cards import Card, Deck
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


@dataclass
class Seat:
    player: Player
    index: int
    life: int = STARTING_LIFE
    library: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Card] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
    command_zone: list[Card] = field(default_factory=list)
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
            if to_bottom >= HAND_SIZE or seat.player.choose("Keep this hand?", ["Keep", "Mulligan"]) == 0:
                break
            taken += 1
        for _ in range(min(to_bottom, HAND_SIZE)):
            i = seat.player.choose("Put a card on the bottom of your library", [c.name for c in seat.hand])
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
        if self.step == "draw":
            # CR 103.8: only a two-player game skips the first player's first draw.
            if not (self.turn == 1 and not self.multiplayer):
                self._draw(seat, 1)
        elif self.step == "cleanup":
            excess = len(seat.hand) - HAND_SIZE
            for _ in range(max(0, excess)):
                i = seat.player.choose("Discard down to hand size", [c.name for c in seat.hand])
                card = seat.hand.pop(i)
                seat.graveyard.append(card)
                self._broadcast({"event": "discard", "seat": seat.index, "card": card.name})
        self._check_state()

    def _priority_round(self, active: Seat) -> None:
        """Give priority around the table until every live player passes in a row (CR 117.4)."""
        passes = 0
        holder = active
        while passes < len(self.live_seats()):
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
        sorcery_timing = seat.index == self.active and self.step in ("main1", "main2")
        if sorcery_timing and seat.lands_played < 1:
            actions += [f"Play land: {c.name}" for c in _unique(seat.hand) if is_land(c)]
        return actions

    def _perform(self, seat: Seat, action: str) -> None:
        if action.startswith("Play land: "):
            name = action.removeprefix("Play land: ")
            card = next(c for c in seat.hand if c.name == name)
            seat.hand.remove(card)
            seat.battlefield.append(card)
            seat.lands_played += 1
            self._broadcast({"event": "play_land", "seat": seat.index, "card": name})

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


def _unique(cards: list[Card]) -> list[Card]:
    return list({c.name: c for c in cards}.values())
