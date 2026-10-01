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
import re
from itertools import combinations
from dataclasses import dataclass, field
from typing import Any

from .analysis import is_land
from .cards import Card, Deck, has_keyword
from . import characteristics
from .characteristics import MINUS, PLUS, Modifier
from .combat import Combat
from .effects import (CANT_ATTACK, CANT_BLOCK, ActivatedAbility, AlternativeCost, AttachAura, Draw, EntersTapped, Modal,
                      TriggeredAbility, WardCounter,
                      activated_abilities, additional_costs, alternative_costs, cost_reductions, kicker_cost, attached_abilities, aura_kind, cycling_cost, enters_tapped_rule,
                      enters_with_counters, is_identity_mana_land, mana_pain, printed_protection, ward_cost,
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
CYCLE = "Cycle: "
SHOCK_PROMPT = "Pay life so it enters untapped? "  # followed by the land's name
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
SACRIFICE_PROMPT = "Choose a creature to sacrifice"
SACRIFICE_COST_PROMPT = "Choose what to sacrifice for "  # followed by the spell's name
COST_PROMPT = "Choose how to cast "  # followed by the spell's name; options: "Pay {2}{U}{U}", then alternative costs
KICKER_PROMPT = "Pay the kicker cost for "  # followed by the spell's name; options: YES_NO
PITCH_PROMPT = "Choose a card to exile from your hand"
WARD_PROMPT = "Pay the ward cost to keep "  # followed by the spell's or source's name; options: "Pay {2}", "Don't pay"
COLOR_NAMES = {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}
COLOR_LETTERS = {name: letter for letter, name in COLOR_NAMES.items()}
MODE_PROMPT = "Choose a mode for "  # followed by the spell's name; options are the modes, then DONE_MODES once enough are chosen
DONE_MODES = "Done choosing modes"
SEARCH_CARD_PROMPT = "Choose a card to search for"  # options are card names
SEARCH_LAND_PROMPT = "Choose a land to put onto the battlefield"
SEARCH_LAND_HAND_PROMPT = "Choose a land to put into your hand"
SCRY_PROMPT = "Scry: "  # followed by the card's name; options are KEEP_ON_TOP and PUT_ON_BOTTOM
SURVEIL_PROMPT = "Surveil: "  # options are KEEP_ON_TOP and PUT_IN_GRAVEYARD
KEEP_ON_TOP, PUT_ON_BOTTOM, PUT_IN_GRAVEYARD = "Keep on top", "Put on the bottom", "Put into your graveyard"
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
    owner: "Seat | None" = None  # whose card it is; None means its controller (the usual case)
    attached_to: "Permanent | None" = None  # the permanent this Equipment or Aura is attached to
    linked_exile: list = field(default_factory=list)  # (owner seat, card) exiled "until this leaves the battlefield"


@dataclass(frozen=True)
class ManaSource:
    """One mana a permanent can make when tapped, and whether making it hurts (painlands, Talismans)."""
    permanent: "Permanent"
    types: frozenset[str]  # one mana of one of these types
    pain: frozenset[str] = frozenset()  # types that deal `damage` to the controller when produced
    damage: int = 0


def _pain(source: ManaSource, symbol: frozenset[str] | None) -> int:
    """Damage for tapping `source` for mana paying `symbol` (None: generic, so any type will do)."""
    options = source.types if symbol is None else source.types & symbol
    return source.damage if source.pain and all(t in source.pain for t in options) else 0


class Payment(list):
    """The permanents to tap for a cost; `pain` is the damage their mana deals to the payer."""
    pain: int = 0


@dataclass(eq=False)
class GraveyardTarget:
    """A card in a graveyard chosen as a target."""
    card: Card
    seat: "Seat"  # whose graveyard


@dataclass(eq=False)
class StackItem:
    card: Card  # the spell, or the source of a triggered ability
    controller: "Seat"
    effects: list | None = field(default_factory=list)  # None: rules text not understood
    targets: list = field(default_factory=list)  # one per targeting effect, in order
    ability: TriggeredAbility | ActivatedAbility | None = None  # set for an ability rather than a spell
    source: "Permanent | None" = None  # the ability's source, for effects on "it"
    x: int = 0  # the value chosen for X when it was cast
    kicked: bool = False
    warding: "StackItem | None" = None  # for a ward trigger: the spell or ability it will counter unless paid for


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
        self.resolving_source: Permanent | None = None  # the source of the ability resolving right now
        self.resolving_item: StackItem | None = None  # what is resolving right now
        self.resolving_colors: frozenset[str] = frozenset()  # its colors (for protection from damage)

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
            for other in self.live_seats():  # "At the beginning of each upkeep / end step"
                for permanent in list(other.battlefield):
                    self.trigger("each_upkeep" if self.step == "upkeep" else "each_end_step", permanent, other)
        elif self.step == "beginning_of_combat":
            for permanent in list(seat.battlefield):
                self.trigger("combat", permanent, seat)
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
                self.send_state(holder)
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
        for card in _unique(seat.hand):
            cost = cycling_cost(card)
            if cost and self._pay_cost(seat, parse_cost(cost)) is not None:
                actions.append(CYCLE + card.name)
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
        return self._targets_exist(seat, ability.effects, frozenset(card.colors))

    def _ability_payment(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility) -> list[Permanent] | None:
        cost = parse_cost(ability.mana_cost) if ability.mana_cost else Cost()
        # A permanent can't tap for mana to pay for its own {T} or sacrifice ability.
        return self._pay_cost(seat, cost, exclude=permanent if ability.tap or ability.sacrifice else None)

    def commander_tax(self, seat: Seat, card: Card) -> int:
        return COMMANDER_TAX * seat.commander_casts.get(card.name, 0)

    def _can_cast(self, seat: Seat, card: Card, from_command_zone: bool = False) -> bool:
        if not self._cast_ways(seat, card, from_command_zone):
            return False
        effects, colors = _effects(card) or [], frozenset(card.colors)
        if effects and isinstance(effects[0], Modal):
            return sum(self._targets_exist(seat, modes, colors) for modes in effects[0].modes) >= effects[0].min
        return self._targets_exist(seat, effects, colors)

    def _spend_mana(self, seat: Seat, sources: list[Permanent]) -> None:
        """Tap the chosen mana sources; ones whose mana ability sacrifices them (Treasure) are sacrificed,
        and painlands and Talismans that made painful mana damage the payer."""
        for source in sources:
            source.tapped = True
            if not is_land(source.card) and mana_ability_sacrifices(source.card):
                self._leave_battlefield(source, "sacrificed")
        if pain := getattr(sources, "pain", 0):
            self.damage(seat, pain)

    def _mana_sources(self, seat: Seat, exclude: Permanent | None = None) -> list[ManaSource]:
        """One entry per mana each untapped permanent can make: nonland sources first,
        then lands, and sources that sacrifice themselves (Treasure) last."""
        abilities, lands, sacrifices = [], [], []
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude:
                continue
            card = permanent.card
            pain, damage = mana_pain(card) or (frozenset(), 0)
            if is_land(card):
                # Command Tower makes only the colors of your commander, whatever the card data lists.
                types = seat.color_identity if is_identity_mana_land(card) else frozenset(card.produced_mana)
                lands.append(ManaSource(permanent, types, pain, damage))
            elif not (permanent.sick and "Creature" in card.type_line):
                bucket = sacrifices if mana_ability_sacrifices(card) else abilities
                for mana in mana_ability(card, seat.color_identity) or []:
                    bucket.append(ManaSource(permanent, mana, pain, damage))
        return abilities + lands + sacrifices

    def _payment(self, seat: Seat, card: Card, from_command_zone: bool = False, x: int = 0,
                 alternative: AlternativeCost | None = None, kicked: bool = False) -> list[Permanent] | None:
        """The permanents to tap for `card` with X = `x`, or None if it can't be paid for now. An alternative
        cost replaces the mana cost; commander tax and kicker are added, then cost reductions apply."""
        cost = Cost() if alternative else parse_cost(card.mana_cost)
        if cost is None:
            return None
        if from_command_zone:
            cost = cost.plus_generic(self.commander_tax(seat, card))
        if kicked:
            cost = cost + parse_cost(kicker_cost(card))
        return self._pay_cost(seat, cost.with_x(x).reduced(self.cost_reduction(seat, card)))

    def cost_reduction(self, seat: Seat, card: Card) -> int:
        """How much less generic mana `card` costs `seat` (Medallions and the like)."""
        return sum(amount for p in seat.battlefield for kind, amount in cost_reductions(p.card)
                   if _spell_matches(kind, card))

    def _cast_ways(self, seat: Seat, card: Card, from_command_zone: bool) -> list[AlternativeCost | None]:
        """The ways `seat` can cast `card` now: None for its mana cost, then its alternative costs."""
        return [way for way in [None, *alternative_costs(card)]
                if self._can_pay_extras(seat, card, way) and self._payment(seat, card, from_command_zone, alternative=way)
                is not None]

    def _can_pay_extras(self, seat: Seat, card: Card, alternative: AlternativeCost | None) -> bool:
        """Whether `seat` can pay the parts of casting `card` that aren't mana: additional costs,
        and `alternative`'s condition, life and card to exile."""
        extras = additional_costs(card)
        others = list(seat.hand)
        if card in others:
            others.remove(card)
        if sum(c.life for c in extras) + (alternative.life if alternative else 0) > seat.life:  # CR 119.4
            return False
        if any(c.discard for c in extras) and not others:
            return False
        if any(c.sacrifice and not any(_permanent_matches(c.sacrifice, p.card) for p in seat.battlefield) for c in extras):
            return False
        if alternative is None:
            return True
        if alternative.commander and not any(p.card.name in (p.owner or seat).commander_names for p in seat.battlefield):
            return False
        if alternative.not_your_turn and self.active == seat.index:
            return False
        return not alternative.exile_color or any(alternative.exile_color in c.colors for c in others)

    def _pay_extras(self, seat: Seat, card: Card, alternative: AlternativeCost | None) -> None:
        """Pay the non-mana costs of casting `card`, which has already left its zone."""
        if alternative and alternative.exile_color:
            options = [c for c in seat.hand if alternative.exile_color in c.colors]
            exiled = options[seat.player.choose(PITCH_PROMPT, [c.name for c in options])]
            seat.hand.remove(exiled)
            self.broadcast({"event": "exiled_from_hand", "seat": seat.index, "card": exiled.name})
            self._move_card(seat, exiled, "exile")
        for extra in additional_costs(card):
            if extra.discard:
                discarded = seat.hand[seat.player.choose(DISCARD_PROMPT, [c.name for c in seat.hand])]
                seat.hand.remove(discarded)
                self.broadcast({"event": "discard", "seat": seat.index, "card": discarded.name})
                self._move_card(seat, discarded, "graveyard")
            if extra.sacrifice:
                options = [p for p in seat.battlefield if _permanent_matches(extra.sacrifice, p.card)]
                choice = options[seat.player.choose(SACRIFICE_COST_PROMPT + card.name, [self.label(p) for p in options])]
                self._leave_together([(choice, "sacrificed")])
        life = sum(c.life for c in additional_costs(card)) + (alternative.life if alternative else 0)
        if life:
            self.change_life(seat, -life)

    def _max_x(self, seat: Seat, card: Card, from_command_zone: bool, kicked: bool) -> int:
        x = 0
        while x < MAX_X and self._payment(seat, card, from_command_zone, x + 1, kicked=kicked) is not None:
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

    def _pay_with_filters(self, cost: Cost, sources: list[ManaSource], combo) -> Payment | None:
        activation = sum((c for _, c, _ in combo), Cost())
        paid_first: dict[int, frozenset[str]] = {}
        first = pay(activation, [s.types for s in sources], paid_first)
        if first is None:
            return None
        rest = [s for i, s in enumerate(sources) if i not in first]
        made = [ManaSource(permanent, mana) for permanent, _, units in combo for mana in units]
        pool = rest + made
        paid_second: dict[int, frozenset[str]] = {}
        second = pay(cost, [s.types for s in pool], paid_second)
        if second is None:
            return None
        used = [sources[i].permanent for i in first] + [pool[i].permanent for i in second] + [p for p, _, _ in combo]
        # A permanent that makes several mana (Sol Ring) is tapped once.
        payment = Payment({id(p): p for p in used}.values())
        payment.pain = (sum(_pain(sources[i], paid_first.get(i)) for i in first)
                        + sum(_pain(pool[i], paid_second.get(i)) for i in second))
        return payment

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
        elif action.startswith(CYCLE):
            self._cycle(seat, _take(seat.hand, action.removeprefix(CYCLE)))
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

    def _cycle(self, seat: Seat, card: Card) -> None:
        """Cycling: pay the cost, discard the card, and draw a card when the ability resolves."""
        cost = cycling_cost(card)
        tapped = self._pay_cost(seat, parse_cost(cost))
        self._spend_mana(seat, tapped)
        ability = ActivatedAbility(f"Cycling {cost}", (Draw(1),), mana_cost=cost)
        self.broadcast({"event": "discard", "seat": seat.index, "card": card.name, "reason": "cycling"})
        self._move_card(seat, card, "graveyard")
        self.stack.append(StackItem(card, seat, [Draw(1)], [], ability))
        self.broadcast({"event": "activate", "seat": seat.index, "card": card.name, "ability": _shown(ability.text, card),
                        "targets": [], "tapped": [p.card.name for p in tapped]})

    def _activate(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility) -> None:
        targets, labels = self._choose_targets(seat, ability.effects, permanent.card.name, permanent,
                                               frozenset(permanent.card.colors))
        tapped = self._ability_payment(seat, permanent, ability)
        self._spend_mana(seat, tapped)
        if ability.tap:
            permanent.tapped = True
        if ability.life:
            self.change_life(seat, -ability.life)
        if ability.loyalty is not None:
            permanent.loyalty = (permanent.loyalty or 0) + ability.loyalty
            permanent.loyalty_turn = self.turn
        permanent.activated_turn[ability.text] = self.turn
        item = StackItem(permanent.card, seat, list(ability.effects), targets, ability, permanent)
        self.stack.append(item)
        self.broadcast({"event": "activate", "seat": seat.index, "card": permanent.card.name,
                        "ability": _shown(ability.text, permanent.card), "targets": labels,
                        "tapped": [p.card.name for p in tapped]})
        self._check_ward(item)
        if ability.sacrifice:
            self._leave_battlefield(permanent, "sacrificed")

    def _targets_exist(self, seat: Seat, effects, colors: frozenset[str] = frozenset()) -> bool:
        return all(self.target_options(kind, seat, colors) for kind in map(target_kind, effects) if kind)

    def _choose_modes(self, seat: Seat, card: Card, modal: Modal) -> list:
        """Ask the caster for the modes of a modal spell (only ones with legal targets are offered) and
        return the chosen modes' effects in printed order."""
        colors = frozenset(card.colors)
        available = [i for i, effects in enumerate(modal.modes) if self._targets_exist(seat, effects, colors)]
        chosen: list[int] = []
        while len(chosen) < modal.max and len(chosen) < len(available):
            remaining = [i for i in available if i not in chosen]
            options = [_shown(modal.texts[i], card) for i in remaining]
            if len(chosen) >= modal.min:
                options.append(DONE_MODES)
            pick = seat.player.choose(MODE_PROMPT + card.name, options)
            if pick == len(remaining):
                break
            chosen.append(remaining[pick])
        return [effect for i in sorted(chosen) for effect in modal.modes[i]]

    def _choose_targets(self, seat: Seat, effects, source_name: str, source: Permanent | None = None,
                        colors: frozenset[str] = frozenset()) -> tuple[list, list[str]] | None:
        """Ask `seat` for a target per targeting effect: (targets, labels), or None if one has no legal target.
        "Another target ..." can't be `source` itself, and nothing with protection from `colors` (the
        colors of the spell or source) can be chosen."""
        targets, labels = [], []
        for effect in effects or []:
            kind = target_kind(effect)
            if not kind:
                continue
            options = [o for o in self.target_options(kind, seat, colors)
                       if not (getattr(effect, "another", False) and o[1] is source)]
            if not options:
                return None
            label, target = options[seat.player.choose(TARGET_PROMPT + source_name, [o[0] for o in options])]
            targets.append(target)
            labels.append(label)
        return targets, labels

    def _cast(self, seat: Seat, card: Card, zone: list[Card], from_command_zone: bool = False) -> None:
        effects = _effects(card)
        if effects and isinstance(effects[0], Modal):
            effects = self._choose_modes(seat, card, effects[0])
        targets, labels = self._choose_targets(seat, effects, card.name, colors=frozenset(card.colors))
        ways = self._cast_ways(seat, card, from_command_zone)
        alternative = ways[0]
        if len(ways) > 1:
            options = [f"Pay {card.mana_cost}" if way is None else way.text for way in ways]
            alternative = ways[seat.player.choose(COST_PROMPT + card.name, options)]
        # Kicker is only offered on instants and sorceries: nothing reads it on permanents yet.
        kicked = (not _is_permanent(card) and kicker_cost(card) is not None
                  and self._payment(seat, card, from_command_zone, alternative=alternative, kicked=True) is not None
                  and seat.player.choose(KICKER_PROMPT + card.name, YES_NO) == 0)
        x = 0
        if alternative is None and parse_cost(card.mana_cost).x:  # casting without paying the mana cost makes X 0
            options = [str(n) for n in range(self._max_x(seat, card, from_command_zone, kicked) + 1)]
            x = seat.player.choose(X_PROMPT + card.name, options)
        tapped = self._payment(seat, card, from_command_zone, x, alternative, kicked)
        self._spend_mana(seat, tapped)
        zone.remove(card)
        self._pay_extras(seat, card, alternative)
        item = StackItem(card, seat, effects, targets, x=x, kicked=kicked)
        self.stack.append(item)
        event = {"event": "cast", "seat": seat.index, "card": card.name,
                 "from": "command_zone" if from_command_zone else "hand",
                 "targets": labels, "x": x, "tapped": [p.card.name for p in tapped]}
        if kicked:
            event["kicked"] = True
        if alternative:
            event["alternative"] = alternative.text
        self.broadcast(event)
        self._observe("cast", card, seat)
        self._check_ward(item)

    # --- what players see ----------------------------------------------------

    def snapshot(self, viewer: Seat) -> dict:
        """The board as `viewer` may see it: everything public, plus their own hand. Opponents' hands and
        libraries show as counts only. It's plain data, ready to send as JSON."""
        return {
            "turn": self.turn, "step": self.step, "active": self.active, "you": viewer.index,
            "stack": [{"card": i.card.name, "seat": i.controller.index, "ability": _shown(i.ability.text, i.card) if i.ability else None}
                      for i in self.stack],
            "hand": [c.name for c in viewer.hand],
            "seats": [{
                "seat": s.index, "name": s.name, "life": s.life, "lost": s.lost,
                "hand": len(s.hand), "library": len(s.library),
                "graveyard": [c.name for c in s.graveyard], "exile": [c.name for c in s.exile],
                "command_zone": [{"name": c.name, "tax": self.commander_tax(s, c)} for c in s.command_zone],
                "commander_damage": [{"from_seat": seat, "commander": name, "damage": dmg}
                                     for (seat, name), dmg in s.commander_damage.items()],
                "battlefield": [self._permanent_view(p) for p in s.battlefield],
            } for s in self.seats],
        }

    def _permanent_view(self, p: Permanent) -> dict:
        creature = "Creature" in p.card.type_line
        host = p.attached_to
        return {
            "name": p.card.name, "type": p.card.type_line, "tapped": p.tapped, "token": _is_token(p.card),
            "sick": p.sick and creature,
            "power": self.power(p) if creature else None, "toughness": self.toughness(p) if creature else None,
            "damage": p.damage, "loyalty": p.loyalty, "counters": {k: v for k, v in p.counters.items() if v},
            "attached_to": host.card.name if host is not None and self.on_battlefield(host) else None,
        }

    def send_state(self, seat: Seat) -> None:
        """Show the board to a player who wants to see it (TCP players do; bots don't)."""
        if getattr(seat.player, "wants_state", False):
            seat.player.notify({"event": "state", **self.snapshot(seat)})

    def _resolve(self, item: StackItem) -> None:
        seat, card = item.controller, item.card
        if item.ability:
            self._resolve_ability(item)
            return
        if _is_permanent(card) and aura_kind(card):
            self._resolve_aura(item)
            return
        if _is_permanent(card):
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
            self._enter(seat, Permanent(card, sick=True, loyalty=_starting_loyalty(card)), x=item.x)
            return
        if item.effects is None:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "unsupported": True})
            self._move_card(seat, card, "graveyard")
            return
        self._apply_effects(item)  # fizzled or not, the spell goes to the graveyard
        self._move_card(seat, card, "graveyard")

    def _resolve_aura(self, item: StackItem) -> None:
        """An Aura spell enters attached to its target, or goes to the graveyard if the target
        is no longer legal (CR 608.3b)."""
        seat, card = item.controller, item.card
        target = item.targets[0] if item.targets else None
        if target is None or not self.is_legal_target(aura_kind(card), target, seat, frozenset(card.colors)):
            self.broadcast({"event": "fizzle", "seat": seat.index, "card": card.name})
            self._move_card(seat, card, "graveyard")
            return
        self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
        self._enter(seat, Permanent(card, sick=True, attached_to=target))
        self.broadcast({"event": "attached", "card": card.name, "to": target.card.name})

    def attach(self, attachment: Permanent, creature: Permanent) -> None:
        """Attach an Equipment to a creature (moving it if it was on another)."""
        if self.on_battlefield(attachment) and self.on_battlefield(creature):
            attachment.attached_to = creature
            self.broadcast({"event": "attached", "card": attachment.card.name, "to": creature.card.name})

    def _resolve_ability(self, item: StackItem) -> None:
        seat, ability = item.controller, item.ability
        if getattr(ability, "optional", False) and seat.player.choose(OPTIONAL_PROMPT + item.card.name, YES_NO) != 0:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": item.card.name,
                            "ability": _shown(ability.text, item.card), "declined": True})
            return
        self._apply_effects(item)

    def amount(self, value: int | str) -> int:
        """A number from an effect; "X" is the resolving spell's X."""
        return self.x_value if value == "X" else value

    def _apply_effects(self, item: StackItem) -> bool:
        """Do a spell's or ability's effects; False if it fizzled because every target was gone (CR 608.2b)."""
        self.x_value, self.resolving_source = item.x, item.source
        self.resolving_item, self.resolving_colors = item, frozenset(item.card.colors)
        try:
            return self._apply_effects_now(item)
        finally:
            self.x_value, self.resolving_source = 0, None
            self.resolving_item, self.resolving_colors = None, frozenset()

    def _apply_effects_now(self, item: StackItem) -> bool:
        seat = item.controller
        colors = frozenset(item.card.colors)
        legal = [self.is_legal_target(target_kind(e), t, seat, colors)
                 for e, t in zip([e for e in item.effects if target_kind(e)], item.targets)]
        about = {"seat": seat.index, "card": item.card.name}
        if item.ability:
            about["ability"] = _shown(item.ability.text, item.card)
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
            if ability.event == event and ability.watch is None:
                self.pending.append(PendingTrigger(ability, permanent, controller))

    def _observe(self, event: str, card: Card, seat: Seat, subject: Permanent | None = None,
                 extra: list[tuple[Permanent, Seat]] = ()) -> None:
        """Trigger abilities that watch for `event` happening to `card` (controlled by `seat`):
        "Whenever another creature enters", landfall, "whenever a creature dies",
        "whenever you cast a spell". `extra` adds watchers that just left the battlefield
        and still "look back in time" (CR 603.10a)."""
        watchers = [(p, s) for s in self.live_seats() for p in s.battlefield] + list(extra)
        for watcher, watcher_seat in watchers:
            for ability in triggered_abilities(watcher.card):
                watch = ability.watch
                if not watch or ability.event != event:
                    continue
                if watch.other and subject is watcher:
                    continue
                if event == "cast":
                    if watch.caster == "you" and watcher_seat is not seat:
                        continue
                    if watch.caster == "opponent" and watcher_seat is seat:
                        continue
                elif watch.yours and watcher_seat is not seat:
                    continue
                if watch.nontoken and _is_token(card):
                    continue
                if not _watch_type_matches(watch.kind, card):
                    continue
                self.pending.append(PendingTrigger(ability, watcher, watcher_seat))

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
            chosen = self._choose_targets(seat, trigger.ability.effects, trigger.source.name, trigger.permanent,
                                          frozenset(trigger.source.colors))
            if chosen is None:
                continue
            targets, labels = chosen
            item = StackItem(trigger.source, seat, list(trigger.ability.effects), targets, trigger.ability,
                             trigger.permanent)
            self.stack.append(item)
            self.broadcast({"event": "trigger", "seat": seat.index, "card": trigger.source.name,
                            "ability": _shown(trigger.ability.text, trigger.source), "targets": labels})
            self._check_ward(item)

    # --- targets -------------------------------------------------------------

    def target_options(self, kind: str, caster: Seat, colors: frozenset[str] = frozenset()) -> list[tuple[str, Any]]:
        """Legal targets of `kind` for a spell or ability `caster` controls, as (label, object). `colors` are the
        colors of the source: a permanent with protection from one of them can't be chosen."""
        options: list[tuple[str, Any]] = []
        if kind.startswith("graveyard:"):  # "graveyard:<card type>:<yours|any>"
            _, card_type, whose = kind.split(":")
            for seat in self.live_seats():
                if whose == "yours" and seat is not caster:
                    continue
                options += [(f"{card.name} (seat {seat.index} graveyard)", GraveyardTarget(card, seat))
                            for card in _unique(seat.graveyard) if _card_matches(card_type, card)]
            return options
        if kind in ("any", "player", "player or planeswalker"):
            options += [(f"Player: {s.name} (seat {s.index})", s) for s in self.live_seats()]
        elif kind == "opponent":
            options += [(f"Player: {s.name} (seat {s.index})", s) for s in self.opponents(caster)]
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
                if self.protected_from(permanent, colors):
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
        host = permanent.attached_to
        attached = f" attached to {host.card.name}" if host is not None and self.on_battlefield(host) else ""
        return f"{permanent.card.name}{stats}{attached} (seat {seat.index}, #{n})"

    def controller_of(self, permanent: Permanent) -> Seat | None:
        return next((s for s in self.seats if any(p is permanent for p in s.battlefield)), None)

    def on_battlefield(self, permanent: Permanent) -> bool:
        return self.controller_of(permanent) is not None

    def turn_order_from_active(self) -> list[Seat]:
        return [s for s in self._turn_order(self.active) if not s.lost]

    def protected_from(self, permanent: Permanent, colors: frozenset[str]) -> bool:
        """Whether the permanent has protection from any of these colors (letters), by its own text or
        because something gave it: it can't be targeted, damaged, blocked, enchanted or equipped by them."""
        if not colors:
            return False
        granted = {kw for mod in self.modifiers(permanent) for kw in mod.keywords if kw.startswith("protection from ")}
        printed = printed_protection(permanent.card)
        return any(c in printed or f"protection from {COLOR_NAMES[c]}" in granted for c in colors)

    def is_legal_target(self, kind: str, target: Any, caster: Seat, colors: frozenset[str] = frozenset()) -> bool:
        for _, option in self.target_options(kind, caster, colors):
            if option is target:
                return True
            if (isinstance(option, GraveyardTarget) and isinstance(target, GraveyardTarget)
                    and option.seat is target.seat and option.card == target.card):
                return True  # identical copies are interchangeable
        return False

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
        if amount:  # "Whenever you gain life" / "Whenever you lose life": once per event, not per point
            for permanent in list(seat.battlefield):
                self.trigger("gain_life" if amount > 0 else "lose_life", permanent, seat)

    def damage(self, target: Seat | Permanent, amount: int, source: Permanent | None = None,
               combat: bool = False) -> None:
        colors = frozenset(source.card.colors) if source is not None else self.resolving_colors
        if isinstance(target, Permanent) and self.protected_from(target, colors):
            self.broadcast({"event": "damage_prevented", "card": target.card.name, "amount": amount})
            return
        controller = self.controller_of(source) if source else None
        if isinstance(target, Seat):
            self.change_life(target, -amount)
            if combat and controller:
                self.trigger("combat_damage_to_player", source, controller)
                for permanent in list(controller.battlefield):  # "Whenever a creature (token) you control deals ..."
                    self.trigger("ally_combat_damage", permanent, controller)
                    if _is_token(source.card):
                        self.trigger("token_combat_damage", permanent, controller)
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

    def mass_targets(self, kind: str, caster: Seat) -> list[Permanent]:
        """Every permanent an "all"/"each" effect of `kind` affects, e.g. "creature",
        "artifact or enchantment", "creature you don't control". Nothing is targeted."""
        kind, controller = _split_controller(kind)
        found: list[Permanent] = []
        for seat in self.live_seats():
            if (controller == "opponent" and seat is caster) or (controller == "you" and seat is not caster):
                continue
            found += [p for p in seat.battlefield if _permanent_matches(kind, p.card)]
        return found

    def destroy_all(self, permanents: list[Permanent]) -> None:
        """Destroy them all at once; indestructible ones survive."""
        self._leave_together([(p, "destroyed") for p in permanents if not self.has_keyword(p, "indestructible")])

    def exile_all(self, permanents: list[Permanent]) -> None:
        self._leave_together([(p, "exiled") for p in permanents], destination="exile")

    def return_to_hand(self, permanent: Permanent) -> None:
        """Bounce: a permanent goes to its owner's hand (a token just stops existing)."""
        self._leave_together([(permanent, "returned")], destination="hand")

    def return_all_to_hand(self, permanents: list[Permanent]) -> None:
        self._leave_together([(p, "returned") for p in permanents], destination="hand")

    def return_from_graveyard(self, target: GraveyardTarget, controller: Seat, to: str) -> None:
        """Move a card out of a graveyard to its owner's hand, or onto the battlefield under
        `controller`'s control (it stays its owner's card)."""
        seat, card = target.seat, target.card
        if card not in seat.graveyard:
            return
        seat.graveyard.remove(card)
        self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": to})
        if to == "hand":
            seat.hand.append(card)
        else:
            self._enter(controller, Permanent(card, sick=True, loyalty=_starting_loyalty(card), owner=seat))

    def exile_from_graveyard(self, target: GraveyardTarget) -> None:
        seat, card = target.seat, target.card
        if card in seat.graveyard:
            seat.graveyard.remove(card)
            self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": "exile"})
            self._move_card(seat, card, "exile")

    def tutor(self, seat: Seat, card_type: str, to: str, reveal: bool) -> None:
        """Search the library for a card of `card_type`: it goes to the hand (`to` is "hand")
        or to the top of the library ("top") after shuffling. Only "reveal" shows others which card."""
        matches = _unique([c for c in seat.library if _card_matches(card_type, c)])
        found = None
        if matches:
            found = matches[seat.player.choose(SEARCH_CARD_PROMPT, [c.name for c in matches])]
            seat.library.remove(found)
        self.rng.shuffle(seat.library)
        if found is None:
            self.broadcast({"event": "searched", "seat": seat.index, "found": False})
            return
        if to == "hand":
            seat.hand.append(found)
        else:
            seat.library.insert(0, found)
        self.broadcast({"event": "searched", "seat": seat.index, "found": True, "to": to,
                        **({"card": found.name} if reveal else {})}, skip=seat)
        seat.player.notify({"event": "searched", "seat": seat.index, "found": True, "to": to, "card": found.name})

    def sacrifice(self, seat: Seat) -> None:
        """`seat` chooses one of its creatures and sacrifices it; it dies (no targeting, so
        hexproof and indestructible don't help)."""
        creatures = [p for p in seat.battlefield if "Creature" in p.card.type_line]
        if creatures:
            choice = creatures[seat.player.choose(SACRIFICE_PROMPT, [self.label(p) for p in creatures])]
            self._leave_together([(choice, "sacrificed")])

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
        for seat in self.seats:  # Equipment and Auras attached to it
            for attachment in seat.battlefield:
                if attachment.attached_to is permanent:
                    mods.extend(buff.modifier for buff in attached_abilities(attachment.card))
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

    def exile_until_leaves(self, target: Permanent, source: Permanent | None) -> None:
        """Exile `target` until `source` leaves the battlefield. If the source is already gone, nothing
        is exiled. A token is exiled for good, since it would stop existing anyway."""
        if source is not None and not self.on_battlefield(source):
            return
        owner = target.owner or self.controller_of(target)
        card, before = target.card, len(owner.exile)
        self.exile(target)
        if source is not None and not _is_token(card) and len(owner.exile) > before:  # not sent to the command zone
            source.linked_exile.append((owner, card))

    def _return_from_exile(self, seat: Seat, card: Card) -> None:
        """A card exiled "until" comes back as a new permanent under its owner's control."""
        if seat.lost or card not in seat.exile:
            return
        seat.exile.remove(card)
        self.broadcast({"event": "returned_from_exile", "seat": seat.index, "card": card.name})
        self._enter(seat, Permanent(card, sick=True, loyalty=_starting_loyalty(card), owner=seat))

    def exile_graveyard(self, seat: Seat) -> None:
        cards, seat.graveyard = seat.graveyard, []
        self.broadcast({"event": "graveyard_exiled", "seat": seat.index, "cards": [c.name for c in cards]})
        for card in cards:
            self._move_card(seat, card, "exile")

    def counter(self, item: StackItem) -> None:
        self.stack.remove(item)
        self.broadcast({"event": "countered", "seat": item.controller.index, "card": item.card.name,
                        "ability": _shown(item.ability.text, item.card) if item.ability else None})
        if not item.ability:  # countering an ability doesn't touch its source
            self._move_card(item.controller, item.card, "graveyard")

    def _check_ward(self, item: StackItem) -> None:
        """Whenever a permanent with ward becomes the target of an opponent's spell or ability, a ward trigger
        goes on the stack above it (CR 702.21a)."""
        for target in item.targets:
            if not isinstance(target, Permanent):
                continue
            owner = self.controller_of(target)
            cost = ward_cost(target.card)
            if owner is None or owner is item.controller or not cost:
                continue
            ability = TriggeredAbility("ward", (WardCounter(cost),), False, f"Ward {cost}")
            self.stack.append(StackItem(target.card, owner, list(ability.effects), [], ability, target, warding=item))
            self.broadcast({"event": "trigger", "seat": owner.index, "card": target.card.name,
                            "ability": ability.text, "targets": []})

    def resolve_ward(self, cost_text: str) -> None:
        """The spell or ability that targeted a warded permanent is countered unless its controller pays."""
        ward = self.resolving_item
        item = ward.warding if ward else None
        if item is None or item not in self.stack:
            return
        payer = item.controller
        payment = self._pay_cost(payer, parse_cost(cost_text))
        if payment is not None and payer.player.choose(WARD_PROMPT + item.card.name,
                                                       [f"Pay {cost_text}", "Don't pay"]) == 0:
            self._spend_mana(payer, payment)
            self.broadcast({"event": "ward_paid", "seat": payer.index, "card": ward.card.name, "cost": cost_text})
            return
        self.counter(item)

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

    def search_for_lands(self, seat: Seat, count: int, subtypes: tuple[str, ...], battlefield: int,
                         tapped: bool, reveal: bool) -> None:
        """Search for up to `count` lands (basic lands, or any land with one of `subtypes`): the first
        `battlefield` go onto the battlefield and the rest into the hand, then the library is shuffled."""
        to_battlefield: list[Card] = []
        to_hand: list[Card] = []
        for n in range(count):
            matches = _unique([c for c in seat.library if _is_searched_land(c, subtypes)])
            if not matches:
                break
            onto = n < battlefield
            card = matches[seat.player.choose(SEARCH_LAND_PROMPT if onto else SEARCH_LAND_HAND_PROMPT,
                                              [c.name for c in matches])]
            seat.library.remove(card)
            (to_battlefield if onto else to_hand).append(card)
        self.rng.shuffle(seat.library)
        for card in to_battlefield:
            self.broadcast({"event": "put_onto_battlefield", "seat": seat.index, "card": card.name, "tapped": tapped})
            self._enter(seat, Permanent(card, tapped=tapped))
        for card in to_hand:
            seat.hand.append(card)
            self.broadcast({"event": "revealed" if reveal else "searched", "seat": seat.index,
                            **({"card": card.name} if reveal else {"found": True, "to": "hand"})}, skip=None if reveal else seat)
            if not reveal:
                seat.player.notify({"event": "searched", "seat": seat.index, "found": True, "to": "hand", "card": card.name})
        if not (to_battlefield or to_hand):
            self.broadcast({"event": "searched", "seat": seat.index, "found": False})

    def scry(self, seat: Seat, count: int) -> None:
        """Look at the top `count` cards and put any of them on the bottom; the rest stay on top in
        their order. Only the scrying player sees the cards."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        kept, bottom = [], []
        for card in top:
            choice = seat.player.choose(SCRY_PROMPT + card.name, [KEEP_ON_TOP, PUT_ON_BOTTOM])
            (kept if choice == 0 else bottom).append(card)
        seat.library = kept + seat.library + bottom
        self.broadcast({"event": "scry", "seat": seat.index, "count": len(top)}, skip=seat)
        seat.player.notify({"event": "scry", "seat": seat.index, "count": len(top), "bottom": [c.name for c in bottom]})

    def surveil(self, seat: Seat, count: int) -> None:
        """Look at the top `count` cards and put any of them into the graveyard (which everyone sees)."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        kept, binned = [], []
        for card in top:
            choice = seat.player.choose(SURVEIL_PROMPT + card.name, [KEEP_ON_TOP, PUT_IN_GRAVEYARD])
            (kept if choice == 0 else binned).append(card)
        seat.library = kept + seat.library
        self.broadcast({"event": "surveil", "seat": seat.index, "count": len(top), "graveyard": [c.name for c in binned]})
        for card in binned:
            self._move_card(seat, card, "graveyard")

    def mill(self, seat: Seat, count: int) -> None:
        """Put the top `count` cards of the library into the graveyard (fewer if there aren't that many)."""
        milled = [seat.library.pop(0) for _ in range(min(count, len(seat.library)))]
        self.broadcast({"event": "milled", "seat": seat.index, "cards": [c.name for c in milled]})
        for card in milled:
            self._move_card(seat, card, "graveyard")

    # --- helpers -------------------------------------------------------------

    def _enter(self, seat: Seat, permanent: Permanent, x: int = 0) -> None:
        for counter, count in enters_with_counters(permanent.card).items():  # CR 614.1c: it arrives with them
            permanent.counters[counter] = permanent.counters.get(counter, 0) + (x if count == "X" else count)
        permanent.owner = permanent.owner or seat
        rule = enters_tapped_rule(permanent.card)
        if rule and self._enters_tapped(seat, rule, permanent.card):
            permanent.tapped = True
        seat.battlefield.append(permanent)
        self.trigger("enters", permanent, seat)
        self._observe("permanent_enters", permanent.card, seat, subject=permanent)

    def _enters_tapped(self, seat: Seat, rule: EntersTapped, card: Card) -> bool:
        """Whether a permanent entering under `seat`'s control enters tapped, given the lands it sees
        (it isn't on the battlefield yet, so "other lands" are all the lands there)."""
        lands = sum(1 for p in seat.battlefield if is_land(p.card))
        if rule.kind == "always":
            return True
        if rule.kind == "unless_land_types":
            return not any(t in p.card.type_line for p in seat.battlefield for t in rule.types)
        if rule.kind == "unless_lands_at_most":
            return lands > rule.count
        if rule.kind == "unless_lands_at_least":
            return lands < rule.count
        if rule.kind == "unless_opponents":
            return len(self.opponents(seat)) < rule.count
        # Shock land: you may pay life. (You can only pay life you have to spare.)
        if seat.life > rule.life and seat.player.choose(SHOCK_PROMPT + card.name,
                                                        [f"Pay {rule.life} life", "Enter tapped"]) == 0:
            self.change_life(seat, -rule.life)
            return False
        return True

    def _leave_battlefield(self, permanent: Permanent, reason: str, destination: str = "graveyard") -> None:
        self._leave_together([(permanent, reason)], destination)

    def _leave_together(self, leaving: list[tuple[Permanent, str]], destination: str = "graveyard") -> None:
        """Permanents leave the battlefield at the same moment (a board wipe, or several
        creatures with lethal damage). They all see each other go (CR 603.10a), so a creature
        that watches for deaths triggers for every other creature that died with it."""
        leaving = [(p, reason) for p, reason in leaving if self.on_battlefield(p)]
        for permanent, _ in leaving:
            permanent.last_power = self.power(permanent)
            permanent.last_controller = self.controller_of(permanent)
        for permanent, _ in leaving:
            owner = permanent.last_controller
            owner.battlefield = [p for p in owner.battlefield if p is not permanent]
        gone = [(permanent, permanent.last_controller) for permanent, _ in leaving]
        for permanent, reason in leaving:
            self.broadcast({"event": reason, "seat": permanent.last_controller.index, "card": permanent.card.name})
        for permanent, reason in leaving:
            if reason == "sacrificed" and "Creature" in permanent.card.type_line:
                # "Whenever you sacrifice a creature" looks back in time, so the sacrificed creature sees itself go.
                controller = permanent.last_controller
                for watcher in controller.battlefield + [p for p, _ in leaving if p.last_controller is controller]:
                    self.trigger("sacrifice_creature", watcher, controller)
        for permanent, _ in leaving:
            controller = permanent.last_controller
            if destination == "graveyard" and "Creature" in permanent.card.type_line:
                self.trigger("dies", permanent, controller)
                self._observe("creature_dies", permanent.card, controller, subject=permanent, extra=gone)
            if not _is_token(permanent.card):  # tokens stop existing once they leave (CR 111.7)
                self._move_card(permanent.owner or controller, permanent.card, destination)
        for permanent, _ in leaving:  # whatever they were holding in exile comes back
            held, permanent.linked_exile = permanent.linked_exile, []
            for seat, card in held:
                self._return_from_exile(seat, card)

    def _move_card(self, seat: Seat, card: Card, zone: str) -> None:
        """Put a card into its owner's graveyard, exile or hand; a commander may go to the
        command zone instead (CR 903.9)."""
        if card.name in seat.commander_names:
            if seat.player.choose(COMMAND_ZONE_PROMPT, ["Command zone", zone.capitalize()]) == 0:
                seat.command_zone.append(card)
                self.broadcast({"event": "to_command_zone", "seat": seat.index, "card": card.name})
                return
        {"exile": seat.exile, "hand": seat.hand, "graveyard": seat.graveyard}[zone].append(card)

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
            dying: list[tuple[Permanent, str]] = []
            for seat in self.live_seats():
                for permanent in list(seat.battlefield):
                    counters = permanent.counters
                    cancel = min(counters.get(PLUS, 0), counters.get(MINUS, 0))
                    if cancel:  # CR 704.5q
                        counters[PLUS] -= cancel
                        counters[MINUS] -= cancel
                    host = permanent.attached_to
                    if host is not None and (not self.on_battlefield(host)
                                             or self.protected_from(host, frozenset(permanent.card.colors))):
                        permanent.attached_to = None  # CR 704.5n: Equipment stays, unattached
                        host = None
                    if "Aura" in permanent.card.type_line and host is None:
                        dying.append((permanent, "unattached"))  # CR 704.5m
                        continue
                    current = self.toughness(permanent)
                    creature = current is not None
                    if (creature and current <= 0) or (permanent.loyalty is not None and permanent.loyalty <= 0):
                        dying.append((permanent, "died"))
                    elif (creature and (permanent.damage >= current or permanent.deathtouched)
                          and not self.has_keyword(permanent, "indestructible")):
                        dying.append((permanent, "destroyed"))
            if dying:  # all at once (CR 704.3)
                self._leave_together(dying)
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


