"""Commander game: setup, mulligans and the turn/priority loop.

Players act only through the Player protocol, so TCP and local players are
interchangeable. Actions so far: play a land, cast a spell (including your
commander, with commander tax), and pass priority. Mana comes from lands and
from permanents with simple mana abilities. Spells use the stack; instants and
sorceries do what effects.py understands of their rules text, and permanents'
other rules text is not implemented yet.
"""

from __future__ import annotations

import contextlib
import dataclasses
import random
import re
from itertools import combinations, permutations
from dataclasses import dataclass, field
from typing import Any, Callable

from .analysis import is_land
from .cards import Card, Deck, has_keyword, shown_type_line
from . import characteristics
from .characteristics import LOSES_HEXPROOF, MINUS, PLUS, Modifier, source_qualities
from .combat import Attack, Combat
from .effects import (CANT_ATTACK, CANT_BLOCK, LOSES_ALL, NO_UNTAP, PROTECTION_CHOSEN, Cascade, ActivatedAbility, AlternativeCost, AttachAura, Draw, GainLife, EntersTapped, GiveBack, Modal,
                      Amount, Condition, GraveyardCast, MassFilter, TriggeredAbility, WardCounter,
                      replacement_effects, clone_kind, temporary_clone_keyword, is_class, class_view, keeps_its_protection_aura, copies_per_sacrifice, graveyard_statics, non_hand_cost_reduction, aura_controls, saga_chapters, entwine_cost, buyback_cost, buyback_other_cost, escalate_cost, granted_abilities, granted_mana, group_mana_grants, with_granted_mana, additional_land_mana, untaps_in_other_untap_steps, suspend_of, counter_mana, x_spell_discount, clone_extra_counters, makes_mana_by_power, chooses_creature_type, annihilator_of, toxic_of, PayToReturnSelf, ReturnThisFromGraveyard, Demonstrate, Backup, encore_cost, unearth_cost, madness_cost, bestow_aura, line_effects, ThroneOfTheDeadThree, activated_abilities, additional_costs, x_limited_by_players, alternative_costs, cost_reductions, cycling, hand_abilities, strive_cost, chooses_color, color_choice_excludes, chosen_color_mana, counter_removal_mana, may_skip_untap, is_multikicker, kicked_effects, kicker_costs, kicker_other_cost, attached_abilities, aura_kind, enters_tapped_rule, reconfigure_cost, reflected_mana, mana_ability_needs_no_tap,
                      affinity_for, cumulative_upkeep, devour, echo_cost, reanimation_aura, replicate_cost, storm_kind, CopySpellTimes, enters_prepared, enters_with_counters, extra_votes, graveyard_casts, graveyard_permission, CastExiledCopy, mana_condition, mana_per_count, mana_threshold,
                      no_max_hand_size, begins_on_battlefield, hand_size_counter, power_toughness_amount, players_have_no_max_hand,
                      overloaded_effects, SacrificeSelf,
                      self_cost_reduction, conditional_cost_reduction, reduced_by_total_power, granted_affinity, is_identity_mana_land, land_mana_units, mana_life_cost, mana_life_types, mana_pain, printed_protection, protection_tokens, ward_cost, ward_fields,
                      filter_mana_ability, follows_target, mana_ability, mana_extra_cost, mana_restriction, charge_mana, mana_ability_sacrifices, mana_spent_trigger, has_next_x_rider, Scry, spell_effects, static_abilities, target_kind,
                      triggered_abilities, uses_player, uses_source, uses_subject)
from .undercity import ROOMS, START
from .mana import GENERIC_ONLY, SNOW, Cost, parse_cost, pay
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
ENCORE = "Encore: "  # followed by the card's name
UNEARTH = "Unearth: "  # followed by the card's name
SUSPEND = "Suspend: "  # followed by the card's name
CAST_PARAGON = "Cast from graveyard (once a turn): "  # Serra Paragon
PLAY_PARAGON = "Play land from graveyard: "
CAST_EXILE = "Cast from exile: "  # a card exiled "you may play it this turn"
CAST_PREPARED = "Cast prepared: "  # a copy of a prepared creature's spell
PLAY_EXILE = "Play land from exile: "
CYCLE = "Cycle: "
ACTIVATE_HAND = "Activate from hand: "  # followed by the card's name: "{U/R}{U/R}, Discard this card: ..." (Magma Opus)
ACTIVATE_GRAVEYARD = "Activate from graveyard: "  # followed by the card's name: "{B}{G}: Return this card from your graveyard to the battlefield tapped."
REVEAL_PROMPT = "Reveal a card from your hand for "  # followed by the land's name
SHOCK_PROMPT = "Pay life so it enters untapped? "  # followed by the land's name
ACTIVATE = "Activate: "  # followed by "<permanent label>: <ability text>"
COMMANDER_TAX = 2  # CR 903.8
PERMANENT_TYPES = ("Artifact", "Battle", "Creature", "Enchantment", "Land", "Planeswalker")
KEEP_PROMPT = "Keep this hand?"
OPENING_PROMPT = "Begin the game with this on the battlefield: "  # followed by the card's name
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
SPLIT_HAND_PROMPT = "Put which card into your hand? "
SPLIT_BOTTOM_PROMPT = "Put which card on the bottom of your library? "
DANCE_PROMPT = "Exile the top card of your library? "  # followed by "(N exiled, total mana value M)"; Yes or No
DANCE_CAST_PROMPT = "Cast for free: "  # followed by the card's name; Yes or No
TURN_UP = "Turn face up: "  # followed by the manifested creature's label
PUT_FROM_HAND_PROMPT = "Put a card from your hand onto the battlefield: "
RETURN_CHOSEN_PROMPT = "Return which card from your graveyard? "
DECLINE = "Don't"
CHOOSE_COLOR_PROMPT = "Choose a color for "  # followed by the card's name; white, blue, black, red, green
KAROO_PROMPT = "Return a land or sacrifice "  # followed by the card's name; the last option is SACRIFICE_IT
SACRIFICE_IT = "Sacrifice it"
CHOOSE_TYPE_PROMPT = "Choose a creature type for "  # followed by the card's name; options are the types, most common first
_PRIMES = frozenset({2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97})
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
MADNESS_PROMPT = "Cast it for its madness cost: "  # followed by the card's name; options: YES_NO
BUYBACK_PROMPT = "Pay the buyback cost for "  # followed by the spell's name; options: YES_NO
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
PUT_ATTACHMENT_PROMPT = "Put an Aura or Equipment onto the battlefield"  # options are card names, then NONE_TAKEN
EQUIP_PROMPT = "Attach it to which creature? "  # followed by the Equipment's name; the last option leaves it unattached
CAST_FREE_PROMPT = "Cast an Aura spell from among the exiled cards without paying its mana cost"  # then NONE_TAKEN
PUT_PERMANENT_PROMPT = "Put a nonland permanent card onto the battlefield"  # then NONE_TAKEN to stop
SET_ASIDE_PROMPT = "Choose a nonland card exiled this way; it can't be cast"
CAST_FREE_EXILED_PROMPT = "Cast a spell from among the other exiled cards without paying its mana cost"  # then NONE_TAKEN
CHOOSE_EXILED_WITH_PROMPT = "Choose a card exiled with this permanent"
SACRIFICE_COPIES_PROMPT = "Sacrifice how many creatures to copy "  # followed by the spell's name; options are "0", "1", ...
LOOK_PROMPT = "Take a card from the top of your library"  # options are card names, then NONE_TAKEN if optional
NONE_TAKEN = "Take none"
PUT_CREATURE_PROMPT = "Put a creature card from your hand onto the battlefield"  # options are card names, then NONE_TAKEN
RETURN_CARD_PROMPT = "Return which card from your graveyard: "  # followed by the kind of card; options are card names
KEEP_ON_TOP, PUT_ON_BOTTOM, PUT_IN_GRAVEYARD = "Keep on top", "Put on the bottom", "Put into your graveyard"
MAX_TARGETS = 30  # a bound on "any number of target ..."
MAX_X = 30  # stop looking for a bigger affordable X here
MAX_LIFE_MANA = 10  # Channel: how many life-paid {C} the payer offers at once
YES_NO = ["Yes", "No"]
LIFE_X_PROMPT = "Pay how much life (X) for "  # followed by the spell's name; options are the numbers
REMOVE_COUNTER_PROMPT = "Remove a counter to draw a card? "  # followed by the permanent's name
ATTACH_PROMPT = "Attach it to the new token? "  # followed by the Aura's name
MAY_PAY_PROMPT = "Pay the cost for "  # followed by the source's name; options are "Pay <cost>" and "Don't pay"
DRAW_UP_TO_PROMPT = "How many cards do you draw? "
SACRIFICE_DRAW_PROMPT = "Sacrifice a permanent to draw cards? "
LOOT_PROMPT = "Discard a card to draw a card? "
PUT_ATTACKING_PROMPT = "Put which creature card onto the battlefield attacking? "
SHUFFLE_PROMPT = "Shuffle your library? "
DEVOUR_PROMPT = "Devour: sacrifice which creature to "  # followed by the creature's name; the last option is DEVOUR_DONE
DEVOUR_DONE = "Done"
REPLICATE_PROMPT = "Choose how many times to replicate "  # followed by the spell's name; options are "0", "1", ...
PILE_PROMPT = "Put which pile into the graveyard? "  # an opponent chooses; the options are the piles
PILE_CAST_PROMPT = "Cast a spell from the pile for free? "  # the options are the cards, then "None"
CASCADE_PROMPT = "Cast for free (cascade): "  # followed by the card's name; Yes or No
DELVE_PROMPT = "Exile which card from your graveyard to pay for "  # followed by the spell's name
UPKEEP_PROMPT = "Pay the cumulative upkeep of "  # followed by the permanent's name; Yes or No (No sacrifices it)
PUT_BACK_PROMPT = "Put which card from your hand on top of your library? "
WHEEL_PROMPT = "Discard your hand and draw a new hand? "
HIDEAWAY_PROMPT = "Hide away a card for "  # followed by the permanent's name; options: the top cards
HIDEAWAY_PLAY_PROMPT = "Play the hidden card for free: "  # followed by its name; options: "Play it", "Don't"
UNTAP_PROMPT = "Untap during your untap step: "  # followed by the permanent's name; options: "Untap", "Leave tapped"
TAP_OR_UNTAP_PROMPT = "Tap or untap "  # followed by the creature's name
COMMANDER_DAMAGE_LIMIT = 21  # CR 903.10a
POISON_LIMIT = 10  # CR 704.5c


@dataclass(eq=False)
class Permanent:
    card: Card
    tapped: bool = False
    sick: bool = False  # entered since its controller's last untap step
    entered_turn: int | None = None  # the turn it came onto the battlefield ("that entered this turn")
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
    last_auras: dict[int, int] = field(default_factory=dict)  # when it died: how many Auras each seat (by index) had on it
    last_power: int = 0  # its power just before it left (CR 608.2h: last known information)
    owner: "Seat | None" = None  # whose card it is; None means its controller (the usual case)
    attached_to: "Permanent | None" = None  # the permanent this Equipment or Aura is attached to
    linked_exile: list = field(default_factory=list)  # (owner seat, card) exiled "until this leaves the battlefield"
    exiled_with: list = field(default_factory=list)  # (owner seat, card) this permanent's abilities exiled for good
    kicked: int = 0  # how many times its kicker cost was paid when it was cast
    kickers: tuple[str, ...] = ()  # the mana kicker costs paid, once per payment
    regeneration: int = 0  # regeneration shields, which last until end of turn
    real_card: "Card | None" = None  # a Clone's own card, while it is a copy of something else; a Class's whole card
    level: int = 1  # a Class's level
    extra_counters: int = 0  # +1/+1 counters it enters with besides its own (Opal Palace's rider)
    control_origin: "Seat | None" = None  # who controlled it before a control-change effect took it
    control_aura: "Permanent | None" = None  # the Aura (Control Magic) that holds control of it
    control_eot: bool = False  # control changes back at end of turn (Threaten)
    original: "Card | None" = None  # a crewed Vehicle's real card, while it is an artifact creature
    reconfigured: "Card | None" = None  # an Equipment creature's real card, while it is attached (and not a creature)
    attacked_turn: int | None = None  # the last turn it attacked
    vow_of: "Seat | None" = None  # Promise of Loyalty: while it has a vow counter it can't attack this player
    escaped: bool = False  # cast with escape: "escapes with two +1/+1 counters on it" (Woe Strider)
    chosen_type: str | None = None  # "As this enters, choose a creature type." (Patchwork Banner)
    chosen_color: str | None = None  # "As this enters, choose a color." (a color letter)
    manifested: bool = False  # a face-down 2/2 whose real card is `real_card`; a creature card can be turned face up
    bestowed_from: "Card | None" = None  # a bestowed Aura: the creature card it goes back to when its creature leaves
    must_attack: "Seat | None" = None  # an Encore token: it attacks this player this turn if able
    goaded_by: "Seat | None" = None  # until that player's next turn it must attack, and not them if possible
    prepared: bool = False  # a prepare creature whose controller may cast a copy of its spell
    echo_pending: bool = False  # its echo cost is due at its controller's next upkeep
    stored: int = 0  # a number it remembers (the life Soulgorger Orgg's controller lost)
    goad_forever: "Seat | None" = None  # goaded for the rest of the game by this player (Life of the Party's copies)
    unearthed: bool = False  # brought back with unearth: exiled instead of going anywhere else, and at the next end step
    paragon_life: tuple["Seat", int] | None = None  # played with Serra Paragon: (who gains life, how much) when it goes to the graveyard


@dataclass(frozen=True)
class ManaSource:
    """One mana a permanent can make when tapped, and whether making it hurts (painlands, Talismans)."""
    permanent: "Permanent | None"  # None: mana already in the pool
    types: frozenset[str]  # one mana of one of these types
    pain: frozenset[str] = frozenset()  # types that deal `damage` to the controller when produced
    damage: int = 0
    life: bool = False  # the `damage` is life paid (Mana Confluence), not damage dealt
    restriction: str | None = None  # what the mana may be spent on (see effects.mana_restriction)
    counter: str | None = None  # the counter removed from the permanent when this mana is used (Vivid and depletion lands)
    counter_free: frozenset[str] = frozenset()  # ... unless it pays for one of these types (the Vivid land's own color)
    counter_each: bool = False  # one counter comes off for each of this permanent's mana that is used (the storage lands)


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
    filters: tuple["Permanent", ...] = ()  # the permanents whose Signet-style ability ("{1}, {T}: Add ...") was used
    counters: tuple[tuple["Permanent", str, int], ...] = ()  # the lands whose mana cost counters (Vivid, depletion, storage): which, how many


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
    bought_back: bool = False  # its buyback cost was paid: it returns to its owner's hand as it resolves
    carried: Any = None  # what an earlier effect chose, for a later one (a fight's first target)
    mana_spent: int = 0  # the mana paid to cast it (Deekah: "the amount of mana spent to cast that spell")
    exile_after: bool = False  # cast with flashback: exiled, not put in the graveyard, when it leaves the stack
    rider_counters: int = 0  # Opal Palace: how many of its mana was spent on this commander
    from_graveyard: bool = False  # cast from a graveyard (flashback and the like): Sevinne's Reclamation asks
    bottom_after: bool = False  # Quintorius: put on the bottom of its owner's library instead of into the graveyard
    is_copy: bool = False  # a copy of a spell: not a card, so it vanishes instead of going to the graveyard
    evoked: bool = False  # cast for its evoke cost: it is sacrificed when it enters
    subject: "Permanent | None" = None  # for a watching trigger: the permanent that set it off ("on it")
    player: "Seat | None" = None  # for a watching trigger: the player whose action set it off ("that player")
    suspend_after: int = 0  # "Exile it with N time counters on it" once it has resolved
    escaped: bool = False  # cast for its escape cost
    bestowed: bool = False  # cast for its bestow cost: an Aura spell that may resolve as a creature
    sacrificed_power: int = 0  # for an ability: the power of the creature sacrificed to pay for it
    tapped_power: int = 0  # for an ability: the power of the creature tapped to pay for it (Station)
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
    spell: "StackItem | None" = None  # for a cast trigger: the spell that was cast

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
    extra_mountain_mana_turn: int | None = None  # Molten Tide: this turn, a Mountain tapped for mana adds an additional {R}
    life_mana_turn: int | None = None  # Channel: this turn, 1 life buys {C} any time
    conjurable: dict[str, Card] = field(default_factory=dict)  # Alchemy: the cards this player's deck can conjure, by name
    noncombat_damage_turn: int | None = None  # the last turn this player was dealt damage that wasn't combat damage
    damage_taken_turn: int | None = None  # the turn `damage_taken` counts for
    damage_taken: int = 0  # the damage dealt to this player that turn
    attackers_turn: int | None = None  # the turn `most_attackers` counts for
    most_attackers: int = 0  # the creatures this player attacked with that turn
    life_lost_amount: int = 0  # how much they lost on life_lost_turn
    keep_pool_turn: int | None = None  # the turn its mana pool is kept as steps end (Rousing Refrain)
    suspended: list = field(default_factory=list)  # [card, time counters] for each card suspended in exile
    player_counters: dict[str, int] = field(default_factory=dict)  # counters on the player: poison, energy, ...
    died_turn: int | None = None  # the turn `died` counts for
    died: int = 0  # creatures that died under this player's control that turn
    creatures_entered_turn: int | None = None  # the turn `creatures_entered` counts for
    creatures_entered: int = 0  # nontoken creatures that entered under this player's control that turn
    land_entered_turn: int | None = None  # the last turn a land entered the battlefield under this player's control
    life_gained_turn: int | None = None
    phased_out: list = field(default_factory=list)  # permanents (with what is attached to them) that phased out; back at its untap step
    life_gained_amount: int = 0  # how much life this player gained on life_gained_turn
    delayed_mana: int = 0  # {C} to add at the beginning of this player's next main phase (Mana Drain)
    combat_shield_turn: int | None = None  # Inkshield: the turn combat damage to this player is prevented
    combat_shield_token: Card | None = None  # ... and the token made for each point prevented
    copy_next_turn: int | None = None  # the turn the next instant or sorcery this player casts is copied (Pigment Wrangler)
    x_rider_turn: int | None = None  # Brass Infiniscope: the turn its delayed "next spell with {X}" triggers were set up
    x_rider_count: int = 0
    copy_next_per_commander: bool = False  # ... once per time the commander was cast from the command zone (Thunderclap Drake)
    flash_turn: int | None = None  # the turn this player may cast spells as though they had flash (Alchemist's Refuge)
    spent_turn: int | None = None  # the turn `spent_amount` counts for
    spent_amount: int = 0  # the mana this player spent casting spells that turn ("Whenever you expend 4")
    surge: tuple[int, Card] | None = None  # Surge to Victory: (the turn, the exiled card its creatures copy on combat damage)
    paragon_turn: int | None = None  # the last turn Serra Paragon's once-a-turn permission was used
    paragon_marked: list = field(default_factory=list)  # cards played with it, which are exiled if they go back (+ life)
    modified_died_turn: int | None = None  # the last turn a modified creature died under this player's control
    citys_blessing: bool = False  # Ascend: ten permanents, for the rest of the game
    graveyard_left_turn: int | None = None  # the last turn a card left this player's graveyard
    cast_log: list[tuple[int, Card]] = field(default_factory=list)  # (turn, spell) for every spell cast
    drew_from_empty: bool = False
    lost: bool = False

    @property
    def name(self) -> str:
        return self.player.name


