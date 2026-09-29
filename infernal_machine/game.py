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
from itertools import combinations
from dataclasses import dataclass, field
from typing import Any

from .analysis import is_land
from .cards import Card, Deck, has_keyword
from . import characteristics
from .characteristics import MINUS, PLUS, Modifier
from .combat import Combat
from .effects import (ActivatedAbility, TriggeredAbility, activated_abilities, enters_with_counters,
                      filter_mana_ability, follows_target, mana_ability, mana_ability_sacrifices, spell_effects, static_abilities, target_kind,
                      triggered_abilities, uses_source)
from .mana import Cost, parse_cost, pay
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
ACTIVATE = "Activate: "  # followed by "<permanent label>: <ability text>"
COMMANDER_TAX = 2  # CR 903.8
PERMANENT_TYPES = ("Artifact", "Battle", "Creature", "Enchantment", "Land", "Planeswalker")
KEEP_PROMPT = "Keep this hand?"
BOTTOM_PROMPT = "Put a card on the bottom of your library"
DISCARD_PROMPT = "Discard down to hand size"
TARGET_PROMPT = "Choose a target for "  # followed by the spell's name
SEARCH_PROMPT = "Choose a basic land to put onto the battlefield"
SEARCH_OPTIONAL_PROMPT = "Search your library for a basic land?"
COMMAND_ZONE_PROMPT = "Move your commander to the command zone?"  # options: "Command zone", then the zone it's going to
OPTIONAL_PROMPT = "Use this ability of "  # followed by the source's name
X_PROMPT = "Choose X for "  # followed by the spell's name; options are "0", "1", ...
MAX_X = 30  # stop looking for a bigger affordable X here
YES_NO = ["Yes", "No"]
COMMANDER_DAMAGE_LIMIT = 21  # CR 903.10a


@dataclass(eq=False)
class Permanent:
    card: Card
    tapped: bool = False
    sick: bool = False  # entered since its controller's last untap step
    damage: int = 0
    deathtouched: bool = False  # dealt damage by a source with deathtouch (CR 704.5h)
    loyalty: int | None = None
    loyalty_turn: int | None = None  # turn a loyalty ability was last activated (CR 606.3)
    counters: dict[str, int] = field(default_factory=dict)  # "+1/+1" -> 2
    until_end_of_turn: list[Modifier] = field(default_factory=list)
    activated_turn: dict[str, int] = field(default_factory=dict)  # ability text -> turn last activated
    last_controller: "Seat | None" = None  # who controlled it when it left the battlefield
    last_power: int = 0  # its power just before it left (CR 608.2h: last known information)


@dataclass(eq=False)
class StackItem:
    card: Card  # the spell, or the source of a triggered ability
    controller: "Seat"
    effects: list | None = field(default_factory=list)  # None: rules text not understood
    targets: list = field(default_factory=list)  # one per targeting effect, in order
    ability: TriggeredAbility | ActivatedAbility | None = None  # set for an ability rather than a spell
    source: "Permanent | None" = None  # the ability's source, for effects on "it"
    x: int = 0  # the value chosen for X when it was cast


@dataclass(eq=False)
class PendingTrigger:
    ability: TriggeredAbility
    permanent: "Permanent"
    controller: "Seat"

    @property
    def source(self) -> Card:
        return self.permanent.card


