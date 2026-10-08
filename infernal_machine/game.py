"""Commander game: setup, mulligans and the turn/priority loop.

Players act only through the Player protocol, so TCP and local players are
interchangeable. Actions so far: play a land, cast a spell (including your
commander, with commander tax), and pass priority. Mana comes from lands and
from permanents with simple mana abilities. Spells use the stack; instants and
sorceries do what effects.py understands of their rules text, and permanents'
other rules text is not implemented yet.
"""

from __future__ import annotations

import dataclasses
import random
import re
from itertools import combinations, permutations
from dataclasses import dataclass, field
from typing import Any, Callable

from .analysis import is_land
from .cards import Card, Deck, has_keyword
from . import characteristics
from .characteristics import MINUS, PLUS, Modifier, source_qualities
from .combat import Combat
from .effects import (CANT_ATTACK, CANT_BLOCK, Cascade, ActivatedAbility, AlternativeCost, AttachAura, Draw, EntersTapped, Modal,
                      Amount, Condition, GraveyardCast, MassFilter, TriggeredAbility, WardCounter,
                      replacement_effects, clone_kind, aura_controls, saga_chapters, entwine_cost, escalate_cost, granted_abilities, granted_mana, line_effects, ThroneOfTheDeadThree, activated_abilities, additional_costs, alternative_costs, cost_reductions, cycling, is_multikicker, kicked_effects, kicker_costs, kicker_other_cost, attached_abilities, aura_kind, enters_tapped_rule, reconfigure_cost, reflected_mana,
                      cumulative_upkeep, echo_cost, reanimation_aura, enters_prepared, enters_with_counters, extra_votes, graveyard_casts, mana_condition, mana_per_count,
                      no_max_hand_size,
                      overloaded_effects, SacrificeSelf,
                      self_cost_reduction, is_identity_mana_land, land_mana_units, mana_life_cost, mana_life_types, mana_pain, printed_protection, protection_tokens, ward_cost, ward_fields,
                      filter_mana_ability, follows_target, mana_ability, mana_ability_sacrifices, spell_effects, static_abilities, target_kind,
                      triggered_abilities, uses_player, uses_source, uses_subject)
from .undercity import ROOMS, START
from .mana import SNOW, Cost, parse_cost, pay
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
CAST_GRAVEYARD = "Cast from graveyard: "  # flashback and escape
CAST_EXILE = "Cast from exile: "  # a card exiled "you may play it this turn"
CAST_PREPARED = "Cast prepared: "  # a copy of a prepared creature's spell
PLAY_EXILE = "Play land from exile: "
CYCLE = "Cycle: "
REVEAL_PROMPT = "Reveal a card from your hand for "  # followed by the land's name
SHOCK_PROMPT = "Pay life so it enters untapped? "  # followed by the land's name
ACTIVATE = "Activate: "  # followed by "<permanent label>: <ability text>"
COMMANDER_TAX = 2  # CR 903.8
PERMANENT_TYPES = ("Artifact", "Battle", "Creature", "Enchantment", "Land", "Planeswalker")
KEEP_PROMPT = "Keep this hand?"
BOTTOM_PROMPT = "Put a card on the bottom of your library"
DISCARD_PROMPT = "Discard down to hand size"
DISCARD_CARD_PROMPT = "Choose a card to discard"  # options are card names
CHOOSE_DISCARD_PROMPT = "Choose a card from their hand to discard"  # options are card names
TARGET_PROMPT = "Choose a target for "  # followed by the spell's name
SEARCH_PROMPT = "Choose a basic land to put onto the battlefield"
SEARCH_OPTIONAL_PROMPT = "Search your library for a basic land?"
COMMAND_ZONE_PROMPT = "Move your commander to the command zone?"  # options: "Command zone", then the zone it's going to
OPTIONAL_PROMPT = "Use this ability of "  # followed by the source's name
X_PROMPT = "Choose X for "  # followed by the spell's name; options are "0", "1", ...
CLONE_PROMPT = "Choose what to copy for "  # followed by the card's name; the last option is NOT_A_COPY
NOT_A_COPY = "Don't copy anything"
CREW_PROMPT = "Choose a creature to tap to crew "  # followed by the Vehicle's name
PROLIFERATE_PROMPT = "Proliferate: choose a permanent"
DONE = "Done"
NO_TARGET = "No target"  # the choice that leaves out an "up to one target"
SACRIFICE_PROMPT = "Choose a creature to sacrifice"
SACRIFICE_COST_PROMPT = "Choose what to sacrifice for "  # followed by the spell's name
DISCARD_COST_PROMPT = "Choose a card to discard for "  # followed by the ability's source
EXILE_COST_PROMPT = "Choose a card to exile from your graveyard for "  # followed by the ability's source
COST_PROMPT = "Choose how to cast "  # followed by the spell's name; options: "Pay {2}{U}{U}", then alternative costs
ENTWINE_PROMPT = "Pay the entwine cost for "  # followed by the spell's name; options: YES_NO
KICKER_PROMPT = "Pay the kicker cost for "  # followed by the spell's name; options: YES_NO
MULTIKICKER_PROMPT = "Choose how many times to kick "  # followed by the spell's name; options are "0", "1", ...
PITCH_PROMPT = "Choose a card to exile from your hand"
ESCAPE_PROMPT = "Choose a card to exile from your graveyard"
VOTE_PROMPT = "Vote: "  # followed by the source's name; options are the choices, or permanent labels
VENTURE_PROMPT = "Venture into the Undercity: choose the next room"  # options are room names
THRONE_PROMPT = "Throne of the Dead Three: choose a creature"  # options are card names
UNLESS_PROMPT = "Pay to stop "  # followed by the triggering card's name; options: "Pay {1}", "Don't pay"
PROTECTION_PROMPT = "Choose a color for protection: "  # followed by the source's name; options are the five colors
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
ORDER_TOP_PROMPT = "Put on top next"  # options are card names; asked while two or more cards stay on top
LOOK_PROMPT = "Take a card from the top of your library"  # options are card names, then NONE_TAKEN if optional
NONE_TAKEN = "Take none"
KEEP_ON_TOP, PUT_ON_BOTTOM, PUT_IN_GRAVEYARD = "Keep on top", "Put on the bottom", "Put into your graveyard"
MAX_X = 30  # stop looking for a bigger affordable X here
YES_NO = ["Yes", "No"]
LIFE_X_PROMPT = "Pay how much life (X) for "  # followed by the spell's name; options are the numbers
LOOT_PROMPT = "Discard a card to draw a card? "
PUT_ATTACKING_PROMPT = "Put which creature card onto the battlefield attacking? "
SHUFFLE_PROMPT = "Shuffle your library? "
CASCADE_PROMPT = "Cast for free (cascade): "  # followed by the card's name; Yes or No
DELVE_PROMPT = "Exile which card from your graveyard to pay for "  # followed by the spell's name
UPKEEP_PROMPT = "Pay the cumulative upkeep of "  # followed by the permanent's name; Yes or No (No sacrifices it)
PUT_BACK_PROMPT = "Put which card from your hand on top of your library? "
WHEEL_PROMPT = "Discard your hand and draw a new hand? "
TAP_OR_UNTAP_PROMPT = "Tap or untap "  # followed by the creature's name
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
    until_next_turn: list[Modifier] = field(default_factory=list)  # "until your next turn": ends as its controller's turn begins
    activated_turn: dict[str, int] = field(default_factory=dict)  # ability text -> turn last activated
    triggered_turn: dict[str, int] = field(default_factory=dict)  # ability text -> turn last triggered (once-a-turn ones)
    last_controller: "Seat | None" = None  # who controlled it when it left the battlefield
    last_power: int = 0  # its power just before it left (CR 608.2h: last known information)
    owner: "Seat | None" = None  # whose card it is; None means its controller (the usual case)
    attached_to: "Permanent | None" = None  # the permanent this Equipment or Aura is attached to
    linked_exile: list = field(default_factory=list)  # (owner seat, card) exiled "until this leaves the battlefield"
    kicked: int = 0  # how many times its kicker cost was paid when it was cast
    kickers: tuple[str, ...] = ()  # the mana kicker costs paid, once per payment
    regeneration: int = 0  # regeneration shields, which last until end of turn
    real_card: "Card | None" = None  # a Clone's own card, while it is a copy of something else
    control_origin: "Seat | None" = None  # who controlled it before a control-change effect took it
    control_aura: "Permanent | None" = None  # the Aura (Control Magic) that holds control of it
    control_eot: bool = False  # control changes back at end of turn (Threaten)
    original: "Card | None" = None  # a crewed Vehicle's real card, while it is an artifact creature
    reconfigured: "Card | None" = None  # an Equipment creature's real card, while it is attached (and not a creature)
    attacked_turn: int | None = None  # the last turn it attacked
    goaded_by: "Seat | None" = None  # until that player's next turn it must attack, and not them if possible
    prepared: bool = False  # a prepare creature whose controller may cast a copy of its spell
    echo_pending: bool = False  # its echo cost is due at its controller's next upkeep


@dataclass(frozen=True)
class ManaSource:
    """One mana a permanent can make when tapped, and whether making it hurts (painlands, Talismans)."""
    permanent: "Permanent | None"  # None: mana already in the pool
    types: frozenset[str]  # one mana of one of these types
    pain: frozenset[str] = frozenset()  # types that deal `damage` to the controller when produced
    damage: int = 0
    life: bool = False  # the `damage` is life paid (Mana Confluence), not damage dealt


def _snowy(permanent: "Permanent", types: frozenset[str]) -> frozenset[str]:
    """A snow permanent's mana can also pay for {S}."""
    return types | {SNOW} if "Snow" in permanent.card.type_line else types


def _pain(source: ManaSource, symbol: frozenset[str] | None) -> int:
    """Damage for tapping `source` for mana paying `symbol` (None: generic, so any type will do)."""
    options = source.types if symbol is None else source.types & symbol
    return source.damage if source.pain and all(t in source.pain for t in options) else 0


class Payment(list):
    """The permanents to tap for a cost; `pain` is the damage their mana deals to the payer, `life` the life it costs,
    `pool` the mana types it uses up from the payer's mana pool."""
    pain: int = 0
    life: int = 0
    pool: tuple[frozenset[str], ...] = ()


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
    kicked: int = 0  # how many times the kicker cost was paid
    kickers: tuple[str, ...] = ()  # the mana kicker costs paid, once per payment
    carried: Any = None  # what an earlier effect chose, for a later one (a fight's first target)
    exile_after: bool = False  # cast with flashback: exiled, not put in the graveyard, when it leaves the stack
    is_copy: bool = False  # a copy of a spell: not a card, so it vanishes instead of going to the graveyard
    evoked: bool = False  # cast for its evoke cost: it is sacrificed when it enters
    subject: "Permanent | None" = None  # for a watching trigger: the permanent that set it off ("on it")
    player: "Seat | None" = None  # for a watching trigger: the player whose action set it off ("that player")
    warding: "StackItem | None" = None  # for a ward trigger: the spell or ability it will counter unless paid for


GERM = Card(name="Phyrexian Germ", type_line="Token Creature — Phyrexian Germ", colors=("B",), power="0", toughness="0")
EVOKE_SACRIFICE = TriggeredAbility("enters", (SacrificeSelf(),), False,
                                   "When this permanent enters, if its evoke cost was paid, sacrifice it.")


@dataclass(eq=False)
class PendingTrigger:
    ability: TriggeredAbility
    permanent: "Permanent"
    controller: "Seat"
    x: int = 0  # for "Whenever you cast a spell with {X}, put X counters ...": that spell's X
    subject: "Permanent | None" = None  # what a watching trigger saw happen
    player: "Seat | None" = None  # who did it
    card: Card | None = None  # for a dungeon room's ability, which has no permanent behind it

    @property
    def source(self) -> Card:
        return self.card or self.permanent.card