class Game:
    # What the mana being paid is for, so "Spend this mana only ..." sources can say whether they qualify: a spell, or an
    # ability whose cost has {X}.
    _spending_spell: Card | None = None
    _spending_x: bool = False
    _spending_from_hand: bool = False  # ... and whether that spell is being cast from its owner's hand

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
                conjurable=dict(deck.conjured),
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
        self.starting_seat = 0  # who took the first turn ("if you were the starting player")
        self.monarch: Seat | None = None
        self.monarch_at_turn_start: Seat | None = None  # who was the monarch as this turn began
        self.initiative: Seat | None = None
        self.graveyarded_turn, self.graveyarded_count = 0, 0  # permanents put into a graveyard this turn (Gravestorm)
        self.deaths_turn, self.deaths_count = 0, 0  # how many creatures have died this turn, for "two or more creatures died this turn"
        self._batch: set[tuple[int, int]] | None = None  # watchers of "one or more ..." already told about this simultaneous event
        self.at_upkeep: list[tuple[int, Callable[[], None]]] = []  # (turn made, what) to do as the next turn's upkeep begins
        self.spectators: list = []  # watchers with notify(event): they see every public event and the board, never a hand
        self.at_end_step: list[tuple[int, Callable[[], None]]] = []  # (turn, what) to do as that turn's next end step begins
        self.at_owner_upkeep: list[tuple[Seat, int, Callable[[], None]]] = []  # (whose upkeep, the turn it was set up, what)
        self.targeting_x = 0  # the X of the spell whose targets are being chosen ("up to X target creatures")
        self.targeting_max: int | None = None  # how many targets "any number of target ..." may have (Strive: what the mana pays for)
        self.cost_sacrificed_power = 0  # the power of what the ability being activated sacrificed
        self.cost_tapped_power = 0  # the power of what the ability being activated tapped as a cost (Station)
        self.x_value = 0  # X of the spell resolving right now
        self.resolving_source: Permanent | None = None  # the source of the ability resolving right now
        self.resolving_item: StackItem | None = None  # what is resolving right now
        self.resolving_target: Any = None  # the last target chosen for it, which "that creature" in a condition means
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
        self.active = self.starting_seat = self.rng.randrange(len(self.seats))
        for seat in self.seats:
            self.rng.shuffle(seat.library)
            self.broadcast({"event": "seat", "seat": seat.index, "name": seat.name,
                             "life": seat.life, "commanders": [c.name for c in seat.command_zone]})
        self.broadcast({"event": "starting_player", "seat": self.active})
        for seat in self._turn_order(self.active):
            self._mulligan(seat)
        for seat in self._turn_order(self.active):  # CR 103.6: Leyline-style cards may start on the battlefield
            for card in [c for c in seat.hand if begins_on_battlefield(c)]:
                if seat.player.choose(f"{OPENING_PROMPT}{card.name}?", ["Yes", "No"]) == 0:
                    seat.hand.remove(card)
                    self._enter(seat, Permanent(card))

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
        self.monarch_at_turn_start = self.monarch
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
            seat.battlefield += seat.phased_out  # they phase in first, then untap with everything else
            seat.phased_out = []
            for permanent in seat.battlefield:
                if self.has_keyword(permanent, NO_UNTAP):  # Infinite Coursework
                    pass
                elif permanent.tapped and may_skip_untap(permanent.card) and \
                        seat.player.choose(UNTAP_PROMPT + permanent.card.name, ["Untap", "Leave tapped"]) != 0:
                    pass  # Hollow Trees: left tapped to collect a storage counter at upkeep
                else:
                    permanent.tapped = False
                permanent.sick = False
                permanent.until_next_turn = []
            for other in self.live_seats():  # goad lasts until the goader's next turn
                for permanent in other.battlefield:
                    if permanent.goaded_by is seat:
                        permanent.goaded_by = None
            for other in self.live_seats():  # Quest for Renewal: untap in each other player's untap step too
                if other is not seat and any(
                        (rule := untaps_in_other_untap_steps(p.card)) and p.counters.get(rule[0], 0) >= rule[1]
                        for p in other.battlefield):
                    for permanent in other.battlefield:
                        if "Creature" in permanent.card.type_line:
                            permanent.tapped = False
        elif self.step == "draw":
            # CR 103.8a: only a two-player game skips the first player's first draw.
            if not (self.turn == 1 and not self.multiplayer):
                self.draw(seat, 1)
            for permanent in list(seat.battlefield):
                self.trigger("draw_step", permanent, seat)
            for other in self.live_seats():  # "At the beginning of each other player's draw step" (Well of Ideas)
                if other is not seat:
                    self._trigger_each("other_draw_step", other, player=seat)
        elif self.step in ("upkeep", "end"):
            if self.step == "end":  # "at the beginning of the next end step"
                due = [what for turn, what in self.at_end_step if turn <= self.turn]
                self.at_end_step = [(turn, what) for turn, what in self.at_end_step if turn > self.turn]
                for what in due:
                    what()
            if self.step == "upkeep":
                due = [what for turn, what in self.at_upkeep if turn < self.turn]
                self.at_upkeep = [(turn, what) for turn, what in self.at_upkeep if turn >= self.turn]
                for what in due:
                    what()
                self._pay_upkeep_costs(seat)
                due = [fn for owner, born, fn in self.at_owner_upkeep if owner is seat and born < self.turn]  # Phytotitan
                self.at_owner_upkeep = [(o, b, fn) for o, b, fn in self.at_owner_upkeep if not (o is seat and b < self.turn)]
                for what in due:
                    what()
                self._tick_suspend(seat)
            for permanent in list(seat.battlefield):
                self.trigger("upkeep" if self.step == "upkeep" else "end_step", permanent, seat)
            if self.step == "upkeep":  # Squee: a card that returns itself from the graveyard at the beginning of your upkeep
                for card in list(seat.graveyard):
                    for ability in triggered_abilities(card):
                        if ability.event == "upkeep" and any(isinstance(e, ReturnThisFromGraveyard) for e in ability.effects):
                            self._queue(ability, Permanent(card), seat)
            for other in self.live_seats():  # "At the beginning of each upkeep / end step"
                for permanent in list(other.battlefield):
                    self.trigger("each_upkeep" if self.step == "upkeep" else "each_end_step", permanent, other)
                    if other is not seat:  # "At the beginning of each opponent's upkeep / end step"
                        self.trigger("opponent_upkeep" if self.step == "upkeep" else "opponent_end_step", permanent, other,
                                     player=seat)  # "that player" is whose turn it is
            if self.step == "upkeep" and self.initiative is seat:  # CR 726.2: the initiative ventures at upkeep
                self.venture(seat)
            if self.step == "end" and self.monarch is seat:  # CR 725.2: the monarch draws at their end step
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
            doomed = [a.attacker for a in self.combat.attacks if self.has_keyword(a.attacker, "decayed")
                      and self.on_battlefield(a.attacker)]
            if doomed:  # decayed: sacrifice it at end of combat
                self._leave_together([(p, "sacrificed") for p in doomed])
            if tokens := [p for p in self.combat.exile_at_end if self.on_battlefield(p)]:  # myriad
                self._leave_together([(p, "exiled") for p in tokens], "exile")
            self.combat = Combat(self)  # CR 511.3: creatures leave combat
            self._add_delayed_mana(seat)
            for permanent in list(seat.battlefield):
                self.trigger("second_main", permanent, seat)
        elif self.step == "cleanup":
            everyone = any(players_have_no_max_hand(p.card) for s in self.seats for p in s.battlefield)  # Price of Knowledge
            limits = [p.counters.get(c, 0) for p in seat.battlefield if (c := hand_size_counter(p.card))]  # Midnight Oil
            excess = 0 if everyone or any(no_max_hand_size(p.card) for p in seat.battlefield) \
                else len(seat.hand) - (min(limits) if limits else HAND_SIZE)
            for _ in range(max(0, excess)):
                i = seat.player.choose(DISCARD_PROMPT, [c.name for c in seat.hand])
                card = seat.hand.pop(i)
                self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
                self._discard_into_zone(seat, card)
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
            if not is_land(card) and (sorcery_timing or seat.flash_turn == self.turn or _instant_speed(card)) and self._can_cast(seat, card):
                actions.append(CAST + card.name)
        for card in seat.command_zone:
            if (sorcery_timing or seat.flash_turn == self.turn or _instant_speed(card)) and self._can_cast(seat, card, from_command_zone=True):
                actions.append(CAST_COMMANDER + card.name)
        for card in _unique(seat.graveyard):
            for cast in graveyard_casts(card)[:1]:
                if not is_land(card) and (sorcery_timing or seat.flash_turn == self.turn or _instant_speed(card)) and self._can_cast(seat, card, graveyard=cast):
                    actions.append(CAST_GRAVEYARD + card.name)
        for card in self._paragon_options(seat):
            if is_land(card):
                if sorcery_timing and seat.lands_played < 1:
                    actions.append(PLAY_PARAGON + card.name)
            elif (sorcery_timing or seat.flash_turn == self.turn or _instant_speed(card)) and self._can_cast(seat, card):
                actions.append(CAST_PARAGON + card.name)
        for card in _unique(seat.hand):  # Suspend N: pay the cost, exile it with time counters
            if (suspend := suspend_of(card)) and (sorcery_timing or seat.flash_turn == self.turn or _instant_speed(card)) \
                    and self._payment(seat, dataclasses.replace(card, mana_cost=suspend[1])) is not None:
                actions.append(SUSPEND + card.name)
        if sorcery_timing:
            for card in _unique(seat.graveyard):
                if (cost := encore_cost(card)) and self._payment(seat, dataclasses.replace(card, mana_cost=cost)) is not None:
                    actions.append(ENCORE + card.name)
                if (cost := unearth_cost(card)) and self._payment(seat, dataclasses.replace(card, mana_cost=cost)) is not None:
                    actions.append(UNEARTH + card.name)
        for card in _unique([c for c, until in seat.exile_play if self.turn <= until and c in seat.exile]):
            if is_land(card):
                if sorcery_timing and seat.lands_played < 1:
                    actions.append(PLAY_EXILE + card.name)
            elif (sorcery_timing or seat.flash_turn == self.turn or _instant_speed(card)) and self._can_cast(seat, card):
                actions.append(CAST_EXILE + card.name)
        for spell in _unique([p.card.prepare for p in seat.battlefield if p.prepared and p.card.prepare]):
            if (sorcery_timing or seat.flash_turn == self.turn or _instant_speed(spell)) and self._can_cast(seat, spell):
                actions.append(CAST_PREPARED + spell.name)
        actions += [TURN_UP + self.label(p) for p in self._turn_up_options(seat)]  # manifested creature cards
        for card in _unique(seat.hand):
            if (found := cycling(card)) and self._can_cycle(seat, found[1], found[3]):
                actions.append(CYCLE + card.name)
            for ability in hand_abilities(card)[:1]:
                if self._pay_cost(seat, parse_cost(ability.mana_cost)) is not None \
                        and self._effects_possible(seat, ability.effects, source_qualities(card)):
                    actions.append(ACTIVATE_HAND + card.name)
        for card in _unique(seat.graveyard):
            for ability in activated_abilities(card):
                if ability.from_graveyard and self._pay_cost(seat, parse_cost(ability.mana_cost)) is not None:
                    actions.append(ACTIVATE_GRAVEYARD + card.name)
                    break
        actions += list(self._activations(seat, sorcery_timing))
        return actions

    def _activations(self, seat: Seat, sorcery_timing: bool) -> dict[str, tuple[Permanent, ActivatedAbility]]:
        """Activated abilities `seat` can activate now, keyed by their action text."""
        options = {}
        for permanent in seat.battlefield:
            granted = [a for other in self.seats for attachment in other.battlefield if attachment.attached_to is permanent
                       for a in granted_abilities(attachment.card)]
            own = [] if self.loses_abilities(permanent) else activated_abilities(permanent.card)
            for ability in [*own, *granted]:
                if not ability.discard_self and not ability.from_graveyard and self._can_activate(seat, permanent, ability, sorcery_timing):
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
        if self._life_cost(seat, ability) > seat.life:  # CR 119.4
            return False
        if len(seat.hand) < ability.discard or len(self._exile_cost_choices(seat, ability)) < ability.exile_graveyard:
            return False
        if ability.sacrifice_other and len(self._sacrifice_choices(seat, permanent, ability)) < ability.sacrifice_count:
            return False
        if ability.remove_counter and not permanent.counters.get(ability.remove_counter, 0):
            return False
        if ability.tap_creatures and len(self._crew_candidates(seat, permanent)) < ability.tap_creatures:
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
        return self._effects_possible(seat, ability.effects, source_qualities(card), permanent)

    def _exile_cost_choices(self, seat: Seat, ability: ActivatedAbility) -> list[Card]:
        """The cards of `seat`'s graveyard that could be exiled to pay the ability's "Exile a creature card" cost."""
        return [c for c in seat.graveyard if _card_matches(ability.exile_graveyard_kind or "card", c)]

    def _life_cost(self, seat: Seat, ability: ActivatedAbility) -> int:
        return ability.life + (len(seat.color_identity) if ability.life_identity else 0)

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
                artifact: bool, keywords: frozenset[str], on_your_turn: frozenset[str] = frozenset()) -> None:
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
        if on_your_turn:
            permanent.until_end_of_turn.append(Modifier(0, 0, on_your_turn, your_turn=True))
        self.broadcast({"event": "became_creature", "card": permanent.card.name, "power": power, "toughness": toughness})

    def move_counters(self, source: Permanent, destination: Permanent, counter: str, count: int | None) -> None:
        """Move up to `count` counters (all of them if None) from one permanent to another. They are moved, not put
        on it, so nothing that doubles counters applies."""
        if counter is None:  # Nexus Mentality: all counters, of every kind
            for kind in list(source.counters):
                self.move_counters(source, destination, kind, count)
            return
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
                self.tap(member)
                crewed += self.power(member)
        self.cost_tapped_power = 0
        for _ in range(ability.tap_creatures):  # like crewing, but a fixed number of creatures
            options = self._crew_candidates(seat, source)
            member = options[seat.player.choose(CREW_PROMPT + name, [self.label(p) for p in options])]
            self.cost_tapped_power += self.power(member)
            self.tap(member)
        for _ in range(ability.discard):
            card = seat.hand[seat.player.choose(DISCARD_COST_PROMPT + name, [c.name for c in seat.hand])]
            seat.hand.remove(card)
            self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
            self._discard_into_zone(seat, card)
        for _ in range(ability.exile_graveyard):
            options = self._exile_cost_choices(seat, ability)
            card = options[seat.player.choose(EXILE_COST_PROMPT + name, [c.name for c in options])]
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
        self.cost_sacrificed_power = sum(self.power(p) for p in chosen)
        if chosen:
            self._leave_together([(p, "sacrificed") for p in chosen])

    def _ability_payment(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility,
                         x: int = 0) -> list[Permanent] | None:
        cost = (parse_cost(ability.mana_cost) if ability.mana_cost else Cost()).with_x(x)
        # A permanent can't tap for mana to pay for its own {T} or sacrifice ability.
        self._spending_x = "{X}" in ability.mana_cost
        try:
            return self._pay_cost(seat, cost, exclude=permanent if ability.tap or ability.sacrifice or ability.exile_source else None)
        finally:
            self._spending_x = False

    def _mana_spent_matches(self, seat: Seat, source: Permanent, card: Card, from_command_zone: bool, tapped) -> bool:
        """Whether `source`'s "When that mana is spent to cast ..." rider applies to casting `card`. A Study Hall
        tapped for its plain {C} spent no such mana: only its "{1}, {T}" ability carries the rider."""
        rider = mana_spent_trigger(source.card)
        if rider is None or (filter_mana_ability(source.card) and source not in getattr(tapped, "filters", ())):
            return False
        if rider.spell == "commander":
            return from_command_zone and card.name in seat.commander_names
        if "Creature" not in card.type_line:
            return False
        types = set(card.type_line.partition("—")[2].split())
        commanders = [c for zone in (seat.command_zone, seat.graveyard, seat.exile, seat.library, seat.hand) for c in zone
                      if c.name in seat.commander_names] + [p.card for p in seat.battlefield if p.card.name in seat.commander_names]
        return any(types & set(c.type_line.partition("—")[2].split()) for c in commanders)

    def commander_tax(self, seat: Seat, card: Card) -> int:
        return COMMANDER_TAX * seat.commander_casts.get(card.name, 0)

    def _can_cast(self, seat: Seat, card: Card, from_command_zone: bool = False,
                  graveyard: GraveyardCast | None = None) -> bool:
        if not self._cast_ways(seat, card, from_command_zone, graveyard):
            return False
        effects, colors = kicked_effects(_effects(card), 0) or [], source_qualities(card)
        if not self._effects_possible(seat, effects, colors):
            return False
        if parse_cost(card.mana_cost).x and any((kind := target_kind(e)) and kind.endswith(" with mana value x") for e in effects):
            # "target creature with mana value X": some X it can pay for has to match a creature
            return bool(self._x_values_with_targets(seat, effects, colors, self._max_x(seat, card, from_command_zone, ())))
        return True

    def tap(self, permanent: Permanent) -> None:
        """Tap a permanent. A tapped one stays as it is; one that becomes tapped is seen by "Whenever a creature you
        control becomes tapped"."""
        if permanent.tapped:
            return
        permanent.tapped = True
        controller = self.controller_of(permanent)
        if controller is not None:
            self._observe("permanent_taps", permanent.card, controller, subject=permanent)

    def _spend_mana(self, seat: Seat, sources: list[Permanent]) -> None:
        """Tap the chosen mana sources; ones whose mana ability sacrifices them (Treasure) are sacrificed,
        and painlands and Talismans that made painful mana damage the payer."""
        for source in sources:
            if (kind := counter_mana(source.card)) is not None:  # no {T} in the cost: it isn't tapped
                self.remove_counters(source, kind, 1)
                source.activated_turn["counter mana"] = self.turn
                continue
            self.tap(source)
            if has_next_x_rider(source.card):  # Brass Infiniscope
                seat.x_rider_count = (seat.x_rider_count if seat.x_rider_turn == self.turn else 0) + 1
                seat.x_rider_turn = self.turn
            if not is_land(source.card) and mana_ability_sacrifices(source.card):
                self._leave_battlefield(source, "sacrificed")
            if (extra := mana_extra_cost(source.card)) == "mill":
                self.mill(seat, 1)
            elif extra == "food" and (food := next((p for p in seat.battlefield if _has_type(p.card, "food")), None)):
                self._leave_battlefield(food, "sacrificed")
        for permanent, kind, amount in getattr(sources, "counters", ()):  # Vivid, depletion and storage lands
            self.remove_counters(permanent, kind, amount)
            if not permanent.counters.get(kind) and counter_removal_mana(permanent.card).sacrifice_at_zero:
                self._leave_battlefield(permanent, "sacrificed")
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

    def _tick_suspend(self, seat: Seat) -> None:
        """At the beginning of its owner's upkeep a suspended card loses a time counter; when the last is gone it is cast
        without paying its mana cost, if the owner chooses to."""
        for entry in list(seat.suspended):
            entry[1] -= 1
            if entry[1] > 0:
                continue
            seat.suspended.remove(entry)
            card = entry[0]
            if card in seat.exile and seat.player.choose(CASCADE_PROMPT + card.name, YES_NO) == 0:
                self._cast(seat, card, seat.exile, free=True)
            elif card in seat.exile:
                seat.exile.remove(card)  # not cast: it stays exiled for good
                seat.exile.append(card)

    def _empty_pools(self) -> None:
        for seat in self.seats:
            if seat.keep_pool_turn == self.turn and self.step != "cleanup":  # "you don't lose this mana ... until end of turn"
                continue
            seat.mana_pool.clear()

    @contextlib.contextmanager
    def _paying_for(self, seat: Seat, card: Card):
        """While mana is paid for casting `card`, which is still in the zone it is cast from."""
        self._spending_spell, self._spending_from_hand = card, any(c is card for c in seat.hand)
        try:
            yield
        finally:
            self._spending_spell, self._spending_from_hand = None, False

    def _restriction_ok(self, restriction: str | None) -> bool:
        """Whether mana limited by `restriction` can pay for what is being paid for now."""
        if restriction is None:
            return True
        spell = self._spending_spell
        if restriction == "not_from_hand":  # Heartwood Crafter: only spells cast from hand are off limits
            return not self._spending_from_hand
        if restriction == "instant_or_sorcery":  # Galazeth Prismari
            return spell is not None and ("Instant" in spell.type_line or "Sorcery" in spell.type_line)
        if restriction == "x_cost":
            return self._spending_x or (spell is not None and "{X}" in spell.mana_cost)
        return spell is not None and (spell.cmc >= 5 or "{X}" in spell.mana_cost)

    def _mana_sources(self, seat: Seat, exclude: Permanent | None = None) -> list[ManaSource]:
        """One entry per mana each untapped permanent can make: nonland sources first,
        then lands, and sources that sacrifice themselves (Treasure) last."""
        abilities, lands, sacrifices = [], [], []
        pooled = [ManaSource(None, unit) for unit in seat.mana_pool]
        foods = sum(_has_type(p.card, "food") for p in seat.battlefield)  # Gilded Goose: one Food per use
        grants = [g for p in seat.battlefield if not self.loses_abilities(p) for g in group_mana_grants(p.card)]
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude or self.loses_abilities(permanent):
                continue
            card = permanent.card
            if grants and not is_land(card) and (given := tuple(line for kind, line in grants if kind in card.type_line)):
                card = with_granted_mana(card, given)  # Goldspan Dragon, Galazeth Prismari
            pain, damage = mana_pain(card) or (frozenset(), 0)
            if (condition := mana_condition(card)) and not self.condition_holds(condition, seat, permanent):
                continue  # "Activate only if you control five or more lands."
            if (per := mana_per_count(card)) is not None:  # Gaea's Cradle: as much as you control
                if not per[0] and not (permanent.sick and "Creature" in card.type_line):
                    lands.extend(ManaSource(permanent, frozenset(per[1]))
                                 for _ in range(sum(_has_type(p.card, per[2]) for p in seat.battlefield)))
                if not per[0] or mana_ability(card, seat.color_identity) is None:
                    continue  # (Cabal Coffers has only the ability that costs mana; Evendo's plain {T}: Add {G} is read below)
            if is_land(card):
                if life_cost := mana_life_cost(card):
                    if seat.life > life_cost:  # Mana Confluence: paying life, never down to 0
                        lands.append(ManaSource(permanent, mana_life_types(card), frozenset("WUBRGC"), life_cost, life=True))
                    continue
                if (cm := counter_removal_mana(card)) is not None:  # Vivid Crag, Hickory Woodlot: the mana costs a counter
                    plain = mana_ability(card, seat.color_identity)
                    free = frozenset().union(*plain) if plain else frozenset()  # the Vivid land's own color costs nothing
                    if cm.each:  # a storage land: one mana for each counter it could lose
                        lands.extend(ManaSource(permanent, cm.mana[0], counter=cm.counter, counter_each=True)
                                     for _ in range(permanent.counters.get(cm.counter, 0)))
                    elif permanent.counters.get(cm.counter, 0):
                        lands.extend(ManaSource(permanent, mana | free, counter=cm.counter, counter_free=free) for mana in cm.mana)
                    elif free:
                        lands.append(ManaSource(permanent, free))
                    continue
                gifted = [mana for other in self.seats for a in other.battlefield if a.attached_to is permanent
                          for mana in granted_mana(a.card)]  # "Enchanted land has "{T}: Add {G}{G}."": the better of the two
                extra = [ManaSource(permanent, mana, pain, damage) for other in self.seats for a in other.battlefield
                         if a.attached_to is permanent for mana in additional_land_mana(a.card)]  # Wild Growth
                if seat.extra_mountain_mana_turn == self.turn and "Mountain" in card.type_line:  # Molten Tide
                    extra.append(ManaSource(permanent, frozenset("R"), pain, damage))
                if units := land_mana_units(card):  # a bounceland or Ancient Tomb makes several mana in one tap
                    lands.extend([ManaSource(permanent, mana, pain, damage) for mana in units] + extra)
                    continue
                if len(gifted) > 1:  # more mana than the land's own single one
                    lands.extend([ManaSource(permanent, mana, pain, damage) for mana in gifted] + extra)
                    continue
                # Command Tower makes only the colors of your commander, whatever the card data lists.
                types = seat.color_identity if is_identity_mana_land(card) else frozenset(card.produced_mana)
                if (chosen := chosen_color_mana(card)) is not None:  # Room of Refuge, a Thriving land: the color chosen as it entered
                    types = frozenset(c for c in (chosen[0], permanent.chosen_color) if c)
                    if not types:
                        continue
                if filter_mana_ability(card) is not None:  # Hall of Oracles: the colors cost {1}; alone it makes {C}
                    plain = mana_ability(card, seat.color_identity)
                    types = frozenset().union(*plain) if plain else frozenset()
                    if not types:
                        continue
                if reflect := reflected_mana(card):
                    types = self._reflected_types(seat, *reflect)
                    if not types:
                        continue
                lands.extend([ManaSource(permanent, _snowy(permanent, types), pain, damage)] + extra)
            elif not (permanent.sick and "Creature" in card.type_line and not mana_ability_needs_no_tap(card)):
                bucket = sacrifices if mana_ability_sacrifices(card) else abilities
                extra = mana_extra_cost(card)
                if extra == "food" and foods <= 0 or extra == "mill" and not seat.library:
                    continue  # nothing to pay the mana ability's extra cost with
                if extra == "food":
                    foods -= 1
                if (charge := charge_mana(card)) is not None:  # Astral Cornucopia: a mana for each charge counter
                    if permanent.counters.get("charge", 0) and self._restriction_ok(charge[1]):
                        bucket.extend(ManaSource(permanent, charge[0], restriction=charge[1])
                                      for _ in range(permanent.counters["charge"]))
                if (kind := counter_mana(card)) is not None:  # Mana Bloom: a counter for one mana, once each turn
                    if permanent.counters.get(kind, 0) and permanent.activated_turn.get("counter mana") != self.turn:
                        bucket.append(ManaSource(permanent, frozenset("WUBRG")))
                    continue
                if reflect := reflected_mana(card):  # Fellwar Stone: what the opponents' lands could produce
                    types = self._reflected_types(seat, *reflect)
                    if types:
                        bucket.append(ManaSource(permanent, types))
                    continue
                units = ([frozenset("WUBRG")] * max(0, self.power(permanent)) if makes_mana_by_power(card)
                         else mana_ability(card, seat.color_identity) or [])  # (the power's worth need not be one color here)
                restriction = mana_restriction(card)
                if not self._restriction_ok(restriction):
                    continue
                for mana in units:
                    bucket.append(ManaSource(permanent, _snowy(permanent, mana), pain, damage, restriction=restriction))
        return pooled + abilities + lands + sacrifices + self._convoke_sources(seat, exclude, pooled + abilities + lands + sacrifices)

    def _convoke_sources(self, seat: Seat, exclude: Permanent | None, taken: list[ManaSource]) -> list[ManaSource]:
        """While a spell with Convoke (or Improvise) is being paid for: each untapped creature (artifact) not already a mana
        source can be tapped for {1}, or for one mana of its color. Summoning-sick ones can, since it isn't a {T} cost; they go
        first, being the ones that couldn't attack anyway."""
        spell = self._spending_spell
        if spell is None:
            return []
        convoke, improvise = has_keyword(spell, "convoke"), has_keyword(spell, "improvise")
        busy = {id(s.permanent) for s in taken if s.permanent is not None}
        found = []
        for permanent in sorted(seat.battlefield, key=lambda p: not p.sick):
            if permanent.tapped or permanent is exclude or id(permanent) in busy:
                continue
            if convoke and "Creature" in permanent.card.type_line:
                found.append(ManaSource(permanent, frozenset(permanent.card.colors) or frozenset({GENERIC_ONLY})))
            elif improvise and "Artifact" in permanent.card.type_line:
                found.append(ManaSource(permanent, frozenset({GENERIC_ONLY})))
        return found

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
        """The permanents to tap for `card` with X = `x`, or None if it can't be paid for now."""
        cost = self._cast_cost(seat, card, from_command_zone, x, alternative, kickers, extra, delve)
        if cost is None:
            return None
        with self._paying_for(seat, card):
            return self._pay_cost(seat, cost)

    def _cast_cost(self, seat: Seat, card: Card, from_command_zone: bool = False, x: int = 0,
                   alternative: AlternativeCost | None = None, kickers: tuple[str, ...] = (), extra: str = "",
                   delve: int = 0) -> Cost | None:
        """The mana to pay for `card` with X = `x`. An alternative cost replaces the mana cost; commander tax and
        kicker are added, then cost reductions apply."""
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
        return cost.with_x(x).reduced(self.cost_reduction(seat, card) + delve)

    def cost_reduction(self, seat: Seat, card: Card) -> int:
        """How much less generic mana `card` costs `seat` (Medallions and the like)."""
        reduction = sum(amount for p in seat.battlefield for kind, amount in cost_reductions(p.card)
                        if _spell_matches(kind, card))
        if (kind := affinity_for(card)) is not None:  # Affinity for planeswalkers
            reduction += sum(_has_type(p.card, kind) for p in seat.battlefield)
        if "{X}" in card.mana_cost and not any("{X}" in c.mana_cost for turn, c in seat.cast_log if turn == self.turn):
            reduction += sum(p.counters.get("+1/+1", 0) for p in seat.battlefield if x_spell_discount(p.card))  # Zimone
        for p in seat.battlefield:  # Pearl-Ear, Imperial Advisor: affinity for Auras
            if (kind := granted_affinity(p.card)) and _spell_matches(kind, card):
                reduction += sum(_has_type(a.card, "aura") for a in seat.battlefield)
        if not any(c is card for c in seat.hand):  # Advanced Reconstruction: spells cast from anywhere other than your hand
            reduction += sum(non_hand_cost_reduction(p.card) for p in seat.battlefield)
        if (conditional := conditional_cost_reduction(card)) and self.condition_holds(conditional[1], seat):
            reduction += conditional[0]
        if reduced_by_total_power(card):
            reduction += sum(self.power(p) for p in seat.battlefield if "Creature" in p.card.type_line)
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
            if graveyard.discard_land and not any(is_land(c) for c in seat.hand):
                return []
            return [None] if others >= graveyard.exile and graveyard.life <= seat.life and self._payment(seat, paying) is not None else []
        return [way for way in [None, *alternative_costs(card)]
                if self._can_pay_extras(seat, card, way)
                and not (way and way.bestow and not self.target_options("creature", seat, source_qualities(card)))
                and self._payment(seat, card, from_command_zone, alternative=way,
                                  delve=self._delve_max(seat, card) if way is None else 0) is not None]

    def _extra_costs(self, card: Card, kicked: int, bought_back: bool = False) -> list:
        """The non-mana costs of casting `card`: its additional costs, plus a non-mana kicker cost if kicked and a non-mana
        buyback cost if bought back."""
        kicker = kicker_other_cost(card) if kicked else None
        buyback = buyback_other_cost(card) if bought_back else None
        return additional_costs(card) + ([kicker] if kicker else []) + ([buyback] if buyback else [])

    def _sacrifice_for_copies(self, seat: Seat, card: Card) -> int:
        """Plumb the Forbidden: "you may sacrifice one or more creatures. When you do, copy this spell for each creature sacrificed";
        returns how many were."""
        if not copies_per_sacrifice(card):
            return 0
        creatures = sum("Creature" in p.card.type_line for p in seat.battlefield)
        if not creatures:
            return 0
        wanted = seat.player.choose(SACRIFICE_COPIES_PROMPT + card.name, [str(n) for n in range(creatures + 1)])
        return len([gone for _ in range(wanted) for gone in self.sacrifice(seat, "creature")])

    def _can_pay_extras(self, seat: Seat, card: Card, alternative: AlternativeCost | None, kicked: int = 0,
                        bought_back: bool = False) -> bool:
        """Whether `seat` can pay the parts of casting `card` that aren't mana: additional costs, a non-mana
        kicker cost, and `alternative`'s condition, life and card to exile."""
        extras = self._extra_costs(card, kicked, bought_back)
        others = list(seat.hand)
        if card in others:
            others.remove(card)
        if sum(c.life for c in extras) + (alternative.life if alternative else 0) > seat.life:  # CR 119.4
            return False
        if sum(c.discard for c in extras) > len(others):
            return False
        for kind in {c.sacrifice for c in extras if c.sacrifice and not c.sacrifice_x}:
            needed = sum(c.sacrifice == kind for c in extras if not c.sacrifice_x)
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
                    graveyard: GraveyardCast | None = None, x: int = 0, kicked: int = 0, bought_back: bool = False) -> None:
        """Pay the non-mana costs of casting `card`, which has already left its zone."""
        for _ in range(graveyard.exile if graveyard else 0):  # Escape: exile other cards from the graveyard
            exiled = seat.graveyard[seat.player.choose(ESCAPE_PROMPT, [c.name for c in seat.graveyard])]
            seat.graveyard.remove(exiled)
            self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": exiled.name, "to": "exile"})
            self._move_card(seat, exiled, "exile")
        if graveyard and graveyard.exile:
            self._left_graveyard(seat)
        if graveyard and graveyard.life:  # "Flashback\u2014{1}{U}, Pay 3 life."
            self.change_life(seat, -graveyard.life)
        if graveyard and graveyard.discard_land:  # Retrace
            lands = [c for c in seat.hand if is_land(c)]
            discarded = lands[seat.player.choose(DISCARD_PROMPT, [c.name for c in lands])]
            seat.hand.remove(discarded)
            self.broadcast({"event": "discard", "seat": seat.index, "card": discarded.name})
            self._move_card(seat, discarded, "graveyard")
        if alternative and alternative.exile_color:
            options = [c for c in seat.hand if alternative.exile_color in c.colors]
            exiled = options[seat.player.choose(PITCH_PROMPT, [c.name for c in options])]
            seat.hand.remove(exiled)
            self.broadcast({"event": "exiled_from_hand", "seat": seat.index, "card": exiled.name})
            self._move_card(seat, exiled, "exile")
        extras = self._extra_costs(card, kicked, bought_back)
        for extra in extras:
            if extra.discard:
                discarded = seat.hand[seat.player.choose(DISCARD_PROMPT, [c.name for c in seat.hand])]
                seat.hand.remove(discarded)
                self.broadcast({"event": "discard", "seat": seat.index, "card": discarded.name})
                self._discard_into_zone(seat, discarded)
            for _ in range(x if extra.sacrifice_x else 1 if extra.sacrifice else 0):
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
        if seat.life_mana_turn == self.turn and seat.life > 1:  # Channel: only when nothing that costs nothing will do
            lives = [ManaSource(None, frozenset("C"), frozenset("C"), 1, life=True) for _ in range(min(seat.life - 1, MAX_LIFE_MANA))]
            for size in range(len(filters) + 1):
                for combo in combinations(filters, size):
                    chosen = self._pay_with_filters(cost, sources + lives, combo)
                    if chosen is not None and chosen.life < seat.life:  # never down to 0
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
        payment.pool = tuple(s.types for s, _ in used if s.permanent is None and not s.life)  # a life-paid {C} (Channel) isn't pooled
        payment.filters = tuple(p for p, _, _ in ordered)
        # A permanent hurts (or costs life) once per tap, however many of its mana are used.
        hurt: dict[int, int] = {}
        paid_life: dict[int, int] = {}
        for source, symbol in used:
            into = paid_life if source.life else hurt
            key = id(source) if source.permanent is None else id(source.permanent)  # each life-paid {C} costs its own life
            into[key] = max(into.get(key, 0), _pain(source, symbol))
        payment.pain, payment.life = sum(hurt.values()), sum(paid_life.values())
        # A land whose mana costs a counter loses one per tap, unless it only made its own color (or generic mana).
        losing: dict[int, list] = {}
        for s, symbol in used:
            if s.counter and not (s.counter_free and (symbol is None or s.counter_free & symbol)):
                entry = losing.setdefault(id(s.permanent), [s.permanent, s.counter, 0])
                entry[2] = entry[2] + 1 if s.counter_each else 1
        payment.counters = tuple(tuple(entry) for entry in losing.values())
        return payment

    def _filter_sources(self, seat: Seat, exclude: Permanent | None) -> list[tuple[Permanent, Cost, list]]:
        found = []
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude or (permanent.sick and "Creature" in permanent.card.type_line) \
                    or self.loses_abilities(permanent):
                continue
            ability = filter_mana_ability(permanent.card)
            if ability:
                found.append((permanent, parse_cost(ability[0]), ability[1]))
            elif (per := mana_per_count(permanent.card)) is not None and per[0] \
                    and permanent.counters.get("charge", 0) >= mana_threshold(permanent.card):  # Cabal Coffers, Evendo
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
        elif action.startswith(PLAY_PARAGON):
            card = _take(seat.graveyard, action.removeprefix(PLAY_PARAGON))
            self._used_paragon(seat, card)
            self._left_graveyard(seat, [card])
            self._enter(seat, Permanent(card, sick=True))
            seat.lands_played += 1
            self.broadcast({"event": "play_land", "seat": seat.index, "card": card.name, "from": "graveyard"})
        elif action.startswith(CAST_PARAGON):
            card = next(c for c in seat.graveyard if c.name == action.removeprefix(CAST_PARAGON))
            self._used_paragon(seat, card)
            self._cast(seat, card, seat.graveyard)
        elif action.startswith(CAST_EXILE):
            card = next(c for c in seat.exile if c.name == action.removeprefix(CAST_EXILE))
            self._used_exile_permission(seat, card)
            self._cast(seat, card, seat.exile)
        elif action.startswith(TURN_UP):
            permanent = next(p for p in self._turn_up_options(seat) if self.label(p) == action.removeprefix(TURN_UP))
            self.turn_face_up(seat, permanent)
        elif action.startswith(CYCLE):
            self._cycle(seat, _take(seat.hand, action.removeprefix(CYCLE)))
        elif action.startswith(ACTIVATE_HAND):
            self._activate_from_hand(seat, _take(seat.hand, action.removeprefix(ACTIVATE_HAND)))
        elif action.startswith(ACTIVATE_GRAVEYARD):
            self._activate_from_graveyard(seat, next(c for c in seat.graveyard if c.name == action.removeprefix(ACTIVATE_GRAVEYARD)))
        elif action.startswith(CAST_COMMANDER):
            name = action.removeprefix(CAST_COMMANDER)
            card = next(c for c in seat.command_zone if c.name == name)
            self._cast(seat, card, seat.command_zone, from_command_zone=True)
            seat.commander_casts[name] = seat.commander_casts.get(name, 0) + 1
        elif action.startswith(CAST_GRAVEYARD):
            card = next(c for c in seat.graveyard if c.name == action.removeprefix(CAST_GRAVEYARD))
            self._cast(seat, card, seat.graveyard, graveyard=graveyard_casts(card)[0])
        elif action.startswith(SUSPEND):
            card = next(c for c in seat.hand if c.name == action.removeprefix(SUSPEND))
            counters, cost = suspend_of(card)
            self._spend_mana(seat, self._payment(seat, dataclasses.replace(card, mana_cost=cost)))
            seat.hand.remove(card)
            seat.exile.append(card)
            seat.suspended.append([card, counters])
            self.broadcast({"event": "suspended", "seat": seat.index, "card": card.name, "counters": counters})
        elif action.startswith(UNEARTH):
            self._unearth(seat, next(c for c in seat.graveyard if c.name == action.removeprefix(UNEARTH)))
        elif action.startswith(ENCORE):
            self._encore(seat, next(c for c in seat.graveyard if c.name == action.removeprefix(ENCORE)))
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

    def choose_piles(self, seat: Seat) -> None:
        """Abstract Performance: two piles of four exiled cards (one face down); an opponent chooses which goes to the
        graveyard, then `seat` may cast a spell from the other one for free and puts the rest into their hand."""
        piles = []
        for face in ("face-down", "face-up"):
            pile = [seat.library.pop(0) for _ in range(min(4, len(seat.library)))]
            piles.append(pile)
            self.broadcast({"event": "exiled_pile", "seat": seat.index, "face": face,
                            "cards": [] if face == "face-down" else [c.name for c in pile]})
        opponents = self.opponents(seat)
        chooser = opponents[0] if opponents else seat
        lost = piles[chooser.player.choose(PILE_PROMPT, [f"The face-down pile ({len(piles[0])} cards)",
                                                           "The face-up pile: " + ", ".join(c.name for c in piles[1])])]
        kept = piles[1] if lost is piles[0] else piles[0]
        for card in lost:
            self._move_card(seat, card, "graveyard")
        for card in kept:
            seat.exile.append(card)
        options = [c for c in kept if not is_land(c)]
        if options:
            pick = seat.player.choose(PILE_CAST_PROMPT, [c.name for c in options] + ["None"])
            if pick < len(options):
                self._cast(seat, options[pick], seat.exile, free=True)
        for card in kept:
            if card in seat.exile:
                seat.exile.remove(card)
                seat.hand.append(card)

    def cast_copy_free(self, seat: Seat, card: Card) -> None:
        """Cast a copy of `card` without paying its mana cost (Surge to Victory); the copy stops existing afterwards."""
        self._cast(seat, card, [card], free=True, copy=True)

    def _paragon_options(self, seat: Seat) -> list[Card]:
        """Cards in the graveyard Serra Paragon lets `seat` play this turn (once a turn): a land, or a permanent spell
        of mana value 3 or less."""
        if seat.paragon_turn == self.turn:
            return []
        limits = [found[0] for p in seat.battlefield if (found := graveyard_permission(p.card))]
        if not limits:
            return []
        return _unique([c for c in seat.graveyard
                        if is_land(c) or ("Instant" not in c.type_line and "Sorcery" not in c.type_line and c.cmc <= max(limits))])

    def _used_paragon(self, seat: Seat, card: Card) -> None:
        seat.paragon_turn = self.turn
        seat.paragon_marked = [card]

    def _used_exile_permission(self, seat: Seat, card: Card) -> None:
        seat.exile_play = [(c, until) for c, until in seat.exile_play if c != card] + \
                          [(c, until) for c, until in seat.exile_play if c == card][1:]

    def exile_top(self, seat: Seat, count: int, play: str | None) -> list[Card]:
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
        if exiled:
            self._exiled_from_library_or_graveyard(seat)
        return exiled

    def exile_random_from_graveyard(self, seat: Seat, play_this_turn: bool) -> None:
        """Exile a card chosen at random from the graveyard; it can be played until the turn ends."""
        if seat.graveyard:
            self.exile_card_from_graveyard(seat, seat.graveyard[self.rng.randrange(len(seat.graveyard))], play_this_turn)

    def exile_card_from_graveyard(self, seat: Seat, card: Card, play_this_turn: bool) -> None:
        """Exile that card from `seat`'s graveyard; it can be played until the turn ends."""
        seat.graveyard.remove(card)
        self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": "exile"})
        self._move_card(seat, card, "exile")
        self._note_exiled_with(seat, card)
        self._left_graveyard(seat, [card])
        self._exiled_from_library_or_graveyard(seat)
        if play_this_turn and card in seat.exile:
            seat.exile_play.append((card, self.turn))

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
        self._trigger_each("cycle", seat)
        self._trigger_each("cycle_or_discard", seat)
        self.broadcast({"event": "activate", "seat": seat.index, "card": card.name, "ability": _shown(ability.text, card),
                        "targets": [], "tapped": [p.card.name for p in tapped]})

    def _activate_from_hand(self, seat: Seat, card: Card) -> None:
        """"{U/R}{U/R}, Discard this card: Create a Treasure token.": like cycling, the card is discarded as a cost and
        the ability goes on the stack."""
        ability = hand_abilities(card)[0]
        effects = list(ability.effects)
        targets, labels = self._choose_targets(seat, effects, card.name, colors=source_qualities(card))
        tapped = self._pay_cost(seat, parse_cost(ability.mana_cost)) if ability.mana_cost else []
        self._spend_mana(seat, tapped)
        self.broadcast({"event": "discard", "seat": seat.index, "card": card.name, "reason": "cost"})
        self._move_card(seat, card, "graveyard")
        self.stack.append(StackItem(card, seat, effects, targets, ability))
        self.broadcast({"event": "activate", "seat": seat.index, "card": card.name, "ability": _shown(ability.text, card),
                        "targets": labels, "tapped": [p.card.name for p in tapped]})

    def _activate_from_graveyard(self, seat: Seat, card: Card) -> None:
        """"{B}{G}: Return this card from your graveyard to the battlefield tapped.": only its mana cost is paid; the card
        stays where it is until the ability resolves."""
        ability = next(a for a in activated_abilities(card) if a.from_graveyard)
        tapped = self._pay_cost(seat, parse_cost(ability.mana_cost)) if ability.mana_cost else []
        self._spend_mana(seat, tapped)
        self.stack.append(StackItem(card, seat, list(ability.effects), [], ability))
        self.broadcast({"event": "activate", "seat": seat.index, "card": card.name, "ability": _shown(ability.text, card),
                        "targets": [], "tapped": [p.card.name for p in tapped]})

    def _activate(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility) -> None:
        effects = list(ability.effects)
        if effects and isinstance(effects[0], Modal):
            effects, _ = self._choose_modes(seat, permanent.card, effects[0], source=permanent)
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
            self.tap(permanent)
        if life := self._life_cost(seat, ability):
            self.change_life(seat, -life)
        self._pay_card_costs(seat, permanent, ability)
        if ability.loyalty is not None:
            permanent.loyalty = (permanent.loyalty or 0) + ability.loyalty
            permanent.loyalty_turn = self.turn
        permanent.activated_turn[ability.text] = self.turn
        if ability.exile_source or ability.bounce_source:  # a cost: the ability exists apart from the source (CR 113.7a)
            self._leave_battlefield(permanent, "exiled" if ability.exile_source else "returned",
                                    destination="exile" if ability.exile_source else "hand")
        item = StackItem(permanent.card, seat, effects, targets, ability, permanent, x=x,
                         sacrificed_power=self.cost_sacrificed_power, tapped_power=self.cost_tapped_power)
        self.stack.append(item)
        self.broadcast({"event": "activate", "seat": seat.index, "card": permanent.card.name,
                        "ability": _shown(ability.text, permanent.card), "targets": labels,
                        "tapped": [p.card.name for p in tapped]})
        if ability.mana_cost and parse_cost(ability.mana_cost).x:  # Unbound Flourishing
            self._trigger_each("activate_x", seat, spell=item)
        self._check_ward(item)
        if ability.sacrifice:
            self._leave_battlefield(permanent, "sacrificed")
        elif ability.exile_source:  # "Exile this land" (Tomb Fortress)
            self.exile(permanent)

    def _x_values_with_targets(self, seat: Seat, effects, colors: frozenset[str], most: int) -> list[int]:
        """The X from 0 to `most` for which every "target creature with mana value X" has a legal target. Any X will do
        for a spell whose targets don't depend on X."""
        kinds = [kind for e in effects or [] if (kind := target_kind(e)) and kind.endswith(" with mana value x")]
        if not kinds:
            return list(range(most + 1))
        saved, good = self.targeting_x, []
        try:
            for n in range(most + 1):
                self.targeting_x = n
                if all(self.target_options(self._fixed_kind(kind, None), seat, colors) for kind in kinds):
                    good.append(n)
        finally:
            self.targeting_x = saved
        return good

    def _effects_possible(self, seat: Seat, effects, colors: frozenset[str] = frozenset(),
                          source: Permanent | None = None) -> bool:
        """Whether the targets exist: for a modal spell or ability, for enough of its modes."""
        if effects and isinstance(effects[0], Modal):
            return sum(self._targets_exist(seat, modes, colors, source) for modes in effects[0].modes) >= effects[0].min
        return self._targets_exist(seat, effects, colors, source)

    def _targets_exist(self, seat: Seat, effects, colors: frozenset[str] = frozenset(),
                       source: Permanent | None = None) -> bool:
        """Whether every targeting effect (but "up to one target") has a legal target; a `distinct` one needs one
        besides the targets chosen for earlier effects of the same kind, and an "another" one can't be `source`."""
        kinds = [(kind, getattr(e, "distinct", False), getattr(e, "another", False)) for e in effects
                 if (kind := target_kind(e)) and not getattr(e, "optional_target", False)]
        for i, (kind, distinct, another) in enumerate(kinds):
            needed = 1 + (sum(k == kind for k, _, _ in kinds[:i]) if distinct else 0)
            kind = kind.removesuffix(" with mana value x")  # X isn't chosen yet: any creature could do
            options = [o for _, o in self.target_options(self._fixed_kind(kind, source), seat, colors)
                       if not (another and o is source)]
            if len(options) < needed:
                return False
        return True

    def _choose_modes(self, seat: Seat, card: Card, modal: Modal, from_command_zone: bool = False,
                      casting: bool = False, source: Permanent | None = None) -> tuple[list, str]:
        """Ask the controller for the modes of a modal spell or ability (only ones with legal targets are offered):
        the chosen modes' effects in printed order, and any extra mana cost for them. When casting, entwine (all the
        modes) and escalate (each mode beyond the first) are offered if they can be paid for."""
        colors = source_qualities(card)
        available = [i for i, effects in enumerate(modal.modes) if self._targets_exist(seat, effects, colors, source)]
        if len(available) < modal.min:
            return [], ""
        if modal.optional and seat.player.choose(OPTIONAL_PROMPT + card.name, YES_NO) != 0:
            return [], ""  # "you may choose two": declined
        entwine, escalate = (entwine_cost(card), escalate_cost(card)) if casting else (None, None)
        if modal.commander_both and any(p.card.name in (p.owner or seat).commander_names for p in seat.battlefield):
            modal = dataclasses.replace(modal, max=len(modal.modes))  # "if you control a commander ... you may choose both"
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
            kind = self._fixed_kind(kind, source)
            if getattr(effect, "per_player", False):  # "for each player, ... up to one target creature that player controls"
                picked = []
                for owner in self.turn_order_from_active():
                    pool = [o for o in self.target_options(kind, seat, colors) if self.controller_of(o[1]) is owner]
                    if pool:
                        pick = seat.player.choose(TARGET_PROMPT + source_name, [o[0] for o in pool] + [NO_TARGET])
                        if pick < len(pool):
                            picked.append(pool[pick][1])
                targets.append(picked)
                labels.append(", ".join(self.label(p) for p in picked) or NO_TARGET)
                continue
            if getattr(effect, "up_to_x", False) or getattr(effect, "any_number", False):
                # "up to X target creatures", "X target creatures", "any number of target creatures": one slot holding a list
                picked: list = []
                picked_labels: list[str] = []
                taken_here = set()
                exact = getattr(effect, "exact_x", False)  # "X target creatures": no stopping early
                limit = self.targeting_x if getattr(effect, "up_to_x", False) else (
                    getattr(effect, "max_targets", 0) or (self.targeting_max if self.targeting_max is not None else MAX_TARGETS))
                for _ in range(limit):
                    pool = [(i, o) for i, o in enumerate(self.target_options(kind, seat, colors)) if i not in taken_here
                            and not (getattr(effect, "another", False) and o[1] is source)]  # "other target creatures"
                    if not pool:
                        break
                    pick = seat.player.choose(TARGET_PROMPT + source_name,
                                              [o[1][0] for o in pool] + ([] if exact else [NO_TARGET]))
                    if pick == len(pool):
                        break
                    taken_here.add(pool[pick][0])
                    picked.append(pool[pick][1][1])
                    picked_labels.append(pool[pick][1][0])
                targets.append(picked)
                labels.append(", ".join(picked_labels) or NO_TARGET)
                continue
            taken = chosen.setdefault(kind, set())
            options = [(i, o) for i, o in enumerate(self.target_options(kind, seat, colors))
                       if not (getattr(effect, "another", False) and o[1] is source)
                       and not (getattr(effect, "same_controller", False) and targets
                                and self.controller_of(o[1]) is not self.controller_of(targets[-1]))
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
              graveyard: GraveyardCast | None = None, prepared: Permanent | None = None, free: bool = False,
              copy: bool = False, bottom_after: bool = False, madness: AlternativeCost | None = None) -> None:
        effects = _effects(card)
        paying = dataclasses.replace(card, mana_cost=graveyard.cost) if graveyard else card
        extra = ""
        if effects and isinstance(effects[0], Modal):
            effects, extra = self._choose_modes(seat, card, effects[0], from_command_zone, casting=True)
        # Alternative costs and kicker are announced before targets are chosen (CR 601.2b-c).
        ways = ([AlternativeCost("Cast without paying its mana cost")] if free else [madness] if madness
                else self._cast_ways(seat, card, from_command_zone, graveyard))
        alternative = ways[0]
        if len(ways) > 1:
            options = [f"Pay {card.mana_cost}" if way is None else way.text for way in ways]
            alternative = ways[seat.player.choose(COST_PROMPT + card.name, options)]
        if alternative and alternative.bestow:  # an Aura spell that must target a creature
            effects = [AttachAura("creature")]
        if alternative and alternative.overload:  # every "target" is "each": no targets
            effects = overloaded_effects(card) or effects
        kicked, kickers = (0, ()) if graveyard else self._choose_kicks(seat, card, effects, from_command_zone, alternative)
        replicated = 0 if graveyard or prepared is not None else self._choose_replicate(seat, card, from_command_zone, kickers, extra, alternative)
        if replicated:
            extra += replicate_cost(card) * replicated
        bought_back = self._choose_buyback(seat, card, from_command_zone, kickers, extra, alternative)
        if bought_back:
            extra += buyback_cost(card) or ""
        effects = kicked_effects(effects, kicked, kickers)
        x = 0  # announced before the targets (CR 601.2b-c): "up to X target creatures" needs it
        if alternative is None and (parse_cost(paying.mana_cost).x or any(c.sacrifice_x for c in additional_costs(card))):
            # casting without paying the mana cost makes X 0; Immoral Bargain has X only in its additional cost
            most = self._max_x(seat, paying, from_command_zone, kickers, extra)
            for effect in effects or []:  # "Exile X target creatures": there have to be X legal targets
                if getattr(effect, "exact_x", False):
                    most = min(most, len(self.target_options(target_kind(effect), seat, source_qualities(card))))
            if x_limited_by_players(card):
                most = min(most, len(self.live_seats()))
            for cost in additional_costs(card):  # "sacrifice X creatures": there have to be X of them
                if cost.sacrifice_x:
                    most = min(most, sum(_permanent_matches(cost.sacrifice, p.card) for p in seat.battlefield))
            choices = self._x_values_with_targets(seat, effects, source_qualities(card), most)
            if not choices:  # nothing could be targeted for any X that can be paid
                return
            x = choices[seat.player.choose(X_PROMPT + card.name, [str(n) for n in choices])]
        elif any(c.life_x for c in additional_costs(card)):  # "pay X life": any amount that leaves you alive
            x = seat.player.choose(LIFE_X_PROMPT + card.name, [str(n) for n in range(max(seat.life, 1))])
        self.targeting_x = x
        strive = strive_cost(card)
        if strive:  # as many targets as the mana will pay for: each one beyond the first costs more
            more = 0
            while more < MAX_TARGETS and self._payment(seat, paying, from_command_zone, x, alternative, kickers,
                                                       extra + strive * (more + 1)) is not None:
                more += 1
            self.targeting_max = more + 1
        chosen_targets = self._choose_targets(seat, effects, card.name, colors=source_qualities(card))
        self.targeting_max = None
        if chosen_targets is None:  # no legal target (a free cast: cascade, suspend ...): it isn't cast, and stays where it is
            self.broadcast({"event": "cant_cast", "seat": seat.index, "card": card.name})
            return
        targets, labels = chosen_targets
        if strive:
            chosen = sum(len(t) for e, t in zip([e for e in effects or [] if target_kind(e)], targets)
                         if getattr(e, "any_number", False))
            extra += strive * max(0, chosen - 1)
        delve = 0
        if alternative is None and not graveyard and has_keyword(card, "delve"):  # exile as few cards as will do
            delve = next(k for k in range(self._delve_max(seat, paying) + 1)
                         if self._payment(seat, paying, from_command_zone, x, alternative, kickers, extra, delve=k) is not None)
        cost = self._cast_cost(seat, paying, from_command_zone, x, alternative, kickers, extra, delve=delve)
        with self._paying_for(seat, paying):
            tapped = self._pay_cost(seat, cost)
        self._spend_mana(seat, tapped)
        spent = cost.generic + len(cost.colored) + len(cost.twobrid) + len(cost.phyrexian)  # "mana spent to cast it"
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
        self._pay_extras(seat, card, alternative, graveyard, x, kicked, bought_back)
        sacrificed = self._sacrifice_for_copies(seat, card)
        item = StackItem(card, seat, effects, targets, x=x, kicked=kicked, kickers=kickers, bought_back=bought_back, exile_after=bool(graveyard and graveyard.exile_after), bottom_after=bottom_after, from_graveyard=graveyard is not None,
                         is_copy=prepared is not None or copy, evoked=bool(alternative and alternative.evoke),
                         escaped=bool(graveyard and graveyard.word == "Escape"),
                         bestowed=bool(alternative and alternative.bestow), mana_spent=spent)
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
        copies = (replicated or 0) + sacrificed
        if (storm := storm_kind(card)) is not None and prepared is None:
            before = [t for s in self.seats for t, _ in s.cast_log if t == self.turn]  # spells cast before this one
            copies += (len(before) - 1) if storm == "storm" else (self.graveyarded_count if self.graveyarded_turn == self.turn else 0)
        if copies and prepared is None:  # Replicate, Storm, Gravestorm: a trigger above the spell copies it
            ability = TriggeredAbility("cast", (CopySpellTimes(copies),), False, "Copy this spell")
            self.stack.append(StackItem(card, seat, list(ability.effects), [], ability, carried=item))
        if has_keyword(card, "demonstrate") and prepared is None:
            ability = TriggeredAbility("cast", (Demonstrate(),), False, "Demonstrate")
            self.stack.append(StackItem(card, seat, list(ability.effects), [], ability, carried=item))
        for ability in triggered_abilities(card):  # "When you cast this spell, ..." (Hydroid Krasis)
            if ability.event == "cast_self" and prepared is None:
                self.stack.append(StackItem(card, seat, list(ability.effects), [], ability, x=x))
        for source in tapped or ():  # Study Hall, Path of Ancestry: "When that mana is spent to cast ..., scry"
            if self._mana_spent_matches(seat, source, card, from_command_zone, tapped):
                if mana_spent_trigger(source.card).counters:  # Opal Palace: it enters with more counters
                    item.rider_counters += 1
                    continue
                scry = mana_spent_trigger(source.card).scry
                count = seat.commander_casts.get(card.name, 0) + 1 if scry == "commander_casts" else scry
                ability = TriggeredAbility("cast", (Scry("X"),), False, f"Scry {count}")
                self.stack.append(StackItem(source.card, seat, list(ability.effects), [], ability, source, x=count))
        if seat.x_rider_turn == self.turn and seat.x_rider_count and "{X}" in card.mana_cost:  # Brass Infiniscope
            ability = TriggeredAbility("cast", (Draw(1), GainLife("hX")), False, "Draw a card and gain half X life")
            for _ in range(seat.x_rider_count):
                self.stack.append(StackItem(card, seat, list(ability.effects), [], ability, x=x))
            seat.x_rider_count = 0
        if has_keyword(card, "cascade") and prepared is None:  # the trigger goes on the stack above the spell
            ability = TriggeredAbility("cast", (Cascade(int(card.cmc) + x),), False, "Cascade")
            self.stack.append(StackItem(card, seat, list(ability.effects), [], ability))
        if seat.copy_next_turn == self.turn and ("Instant" in card.type_line or "Sorcery" in card.type_line):
            seat.copy_next_turn = None  # a delayed trigger: it copies the spell, with new targets
            copies = sum(seat.commander_casts.values()) if seat.copy_next_per_commander else 1
            if copies:
                ability = TriggeredAbility("cast", (CopySpellTimes(copies),), False, "Copy that spell")
                self.stack.append(StackItem(card, seat, list(ability.effects), [], ability, carried=item))
        self._observe("cast", card, seat, x=x, from_hand=zone is seat.hand and not prepared,
                      prepared=prepared is not None, spell=item, from_graveyard=graveyard is not None)
        if seat.spent_turn != self.turn:
            seat.spent_turn, seat.spent_amount = self.turn, 0
        before, seat.spent_amount = seat.spent_amount, seat.spent_amount + spent
        for total in range(before + 1, seat.spent_amount + 1):  # "Whenever you expend N": the Nth mana spent this turn
            self._observe("expend", card, seat, x=total)
        for target in (t for chosen in item.targets for t in (chosen if isinstance(chosen, list) else [chosen])):
            if isinstance(target, Permanent) and self.on_battlefield(target):  # "Whenever this creature becomes the target of a spell"
                self.trigger("targeted", target, self.controller_of(target))
        self._check_ward(item)

    def _choose_buyback(self, seat: Seat, card: Card, from_command_zone: bool, kickers: tuple[str, ...], extra: str,
                        alternative: AlternativeCost | None) -> bool:
        """Buyback: ask whether to pay it, when the spell has one and it can be paid on top of everything else."""
        mana = buyback_cost(card)
        if mana is None and buyback_other_cost(card) is None:
            return False
        return (self._can_pay_extras(seat, card, alternative, bought_back=True)
                and self._payment(seat, card, from_command_zone, alternative=alternative, kickers=kickers,
                                  extra=extra + (mana or "")) is not None
                and seat.player.choose(BUYBACK_PROMPT + card.name, YES_NO) == 0)

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

    def snapshot(self, viewer: Seat | None) -> dict:
        """The board as `viewer` may see it: everything public, plus their own hand. Opponents' hands and
        libraries show as counts only. A spectator (no viewer) sees no hand at all. It's plain data, ready to send
        as JSON."""
        return {
            "turn": self.turn, "step": self.step, "active": self.active, "you": viewer.index if viewer else -1,
            "stack": [{"card": i.card.name, "seat": i.controller.index, "ability": _shown(i.ability.text, i.card) if i.ability else None}
                      for i in self.stack],
            "hand": [c.name for c in viewer.hand] if viewer else [],
            "seats": [{
                "seat": s.index, "name": s.name, "life": s.life, "poison": s.player_counters.get("poison", 0), "lost": s.lost,
                "mana_pool": ["".join(sorted(u)) for u in s.mana_pool],
                "hand": len(s.hand), "library": len(s.library),
                "graveyard": [c.name for c in s.graveyard], "exile": [c.name for c in s.exile],
                "command_zone": [{"name": c.name, "tax": self.commander_tax(s, c)} for c in s.command_zone],
                "commander_damage": [{"from_seat": seat, "commander": name, "damage": dmg}
                                     for (seat, name), dmg in s.commander_damage.items()],
                "battlefield": [self._permanent_view(p, viewer if viewer is s else None) for p in s.battlefield],
            } for s in self.seats],
        }

    def _permanent_view(self, p: Permanent, owner_viewing: Seat | None = None) -> dict:
        creature = "Creature" in p.card.type_line
        host = p.attached_to
        return {
            "name": p.card.name, "type": shown_type_line(p.card), "tapped": p.tapped, "token": _is_token(p.card),
            "sick": p.sick and creature,
            "power": self.power(p) if creature else None, "toughness": self.toughness(p) if creature else None,
            "damage": p.damage, "loyalty": p.loyalty, "counters": {k: v for k, v in p.counters.items() if v},
            "attached_to": host.card.name if host is not None and self.on_battlefield(host) else None,
            # a manifested card is face down for everyone but the player who controls it
            "face_down_as": p.real_card.name if p.manifested and p.real_card is not None and owner_viewing is not None else None,
        }

    def send_state(self, seat: Seat) -> None:
        """Show the board to a player who wants to see it (TCP players do; bots don't)."""
        if getattr(seat.player, "wants_state", False):
            seat.player.notify({"event": "state", **self.snapshot(seat)})
        if self.spectators:
            board = {"event": "state", **self.snapshot(None)}
            for spectator in self.spectators:
                spectator.notify(board)

    def _resolve(self, item: StackItem) -> None:
        seat, card = item.controller, item.card
        if item.ability:
            self._resolve_ability(item)
            return
        if item.bestowed:
            self._resolve_bestow(item)
            return
        if _is_permanent(card) and aura_kind(card):
            self._resolve_aura(item)
            return
        if _is_permanent(card):
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
            if item.is_copy:  # a copy of a permanent spell becomes a token (CR 707.10f)
                card = dataclasses.replace(card, type_line="Token " + card.type_line.removeprefix("Token "))
            entering = Permanent(card, sick=True, loyalty=_starting_loyalty(card), kicked=item.kicked, kickers=item.kickers,
                                 escaped=item.escaped,
                                 extra_counters=item.rider_counters * seat.commander_casts.get(card.name, 0))
            if item.evoked:  # queued first, so it resolves after the creature's own "when it enters" abilities
                self._queue(EVOKE_SACRIFICE, entering, seat)
            self._enter(seat, entering, x=item.x)
            return
        if item.effects is None:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "unsupported": True})
            if not item.is_copy:
                self._finish_spell(item)
            return
        resolved = self._apply_effects(item)  # fizzled or not, the spell goes to the graveyard (or exile, after flashback)
        if item.suspend_after and not item.is_copy:  # "Exile it with three time counters on it"
            seat.exile.append(card)
            seat.suspended.append([card, item.suspend_after])
            self.broadcast({"event": "suspended", "seat": seat.index, "card": card.name, "counters": item.suspend_after})
        elif not item.is_copy:
            self._finish_spell(item, resolved)

    def _finish_spell(self, item: StackItem, resolved: bool = True) -> None:
        """A resolved instant or sorcery goes to its graveyard; exiled after flashback; or, cast with Quintorius, to the bottom of
        its owner's library. One that was bought back returns to its owner's hand, but only if it resolved."""
        if item.bought_back and resolved:
            self.broadcast({"event": "buyback", "seat": item.controller.index, "card": item.card.name})
            self._move_card(item.controller, item.card, "hand")
            return
        if item.bottom_after and item.card.name not in item.controller.commander_names:
            item.controller.library.append(item.card)
            return
        self._move_card(item.controller, item.card, "exile" if item.exile_after else "graveyard")

    def _resolve_bestow(self, item: StackItem) -> None:
        """A bestow spell enters attached to its creature as an Aura. If that creature is no longer a legal target,
        it resolves as a creature spell instead (CR 702.103e)."""
        seat, card = item.controller, item.card
        target = item.targets[0] if item.targets else None
        aura = bestow_aura(card)
        self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
        if target is not None and self.is_legal_target("creature", target, seat, source_qualities(card)):
            self._enter(seat, Permanent(aura, sick=True, attached_to=target, bestowed_from=card, kicked=item.kicked))
            self.broadcast({"event": "attached", "card": card.name, "to": target.card.name})
        else:
            self._enter(seat, Permanent(card, sick=True), x=item.x)

    def _resolve_aura(self, item: StackItem) -> None:
        """An Aura spell enters attached to its target, or goes to the graveyard if the target
        is no longer legal (CR 608.3b)."""
        seat, card = item.controller, item.card
        target = item.targets[0] if item.targets else None
        if target is None or not self.is_legal_target(aura_kind(card), target, seat, source_qualities(card)):
            self.broadcast({"event": "fizzle", "seat": seat.index, "card": card.name})
            if not item.is_copy:
                self._move_card(seat, card, "graveyard")
            return
        if item.is_copy:  # a copy of an Aura spell becomes a token Aura
            card = dataclasses.replace(card, type_line="Token " + card.type_line.removeprefix("Token "))
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
                self._left_graveyard(seat, [card])
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

    def may_attach(self, seat: Seat, attachment: Permanent, creature: Permanent) -> None:
        """ "You may attach it to the token.": asked, then the Aura moves."""
        if seat.player.choose(ATTACH_PROMPT + attachment.card.name, YES_NO) == 0:
            self.attach(attachment, creature)

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
        if condition and not self.condition_holds(condition, seat, item.source, item.x, item.player):  # checked again on resolution (CR 603.4)
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
        if kind == "auras_on_creatures":
            return sum(1 for p in controller.battlefield if "Aura" in p.card.type_line and p.attached_to is not None
                       and "Creature" in p.attached_to.card.type_line)
        if kind == "auras_on_subject":  # Hateful Eidolon: the Auras you controlled that were attached to the creature that died
            subject = self.resolving_item.subject if self.resolving_item is not None else None
            return subject.last_auras.get(controller.index, 0) if subject is not None else 0
        if kind == "creatures_entered":  # nontoken creatures that entered under your control this turn
            return controller.creatures_entered if controller.creatures_entered_turn == self.turn else 0
        if kind == "sacrificed_power":  # the creature sacrificed to pay this ability's cost
            return self.resolving_item.sacrificed_power if self.resolving_item else 0
        if kind == "tapped_power":  # the creature tapped to pay this ability's cost (Station)
            return self.resolving_item.tapped_power if self.resolving_item else 0
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
        if kind == "life_lost":
            return controller.life_lost_amount if controller.life_lost_turn == self.turn else 0
        if kind == "life_gained":
            return controller.life_gained_amount if controller.life_gained_turn == self.turn else 0
        if kind == "spells_cast":
            return len(this_turn)
        if kind == "one_plus_spells":  # Rionya: one plus the instant and sorcery spells you've cast this turn
            return 1 + sum(_watch_type_matches(amount.what, c) for c in this_turn)
        if kind == "greatest_mana_value_cast":
            return int(max((c.cmc for c in this_turn if _watch_type_matches(amount.what, c)), default=0))
        if kind == "opponents":
            return len(self.opponents(controller))
        if kind == "spell_colors":  # Mana Cannons: the spell that set off this trigger
            spell = self.resolving_item.carried if self.resolving_item is not None else None
            return len(spell.card.colors) if isinstance(spell, StackItem) else 0
        if kind == "graveyards_same_name":  # Aven Shrine
            spell = self.resolving_item.carried if self.resolving_item is not None else None
            return sum(c.name == spell.card.name for s in self.seats for c in s.graveyard) if isinstance(spell, StackItem) else 0
        if kind == "hand_size":
            return len(controller.hand)
        if kind in ("player_hand", "player_hand_minus"):  # the player the trigger is about (Price of Knowledge, Viseling)
            who = self.resolving_item.player if self.resolving_item is not None else None
            return max(0, len(who.hand) - int(amount.what or 0)) if who is not None else 0
        if kind == "spell_mana_value":  # Renegade Bull: the spell that set off this trigger
            spell = self.resolving_item.carried if self.resolving_item is not None else None
            return int(spell.card.cmc) + spell.x if isinstance(spell, StackItem) else 0
        if kind == "mana_spent":  # on the spell that set off this trigger; a copy of a spell was never cast
            spell = self.resolving_item.carried if self.resolving_item is not None else None
            return spell.mana_spent if isinstance(spell, StackItem) else 0
        raise ValueError(f"unknown amount {kind}")

    def amount(self, value: int | str) -> int:
        """A number from an effect; "X" is the resolving spell's X, "2X" twice it."""
        if value == "hX":  # half X, rounded down (Hydroid Krasis, The Goose Mother)
            return self.x_value // 2
        if value == "hX+":  # ... rounded up
            return (self.x_value + 1) // 2
        return self.x_value if value == "X" else 2 * self.x_value if value == "2X" else value

    def _apply_effects(self, item: StackItem) -> bool:
        """Do a spell's or ability's effects; False if it fizzled because every target was gone (CR 608.2b)."""
        self.x_value, self.resolving_source = item.x, item.source
        self.resolving_item, self.resolving_colors = item, source_qualities(item.card)
        try:
            return self._apply_effects_now(item)
        finally:
            self.x_value, self.resolving_source = 0, None
            self.resolving_item, self.resolving_colors = None, frozenset()
            self.resolving_target = None

    def _apply_effects_now(self, item: StackItem) -> bool:
        seat = item.controller
        colors = source_qualities(item.card)
        declared = {}  # a target list that had targets when the spell was put on the stack
        for index, (e, t) in enumerate(zip([e for e in item.effects if target_kind(e)], item.targets)):
            if getattr(e, "multi_target", False):  # keep only the targets that are still legal
                declared[index] = bool(t)
                item.targets[index] = [p for p in t if self.is_legal_target(target_kind(e), p, seat, colors)]
        legal = [(index in declared and (not declared[index] or bool(t)))  # a list with none chosen still resolves
                 or (t is None and getattr(e, "optional_target", False))
                 or (index not in declared and self.is_legal_target(self._fixed_kind(target_kind(e), item.source, item.x), t, seat, colors))
                 for index, (e, t) in enumerate(zip([e for e in item.effects if target_kind(e)], item.targets))]
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
            self.resolving_target = previous
            effect.resolve(self, seat, target)
        return True

    # --- triggered abilities -------------------------------------------------

    def trigger(self, event: str, permanent: Permanent, controller: Seat, subject: Permanent | None = None,
                player: Seat | None = None, x: int = 0, spell: "StackItem | Card | None" = None) -> None:
        """Note that `permanent`'s abilities for `event` triggered; they go on the stack
        the next time a player would get priority (CR 603.3)."""
        if self.loses_abilities(permanent):
            return
        for ability in triggered_abilities(permanent.card):
            if ability.event == event and ability.watch is None:
                if any(isinstance(e, ReturnThisFromGraveyard) for e in ability.effects) and self.on_battlefield(permanent):
                    continue  # it only works from the graveyard (Squee)
                for _ in range(self._trigger_times(controller, event, permanent.card, source=permanent)):
                    self._queue(ability, permanent, controller, x=x, subject=subject, player=player, spell=spell)

    def _trigger_each(self, event: str, seat: Seat, subject: Permanent | None = None,
                      player: Seat | None = None, spell: "StackItem | Card | None" = None) -> None:
        """`event` happened for `seat`: every permanent it controls with an ability for it triggers. `subject` is
        the permanent it happened to, `player` the player who did it, `spell` the spell (or card) involved."""
        for permanent in list(seat.battlefield):
            self.trigger(event, permanent, seat, subject, player, spell=spell)

    def _searched(self, seat: Seat) -> None:
        """`seat` searched their library (found something or not)."""
        for opponent in self.opponents(seat):
            self._trigger_each("opponent_search", opponent, player=seat)

    def _discarded(self, seat: Seat, card: Card | None = None, together: bool = False) -> None:
        """`seat` discarded a card: "Whenever you discard a card" and "Whenever an opponent discards a card". Cards
        discarded `together` set off "one or more nonland cards" once, which the caller reports (_discarded_nonland)."""
        self._trigger_each("discard", seat, spell=card)
        if not together and card is not None:
            self._discarded_nonland(seat, [card])
        self._trigger_each("cycle_or_discard", seat)
        for opponent in self.opponents(seat):
            self._trigger_each("opponent_discard", opponent, player=seat)

    def _discarded_nonland(self, seat: Seat, cards: list[Card]) -> None:
        """"Whenever you discard one or more nonland cards": once, carrying the nonland cards among those discarded."""
        if nonland := tuple(c for c in cards if "Land" not in c.type_line):
            self._trigger_each("discard_nonland", seat, spell=nonland)

    def _queue(self, ability: TriggeredAbility, permanent: Permanent, controller: Seat, x: int = 0,
               subject: Permanent | None = None, player: Seat | None = None, spell: "StackItem | None" = None) -> None:
        if ability.condition and not self.condition_holds(ability.condition, controller, permanent, x, player):
            return
        if ability.once_per_turn:  # "This ability triggers only once each turn."
            if permanent.triggered_turn.get(ability.text) == self.turn:
                return
            permanent.triggered_turn[ability.text] = self.turn
        self.pending.append(PendingTrigger(ability, permanent, controller, x, subject, player, spell=spell))

    def condition_holds(self, condition: Condition, seat: Seat, source: Permanent | None = None, x: int = 0,
                        player: Seat | None = None) -> bool:
        """Whether an intervening "if" clause is true for `seat`, the ability's controller, and `source`. `x` is the
        number the event carried (how many attackers went at the controller, for "two or more of those creatures");
        `player` is the player the trigger is about ("that player")."""
        kind = condition.kind
        if condition.also is not None and not self.condition_holds(condition.also, seat, source, x, player):
            return False
        if kind == "all_hands_empty":  # Howltooth Hollow
            return not any(s.hand for s in self.live_seats())
        if kind == "creature_power_at_least":  # Mosswort Bridge: creatures you control have total power N or greater
            return sum(self.power(p) for p in seat.battlefield if "Creature" in p.card.type_line) >= condition.count
        if kind == "any_library_at_most":  # Shelldock Isle
            return any(len(s.library) <= condition.count for s in self.live_seats())
        if kind == "opponent_damage_at_least":  # Spinerock Knoll: one opponent was dealt that much this turn
            return any(o.damage_taken_turn == self.turn and o.damage_taken >= condition.count for o in self.opponents(seat))
        if kind == "attacked_with_at_least":  # Windbrisk Heights: that many creatures in one combat this turn
            return seat.attackers_turn == self.turn and seat.most_attackers >= condition.count
        if kind == "source_counters_at_least":  # a Planet's "12+ |" abilities: that many counters of the kind on it
            return source is not None and source.counters.get(condition.what, 0) >= condition.count
        if kind == "in_graveyard":  # Anger: "As long as this card is in your graveyard"
            return source is not None and any(c is source.card for c in seat.graveyard)
        if kind == "has_exiled_with":  # Currency Converter, Quintorius: "a card exiled with this"
            return source is not None and any(any(c is card for c in owner.exile) for owner, card in source.exiled_with)
        if kind == "x_at_least":  # Kinetic Ooze: the X the resolving spell or ability carries
            return self.x_value >= condition.count
        if kind == "attackers_at_most":
            return x <= condition.count
        if kind == "defender_more_life":  # Breena: x is the seat attacked; it has more life than another of the opponents
            defender = self.seats[x]
            return any(defender.life > other.life for other in self.opponents(seat) if other is not defender)
        if kind == "land_entered":
            return seat.land_entered_turn == self.turn
        if kind == "lands_prime":
            return sum("Land" in p.card.type_line for p in seat.battlefield) in _PRIMES
        if kind == "source_not_token":  # Life of the Party: its copies don't copy themselves again
            return source is not None and not _is_token(source.card)
        if kind == "control_no_other":  # Lone Revenant
            return not any("Creature" in p.card.type_line and p is not source for p in seat.battlefield)
        if kind == "player_cast_none":  # "that player didn't cast a creature spell this turn" (Predatory Advantage)
            return player is not None and not any(
                turn == self.turn and _watch_type_matches(condition.what, c) for turn, c in player.cast_log)
        if kind == "player_hand_at_most":
            return player is not None and len(player.hand) <= condition.count
        if kind == "attackers_at_least":
            return x >= condition.count
        if kind == "control_none_keyword":  # Jadar: "you control no creatures with decayed"
            return not any("Creature" in p.card.type_line and self.has_keyword(p, condition.what) for p in seat.battlefield)
        if kind == "opponent_life_at_most":  # Bloodghast
            return any(o.life <= condition.count for o in self.opponents(seat))
        if kind == "modified_died":
            return seat.modified_died_turn == self.turn
        if kind == "control_no_other":
            return not any(_has_type(p.card, condition.what) for p in seat.battlefield if p is not source)
        if kind == "eminence":  # the watcher is only looked for on the battlefield and in the command zone
            return True
        if kind == "kicked":  # "if it was kicked (with its {R} kicker)"
            return source is not None and bool(source.kicked) and (not condition.what or condition.what in source.kickers)
        if kind == "graveyard_left":
            return seat.graveyard_left_turn == self.turn
        if kind == "gained_life":
            return seat.life_gained_turn == self.turn
        if kind == "opponent_more_lands":
            lands = lambda s: sum(is_land(p.card) for p in s.battlefield)
            return any(lands(o) > lands(seat) for o in self.opponents(seat))
        if kind == "player_more_lands":  # Archaeomancer's Map: the player whose land entered
            lands = lambda s: sum(is_land(p.card) for p in s.battlefield)
            return player is not None and lands(player) > lands(seat)
        if kind == "opponent_dealt_noncombat_damage":  # Whiplash Wordsmith
            return any(o.noncombat_damage_turn == self.turn for o in self.opponents(seat))
        if kind == "spell_mv_at_least":  # Prismari Pianist: "if that spell's mana value is 5 or greater" (the spell that set it off)
            spell = self.resolving_item.carried if self.resolving_item is not None else None
            return isinstance(spell, StackItem) and int(spell.card.cmc) + spell.x >= condition.count
        if kind == "target_power_at_least":  # Yavimaya Bloomsage: "if that creature has power 7 or greater"
            target = self.resolving_target
            return isinstance(target, Permanent) and self.on_battlefield(target) and self.power(target) >= condition.count
        if kind == "opponent_more_creatures":  # Emeritus of Truce
            creatures = lambda s: sum("Creature" in p.card.type_line for p in s.battlefield)
            return any(creatures(o) > creatures(seat) for o in self.opponents(seat))
        if kind == "cast_this_turn":
            return any(turn == self.turn and _watch_type_matches(condition.what, c) for turn, c in seat.cast_log)
        if kind == "no_counter":  # "if it had no -1/-1 counters on it": what it had when it left
            return source is None or source.counters.get(condition.what, 0) == 0
        if kind == "your_turn":
            return self.active == seat.index
        if kind == "monarch":
            return self.monarch is seat
        if kind == "source_no_counters":
            return source is not None and source.counters.get(condition.what, 0) == 0
        if kind == "source_counters_at_least":
            return source is not None and source.counters.get(condition.what, 0) >= condition.count
        if kind == "monarch_at_turn_start":
            return self.monarch_at_turn_start is seat
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
        if kind == "citys_blessing":
            return seat.citys_blessing
        if kind == "source_tapped":
            return source is not None and source.tapped
        if kind == "not_prepared":
            return source is not None and not source.prepared
        if kind == "graveyard_at_least":
            return sum(_card_matches(condition.what, c) for c in seat.graveyard) >= condition.count
        if kind == "any_hand_at_most":
            return any(len(s.hand) <= condition.count for s in self.live_seats())
        if kind == "opponent_more_cards":
            return any(len(o.hand) > len(seat.hand) for o in self.opponents(seat))
        if kind == "control_none_token":  # Pest Rescuer: "you don't control a Pest creature token"
            return not any(_is_token(p.card) and "Creature" in p.card.type_line and _has_type(p.card, condition.what)
                           for p in seat.battlefield)
        matching = sum(_has_type(p.card, condition.what) for p in seat.battlefield)
        return matching >= condition.count if kind == "control_at_least" else matching == 0

    def _observe(self, event: str, card: Card, seat: Seat, subject: Permanent | None = None,
                 extra: list[tuple[Permanent, Seat]] = (), x: int = 0, from_hand: bool = False,
                 prepared: bool = False, spell: "StackItem | None" = None, from_graveyard: bool = False) -> None:
        """Trigger abilities that watch for `event` happening to `card` (controlled by `seat`):
        "Whenever another creature enters", landfall, "whenever a creature dies",
        "whenever you cast a spell". `extra` adds watchers that just left the battlefield
        and still "look back in time" (CR 603.10a). Event "copy" is a spell being copied, which only a
        "cast or copy" watcher (magecraft) notices."""
        watchers = [(p, s) for s in self.live_seats() for p in s.battlefield] + list(extra)
        # Eminence abilities (Edgar Markov) also work from the command zone, where a card is no Permanent.
        eminent = [(Permanent(c), s) for s in self.live_seats() for c in s.command_zone]
        # A few cards watch from the graveyard (Vanguard of the Restless), where a card is no Permanent either.
        buried = [(Permanent(c), s) for s in self.live_seats() for c in s.graveyard]
        for watcher, watcher_seat in watchers + eminent + buried:
            in_command_zone = any(watcher is p for p, _ in eminent)
            in_graveyard = any(watcher is p for p, _ in buried)
            if self.loses_abilities(watcher):
                continue
            for ability in triggered_abilities(watcher.card):
                watch = ability.watch
                if not watch or ability.event != ("cast" if event == "copy" else event):
                    continue
                if in_command_zone and not ability.text.startswith("Eminence"):
                    continue
                if in_graveyard and not any(isinstance(effect, (PayToReturnSelf, ReturnThisFromGraveyard)) for effect in ability.effects):
                    continue
                if watch.other and event in ("cast", "copy") and card is watcher.card:
                    continue  # "another" spell: not the one that has this ability
                if event == "copy" and not watch.with_copy:
                    continue
                if event in ("cast", "copy") and (card.cmc < watch.mv_at_least or (watch.from_hand and not from_hand)):
                    continue
                if event in ("cast", "copy") and ((watch.from_zone == "graveyard" and not from_graveyard)
                                                  or (watch.from_zone == "not_hand" and from_hand)):
                    continue
                if watch.qualifier == "targets_modified":  # a cast of a spell that targets a modified permanent you control
                    if not self._targets_modified(spell, watcher_seat):
                        continue
                elif watch.qualifier == "targets_only_source":  # Mirrorwing Dragon: the spell targets only the watcher
                    flat = [t for target in (spell.targets if isinstance(spell, StackItem) else [])
                            for t in (target if isinstance(target, list) else [target])]
                    if not flat or any(t is not watcher for t in flat):
                        continue
                elif watch.qualifier and (subject is None or not self._qualifies(watch.qualifier, subject)):
                    continue
                if watch.batch and self._batch is not None:  # "one or more": once for everything that happened together
                    if (id(watcher), id(ability)) in self._batch:
                        continue
                    self._batch.add((id(watcher), id(ability)))
                if event == "expend" and watch.expend != x:  # x is the total the spell took the count up to
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
                if watch.not_starting_deck and not card.conjured:
                    continue
                if watch.kind == "prepared spell":  # cast as a prepared creature's spell, whatever kind of spell it is
                    if not prepared:
                        continue
                elif not _watch_type_matches(watch.kind, card):
                    continue
                if watch.nth_each_turn and sum(turn == self.turn and _watch_type_matches(watch.kind, c)
                                               for turn, c in seat.cast_log) != watch.nth_each_turn:
                    continue
                for _ in range(self._trigger_times(watcher_seat, event, card, seat, source=watcher)):
                    self._queue(ability, watcher, watcher_seat, x, subject, seat, spell)

    def _is_modified(self, permanent: Permanent, controller: Seat | None = None) -> bool:
        """CR 700.9: it has a counter, or an Equipment or an Aura its controller controls is attached to it."""
        controller = controller or self.controller_of(permanent)
        return bool(permanent.counters and any(permanent.counters.values())) or any(
            a.attached_to is permanent and self.controller_of(a) is controller
            and ("Equipment" in a.card.type_line or "Aura" in a.card.type_line)
            for s in self.live_seats() for a in s.battlefield)

    def _targets_modified(self, spell: "StackItem | Card | None", seat: Seat) -> bool:
        """Whether the spell targets a modified permanent that `seat` controls (Pearl-Ear)."""
        targets = spell.targets if isinstance(spell, StackItem) else []
        flat = [t for target in targets for t in (target if isinstance(target, list) else [target])]
        return any(isinstance(t, Permanent) and self.on_battlefield(t) and self.controller_of(t) is seat and self._is_modified(t, seat)
                   for t in flat)

    def _qualifies(self, qualifier: str, permanent: Permanent) -> bool:
        """A watch's "with power 4 or greater" / "with flying" / "with a +1/+1 counter on it": for a creature that is
        gone (it died), what it last was."""
        here = self.on_battlefield(permanent)
        if m := re.fullmatch(r"(power|toughness)(>=|<=)(\d+)", qualifier):
            if m[1] == "power":
                value = self.power(permanent) if here else permanent.last_power
            else:  # a gone creature's toughness: its printed one plus counters, the last known information
                value = self.toughness(permanent) if here else int(permanent.card.toughness or 0) + permanent.counters.get("+1/+1", 0)
            return value >= int(m[3]) if m[2] == ">=" else value <= int(m[3])
        if qualifier.startswith("mv<="):
            return permanent.card.cmc <= int(qualifier.removeprefix("mv<="))
        if qualifier == "enchanted":  # "an enchanted creature dies": it had an Aura on it (as it died, if it is gone)
            if here:
                return any(p.attached_to is permanent and "Aura" in p.card.type_line for s in self.seats for p in s.battlefield)
            return any(permanent.last_auras.values())
        if qualifier == "flying":
            return self.has_keyword(permanent, "flying") if here else has_keyword(permanent.card, "flying")
        return permanent.counters.get(qualifier.removeprefix("counter:"), 0) > 0

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
                effects, _ = self._choose_modes(seat, trigger.source, effects[0], source=trigger.permanent)
                if not effects:
                    continue
            self.targeting_x = trigger.x  # "mana value X or less, where X is the damage dealt" (Venerable Warsinger)
            try:
                chosen = self._choose_targets(seat, effects, trigger.source.name, trigger.permanent,
                                              source_qualities(trigger.source))
            finally:
                self.targeting_x = 0
            if chosen is None:
                continue
            targets, labels = chosen
            item = StackItem(trigger.source, seat, effects, targets, trigger.ability,
                             trigger.permanent, x=trigger.x, subject=trigger.subject, player=trigger.player,
                             carried=trigger.spell)
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
        limit = re.search(r" with mana value (\d+|x)(?: or (less|greater))?$", kind)  # "creature ... with mana value 3 or less"
        if limit:
            kind = kind[:limit.start()]
            value = int(limit[1]) if limit[1] != "x" else self.x_value if self.resolving_item is not None else self.targeting_x
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
                if controller == "own" and (permanent.owner or seat) is not caster:
                    continue
                if attacked and permanent.attacked_turn != self.turn:
                    continue
                if limit and (card.cmc > value if limit[2] == "less" else card.cmc < value if limit[2] == "greater"
                              else card.cmc != value):
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
        if amount > 0:  # Pest Rescuer: "you gain that much life plus 1 instead"
            amount += sum(replacement_effects(p.card).life_gain_plus for p in seat.battlefield)
        seat.life += amount
        self.broadcast({"event": "life", "seat": seat.index, "change": amount, "life": seat.life})
        if amount:  # "Whenever you gain life" / "Whenever you lose life": once per event, not per point
            first_loss = amount < 0 and seat.life_lost_turn != self.turn
            first_gain = amount > 0 and seat.life_gained_turn != self.turn
            if amount < 0:
                if seat.life_lost_turn != self.turn:
                    seat.life_lost_amount = 0
                seat.life_lost_amount -= amount
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
        infect = source is not None and self.has_keyword(source, "infect")  # to a player: poison counters; to a creature: wither
        wither = infect or (source is not None and self.has_keyword(source, "wither"))
        if isinstance(target, Seat) and combat and target.combat_shield_turn == self.turn:  # Inkshield
            self.broadcast({"event": "damage_prevented", "seat": target.index, "amount": amount})
            if target.combat_shield_token is not None and amount > 0:
                self.create_tokens(target, target.combat_shield_token, amount)
            return
        if isinstance(target, Seat):
            if amount > 0 and not combat:
                target.noncombat_damage_turn = self.turn
            if amount > 0:
                target.damage_taken = (target.damage_taken if target.damage_taken_turn == self.turn else 0) + amount
                target.damage_taken_turn = self.turn
            if infect:
                self.give_poison(target, amount)
            else:
                self.change_life(target, -amount)
            if combat and amount > 0 and source is not None and not self.loses_abilities(source) \
                    and (toxic := toxic_of(source.card)):
                self.give_poison(target, toxic)  # Toxic N: that many poison counters in addition to the damage
            if combat and controller:
                self.trigger("combat_damage_to_player", source, controller, x=amount)
                if target is self.monarch and controller is not target:  # CR 725.2
                    self.become_monarch(controller)
                if target is self.initiative and controller is not target:  # CR 726.2
                    self.take_initiative(controller)
                for holder in self.live_seats():  # "Whenever equipped (enchanted) creature deals combat damage to a player"
                    for attachment in list(holder.battlefield):
                        if attachment.attached_to is source:
                            self.trigger("host_combat_damage", attachment, holder, source, player=target)
                if controller.surge is not None and controller.surge[0] == self.turn:  # Surge to Victory
                    self._queue(TriggeredAbility("ally_combat_damage", (CastExiledCopy(controller.surge[1]),), True,
                                                 "Surge to Victory"), source, controller)
                for watched, watcher, effect in list(self.combat.damage_watches):  # "Whenever that creature deals ... this combat"
                    if watched is source and self.on_battlefield(watcher):
                        self._queue(TriggeredAbility("ally_combat_damage", (effect.then,), False, effect.text), watcher,
                                    self.controller_of(watcher))
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
                if wither and amount > 0:
                    self.put_counters(target, MINUS, amount)  # CR 702.80, 702.90: -1/-1 counters, not marked damage
                else:
                    target.damage += amount
                if source and self.has_keyword(source, "deathtouch"):
                    target.deathtouched = True
            if target.loyalty is not None:
                target.loyalty -= amount
            self.broadcast({"event": "damage", "card": target.card.name, "amount": amount,
                            "source": source.card.name if source else None})
        if controller and self.has_keyword(source, "lifelink"):
            self.change_life(controller, amount)

    def give_poison(self, seat: Seat, count: int) -> None:
        if count > 0:
            seat.player_counters["poison"] = seat.player_counters.get("poison", 0) + count
            self.broadcast({"event": "poison", "seat": seat.index, "added": count, "total": seat.player_counters["poison"]})

    def prevent_combat_damage(self, seat: Seat, token: Card | None) -> None:
        """Inkshield: no combat damage is dealt to `seat` this turn; `token` is created for each point prevented."""
        seat.combat_shield_turn, seat.combat_shield_token = self.turn, token
        self.broadcast({"event": "combat_shield", "seat": seat.index})

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
        loses all damage and is removed from combat (CR 701.19a)."""
        if permanent.regeneration <= 0:
            return False
        permanent.regeneration -= 1
        self.tap(permanent)
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
        limit = re.search(r" with mana value (\d+)(?: or (less|greater))?$", kind)  # "nonland permanent with mana value 2 or less"
        if limit:
            kind = kind[:limit.start()]
        kind, controller = _split_controller(kind)
        found: list[Permanent] = []
        for seat in self.live_seats():
            if (controller == "opponent" and seat is caster) or (controller == "you" and seat is not caster):
                continue
            found += [p for p in seat.battlefield
                      if _permanent_matches(kind, p.card) and self._passes(p, restriction)
                      and not (limit and (p.card.cmc > int(limit[1]) if limit[2] == "less" else
                                          p.card.cmc < int(limit[1]) if limit[2] == "greater" else p.card.cmc != int(limit[1])))]
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
        if restriction.enchanted is not None and restriction.enchanted != any(
                a.attached_to is permanent and "Aura" in a.card.type_line for seat in self.seats for a in seat.battlefield):
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

    def destroy_all(self, permanents: list[Permanent], no_regen: bool = False, gives: GiveBack | None = None,
                    caster: Seat | None = None) -> list[Permanent]:
        """Destroy them all at once; indestructible ones survive, and so do ones with a regeneration shield
        unless they "can't be regenerated". `gives`: tokens for what was destroyed (see _give_back). Returns what was destroyed."""
        doomed = [p for p in permanents if not self.has_keyword(p, "indestructible")
                  and (no_regen or not self._regenerated(p))]
        self._leave_together([(p, "destroyed") for p in doomed])
        self._give_back(doomed, gives, caster)
        return [p for p in doomed if not self.on_battlefield(p)]

    def exile_all(self, permanents: list[Permanent], gives: GiveBack | None = None, caster: Seat | None = None) -> None:
        self._leave_together([(p, "exiled") for p in permanents], destination="exile")
        self._give_back(permanents, gives, caster)

    def _give_back(self, gone: list[Permanent], gives: GiveBack | None, caster: Seat | None) -> None:
        """"For each creature destroyed this way, its controller creates a token": for each one that left. Ceaseless
        Conflict pays only `caster`, for their own nontoken creatures; Oversimplify gives every player one token with a
        +1/+1 counter per point of power (as it last was) of the creatures they lost."""
        if gives is None:
            return
        left = [p for p in gone if p.last_controller is not None and not self.on_battlefield(p)
                and not (gives.nontoken and _is_token(p.card))]
        if gives.who == "each player":
            for seat in self.turn_order_from_active():
                power = sum(p.last_power for p in left if p.last_controller is seat) if gives.power_counters else 0
                self.create_tokens(seat, gives.token, gives.count, (power, "+1/+1") if power else None)
            return
        for permanent in left:
            if gives.who == "you" and permanent.last_controller is not caster:
                continue
            self.create_tokens(caster if gives.who == "you" else permanent.last_controller, gives.token, gives.count)

    def return_to_hand(self, permanent: Permanent) -> None:
        """Bounce: a permanent goes to its owner's hand (a token just stops existing)."""
        self._leave_together([(permanent, "returned")], destination="hand")

    def return_all_to_hand(self, permanents: list[Permanent]) -> None:
        self._leave_together([(p, "returned") for p in permanents], destination="hand")

    def return_from_graveyard(self, target: GraveyardTarget, controller: Seat, to: str, tapped: bool = False,
                              finality: bool = False) -> None:
        """Move a card out of a graveyard to its owner's hand, or onto the battlefield under
        `controller`'s control (it stays its owner's card)."""
        seat, card = target.seat, target.card
        if card not in seat.graveyard:
            return
        seat.graveyard.remove(card)
        self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": to})
        self._left_graveyard(seat, [card])
        if to == "hand":
            seat.hand.append(card)
        elif to in ("library_top", "library_bottom"):
            seat.library.insert(0, card) if to == "library_top" else seat.library.append(card)
        elif finality:
            self._enter(controller, self._finality_spirit(card, seat))
        else:
            self._enter(controller, Permanent(card, sick=True, tapped=tapped, loyalty=_starting_loyalty(card), owner=seat))

    def _finality_spirit(self, card: Card, owner: Seat) -> Permanent:
        """Excava, the Risen Past: the card returns with a finality counter, as a 1/1 Spirit creature with flying in addition to its
        other types. It is still the same card when it leaves (`real_card`)."""
        head, dash, tail = card.type_line.partition("\u2014")
        types = head.split()
        if "Creature" not in types:
            types.append("Creature")
        became = dataclasses.replace(card, power="1", toughness="1", type_line=" ".join(types) + f" {dash} {tail.strip()} Spirit".rstrip()
                                     if dash else " ".join(types) + " \u2014 Spirit",
                                     oracle_text=(card.oracle_text + "\nFlying").strip())
        return Permanent(became, sick=True, owner=owner, real_card=card, counters={"finality": 1})

    def return_all_from_graveyard(self, seat: Seat, kind: str, to: str) -> None:
        """"Return all enchantment cards from your graveyard to the battlefield.": they all come back at once."""
        for card in [c for c in seat.graveyard if _card_matches(kind, c)]:
            self.return_from_graveyard(GraveyardTarget(card, seat), seat, to)

    def graveyard_target(self, card: Card, seat: Seat) -> "GraveyardTarget":
        return GraveyardTarget(card, seat)

    def _graveyard_of(self, card: Card) -> Seat | None:
        return next((s for s in self.seats if any(c is card for c in s.graveyard)), None)

    def return_dead_to_battlefield(self, dead: Permanent, controller: Seat, under_owner: bool, tapped: bool = False) -> None:
        """A creature that just died comes back from its owner's graveyard, under `controller`'s control unless
        `under_owner`."""
        holder = self._graveyard_of(dead.card)
        if holder is not None:
            self.return_from_graveyard(GraveyardTarget(dead.card, holder), holder if under_owner else controller,
                                       "battlefield", tapped)

    def look_take(self, seat: Seat, count: int, take: int) -> None:
        """Look at the top `count` cards; `take` of them go to the hand and the rest to the bottom of the library."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        for _ in range(min(take, len(top))):
            card = top.pop(seat.player.choose(SPLIT_HAND_PROMPT, [c.name for c in top]) if len(top) > 1 else 0)
            seat.hand.append(card)
        seat.library.extend(top)

    def three_way_split(self, seat: Seat, count: int, play: bool) -> None:
        """Expressive Iteration: look at the top `count` cards; one to your hand, one to the bottom of your library, one
        exiled (and playable this turn, if `play`)."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        if not top:
            return
        hand = top.pop(seat.player.choose(SPLIT_HAND_PROMPT, [c.name for c in top]) if len(top) > 1 else 0)
        seat.hand.append(hand)
        bottom = top.pop(seat.player.choose(SPLIT_BOTTOM_PROMPT, [c.name for c in top]) if len(top) > 1 else 0) if top else None
        if bottom is not None:
            seat.library.append(bottom)
        for exiled in top:
            self._move_card(seat, exiled, "exile")
            if play and exiled in seat.exile:
                seat.exile_play.append((exiled, self.turn))
        self.broadcast({"event": "split_top", "seat": seat.index, "count": count})

    def manifest(self, seat: Seat) -> None:
        """Manifest the top card of the library: it enters face down as a 2/2 creature with no abilities. A creature card
        can be turned face up (TURN_UP) for its mana cost; it goes to the graveyard as itself."""
        if not seat.library:
            return
        real = seat.library.pop(0)
        face_down = Card(name="Face-down creature", type_line="Creature", power="2", toughness="2")
        self.broadcast({"event": "manifested", "seat": seat.index})
        self._enter(seat, Permanent(face_down, sick=True, real_card=real, manifested=True, owner=seat))

    def _turn_up_options(self, seat: Seat) -> list[Permanent]:
        """Manifested creature cards of `seat` that it can afford to turn face up."""
        return [p for p in seat.battlefield if p.manifested and p.real_card is not None
                and "Creature" in p.real_card.type_line and self._payment(seat, p.real_card) is not None]

    def turn_face_up(self, seat: Seat, permanent: Permanent) -> None:
        self._spend_mana(seat, self._payment(seat, permanent.real_card))
        permanent.card, permanent.real_card, permanent.manifested = permanent.real_card, None, False
        self.broadcast({"event": "turned_face_up", "seat": seat.index, "card": permanent.card.name})

    def dance_with_calamity(self, seat: Seat, limit: int) -> None:
        """Shuffle, exile the top card as many times as you choose; if the total mana value is `limit` or less, cast any
        number of the spells among them for free. Cards not cast stay exiled."""
        self.rng.shuffle(seat.library)
        exiled: list[Card] = []
        while seat.library:
            total = int(sum(c.cmc for c in exiled))
            if seat.player.choose(f"{DANCE_PROMPT}({len(exiled)} exiled, total mana value {total})", YES_NO) != 0:
                break
            card = seat.library.pop(0)
            exiled.append(card)
            self._move_card(seat, card, "exile")
        if exiled and sum(c.cmc for c in exiled) <= limit:
            for card in [c for c in exiled if not is_land(c)]:
                if card in seat.exile and seat.player.choose(DANCE_CAST_PROMPT + card.name, YES_NO) == 0:
                    self._cast(seat, card, seat.exile, free=True)

    def copy_attacking(self, seat: Seat, source: Permanent) -> None:
        """A token that's a copy of `source`, tapped and attacking whom it attacks."""
        attack = next((a for a in self.combat.attacks if a.attacker is source), None)
        card = source.card if _is_token(source.card) else dataclasses.replace(source.card, type_line="Token " + source.card.type_line)
        for made in self.create_tokens(seat, card, 1):
            made.tapped = True
            if attack is not None:
                self.combat.attacks.append(Attack(made, seat, attack.defender, walker=attack.walker))
                self.broadcast({"event": "attack", "seat": seat.index, "card": made.card.name, "defender": attack.defender.index})

    def token_attacking(self, seat: Seat, token: Card, defender: Seat) -> None:
        """A token created for `seat`, tapped and attacking `defender`; it was never declared, so attack triggers don't see it."""
        for made in self.create_tokens(seat, token, 1):
            made.tapped = True
            self.combat.attacks.append(Attack(made, seat, defender))
            self.broadcast({"event": "attack", "seat": seat.index, "card": made.card.name, "defender": defender.index})

    def exile_dead_make_spirit_copy(self, seat: Seat, dead: Permanent) -> None:
        """Hofri Ghostforge: exile the creature that just died from its owner's graveyard; if that works, `seat` creates a token
        that's a copy of it, a Spirit too, which sends the exiled card back to the graveyard when it leaves."""
        owner = dead.owner or dead.last_controller
        if owner is None or not self.exile_from_graveyard(GraveyardTarget(dead.card, owner)):
            return
        card = dead.card
        text = (card.oracle_text + "\nWhen this token leaves the battlefield, return the exiled card to its owner's graveyard.").strip()
        head, dash, tail = card.type_line.partition("\u2014")
        spirit = dataclasses.replace(card, type_line=f"Token {head.strip()} {dash} {tail.strip()} Spirit" if dash else f"Token {head.strip()}",
                                     oracle_text=text)
        for made in self.create_tokens(seat, spirit, 1):
            made.exiled_with.append((owner, card))

    def return_exiled_with_to_graveyard(self, leaver: Permanent) -> None:
        """The exiled card a Hofri Ghostforge token was made from goes to its owner's graveyard."""
        for owner, card in leaver.exiled_with:
            if any(c is card for c in owner.exile):
                owner.exile = [c for c in owner.exile if c is not card]
                self._move_card(owner, card, "graveyard")
        leaver.exiled_with = []

    def copy_entered_tokens_attacking(self, seat: Seat, source: Permanent) -> None:
        """Redoubled Stormsinger: for each creature token `seat` controls that entered this turn, a tapped and attacking copy
        attacks whom `source` attacks; the copies are sacrificed as the next end step begins."""
        attack = next((a for a in self.combat.attacks if a.attacker is source), None)
        originals = [p for p in seat.battlefield if "Creature" in p.card.type_line and _is_token(p.card) and p.entered_turn == self.turn]
        copies = []
        for original in originals:
            for made in self.create_tokens(seat, original.card, 1):
                made.tapped = True
                if attack is not None:
                    self.combat.attacks.append(Attack(made, seat, attack.defender, walker=attack.walker))
                    self.broadcast({"event": "attack", "seat": seat.index, "card": made.card.name, "defender": attack.defender.index})
                copies.append(made)
        if copies:
            self.leave_at_next_end_step(copies, "sacrificed", "graveyard")

    def put_from_hand(self, seat: Seat, kind: str, tapped: bool = False) -> None:
        """"You may put a creature card from your hand onto the battlefield.": you choose one, or none."""
        options = [c for c in seat.hand if _card_matches(kind, c)]
        if not options:
            return
        pick = seat.player.choose(PUT_FROM_HAND_PROMPT, [c.name for c in options] + [DECLINE])
        if pick < len(options):
            card = options[pick]
            seat.hand.remove(card)
            self._enter(seat, Permanent(card, sick=True, tapped=tapped, loyalty=_starting_loyalty(card)))

    def return_chosen(self, seat: Seat, kind: str, to: str) -> None:
        """"Return a creature card from your graveyard to your hand.": you choose, nothing is targeted."""
        options = [c for c in seat.graveyard if _card_matches(kind, c)]
        if not options:
            return
        card = options[0] if len(options) == 1 else options[seat.player.choose(RETURN_CHOSEN_PROMPT, [c.name for c in options])]
        self.return_from_graveyard(GraveyardTarget(card, seat), seat, to)

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
            self._left_graveyard(holder, [card])
            self._enter(controller, Permanent(card, sick=True, attached_to=target, owner=holder))
            self.broadcast({"event": "attached", "card": card.name, "to": target.card.name})

        if when == "now":
            bring_back()
        else:
            fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
            self.at_end_step.append((fire_turn, bring_back))

    def exile_own_graveyard(self, seat: Seat, count: int) -> bool:
        """Exile `count` cards of the player's choice from their graveyard; False (and nothing happens) if they have fewer."""
        if len(seat.graveyard) < count:
            return False
        for _ in range(count):
            card = seat.graveyard[seat.player.choose(EXILE_COST_PROMPT, [c.name for c in seat.graveyard])]
            seat.graveyard.remove(card)
            self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": "exile"})
            self._move_card(seat, card, "exile")
        if count:
            self._left_graveyard(seat)
            self._exiled_from_library_or_graveyard(seat)
        return True

    def shuffle_into_library(self, seat: Seat, targets: list[GraveyardTarget]) -> None:
        """The chosen cards of a graveyard go into their owner's library, which is then shuffled."""
        owners = []
        for target in targets:
            if target.card in target.seat.graveyard:
                target.seat.graveyard.remove(target.card)
                target.seat.library.append(target.card)
                self.broadcast({"event": "left_graveyard", "seat": target.seat.index, "card": target.card.name, "to": "library"})
                owners.append(target.seat)
        for owner in dict.fromkeys(owners):
            self.rng.shuffle(owner.library)
            self._left_graveyard(owner, [t.card for t in targets if t.seat is owner])

    def exile_from_graveyard(self, target: GraveyardTarget) -> bool:
        """Exile the card from its graveyard; whether it was still there."""
        seat, card = target.seat, target.card
        if card not in seat.graveyard:
            return False
        seat.graveyard.remove(card)
        self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": "exile"})
        self._move_card(seat, card, "exile")
        self._note_exiled_with(seat, card)
        self._left_graveyard(seat, [card])
        self._exiled_from_library_or_graveyard(seat)
        return True

    def _note_exiled_with(self, owner: Seat, card: Card) -> None:
        """The card in `owner`'s exile was exiled by the ability that is resolving: "a card exiled with this artifact"."""
        source = self.resolving_source
        if source is not None and not _is_token(card) and any(c is card for c in owner.exile):
            source.exiled_with.append((owner, card))

    def _left_graveyard(self, seat: Seat, cards: list[Card] | tuple = ()) -> None:
        """One or more cards just left `seat`'s graveyard, as one event. `cards` are those that left, when the caller
        knows them (Spirit of Resilience copies one); a cost paid by exiling cards does not say."""
        seat.graveyard_left_turn = self.turn
        for permanent in list(seat.battlefield):
            self.trigger("graveyard_leave", permanent, seat, spell=tuple(cards))

    def _exiled_from_library_or_graveyard(self, seat: Seat) -> None:
        """One or more of `seat`'s cards were just put into exile from its library and/or graveyard, as one event (Laelia)."""
        self._trigger_each("exile_library_graveyard", seat)

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
        elif to == "graveyard":
            self._move_card(seat, found, "graveyard")
        else:
            seat.library.insert(0, found)
        self.broadcast({"event": "searched", "seat": seat.index, "found": True, "to": to,
                        **({"card": found.name} if reveal else {})}, skip=seat)
        seat.player.notify({"event": "searched", "seat": seat.index, "found": True, "to": to, "card": found.name})

    def sacrifice(self, seat: Seat, kind: str = "creature", count: int | None = 1, greatest: bool = False) -> list[Permanent]:
        """`seat` chooses `count` of its permanents of `kind` (a creature, artifact, land, ...) and sacrifices them
        (all of them if `count` is None); with `greatest`, only a creature with the greatest power among its creatures
        can be chosen. No targeting, so hexproof and indestructible don't help. Returns what was sacrificed."""
        state = kind.split(" ")[0] if kind.split(" ")[0] in ("attacking", "tapped", "untapped") else ""
        base = kind.removeprefix(state + " ") if state else kind
        options = [p for p in seat.battlefield if _permanent_matches(base, p.card) and self._in_state(p, state)]
        if count is None:
            self._leave_together([(p, "sacrificed") for p in options])
            return options
        sacrificed = []
        for _ in range(count):
            options = [p for p in options if self.on_battlefield(p)]
            if greatest and options:
                top = max(self.power(p) for p in options)
                options = [p for p in options if self.power(p) == top]
            if not options:
                return sacrificed
            prompt = SACRIFICE_PROMPT if kind == "creature" else f"Choose a {kind} to sacrifice"
            choice = options[seat.player.choose(prompt, [self.label(p) for p in options])]
            self._leave_together([(choice, "sacrificed")])
            sacrificed.append(choice)
        return sacrificed

    # --- characteristics -----------------------------------------------------

    def subtypes(self, permanent: Permanent) -> list[str]:
        """Its creature types: the printed ones, plus those an Aura gives it ("is an Angel in addition")."""
        printed = permanent.card.type_line.partition("—")[2].split()
        added = [buff.subtype for seat in self.seats for a in seat.battlefield if a.attached_to is permanent
                 for buff in attached_abilities(a.card) if buff.subtype]
        return printed + added

    def modifiers(self, permanent: Permanent) -> list[Modifier]:
        """Everything currently changing a permanent: its "until end of turn" effects, plus
        static abilities of permanents its controller controls ("Creatures you control get +1/+1")."""
        controller = self.controller_of(permanent)
        mods = [m for m in permanent.until_end_of_turn + permanent.until_next_turn
                if not m.your_turn or self.seats[self.active] is controller]
        if controller is not None and (cda := power_toughness_amount(permanent.card)) is not None:
            size = self.evaluate(cda, controller)  # Overbeing of Myth: its base power and toughness
            mods = [Modifier(set_pt=(size, size))] + mods
        if controller is None or "Creature" not in permanent.card.type_line:
            return mods
        subtypes = self.subtypes(permanent)
        in_graveyards = [(s, Permanent(c)) for s in self.seats for c in s.graveyard if graveyard_statics(c)]  # Anger
        for owner, source in [(s, p) for s in self.seats for p in s.battlefield] + in_graveyards:
            if self.loses_abilities(source):
                continue
            for buff in static_abilities(source.card):
                if owner is not controller and not buff.everyone:
                    continue
                if buff.plus_counter and not permanent.counters.get("+1/+1"):
                    continue
                if buff.with_counters and not any(permanent.counters.values()):
                    continue
                wanted = source.chosen_type if buff.subtype == "chosen" else buff.subtype
                if wanted == "Commander":  # Guardian Augmenter: not a creature type, a role
                    if _is_token(permanent.card) or not any(permanent.card.name in s.commander_names for s in self.seats):
                        continue
                elif (buff.other and source is permanent) or (wanted and wanted not in subtypes) or (buff.subtype == "chosen" and not wanted):
                    continue
                if buff.self_only and source is not permanent:
                    continue
                if buff.color and buff.color not in permanent.card.colors:
                    continue
                if buff.token and not _is_token(permanent.card):
                    continue
                if buff.attacking and not any(a.attacker is permanent for a in self.combat.attacks):
                    continue
                if buff.condition and not self.condition_holds(buff.condition, owner, source):
                    continue
                mods.append(self._scaled(buff.modifier, buff.per, permanent, controller))
        for seat in self.seats:  # Equipment and Auras attached to it
            for attachment in seat.battlefield:
                if attachment.attached_to is permanent:
                    mods.extend(self._chosen_protection(self._scaled(buff.modifier, buff.per, permanent, controller), attachment)
                                for buff in attached_abilities(attachment.card))
        return mods

    @staticmethod
    def _chosen_protection(modifier: Modifier, attachment: Permanent) -> Modifier:
        """Flickering Ward: "protection from the chosen color" is protection from the color its Aura chose."""
        if PROTECTION_CHOSEN not in modifier.keywords:
            return modifier
        name = {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}.get(attachment.chosen_color or "")
        kept = modifier.keywords - {PROTECTION_CHOSEN}
        return dataclasses.replace(modifier, keywords=kept | ({f"protection from {name}"} if name else set()))

    def _scaled(self, modifier: Modifier, per: tuple[str, str] | None, permanent: Permanent, controller: Seat) -> Modifier:
        """A "for each ..." bonus times how many there are right now."""
        if per is None:
            return modifier
        what, kind = per
        if what == "permanent":
            count = sum(_has_type(p.card, kind) for p in controller.battlefield)
        elif what == "commander_casts":
            count = sum(controller.commander_casts.values())
        elif what == "commander_casts":
            count = sum(controller.commander_casts.values())
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
        if permanent.goad_forever:
            return permanent.goad_forever
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
        mods = self.modifiers(permanent)
        if keyword in ("hexproof", "shroud") and any(LOSES_HEXPROOF in m.keywords for m in mods):
            return False  # Arcane Lighthouse
        printed = has_keyword(permanent.card, keyword) and not self.loses_abilities(permanent)
        return printed or any(keyword in m.keywords for m in mods)

    def loses_abilities(self, permanent: Permanent) -> bool:
        """Whether an Aura or Equipment on it takes away all its abilities (Infinite Coursework). Abilities that other
        effects give it are kept; the order effects were made in is not tracked."""
        return any(a.attached_to is permanent and any(LOSES_ALL in b.modifier.keywords for b in attached_abilities(a.card))
                   for s in self.seats for a in s.battlefield)

    def annihilator(self, permanent: Permanent) -> int:
        """N of the creature's Annihilator N, printed or granted (Eldrazi Conscription); they add up."""
        granted = [int(k.split()[1]) for m in self.modifiers(permanent) for k in m.keywords if k.startswith("annihilator ")]
        return annihilator_of(permanent.card) + sum(granted)

    def modify_until_end_of_turn(self, permanent: Permanent, modifier: Modifier) -> None:
        permanent.until_end_of_turn.append(modifier)
        self.broadcast({"event": "modified", "card": permanent.card.name, "power": modifier.power,
                        "toughness": modifier.toughness, "keywords": sorted(modifier.keywords)})

    def gain_control(self, permanent: Permanent, seat: Seat, aura: Permanent | None = None, until_eot: bool = False,
                     untap: bool = False, haste: bool = False) -> None:
        """`seat` takes control of `permanent` (CR 110.2): it moves to their battlefield, is summoning sick under
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
        """Two creatures each deal damage equal to their power to the other at the same time (CR 701.14). With
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
        self._left_graveyard(seat, [dead.card])
        self._enter(seat, Permanent(dead.card, sick=True, loyalty=_starting_loyalty(dead.card), counters={counter: 1}))

    def _unearth(self, seat: Seat, card: Card) -> None:
        """Unearth: pay its cost and return it from the graveyard (it is not cast); it has haste, and is exiled at the beginning
        of the next end step or instead of leaving the battlefield some other way."""
        tapped = self._payment(seat, dataclasses.replace(card, mana_cost=unearth_cost(card)))
        self._spend_mana(seat, tapped)
        seat.graveyard.remove(card)
        self.broadcast({"event": "unearth", "seat": seat.index, "card": card.name})
        self._left_graveyard(seat, [card])
        permanent = Permanent(card, sick=True, unearthed=True)
        self._enter(seat, permanent)
        self.modify_until_end_of_turn(permanent, Modifier(keywords=frozenset({"haste"})))
        fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
        self.at_end_step.append((fire_turn, lambda: self._leave_together(
            [(permanent, "exiled")] if self.on_battlefield(permanent) else [], "exile")))

    def _encore(self, seat: Seat, card: Card) -> None:
        """Encore: pay its cost and exile it from the graveyard; for each opponent, a token copy with haste attacks that
        opponent this turn if able and is sacrificed at the beginning of the next end step."""
        tapped = self._payment(seat, dataclasses.replace(card, mana_cost=encore_cost(card)))
        self._spend_mana(seat, tapped)
        seat.graveyard.remove(card)
        self.broadcast({"event": "encore", "seat": seat.index, "card": card.name})
        self._move_card(seat, card, "exile")
        self._left_graveyard(seat, [card])
        self.attacking_tokens(seat, dataclasses.replace(card, type_line="Token " + card.type_line), 1, True, "sacrificed")

    def attacking_tokens(self, seat: Seat, token: Card, count: int, haste: bool, at_end: str | None) -> None:
        """For each opponent, `count` tokens that attack that opponent this turn if able (Encore, Furygale Flocking);
        with `haste` until end of turn, and `at_end` ("sacrificed" or "exiled") at the beginning of the next end step."""
        made = []
        for opponent in self.opponents(seat):
            for _ in range(count * self._factor(seat, "tokens")):
                copy = Permanent(token, sick=True, must_attack=opponent)
                self.broadcast({"event": "token_created", "seat": seat.index, "card": token.name,
                                "type_line": token.type_line, "power": token.power, "toughness": token.toughness})
                self._enter(seat, copy)
                if haste:
                    self.modify_until_end_of_turn(copy, Modifier(keywords=frozenset({"haste"})))
                made.append(copy)
        if at_end:
            fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
            self.at_end_step.append((fire_turn, lambda: self._leave_together(
                [(p, at_end) for p in made if self.on_battlefield(p)], "exile" if at_end == "exiled" else "graveyard")))

    def tokens_become_copies(self, seat: Seat, until_end_of_turn: bool = False) -> None:
        """Brudiclad: `seat` may choose a token they control; each other token they control becomes a copy of it, for good or
        (the older wording) until end of turn, when like a crewed Vehicle the card comes back at cleanup. Counters and damage
        stay where they are."""
        tokens = [p for p in seat.battlefield if _is_token(p.card)]
        if not tokens:
            return
        pick = seat.player.choose(CLONE_PROMPT + "tokens", [self.label(p) for p in tokens] + [NOT_A_COPY])
        if pick == len(tokens):
            return
        chosen = tokens[pick]
        for permanent in tokens:
            if permanent is not chosen:
                was = permanent.card
                if until_end_of_turn:
                    permanent.original = permanent.original or permanent.card
                permanent.card = chosen.card
                self.broadcast({"event": "copied_permanent", "seat": seat.index, "card": was.name,
                                "as": chosen.card.name})

    def become_copy_until_end_of_turn(self, permanent: Permanent, copied: Permanent, keyword: str, seat: Seat | None = None) -> None:
        """`permanent` becomes a copy of `copied`, except it has `keyword`, until end of turn (the card comes back at cleanup).
        Counters and damage stay where they are."""
        permanent.original = permanent.original or permanent.card
        card = copied.card
        text = (card.oracle_text + f"\n{keyword}").strip()
        permanent.card = dataclasses.replace(card, type_line=card.type_line.removeprefix("Token "), oracle_text=text)
        self.broadcast({"event": "copied_permanent", "seat": (seat or self.controller_of(permanent)).index,
                        "card": permanent.original.name, "as": card.name})

    def may_become_copy(self, seat: Seat, permanent: Permanent, cards: list[Card]) -> None:
        """`permanent` may become a copy of one of `cards` until end of turn (like a crewed Vehicle, its card comes back at
        cleanup). Counters and damage stay where they are."""
        pick = seat.player.choose(CLONE_PROMPT + permanent.card.name, [c.name for c in cards] + [NOT_A_COPY])
        if pick == len(cards):
            return
        permanent.original = permanent.original or permanent.card
        permanent.card = cards[pick]
        self.broadcast({"event": "copied_permanent", "seat": seat.index, "card": permanent.original.name, "as": cards[pick].name})

    def grant_abilities(self, permanent: Permanent, text: str) -> None:
        """The permanent gains the abilities written in `text` until end of turn (Backup); like a crewed Vehicle, its
        card is replaced and comes back at end of turn."""
        permanent.original = permanent.original or permanent.card
        permanent.card = dataclasses.replace(permanent.card, oracle_text=permanent.card.oracle_text + "\n" + text)
        self.broadcast({"event": "gained_abilities", "card": permanent.card.name, "text": text})

    def _fixed_kind(self, kind: str, source: Permanent | None, x: int | None = None) -> str:
        """A target kind with "mv<=power" turned into the source creature's power right now, or "mv<=x" into the X the
        ability carries (Venerable Warsinger: the damage dealt)."""
        if "mv<=power" in kind and source is not None:
            power = self.power(source) if self.on_battlefield(source) else source.last_power
            return kind.replace("mv<=power", f"mv<={max(power, 0)}")
        if "mv<=x" in kind:
            return kind.replace("mv<=x", f"mv<={max(self.targeting_x if x is None else x, 0)}")
        return kind

    def put_counters(self, permanent: Permanent, counter: str, count: int) -> None:
        holder = self.controller_of(permanent)
        if holder is not None:
            count = self._counters_to_add(holder, permanent.card, counter, count, permanent)
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

    def conjure(self, seat: Seat, name: str) -> None:
        """Alchemy: create the named card, from the cards this player's deck can conjure, onto the battlefield. A card the
        deck has no definition for is not conjured."""
        card = seat.conjurable.get(name)
        if card is None:
            self.broadcast({"event": "conjure_failed", "seat": seat.index, "card": name})
            return
        self.broadcast({"event": "conjure", "seat": seat.index, "card": name})
        self._enter(seat, Permanent(dataclasses.replace(card, conjured=True), sick=True))
        for permanent in list(seat.battlefield):
            self.trigger("conjure", permanent, seat)

    def create_tokens(self, seat: Seat, token: Card, count: int, counters: tuple[int, str] | None = None,
                      tapped: bool = False) -> list[Permanent]:
        return self.create_token_batch(seat, [token] * count, counters, tapped)

    def create_token_batch(self, seat: Seat, tokens: list[Card], counters: tuple[int, str] | None = None,
                           tapped: bool = False) -> list[Permanent]:
        outer = self._batch
        self._batch = set() if outer is None else outer
        try:
            return self._create_token_batch_now(seat, tokens, counters, tapped)
        finally:
            self._batch = outer

    def _create_token_batch_now(self, seat: Seat, tokens: list[Card], counters: tuple[int, str] | None,
                                tapped: bool) -> list[Permanent]:
        """Create tokens at once, each as many times as the replacement effects say (Doubling Season). Watchers of "one or
        more creature tokens" see the whole batch as one event."""
        made = []
        for token in tokens:
            for _ in range(self._factor(seat, "tokens")):
                self.broadcast({"event": "token_created", "seat": seat.index, "card": token.name,
                                "type_line": token.type_line, "power": token.power, "toughness": token.toughness})
                permanent = Permanent(token, sick=True, tapped=tapped)
                self._enter(seat, permanent)
                if counters:
                    self.put_counters(permanent, counters[1], counters[0])
                made.append(permanent)
        if any("Creature" in p.card.type_line for p in made):
            self._trigger_each("tokens_created", seat)
        if made:
            self._trigger_each("tokens_enter", seat)
        return made

    def leave_at_next_end_step(self, permanents: list[Permanent], reason: str, destination: str) -> None:
        """They leave the battlefield (exiled, sacrificed) as the next end step begins."""
        fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
        self.at_end_step.append((fire_turn, lambda: self._leave_together(
            [(p, reason) for p in permanents if self.on_battlefield(p)], destination)))

    def copy_tokens(self, seat: Seat, sources: list[Permanent], haste: bool, exile_at_end: bool) -> None:
        """Twinflame: a token that's a copy of each of `sources`, except it has haste, exiled as the next end step begins."""
        cards = []
        for source in sources:
            card = source.card if _is_token(source.card) else dataclasses.replace(source.card, type_line="Token " + source.card.type_line)
            if haste:
                card = dataclasses.replace(card, oracle_text=(card.oracle_text + "\nHaste").strip())
            cards.append(card)
        made = self.create_token_batch(seat, cards)
        if made and exile_at_end:
            fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
            self.at_end_step.append((fire_turn, lambda: self._leave_together(
                [(p, "exiled") for p in made if self.on_battlefield(p)], "exile")))

    def exile(self, permanent: Permanent) -> None:
        self._leave_battlefield(permanent, "exiled", destination="exile")

    def copies_of_creature(self, seat: Seat, original: Permanent, count: int, not_legendary: bool, exile: bool = False) -> None:
        """Orthion, Tempestra, Rionya: `count` tokens that are copies of `original` with haste (not legendary for Tempestra),
        sacrificed (or exiled, for Rionya) as the next end step begins."""
        card = original.card if _is_token(original.card) else dataclasses.replace(original.card, type_line="Token " + original.card.type_line)
        card = dataclasses.replace(card, oracle_text=(card.oracle_text + "\nHaste").strip())
        if not_legendary:
            card = dataclasses.replace(card, type_line=card.type_line.replace("Legendary ", ""))
        made = self.create_token_batch(seat, [card] * count)
        if made:
            self.leave_at_next_end_step(made, "exiled" if exile else "sacrificed", "exile" if exile else "graveyard")

    def goaded_copies_for_opponents(self, seat: Seat, original: Permanent) -> None:
        """Life of the Party: each opponent gets a token copy, goaded by `seat` for the rest of the game."""
        card = original.card if _is_token(original.card) else dataclasses.replace(original.card, type_line="Token " + original.card.type_line)
        for opponent in self.opponents(seat):
            for made in self.create_token_batch(opponent, [card]):
                made.goad_forever = seat

    def return_at_next_upkeep(self, dead: Permanent) -> None:
        """Phytotitan: its card comes back tapped at the beginning of its owner's next upkeep."""
        owner = dead.owner or dead.last_controller
        card = dead.card
        self.at_owner_upkeep.append((owner, self.turn, lambda: self._return_card_tapped(owner, card)))

    def _return_card_tapped(self, owner: Seat, card: Card) -> None:
        if any(c is card for c in owner.graveyard):
            self.return_from_graveyard(GraveyardTarget(card, owner), owner, "battlefield", tapped=True)

    def put_creature_from_hand(self, seat: Seat, reduction: int) -> None:
        """Flash: put a creature card from hand onto the battlefield; sacrifice it unless its mana cost, reduced, is paid."""
        options = [c for c in _unique(seat.hand) if "Creature" in c.type_line]
        if not options:
            return
        pick = seat.player.choose(PUT_CREATURE_PROMPT, [c.name for c in options] + [NONE_TAKEN])
        if pick == len(options):
            return
        card = options[pick]
        seat.hand.remove(card)
        entering = Permanent(card, sick=True, loyalty=_starting_loyalty(card))
        self._enter(seat, entering)
        cost = parse_cost(card.mana_cost).reduced(reduction) if card.mana_cost else Cost()
        paid = self._pay_cost(seat, cost) if cost.generic or cost.colored else []
        if paid is not None and (not paid or seat.player.choose(UNLESS_PROMPT + card.name, ["Pay the reduced cost", "Sacrifice it"]) == 0):
            self._spend_mana(seat, paid)
        else:
            self._leave_battlefield(entering, "sacrificed")

    def mill_then_return(self, seat: Seat, count: int, kinds: tuple[str, ...], to: str, tapped: bool) -> None:
        """Mill, then return a card of each kind from the graveyard (the player picks, among everything there)."""
        self.mill(seat, count)
        for kind in kinds:
            options = [c for c in _unique(seat.graveyard) if _card_matches(kind, c)]
            if not options:
                continue
            card = options[seat.player.choose(RETURN_CARD_PROMPT + kind, [c.name for c in options])]
            self.return_from_graveyard(GraveyardTarget(card, seat), seat, to, tapped)

    def exile_noting(self, target: Permanent, source: Permanent | None) -> None:
        """Exile `target` and remember the card on `source` ("the exiled card's owner ..."). Tokens are not remembered."""
        owner = target.owner or self.controller_of(target)
        card, before = target.card, len(owner.exile)
        self.exile(target)
        if source is not None and not _is_token(card) and len(owner.exile) > before:
            source.exiled_with.append((owner, card))

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
            self._left_graveyard(seat, cards)

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

    def fetch_basic_land(self, seat: Seat, optional: bool = False, untap_if: "Condition | None" = None,
                         tapped: bool = True) -> None:
        if optional and seat.player.choose(SEARCH_OPTIONAL_PROMPT, YES_NO) != 0:
            return
        basics = _unique([c for c in seat.library if "Basic" in c.type_line and "Land" in c.type_line])
        if basics:
            choice = basics[seat.player.choose(SEARCH_PROMPT, [c.name for c in basics])]
            seat.library.remove(choice)
            self.broadcast({"event": "put_onto_battlefield", "seat": seat.index, "card": choice.name, "tapped": tapped})
            land = Permanent(choice, tapped=tapped)
            self._enter(seat, land)
            if untap_if and self.condition_holds(untap_if, seat, self.resolving_source):
                land.tapped = False
        self.rng.shuffle(seat.library)
        self._searched(seat)

    def search_for_lands(self, seat: Seat, count: int, subtypes: tuple[str, ...], battlefield: int,
                         tapped: bool, reveal: bool, basic_only: bool = False) -> None:
        """Search for up to `count` lands (basic lands, or any land with one of `subtypes`): the first
        `battlefield` go onto the battlefield and the rest into the hand, then the library is shuffled."""
        to_battlefield: list[Card] = []
        to_hand: list[Card] = []
        for n in range(count):
            matches = _unique([c for c in seat.library if _is_searched_land(c, subtypes) and (not basic_only or "Basic" in c.type_line)])
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
        if top:  # CR 701.22b: scry 0 is no scry event
            self._trigger_each("scry", seat)
            self._trigger_each("scry_or_surveil", seat)

    def _ordered(self, seat: Seat, cards: list[Card]) -> list[Card]:
        """Let the player choose the order of the cards they keep on top (first asked goes on top)."""
        cards, ordered = list(cards), []
        while len(cards) > 1:
            ordered.append(cards.pop(seat.player.choose(ORDER_TOP_PROMPT, [c.name for c in cards])))
        return ordered + cards

    def _devour(self, seat: Seat, permanent: Permanent) -> None:
        """Devour N: sacrifice any number of other creatures as it enters; it gets N +1/+1 counters for each."""
        eaten = 0
        while True:
            options = [p for p in seat.battlefield if "Creature" in p.card.type_line and p is not permanent]
            if not options:
                break
            pick = seat.player.choose(DEVOUR_PROMPT + permanent.card.name, [self.label(p) for p in options] + [DEVOUR_DONE])
            if pick == len(options):
                break
            self._leave_together([(options[pick], "sacrificed")])
            eaten += 1
        if eaten:
            permanent.counters[PLUS] = permanent.counters.get(PLUS, 0) + eaten * devour(permanent.card)
            self.broadcast({"event": "devoured", "seat": seat.index, "card": permanent.card.name, "creatures": eaten})

    def _choose_replicate(self, seat: Seat, card: Card, from_command_zone: bool, kickers: tuple[str, ...], extra: str,
                          alternative: AlternativeCost | None) -> int:
        """Replicate {cost}: how many times to pay it (any affordable number)."""
        cost = replicate_cost(card)
        if cost is None:
            return 0
        most = 0
        while (most < MAX_X and self._payment(seat, card, from_command_zone, alternative=alternative, kickers=kickers,
                                              extra=extra + cost * (most + 1)) is not None):
            most += 1
        return seat.player.choose(REPLICATE_PROMPT + card.name, [str(n) for n in range(most + 1)]) if most else 0

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

    def cascade(self, seat: Seat, value: int | None) -> None:
        """Exile cards from the top of the library until a nonland card that costs less than `value` is exiled; the
        player may cast it for free, and the rest go to the bottom of the library in a random order."""
        passed: list[Card] = []
        found = None
        while seat.library:
            card = seat.library.pop(0)
            if not is_land(card) and (value is None or card.cmc < value):
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

    def _can_put_attachment(self, seat: Seat, card: Card) -> bool:
        """Whether an Aura or Equipment card could be put onto the battlefield (an Aura needs something to enchant)."""
        if "Equipment" in card.type_line:
            return True
        return "Aura" in card.type_line and bool(self.target_options(aura_kind(card) or "creature", seat, source_qualities(card)))

    def put_attachment_onto_battlefield(self, seat: Seat, card: Card) -> None:
        """Put an Aura or Equipment card (already out of its zone) onto the battlefield without casting it. An Aura enters
        attached to what `seat` chooses; an Equipment may then be attached to a creature `seat` controls."""
        self.broadcast({"event": "put_onto_battlefield", "seat": seat.index, "card": card.name, "tapped": False})
        if "Aura" in card.type_line:
            options = self.target_options(aura_kind(card) or "creature", seat, source_qualities(card))
            host = options[seat.player.choose(f"Enchant which permanent with {card.name}? ", [n for n, _ in options])
                           if len(options) > 1 else 0][1]
            self._enter(seat, Permanent(card, sick=True, attached_to=host, owner=seat))
            self.broadcast({"event": "attached", "card": card.name, "to": host.card.name})
            return
        equipment = Permanent(card, sick=True, owner=seat)
        self._enter(seat, equipment)
        creatures = [p for p in seat.battlefield if "Creature" in p.card.type_line and p is not equipment]
        if creatures:
            pick = seat.player.choose(EQUIP_PROMPT + card.name, [self.label(p) for p in creatures] + [DECLINE])
            if pick < len(creatures):
                self.attach(equipment, creatures[pick])

    def look_and_put_attachment(self, seat: Seat, count: int) -> None:
        """Armored Skyhunter: look at the top `count` cards; you may put an Aura or Equipment card from among them onto the
        battlefield; the rest go to the bottom in a random order."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        options = _unique([c for c in top if self._can_put_attachment(seat, c)])
        if options:
            choice = seat.player.choose(PUT_ATTACHMENT_PROMPT, [c.name for c in options] + [NONE_TAKEN])
            if choice < len(options):
                top.remove(options[choice])
                self.put_attachment_onto_battlefield(seat, options[choice])
        self.rng.shuffle(top)
        seat.library += top
        self.broadcast({"event": "looked", "seat": seat.index, "count": len(top)}, skip=seat)

    def cast_exiled_with_free(self, seat: Seat, source: Permanent, bottom_after: bool) -> None:
        """Quintorius: you may cast a card exiled with `source` without paying its mana cost (this turn; it is done as the ability
        resolves). A spell that would go to a graveyard goes to the bottom of its owner's library when `bottom_after`."""
        options = [(owner, card) for owner, card in source.exiled_with if any(c is card for c in owner.exile)]
        if not options:
            return
        pick = seat.player.choose(CHOOSE_EXILED_WITH_PROMPT, [card.name for _, card in options] + [NONE_TAKEN])
        if pick >= len(options):
            return
        owner, card = options[pick]
        source.exiled_with = [pair for pair in source.exiled_with if pair[1] is not card]
        self._cast(seat, card, owner.exile, free=True, bottom_after=bottom_after)

    def each_player_exiles_graveyard_card(self, starting: Seat) -> int:
        """Augusta, Order Returned: each player exiles a card from their graveyard (their choice); returns how many of the cards
        exiled were nonland."""
        nonland = 0
        for seat in [s for s in self._turn_order(starting.index) if not s.lost]:
            if not seat.graveyard:
                continue
            card = seat.graveyard[seat.player.choose(EXILE_COST_PROMPT, [c.name for c in seat.graveyard])]
            self.exile_card_from_graveyard(seat, card, False)
            nonland += "Land" not in card.type_line
        return nonland

    def class_level_up(self, permanent: Permanent) -> None:
        """A Class gains its next level: it reads as the abilities of that level from now on."""
        if permanent.real_card is None or not self.on_battlefield(permanent):
            return
        permanent.level += 1
        permanent.card = class_view(permanent.real_card, permanent.level)
        self.broadcast({"event": "class_level", "seat": self.controller_of(permanent).index, "card": permanent.real_card.name,
                        "level": permanent.level})

    def put_exiled_with_into_graveyard(self, seat: Seat, source: Permanent) -> Card | None:
        """Currency Converter: a card exiled with `source` (the player chooses) goes to its owner's graveyard; returns it."""
        options = [(owner, card) for owner, card in source.exiled_with if any(c is card for c in owner.exile)]
        if not options:
            return None
        pick = 0 if len(options) == 1 else seat.player.choose(CHOOSE_EXILED_WITH_PROMPT, [card.name for _, card in options])
        owner, card = options[pick]
        owner.exile = [c for c in owner.exile if c is not card]
        source.exiled_with = [pair for pair in source.exiled_with if pair[1] is not card]
        self._move_card(owner, card, "graveyard")
        return card

    def phase_out(self, permanent: Permanent) -> None:
        """The permanent, and every Aura and Equipment attached to it, phase out: they are not on the battlefield (nothing leaves it) until
        their controller's next untap step, when they come back as the same objects."""
        seat = self.controller_of(permanent)
        if seat is None:
            return
        together = [permanent] + [a for s in self.seats for a in s.battlefield if a.attached_to is permanent]
        for one in together:
            holder = self.controller_of(one)
            holder.battlefield = [p for p in holder.battlefield if p is not one]
            holder.phased_out.append(one)
        left = {id(p) for p in together}
        self.combat.attacks = [a for a in self.combat.attacks if id(a.attacker) not in left]
        self.broadcast({"event": "phased_out", "seat": seat.index, "card": permanent.card.name})

    def create_attached_token(self, seat: Seat, token: Card, host: Permanent) -> None:
        """An Aura token created attached to `host`, under `seat`'s control."""
        self.broadcast({"event": "token_created", "seat": seat.index, "card": token.name, "type_line": token.type_line,
                        "power": token.power, "toughness": token.toughness})
        self._enter(seat, Permanent(token, sick=True, attached_to=host, owner=seat))

    def tragic_arrogance(self, chooser: Seat) -> None:
        """Tragic Arrogance: `chooser` picks, from each player's permanents, an artifact, a creature, an enchantment and a planeswalker
        to keep; every other nonland permanent is sacrificed."""
        keep: list[Permanent] = []
        for seat in self.turn_order_from_active():
            for kind in ("Artifact", "Creature", "Enchantment", "Planeswalker"):
                options = [p for p in seat.battlefield if kind in p.card.type_line]
                if options:
                    pick = 0 if len(options) == 1 else chooser.player.choose(f"Choose a {kind.lower()} {seat.name} keeps", [self.label(p) for p in options])
                    keep.append(options[pick])
        doomed = [p for s in self.live_seats() for p in s.battlefield if "Land" not in p.card.type_line and not any(p is k for k in keep)]
        self._leave_together([(p, "sacrificed") for p in doomed])

    def may_return_permanent_card(self, seat: Seat, other_than: list[Card]) -> None:
        """Deadly Brew: you may return a permanent card from your graveyard to your hand, another one than `other_than`."""
        options = _unique([c for c in seat.graveyard if _is_permanent(c) and not any(c is o for o in other_than)])
        if not options:
            return
        pick = seat.player.choose(RETURN_CHOSEN_PROMPT, [c.name for c in options] + [NONE_TAKEN])
        if pick < len(options):
            self.return_from_graveyard(GraveyardTarget(options[pick], seat), seat, "hand")

    def reveal_lands(self, seat: Seat, count: int, until_lands: bool, untap_if: "Condition | None") -> None:
        """Animist's Awakening and Open the Way: reveal the top `count` cards (or cards until `count` lands); the lands go onto the
        battlefield tapped (untapped, if `untap_if` holds), the rest to the bottom of the library in a random order."""
        revealed, found = [], []
        while seat.library and (len(found) < count if until_lands else len(revealed) + len(found) < count):
            card = seat.library.pop(0)
            (found if "Land" in card.type_line else revealed).append(card)
        self.broadcast({"event": "revealed", "seat": seat.index, "count": len(found) + len(revealed),
                        "cards": [c.name for c in found + revealed]})
        entered = []
        for card in found:
            self.broadcast({"event": "put_onto_battlefield", "seat": seat.index, "card": card.name, "tapped": True})
            permanent = Permanent(card, tapped=True)
            self._enter(seat, permanent)
            entered.append(permanent)
        if untap_if is not None and self.condition_holds(untap_if, seat, self.resolving_source):
            for permanent in entered:
                permanent.tapped = False
        self.rng.shuffle(revealed)
        seat.library += revealed

    def reveal_until_aura(self, seat: Seat) -> None:
        """Songbirds' Blessing: reveal cards from the top until an Aura; you may put it onto the battlefield, else it goes to
        your hand; the rest go to the bottom in a random order."""
        revealed, aura = [], None
        while seat.library:
            card = seat.library.pop(0)
            if "Aura" in card.type_line:
                aura = card
                break
            revealed.append(card)
        self.broadcast({"event": "revealed", "seat": seat.index, "card": aura.name if aura else None,
                        "count": len(revealed) + (aura is not None)})
        if aura is not None:
            if self._can_put_attachment(seat, aura) and seat.player.choose(PUT_ATTACHMENT_PROMPT + f": {aura.name}?", YES_NO) == 0:
                self.put_attachment_onto_battlefield(seat, aura)
            else:
                seat.hand.append(aura)
        self.rng.shuffle(revealed)
        seat.library += revealed

    def exile_top_cast_aura(self, seat: Seat, count: int) -> None:
        """Herald of Amity: exile the top `count` cards; you may cast an Aura spell from among them without paying its mana
        cost; the rest (the Aura too, if it wasn't cast) go to the bottom of the library in a random order."""
        exiled = self.exile_top(seat, count, None)
        auras = _unique([c for c in exiled if "Aura" in c.type_line])
        if auras:
            choice = seat.player.choose(CAST_FREE_PROMPT, [c.name for c in auras] + [NONE_TAKEN])
            if choice < len(auras):
                self._cast(seat, auras[choice], seat.exile, free=True)
        rest = [c for c in exiled if any(c is e for e in seat.exile)]
        for card in rest:
            seat.exile = [e for e in seat.exile if e is not card]
        self.rng.shuffle(rest)
        seat.library += rest

    def return_attachment_to(self, seat: Seat, host: Permanent) -> None:
        """Forum Filibuster: return up to one Aura or Equipment card from `seat`'s graveyard to the battlefield attached to
        `host` (an Aura only if it could enchant it)."""
        def fits(card: Card) -> bool:
            if "Equipment" in card.type_line:
                return True
            return "Aura" in card.type_line and any(
                p is host for _, p in self.target_options(aura_kind(card) or "creature", seat, source_qualities(card)))
        options = _unique([c for c in seat.graveyard if fits(c)])
        if not options:
            return
        choice = seat.player.choose(RETURN_CHOSEN_PROMPT, [c.name for c in options] + [NONE_TAKEN])
        if choice >= len(options):
            return
        card = options[choice]
        seat.graveyard.remove(card)
        self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": card.name, "to": "battlefield"})
        self._left_graveyard(seat, [card])
        self._enter(seat, Permanent(card, sick=True, attached_to=host, owner=seat))
        self.broadcast({"event": "attached", "card": card.name, "to": host.card.name})

    def look_and_put_permanents(self, seat: Seat, count: int, total_mv: int) -> None:
        """Ao, the Dawn Sky: look at the top `count` cards; put any number of nonland permanent cards with total mana value
        `total_mv` or less from among them onto the battlefield; the rest go to the bottom in a random order."""
        top = seat.library[:count]
        del seat.library[:len(top)]
        left = total_mv
        while True:
            options = _unique([c for c in top if "Land" not in c.type_line and c.cmc <= left
                               and _card_matches("permanent", c) and ("Aura" not in c.type_line or self._can_put_attachment(seat, c))])
            if not options:
                break
            choice = seat.player.choose(PUT_PERMANENT_PROMPT + f" (mana value {left} or less left)", [c.name for c in options] + [NONE_TAKEN])
            if choice >= len(options):
                break
            card = options[choice]
            top.remove(card)
            left -= int(card.cmc)
            if "Aura" in card.type_line:
                self.put_attachment_onto_battlefield(seat, card)
            else:
                self.broadcast({"event": "put_onto_battlefield", "seat": seat.index, "card": card.name, "tapped": False})
                self._enter(seat, Permanent(card, sick=True, loyalty=_starting_loyalty(card)))
        self.rng.shuffle(top)
        seat.library += top
        self.broadcast({"event": "looked", "seat": seat.index, "count": len(top)}, skip=seat)

    def exile_until_nonland_and_cast(self, seat: Seat, casts: int) -> None:
        """Plargg and Nassari: each player exiles cards from the top of their library until they exile a nonland card; an
        opponent of `seat` chooses one of those nonland cards; `seat` may cast up to `casts` spells from among the others
        without paying their mana costs. Cards not cast stay exiled."""
        found: list[tuple[Seat, Card]] = []
        for player in self.live_seats():
            while player.library:
                card = player.library.pop(0)
                self.broadcast({"event": "exiled_from_library", "seat": player.index, "cards": [card.name], "may_play": False})
                self._move_card(player, card, "exile")
                if "Land" not in card.type_line:
                    found.append((player, card))
                    break
        others = list(found)
        chooser = next(iter(self.opponents(seat)), None)
        if len(found) > 1 and chooser is not None:
            aside = chooser.player.choose(SET_ASIDE_PROMPT, [card.name for _, card in found])
            others.pop(aside)
        for _ in range(casts):
            options = [(owner, card) for owner, card in others if any(c is card for c in owner.exile)]
            if not options:
                return
            choice = seat.player.choose(CAST_FREE_EXILED_PROMPT, [card.name for _, card in options] + [NONE_TAKEN])
            if choice >= len(options):
                return
            owner, card = options[choice]
            others = [pair for pair in others if pair[1] is not card]
            self._cast(seat, card, owner.exile, free=True)

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

    def pays_optional(self, payer: Seat, cost_text: str, source: Card | None) -> bool:
        """ "You may pay {2}. If you do, ...": whether `payer` can and chooses to pay the cost (and pays it)."""
        payment = self._pay_cost(payer, parse_cost(cost_text))
        name = source.name if source is not None else ""
        if payment is None or payer.player.choose(MAY_PAY_PROMPT + name, [f"Pay {cost_text}", "Don't pay"]) != 0:
            return False
        self._spend_mana(payer, payment)
        self.broadcast({"event": "paid_unless", "seat": payer.index, "card": name, "cost": cost_text})
        return True

    def take_initiative(self, seat: Seat) -> None:
        """Taking the initiative ventures into the Undercity (CR 726.2); already having it does nothing."""
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
        if top:  # surveil 0 is no surveil event either
            self._trigger_each("surveil", seat)
            self._trigger_each("scry_or_surveil", seat)

    def may_loot(self, seat: Seat, draw: int = 1, mill: int = 0) -> None:
        """ "You may discard a card. If you do, draw a card." (and maybe then mill some)"""
        if seat.hand and seat.player.choose(LOOT_PROMPT, YES_NO) == 0:
            self.discard(seat, 1)
            self.draw(seat, draw)
            if mill:
                self.mill(seat, mill)

    def may_sacrifice(self, seat: Seat, kind: str) -> bool:
        """ "You may sacrifice a permanent." Whether they did (they need one to sacrifice, and to want to)."""
        if any(_permanent_matches(kind, p.card) for p in seat.battlefield) \
                and seat.player.choose(SACRIFICE_DRAW_PROMPT, YES_NO) == 0:
            self.sacrifice(seat, kind, 1)
            return True
        return False

    def may_sacrifice_draw(self, seat: Seat, kind: str, draw: int) -> None:
        """ "You may sacrifice a permanent. If you do, draw two cards." """
        if self.may_sacrifice(seat, kind):
            self.draw(seat, draw)

    def draw_at_next_upkeep(self, seat: Seat, count: int, up_to: bool) -> None:
        """"... draw a card at the beginning of the next turn's upkeep": with `up_to`, the player picks how many when it happens."""
        def draw() -> None:
            if up_to and count > 1:
                number = seat.player.choose(DRAW_UP_TO_PROMPT, [str(n) for n in range(count + 1)])
            else:
                number = count if not up_to else seat.player.choose(DRAW_UP_TO_PROMPT, ["0", "1"])
            self.draw(seat, number)
        self.at_upkeep.append((self.turn, draw))

    def may_remove_counter_draw(self, seat: Seat, source: Permanent, counter: str, draw: int) -> None:
        """ "You may remove a +1/+1 counter from it. If you do, draw a card." """
        if source.counters.get(counter, 0) and seat.player.choose(REMOVE_COUNTER_PROMPT + source.card.name, YES_NO) == 0:
            self.remove_counters(source, counter, 1)
            self.draw(seat, draw)

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
        discarded = []
        for _ in range(len(seat.hand) if count is None else min(count, len(seat.hand))):
            if count is None:
                card = seat.hand.pop(0)  # all of them go, so there is nothing to choose
            elif random:
                card = seat.hand.pop(self.rng.randrange(len(seat.hand)))
            else:
                card = seat.hand.pop(seat.player.choose(DISCARD_CARD_PROMPT, [c.name for c in seat.hand]))
            self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
            self._discard_into_zone(seat, card)
            discarded.append(card)
            self._discarded(seat, card, together=True)
        self._discarded_nonland(seat, discarded)

    def _discard_into_zone(self, seat: Seat, card: Card) -> None:
        """A card that was just discarded goes to the graveyard. With madness it goes to exile, and its owner may cast it for
        its madness cost; if it isn't cast it goes to the graveyard then. (The choice is made at once, not from a trigger.)"""
        cost = madness_cost(card)
        if cost is None:
            self._move_card(seat, card, "graveyard")
            return
        seat.exile.append(card)
        self.broadcast({"event": "madness", "seat": seat.index, "card": card.name})
        way = AlternativeCost(f"Madness {cost}", mana_cost=cost)
        if self._payment(seat, card, alternative=way) is not None and seat.player.choose(MADNESS_PROMPT + card.name, YES_NO) == 0:
            self._cast(seat, card, seat.exile, madness=way)
        if any(c is card for c in seat.exile):  # not cast (declined, or no legal target): into the graveyard
            seat.exile.remove(card)
            self._move_card(seat, card, "graveyard")

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
        self._discard_into_zone(victim, card)
        self._discarded(victim, card)

    def mill(self, seat: Seat, count: int) -> list[Card]:
        """Put the top `count` cards of the library into the graveyard (fewer if there aren't that many); the cards milled."""
        milled = [seat.library.pop(0) for _ in range(min(count, len(seat.library)))]
        self.broadcast({"event": "milled", "seat": seat.index, "cards": [c.name for c in milled]})
        for card in milled:
            self._move_card(seat, card, "graveyard")
        return milled

    def return_chosen_from(self, seat: Seat, among: list[Card], kind: str, to: str) -> None:
        """"Put a creature card from among them onto the battlefield.": one of `among` that is still in the graveyard."""
        options = [c for c in among if c in seat.graveyard and _card_matches(kind, c)]
        if options:
            card = options[0] if len(options) == 1 else options[seat.player.choose(RETURN_CHOSEN_PROMPT, [c.name for c in options])]
            self.return_from_graveyard(GraveyardTarget(card, seat), seat, to)

    # --- helpers -------------------------------------------------------------

    def _enter(self, seat: Seat, permanent: Permanent, x: int = 0) -> None:
        if is_class(permanent.card):  # a Class enters at level 1: it reads as the abilities of that level
            permanent.real_card, permanent.card, permanent.level = permanent.card, class_view(permanent.card, 1), 1
        extra_when_copy = False
        if keyword := temporary_clone_keyword(permanent.card):  # Cursed Mirror
            self._become_temporary_copy(seat, permanent, keyword)
        elif clone := clone_kind(permanent.card):  # "You may have it enter as a copy of ...": decided as it enters
            extra_when_copy = clone_extra_counters(permanent.card)
            self._become_copy(seat, permanent, *clone)
        counters = {counter: (x if count == "X" else 2 * x if count == "2X" else count)
                    for counter, count in enters_with_counters(permanent.card, permanent.kicked, permanent.escaped).items()}
        if permanent.extra_counters:  # Opal Palace: mana spent on the commander
            counters["+1/+1"] = counters.get("+1/+1", 0) + permanent.extra_counters
        if extra_when_copy and permanent.real_card is not None:  # Altered Ego: X additional counters on the copy
            counters["+1/+1"] = counters.get("+1/+1", 0) + x
        if "Creature" in permanent.card.type_line and not _is_token(permanent.card) and seat.died_turn == self.turn:
            bonus = sum(replacement_effects(p.card).enter_counters_per_death for p in seat.battlefield) * seat.died
            if bonus:  # Gorma, the Gullet
                counters["+1/+1"] = counters.get("+1/+1", 0) + bonus
        for counter, amount in counters.items():  # CR 614.1c: it arrives with them
            number = self._counters_to_add(seat, permanent.card, counter, amount, permanent)
            permanent.counters[counter] = permanent.counters.get(counter, 0) + number
        permanent.owner = permanent.owner or seat
        permanent.entered_turn = self.turn
        if any(c is permanent.card for c in seat.paragon_marked):  # Serra Paragon's permission
            seat.paragon_marked = [c for c in seat.paragon_marked if c is not permanent.card]
            permanent.paragon_life = (seat, next((found[1] for p in seat.battlefield if (found := graveyard_permission(p.card))), 2))
        if chooses_creature_type(permanent.card):
            permanent.chosen_type = self._choose_creature_type(seat, permanent.card)
        if chooses_color(permanent.card):
            names = {"White": "W", "Blue": "U", "Black": "B", "Red": "R", "Green": "G"}
            names = {name: letter for name, letter in names.items() if letter != color_choice_excludes(permanent.card)}
            permanent.chosen_color = names[list(names)[seat.player.choose(CHOOSE_COLOR_PROMPT + permanent.card.name, list(names))]]
        if enters_prepared(permanent.card):
            permanent.prepared = True
        if echo_cost(permanent.card):
            permanent.echo_pending = True
        if devour(permanent.card):
            self._devour(seat, permanent)
        rule = enters_tapped_rule(permanent.card)
        if rule and self._enters_tapped(seat, rule, permanent.card):
            permanent.tapped = True
        if saga_chapters(permanent.card):  # a Saga arrives with a lore counter, which triggers chapter I
            permanent.counters["lore"] = permanent.counters.get("lore", 0) + 1
        seat.battlefield.append(permanent)
        if "Land" in permanent.card.type_line:
            seat.land_entered_turn = self.turn
        if "Creature" in permanent.card.type_line and not _is_token(permanent.card):
            if seat.creatures_entered_turn != self.turn:
                seat.creatures_entered_turn, seat.creatures_entered = self.turn, 0
            seat.creatures_entered += 1
        self.trigger("enters", permanent, seat, x=x)  # the X it was cast with ("destroy ... with mana value X or less")
        if not permanent.tapped:
            self.trigger("enters_untapped", permanent, seat)
        if saga_chapters(permanent.card):
            self.trigger(f"chapter_{permanent.counters['lore']}", permanent, seat)
        self._observe("permanent_enters", permanent.card, seat, subject=permanent)

    def _choose_creature_type(self, seat: Seat, card: Card) -> str:
        """The creature type `seat` names as `card` enters: one of those in its cards, the most common first."""
        counts: dict[str, int] = {}
        for owned in [*seat.library, *seat.hand, *seat.graveyard, *seat.command_zone, *(p.card for p in seat.battlefield)]:
            if "Creature" in owned.type_line:
                for kind in owned.type_line.partition("—")[2].split():
                    counts[kind] = counts.get(kind, 0) + 1
        options = sorted(counts, key=lambda kind: (-counts[kind], kind)) or ["Human"]
        return options[seat.player.choose(CHOOSE_TYPE_PROMPT + card.name, options)]

    def prepare(self, permanent: Permanent) -> None:
        """A creature with a prepare spell becomes prepared (nothing happens if it already is)."""
        if self.on_battlefield(permanent) and permanent.card.prepare and not permanent.prepared:
            permanent.prepared = True
            self.broadcast({"event": "prepared", "card": permanent.card.name})

    def unprepare(self, permanent: Permanent) -> None:
        if permanent.prepared:
            permanent.prepared = False
            self.broadcast({"event": "unprepared", "card": permanent.card.name})

    def _become_temporary_copy(self, seat: Seat, permanent: Permanent, keyword: str) -> None:
        """Cursed Mirror: as it enters, it may become a copy of any creature on the battlefield until end of turn, except it has
        `keyword`."""
        options = [p for s in self.live_seats() for p in s.battlefield if "Creature" in p.card.type_line]
        if not options:
            return
        pick = seat.player.choose(CLONE_PROMPT + permanent.card.name, [self.label(p) for p in options] + [NOT_A_COPY])
        if pick < len(options):
            self.become_copy_until_end_of_turn(permanent, options[pick], keyword, seat)

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

    def copy_ability(self, item: StackItem, controller: Seat) -> None:
        """Put a copy of an activated ability on the stack under `controller`'s control; it resolves first, with the same
        targets and X (new targets are not chosen)."""
        if item not in self.stack:
            return
        self.stack.append(StackItem(item.card, controller, item.effects, list(item.targets), item.ability, item.source, x=item.x,
                                    sacrificed_power=item.sacrificed_power, tapped_power=item.tapped_power))
        self.broadcast({"event": "copied_ability", "seat": controller.index, "card": item.card.name})

    def copy_spell_for_each_other_creature(self, item: StackItem, caster: Seat, source: Permanent) -> None:
        """Mirrorwing Dragon: `caster` copies the spell once for each other creature they control that it could target; each
        copy targets that creature instead of `source`."""
        if item not in self.stack:
            return
        kind = next((target_kind(e) for e in item.effects if target_kind(e)), None)
        if kind is None:
            return
        legal = [p for _, p in self.target_options(kind, caster, source_qualities(item.card))]
        for creature in [p for p in caster.battlefield if "Creature" in p.card.type_line and p is not source and p in legal]:
            targets = [[creature if t is source else t for t in target] if isinstance(target, list) else
                       creature if target is source else target for target in item.targets]
            self.stack.append(StackItem(item.card, caster, item.effects, targets, x=item.x, kicked=item.kicked,
                                        kickers=item.kickers, is_copy=True))
            self.broadcast({"event": "copied_spell", "seat": caster.index, "card": item.card.name})
            self._observe("copy", item.card, caster)

    def copy_spell(self, item: StackItem, controller: Seat, new_targets: bool = False) -> None:
        """Put a copy of a spell on the stack under `controller`'s control; it resolves first. It isn't cast, and it
        stops existing instead of going to the graveyard. With `new_targets` the copy's controller chooses its
        targets again (the old ones are still legal choices)."""
        if (item not in self.stack and item is not self.resolving_item) or item.ability:  # (a spell may copy itself as it resolves)
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
        if rule.kind == "unless_control":  # a planeswalker, a basic land, a Mountain, a legendary creature, a Mount or Vehicle
            return not any(any(all(_has_type(p.card, word) for word in alternative.split("+")) for alternative in rule.types)
                           for p in seat.battlefield)
        if rule.kind == "unless_a_player_life":
            return not any(s.life <= rule.count for s in self.live_seats())
        if rule.kind == "if_lands_at_least":
            return lands >= rule.count
        if rule.kind == "if_starting_player":
            return seat.index == self.starting_seat
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

    def hideaway(self, seat: Seat, source: Permanent, count: int) -> None:
        """Hideaway N: look at the top N cards, exile one face down (remembered by `source`), the rest go to the bottom of
        the library in a random order."""
        top = seat.library[:count]
        if not top:
            return
        pick = seat.player.choose(HIDEAWAY_PROMPT + source.card.name, [c.name for c in top]) if len(top) > 1 else 0
        chosen = top[pick]
        rest = [c for i, c in enumerate(top) if i != pick]
        del seat.library[:len(top)]
        self.rng.shuffle(rest)
        seat.library.extend(rest)
        seat.exile.append(chosen)
        source.exiled_with.append((seat, chosen))
        self.broadcast({"event": "hideaway", "seat": seat.index, "card": source.card.name})  # face down: no name

    def play_hideaway(self, seat: Seat, source: Permanent) -> None:
        """"You may play the exiled card without paying its mana cost": a land needs a land drop; a spell is cast free."""
        found = next(((owner, card) for owner, card in source.exiled_with if any(c is card for c in owner.exile)), None)
        if found is None:
            return
        owner, card = found
        is_a_land = is_land(card)
        if is_a_land and seat.lands_played >= 1:
            return  # it stays hidden away until a land can be played
        if seat.player.choose(HIDEAWAY_PLAY_PROMPT + card.name, ["Play it", "Don't"]) != 0:
            return
        source.exiled_with.remove(found)
        if is_a_land:
            owner.exile = [c for c in owner.exile if c is not card]
            self._enter(seat, Permanent(card, sick=True))
            seat.lands_played += 1
            self.broadcast({"event": "play_land", "seat": seat.index, "card": card.name, "from": "exile"})
        else:
            self._cast(seat, card, owner.exile, free=True)

    def karoo(self, seat: Seat, source: Permanent, land_type: str) -> None:
        """The Karoo cycle: return an untapped land of the type you control to its owner's hand, or sacrifice the Karoo."""
        if not self.on_battlefield(source):
            return
        options = [p for p in seat.battlefield if p is not source and not p.tapped and _has_type(p.card, land_type)]
        if options:
            pick = seat.player.choose(KAROO_PROMPT + source.card.name,
                                      [f"Return {self.label(p)}" for p in options] + [SACRIFICE_IT])
            if pick < len(options):
                self.return_to_hand(options[pick])
                return
        self._leave_battlefield(source, "sacrificed")

    def _leave_battlefield(self, permanent: Permanent, reason: str, destination: str = "graveyard") -> None:
        self._leave_together([(permanent, reason)], destination)

    def _leave_together(self, leaving: list[tuple[Permanent, str]], destination: str = "graveyard") -> None:
        outer = self._batch
        self._batch = set() if outer is None else outer  # watchers of "one or more" hear of it once
        try:
            self._leave_together_now(leaving, destination)
        finally:
            self._batch = outer

    def _leave_together_now(self, leaving: list[tuple[Permanent, str]], destination: str) -> None:
        """Permanents leave the battlefield at the same moment (a board wipe, or several
        creatures with lethal damage). They all see each other go (CR 603.10a), so a creature
        that watches for deaths triggers for every other creature that died with it."""
        leaving = [(p, reason) for p, reason in leaving if self.on_battlefield(p)]
        for permanent, _ in leaving:
            permanent.last_power = self.power(permanent)
            permanent.last_controller = self.controller_of(permanent)
            permanent.last_auras = {s.index: n for s in self.seats
                                    if (n := sum(p.attached_to is permanent and "Aura" in p.card.type_line for p in s.battlefield))}
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
        destination_all = destination
        for permanent, _ in leaving:
            controller = permanent.last_controller
            destination = ("exile" if destination_all == "graveyard" and permanent.counters.get("finality")
                           and "Creature" in permanent.card.type_line else destination_all)  # a finality counter: exiled, not dying
            if permanent.unearthed:
                destination = "exile"  # unearth: exiled if it would leave the battlefield, so it never dies or goes to a hand
            if destination == "graveyard":
                if self.graveyarded_turn != self.turn:
                    self.graveyarded_turn, self.graveyarded_count = self.turn, 0
                self.graveyarded_count += 1
            self.trigger("leaves", permanent, controller)  # "When this creature leaves the battlefield" (Soulgorger Orgg)
            if destination == "graveyard":  # Rancor: "put into a graveyard from the battlefield"; a token does too (CR 111.7)
                self.trigger("put_into_graveyard", permanent, controller)
                self._observe("permanent_to_graveyard", permanent.card, controller, subject=permanent, extra=gone)
            if destination == "graveyard" and "Creature" in permanent.card.type_line:
                if self._is_modified(permanent, controller):
                    controller.modified_died_turn = self.turn
                if self.deaths_turn != self.turn:
                    self.deaths_turn, self.deaths_count = self.turn, 0
                self.deaths_count += 1
                if controller.died_turn != self.turn:
                    controller.died_turn, controller.died = self.turn, 0
                controller.died += 1
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
            where = destination
            if destination == "graveyard" and permanent.paragon_life is not None:  # "exile it and you gain 2 life"
                where = "exile"
                self.change_life(permanent.paragon_life[0], permanent.paragon_life[1])
            if not _is_token(permanent.card):  # tokens stop existing once they leave (CR 111.7)
                self._move_card(permanent.owner or controller, permanent.card, where)
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
                self._left_graveyard(seat, cards)

    def _factor(self, seat: Seat, attribute: str) -> int:
        """How many times as many tokens or counters `seat`'s replacement effects make (Doubling Season stacks)."""
        factor = 1
        for permanent in seat.battlefield:
            factor *= getattr(replacement_effects(permanent.card), attribute)
        return factor

    def _counters_to_add(self, seat: Seat, card: Card, counter: str, count: int,
                         receiver: Permanent | None = None) -> int:
        """Counters going onto a permanent `seat` controls: +1/+1 counters get Hardened Scales' extra one first
        (Benevolent Hydra's only for other creatures), then Doubling Season doubles."""
        if counter == "+1/+1":
            creature = "Creature" in card.type_line
            for p in seat.battlefield:
                replacements = replacement_effects(p.card)
                count += replacements.plus_one_permanents
                if creature or "Artifact" in card.type_line:
                    count += replacements.plus_one_artifacts
                if creature:
                    count += replacements.plus_one + (replacements.plus_one_others if p is not receiver else 0)
        return count * self._factor(seat, "counters")

    def _trigger_times(self, controller: Seat, event: str, entering: Card | None, cause: Seat | None = None,
                       source: Permanent | None = None) -> int:
        """A triggered ability of `source` triggers once, plus once more for each Harmonic Prodigy (another one) when `source` is a
        Shaman or Wizard, plus what _trigger_times_entering adds."""
        times = self._trigger_times_entering(controller, event, entering, cause)
        if source is not None and {"Shaman", "Wizard"} & set(self.subtypes(source)):
            times += sum(replacement_effects(p.card).extra_trigger == "wizard" for p in controller.battlefield if p is not source)
        return times

    def _trigger_times_entering(self, controller: Seat, event: str, entering: Card | None, cause: Seat | None = None) -> int:
        """How many times an ability of `controller`'s triggers: once, plus once more for each Panharmonicon when an
        artifact or creature (or any permanent, for Yarok) is entering the battlefield, and for each Veyran when
        `controller` casts or copies an instant or sorcery spell."""
        if event in ("cast", "copy") and entering is not None and cause is controller \
                and ("Instant" in entering.type_line or "Sorcery" in entering.type_line):
            return 1 + sum(replacement_effects(p.card).extra_trigger == "spell" for p in controller.battlefield)
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
        if zone == "graveyard":  # "Whenever a creature card is put into your graveyard from anywhere"
            self._observe("card_to_graveyard", card, seat)

    def _check_state(self) -> None:
        """State-based actions (CR 704.5): losing the game, lethal damage, zero toughness or loyalty."""
        while True:
            changed = False
            for seat in self.live_seats():
                if (not seat.citys_blessing and len(seat.battlefield) >= 10
                        and any(has_keyword(p.card, "ascend") for p in seat.battlefield)):
                    seat.citys_blessing = True
                    self.broadcast({"event": "citys_blessing", "seat": seat.index})
                reason = ("life" if seat.life <= 0
                          else "empty_library" if seat.drew_from_empty
                          else "poison" if seat.player_counters.get("poison", 0) >= POISON_LIMIT
                          else "commander_damage" if any(d >= COMMANDER_DAMAGE_LIMIT for d in seat.commander_damage.values())
                          else None)
                if reason:
                    seat.lost = True
                    seat.battlefield = []  # CR 800.4a: their objects leave the game
                    self.stack = [item for item in self.stack if item.controller is not seat]
                    self.combat.attacks = [a for a in self.combat.attacks
                                           if a.defender is not seat and a.controller is not seat]
                    self.broadcast({"event": "player_lost", "seat": seat.index, "reason": reason})
                    if self.monarch is seat:  # CR 725.4: the active player takes it, if they're still in
                        self.monarch = None
                        if not self.seats[self.active].lost:
                            self.become_monarch(self.seats[self.active])
                    if self.initiative is seat:  # CR 726.4: the active player takes it, if they're still in
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
                                             or self.protected_from(host, source_qualities(permanent.card))
                                             and not keeps_its_protection_aura(permanent.card)):  # Flickering Ward stays
                        self.detach(permanent)  # CR 704.5n: Equipment stays, unattached
                        host = None
                    if "Aura" in permanent.card.type_line and host is None:
                        if permanent.bestowed_from is not None:  # CR 702.103f: it becomes a creature again
                            permanent.card, permanent.bestowed_from = permanent.bestowed_from, None
                            self.broadcast({"event": "bestow_ended", "card": permanent.card.name})
                            changed = True
                        else:
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
        for spectator in self.spectators:
            spectator.notify(event)


