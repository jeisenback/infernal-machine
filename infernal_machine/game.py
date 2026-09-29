"""Commander game: setup, mulligans and the turn/priority loop.

Players act only through the Player protocol, so TCP and local players are
interchangeable. Actions so far: play a land, cast a spell (including your
commander, with commander tax), and pass priority. Mana comes from lands and
from permanents with simple mana abilities. Spells use the stack; instants and
sorceries do what effects.py understands of their rules text, and permanents'
other rules text is not implemented yet.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .analysis import is_land
from .cards import Card, Deck, has_keyword
from .effects import mana_ability, spell_effects, target_kind
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
TARGET_PROMPT = "Choose a target for "  # followed by the spell's name
SEARCH_PROMPT = "Choose a basic land to put onto the battlefield"
COMMAND_ZONE_PROMPT = "Move your commander to the command zone?"
COMMAND_ZONE_OPTIONS = ["Command zone", "Graveyard"]


@dataclass(eq=False)
class Permanent:
    card: Card
    tapped: bool = False
    sick: bool = False  # entered since its controller's last untap step
    damage: int = 0
    loyalty: int | None = None


@dataclass(eq=False)
class StackItem:
    card: Card
    controller: "Seat"
    effects: list | None = field(default_factory=list)  # None: rules text not understood
    targets: list = field(default_factory=list)  # one per targeting effect, in order


@dataclass(eq=False)
class Seat:
    player: Player
    index: int
    life: int = STARTING_LIFE
    library: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
    command_zone: list[Card] = field(default_factory=list)
    commander_names: set[str] = field(default_factory=set)
    color_identity: frozenset[str] = frozenset()
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
            Seat(
                player,
                i,
                library=list(deck.main),
                command_zone=list(deck.commanders),
                commander_names={c.name for c in deck.commanders},
                color_identity=frozenset(color for c in deck.commanders for color in c.color_identity),
            )
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

    def opponents(self, seat: Seat) -> list[Seat]:
        return [s for s in self.live_seats() if s is not seat]

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
            self.draw(seat, HAND_SIZE, announce=False)
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
                permanent.sick = False
        elif self.step == "draw":
            # CR 103.8: only a two-player game skips the first player's first draw.
            if not (self.turn == 1 and not self.multiplayer):
                self.draw(seat, 1)
        elif self.step == "cleanup":
            excess = len(seat.hand) - HAND_SIZE
            for _ in range(max(0, excess)):
                i = seat.player.choose(DISCARD_PROMPT, [c.name for c in seat.hand])
                card = seat.hand.pop(i)
                seat.graveyard.append(card)
                self._broadcast({"event": "discard", "seat": seat.index, "card": card.name})
            for other in self.seats:  # CR 514.2
                for permanent in other.battlefield:
                    permanent.damage = 0
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
                holder = active  # after resolving, the active player gets priority (CR 117.3b)
            else:
                actions = self.legal_actions(holder)
                choice = actions[holder.player.choose(f"Priority: {self.step}", actions)]
                if choice == PASS:
                    passes += 1
                    holder = self.seats[self._next_live_seat(holder.index)]
                    continue
                self._perform(holder, choice)  # the same player gets priority again (CR 117.3c)
            passes = 0
            self._check_state()
            if self.winner() is not None or active.lost:
                return
            if holder.lost:
                holder = self.seats[self._next_live_seat(holder.index)]

    # --- actions -------------------------------------------------------------

    def legal_actions(self, seat: Seat) -> list[str]:
        actions = [PASS]
        sorcery_timing = seat.index == self.active and self.step in ("main1", "main2") and not self.stack
        if sorcery_timing and seat.lands_played < 1:
            actions += [PLAY_LAND + c.name for c in _unique(seat.hand) if is_land(c)]
        for card in _unique(seat.hand):
            if not is_land(card) and (sorcery_timing or _instant_speed(card)) and self._can_cast(seat, card):
                actions.append(CAST + card.name)
        for card in seat.command_zone:
            if (sorcery_timing or _instant_speed(card)) and self._can_cast(seat, card, from_command_zone=True):
                actions.append(CAST_COMMANDER + card.name)
        return actions

    def commander_tax(self, seat: Seat, card: Card) -> int:
        return COMMANDER_TAX * seat.commander_casts.get(card.name, 0)

    def _can_cast(self, seat: Seat, card: Card, from_command_zone: bool = False) -> bool:
        if self._payment(seat, card, from_command_zone) is None:
            return False
        kinds = [target_kind(e) for e in _effects(card) or []]
        return all(self.target_options(kind, seat) for kind in kinds if kind)

    def _mana_sources(self, seat: Seat) -> list[tuple[Permanent, frozenset[str]]]:
        """One entry per mana each untapped permanent can make; nonland sources first."""
        abilities, lands = [], []
        for permanent in seat.battlefield:
            if permanent.tapped:
                continue
            if is_land(permanent.card):
                lands.append((permanent, frozenset(permanent.card.produced_mana)))
            elif not (permanent.sick and "Creature" in permanent.card.type_line):
                for mana in mana_ability(permanent.card, seat.color_identity) or []:
                    abilities.append((permanent, mana))
        return abilities + lands

    def _payment(self, seat: Seat, card: Card, from_command_zone: bool = False) -> list[Permanent] | None:
        """The permanents to tap for `card`, or None if it can't be paid for now."""
        cost = parse_cost(card.mana_cost)
        if cost is None:
            return None
        if from_command_zone:
            cost = cost.plus_generic(self.commander_tax(seat, card))
        sources = self._mana_sources(seat)
        chosen = pay(cost, [mana for _, mana in sources])
        if chosen is None:
            return None
        # A permanent that makes several mana (Sol Ring) is tapped once.
        return list({id(sources[i][0]): sources[i][0] for i in chosen}.values())

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
        effects = _effects(card)
        targets, labels = [], []
        for kind in (target_kind(e) for e in effects or []):
            if kind:
                options = self.target_options(kind, seat)
                label, target = options[seat.player.choose(TARGET_PROMPT + card.name, [o[0] for o in options])]
                targets.append(target)
                labels.append(label)
        tapped = self._payment(seat, card, from_command_zone)
        for permanent in tapped:
            permanent.tapped = True
        zone.remove(card)
        self.stack.append(StackItem(card, seat, effects, targets))
        self._broadcast({"event": "cast", "seat": seat.index, "card": card.name,
                         "from": "command_zone" if from_command_zone else "hand",
                         "targets": labels, "tapped": [p.card.name for p in tapped]})

    def _resolve(self, item: StackItem) -> None:
        seat, card = item.controller, item.card
        if _is_permanent(card):
            loyalty = int(card.loyalty) if card.loyalty and card.loyalty.isdigit() else None
            seat.battlefield.append(Permanent(card, sick=True, loyalty=loyalty))
            self._broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
            return
        if item.effects is None:
            self._broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "unsupported": True})
            self._to_graveyard(seat, card)
            return
        legal = [self.is_legal_target(target_kind(e), t, seat)
                 for e, t in zip([e for e in item.effects if target_kind(e)], item.targets)]
        if legal and not any(legal):  # CR 608.2b: every target is gone
            self._broadcast({"event": "fizzle", "seat": seat.index, "card": card.name})
            self._to_graveyard(seat, card)
            return
        self._broadcast({"event": "resolve", "seat": seat.index, "card": card.name})
        checks = iter(zip(item.targets, legal))
        for effect in item.effects:
            target = None
            if target_kind(effect):
                candidate, ok = next(checks)
                target = candidate if ok else None
            effect.resolve(self, seat, target)
        self._to_graveyard(seat, card)

    # --- targets -------------------------------------------------------------

    def target_options(self, kind: str, caster: Seat) -> list[tuple[str, Any]]:
        """Legal targets of `kind` for a spell `caster` controls, as (label, object)."""
        options: list[tuple[str, Any]] = []
        if kind in ("any", "player", "player or planeswalker"):
            options += [(f"Player: {s.name} (seat {s.index})", s) for s in self.live_seats()]
        if kind == "spell":
            options += [(f"Spell: {i.card.name} (seat {i.controller.index})", i) for i in self.stack]
            return options
        for seat in self.live_seats():
            for n, permanent in enumerate(seat.battlefield):
                card = permanent.card
                if not _permanent_matches(kind, card) or has_keyword(card, "shroud"):
                    continue
                if has_keyword(card, "hexproof") and seat is not caster:
                    continue
                options.append((f"{card.name} (seat {seat.index}, #{n + 1})", permanent))
        return options

    def is_legal_target(self, kind: str, target: Any, caster: Seat) -> bool:
        return any(option is target for _, option in self.target_options(kind, caster))

    # --- things effects do ---------------------------------------------------

    def draw(self, seat: Seat, count: int, announce: bool = True) -> None:
        for _ in range(count):
            if not seat.library:
                seat.drew_from_empty = True
                return
            card = seat.library.pop(0)
            seat.hand.append(card)
            if announce:
                seat.player.notify({"event": "draw", "card": card.name})
                self._broadcast({"event": "drew", "seat": seat.index, "hand_size": len(seat.hand)}, skip=seat)

    def change_life(self, seat: Seat, amount: int) -> None:
        seat.life += amount
        self._broadcast({"event": "life", "seat": seat.index, "change": amount, "life": seat.life})

    def damage(self, target: Seat | Permanent, amount: int) -> None:
        if isinstance(target, Seat):
            self.change_life(target, -amount)
            return
        if "Creature" in target.card.type_line:
            target.damage += amount
        if target.loyalty is not None:
            target.loyalty -= amount
        self._broadcast({"event": "damage", "card": target.card.name, "amount": amount})

    def destroy(self, permanent: Permanent) -> None:
        if has_keyword(permanent.card, "indestructible"):
            return
        self._leave_battlefield(permanent, "destroyed")

    def counter(self, item: StackItem) -> None:
        self.stack.remove(item)
        self._broadcast({"event": "countered", "seat": item.controller.index, "card": item.card.name})
        self._to_graveyard(item.controller, item.card)

    def fetch_basic_land(self, seat: Seat) -> None:
        basics = _unique([c for c in seat.library if "Basic" in c.type_line and "Land" in c.type_line])
        if basics:
            choice = basics[seat.player.choose(SEARCH_PROMPT, [c.name for c in basics])]
            seat.library.remove(choice)
            seat.battlefield.append(Permanent(choice, tapped=True))
            self._broadcast({"event": "put_onto_battlefield", "seat": seat.index, "card": choice.name, "tapped": True})
        self.rng.shuffle(seat.library)

    # --- helpers -------------------------------------------------------------

    def _leave_battlefield(self, permanent: Permanent, reason: str) -> None:
        owner = next(s for s in self.seats if any(p is permanent for p in s.battlefield))
        owner.battlefield = [p for p in owner.battlefield if p is not permanent]
        self._broadcast({"event": reason, "seat": owner.index, "card": permanent.card.name})
        self._to_graveyard(owner, permanent.card)

    def _to_graveyard(self, seat: Seat, card: Card) -> None:
        """Put a card into its owner's graveyard; a commander may go to the command zone (CR 903.9a)."""
        if card.name in seat.commander_names and seat.player.choose(COMMAND_ZONE_PROMPT, COMMAND_ZONE_OPTIONS) == 0:
            seat.command_zone.append(card)
            self._broadcast({"event": "to_command_zone", "seat": seat.index, "card": card.name})
            return
        seat.graveyard.append(card)

    def _check_state(self) -> None:
        """State-based actions (CR 704.5): losing the game, lethal damage, zero toughness or loyalty."""
        while True:
            changed = False
            for seat in self.live_seats():
                reason = "life" if seat.life <= 0 else "empty_library" if seat.drew_from_empty else None
                if reason:
                    seat.lost = True
                    seat.battlefield = []  # CR 800.4a: their objects leave the game
                    self.stack = [item for item in self.stack if item.controller is not seat]
                    self._broadcast({"event": "player_lost", "seat": seat.index, "reason": reason})
                    changed = True
            for seat in self.live_seats():
                for permanent in list(seat.battlefield):
                    toughness = _number(permanent.card.toughness)
                    creature = "Creature" in permanent.card.type_line and toughness is not None
                    if (creature and toughness <= 0) or (permanent.loyalty is not None and permanent.loyalty <= 0):
                        self._leave_battlefield(permanent, "died")
                        changed = True
                    elif creature and permanent.damage >= toughness and not has_keyword(permanent.card, "indestructible"):
                        self._leave_battlefield(permanent, "destroyed")
                        changed = True
            if not changed:
                return

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


def _is_permanent(card: Card) -> bool:
    return any(t in card.type_line for t in PERMANENT_TYPES)


def _effects(card: Card) -> list | None:
    """Spell effects for instants and sorceries; permanent spells just enter the battlefield."""
    return [] if _is_permanent(card) else spell_effects(card)


def _instant_speed(card: Card) -> bool:
    return "Instant" in card.type_line or has_keyword(card, "flash")


def _permanent_matches(kind: str, card: Card) -> bool:
    if kind == "any":
        return "Creature" in card.type_line or "Planeswalker" in card.type_line
    if kind == "permanent":
        return True
    if kind == "nonland permanent":
        return not is_land(card)
    return any(t.capitalize() in card.type_line for t in kind.split(" or ") if t != "player")


def _number(value: str | None) -> int | None:
    return int(value) if value and value.lstrip("-").isdigit() else None


def _take(cards: list[Card], name: str) -> Card:
    card = next(c for c in cards if c.name == name)
    cards.remove(card)
    return card


def _unique(cards: list[Card]) -> list[Card]:
    return list({c.name: c for c in cards}.values())