@dataclass(eq=False)
class Seat:
    player: Player
    index: int
    life: int = STARTING_LIFE
    library: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    exile_play: list[tuple[Card, int]] = field(default_factory=list)  # exiled cards its owner may play, and the last turn they can
    undercity_room: str | None = None  # where this player's venture marker is, if they are in the Undercity
    mana_pool: list[frozenset[str]] = field(default_factory=list)  # mana added by rituals, gone at the end of the step
    graveyard: list[Card] = field(default_factory=list)
    exile: list[Card] = field(default_factory=list)
    command_zone: list[Card] = field(default_factory=list)
    commander_names: set[str] = field(default_factory=set)
    color_identity: frozenset[str] = frozenset()
    commander_casts: dict[str, int] = field(default_factory=dict)
    commander_damage: dict[tuple[int, str], int] = field(default_factory=dict)  # (seat, commander) -> damage
    lands_played: int = 0
    draw_turn: int | None = None  # the last turn this player drew a card (not counting the opening hand)
    draw_count: int = 0  # how many they drew on draw_turn
    life_lost_turn: int | None = None  # the last turn this player lost life
    life_gained_turn: int | None = None
    life_gained_amount: int = 0  # how much life this player gained on life_gained_turn
    delayed_mana: int = 0  # {C} to add at the beginning of this player's next main phase (Mana Drain)
    graveyard_left_turn: int | None = None  # the last turn a card left this player's graveyard
    cast_log: list[tuple[int, Card]] = field(default_factory=list)  # (turn, spell) for every spell cast
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
        self.extra_turns: list[int] = []  # seats that take an extra turn next; the last one asked for goes first
        self._plan: list[str] = list(STEPS)  # the steps of the current turn, extended by extra combat phases
        self._plan_index = 0
        self.regular = 0  # the seat whose regular turn it is (or was, during an extra turn)
        self.monarch: Seat | None = None
        self.initiative: Seat | None = None
        self.deaths_turn, self.deaths_count = 0, 0  # how many creatures have died this turn, for "two or more creatures died this turn"
        self.at_end_step: list[tuple[int, Callable[[], None]]] = []  # (turn, what) to do as that turn's next end step begins
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
        self.regular = self.active
        while self.winner() is None and self.turn < max_turns:
            self.turn += 1
            self._take_turn(self.seats[self.active])
            self.active = self._next_turn_seat()
        winner = self.winner()
        self.broadcast({"event": "game_over", "winner": winner.index if winner else None, "turn": self.turn})
        return winner

    def _next_turn_seat(self) -> int:
        """Whose turn comes next: an extra turn if one was asked for (CR 500.7), else the next regular turn."""
        while self.extra_turns:
            index = self.extra_turns.pop()
            if not self.seats[index].lost:
                return index
        self.regular = self._next_live_seat(self.regular)
        return self.regular

    def _take_turn(self, seat: Seat) -> None:
        seat.lands_played = 0
        self.broadcast({"event": "turn", "turn": self.turn, "seat": seat.index})
        over = lambda: self.winner() is not None or seat.lost
        self._plan, index = list(STEPS), 0
        while index < len(self._plan):
            step = self._plan[index]
            self._plan_index = index
            index += 1
            if step in ("declare_blockers", "combat_damage") and not self.combat.attacks:
                continue  # CR 508.8: no attackers, no blockers or damage steps
            if step == "combat_damage" and self.combat.has_first_strike():
                self.step = "first_strike_damage"  # CR 510.4
                self.combat.deal_damage(first_strike_step=True)
                self._check_state()
                if over():
                    return
                self._priority_round(seat)
                self._empty_pools()
                if over():
                    return
            self.step = step
            self._turn_based_actions(seat)
            if over():
                return
            if step not in NO_PRIORITY_STEPS:
                self._priority_round(seat)
            self._empty_pools()

    def _turn_based_actions(self, seat: Seat) -> None:
        if self.step == "untap":
            self.combat = Combat(self)
            for permanent in seat.battlefield:
                permanent.tapped = False
                permanent.sick = False
                permanent.until_next_turn = []
            for other in self.live_seats():  # goad lasts until the goader's next turn
                for permanent in other.battlefield:
                    if permanent.goaded_by is seat:
                        permanent.goaded_by = None
        elif self.step == "draw":
            # CR 103.8: only a two-player game skips the first player's first draw.
            if not (self.turn == 1 and not self.multiplayer):
                self.draw(seat, 1)
        elif self.step in ("upkeep", "end"):
            if self.step == "end":  # "at the beginning of the next end step"
                due = [what for turn, what in self.at_end_step if turn <= self.turn]
                self.at_end_step = [(turn, what) for turn, what in self.at_end_step if turn > self.turn]
                for what in due:
                    what()
            if self.step == "upkeep":
                self._pay_upkeep_costs(seat)
            for permanent in list(seat.battlefield):
                self.trigger("upkeep" if self.step == "upkeep" else "end_step", permanent, seat)
            for other in self.live_seats():  # "At the beginning of each upkeep / end step"
                for permanent in list(other.battlefield):
                    self.trigger("each_upkeep" if self.step == "upkeep" else "each_end_step", permanent, other)
            if self.step == "upkeep" and self.initiative is seat:  # CR 725.2: the initiative ventures at upkeep
                self.venture(seat)
            if self.step == "end" and self.monarch is seat:  # CR 724.2: the monarch draws at their end step
                self.broadcast({"event": "monarch_draw", "seat": seat.index})
                self.draw(seat, 1)
        elif self.step == "main1":  # after the draw step, each Saga gets a lore counter and its chapter triggers
            for permanent in list(seat.battlefield):
                if saga_chapters(permanent.card):
                    permanent.counters["lore"] = permanent.counters.get("lore", 0) + 1
                    self.broadcast({"event": "counters", "card": permanent.card.name, "counter": "lore",
                                    "added": 1, "total": permanent.counters["lore"]})
                    self.trigger(f"chapter_{permanent.counters['lore']}", permanent, seat)
            self._add_delayed_mana(seat)
            for permanent in list(seat.battlefield):
                self.trigger("first_main", permanent, seat)
        elif self.step == "beginning_of_combat":
            self.combat = Combat(self)
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
            self._add_delayed_mana(seat)
            for permanent in list(seat.battlefield):
                self.trigger("second_main", permanent, seat)
        elif self.step == "cleanup":
            excess = 0 if any(no_max_hand_size(p.card) for p in seat.battlefield) else len(seat.hand) - HAND_SIZE
            for _ in range(max(0, excess)):
                i = seat.player.choose(DISCARD_PROMPT, [c.name for c in seat.hand])
                card = seat.hand.pop(i)
                self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
                self._move_card(seat, card, "graveyard")
            for other in self.seats:  # CR 514.2
                for permanent in other.battlefield:
                    permanent.damage = 0
                    permanent.deathtouched = False
                    permanent.until_end_of_turn = []  # CR 514.2
                    permanent.regeneration = 0
                    if permanent.original is not None:  # a Vehicle's crew lasts until end of turn
                        permanent.card, permanent.original = permanent.original, None
            for permanent in [p for s in self.live_seats() for p in s.battlefield]:  # control "until end of turn" ends
                if permanent.control_eot:
                    self._return_control(permanent)
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
            actions += [PLAY_LAND + c.back.name for c in _unique(seat.hand) if c.back]  # a Pathway's other face
        for card in _unique(seat.hand):
            if not is_land(card) and (sorcery_timing or _instant_speed(card)) and self._can_cast(seat, card):
                actions.append(CAST + card.name)
        for card in seat.command_zone:
            if (sorcery_timing or _instant_speed(card)) and self._can_cast(seat, card, from_command_zone=True):
                actions.append(CAST_COMMANDER + card.name)
        for card in _unique(seat.graveyard):
            for cast in graveyard_casts(card)[:1]:
                if not is_land(card) and (sorcery_timing or _instant_speed(card)) and self._can_cast(seat, card, graveyard=cast):
                    actions.append(CAST_GRAVEYARD + card.name)
        for card in _unique([c for c, until in seat.exile_play if self.turn <= until and c in seat.exile]):
            if is_land(card):
                if sorcery_timing and seat.lands_played < 1:
                    actions.append(PLAY_EXILE + card.name)
            elif (sorcery_timing or _instant_speed(card)) and self._can_cast(seat, card):
                actions.append(CAST_EXILE + card.name)
        for spell in _unique([p.card.prepare for p in seat.battlefield if p.prepared and p.card.prepare]):
            if (sorcery_timing or _instant_speed(spell)) and self._can_cast(seat, spell):
                actions.append(CAST_PREPARED + spell.name)
        for card in _unique(seat.hand):
            if (found := cycling(card)) and self._can_cycle(seat, found[1], found[3]):
                actions.append(CYCLE + card.name)
        actions += list(self._activations(seat, sorcery_timing))
        return actions

    def _activations(self, seat: Seat, sorcery_timing: bool) -> dict[str, tuple[Permanent, ActivatedAbility]]:
        """Activated abilities `seat` can activate now, keyed by their action text."""
        options = {}
        for permanent in seat.battlefield:
            granted = [a for other in self.seats for attachment in other.battlefield if attachment.attached_to is permanent
                       for a in granted_abilities(attachment.card)]
            for ability in [*activated_abilities(permanent.card), *granted]:
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
        if len(seat.hand) < ability.discard or len(seat.graveyard) < ability.exile_graveyard:
            return False
        if ability.sacrifice_other and len(self._sacrifice_choices(seat, permanent, ability)) < ability.sacrifice_count:
            return False
        if ability.remove_counter and not permanent.counters.get(ability.remove_counter, 0):
            return False
        if ability.condition and not self.condition_holds(ability.condition, seat, permanent):
            return False
        if ability.reconfigure == "unattach" and permanent.attached_to is None:
            return False
        if ability.reconfigure == "attach" and not any(p is not permanent and "Creature" in p.card.type_line
                                                       for p in seat.battlefield):
            return False
        if ability.crew and (permanent.original is not None
                             or any(i.source is permanent and getattr(i.ability, "crew", 0) for i in self.stack)  # already crewing
                             or sum(self.power(p) for p in self._crew_candidates(seat, permanent)) < ability.crew):
            return False
        if self._ability_payment(seat, permanent, ability) is None:
            return False
        return self._effects_possible(seat, ability.effects, source_qualities(card))

    def _sacrifice_choices(self, seat: Seat, source: Permanent, ability: ActivatedAbility) -> list[Permanent]:
        """What `seat` could sacrifice to pay the ability's "Sacrifice a creature" cost."""
        return [p for p in seat.battlefield if _permanent_matches(ability.sacrifice_other, p.card)
                and not (ability.sacrifice_another and p is source)]

    def _crew_candidates(self, seat: Seat, vehicle: Permanent) -> list[Permanent]:
        """The untapped creatures that could crew `vehicle` (summoning sickness doesn't matter, CR 702.122)."""
        return [p for p in seat.battlefield if p is not vehicle and not p.tapped and "Creature" in p.card.type_line]

    def become_creature(self, vehicle: Permanent) -> None:
        """A crewed Vehicle is an artifact creature until end of turn."""
        if vehicle.original is None:
            vehicle.original = vehicle.card
            vehicle.card = dataclasses.replace(vehicle.card, type_line=vehicle.card.type_line.replace("Artifact", "Artifact Creature", 1))
            self.broadcast({"event": "became_creature", "card": vehicle.card.name})

    def animate(self, permanent: Permanent, power: int, toughness: int, colors: tuple[str, ...], subtypes: str,
                artifact: bool, keywords: frozenset[str]) -> None:
        """"Until end of turn, this land becomes a 3/3 green Ape creature with trample. It's still a land.": it keeps
        its other types and gains Creature (and Artifact); the card comes back at end of turn (like a crewed Vehicle)."""
        base = permanent.original or permanent.card
        permanent.original = base
        types = base.type_line.partition("\u2014")[0].split()
        for added in (["Artifact"] if artifact and "Artifact" not in types else []) + ["Creature"]:
            if added not in types:
                types.append(added)
        type_line = " ".join(types) + (f" \u2014 {subtypes}" if subtypes else "")
        permanent.card = dataclasses.replace(base, type_line=type_line, power=str(power), toughness=str(toughness),
                                             colors=colors or base.colors)
        if keywords:
            permanent.until_end_of_turn.append(Modifier(0, 0, keywords))
        self.broadcast({"event": "became_creature", "card": permanent.card.name, "power": power, "toughness": toughness})

    def move_counters(self, source: Permanent, destination: Permanent, counter: str, count: int | None) -> None:
        """Move up to `count` counters (all of them if None) from one permanent to another. They are moved, not put
        on it, so nothing that doubles counters applies."""
        moved = min(source.counters.get(counter, 0), source.counters.get(counter, 0) if count is None else count)
        if not moved:
            return
        self.remove_counters(source, counter, moved)
        destination.counters[counter] = destination.counters.get(counter, 0) + moved
        self.broadcast({"event": "counters", "card": destination.card.name, "counter": counter,
                        "added": moved, "total": destination.counters[counter]})

    def _pay_card_costs(self, seat: Seat, source: Permanent, ability: ActivatedAbility) -> None:
        """Pay an activated ability's "Sacrifice a creature", "Discard a card" and "Exile a card from your
        graveyard" costs (CR 602.2b)."""
        name = source.card.name
        if ability.crew:  # tap creatures until their power adds up to the crew number
            crewed = 0
            while crewed < ability.crew:
                options = self._crew_candidates(seat, source)
                member = options[seat.player.choose(CREW_PROMPT + name, [self.label(p) for p in options])]
                member.tapped = True
                crewed += self.power(member)
        for _ in range(ability.discard):
            card = seat.hand[seat.player.choose(DISCARD_COST_PROMPT + name, [c.name for c in seat.hand])]
            seat.hand.remove(card)
            self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
            self._move_card(seat, card, "graveyard")
        for _ in range(ability.exile_graveyard):
            card = seat.graveyard[seat.player.choose(EXILE_COST_PROMPT + name, [c.name for c in seat.graveyard])]
            seat.graveyard.remove(card)
            self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": "exile"})
            self._move_card(seat, card, "exile")
        if ability.exile_graveyard:
            self._left_graveyard(seat)
        if ability.remove_counter:
            self.remove_counters(source, ability.remove_counter, 1)
        chosen = []
        for _ in range(ability.sacrifice_count if ability.sacrifice_other else 0):
            options = [p for p in self._sacrifice_choices(seat, source, ability) if p not in chosen]
            chosen.append(options[seat.player.choose(SACRIFICE_COST_PROMPT + name, [self.label(p) for p in options])])
        if chosen:
            self._leave_together([(p, "sacrificed") for p in chosen])

    def _ability_payment(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility,
                         x: int = 0) -> list[Permanent] | None:
        cost = (parse_cost(ability.mana_cost) if ability.mana_cost else Cost()).with_x(x)
        # A permanent can't tap for mana to pay for its own {T} or sacrifice ability.
        return self._pay_cost(seat, cost, exclude=permanent if ability.tap or ability.sacrifice else None)

    def commander_tax(self, seat: Seat, card: Card) -> int:
        return COMMANDER_TAX * seat.commander_casts.get(card.name, 0)

    def _can_cast(self, seat: Seat, card: Card, from_command_zone: bool = False,
                  graveyard: GraveyardCast | None = None) -> bool:
        if not self._cast_ways(seat, card, from_command_zone, graveyard):
            return False
        effects, colors = kicked_effects(_effects(card), 0) or [], source_qualities(card)
        return self._effects_possible(seat, effects, colors)

    def _spend_mana(self, seat: Seat, sources: list[Permanent]) -> None:
        """Tap the chosen mana sources; ones whose mana ability sacrifices them (Treasure) are sacrificed,
        and painlands and Talismans that made painful mana damage the payer."""
        for source in sources:
            source.tapped = True
            if not is_land(source.card) and mana_ability_sacrifices(source.card):
                self._leave_battlefield(source, "sacrificed")
        if pain := getattr(sources, "pain", 0):
            self.damage(seat, pain)
        if life := getattr(sources, "life", 0):
            self.change_life(seat, -life)
        for unit in getattr(sources, "pool", ()):
            seat.mana_pool.remove(unit)

    def add_mana(self, seat: Seat, units: tuple[frozenset[str], ...]) -> None:
        """Mana from a spell or ability goes to the pool, to be spent before the step ends."""
        seat.mana_pool.extend(units)
        self.broadcast({"event": "mana_added", "seat": seat.index, "mana": ["".join(sorted(u)) for u in units]})

    def _empty_pools(self) -> None:
        for seat in self.seats:
            seat.mana_pool.clear()

    def _mana_sources(self, seat: Seat, exclude: Permanent | None = None) -> list[ManaSource]:
        """One entry per mana each untapped permanent can make: nonland sources first,
        then lands, and sources that sacrifice themselves (Treasure) last."""
        abilities, lands, sacrifices = [], [], []
        pooled = [ManaSource(None, unit) for unit in seat.mana_pool]
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude:
                continue
            card = permanent.card
            pain, damage = mana_pain(card) or (frozenset(), 0)
            if (condition := mana_condition(card)) and not self.condition_holds(condition, seat, permanent):
                continue  # "Activate only if you control five or more lands."
            if (per := mana_per_count(card)) is not None:  # Gaea's Cradle: as much as you control
                if not per[0] and not (permanent.sick and "Creature" in card.type_line):
                    lands.extend(ManaSource(permanent, frozenset(per[1]))
                                 for _ in range(sum(_has_type(p.card, per[2]) for p in seat.battlefield)))
                continue
            if is_land(card):
                if life_cost := mana_life_cost(card):
                    if seat.life > life_cost:  # Mana Confluence: paying life, never down to 0
                        lands.append(ManaSource(permanent, mana_life_types(card), frozenset("WUBRGC"), life_cost, life=True))
                    continue
                gifted = [mana for other in self.seats for a in other.battlefield if a.attached_to is permanent
                          for mana in granted_mana(a.card)]  # "Enchanted land has "{T}: Add {G}{G}."": the better of the two
                if units := land_mana_units(card):  # a bounceland or Ancient Tomb makes several mana in one tap
                    lands.extend(ManaSource(permanent, mana, pain, damage) for mana in units)
                    continue
                if len(gifted) > 1:  # more mana than the land's own single one
                    lands.extend(ManaSource(permanent, mana, pain, damage) for mana in gifted)
                    continue
                # Command Tower makes only the colors of your commander, whatever the card data lists.
                types = seat.color_identity if is_identity_mana_land(card) else frozenset(card.produced_mana)
                if reflect := reflected_mana(card):
                    types = self._reflected_types(seat, *reflect)
                    if not types:
                        continue
                lands.append(ManaSource(permanent, _snowy(permanent, types), pain, damage))
            elif not (permanent.sick and "Creature" in card.type_line):
                bucket = sacrifices if mana_ability_sacrifices(card) else abilities
                for mana in mana_ability(card, seat.color_identity) or []:
                    bucket.append(ManaSource(permanent, _snowy(permanent, mana), pain, damage))
        return pooled + abilities + lands + sacrifices

    def _reflected_types(self, seat: Seat, opponents: bool, colorless: bool) -> frozenset[str]:
        """What Exotic Orchard / Reflecting Pool can make: the mana types the lands of the opponents (or your other
        lands) could produce. Lands that copy this kind of ability add nothing, so there is no loop."""
        owners = [s for s in self.live_seats() if (s is not seat) == opponents] if opponents else [seat]
        types: set[str] = set()
        for owner in owners:
            for land in owner.battlefield:
                if is_land(land.card) and not reflected_mana(land.card):
                    types |= set(land.card.produced_mana)
        return frozenset(types if colorless else types - {"C"})

    def _payment(self, seat: Seat, card: Card, from_command_zone: bool = False, x: int = 0,
                 alternative: AlternativeCost | None = None, kickers: tuple[str, ...] = (), extra: str = "",
                 delve: int = 0) -> list[Permanent] | None:
        """The permanents to tap for `card` with X = `x`, or None if it can't be paid for now. An alternative
        cost replaces the mana cost; commander tax and kicker are added, then cost reductions apply."""
        if alternative:
            cost = parse_cost(alternative.mana_cost) if alternative.mana_cost else Cost()  # Evoke and Overload cost mana
        else:
            cost = parse_cost(card.mana_cost)
        if cost is None:
            return None
        if from_command_zone:
            cost = cost.plus_generic(self.commander_tax(seat, card))
        for kicker in kickers:
            cost = cost + parse_cost(kicker)
        if extra:  # entwine, or escalate for each mode beyond the first
            cost = cost + parse_cost(extra)
        return self._pay_cost(seat, cost.with_x(x).reduced(self.cost_reduction(seat, card) + delve))

    def cost_reduction(self, seat: Seat, card: Card) -> int:
        """How much less generic mana `card` costs `seat` (Medallions and the like)."""
        reduction = sum(amount for p in seat.battlefield for kind, amount in cost_reductions(p.card)
                        if _spell_matches(kind, card))
        if own := self_cost_reduction(card):  # "This spell costs {1} less to cast for each creature on the battlefield."
            amount, what = own
            counted = (sum(_has_type(p.card, "creature") for s in self.live_seats() for p in s.battlefield)
                       if what == "creature" else sum(_card_matches(what, c) for c in seat.graveyard))
            reduction += amount * counted
        return reduction

    def _cast_ways(self, seat: Seat, card: Card, from_command_zone: bool,
                   graveyard: GraveyardCast | None = None) -> list[AlternativeCost | None]:
        """The ways `seat` can cast `card` now: None for its mana cost, then its alternative costs. Casting from
        the graveyard has one way: its flashback or escape cost (and enough other cards to exile)."""
        if graveyard:
            paying = dataclasses.replace(card, mana_cost=graveyard.cost)
            others = len(seat.graveyard) - (card in seat.graveyard)
            return [None] if others >= graveyard.exile and self._payment(seat, paying) is not None else []
        return [way for way in [None, *alternative_costs(card)]
                if self._can_pay_extras(seat, card, way)
                and self._payment(seat, card, from_command_zone, alternative=way,
                                  delve=self._delve_max(seat, card) if way is None else 0) is not None]

    def _extra_costs(self, card: Card, kicked: int) -> list:
        """The non-mana costs of casting `card`: its additional costs, plus a non-mana kicker cost if kicked."""
        kicker = kicker_other_cost(card) if kicked else None
        return additional_costs(card) + ([kicker] if kicker else [])

    def _can_pay_extras(self, seat: Seat, card: Card, alternative: AlternativeCost | None, kicked: int = 0) -> bool:
        """Whether `seat` can pay the parts of casting `card` that aren't mana: additional costs, a non-mana
        kicker cost, and `alternative`'s condition, life and card to exile."""
        extras = self._extra_costs(card, kicked)
        others = list(seat.hand)
        if card in others:
            others.remove(card)
        if sum(c.life for c in extras) + (alternative.life if alternative else 0) > seat.life:  # CR 119.4
            return False
        if sum(c.discard for c in extras) > len(others):
            return False
        for kind in {c.sacrifice for c in extras if c.sacrifice}:
            needed = sum(c.sacrifice == kind for c in extras)
            if sum(_permanent_matches(kind, p.card) for p in seat.battlefield) < needed:
                return False
        if alternative is None:
            return True
        if alternative.commander and not any(p.card.name in (p.owner or seat).commander_names for p in seat.battlefield):
            return False
        if alternative.not_your_turn and self.active == seat.index:
            return False
        return not alternative.exile_color or any(alternative.exile_color in c.colors for c in others)

    def _pay_extras(self, seat: Seat, card: Card, alternative: AlternativeCost | None,
                    graveyard: GraveyardCast | None = None, x: int = 0, kicked: int = 0) -> None:
        """Pay the non-mana costs of casting `card`, which has already left its zone."""
        for _ in range(graveyard.exile if graveyard else 0):  # Escape: exile other cards from the graveyard
            exiled = seat.graveyard[seat.player.choose(ESCAPE_PROMPT, [c.name for c in seat.graveyard])]
            seat.graveyard.remove(exiled)
            self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": exiled.name, "to": "exile"})
            self._move_card(seat, exiled, "exile")
        if graveyard and graveyard.exile:
            self._left_graveyard(seat)
        if alternative and alternative.exile_color:
            options = [c for c in seat.hand if alternative.exile_color in c.colors]
            exiled = options[seat.player.choose(PITCH_PROMPT, [c.name for c in options])]
            seat.hand.remove(exiled)
            self.broadcast({"event": "exiled_from_hand", "seat": seat.index, "card": exiled.name})
            self._move_card(seat, exiled, "exile")
        extras = self._extra_costs(card, kicked)
        for extra in extras:
            if extra.discard:
                discarded = seat.hand[seat.player.choose(DISCARD_PROMPT, [c.name for c in seat.hand])]
                seat.hand.remove(discarded)
                self.broadcast({"event": "discard", "seat": seat.index, "card": discarded.name})
                self._move_card(seat, discarded, "graveyard")
            if extra.sacrifice:
                options = [p for p in seat.battlefield if _permanent_matches(extra.sacrifice, p.card)]
                choice = options[seat.player.choose(SACRIFICE_COST_PROMPT + card.name, [self.label(p) for p in options])]
                self._leave_together([(choice, "sacrificed")])
        life = (sum(c.life for c in extras) + (alternative.life if alternative else 0)
                + (x if any(c.life_x for c in additional_costs(card)) else 0))
        if life:
            self.change_life(seat, -life)

    def _max_x(self, seat: Seat, card: Card, from_command_zone: bool, kickers: tuple[str, ...], extra: str = "") -> int:
        x = 0
        while x < MAX_X and self._payment(seat, card, from_command_zone, x + 1, kickers=kickers, extra=extra) is not None:
            x += 1
        return x

    def _pay_cost(self, seat: Seat, cost: Cost, exclude: Permanent | None = None) -> list[Permanent] | None:
        """The permanents to tap for `cost`, or None if it can't be paid. A Phyrexian symbol is paid with mana
        when that works, otherwise with 2 life (never down to 0 life)."""
        for by_life in range(len(cost.phyrexian) + 1):
            rest = dataclasses.replace(cost, phyrexian=cost.phyrexian[by_life:])
            payment = self._pay_mana(seat, rest, exclude)
            if payment is not None and not by_life:
                return payment
            if payment is not None and seat.life > payment.life + 2 * by_life:
                payment.life += 2 * by_life
                return payment
        return None

    def _pay_mana(self, seat: Seat, cost: Cost, exclude: Permanent | None = None) -> list[Permanent] | None:
        """The permanents to tap for a cost of mana only, or None if it can't be paid.

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
        """Pay `cost` using the filters in `combo`, in any order: each filter's own cost is paid from plain sources or
        the mana earlier filters made (so Signets can feed each other, but none feeds itself)."""
        for ordered in permutations(combo):
            if (payment := self._pay_in_order(cost, sources, ordered)) is not None:
                return payment
        return None

    def _pay_in_order(self, cost: Cost, sources: list[ManaSource], ordered) -> Payment | None:
        pool = list(sources)
        used: list[tuple[ManaSource, frozenset[str] | None]] = []
        for permanent, activation, units in ordered:
            # Its own cost is paid by other permanents: a filter can't tap for mana to pay for its own ability.
            available = [i for i, s in enumerate(pool) if s.permanent is not permanent]
            paid_here: dict[int, frozenset[str]] = {}
            chosen_here = pay(activation, [pool[i].types for i in available], paid_here)
            if chosen_here is None:
                return None
            chosen = [available[j] for j in chosen_here]
            paid = {available[j]: symbol for j, symbol in paid_here.items()}
            used += [(pool[i], paid.get(i)) for i in chosen]
            pool = [s for i, s in enumerate(pool) if i not in chosen] + [ManaSource(permanent, mana) for mana in units]
        paid = {}
        chosen = pay(cost, [s.types for s in pool], paid)
        if chosen is None:
            return None
        used += [(pool[i], paid.get(i)) for i in chosen]
        # A permanent that makes several mana (Sol Ring) is tapped once. Mana already in the pool has no permanent.
        permanents = [s.permanent for s, _ in used if s.permanent is not None] + [p for p, _, _ in ordered]
        payment = Payment({id(p): p for p in permanents}.values())
        payment.pool = tuple(s.types for s, _ in used if s.permanent is None)
        # A permanent hurts (or costs life) once per tap, however many of its mana are used.
        hurt: dict[int, int] = {}
        paid_life: dict[int, int] = {}
        for source, symbol in used:
            into = paid_life if source.life else hurt
            into[id(source.permanent)] = max(into.get(id(source.permanent), 0), _pain(source, symbol))
        payment.pain, payment.life = sum(hurt.values()), sum(paid_life.values())
        return payment

    def _filter_sources(self, seat: Seat, exclude: Permanent | None) -> list[tuple[Permanent, Cost, list]]:
        found = []
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude or (permanent.sick and "Creature" in permanent.card.type_line):
                continue
            ability = filter_mana_ability(permanent.card)
            if ability:
                found.append((permanent, parse_cost(ability[0]), ability[1]))
            elif (per := mana_per_count(permanent.card)) is not None and per[0]:  # Cabal Coffers
                units = [frozenset(per[1])] * sum(_has_type(p.card, per[2]) for p in seat.battlefield)
                if units:
                    found.append((permanent, parse_cost(per[0]), units))
        return found

    def _perform(self, seat: Seat, action: str) -> None:
        if action.startswith(PLAY_LAND):
            name = action.removeprefix(PLAY_LAND)
            card = _take_face(seat.hand, name)
            self._enter(seat, Permanent(card, sick=True))  # a land that becomes a creature can't attack the turn it came in
            seat.lands_played += 1
            self.broadcast({"event": "play_land", "seat": seat.index, "card": card.name})
        elif action.startswith(PLAY_EXILE):
            card = _take(seat.exile, action.removeprefix(PLAY_EXILE))
            self._used_exile_permission(seat, card)
            self._enter(seat, Permanent(card, sick=True))
            seat.lands_played += 1
            self.broadcast({"event": "play_land", "seat": seat.index, "card": card.name, "from": "exile"})
        elif action.startswith(CAST_EXILE):
            card = next(c for c in seat.exile if c.name == action.removeprefix(CAST_EXILE))
            self._used_exile_permission(seat, card)
            self._cast(seat, card, seat.exile)
        elif action.startswith(CYCLE):
            self._cycle(seat, _take(seat.hand, action.removeprefix(CYCLE)))
        elif action.startswith(CAST_COMMANDER):
            name = action.removeprefix(CAST_COMMANDER)
            card = next(c for c in seat.command_zone if c.name == name)
            self._cast(seat, card, seat.command_zone, from_command_zone=True)
            seat.commander_casts[name] = seat.commander_casts.get(name, 0) + 1
        elif action.startswith(CAST_GRAVEYARD):
            card = next(c for c in seat.graveyard if c.name == action.removeprefix(CAST_GRAVEYARD))
            self._cast(seat, card, seat.graveyard, graveyard=graveyard_casts(card)[0])
        elif action.startswith(CAST_PREPARED):
            name = action.removeprefix(CAST_PREPARED)
            permanent = next(p for p in seat.battlefield if p.prepared and p.card.prepare and p.card.prepare.name == name)
            self._cast(seat, permanent.card.prepare, [permanent.card.prepare], prepared=permanent)
        elif action.startswith(CAST):
            card = next(c for c in seat.hand if c.name == action.removeprefix(CAST))
            self._cast(seat, card, seat.hand)
        elif action.startswith(ACTIVATE):
            sorcery_timing = seat.index == self.active and self.step in ("main1", "main2") and not self.stack
            permanent, ability = self._activations(seat, sorcery_timing)[action]
            self._activate(seat, permanent, ability)

    def _used_exile_permission(self, seat: Seat, card: Card) -> None:
        seat.exile_play = [(c, until) for c, until in seat.exile_play if c != card] + \
                          [(c, until) for c, until in seat.exile_play if c == card][1:]

    def exile_top(self, seat: Seat, count: int, play: str | None) -> None:
        """Exile the top `count` cards of the library; `play` is None, "this turn" or "next turn" (until the end of
        their controller's next turn): the cards may then be played from exile until that turn ends."""
        seats = len(self.seats)
        until = (None if play is None else self.turn if play == "this turn"
                 else self.turn + ((seat.index - self.active) % seats or seats))  # the end of their next turn
        exiled = [seat.library.pop(0) for _ in range(min(count, len(seat.library)))]
        self.broadcast({"event": "exiled_from_library", "seat": seat.index, "cards": [c.name for c in exiled],
                        "may_play": play is not None})
        for card in exiled:
            self._move_card(seat, card, "exile")
            if until is not None and card in seat.exile:
                seat.exile_play.append((card, until))

    def _can_cycle(self, seat: Seat, cost: str, life: int) -> bool:
        """Cycling costs mana, or life you can spare (never down to 0)."""
        return life < seat.life if life else self._pay_cost(seat, parse_cost(cost)) is not None

    def _cycle(self, seat: Seat, card: Card) -> None:
        """Cycling: pay the cost, discard the card, and draw a card when the ability resolves."""
        word, cost, effects, life = cycling(card)
        tapped = self._pay_cost(seat, parse_cost(cost)) if cost else []
        self._spend_mana(seat, tapped)
        if life:
            self.change_life(seat, -life)
        ability = ActivatedAbility(f"{word} {cost}" if cost else f"{word}\u2014Pay {life} life.", effects, mana_cost=cost, life=life)
        self.broadcast({"event": "discard", "seat": seat.index, "card": card.name, "reason": "cycling"})
        self._move_card(seat, card, "graveyard")
        self.stack.append(StackItem(card, seat, list(effects), [], ability))
        self.broadcast({"event": "activate", "seat": seat.index, "card": card.name, "ability": _shown(ability.text, card),
                        "targets": [], "tapped": [p.card.name for p in tapped]})

    def _activate(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility) -> None:
        effects = list(ability.effects)
        if effects and isinstance(effects[0], Modal):
            effects, _ = self._choose_modes(seat, permanent.card, effects[0])
        targets, labels = self._choose_targets(seat, effects, permanent.card.name, permanent,
                                               source_qualities(permanent.card))
        x = 0
        if ability.mana_cost and parse_cost(ability.mana_cost).x:  # "{X}, {T}: ...": X is chosen, then paid
            most = 0
            while most < MAX_X and self._ability_payment(seat, permanent, ability, most + 1) is not None:
                most += 1
            x = seat.player.choose(X_PROMPT + permanent.card.name, [str(n) for n in range(most + 1)])
        tapped = self._ability_payment(seat, permanent, ability, x)
        self._spend_mana(seat, tapped)
        if ability.tap:
            permanent.tapped = True
        if ability.life:
            self.change_life(seat, -ability.life)
        self._pay_card_costs(seat, permanent, ability)
        if ability.loyalty is not None:
            permanent.loyalty = (permanent.loyalty or 0) + ability.loyalty
            permanent.loyalty_turn = self.turn
        permanent.activated_turn[ability.text] = self.turn
        item = StackItem(permanent.card, seat, effects, targets, ability, permanent, x=x)
        self.stack.append(item)
        self.broadcast({"event": "activate", "seat": seat.index, "card": permanent.card.name,
                        "ability": _shown(ability.text, permanent.card), "targets": labels,
                        "tapped": [p.card.name for p in tapped]})
        self._check_ward(item)
        if ability.sacrifice:
            self._leave_battlefield(permanent, "sacrificed")

    def _effects_possible(self, seat: Seat, effects, colors: frozenset[str] = frozenset()) -> bool:
        """Whether the targets exist: for a modal spell or ability, for enough of its modes."""
        if effects and isinstance(effects[0], Modal):
            return sum(self._targets_exist(seat, modes, colors) for modes in effects[0].modes) >= effects[0].min
        return self._targets_exist(seat, effects, colors)

    def _targets_exist(self, seat: Seat, effects, colors: frozenset[str] = frozenset()) -> bool:
        """Whether every targeting effect (but "up to one target") has a legal target; a `distinct` one needs one
        besides the targets chosen for earlier effects of the same kind."""
        kinds = [(kind, getattr(e, "distinct", False)) for e in effects
                 if (kind := target_kind(e)) and not getattr(e, "optional_target", False)]
        for i, (kind, distinct) in enumerate(kinds):
            needed = 1 + (sum(k == kind for k, _ in kinds[:i]) if distinct else 0)
            if len(self.target_options(kind, seat, colors)) < needed:
                return False
        return True

    def _choose_modes(self, seat: Seat, card: Card, modal: Modal, from_command_zone: bool = False,
                      casting: bool = False) -> tuple[list, str]:
        """Ask the controller for the modes of a modal spell or ability (only ones with legal targets are offered):
        the chosen modes' effects in printed order, and any extra mana cost for them. When casting, entwine (all the
        modes) and escalate (each mode beyond the first) are offered if they can be paid for."""
        colors = source_qualities(card)
        available = [i for i, effects in enumerate(modal.modes) if self._targets_exist(seat, effects, colors)]
        if len(available) < modal.min:
            return [], ""
        entwine, escalate = (entwine_cost(card), escalate_cost(card)) if casting else (None, None)
        if (entwine and len(available) == len(modal.modes) > 1
                and self._payment(seat, card, from_command_zone, extra=entwine) is not None
                and seat.player.choose(ENTWINE_PROMPT + card.name, YES_NO) == 0):
            return [effect for modes in modal.modes for effect in modes], entwine
        chosen: list[int] = []
        while len(chosen) < modal.max and len(chosen) < len(available):
            if escalate and chosen and self._payment(seat, card, from_command_zone,
                                                     extra=escalate * len(chosen)) is None:
                break  # another mode would cost more than the caster has
            remaining = [i for i in available if i not in chosen]
            options = [_shown(modal.texts[i], card) for i in remaining]
            if len(chosen) >= modal.min:
                options.append(DONE_MODES)
            pick = seat.player.choose(MODE_PROMPT + card.name, options)
            if pick == len(remaining):
                break
            chosen.append(remaining[pick])
        extra = escalate * (len(chosen) - 1) if escalate and len(chosen) > 1 else ""
        return [effect for i in sorted(chosen) for effect in modal.modes[i]], extra

    def _choose_targets(self, seat: Seat, effects, source_name: str, source: Permanent | None = None,
                        colors: frozenset[str] = frozenset()) -> tuple[list, list[str]] | None:
        """Ask `seat` for a target per targeting effect: (targets, labels), or None if one has no legal target.
        "Another target ..." can't be `source` itself, and
        nothing with protection from `colors` (the colors of the spell or source) can be chosen."""
        targets, labels = [], []
        chosen: dict[str, set[int]] = {}  # kind -> which of its options were already chosen ("up to two target ...")
        for effect in effects or []:
            kind = target_kind(effect)
            if not kind:
                continue
            taken = chosen.setdefault(kind, set())
            options = [(i, o) for i, o in enumerate(self.target_options(kind, seat, colors))
                       if not (getattr(effect, "another", False) and o[1] is source)
                       and not (getattr(effect, "distinct", False) and i in taken)]
            if getattr(effect, "optional_target", False):  # "up to one target": it can be left out
                options.append((-1, (NO_TARGET, None)))
            if not options:
                return None
            index, (label, target) = options[seat.player.choose(TARGET_PROMPT + source_name, [o[1][0] for o in options])]
            if index >= 0:
                taken.add(index)
            targets.append(target)
            labels.append(label)
        return targets, labels

    def _cast(self, seat: Seat, card: Card, zone: list[Card], from_command_zone: bool = False,
              graveyard: GraveyardCast | None = None, prepared: Permanent | None = None, free: bool = False) -> None:
        effects = _effects(card)
        paying = dataclasses.replace(card, mana_cost=graveyard.cost) if graveyard else card
        extra = ""
        if effects and isinstance(effects[0], Modal):
            effects, extra = self._choose_modes(seat, card, effects[0], from_command_zone, casting=True)
        # Alternative costs and kicker are announced before targets are chosen (CR 601.2b-c).
        ways = [AlternativeCost("Cast without paying its mana cost")] if free else self._cast_ways(seat, card, from_command_zone, graveyard)
        alternative = ways[0]
        if len(ways) > 1:
            options = [f"Pay {card.mana_cost}" if way is None else way.text for way in ways]
            alternative = ways[seat.player.choose(COST_PROMPT + card.name, options)]
        if alternative and alternative.overload:  # every "target" is "each": no targets
            effects = overloaded_effects(card) or effects
        kicked, kickers = (0, ()) if graveyard else self._choose_kicks(seat, card, effects, from_command_zone, alternative)
        effects = kicked_effects(effects, kicked, kickers)
        targets, labels = self._choose_targets(seat, effects, card.name, colors=source_qualities(card))
        x = 0
        if alternative is None and parse_cost(paying.mana_cost).x:  # casting without paying the mana cost makes X 0
            options = [str(n) for n in range(self._max_x(seat, paying, from_command_zone, kickers, extra) + 1)]
            x = seat.player.choose(X_PROMPT + card.name, options)
        elif any(c.life_x for c in additional_costs(card)):  # "pay X life": any amount that leaves you alive
            x = seat.player.choose(LIFE_X_PROMPT + card.name, [str(n) for n in range(max(seat.life, 1))])
        delve = 0
        if alternative is None and not graveyard and has_keyword(card, "delve"):  # exile as few cards as will do
            delve = next(k for k in range(self._delve_max(seat, paying) + 1)
                         if self._payment(seat, paying, from_command_zone, x, alternative, kickers, extra, delve=k) is not None)
        tapped = self._payment(seat, paying, from_command_zone, x, alternative, kickers, extra, delve=delve)
        self._spend_mana(seat, tapped)
        for _ in range(delve):
            exiled = seat.graveyard[seat.player.choose(DELVE_PROMPT + card.name, [c.name for c in seat.graveyard])]
            seat.graveyard.remove(exiled)
            self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": exiled.name, "to": "exile"})
            self._move_card(seat, exiled, "exile")
        if delve:
            self._left_graveyard(seat)
        zone.remove(card)
        if prepared is not None:  # a copy of the spell is cast, and the creature is no longer prepared
            prepared.prepared = False
        self._pay_extras(seat, card, alternative, graveyard, x, kicked)
        item = StackItem(card, seat, effects, targets, x=x, kicked=kicked, kickers=kickers, exile_after=bool(graveyard and graveyard.exile_after),
                         is_copy=prepared is not None, evoked=bool(alternative and alternative.evoke))
        self.stack.append(item)
        event = {"event": "cast", "seat": seat.index, "card": card.name,
                 "from": "prepared" if prepared else "graveyard" if graveyard else "command_zone" if from_command_zone else "hand",
                 "targets": labels, "x": x, "tapped": [p.card.name for p in tapped]}
        if kicked:
            event["kicked"] = kicked
        if extra:
            event["extra_cost"] = extra
        if alternative:
            event["alternative"] = alternative.text
        self.broadcast(event)
        seat.cast_log.append((self.turn, card))
        if has_keyword(card, "cascade") and prepared is None:  # the trigger goes on the stack above the spell
            ability = TriggeredAbility("cast", (Cascade(int(card.cmc) + x),), False, "Cascade")
            self.stack.append(StackItem(card, seat, list(ability.effects), [], ability))
        self._observe("cast", card, seat, x=x, from_hand=zone is seat.hand and not prepared)
        self._check_ward(item)

    def _choose_kicks(self, seat: Seat, card: Card, effects: list | None, from_command_zone: bool,
                      alternative: AlternativeCost | None) -> tuple[int, tuple[str, ...]]:
        """Ask which kicker costs to pay: yes or no, any affordable number for multikicker, or each of two kicker
        costs. Returns (times kicked, mana kicker costs paid). A kick is only offered when it can be paid and the
        spell's kicked targets exist."""
        costs = kicker_costs(card)
        if not costs and kicker_other_cost(card) is None:
            return 0, ()

        def possible(kickers: tuple[str, ...], kicked: int) -> bool:
            return (self._targets_exist(seat, kicked_effects(effects, kicked, kickers) or [], source_qualities(card))
                    and self._can_pay_extras(seat, card, alternative, kicked)
                    and self._payment(seat, card, from_command_zone, alternative=alternative, kickers=kickers) is not None)

        if is_multikicker(card):
            most = 0
            while most < MAX_X and possible(costs * (most + 1), most + 1):
                most += 1
            times = seat.player.choose(MULTIKICKER_PROMPT + card.name, [str(n) for n in range(most + 1)]) if most else 0
            return times, costs * times
        if len(costs) == 2:
            chosen: tuple[str, ...] = ()
            for cost in costs:
                if (possible(chosen + (cost,), len(chosen) + 1)
                        and seat.player.choose(f"{KICKER_PROMPT}{card.name} ({cost})", YES_NO) == 0):
                    chosen += (cost,)
            return len(chosen), chosen
        if possible(costs, 1) and seat.player.choose(KICKER_PROMPT + card.name, YES_NO) == 0:
            return 1, costs
        return 0, ()

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
                "mana_pool": ["".join(sorted(u)) for u in s.mana_pool],
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
            entering = Permanent(card, sick=True, loyalty=_starting_loyalty(card), kicked=item.kicked, kickers=item.kickers)
            if item.evoked:  # queued first, so it resolves after the creature's own "when it enters" abilities
                self._queue(EVOKE_SACRIFICE, entering, seat)
            self._enter(seat, entering, x=item.x)
            return
        if item.effects is None:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "unsupported": True})
            if not item.is_copy:
                self._move_card(seat, card, "exile" if item.exile_after else "graveyard")
            return
        self._apply_effects(item)  # fizzled or not, the spell goes to the graveyard (or exile, after flashback)
        if not item.is_copy:
            self._move_card(seat, card, "exile" if item.exile_after else "graveyard")

    def _resolve_aura(self, item: StackItem) -> None:
        """An Aura spell enters attached to its target, or goes to the graveyard if the target
        is no longer legal (CR 608.3b)."""
        seat, card = item.controller, item.card
        target = item.targets[0] if item.targets else None
        if target is None or not self.is_legal_target(aura_kind(card), target, seat, source_qualities(card)):
            self.broadcast({"event": "fizzle", "seat": seat.index, "card": card.name})
            self._move_card(seat, card, "graveyard")
            return
        if (reanimation := reanimation_aura(card)) is not None:  # Animate Dead: the creature comes back, the Aura on it
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
            self.return_from_graveyard(target, seat, "battlefield", tapped=reanimation[0])
            creature = next((p for p in reversed(seat.battlefield) if p.card is target.card), None)
            if creature is None:  # it could not come back (it was exiled instead, say): the Aura has nothing to enchant
                self._move_card(seat, card, "graveyard")
                return
            self._enter(seat, Permanent(card, sick=True, attached_to=creature, kicked=item.kicked, kickers=item.kickers))
            self.broadcast({"event": "attached", "card": card.name, "to": creature.card.name})
            return
        self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
        self._enter(seat, Permanent(card, sick=True, attached_to=target, kicked=item.kicked, kickers=item.kickers))
        self.broadcast({"event": "attached", "card": card.name, "to": target.card.name})

    def return_to_hand_from_graveyard(self, card: Card) -> None:
        """Put `card` from whichever graveyard it is in into its hand (it may already be gone)."""
        for seat in self.seats:
            if any(c is card for c in seat.graveyard):
                seat.graveyard = [c for c in seat.graveyard if c is not card]
                seat.hand.append(card)
                self.broadcast({"event": "returned_to_hand", "seat": seat.index, "card": card.name})
                self._left_graveyard(seat)
                return

    def attach(self, attachment: Permanent, creature: Permanent) -> None:
        """Attach an Equipment to a creature (moving it if it was on another)."""
        if self.on_battlefield(attachment) and self.on_battlefield(creature):
            attachment.attached_to = creature
            if reconfigure_cost(attachment.card) and attachment.reconfigured is None and "Creature" in attachment.card.type_line:
                attachment.reconfigured = attachment.card  # Reconfigure: attached, it isn't a creature
                head, dash, tail = attachment.card.type_line.partition("\u2014")
                attachment.card = dataclasses.replace(attachment.card,
                                                      type_line=" ".join(w for w in head.split() if w != "Creature") + f" {dash}{tail}".rstrip())
            self.broadcast({"event": "attached", "card": attachment.card.name, "to": creature.card.name})

    def untap_all(self, seat: Seat, kind: str) -> None:
        for permanent in seat.battlefield:
            if _permanent_matches(kind, permanent.card):
                permanent.tapped = False

    def detach(self, attachment: Permanent) -> None:
        """An Equipment stops being attached; a Reconfigure creature becomes a creature again."""
        attachment.attached_to = None
        if attachment.reconfigured is not None:
            attachment.card, attachment.reconfigured = attachment.reconfigured, None

    def _resolve_ability(self, item: StackItem) -> None:
        seat, ability = item.controller, item.ability
        if getattr(ability, "optional", False) and seat.player.choose(OPTIONAL_PROMPT + item.card.name, YES_NO) != 0:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": item.card.name,
                            "ability": _shown(ability.text, item.card), "declined": True})
            return
        condition = getattr(ability, "condition", None)
        if condition and not self.condition_holds(condition, seat, item.source):  # checked again on resolution (CR 603.4)
            self.broadcast({"event": "resolve", "seat": seat.index, "card": item.card.name,
                            "ability": _shown(ability.text, item.card), "condition_false": True})
            return
        self._apply_effects(item)

    def evaluate(self, amount: Amount, controller: Seat) -> int:
        """Work out an amount that depends on the game, for the resolving spell or ability."""
        source, kind = self.resolving_source, amount.kind
        this_turn = [card for turn, card in controller.cast_log if turn == self.turn]
        if kind == "source_power":
            if source is None:
                return 0
            return self.power(source) if self.on_battlefield(source) else source.last_power  # last known (CR 608.2h)
        if kind == "source_counters":
            return source.counters.get(amount.what, 0) if source else 0
        if kind == "on_battlefield":
            return sum(_has_type(p.card, amount.what) for s in self.live_seats() for p in s.battlefield)
        if kind == "you_control":
            return sum(_has_type(p.card, amount.what) for p in controller.battlefield)
        if kind == "graveyard":
            return sum(_card_matches(amount.what, c) for c in controller.graveyard)
        if kind == "half_life":
            return max(0, controller.life) // 2 if amount.what == "down" else (max(0, controller.life) + 1) // 2
        if kind == "life_gained":
            return controller.life_gained_amount if controller.life_gained_turn == self.turn else 0
        if kind == "spells_cast":
            return len(this_turn)
        if kind == "greatest_mana_value_cast":
            return int(max((c.cmc for c in this_turn if _watch_type_matches(amount.what, c)), default=0))
        if kind == "opponents":
            return len(self.opponents(controller))
        raise ValueError(f"unknown amount {kind}")

    def amount(self, value: int | str) -> int:
        """A number from an effect; "X" is the resolving spell's X."""
        return self.x_value if value == "X" else value

    def _apply_effects(self, item: StackItem) -> bool:
        """Do a spell's or ability's effects; False if it fizzled because every target was gone (CR 608.2b)."""
        self.x_value, self.resolving_source = item.x, item.source
        self.resolving_item, self.resolving_colors = item, source_qualities(item.card)
        try:
            return self._apply_effects_now(item)
        finally:
            self.x_value, self.resolving_source = 0, None
            self.resolving_item, self.resolving_colors = None, frozenset()

    def _apply_effects_now(self, item: StackItem) -> bool:
        seat = item.controller
        colors = source_qualities(item.card)
        legal = [(t is None and getattr(e, "optional_target", False)) or self.is_legal_target(target_kind(e), t, seat, colors)
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
            elif uses_player(effect):
                target = item.player if item.player and not item.player.lost else None
            elif uses_subject(effect):
                target = item.subject if item.subject and self.on_battlefield(item.subject) else None
            elif getattr(effect, "uses_dead_subject", False):
                target = item.subject  # "When enchanted creature dies, return it ...": the creature has already left
            elif getattr(effect, "uses_dead_both", False):
                target = (item.source, item.subject) if item.source else None
            elif getattr(effect, "uses_dead_source", False):
                target = item.source  # persist and undying: the creature has already left the battlefield
            elif uses_source(effect):
                target = item.source if item.source and self.on_battlefield(item.source) else None
            effect.resolve(self, seat, target)
        return True

    # --- triggered abilities -------------------------------------------------

    def trigger(self, event: str, permanent: Permanent, controller: Seat, subject: Permanent | None = None,
                player: Seat | None = None) -> None:
        """Note that `permanent`'s abilities for `event` triggered; they go on the stack
        the next time a player would get priority (CR 603.3)."""
        for ability in triggered_abilities(permanent.card):
            if ability.event == event and ability.watch is None:
                for _ in range(self._trigger_times(controller, event, permanent.card)):
                    self._queue(ability, permanent, controller, subject=subject, player=player)

    def _trigger_each(self, event: str, seat: Seat, subject: Permanent | None = None,
                      player: Seat | None = None) -> None:
        """`event` happened for `seat`: every permanent it controls with an ability for it triggers. `subject` is
        the permanent it happened to, `player` the player who did it."""
        for permanent in list(seat.battlefield):
            self.trigger(event, permanent, seat, subject, player)

    def _searched(self, seat: Seat) -> None:
        """`seat` searched their library (found something or not)."""
        for opponent in self.opponents(seat):
            self._trigger_each("opponent_search", opponent, player=seat)

    def _discarded(self, seat: Seat) -> None:
        """`seat` discarded a card: "Whenever you discard a card" and "Whenever an opponent discards a card"."""
        self._trigger_each("discard", seat)
        for opponent in self.opponents(seat):
            self._trigger_each("opponent_discard", opponent, player=seat)

    def _queue(self, ability: TriggeredAbility, permanent: Permanent, controller: Seat, x: int = 0,
               subject: Permanent | None = None, player: Seat | None = None) -> None:
        if ability.condition and not self.condition_holds(ability.condition, controller, permanent):
            return
        if ability.once_per_turn:  # "This ability triggers only once each turn."
            if permanent.triggered_turn.get(ability.text) == self.turn:
                return
            permanent.triggered_turn[ability.text] = self.turn
        self.pending.append(PendingTrigger(ability, permanent, controller, x, subject, player))

    def condition_holds(self, condition: Condition, seat: Seat, source: Permanent | None = None) -> bool:
        """Whether an intervening "if" clause is true for `seat`, the ability's controller, and `source`."""
        kind = condition.kind
        if kind == "kicked":  # "if it was kicked (with its {R} kicker)"
            return source is not None and bool(source.kicked) and (not condition.what or condition.what in source.kickers)
        if kind == "graveyard_left":
            return seat.graveyard_left_turn == self.turn
        if kind == "gained_life":
            return seat.life_gained_turn == self.turn
        if kind == "opponent_more_lands":
            lands = lambda s: sum(is_land(p.card) for p in s.battlefield)
            return any(lands(o) > lands(seat) for o in self.opponents(seat))
        if kind == "cast_this_turn":
            return any(turn == self.turn and _watch_type_matches(condition.what, c) for turn, c in seat.cast_log)
        if kind == "no_counter":  # "if it had no -1/-1 counters on it": what it had when it left
            return source is None or source.counters.get(condition.what, 0) == 0
        if kind == "your_turn":
            return self.active == seat.index
        if kind == "monarch":
            return self.monarch is seat
        if kind == "hand_at_least":
            return len(seat.hand) >= condition.count
        if kind == "hand_none":
            return not seat.hand
        if kind == "control_color_at_least":
            letter = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}[condition.what]
            return sum(letter in p.card.colors for p in seat.battlefield) >= condition.count
        if kind == "gained_life_at_least":
            return seat.life_gained_turn == self.turn and seat.life_gained_amount >= condition.count
        if kind == "creatures_died":
            return self.deaths_turn == self.turn and self.deaths_count >= condition.count
        if kind == "not_prepared":
            return source is not None and not source.prepared
        if kind == "graveyard_at_least":
            return sum(_card_matches(condition.what, c) for c in seat.graveyard) >= condition.count
        if kind == "any_hand_at_most":
            return any(len(s.hand) <= condition.count for s in self.live_seats())
        if kind == "opponent_more_cards":
            return any(len(o.hand) > len(seat.hand) for o in self.opponents(seat))
        matching = sum(_has_type(p.card, condition.what) for p in seat.battlefield)
        return matching >= condition.count if kind == "control_at_least" else matching == 0

    def _observe(self, event: str, card: Card, seat: Seat, subject: Permanent | None = None,
                 extra: list[tuple[Permanent, Seat]] = (), x: int = 0, from_hand: bool = False) -> None:
        """Trigger abilities that watch for `event` happening to `card` (controlled by `seat`):
        "Whenever another creature enters", landfall, "whenever a creature dies",
        "whenever you cast a spell". `extra` adds watchers that just left the battlefield
        and still "look back in time" (CR 603.10a). Event "copy" is a spell being copied, which only a
        "cast or copy" watcher (magecraft) notices."""
        watchers = [(p, s) for s in self.live_seats() for p in s.battlefield] + list(extra)
        for watcher, watcher_seat in watchers:
            for ability in triggered_abilities(watcher.card):
                watch = ability.watch
                if not watch or ability.event != ("cast" if event == "copy" else event):
                    continue
                if event == "copy" and not watch.with_copy:
                    continue
                if event in ("cast", "copy") and (card.cmc < watch.mv_at_least or (watch.from_hand and not from_hand)):
                    continue
                if watch.other and subject is watcher:
                    continue
                if event in ("cast", "copy"):
                    if watch.caster == "you" and watcher_seat is not seat:
                        continue
                    if watch.caster == "opponent" and watcher_seat is seat:
                        continue
                elif watch.yours and watcher_seat is not seat:
                    continue
                if watch.theirs and watcher_seat is seat:
                    continue
                if watch.nontoken and _is_token(card):
                    continue
                if not _watch_type_matches(watch.kind, card):
                    continue
                if watch.nth_each_turn and sum(turn == self.turn and _watch_type_matches(watch.kind, c)
                                               for turn, c in seat.cast_log) != watch.nth_each_turn:
                    continue
                for _ in range(self._trigger_times(watcher_seat, event, card)):
                    self._queue(ability, watcher, watcher_seat, x, subject, seat)

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
            effects = list(trigger.ability.effects)
            if effects and isinstance(effects[0], Modal):  # "When this enters, choose one —": modes, then targets
                effects, _ = self._choose_modes(seat, trigger.source, effects[0])
                if not effects:
                    continue
            chosen = self._choose_targets(seat, effects, trigger.source.name, trigger.permanent,
                                          source_qualities(trigger.source))
            if chosen is None:
                continue
            targets, labels = chosen
            item = StackItem(trigger.source, seat, effects, targets, trigger.ability,
                             trigger.permanent, x=trigger.x, subject=trigger.subject, player=trigger.player)
            self.stack.append(item)
            self.broadcast({"event": "trigger", "seat": seat.index, "card": trigger.source.name,
                            "ability": _shown(trigger.ability.text, trigger.source), "targets": labels})
            self._check_ward(item)

    # --- targets -------------------------------------------------------------

    def target_options(self, kind: str, caster: Seat, colors: frozenset[str] = frozenset()) -> list[tuple[str, Any]]:
        """Legal targets of `kind` for a spell or ability `caster` controls, as (label, object). `colors` are the
        colors of the source: a permanent with protection from one of them can't be chosen."""
        options: list[tuple[str, Any]] = []
        if kind == "creature card in a graveyard":  # Animate Dead is cast on one
            kind = "graveyard:creature:any"
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
        if _split_controller(kind)[0].endswith("spell"):  # "spell", "noncreature spell", "... spell you control"
            kind, whose = _split_controller(kind)
            options += [(f"Spell: {i.card.name} (seat {i.controller.index})", i) for i in self.stack
                        if not i.ability and _watch_type_matches(kind, i.card)
                        and not (whose == "you" and i.controller is not caster)]
            return options
        limit = re.search(r" with mana value (\d+) or (less|greater)$", kind)  # "creature ... with mana value 3 or less"
        if limit:
            kind = kind[:limit.start()]
        attacked = kind.endswith(" that attacked this turn")  # "creature that attacked this turn"
        kind, controller = _split_controller(kind.removesuffix(" that attacked this turn"))
        state, _, base = kind.partition(" ") if kind.split(" ")[0] in ("tapped", "untapped", "attacking") else ("", "", kind)
        for seat in self.live_seats():
            if (controller == "opponent" and seat is caster) or (controller == "you" and seat is not caster):
                continue
            for n, permanent in enumerate(seat.battlefield):
                card = permanent.card
                if not _permanent_matches(base, card) or self.has_keyword(permanent, "shroud"):
                    continue
                if attacked and permanent.attacked_turn != self.turn:
                    continue
                if limit and (card.cmc > int(limit[1]) if limit[2] == "less" else card.cmc < int(limit[1])):
                    continue
                if ((state == "tapped" and not permanent.tapped) or (state == "untapped" and permanent.tapped)
                        or (state == "attacking" and not any(a.attacker is permanent for a in self.combat.attacks))):
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
        """Whether the permanent has protection from a source with these qualities (color letters, card types,
        "monocolored" and so on; see source_qualities), by its own text or because something gave it: it can't be
        targeted, damaged, blocked, enchanted or equipped by it."""
        if not colors:
            return False
        held = set(printed_protection(permanent.card))
        for modifier in self.modifiers(permanent):
            for keyword in modifier.keywords:
                if keyword.startswith("protection from "):
                    held |= protection_tokens(keyword)
        return "everything" in held or bool(held & colors)

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
                self._trigger_each("draw", seat)
                for opponent in self.opponents(seat):
                    self._trigger_each("opponent_draw", opponent, player=seat)
                if seat.draw_turn != self.turn:
                    seat.draw_turn, seat.draw_count = self.turn, 0
                seat.draw_count += 1
                if seat.draw_count == 2:
                    self._trigger_each("second_draw", seat)
                    for opponent in self.opponents(seat):
                        self._trigger_each("opponent_second_draw", opponent, player=seat)

    def change_life(self, seat: Seat, amount: int) -> None:
        seat.life += amount
        self.broadcast({"event": "life", "seat": seat.index, "change": amount, "life": seat.life})
        if amount:  # "Whenever you gain life" / "Whenever you lose life": once per event, not per point
            first_loss = amount < 0 and seat.life_lost_turn != self.turn
            first_gain = amount > 0 and seat.life_gained_turn != self.turn
            if amount < 0:
                seat.life_lost_turn = self.turn
            else:
                if seat.life_gained_turn != self.turn:
                    seat.life_gained_amount = 0
                seat.life_gained_amount += amount
                seat.life_gained_turn = self.turn
            for permanent in list(seat.battlefield):
                self.trigger("gain_life" if amount > 0 else "lose_life", permanent, seat)
                if first_loss:
                    self.trigger("first_life_loss", permanent, seat)
                if first_gain:
                    self.trigger("first_life_gain", permanent, seat)
            for opponent in self.opponents(seat):
                self._trigger_each("opponent_gain_life" if amount > 0 else "opponent_lose_life", opponent, player=seat)

    def damage(self, target: Seat | Permanent, amount: int, source: Permanent | None = None,
               combat: bool = False) -> None:
        colors = source_qualities(source.card) if source is not None else self.resolving_colors
        if isinstance(target, Permanent) and self.protected_from(target, colors):
            self.broadcast({"event": "damage_prevented", "card": target.card.name, "amount": amount})
            return
        controller = self.controller_of(source) if source else None
        if isinstance(target, Seat):
            self.change_life(target, -amount)
            if combat and controller:
                self.trigger("combat_damage_to_player", source, controller)
                if target is self.monarch and controller is not target:  # CR 724.2
                    self.become_monarch(controller)
                if target is self.initiative and controller is not target:  # CR 725.2
                    self.take_initiative(controller)
                for holder in self.live_seats():  # "Whenever equipped (enchanted) creature deals combat damage to a player"
                    for attachment in list(holder.battlefield):
                        if attachment.attached_to is source:
                            self.trigger("host_combat_damage", attachment, holder, source)
                for permanent in list(controller.battlefield):  # "Whenever a creature (token) you control deals ..."
                    self.trigger("ally_combat_damage", permanent, controller, subject=source)
                    if _is_token(source.card):
                        self.trigger("token_combat_damage", permanent, controller, subject=source)
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

    def destroy(self, permanent: Permanent, no_regen: bool = False) -> None:
        if self.has_keyword(permanent, "indestructible"):
            return
        if not no_regen and self._regenerated(permanent):
            return
        self._leave_battlefield(permanent, "destroyed")

    def regenerate(self, permanent: Permanent) -> None:
        """Give `permanent` a regeneration shield until end of turn."""
        permanent.regeneration += 1
        self.broadcast({"event": "regeneration_shield", "card": permanent.card.name})

    def _regenerated(self, permanent: Permanent) -> bool:
        """Use up a regeneration shield, if it has one, instead of letting `permanent` be destroyed: it taps,
        loses all damage and is removed from combat (CR 701.15)."""
        if permanent.regeneration <= 0:
            return False
        permanent.regeneration -= 1
        permanent.tapped = True
        permanent.damage = 0
        permanent.deathtouched = False
        self.combat.attacks = [a for a in self.combat.attacks if a.attacker is not permanent]
        for attack in self.combat.attacks:
            attack.blockers = [b for b in attack.blockers if b is not permanent]
        self.broadcast({"event": "regenerated", "card": permanent.card.name})
        return True

    def mass_targets(self, kind: str, caster: Seat, restriction: MassFilter | None = None) -> list[Permanent]:
        """Every permanent an "all"/"each" effect of `kind` affects, e.g. "creature",
        "artifact or enchantment", "creature you don't control", narrowed by a restriction such as
        "with flying". Nothing is targeted."""
        kind, controller = _split_controller(kind)
        found: list[Permanent] = []
        for seat in self.live_seats():
            if (controller == "opponent" and seat is caster) or (controller == "you" and seat is not caster):
                continue
            found += [p for p in seat.battlefield
                      if _permanent_matches(kind, p.card) and self._passes(p, restriction)]
        return found

    def _passes(self, permanent: Permanent, restriction: MassFilter | None) -> bool:
        if restriction is None:
            return True
        if restriction.keyword and self.has_keyword(permanent, restriction.keyword) != restriction.keyword_wanted:
            return False
        if restriction.stat:
            if restriction.stat == "mana_value":
                value = permanent.card.cmc
            else:
                value = self.power(permanent) if restriction.stat == "power" else self.toughness(permanent)
                if value is None or "Creature" not in permanent.card.type_line:
                    return False
            at_most = self.x_value if restriction.at_most == "X" else restriction.at_most
            if (restriction.at_least is not None and value < restriction.at_least) or \
                    (at_most is not None and value > at_most):
                return False
        if restriction.color and (restriction.color in permanent.card.colors) == restriction.other_color:
            return False
        card = permanent.card
        if ((restriction.token is not None and _is_token(card) != restriction.token)
                or (restriction.legendary is not None and ("Legendary" in card.type_line) != restriction.legendary)
                or (restriction.basic is not None and ("Basic" in card.type_line) != restriction.basic)
                or (restriction.tapped is not None and permanent.tapped != restriction.tapped)
                or (restriction.has_type and restriction.has_type not in card.type_line)):
            return False
        if restriction.colors_are:
            count = len(card.colors)
            if not {"one or more colors": count >= 1, "colorless": count == 0, "multicolored": count >= 2,
                    "monocolored": count == 1}[restriction.colors_are]:
                return False
        if restriction.exclude is not None and self._spared(permanent, restriction.exclude):
            return False
        return True

    def _in_state(self, permanent: Permanent, state: str) -> bool:
        """Whether a permanent is "attacking", "tapped" or "untapped" (any permanent, if no state is asked for)."""
        if state == "attacking":
            return any(a.attacker is permanent for a in self.combat.attacks)
        return {"tapped": permanent.tapped, "untapped": not permanent.tapped}.get(state, True)

    def _spared(self, permanent: Permanent, spared: MassFilter) -> bool:
        """Whether an "except for ..." filter describes this permanent (so it is left alone)."""
        return self._passes(permanent, spared)

    def destroy_all(self, permanents: list[Permanent], no_regen: bool = False, gives: tuple[int, Card] | None = None) -> None:
        """Destroy them all at once; indestructible ones survive, and so do ones with a regeneration shield
        unless they "can't be regenerated". `gives`: each controller then gets tokens for each one destroyed."""
        doomed = [p for p in permanents if not self.has_keyword(p, "indestructible")
                  and (no_regen or not self._regenerated(p))]
        self._leave_together([(p, "destroyed") for p in doomed])
        self._give_back(doomed, gives)

    def exile_all(self, permanents: list[Permanent], gives: tuple[int, Card] | None = None) -> None:
        self._leave_together([(p, "exiled") for p in permanents], destination="exile")
        self._give_back(permanents, gives)

    def _give_back(self, gone: list[Permanent], gives: tuple[int, Card] | None) -> None:
        """"For each creature destroyed this way, its controller creates a token": for each one that left."""
        if gives is None:
            return
        count, token = gives
        for permanent in gone:
            if permanent.last_controller is not None and not self.on_battlefield(permanent):
                self.create_tokens(permanent.last_controller, token, count)

    def return_to_hand(self, permanent: Permanent) -> None:
        """Bounce: a permanent goes to its owner's hand (a token just stops existing)."""
        self._leave_together([(permanent, "returned")], destination="hand")

    def return_all_to_hand(self, permanents: list[Permanent]) -> None:
        self._leave_together([(p, "returned") for p in permanents], destination="hand")

    def return_from_graveyard(self, target: GraveyardTarget, controller: Seat, to: str, tapped: bool = False) -> None:
        """Move a card out of a graveyard to its owner's hand, or onto the battlefield under
        `controller`'s control (it stays its owner's card)."""
        seat, card = target.seat, target.card
        if card not in seat.graveyard:
            return
        seat.graveyard.remove(card)
        self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": to})
        self._left_graveyard(seat)
        if to == "hand":
            seat.hand.append(card)
        else:
            self._enter(controller, Permanent(card, sick=True, tapped=tapped, loyalty=_starting_loyalty(card), owner=seat))

    def _graveyard_of(self, card: Card) -> Seat | None:
        return next((s for s in self.seats if any(c is card for c in s.graveyard)), None)

    def return_dead_to_battlefield(self, dead: Permanent, controller: Seat, under_owner: bool) -> None:
        """A creature that just died comes back from its owner's graveyard, under `controller`'s control unless
        `under_owner`."""
        holder = self._graveyard_of(dead.card)
        if holder is not None:
            self.return_from_graveyard(GraveyardTarget(dead.card, holder), holder if under_owner else controller,
                                       "battlefield")

    def return_aura(self, source: Permanent, controller: Seat, when: str, host: Permanent | None) -> None:
        """An Aura in a graveyard comes back to the battlefield, right away ("now") or as the next end step begins.
        It enters attached to what `controller` chooses, or to `host` (the creature that died, if it is back)."""
        card = source.card

        def bring_back() -> None:
            holder = self._graveyard_of(card)
            if holder is None or controller.lost:
                return
            if host is not None:  # the creature came back as a new object
                options = [("", p) for s in self.live_seats() for p in s.battlefield if p.card is host.card]
            else:
                options = self.target_options(aura_kind(card) or "creature", controller, source_qualities(card))
            if not options:
                return  # nothing to enchant: it stays in the graveyard
            pick = controller.player.choose(f"Enchant which permanent with {card.name}? ", [name for name, _ in options])                 if len(options) > 1 else 0
            target = options[pick][1]
            holder.graveyard = [c for c in holder.graveyard if c is not card]
            self.broadcast({"event": "left_graveyard", "seat": holder.index, "card": card.name, "to": "battlefield"})
            self._left_graveyard(holder)
            self._enter(controller, Permanent(card, sick=True, attached_to=target, owner=holder))
            self.broadcast({"event": "attached", "card": card.name, "to": target.card.name})

        if when == "now":
            bring_back()
        else:
            fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
            self.at_end_step.append((fire_turn, bring_back))

    def exile_from_graveyard(self, target: GraveyardTarget) -> None:
        seat, card = target.seat, target.card
        if card in seat.graveyard:
            seat.graveyard.remove(card)
            self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": "exile"})
            self._move_card(seat, card, "exile")
            self._left_graveyard(seat)

    def _left_graveyard(self, seat: Seat) -> None:
        """One or more cards just left `seat`'s graveyard, as one event."""
        seat.graveyard_left_turn = self.turn
        for permanent in list(seat.battlefield):
            self.trigger("graveyard_leave", permanent, seat)

    def tutor(self, seat: Seat, card_type: str, to: str, reveal: bool) -> None:
        """Search the library for a card of `card_type`: it goes to the hand (`to` is "hand")
        or to the top of the library ("top") after shuffling. Only "reveal" shows others which card."""
        matches = _unique([c for c in seat.library if _card_matches(card_type, c)])
        found = None
        if matches:
            found = matches[seat.player.choose(SEARCH_CARD_PROMPT, [c.name for c in matches])]
            seat.library.remove(found)
        self.rng.shuffle(seat.library)
        self._searched(seat)
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

    def sacrifice(self, seat: Seat, kind: str = "creature", count: int | None = 1, greatest: bool = False) -> None:
        """`seat` chooses `count` of its permanents of `kind` (a creature, artifact, land, ...) and sacrifices them
        (all of them if `count` is None); with `greatest`, only a creature with the greatest power among its creatures
        can be chosen. No targeting, so hexproof and indestructible don't help."""
        state = kind.split(" ")[0] if kind.split(" ")[0] in ("attacking", "tapped", "untapped") else ""
        base = kind.removeprefix(state + " ") if state else kind
        options = [p for p in seat.battlefield if _permanent_matches(base, p.card) and self._in_state(p, state)]
        if count is None:
            self._leave_together([(p, "sacrificed") for p in options])
            return
        for _ in range(count):
            options = [p for p in options if self.on_battlefield(p)]
            if greatest and options:
                top = max(self.power(p) for p in options)
                options = [p for p in options if self.power(p) == top]
            if not options:
                return
            prompt = SACRIFICE_PROMPT if kind == "creature" else f"Choose a {kind} to sacrifice"
            choice = options[seat.player.choose(prompt, [self.label(p) for p in options])]
            self._leave_together([(choice, "sacrificed")])

    # --- characteristics -----------------------------------------------------

    def modifiers(self, permanent: Permanent) -> list[Modifier]:
        """Everything currently changing a permanent: its "until end of turn" effects, plus
        static abilities of permanents its controller controls ("Creatures you control get +1/+1")."""
        mods = permanent.until_end_of_turn + permanent.until_next_turn
        controller = self.controller_of(permanent)
        if controller is None or "Creature" not in permanent.card.type_line:
            return mods
        subtypes = permanent.card.type_line.partition("—")[2].split()
        for source in controller.battlefield:
            for buff in static_abilities(source.card):
                if (buff.other and source is permanent) or (buff.subtype and buff.subtype not in subtypes):
                    continue
                if buff.self_only and source is not permanent:
                    continue
                if buff.color and buff.color not in permanent.card.colors:
                    continue
                if buff.attacking and not any(a.attacker is permanent for a in self.combat.attacks):
                    continue
                if buff.condition and not self.condition_holds(buff.condition, controller, source):
                    continue
                mods.append(self._scaled(buff.modifier, buff.per, permanent, controller))
        for seat in self.seats:  # Equipment and Auras attached to it
            for attachment in seat.battlefield:
                if attachment.attached_to is permanent:
                    mods.extend(self._scaled(buff.modifier, buff.per, permanent, controller)
                                for buff in attached_abilities(attachment.card))
        return mods

    def _scaled(self, modifier: Modifier, per: tuple[str, str] | None, permanent: Permanent, controller: Seat) -> Modifier:
        """A "for each ..." bonus times how many there are right now."""
        if per is None:
            return modifier
        what, kind = per
        if what == "permanent":
            count = sum(_has_type(p.card, kind) for p in controller.battlefield)
        elif what == "graveyard":
            count = sum(_card_matches(kind, c) for c in controller.graveyard)
        elif what == "auras_on_it":
            count = sum(1 for s in self.seats for p in s.battlefield
                        if p.attached_to is permanent and "Aura" in p.card.type_line)
        else:  # "auras_on_creatures": Auras you control that are attached to a creature
            count = sum(1 for p in controller.battlefield if "Aura" in p.card.type_line and p.attached_to is not None
                        and "Creature" in p.attached_to.card.type_line)
        return Modifier(modifier.power * count, modifier.toughness * count, modifier.keywords)

    def goader_of(self, permanent: Permanent) -> Seat | None:
        """Who is goading this creature: the player who goaded it, or the controller of an Aura that says it is goaded."""
        if permanent.goaded_by:
            return permanent.goaded_by
        for seat in self.seats:
            for attachment in seat.battlefield:
                if attachment.attached_to is permanent and any(b.goaded for b in attached_abilities(attachment.card)):
                    return seat
        return None

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

    def gain_control(self, permanent: Permanent, seat: Seat, aura: Permanent | None = None, until_eot: bool = False,
                     untap: bool = False, haste: bool = False) -> None:
        """`seat` takes control of `permanent` (CR 701.10): it moves to their battlefield, is summoning sick under
        them, and leaves combat. `aura` holds control for as long as it stays attached; `until_eot` gives it back
        at end of turn. Its owner doesn't change."""
        current = self.controller_of(permanent)
        if current is None:
            return
        if current is not seat:
            permanent.owner = permanent.owner or current  # whose card it is doesn't change
            current.battlefield = [p for p in current.battlefield if p is not permanent]
            seat.battlefield.append(permanent)
            permanent.sick = True
            if permanent.control_origin is None:
                permanent.control_origin = current
            self.combat.attacks = [a for a in self.combat.attacks if a.attacker is not permanent]
            for attack in self.combat.attacks:
                attack.blockers = [b for b in attack.blockers if b is not permanent]
            self.broadcast({"event": "gained_control", "seat": seat.index, "card": permanent.card.name})
        if aura is not None:
            permanent.control_aura = aura
        if until_eot:
            permanent.control_eot = True
        if untap:
            permanent.tapped = False
        if haste:
            self.modify_until_end_of_turn(permanent, Modifier(0, 0, frozenset({"haste"})))

    def _return_control(self, permanent: Permanent) -> None:
        """A control-change effect ended: `permanent` goes back to the player who controlled it before."""
        origin, now = permanent.control_origin, self.controller_of(permanent)
        permanent.control_origin, permanent.control_aura, permanent.control_eot = None, None, False
        if origin is None or origin.lost or now is None or now is origin:
            return
        now.battlefield = [p for p in now.battlefield if p is not permanent]
        origin.battlefield.append(permanent)
        permanent.sick = True
        self.combat.attacks = [a for a in self.combat.attacks if a.attacker is not permanent]
        self.broadcast({"event": "control_returned", "seat": origin.index, "card": permanent.card.name})

    def proliferate(self, seat: Seat) -> None:
        """`seat` chooses any permanents with counters (or planeswalkers); each gets one more of every kind of
        counter it has."""
        candidates = [p for s in self.live_seats() for p in s.battlefield
                      if any(n > 0 for n in p.counters.values()) or p.loyalty is not None]
        chosen: list[Permanent] = []
        while len(chosen) < len(candidates):
            rest = [p for p in candidates if p not in chosen]
            pick = seat.player.choose(PROLIFERATE_PROMPT, [self.label(p) for p in rest] + [DONE])
            if pick == len(rest):
                break
            chosen.append(rest[pick])
        for permanent in chosen:
            for counter, count in list(permanent.counters.items()):
                if count > 0:
                    self.put_counters(permanent, counter, 1)
            if permanent.loyalty is not None:
                permanent.loyalty += 1
                self.broadcast({"event": "counters", "card": permanent.card.name, "counter": "loyalty",
                                "added": 1, "total": permanent.loyalty})

    def fight(self, first: Permanent, second: Permanent, one_sided: bool = False) -> None:
        """Two creatures each deal damage equal to their power to the other at the same time (CR 701.12). With
        `one_sided`, only `first` deals damage."""
        if not (self.on_battlefield(first) and self.on_battlefield(second)):
            return
        hit_second, hit_first = self.power(first), self.power(second)
        self.broadcast({"event": "fight", "card": first.card.name, "against": second.card.name})
        self.damage(second, hit_second, source=first)
        if not one_sided:
            self.damage(first, hit_first, source=second)

    def return_with_counter(self, dead: Permanent | None, counter: str) -> None:
        """Persist and undying: put the card that just died back onto the battlefield with a counter, under its
        owner's control, if it is still in the graveyard (a token or a commander sent elsewhere isn't)."""
        seat = (dead.owner or dead.last_controller) if dead is not None else None
        if seat is None or dead.card not in seat.graveyard:
            return
        seat.graveyard.remove(dead.card)
        self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": dead.card.name, "to": "battlefield"})
        self._left_graveyard(seat)
        self._enter(seat, Permanent(dead.card, sick=True, loyalty=_starting_loyalty(dead.card), counters={counter: 1}))

    def put_counters(self, permanent: Permanent, counter: str, count: int) -> None:
        holder = self.controller_of(permanent)
        if holder is not None:
            count = self._counters_to_add(holder, permanent.card, counter, count)
        permanent.counters[counter] = permanent.counters.get(counter, 0) + count
        self.broadcast({"event": "counters", "card": permanent.card.name, "counter": counter,
                        "added": count, "total": permanent.counters[counter]})

    def remove_counters(self, permanent: Permanent, counter: str | None, count: int | None) -> None:
        """Remove `count` counters of one kind (all of them if None), or every counter if `counter` is None."""
        for kind in [counter] if counter else list(permanent.counters):
            removed = min(permanent.counters.get(kind, 0), permanent.counters.get(kind, 0) if count is None else count)
            if removed:
                permanent.counters[kind] -= removed
                if not permanent.counters[kind]:
                    del permanent.counters[kind]
                self.broadcast({"event": "counters", "card": permanent.card.name, "counter": kind,
                                "added": -removed, "total": permanent.counters.get(kind, 0)})

    def create_tokens(self, seat: Seat, token: Card, count: int, counters: tuple[int, str] | None = None) -> None:
        for _ in range(count * self._factor(seat, "tokens")):
            self.broadcast({"event": "token_created", "seat": seat.index, "card": token.name,
                            "type_line": token.type_line, "power": token.power, "toughness": token.toughness})
            made = Permanent(token, sick=True)
            self._enter(seat, made)
            if counters:
                self.put_counters(made, counters[1], counters[0])

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

    def flicker(self, target: Permanent, controller: Seat, when: str, to: str, under_owner: bool) -> None:
        """Exile `target`, then return it to the battlefield (or its owner's hand) right away (`when` is "now") or as the
        next end step begins ("end_step"). A token is gone for good; it comes back under `controller`'s control if
        the card says "under your control", otherwise under its owner's."""
        owner = target.owner or self.controller_of(target)
        card, before = target.card, len(owner.exile)
        self.exile(target)
        if _is_token(card) or len(owner.exile) <= before:  # a token ceases to exist; a commander went to the command zone
            return

        def bring_back() -> None:
            if card not in owner.exile:
                return
            if to == "hand":
                owner.exile.remove(card)
                owner.hand.append(card)
                self.broadcast({"event": "returned_from_exile", "seat": owner.index, "card": card.name, "to": "hand"})
            else:
                self._return_from_exile(owner if under_owner else controller, card, owner)

        if when == "now":
            bring_back()
        else:
            fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
            self.at_end_step.append((fire_turn, bring_back))

    def _return_from_exile(self, seat: Seat, card: Card, owner: Seat | None = None) -> None:
        """A card exiled "until" comes back as a new permanent under its owner's control."""
        holder = owner or seat  # the exile zone it is in belongs to its owner, who may not be the one it returns to
        if seat.lost or card not in holder.exile:
            return
        holder.exile.remove(card)
        self.broadcast({"event": "returned_from_exile", "seat": seat.index, "card": card.name})
        self._enter(seat, Permanent(card, sick=True, loyalty=_starting_loyalty(card), owner=holder))

    def exile_graveyard(self, seat: Seat) -> None:
        cards, seat.graveyard = seat.graveyard, []
        self.broadcast({"event": "graveyard_exiled", "seat": seat.index, "cards": [c.name for c in cards]})
        for card in cards:
            self._move_card(seat, card, "exile")
        if cards:
            self._left_graveyard(seat)

    def counter(self, item: StackItem, exile: bool = False) -> None:
        self.stack.remove(item)
        self.broadcast({"event": "countered", "seat": item.controller.index, "card": item.card.name,
                        "ability": _shown(item.ability.text, item.card) if item.ability else None})
        if not item.ability and not item.is_copy:  # countering an ability doesn't touch its source; a copy just ends
            self._move_card(item.controller, item.card, "exile" if exile or item.exile_after else "graveyard")

    def _check_ward(self, item: StackItem) -> None:
        """Whenever a permanent with ward becomes the target of an opponent's spell or ability, a ward trigger
        goes on the stack above it (CR 702.21a)."""
        for target in item.targets:
            if not isinstance(target, Permanent):
                continue
            owner = self.controller_of(target)
            cost = self.ward_of(target)
            if owner is None or owner is item.controller or not cost:
                continue
            ability = TriggeredAbility("ward", (WardCounter(cost),), False, f"Ward {cost}")
            self.stack.append(StackItem(target.card, owner, list(ability.effects), [], ability, target, warding=item))
            self.broadcast({"event": "trigger", "seat": owner.index, "card": target.card.name,
                            "ability": ability.text, "targets": []})

    def ward_of(self, permanent: Permanent) -> str | None:
        """The ward cost the permanent has: its own, or one a static ability gives it ("Creatures you control have ward {1}")."""
        return ward_cost(permanent.card) or next((keyword.removeprefix("ward ") for modifier in self.modifiers(permanent)
                                                  for keyword in modifier.keywords if keyword.startswith("ward ")), None)

    def _ward_payment(self, payer: Seat, fields: dict) -> list[Permanent] | None:
        """The permanents to tap for a ward cost's mana (none if it has no mana), or None if it can't be paid."""
        return self._pay_cost(payer, parse_cost(fields["mana_cost"])) if fields.get("mana_cost") else []

    def can_pay_ward(self, payer: Seat, cost_text: str) -> bool:
        fields = ward_fields(cost_text) or {}
        return (self._ward_payment(payer, fields) is not None
                and payer.life >= fields.get("life", 0) and (not fields.get("discard") or bool(payer.hand))
                and (not fields.get("sacrifice_other")
                     or any(_permanent_matches(fields["sacrifice_other"], p.card) for p in payer.battlefield)))

    def pay_ward(self, payer: Seat, cost_text: str) -> None:
        fields = ward_fields(cost_text) or {}
        self._spend_mana(payer, self._ward_payment(payer, fields) or [])
        if fields.get("life"):
            self.change_life(payer, -fields["life"])
        if fields.get("discard"):
            self.discard(payer, 1)
        if fields.get("sacrifice_other"):
            self.sacrifice(payer, fields["sacrifice_other"])

    def grant_protection_of_choice(self, permanent: Permanent, chooser: Seat) -> None:
        """"... gains protection from the color of your choice until end of turn." """
        source = self.resolving_item.card.name if self.resolving_item else permanent.card.name
        names = list(COLOR_NAMES.values())
        name = names[chooser.player.choose(PROTECTION_PROMPT + source, names)]
        self.modify_until_end_of_turn(permanent, Modifier(0, 0, frozenset({f"protection from {name}"})))

    def resolve_ward(self, cost_text: str) -> None:
        """The spell or ability that targeted a warded permanent is countered unless its controller pays."""
        ward = self.resolving_item
        item = ward.warding if ward else None
        if item is None or item not in self.stack:
            return
        payer = item.controller
        shown = f"Pay {cost_text}" if cost_text.startswith("{") else cost_text
        if self.can_pay_ward(payer, cost_text) and payer.player.choose(WARD_PROMPT + item.card.name,
                                                                       [shown, "Don't pay"]) == 0:
            self.pay_ward(payer, cost_text)
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
        self._searched(seat)

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
        self._searched(seat)

    def reveal_top_land_or_draw(self, seat: Seat, scry: int, tapped: bool) -> None:
        """Scry, then reveal the top card: a land goes onto the battlefield, anything else is drawn."""
        self.scry(seat, scry)
        if not seat.library:
            seat.drew_from_empty = True  # nothing to reveal, so the "otherwise" draw comes up empty
            return
        card = seat.library[0]
        self.broadcast({"event": "revealed", "seat": seat.index, "card": card.name})
        if "Land" in card.type_line:
            seat.library.pop(0)
            self.broadcast({"event": "put_onto_battlefield", "seat": seat.index, "card": card.name, "tapped": tapped})
            self._enter(seat, Permanent(card, tapped=tapped))
        else:
            self.draw(seat, 1)

    def scry(self, seat: Seat, count: int) -> None:
        """Look at the top `count` cards and put any of them on the bottom; the rest stay on top in
        their order. Only the scrying player sees the cards."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        kept, bottom = [], []
        for card in top:
            choice = seat.player.choose(SCRY_PROMPT + card.name, [KEEP_ON_TOP, PUT_ON_BOTTOM])
            (kept if choice == 0 else bottom).append(card)
        seat.library = self._ordered(seat, kept) + seat.library + bottom
        self.broadcast({"event": "scry", "seat": seat.index, "count": len(top)}, skip=seat)
        seat.player.notify({"event": "scry", "seat": seat.index, "count": len(top), "bottom": [c.name for c in bottom]})

    def _ordered(self, seat: Seat, cards: list[Card]) -> list[Card]:
        """Let the player choose the order of the cards they keep on top (first asked goes on top)."""
        cards, ordered = list(cards), []
        while len(cards) > 1:
            ordered.append(cards.pop(seat.player.choose(ORDER_TOP_PROMPT, [c.name for c in cards])))
        return ordered + cards

    def living_weapon(self, equipment: Permanent) -> None:
        """Create a 0/0 black Phyrexian Germ token and attach the Equipment to it."""
        seat = self.controller_of(equipment)
        if seat is None:
            return
        germ = Permanent(GERM, sick=True)
        self.broadcast({"event": "token_created", "seat": seat.index, "card": GERM.name, "type_line": GERM.type_line,
                        "power": GERM.power, "toughness": GERM.toughness})
        self._enter(seat, germ)
        self.attach(equipment, germ)

    def cascade(self, seat: Seat, value: int) -> None:
        """Exile cards from the top of the library until a nonland card that costs less than `value` is exiled; the
        player may cast it for free, and the rest go to the bottom of the library in a random order."""
        passed: list[Card] = []
        found = None
        while seat.library:
            card = seat.library.pop(0)
            if not is_land(card) and card.cmc < value:
                found = card
                break
            passed.append(card)
        self.broadcast({"event": "cascade", "seat": seat.index, "exiled": len(passed) + (found is not None),
                        **({"card": found.name} if found else {})})
        if found is not None:
            seat.exile.append(found)
            if seat.player.choose(CASCADE_PROMPT + found.name, YES_NO) == 0:
                self._cast(seat, found, seat.exile, free=True)
            if found in seat.exile:  # not cast: it goes to the bottom too
                seat.exile.remove(found)
                passed.append(found)
        self.rng.shuffle(passed)
        seat.library += passed

    def _delve_max(self, seat: Seat, card: Card) -> int:
        """Delve: how many cards in the graveyard could help pay for `card` (one for each generic mana)."""
        if not has_keyword(card, "delve"):
            return 0
        cost = parse_cost(card.mana_cost)
        return min(len(seat.graveyard), cost.generic) if cost is not None else 0

    def put_attacking_from_hand(self, seat: Seat, defender: Seat, types: tuple[str, ...]) -> None:
        """Kaalia of the Vast: a creature card of one of `types` from the hand enters tapped and attacking `defender`."""
        options = [c for c in _unique(seat.hand) if "Creature" in c.type_line and any(t in c.type_line for t in types)]
        if not options or self.combat is None:
            return
        card = options[seat.player.choose(PUT_ATTACKING_PROMPT, [c.name for c in options])]
        seat.hand.remove(card)
        entering = Permanent(card, sick=True, tapped=True, loyalty=_starting_loyalty(card))
        self._enter(seat, entering)
        self.combat.add_attacker(entering, seat, defender)
        self.broadcast({"event": "attack", "seat": seat.index, "card": card.name, "defender": defender.index})

    def _add_delayed_mana(self, seat: Seat) -> None:
        """Mana Drain: {C} for the spell it countered arrives at the beginning of your next main phase."""
        if seat.delayed_mana:
            self.add_mana(seat, (frozenset("C"),) * seat.delayed_mana)
            seat.delayed_mana = 0

    def put_on_library_top(self, permanent: Permanent) -> None:
        """Sensei's Divining Top: the permanent goes on top of its owner's library (a token just ceases to exist)."""
        self._leave_together([(permanent, "returned")], destination="library_top")

    def chaos_warp(self, permanent: Permanent) -> None:
        """Its owner shuffles it into their library, reveals the top card and puts it onto the battlefield if it is a
        permanent card (an Aura stays on top: it would have nothing to enchant)."""
        owner = permanent.owner or self.controller_of(permanent)
        self._leave_together([(permanent, "returned")], destination="library")
        self.rng.shuffle(owner.library)
        if not owner.library:
            return
        top = owner.library[0]
        self.broadcast({"event": "revealed", "seat": owner.index, "card": top.name})
        if _is_permanent(top) and not aura_kind(top):
            owner.library.pop(0)
            self._enter(owner, Permanent(top, sick=True, loyalty=_starting_loyalty(top)))

    def _pay_upkeep_costs(self, seat: Seat) -> None:
        """Cumulative upkeep: an age counter, then pay the cost once for each counter or sacrifice the permanent."""
        for permanent in list(seat.battlefield):
            if permanent.echo_pending and (echo := echo_cost(permanent.card)):  # Echo: pay once, or sacrifice it
                permanent.echo_pending = False
                paid = self._pay_cost(seat, parse_cost(echo))
                if paid is not None and seat.player.choose(UPKEEP_PROMPT + permanent.card.name, YES_NO) == 0:
                    self._spend_mana(seat, paid)
                else:
                    self._leave_battlefield(permanent, "sacrificed")
                continue
            base = cumulative_upkeep(permanent.card)
            if not base:
                continue
            permanent.counters["age"] = permanent.counters.get("age", 0) + 1
            cost = parse_cost(base * permanent.counters["age"])
            tapped = self._pay_cost(seat, cost) if cost is not None else None
            if tapped is not None and seat.player.choose(UPKEEP_PROMPT + permanent.card.name, YES_NO) == 0:
                self._spend_mana(seat, tapped)
                self.broadcast({"event": "upkeep_paid", "seat": seat.index, "card": permanent.card.name,
                                "age": permanent.counters["age"]})
            else:
                self._leave_battlefield(permanent, "sacrificed")

    def rearrange_top(self, seat: Seat, count: int, may_shuffle: bool) -> None:
        """Ponder: look at the top `count` cards, put them back in any order, and maybe shuffle the library."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        seat.library = self._ordered(seat, top) + seat.library
        self.broadcast({"event": "looked", "seat": seat.index, "count": len(top)}, skip=seat)
        if may_shuffle and seat.player.choose(SHUFFLE_PROMPT, YES_NO) == 0:
            self.rng.shuffle(seat.library)

    def put_back_from_hand(self, seat: Seat, count: int) -> None:
        """Brainstorm: choose cards from your hand and put them on top of your library in the order you choose."""
        chosen: list[Card] = []
        for _ in range(min(count, len(seat.hand))):
            card = seat.hand[seat.player.choose(PUT_BACK_PROMPT, [c.name for c in seat.hand])]
            seat.hand.remove(card)
            chosen.append(card)
        seat.library = self._ordered(seat, chosen) + seat.library
        self.broadcast({"event": "put_back", "seat": seat.index, "count": len(chosen)})

    def look_at_top(self, seat: Seat, count: int, card_type: str | None) -> None:
        """Look at the top `count` cards: take one into the hand (a card of `card_type` if given, and then
        only if the player wants it); the rest go to the bottom in a random order."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        matches = _unique([c for c in top if card_type is None or _card_matches(card_type, c)])
        taken = None
        if matches:
            options = [c.name for c in matches] + ([NONE_TAKEN] if card_type else [])
            choice = seat.player.choose(LOOK_PROMPT, options)
            if choice < len(matches):
                taken = matches[choice]
                top.remove(taken)
                seat.hand.append(taken)
        self.rng.shuffle(top)
        seat.library += top
        looked = len(top) + (taken is not None)
        self.broadcast({"event": "looked", "seat": seat.index, "count": looked,
                        **({"card": taken.name} if taken and card_type else {})}, skip=seat)
        seat.player.notify({"event": "looked", "seat": seat.index, "count": looked,
                            "card": taken.name if taken else None})

    def add_combat(self, main: bool) -> None:
        """An additional combat phase (and main phase) right after the current phase (CR 500.8)."""
        at = self._plan_index
        if self.step in ("beginning_of_combat", "declare_attackers", "declare_blockers", "first_strike_damage",
                         "combat_damage", "end_of_combat"):
            at = self._plan.index("end_of_combat", at)
        extra = ["beginning_of_combat", "declare_attackers", "declare_blockers", "combat_damage", "end_of_combat"]
        self._plan[at + 1:at + 1] = extra + (["main2"] if main else [])

    def become_monarch(self, seat: Seat) -> None:
        if self.monarch is seat:  # already the monarch: nothing changes, so nothing triggers
            return
        self.monarch = seat
        self.broadcast({"event": "monarch", "seat": seat.index})
        self._trigger_each("become_monarch", seat)
        for opponent in self.opponents(seat):
            self._trigger_each("opponent_become_monarch", opponent, player=seat)

    def pays_unless(self, payer: Seat, cost_text: str, source: Card) -> bool:
        """"... unless that player pays {1}": whether `payer` can and chooses to pay the cost (and pays it)."""
        payment = self._pay_cost(payer, parse_cost(cost_text))
        if payment is None or payer.player.choose(UNLESS_PROMPT + source.name, [f"Pay {cost_text}", "Don't pay"]) != 0:
            return False
        self._spend_mana(payer, payment)
        self.broadcast({"event": "paid_unless", "seat": payer.index, "card": source.name, "cost": cost_text})
        return True

    def take_initiative(self, seat: Seat) -> None:
        """Taking the initiative ventures into the Undercity (CR 725.2); already having it does nothing."""
        if self.initiative is seat:
            return
        self.initiative = seat
        self.broadcast({"event": "initiative", "seat": seat.index})
        self.venture(seat)

    def venture(self, seat: Seat) -> None:
        """Move `seat`'s marker into the next room of the Undercity (the first room if it has none yet); leaving the
        last room completes the dungeon, and the venture starts a fresh one. The room's ability is put on the stack."""
        room = seat.undercity_room
        options = ROOMS[room].leads_to if room else (START,)
        if not options:
            self.broadcast({"event": "dungeon_completed", "seat": seat.index, "dungeon": "Undercity"})
            options = (START,)
        entered = options[seat.player.choose(VENTURE_PROMPT, list(options))] if len(options) > 1 else options[0]
        seat.undercity_room = entered
        self.broadcast({"event": "venture", "seat": seat.index, "room": entered})
        effects = (ThroneOfTheDeadThree(),) if entered == "Throne of the Dead Three" else tuple(line_effects(ROOMS[entered].text))
        ability = TriggeredAbility("venture", effects, False, ROOMS[entered].text)
        self.pending.append(PendingTrigger(ability, None, seat, card=Card(name=entered, type_line="Dungeon Room")))

    def throne_of_the_dead_three(self, seat: Seat) -> None:
        """Reveal the top ten cards; a creature among them enters with three +1/+1 counters and hexproof until
        the controller's next turn; the library is shuffled."""
        top = seat.library[:10]
        self.broadcast({"event": "revealed", "seat": seat.index, "cards": [c.name for c in top]})
        creatures = _unique([c for c in top if "Creature" in c.type_line])
        if creatures:
            card = creatures[seat.player.choose(THRONE_PROMPT, [c.name for c in creatures])]
            seat.library.remove(card)
            permanent = Permanent(card, sick=True)
            self._enter(seat, permanent)
            self.put_counters(permanent, "+1/+1", 3)
            permanent.until_next_turn.append(Modifier(0, 0, frozenset({"hexproof"})))
        self.rng.shuffle(seat.library)

    def vote(self, starter: Seat, options: list[str]) -> list[int]:
        """Each player votes, starting with `starter` and going in turn order; the votes are public. Returns the
        number of votes for each option."""
        source = self.resolving_item.card.name if self.resolving_item else ""
        counts = [0] * len(options)
        for seat in self._turn_order(starter.index):
            if seat.lost:
                continue
            for _ in range(1 + sum(extra_votes(p.card) for p in seat.battlefield)):  # "you may vote an additional time"
                choice = seat.player.choose(VOTE_PROMPT + source, options)
                counts[choice] += 1
                self.broadcast({"event": "vote", "seat": seat.index, "choice": options[choice]})
        return counts

    def vote_to_exile(self, starter: Seat) -> None:
        """Council's Judgment: each player votes for a nonland permanent `starter` doesn't control; each permanent
        with the most votes, or tied for the most, is exiled."""
        voted = [p for seat in self.opponents(starter) for p in seat.battlefield if not is_land(p.card)]
        if not voted:
            return
        counts = self.vote(starter, [self.label(p) for p in voted])
        for permanent, count in zip(voted, counts):
            if count == max(counts) and self.on_battlefield(permanent):
                self.exile(permanent)

    def goad(self, permanent: Permanent, goader: Seat) -> None:
        permanent.goaded_by = goader
        self.broadcast({"event": "goaded", "card": permanent.card.name, "by": goader.index})

    def surveil(self, seat: Seat, count: int) -> None:
        """Look at the top `count` cards and put any of them into the graveyard (which everyone sees)."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        kept, binned = [], []
        for card in top:
            choice = seat.player.choose(SURVEIL_PROMPT + card.name, [KEEP_ON_TOP, PUT_IN_GRAVEYARD])
            (kept if choice == 0 else binned).append(card)
        seat.library = self._ordered(seat, kept) + seat.library
        self.broadcast({"event": "surveil", "seat": seat.index, "count": len(top), "graveyard": [c.name for c in binned]})
        for card in binned:
            self._move_card(seat, card, "graveyard")

    def may_loot(self, seat: Seat) -> None:
        """ "You may discard a card. If you do, draw a card." """
        if seat.hand and seat.player.choose(LOOT_PROMPT, YES_NO) == 0:
            self.discard(seat, 1)
            self.draw(seat, 1)

    def may_wheel(self, count: int) -> None:
        """ "Each player may discard their hand and draw seven cards." """
        for seat in self.turn_order_from_active():
            if seat.player.choose(WHEEL_PROMPT, YES_NO) == 0:
                self.discard(seat, None)
                self.draw(seat, count)

    def tap_or_untap(self, seat: Seat, target: Permanent) -> None:
        pick = seat.player.choose(TAP_OR_UNTAP_PROMPT + target.card.name, ["Tap", "Untap", "Neither"])
        if pick < 2:
            target.tapped = pick == 0

    def discard(self, seat: Seat, count: int | None, random: bool = False) -> None:
        """Discard `count` cards (the whole hand if None); the player chooses which unless it says "at random"."""
        for _ in range(len(seat.hand) if count is None else min(count, len(seat.hand))):
            if count is None:
                card = seat.hand.pop(0)  # all of them go, so there is nothing to choose
            elif random:
                card = seat.hand.pop(self.rng.randrange(len(seat.hand)))
            else:
                card = seat.hand.pop(seat.player.choose(DISCARD_CARD_PROMPT, [c.name for c in seat.hand]))
            self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
            self._move_card(seat, card, "graveyard")
            self._discarded(seat)

    def reveal_and_discard(self, chooser: Seat, victim: Seat, excluded: tuple[str, ...], max_mv: int | None) -> None:
        """Thoughtseize: `victim` reveals their hand and `chooser` picks a card from it that isn't one of the
        `excluded` types (and costs at most `max_mv`); the victim discards it."""
        self.broadcast({"event": "revealed_hand", "seat": victim.index, "cards": [c.name for c in victim.hand]})
        eligible = _unique([c for c in victim.hand if not any(t.capitalize() in c.type_line for t in excluded)
                            and (max_mv is None or c.cmc <= max_mv)])
        if not eligible:
            return
        card = eligible[chooser.player.choose(CHOOSE_DISCARD_PROMPT, [c.name for c in eligible])]
        victim.hand.remove(card)
        self.broadcast({"event": "discard", "seat": victim.index, "card": card.name})
        self._move_card(victim, card, "graveyard")
        self._discarded(victim)

    def mill(self, seat: Seat, count: int) -> None:
        """Put the top `count` cards of the library into the graveyard (fewer if there aren't that many)."""
        milled = [seat.library.pop(0) for _ in range(min(count, len(seat.library)))]
        self.broadcast({"event": "milled", "seat": seat.index, "cards": [c.name for c in milled]})
        for card in milled:
            self._move_card(seat, card, "graveyard")

    # --- helpers -------------------------------------------------------------

    def _enter(self, seat: Seat, permanent: Permanent, x: int = 0) -> None:
        if clone := clone_kind(permanent.card):  # "You may have it enter as a copy of ...": decided as it enters
            self._become_copy(seat, permanent, *clone)
        for counter, count in enters_with_counters(permanent.card, permanent.kicked).items():  # CR 614.1c: it arrives with them
            number = self._counters_to_add(seat, permanent.card, counter, x if count == "X" else count)
            permanent.counters[counter] = permanent.counters.get(counter, 0) + number
        permanent.owner = permanent.owner or seat
        if enters_prepared(permanent.card):
            permanent.prepared = True
        if echo_cost(permanent.card):
            permanent.echo_pending = True
        rule = enters_tapped_rule(permanent.card)
        if rule and self._enters_tapped(seat, rule, permanent.card):
            permanent.tapped = True
        if saga_chapters(permanent.card):  # a Saga arrives with a lore counter, which triggers chapter I
            permanent.counters["lore"] = permanent.counters.get("lore", 0) + 1
        seat.battlefield.append(permanent)
        self.trigger("enters", permanent, seat)
        if saga_chapters(permanent.card):
            self.trigger(f"chapter_{permanent.counters['lore']}", permanent, seat)
        self._observe("permanent_enters", permanent.card, seat, subject=permanent)

    def prepare(self, permanent: Permanent) -> None:
        """A creature with a prepare spell becomes prepared (nothing happens if it already is)."""
        if self.on_battlefield(permanent) and permanent.card.prepare and not permanent.prepared:
            permanent.prepared = True
            self.broadcast({"event": "prepared", "card": permanent.card.name})

    def unprepare(self, permanent: Permanent) -> None:
        if permanent.prepared:
            permanent.prepared = False
            self.broadcast({"event": "unprepared", "card": permanent.card.name})

    def _become_copy(self, seat: Seat, permanent: Permanent, kind: str, yours: bool) -> None:
        """Clone: choose a permanent on the battlefield and enter as a copy of it. A copy gets the other card's
        printed characteristics (not its counters, damage or changes); a token's copy isn't a token."""
        options = [p for s in self.live_seats() if not yours or s is seat for p in s.battlefield
                   if _permanent_matches(kind, p.card)]
        if not options:
            return
        pick = seat.player.choose(CLONE_PROMPT + permanent.card.name, [self.label(p) for p in options] + [NOT_A_COPY])
        if pick == len(options):
            return
        copied = options[pick].card
        permanent.real_card = permanent.card
        permanent.card = dataclasses.replace(copied, type_line=copied.type_line.removeprefix("Token "))
        self.broadcast({"event": "copied_permanent", "seat": seat.index, "card": permanent.real_card.name,
                        "as": permanent.card.name})

    def copy_spell(self, item: StackItem, controller: Seat, new_targets: bool = False) -> None:
        """Put a copy of a spell on the stack under `controller`'s control; it resolves first. It isn't cast, and it
        stops existing instead of going to the graveyard. With `new_targets` the copy's controller chooses its
        targets again (the old ones are still legal choices)."""
        if item not in self.stack or item.ability:
            return
        targets = list(item.targets)
        if new_targets and (chosen := self._choose_targets(controller, item.effects, item.card.name,
                                                           colors=source_qualities(item.card))):
            targets = chosen[0]
        self.stack.append(StackItem(item.card, controller, item.effects, targets, x=item.x, kicked=item.kicked,
                                    kickers=item.kickers, is_copy=True))
        self.broadcast({"event": "copied_spell", "seat": controller.index, "card": item.card.name})
        self._observe("copy", item.card, controller)

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
        if rule.kind == "unless_basic_lands":
            return sum(1 for p in seat.battlefield if "Basic" in p.card.type_line and is_land(p.card)) < rule.count
        if rule.kind == "unless_land_type_count":
            return sum(1 for p in seat.battlefield if rule.types[0] in p.card.type_line) < rule.count
        if rule.kind == "unless_opponent_lands":
            return sum(1 for o in self.opponents(seat) for p in o.battlefield if is_land(p.card)) < rule.count
        if rule.kind == "reveal":  # a Snarl: show a matching card from your hand or enter tapped
            matching = [c for c in seat.hand if any(t in c.type_line for t in rule.types)]
            if matching and seat.player.choose(REVEAL_PROMPT + card.name, [f"Reveal {matching[0].name}", "Enter tapped"]) == 0:
                self.broadcast({"event": "revealed", "seat": seat.index, "card": matching[0].name})
                return False
            return True
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
        left = {id(permanent) for permanent, _ in leaving}  # an attacker that leaves is removed from combat
        self.combat.attacks = [a for a in self.combat.attacks if id(a.attacker) not in left]
        gone = [(permanent, permanent.last_controller) for permanent, _ in leaving]
        for permanent, reason in leaving:
            self.broadcast({"event": reason, "seat": permanent.last_controller.index, "card": permanent.card.name})
        # Sacrifice triggers look back in time, so what was sacrificed sees itself go.
        everyone = [(p, s) for s in self.live_seats() for p in s.battlefield] + gone
        for permanent, reason in leaving:
            if reason != "sacrificed":
                continue
            controller = permanent.last_controller
            for watcher, watcher_seat in everyone:
                if watcher_seat is controller and "Creature" in permanent.card.type_line:
                    self.trigger("sacrifice_creature", watcher, controller)
                if watcher_seat is not controller and "Creature" in permanent.card.type_line:
                    self.trigger("opponent_sacrifice_creature", watcher, watcher_seat, player=controller)
                self.trigger("any_sacrifice", watcher, watcher_seat)
                if watcher is not permanent:
                    self.trigger("other_sacrifice", watcher, watcher_seat)
        for permanent, _ in leaving:
            controller = permanent.last_controller
            if destination == "graveyard" and not _is_token(permanent.card):  # Rancor: "put into a graveyard from the battlefield"
                self.trigger("put_into_graveyard", permanent, controller)
            if destination == "graveyard" and "Creature" in permanent.card.type_line:
                if self.deaths_turn != self.turn:
                    self.deaths_turn, self.deaths_count = self.turn, 0
                self.deaths_count += 1
                self.trigger("dies", permanent, controller)
                for attachment, attachment_seat in everyone:  # "When enchanted creature dies"
                    if attachment.attached_to is permanent:
                        self.trigger("host_dies", attachment, attachment_seat, subject=permanent)
                self._observe("creature_dies", permanent.card, controller, subject=permanent, extra=gone)
            self._observe("permanent_leaves", permanent.card, controller, subject=permanent, extra=gone)
            if permanent.real_card is not None:  # a Clone goes to the graveyard as itself
                permanent.card, permanent.real_card = permanent.real_card, None
            if permanent.reconfigured is not None:  # an attached Equipment creature goes back to being just a card
                permanent.card, permanent.reconfigured = permanent.reconfigured, None
            if permanent.original is not None:  # a crewed Vehicle goes back to being just a card
                permanent.card, permanent.original = permanent.original, None
            if not _is_token(permanent.card):  # tokens stop existing once they leave (CR 111.7)
                self._move_card(permanent.owner or controller, permanent.card, destination)
        for permanent, _ in leaving:  # Animate Dead leaves: "that creature's controller sacrifices it"
            host = permanent.attached_to
            if reanimation_aura(permanent.card) is not None and host is not None and self.on_battlefield(host):
                self._leave_battlefield(host, "sacrificed")
        for permanent, _ in leaving:  # whatever they were holding in exile comes back
            held, permanent.linked_exile = permanent.linked_exile, []
            for seat, card in held:
                self._return_from_exile(seat, card)

    def _exiled_instead(self, owner: Seat) -> bool:
        """Whether a card of `owner`'s going to the graveyard is exiled instead (Rest in Peace, Leyline of the Void)."""
        for seat in self.live_seats():
            for permanent in seat.battlefield:
                kind = replacement_effects(permanent.card).graveyard
                if kind == "any" or (kind == "opponent" and owner is not seat):
                    return True
        return False

    def exile_all_graveyards(self) -> None:
        for seat in self.live_seats():
            cards, seat.graveyard = seat.graveyard, []
            for card in cards:
                self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": "exile"})
                self._move_card(seat, card, "exile")
            if cards:
                self._left_graveyard(seat)

    def _factor(self, seat: Seat, attribute: str) -> int:
        """How many times as many tokens or counters `seat`'s replacement effects make (Doubling Season stacks)."""
        factor = 1
        for permanent in seat.battlefield:
            factor *= getattr(replacement_effects(permanent.card), attribute)
        return factor

    def _counters_to_add(self, seat: Seat, card: Card, counter: str, count: int) -> int:
        """Counters going onto a permanent `seat` controls: +1/+1 counters get Hardened Scales' extra one first,
        then Doubling Season doubles."""
        if counter == "+1/+1" and "Creature" in card.type_line:
            count += sum(replacement_effects(p.card).plus_one for p in seat.battlefield)
        return count * self._factor(seat, "counters")

    def _trigger_times(self, controller: Seat, event: str, entering: Card | None) -> int:
        """How many times an ability of `controller`'s triggers: once, plus once more for each Panharmonicon when an
        artifact or creature (or any permanent, for Yarok) is entering the battlefield."""
        if event not in ("enters", "permanent_enters") or entering is None:
            return 1
        extra = 0
        for permanent in controller.battlefield:
            kind = replacement_effects(permanent.card).extra_trigger
            if kind == "permanent" or (kind == "artifact or creature"
                                       and ("Artifact" in entering.type_line or "Creature" in entering.type_line)):
                extra += 1
        return 1 + extra

    def _move_card(self, seat: Seat, card: Card, zone: str) -> None:
        """Put a card into its owner's graveyard, exile or hand; a commander may go to the
        command zone instead (CR 903.9). Rest in Peace and its kind send a card to exile instead of a graveyard."""
        if zone == "graveyard" and self._exiled_instead(seat):
            zone = "exile"
        if card.name in seat.commander_names:
            if seat.player.choose(COMMAND_ZONE_PROMPT, ["Command zone", zone.capitalize()]) == 0:
                seat.command_zone.append(card)
                self.broadcast({"event": "to_command_zone", "seat": seat.index, "card": card.name})
                return
        if zone == "library_top":
            seat.library.insert(0, card)
            return
        {"exile": seat.exile, "hand": seat.hand, "graveyard": seat.graveyard, "library": seat.library}[zone].append(card)

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
                    if self.monarch is seat:  # CR 724.4: the active player takes it, if they're still in
                        self.monarch = None
                        if not self.seats[self.active].lost:
                            self.become_monarch(self.seats[self.active])
                    if self.initiative is seat:  # CR 725.4: the active player takes it, if they're still in
                        self.initiative = None
                        if not self.seats[self.active].lost:
                            self.take_initiative(self.seats[self.active])
                    changed = True
            dying: list[tuple[Permanent, str]] = []
            for seat in self.live_seats():
                for permanent in list(seat.battlefield):
                    counters = permanent.counters
                    cancel = min(counters.get(PLUS, 0), counters.get(MINUS, 0))
                    if cancel:  # CR 704.5q
                        counters[PLUS] -= cancel
                        counters[MINUS] -= cancel
                    holder = permanent.control_aura  # Control Magic let go of it: it goes back
                    if holder is not None and (not self.on_battlefield(holder) or holder.attached_to is not permanent):
                        self._return_control(permanent)
                        changed = True
                    host = permanent.attached_to
                    if host is not None and aura_controls(permanent.card) and self.on_battlefield(host) \
                            and self.controller_of(host) is not seat:  # Control Magic takes control of its creature
                        self.gain_control(host, seat, aura=permanent)
                        changed = True
                    if host is not None and (not self.on_battlefield(host)
                                             or self.protected_from(host, source_qualities(permanent.card))):
                        self.detach(permanent)  # CR 704.5n: Equipment stays, unattached
                        host = None
                    if "Aura" in permanent.card.type_line and host is None:
                        dying.append((permanent, "unattached"))  # CR 704.5m
                        continue
                    chapters = saga_chapters(permanent.card)
                    if (chapters and permanent.counters.get("lore", 0) >= max(chapters)
                            and not self._chapter_pending(permanent)):  # CR 714.4: done once the last chapter has resolved
                        dying.append((permanent, "saga_done"))
                        continue
                    current = self.toughness(permanent)
                    creature = current is not None
                    if (creature and current <= 0) or (permanent.loyalty is not None and permanent.loyalty <= 0):
                        dying.append((permanent, "died"))
                    elif (creature and (permanent.damage >= current or permanent.deathtouched)
                          and not self.has_keyword(permanent, "indestructible")):
                        if not self._regenerated(permanent):
                            dying.append((permanent, "destroyed"))
            if dying:  # all at once (CR 704.3)
                self._leave_together(dying)
                changed = True
            if not changed:
                return

    def _chapter_pending(self, saga: Permanent) -> bool:
        """Whether a chapter ability of `saga` is waiting to go on the stack or is on it."""
        return any(i.source is saga for i in self.stack) or any(t.permanent is saga for t in self.pending)

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


def _has_type(card: Card, kind: str) -> bool:
    """Whether a card has a type or subtype: "creature", "Plains", "Snake"."""
    return kind.lower() in card.type_line.lower().replace("—", " ").split()


def _watch_type_matches(kind: str, card: Card) -> bool:
    """Whether `card` is what a watch looks for: "creature", "land", ..., or for casts
    "spell", "creature spell", "noncreature spell", "instant or sorcery spell", "red spell",
    "historic spell", "aura, equipment, or vehicle spell", ..."""
    if kind == "spell with {x} in its mana cost":
        return "{X}" in card.mana_cost
    kind = kind.removesuffix(" spell").removesuffix("spell").strip()
    if not kind:
        return True
    if kind == "token" or kind.endswith(" token"):  # "token", "creature token"
        return _is_token(card) and (kind == "token" or _watch_type_matches(kind.removesuffix(" token"), card))
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
    if subtypes == ("*",):  # "a land card"
        return True
    if subtypes == ("nonbasic",):  # "a nonbasic land card"
        return "Basic" not in card.type_line
    return any(sub in card.type_line for sub in subtypes)


def _starting_loyalty(card: Card) -> int | None:
    return int(card.loyalty) if card.loyalty and card.loyalty.isdigit() else None


def _card_matches(kind: str, card: Card) -> bool:
    """Whether a card in a library or graveyard is of `kind`: "card", "permanent", "creature",
    "instant or sorcery", "basic land", ..."""
    kind, _, value = kind.partition("|")  # "creature|mv<=3": with a mana value of 3 or less
    if value:
        number = int(value.lstrip("mv<>="))
        mana_value = card.cmc
        if not ((value.startswith("mv<=") and mana_value <= number) or (value.startswith("mv>=") and mana_value >= number)
                or (value.startswith("mv=") and mana_value == number)):
            return False
    if kind == "card":
        return True
    if kind == "permanent":
        return _is_permanent(card)
    if kind == "basic land":
        return "Basic" in card.type_line and "Land" in card.type_line
    if kind == "nonbasic land":
        return "Basic" not in card.type_line and "Land" in card.type_line
    if kind.startswith("legendary"):  # "legendary creature": legendary, and the rest of the kind
        return "Legendary" in card.type_line and _card_matches(kind.removeprefix("legendary").strip() or "card", card)
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
    if m := re.fullmatch(r"non(white|blue|black|red|green|artifact) (.+)", kind):  # "nonblack creature"
        has = "Artifact" in card.type_line if m[1] == "artifact" else {
            "white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}[m[1]] in card.colors
        return not has and _permanent_matches(m[2], card)
    if kind == "any":
        return "Creature" in card.type_line or "Planeswalker" in card.type_line
    if kind == "permanent":
        return True
    if kind == "nonland permanent":
        return not is_land(card)
    if kind == "nonbasic land":
        return "Land" in card.type_line and "Basic" not in card.type_line
    if kind.endswith(" token"):  # "creature token"
        return _is_token(card) and _permanent_matches(kind.removesuffix(" token"), card)
    if kind.startswith("nontoken "):
        return not _is_token(card) and _permanent_matches(kind.removeprefix("nontoken "), card)
    return any(t.capitalize() in card.type_line for t in kind.split(" or ") if t != "player")


def _take(cards: list[Card], name: str) -> Card:
    card = next(c for c in cards if c.name == name)
    cards.remove(card)
    return card


def _take_face(cards: list[Card], name: str) -> Card:
    """The card named `name` leaves the list; if it is the back face of a double-faced card, that face comes out."""
    card = next(c for c in cards if c.name == name or (c.back and c.back.name == name))
    cards.remove(card)
    return card.back if card.back and card.back.name == name else card


def _unique(cards: list[Card]) -> list[Card]:
    return list({c.name: c for c in cards}.values())