def _has_type(card: Card, kind: str) -> bool:
    """Whether a card has a type or subtype: "creature", "Plains", "Snake"."""
    return kind.lower() in card.type_line.lower().replace("—", " ").split()


def _watch_type_matches(kind: str, card: Card) -> bool:
    """Whether `card` is what a watch looks for: "creature", "land", ..., or for casts
    "spell", "creature spell", "noncreature spell", "instant or sorcery spell", "red spell",
    "historic spell", "aura, equipment, or vehicle spell", ..."""
    if kind == "spell with {x} in its mana cost":
        return "{X}" in card.mana_cost
    if kind == "permanent spell with a mana cost that contains {x}":
        return "{X}" in card.mana_cost and not ("Instant" in card.type_line or "Sorcery" in card.type_line)
    if kind == "instant or sorcery spell with {x} in its mana cost":
        return "{X}" in card.mana_cost and ("Instant" in card.type_line or "Sorcery" in card.type_line)
    kind = kind.removesuffix(" spell").removesuffix("spell").strip()
    if not kind or kind in ("expend", "permanent"):  # (an expend watch has no kind of card; a permanent is any)
        return True
    if kind == "multicolored":
        return len(card.colors) >= 2
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
    if kind == "nonland permanent":
        return _is_permanent(card) and not is_land(card)
    if kind == "basic land":
        return "Basic" in card.type_line and "Land" in card.type_line
    if kind == "nonbasic land":
        return "Basic" not in card.type_line and "Land" in card.type_line
    words = kind.replace(",", "").split()
    if len(words) > 1 and all(w.startswith("non") for w in words):  # "noncreature, nonland"
        return all(_card_matches(w, card) for w in words)
    if kind.startswith("non") and " " not in kind:  # "nonland", "noncreature"
        return kind[3:].capitalize() not in card.type_line
    if kind.startswith("legendary"):  # "legendary creature": legendary, and the rest of the kind
        return "Legendary" in card.type_line and _card_matches(kind.removeprefix("legendary").strip() or "card", card)
    return any(_type_part_matches(t, card) for t in kind.split(" or "))