@dataclass(eq=False)
class Seat:
    player: Player
    index: int
    life: int = STARTING_LIFE
    library: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
    exile: list[Card] = field(default_factory=list)
    command_zone: list[Card] = field(default_factory=list)
    commander_names: set[str] = field(default_factory=set)
    color_identity: frozenset[str] = frozenset()
    commander_casts: dict[str, int] = field(default_factory=dict)
    commander_damage: dict[tuple[int, str], int] = field(default_factory=dict)  # (seat, commander) -> damage
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
        self.combat = Combat(self)
        self.pending: list[PendingTrigger] = []  # triggered, not yet on the stack
        self.x_value = 0  # X of the spell resolving right now

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
            self.broadcast({"event": "seat", "seat": seat.index, "name": seat.name,
                             "life": seat.life, "commanders": [c.name for c in seat.command_zone]})
        self.broadcast({"event": "starting_player", "seat": self.active})
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
        self.broadcast({"event": "kept", "seat": seat.index, "mulligans": taken, "hand_size": len(seat.hand)})

    # --- turn loop -----------------------------------------------------------

    def play(self, max_turns: int = 100) -> Seat | None:
        """Run setup and turns until one player is left or `max_turns` is reached."""
        self.setup()
        while self.winner() is None and self.turn < max_turns:
            self.turn += 1
            self._take_turn(self.seats[self.active])
            self.active = self._next_live_seat(self.active)
        winner = self.winner()
        self.broadcast({"event": "game_over", "winner": winner.index if winner else None, "turn": self.turn})
        return winner

    def _take_turn(self, seat: Seat) -> None:
        seat.lands_played = 0
        self.broadcast({"event": "turn", "turn": self.turn, "seat": seat.index})
        over = lambda: self.winner() is not None or seat.lost
        for step in STEPS:
            if step in ("declare_blockers", "combat_damage") and not self.combat.attacks:
                continue  # CR 508.8: no attackers, no blockers or damage steps
            if step == "combat_damage" and self.combat.has_first_strike():
                self.step = "first_strike_damage"  # CR 510.4
                self.combat.deal_damage(first_strike_step=True)
                self._check_state()
                if over():
                    return
                self._priority_round(seat)
                if over():
                    return
            self.step = step
            self._turn_based_actions(seat)
            if over():
                return
            if step not in NO_PRIORITY_STEPS:
                self._priority_round(seat)

    def _turn_based_actions(self, seat: Seat) -> None:
        if self.step == "untap":
            self.combat = Combat(self)
            for permanent in seat.battlefield:
                permanent.tapped = False
                permanent.sick = False
        elif self.step == "draw":
            # CR 103.8: only a two-player game skips the first player's first draw.
            if not (self.turn == 1 and not self.multiplayer):
                self.draw(seat, 1)
        elif self.step in ("upkeep", "end"):
            for permanent in list(seat.battlefield):
                self.trigger("upkeep" if self.step == "upkeep" else "end_step", permanent, seat)
        elif self.step == "declare_attackers":
            self.combat.declare_attackers(seat)
        elif self.step == "declare_blockers":
            self.combat.declare_blockers()
        elif self.step == "combat_damage":
            self.combat.deal_damage(first_strike_step=False)
        elif self.step == "main2":
            self.combat = Combat(self)  # CR 511.3: creatures leave combat
        elif self.step == "cleanup":
            excess = len(seat.hand) - HAND_SIZE
            for _ in range(max(0, excess)):
                i = seat.player.choose(DISCARD_PROMPT, [c.name for c in seat.hand])
                card = seat.hand.pop(i)
                seat.graveyard.append(card)
                self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
            for other in self.seats:  # CR 514.2
                for permanent in other.battlefield:
                    permanent.damage = 0
                    permanent.deathtouched = False
                    permanent.until_end_of_turn = []  # CR 514.2
        self._check_state()

    def _priority_round(self, active: Seat) -> None:
        """Pass priority around the table (CR 117.4).

        When every live player passes in a row, the top of the stack resolves
        and the active player gets priority again; with an empty stack the step ends.
        """
        passes = 0
        holder = active
        self._put_triggers_on_stack()
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
            self._put_triggers_on_stack()
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
        actions += list(self._activations(seat, sorcery_timing))
        return actions

    def _activations(self, seat: Seat, sorcery_timing: bool) -> dict[str, tuple[Permanent, ActivatedAbility]]:
        """Activated abilities `seat` can activate now, keyed by their action text."""
        options = {}
        for permanent in seat.battlefield:
            for ability in activated_abilities(permanent.card):
                if self._can_activate(seat, permanent, ability, sorcery_timing):
                    text = ability.text.replace("CARDNAME", permanent.card.name)
                    options[f"{ACTIVATE}{self.label(permanent)}: {text}"] = (permanent, ability)
        return options

    def _can_activate(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility, sorcery_timing: bool) -> bool:
        card = permanent.card
        if ability.sorcery_speed and not sorcery_timing:
            return False
        if ability.tap and (permanent.tapped or (permanent.sick and "Creature" in card.type_line
                                                  and not self.has_keyword(permanent, "haste"))):
            return False
        if ability.once_per_turn and permanent.activated_turn.get(ability.text) == self.turn:
            return False
        if ability.loyalty is not None and (permanent.loyalty_turn == self.turn
                                            or (permanent.loyalty or 0) + ability.loyalty < 0):
            return False
        if ability.life > seat.life:  # CR 119.4
            return False
        if self._ability_payment(seat, permanent, ability) is None:
            return False
        return all(self.target_options(kind, seat) for kind in map(target_kind, ability.effects) if kind)

    def _ability_payment(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility) -> list[Permanent] | None:
        cost = parse_cost(ability.mana_cost) if ability.mana_cost else Cost()
        # A permanent can't tap for mana to pay for its own {T} or sacrifice ability.
        return self._pay_cost(seat, cost, exclude=permanent if ability.tap or ability.sacrifice else None)

    def commander_tax(self, seat: Seat, card: Card) -> int:
        return COMMANDER_TAX * seat.commander_casts.get(card.name, 0)

    def _can_cast(self, seat: Seat, card: Card, from_command_zone: bool = False) -> bool:
        if self._payment(seat, card, from_command_zone) is None:
            return False
        kinds = [target_kind(e) for e in _effects(card) or []]
        return all(self.target_options(kind, seat) for kind in kinds if kind)

    def _spend_mana(self, sources: list[Permanent]) -> None:
        """Tap the chosen mana sources; ones whose mana ability sacrifices them (Treasure) are sacrificed."""
        for source in sources:
            source.tapped = True
            if not is_land(source.card) and mana_ability_sacrifices(source.card):
                self._leave_battlefield(source, "sacrificed")

    def _mana_sources(self, seat: Seat, exclude: Permanent | None = None) -> list[tuple[Permanent, frozenset[str]]]:
        """One entry per mana each untapped permanent can make: nonland sources first,
        then lands, and sources that sacrifice themselves (Treasure) last."""
        abilities, lands, sacrifices = [], [], []
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude:
                continue
            if is_land(permanent.card):
                lands.append((permanent, frozenset(permanent.card.produced_mana)))
            elif not (permanent.sick and "Creature" in permanent.card.type_line):
                bucket = sacrifices if mana_ability_sacrifices(permanent.card) else abilities
                for mana in mana_ability(permanent.card, seat.color_identity) or []:
                    bucket.append((permanent, mana))
        return abilities + lands + sacrifices

    def _payment(self, seat: Seat, card: Card, from_command_zone: bool = False, x: int = 0) -> list[Permanent] | None:
        """The permanents to tap for `card` with X = `x`, or None if it can't be paid for now."""
        cost = parse_cost(card.mana_cost)
        if cost is None:
            return None
        if from_command_zone:
            cost = cost.plus_generic(self.commander_tax(seat, card))
        return self._pay_cost(seat, cost.with_x(x))

    def _max_x(self, seat: Seat, card: Card, from_command_zone: bool) -> int:
        x = 0
        while x < MAX_X and self._payment(seat, card, from_command_zone, x + 1) is not None:
            x += 1
        return x

    def _pay_cost(self, seat: Seat, cost: Cost, exclude: Permanent | None = None) -> list[Permanent] | None:
        """The permanents to tap for `cost`, or None if it can't be paid.

        Signet-style sources ("{1}, {T}: Add {W}{U}.") are tried only when plain
        sources aren't enough, fewest first; their own costs are paid from plain sources.
        """
        sources = self._mana_sources(seat, exclude)
        filters = self._filter_sources(seat, exclude)
        for size in range(len(filters) + 1):
            for combo in combinations(filters, size):
                chosen = self._pay_with_filters(cost, sources, combo)
                if chosen is not None:
                    return chosen
        return None

    def _pay_with_filters(self, cost: Cost, sources, combo) -> list[Permanent] | None:
        activation = sum((c for _, c, _ in combo), Cost())
        first = pay(activation, [mana for _, mana in sources])
        if first is None:
            return None
        rest = [s for i, s in enumerate(sources) if i not in first]
        made = [(permanent, mana) for permanent, _, units in combo for mana in units]
        pool = rest + made
        second = pay(cost, [mana for _, mana in pool])
        if second is None:
            return None
        used = [sources[i][0] for i in first] + [pool[i][0] for i in second] + [p for p, _, _ in combo]
        # A permanent that makes several mana (Sol Ring) is tapped once.
        return list({id(p): p for p in used}.values())

    def _filter_sources(self, seat: Seat, exclude: Permanent | None) -> list[tuple[Permanent, Cost, list]]:
        found = []
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude or (permanent.sick and "Creature" in permanent.card.type_line):
                continue
            ability = filter_mana_ability(permanent.card)
            if ability:
                found.append((permanent, parse_cost(ability[0]), ability[1]))
        return found

    def _perform(self, seat: Seat, action: str) -> None:
        if action.startswith(PLAY_LAND):
            card = _take(seat.hand, action.removeprefix(PLAY_LAND))
            self._enter(seat, Permanent(card))
            seat.lands_played += 1
            self.broadcast({"event": "play_land", "seat": seat.index, "card": card.name})
        elif action.startswith(CAST_COMMANDER):
            name = action.removeprefix(CAST_COMMANDER)
            card = next(c for c in seat.command_zone if c.name == name)
            self._cast(seat, card, seat.command_zone, from_command_zone=True)
            seat.commander_casts[name] = seat.commander_casts.get(name, 0) + 1
        elif action.startswith(CAST):
            card = next(c for c in seat.hand if c.name == action.removeprefix(CAST))
            self._cast(seat, card, seat.hand)
        elif action.startswith(ACTIVATE):
            sorcery_timing = seat.index == self.active and self.step in ("main1", "main2") and not self.stack
            permanent, ability = self._activations(seat, sorcery_timing)[action]
            self._activate(seat, permanent, ability)

    def _activate(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility) -> None:
        targets, labels = self._choose_targets(seat, ability.effects, permanent.card.name)
        tapped = self._ability_payment(seat, permanent, ability)
        self._spend_mana(tapped)
        if ability.tap:
            permanent.tapped = True
        if ability.life:
            self.change_life(seat, -ability.life)
        if ability.loyalty is not None:
            permanent.loyalty = (permanent.loyalty or 0) + ability.loyalty
            permanent.loyalty_turn = self.turn
        permanent.activated_turn[ability.text] = self.turn
        self.stack.append(StackItem(permanent.card, seat, list(ability.effects), targets, ability, permanent))
        self.broadcast({"event": "activate", "seat": seat.index, "card": permanent.card.name,
                        "ability": ability.text, "targets": labels, "tapped": [p.card.name for p in tapped]})
        if ability.sacrifice:
            self._leave_battlefield(permanent, "sacrificed")

    def _choose_targets(self, seat: Seat, effects, source_name: str) -> tuple[list, list[str]] | None:
        """Ask `seat` for a target per targeting effect: (targets, labels), or None if one has no legal target."""
        targets, labels = [], []
        for kind in (target_kind(e) for e in effects or []):
            if not kind:
                continue
            options = self.target_options(kind, seat)
            if not options:
                return None
            label, target = options[seat.player.choose(TARGET_PROMPT + source_name, [o[0] for o in options])]
            targets.append(target)
            labels.append(label)
        return targets, labels

    def _cast(self, seat: Seat, card: Card, zone: list[Card], from_command_zone: bool = False) -> None:
        effects = _effects(card)
        targets, labels = self._choose_targets(seat, effects, card.name)
        x = 0
        if parse_cost(card.mana_cost).x:
            options = [str(n) for n in range(self._max_x(seat, card, from_command_zone) + 1)]
            x = seat.player.choose(X_PROMPT + card.name, options)
        tapped = self._payment(seat, card, from_command_zone, x)
        self._spend_mana(tapped)
        zone.remove(card)
        self.stack.append(StackItem(card, seat, effects, targets, x=x))
        self.broadcast({"event": "cast", "seat": seat.index, "card": card.name,
                         "from": "command_zone" if from_command_zone else "hand",
                         "targets": labels, "x": x, "tapped": [p.card.name for p in tapped]})

    def _resolve(self, item: StackItem) -> None:
        seat, card = item.controller, item.card
        if item.ability:
            self._resolve_ability(item)
            return
        if _is_permanent(card):
            loyalty = int(card.loyalty) if card.loyalty and card.loyalty.isdigit() else None
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
            self._enter(seat, Permanent(card, sick=True, loyalty=loyalty), x=item.x)
            return
        if item.effects is None:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "unsupported": True})
            self._move_card(seat, card, "graveyard")
            return
        self._apply_effects(item)  # fizzled or not, the spell goes to the graveyard
        self._move_card(seat, card, "graveyard")

    def _resolve_ability(self, item: StackItem) -> None:
        seat, ability = item.controller, item.ability
        if getattr(ability, "optional", False) and seat.player.choose(OPTIONAL_PROMPT + item.card.name, YES_NO) != 0:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": item.card.name,
                            "ability": ability.text, "declined": True})
            return
        self._apply_effects(item)

    def amount(self, value: int | str) -> int:
        """A number from an effect; "X" is the resolving spell's X."""
        return self.x_value if value == "X" else value

    def _apply_effects(self, item: StackItem) -> bool:
        """Do a spell's or ability's effects; False if it fizzled because every target was gone (CR 608.2b)."""
        self.x_value = item.x
        try:
            return self._apply_effects_now(item)
        finally:
            self.x_value = 0

    def _apply_effects_now(self, item: StackItem) -> bool:
        seat = item.controller
        legal = [self.is_legal_target(target_kind(e), t, seat)
                 for e, t in zip([e for e in item.effects if target_kind(e)], item.targets)]
        about = {"seat": seat.index, "card": item.card.name}
        if item.ability:
            about["ability"] = item.ability.text
        if legal and not any(legal):
            self.broadcast({"event": "fizzle", **about})
            return False
        self.broadcast({"event": "resolve", **about})
        checks = iter(zip(item.targets, legal))
        previous = None  # the last targeting effect's target, for "Its controller ..." follow-ups
        for effect in item.effects:
            target = None
            if target_kind(effect):
                candidate, ok = next(checks)
                target = previous = candidate if ok else None
            elif follows_target(effect):
                target = previous
            elif uses_source(effect):
                target = item.source if item.source and self.on_battlefield(item.source) else None
            effect.resolve(self, seat, target)
        return True

    # --- triggered abilities -------------------------------------------------

    def trigger(self, event: str, permanent: Permanent, controller: Seat) -> None:
        """Note that `permanent`'s abilities for `event` triggered; they go on the stack
        the next time a player would get priority (CR 603.3)."""
        for ability in triggered_abilities(permanent.card):
            if ability.event == event:
                self.pending.append(PendingTrigger(ability, permanent, controller))

    def _put_triggers_on_stack(self) -> None:
        """Active player's triggers first, then the others in turn order (CR 603.3b).

        Targets are chosen now; an ability with no legal target is removed (CR 603.3d).
        """
        order = {seat.index: n for n, seat in enumerate(self.turn_order_from_active())}
        pending = sorted(self.pending, key=lambda t: order.get(t.controller.index, len(order)))
        self.pending = []
        for trigger in pending:
            seat = trigger.controller
            if seat.lost:
                continue
            chosen = self._choose_targets(seat, trigger.ability.effects, trigger.source.name)
            if chosen is None:
                continue
            targets, labels = chosen
            self.stack.append(StackItem(trigger.source, seat, list(trigger.ability.effects), targets, trigger.ability,
                                        trigger.permanent))
            self.broadcast({"event": "trigger", "seat": seat.index, "card": trigger.source.name,
                            "ability": trigger.ability.text, "targets": labels})

    # --- targets -------------------------------------------------------------

    def target_options(self, kind: str, caster: Seat) -> list[tuple[str, Any]]:
        """Legal targets of `kind` for a spell `caster` controls, as (label, object)."""
        options: list[tuple[str, Any]] = []
        if kind in ("any", "player", "player or planeswalker"):
            options += [(f"Player: {s.name} (seat {s.index})", s) for s in self.live_seats()]
        if kind == "spell":
            options += [(f"Spell: {i.card.name} (seat {i.controller.index})", i) for i in self.stack if not i.ability]
            return options
        kind, controller = _split_controller(kind)
        for seat in self.live_seats():
            if (controller == "opponent" and seat is caster) or (controller == "you" and seat is not caster):
                continue
            for n, permanent in enumerate(seat.battlefield):
                card = permanent.card
                if not _permanent_matches(kind, card) or self.has_keyword(permanent, "shroud"):
                    continue
                if self.has_keyword(permanent, "hexproof") and seat is not caster:
                    continue
                options.append((self.label(permanent), permanent))
        return options

    def label(self, permanent: Permanent) -> str:
        """How a permanent is shown in choices: "Grizzly Bears 2/2 (seat 1, #3)"."""
        seat = self.controller_of(permanent)
        n = next(i for i, p in enumerate(seat.battlefield) if p is permanent) + 1
        stats = ""
        if "Creature" in permanent.card.type_line:
            current = self.toughness(permanent)
            stats = f" {self.power(permanent)}/{permanent.card.toughness if current is None else current}"
        return f"{permanent.card.name}{stats} (seat {seat.index}, #{n})"

    def controller_of(self, permanent: Permanent) -> Seat | None:
        return next((s for s in self.seats if any(p is permanent for p in s.battlefield)), None)

    def on_battlefield(self, permanent: Permanent) -> bool:
        return self.controller_of(permanent) is not None

    def turn_order_from_active(self) -> list[Seat]:
        return [s for s in self._turn_order(self.active) if not s.lost]

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
                self.broadcast({"event": "drew", "seat": seat.index, "hand_size": len(seat.hand)}, skip=seat)

    def change_life(self, seat: Seat, amount: int) -> None:
        seat.life += amount
        self.broadcast({"event": "life", "seat": seat.index, "change": amount, "life": seat.life})

    def damage(self, target: Seat | Permanent, amount: int, source: Permanent | None = None,
               combat: bool = False) -> None:
        controller = self.controller_of(source) if source else None
        if isinstance(target, Seat):
            self.change_life(target, -amount)
            if combat and controller:
                self.trigger("combat_damage_to_player", source, controller)
            if combat and controller and source.card.name in controller.commander_names:
                key = (controller.index, source.card.name)
                target.commander_damage[key] = target.commander_damage.get(key, 0) + amount
                self.broadcast({"event": "commander_damage", "seat": target.index, "from_seat": controller.index,
                                "commander": source.card.name, "total": target.commander_damage[key]})
        else:
            if "Creature" in target.card.type_line:
                target.damage += amount
                if source and self.has_keyword(source, "deathtouch"):
                    target.deathtouched = True
            if target.loyalty is not None:
                target.loyalty -= amount
            self.broadcast({"event": "damage", "card": target.card.name, "amount": amount,
                            "source": source.card.name if source else None})
        if controller and self.has_keyword(source, "lifelink"):
            self.change_life(controller, amount)

    def destroy(self, permanent: Permanent) -> None:
        if self.has_keyword(permanent, "indestructible"):
            return
        self._leave_battlefield(permanent, "destroyed")

    # --- characteristics -----------------------------------------------------

    def modifiers(self, permanent: Permanent) -> list[Modifier]:
        """Everything currently changing a permanent: its "until end of turn" effects, plus
        static abilities of permanents its controller controls ("Creatures you control get +1/+1")."""
        mods = list(permanent.until_end_of_turn)
        controller = self.controller_of(permanent)
        if controller is None or "Creature" not in permanent.card.type_line:
            return mods
        subtypes = permanent.card.type_line.partition("—")[2].split()
        for source in controller.battlefield:
            for buff in static_abilities(source.card):
                if (buff.other and source is permanent) or (buff.subtype and buff.subtype not in subtypes):
                    continue
                mods.append(buff.modifier)
        return mods

    def power(self, permanent: Permanent) -> int:
        return characteristics.power(permanent, self.modifiers(permanent))

    def toughness(self, permanent: Permanent) -> int | None:
        return characteristics.toughness(permanent, self.modifiers(permanent))

    def has_keyword(self, permanent: Permanent, keyword: str) -> bool:
        """Printed or granted ("gains flying until end of turn", "Creatures you control have haste")."""
        return has_keyword(permanent.card, keyword) or any(keyword in m.keywords for m in self.modifiers(permanent))

    def modify_until_end_of_turn(self, permanent: Permanent, modifier: Modifier) -> None:
        permanent.until_end_of_turn.append(modifier)
        self.broadcast({"event": "modified", "card": permanent.card.name, "power": modifier.power,
                        "toughness": modifier.toughness, "keywords": sorted(modifier.keywords)})

    def put_counters(self, permanent: Permanent, counter: str, count: int) -> None:
        permanent.counters[counter] = permanent.counters.get(counter, 0) + count
        self.broadcast({"event": "counters", "card": permanent.card.name, "counter": counter,
                        "added": count, "total": permanent.counters[counter]})

    def create_tokens(self, seat: Seat, token: Card, count: int) -> None:
        for _ in range(count):
            self.broadcast({"event": "token_created", "seat": seat.index, "card": token.name,
                            "type_line": token.type_line, "power": token.power, "toughness": token.toughness})
            self._enter(seat, Permanent(token, sick=True))

    def exile(self, permanent: Permanent) -> None:
        self._leave_battlefield(permanent, "exiled", destination="exile")

    def exile_graveyard(self, seat: Seat) -> None:
        cards, seat.graveyard = seat.graveyard, []
        self.broadcast({"event": "graveyard_exiled", "seat": seat.index, "cards": [c.name for c in cards]})
        for card in cards:
            self._move_card(seat, card, "exile")

    def counter(self, item: StackItem) -> None:
        self.stack.remove(item)
        self.broadcast({"event": "countered", "seat": item.controller.index, "card": item.card.name})
        self._move_card(item.controller, item.card, "graveyard")

    def fetch_basic_land(self, seat: Seat, optional: bool = False) -> None:
        if optional and seat.player.choose(SEARCH_OPTIONAL_PROMPT, YES_NO) != 0:
            return
        basics = _unique([c for c in seat.library if "Basic" in c.type_line and "Land" in c.type_line])
        if basics:
            choice = basics[seat.player.choose(SEARCH_PROMPT, [c.name for c in basics])]
            seat.library.remove(choice)
            self.broadcast({"event": "put_onto_battlefield", "seat": seat.index, "card": choice.name, "tapped": True})
            self._enter(seat, Permanent(choice, tapped=True))
        self.rng.shuffle(seat.library)

    # --- helpers -------------------------------------------------------------

    def _enter(self, seat: Seat, permanent: Permanent, x: int = 0) -> None:
        for counter, count in enters_with_counters(permanent.card).items():  # CR 614.1c: it arrives with them
            permanent.counters[counter] = permanent.counters.get(counter, 0) + (x if count == "X" else count)
        seat.battlefield.append(permanent)
        self.trigger("enters", permanent, seat)

    def _leave_battlefield(self, permanent: Permanent, reason: str, destination: str = "graveyard") -> None:
        owner = next(s for s in self.seats if any(p is permanent for p in s.battlefield))
        permanent.last_power = self.power(permanent)
        owner.battlefield = [p for p in owner.battlefield if p is not permanent]
        permanent.last_controller = owner
        self.broadcast({"event": reason, "seat": owner.index, "card": permanent.card.name})
        if destination == "graveyard" and "Creature" in permanent.card.type_line:
            self.trigger("dies", permanent, owner)
        if _is_token(permanent.card):
            return  # tokens stop existing once they leave the battlefield (CR 111.7)
        self._move_card(owner, permanent.card, destination)

    def _move_card(self, seat: Seat, card: Card, zone: str) -> None:
        """Put a card into its owner's graveyard or exile; a commander may go to the
        command zone instead (CR 903.9a)."""
        if card.name in seat.commander_names:
            if seat.player.choose(COMMAND_ZONE_PROMPT, ["Command zone", zone.capitalize()]) == 0:
                seat.command_zone.append(card)
                self.broadcast({"event": "to_command_zone", "seat": seat.index, "card": card.name})
                return
        (seat.exile if zone == "exile" else seat.graveyard).append(card)

    def _check_state(self) -> None:
        """State-based actions (CR 704.5): losing the game, lethal damage, zero toughness or loyalty."""
        while True:
            changed = False
            for seat in self.live_seats():
                reason = ("life" if seat.life <= 0
                          else "empty_library" if seat.drew_from_empty
                          else "commander_damage" if any(d >= COMMANDER_DAMAGE_LIMIT for d in seat.commander_damage.values())
                          else None)
                if reason:
                    seat.lost = True
                    seat.battlefield = []  # CR 800.4a: their objects leave the game
                    self.stack = [item for item in self.stack if item.controller is not seat]
                    self.combat.attacks = [a for a in self.combat.attacks
                                           if a.defender is not seat and a.controller is not seat]
                    self.broadcast({"event": "player_lost", "seat": seat.index, "reason": reason})
                    changed = True
            for seat in self.live_seats():
                for permanent in list(seat.battlefield):
                    counters = permanent.counters
                    cancel = min(counters.get(PLUS, 0), counters.get(MINUS, 0))
                    if cancel:  # CR 704.5q
                        counters[PLUS] -= cancel
                        counters[MINUS] -= cancel
                    current = self.toughness(permanent)
                    creature = current is not None
                    if (creature and current <= 0) or (permanent.loyalty is not None and permanent.loyalty <= 0):
                        self._leave_battlefield(permanent, "died")
                        changed = True
                    elif (creature and (permanent.damage >= current or permanent.deathtouched)
                          and not self.has_keyword(permanent, "indestructible")):
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

    def broadcast(self, event: dict, skip: Seat | None = None) -> None:
        for seat in self.seats:
            if seat is not skip:
                seat.player.notify(event)