def _watch_type_matches(kind: str, card: Card) -> bool:
    """Whether `card` is what a watch looks for: "creature", "land", ..., or for casts
    "spell", "creature spell", "noncreature spell", "instant or sorcery spell", "red spell",
    "historic spell", "aura, equipment, or vehicle spell", ..."""
    kind = kind.removesuffix(" spell").removesuffix("spell").strip()
    if not kind:
        return True
    if kind.startswith("non"):
        return kind[3:].capitalize() not in card.type_line
    if kind in COLOR_LETTERS:
        return COLOR_LETTERS[kind] in card.colors
    if kind == "historic":  # CR 700.6
        return any(t in card.type_line for t in ("Legendary", "Artifact", "Saga"))
    return any(t.capitalize() in card.type_line for t in re.split(r",? or |, ", kind))


def _is_searched_land(card: Card, subtypes: tuple[str, ...]) -> bool:
    """A basic land card, or (with `subtypes`) any land card with one of those land types."""
    if "Land" not in card.type_line:
        return False
    if not subtypes:
        return "Basic" in card.type_line
    return any(sub in card.type_line for sub in subtypes)


def _starting_loyalty(card: Card) -> int | None:
    return int(card.loyalty) if card.loyalty and card.loyalty.isdigit() else None


def _card_matches(kind: str, card: Card) -> bool:
    """Whether a card in a library or graveyard is of `kind`: "card", "permanent", "creature",
    "instant or sorcery", "basic land", ..."""
    if kind == "card":
        return True
    if kind == "permanent":
        return _is_permanent(card)
    if kind == "basic land":
        return "Basic" in card.type_line and "Land" in card.type_line
    return any(t.capitalize() in card.type_line for t in kind.split(" or "))


def _shown(ability_text: str, card: Card) -> str:
    """An ability's rules text as players see it: the card's name, not the CARDNAME placeholder."""
    return ability_text.replace("CARDNAME", card.name)


def _is_token(card: Card) -> bool:
    return card.type_line.startswith("Token")


def _is_permanent(card: Card) -> bool:
    return any(t in card.type_line for t in PERMANENT_TYPES)


def _effects(card: Card) -> list | None:
    """Spell effects for instants and sorceries. A permanent spell has none (it just enters the
    battlefield) except an Aura, which has to target what it will enchant."""
    if _is_permanent(card):
        kind = aura_kind(card)
        return [AttachAura(kind)] if kind else []
    return spell_effects(card)


def _spell_matches(kind: str, card: Card) -> bool:
    """Whether a spell is the kind a cost reduction names: a color letter, "spell", "noncreature",
    "instant and sorcery", or a card type."""
    if kind == "spell":
        return True
    if kind in COLOR_NAMES:
        return kind in card.colors
    if kind == "noncreature":
        return "Creature" not in card.type_line
    if kind == "instant and sorcery":
        return "Instant" in card.type_line or "Sorcery" in card.type_line
    return kind.capitalize() in card.type_line


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