def _type_part_matches(part: str, card: Card) -> bool:
    if part == "non-aura enchantment":  # Excava
        return "Enchantment" in card.type_line and "Aura" not in card.type_line
    return part.capitalize() in card.type_line


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
    if kind == "targets a creature":  # Killian, Ink Duelist
        return _targets_a_creature(card)
    return kind.capitalize() in card.type_line


def _targets_a_creature(card: Card) -> bool:
    """Whether casting the card means choosing a creature as a target: an Aura that enchants one, or a spell with such a target."""
    if (enchants := aura_kind(card)) is not None:
        return "creature" in enchants
    return any("creature" in (target_kind(e) or "") for e in (_effects(card) or []))


def _instant_speed(card: Card) -> bool:
    return "Instant" in card.type_line or has_keyword(card, "flash")


def _split_controller(kind: str) -> tuple[str, str | None]:
    """ "creature an opponent controls" -> ("creature", "opponent"); "creature" -> ("creature", None)."""
    for suffix, who in ((" an opponent controls", "opponent"), (" you don't control", "opponent"),
                        (" you control", "you"), (" you own", "own")):
        if kind.endswith(suffix):
            return kind.removesuffix(suffix), who
    return kind, None


def _permanent_matches(kind: str, card: Card) -> bool:
    kind = re.sub(r", (?=non)", " ", kind)  # "noncreature, nonland permanent", "nonland, nontoken permanent"
    if m := re.fullmatch(r"non(white|blue|black|red|green|artifact|creature|land|enchantment|legendary) (.+)", kind):  # "nonblack creature"
        has = m[1].capitalize() in card.type_line if m[1] in ("artifact", "creature", "land", "enchantment", "legendary") else {
            "white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}[m[1]] in card.colors
        return not has and _permanent_matches(m[2], card)
    if m := re.fullmatch(r"non-(\w+) (.+)", kind):  # "non-Pilot creature"
        return m[1].capitalize() not in card.type_line.partition("\u2014")[2].split() and _permanent_matches(m[2], card)
    if " or " in kind and any(part.startswith("non") for part in kind.split(" or ")):  # "noncreature artifact or noncreature enchantment"
        return any(_permanent_matches(part, card) for part in kind.split(" or "))
    if kind == "any":
        return "Creature" in card.type_line or "Planeswalker" in card.type_line
    if kind == "permanent":
        return True
    if kind == "nonland permanent":
        return not is_land(card)
    if kind == "monocolored permanent":
        return len(card.colors) == 1
    if kind == "nonbasic land":
        return "Land" in card.type_line and "Basic" not in card.type_line
    if kind.endswith(" token"):  # "creature token"
        return _is_token(card) and _permanent_matches(kind.removesuffix(" token"), card)
    if kind.startswith("nontoken "):
        return not _is_token(card) and _permanent_matches(kind.removeprefix("nontoken "), card)
    if kind.endswith(" creature") and " " not in kind.removesuffix(" creature"):  # "Blinkmoth creature"
        return "Creature" in card.type_line and kind.removesuffix(" creature").capitalize() in card.type_line.partition("—")[2].split()
    return any(t.capitalize() in card.type_line for t in re.split(r",? or |, ", kind) if t != "player")


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