def _is_token(card: Card) -> bool:
    return card.type_line.startswith("Token")


def _is_permanent(card: Card) -> bool:
    return any(t in card.type_line for t in PERMANENT_TYPES)


def _effects(card: Card) -> list | None:
    """Spell effects for instants and sorceries; permanent spells just enter the battlefield."""
    return [] if _is_permanent(card) else spell_effects(card)


def _instant_speed(card: Card) -> bool:
    return "Instant" in card.type_line or has_keyword(card, "flash")


def _split_controller(kind: str) -> tuple[str, str | None]:
    """ "creature an opponent controls" -> ("creature", "opponent"); "creature" -> ("creature", None)."""
    for suffix, who in ((" an opponent controls", "opponent"), (" you don't control", "opponent"),
                        (" you control", "you")):
        if kind.endswith(suffix):
            return kind.removesuffix(suffix), who
    return kind, None


def _permanent_matches(kind: str, card: Card) -> bool:
    if kind == "any":
        return "Creature" in card.type_line or "Planeswalker" in card.type_line
    if kind == "permanent":
        return True
    if kind == "nonland permanent":
        return not is_land(card)
    return any(t.capitalize() in card.type_line for t in kind.split(" or ") if t != "player")


def _take(cards: list[Card], name: str) -> Card:
    card = next(c for c in cards if c.name == name)
    cards.remove(card)
    return card


def _unique(cards: list[Card]) -> list[Card]:
    return list({c.name: c for c in cards}.values())
