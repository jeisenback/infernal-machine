"""Commander game: setup, mulligans and the turn/priority loop.

Players act only through the Player protocol, so TCP and local players are
interchangeable. Actions so far: play a land, cast a spell (including your
commander, with commander tax), and pass priority. Mana comes from lands and
from permanents with simple mana abilities. Spells use the stack; instants and
sorceries do what the effects package understands of their rules text, and permanents'
other rules text is not implemented yet.
"""

from __future__ import annotations

import dataclasses
import itertools
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from .analysis import is_land
from .cards import Card, Deck, has_keyword, shown_type_line
from . import characteristics
from .characteristics import LOSES_HEXPROOF, MINUS, PLUS, Modifier, source_qualities
from .combat import Attack, Combat
from . import casting
from .effects import (EVENTS, Quantity, MorphCost, ReturnWithCounter, heard_on, morph_of, is_room, room_view, rules_lines, CANT_ATTACK, CANT_BLOCK, LOSES_ALL, NO_UNTAP, PROTECTION_CHOSEN, ActivatedAbility, NinjutsuEnter, AlternativeCost, AttachAura, EntersTapped, GiveBack, Modal,
                      Amount, Condition, GraveyardCast, MassFilter, TriggeredAbility, WardCounter,
                      replacement_effects, clone_kind, temporary_clone_keyword, is_class, class_view, keeps_its_protection_aura, copies_per_sacrifice, graveyard_statics, aura_controls, saga_chapters, granted_abilities, untaps_in_other_untap_steps, suspend_of, clone_extra_counters, chooses_creature_type, clone_is_artifact, enters_by_discarding_land, is_chosen_type_itself, annihilator_of, toxic_of, dredge_of, day_night_face, ninjutsu_of, foretell_of, disturb_of, gift_of, FISH, OCTOPUS, PayToReturnSelf, ReturnThisFromGraveyard, Backup, encore_cost, eternalize_cost, eternalize_discards, unearth_cost, damage_prevention, damage_modifiers, DamageModifier, rules_statics, CLUE, FOOD, TREASURE, madness_cost, bestow_aura, line_effects, ThroneOfTheDeadThree, activated_abilities, cycling, hand_abilities, chooses_color, color_choice_excludes, may_skip_untap, kicked_effects, attached_abilities, aura_kind, enters_tapped_rule, reconfigure_cost, cumulative_upkeep, devour, echo_cost, reanimation_aura, enters_prepared, enters_with_counters, extra_votes, graveyard_casts, is_aftermath, graveyard_permission, CastExiledCopy, no_max_hand_size, begins_on_battlefield, hand_size_counter, power_toughness_amount, players_have_no_max_hand,
                      SacrificeSelf,
                      printed_protection, protection_tokens, ward_cost, ward_fields,
                      filter_mana_ability, follows_target, mana_spent_trigger, spell_effects, static_abilities, target_kind,
                      triggered_abilities, uses_player, uses_source, uses_subject)
from .undercity import ROOMS, START
from .filters import has_type, parse_filter
from .mana import Cost, cost_of, parse_cost
from .payment import ManaPayer, ManaSource, Payment
from .player import Player

_T = TypeVar("_T")

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
_COLOR_LETTERS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
EVERYTHING = 10**9  # more damage than there will ever be: "prevent all damage"
SHUFFLED = "library_shuffled"  # where a card goes when it is shuffled into its owner's library instead of a graveyard
ETERNALIZE = "Eternalize: "  # followed by the card's name
UNEARTH = "Unearth: "  # followed by the card's name
SUSPEND = "Suspend: "  # followed by the card's name
FORETELL = "Foretell: "  # followed by the card's name: pay {2} and exile it face down from the hand
CAST_DISTURB = "Cast with disturb: "  # followed by the card's name: its back face, from the graveyard
CAST_FORETOLD = "Cast foretold: "  # followed by the card's name: cast from exile for its foretell cost, on a later turn
FORETELL_COST = "{2}"
NINJUTSU = "Ninjutsu: "  # followed by the card's name: return an unblocked attacker, and it comes in attacking in its place
GIFT_PROMPT = "Promise a gift with "  # followed by the card's name; options: no gift, or one opponent to give it to
NINJUTSU_PROMPT = "Return which unblocked attacker to hand for ninjutsu with "  # followed by the card's name
CAST_PARAGON = "Cast from graveyard (once a turn): "  # Serra Paragon
PLAY_PARAGON = "Play land from graveyard: "
PLAY_GRAVEYARD = "Play land from the graveyard: "  # Crucible of Worlds: any number of lands, within the land drops
CAST_EXILE = "Cast from exile: "  # a card exiled "you may play it this turn"
FOREVER = 10**9  # the last turn of a permission that does not run out (a card on an adventure)
CAST_PREPARED = "Cast prepared: "  # a copy of a prepared creature's spell
PLAY_EXILE = "Play land from exile: "
IMPRINT_PROMPT = "Exile which card from your hand? "
AMASS_PROMPT = "Put the counters on which Army? "
MOX_DIAMOND_PROMPT = "Discard which land to put it onto the battlefield? "
MANA_COLOR_PROMPT = "Which color of mana? "
REVEAL_CHOSEN_PROMPT = "Reveal it and put it into your hand? "
CYCLE = "Cycle: "
ACTIVATE_HAND = "Activate from hand: "  # followed by the card's name: "{U/R}{U/R}, Discard this card: ..." (Magma Opus)
ACTIVATE_GRAVEYARD = "Activate from graveyard: "  # followed by the card's name: "{B}{G}: Return this card from your graveyard to the battlefield tapped."
REVEAL_PROMPT = "Reveal a card from your hand for "  # followed by the land's name
SHOCK_PROMPT = "Pay life so it enters untapped? "  # followed by the land's name
ACTIVATE = "Activate: "  # followed by "<permanent label>: <ability text>"
UNLOCK = "Unlock: "  # followed by "<door name> of <Room label>": pay a locked door's mana cost (a sorcery-speed special action)
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
MANIFEST_DREAD_PROMPT = "Manifest which card? "  # the other goes to the graveyard
DANCE_PROMPT = "Exile the top card of your library? "  # followed by "(N exiled, total mana value M)"; Yes or No
DANCE_CAST_PROMPT = "Cast for free: "  # followed by the card's name; Yes or No
TURN_UP = "Turn face up: "  # followed by the manifested creature's label
CAST_FACE_DOWN = "Cast face down: "  # Morph, Megamorph and Disguise: followed by the card's name
FACE_DOWN = Card(name="Face-down creature", mana_cost="{3}", cmc=3.0, type_line="Creature", power="2", toughness="2")
FACE_DOWN_DISGUISED = dataclasses.replace(FACE_DOWN, oracle_text="Ward {2}")  # Disguise: a face-down creature with ward {2}
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
STACK_TARGET_KINDS = {  # what "Change the target of target ..." can be aimed at: (which spells or abilities, given their lone target
    # and the permanent whose ability this is; whether they need a lone target)
    "spell with a single target": (lambda item, target, me: not item.ability, True),
    "spell or ability with a single target": (lambda item, target, me: True, True),
    "activated ability with a single target": (lambda item, target, me: isinstance(item.ability, ActivatedAbility), True),
    "instant or sorcery spell with a single target": (lambda item, target, me: not item.ability and bool(
        re.search(r"\b(Instant|Sorcery)\b", item.card.type_line)), True),
    "spell that targets only a player": (lambda item, target, me: not item.ability and isinstance(target, Seat), True),
    "spell that targets only a single creature": (lambda item, target, me: not item.ability and isinstance(target, Permanent)
                                                  and "Creature" in target.card.type_line, True),
    "spell that targets only this creature": (lambda item, target, me: not item.ability and target is me, True),
    "spell or ability that targets only this creature": (lambda item, target, me: target is me, True),
    "spell or ability": (lambda item, target, me: True, False),  # Deflecting Swat, Spellskite
}
MORPH_RETURN_PROMPT = "Return which permanent to turn face up "  # followed by the creature's name
CHANGE_WHICH_PROMPT = "Change which target of "  # followed by the spell's name
NO_TARGET = "No target"  # the choice that leaves out an "up to one target"
SACRIFICE_PROMPT = "Choose a creature to sacrifice"
SACRIFICE_COST_PROMPT = "Choose what to sacrifice for "  # followed by the spell's name
DISCARD_COST_PROMPT = "Choose a card to discard for "  # followed by the ability's source
EXILE_COST_PROMPT = "Choose a card to exile from your graveyard for "  # followed by the ability's source
COST_PROMPT = "Choose how to cast "  # followed by the spell's name; options: "Pay {2}{U}{U}", then alternative costs
ENTWINE_PROMPT = "Pay the entwine cost for "  # followed by the spell's name; options: YES_NO
MADNESS_PROMPT = "Cast it for its madness cost: "  # followed by the card's name; options: YES_NO
BUYBACK_PROMPT = "Pay the buyback cost for "  # followed by the spell's name; options: YES_NO
SYLVAN_PROMPT = "Draw two additional cards with Sylvan Library? "  # options: Yes, No
DREDGE_PROMPT = "Dredge instead of drawing a card? "  # options: Draw a card, then one per card that can be dredged
SYLVAN_CHOOSE_PROMPT = "Choose a card you drew this turn: "  # asked twice, for the two cards
SYLVAN_PAY_PROMPT = "Pay life for it or put it on top of your library: "  # followed by the card's name
REBOUND_PROMPT = "Cast it again with rebound: "  # followed by the card's name; options: YES_NO
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
DAMAGE_ORDER_PROMPT = "Choose the order the damage is changed in: "  # followed by who is dealt it; options are the orders, least damage first
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
    lured_turn: int = 0  # the turn all creatures able to block it have to ("All creatures able to block target creature this turn do so.")
    must_block_turn: int = 0  # the turn it has to block if able ("Target creature blocks this turn if able.")
    must_block_what: "Permanent | None" = None  # ... that creature in particular ("blocks this creature this turn if able")
    vow_of: "Seat | None" = None  # Promise of Loyalty: while it has a vow counter it can't attack this player
    escaped: bool = False  # cast with escape: "escapes with two +1/+1 counters on it" (Woe Strider)
    turn_up_cost: "MorphCost | None" = None  # Morph, Megamorph, Disguise: what it costs to turn it face up (a manifested card pays its own mana cost)
    megamorph: bool = False  # it gets a +1/+1 counter when it is turned face up
    doors: tuple[str, ...] = ()  # a Room: the names of its unlocked doors (its `card` reads as only those; the whole card is `real_card`)
    cast: bool = False  # it came from a spell that was cast ("When it enters, if you cast it")
    returns_when_dies: int = 0  # Malakir Rebirth: the turn it gained "When this creature dies, return it to the battlefield tapped"
    chosen_type: str | None = None  # "As this enters, choose a creature type." (Patchwork Banner)
    chosen_color: str | None = None  # "As this enters, choose a color." (a color letter)
    manifested: bool = False  # a face-down 2/2 whose real card is `real_card`; a creature card can be turned face up
    bestowed_from: "Card | None" = None  # a bestowed Aura: the creature card it goes back to when its creature leaves
    must_attack: "Seat | None" = None  # an Encore token: it attacks this player this turn if able
    goaded_by: "Seat | None" = None  # until that player's next turn it must attack, and not them if possible
    prepared: bool = False  # a prepare creature whose controller may cast a copy of its spell
    renowned: bool = False  # Renown: it has already got its counters
    transformed_from: "Card | None" = None  # a transformed double-faced permanent: its front face (`card` is the back face)
    echo_pending: bool = False  # its echo cost is due at its controller's next upkeep
    stored: int = 0  # a number it remembers (the life Soulgorger Orgg's controller lost)
    goad_forever: "Seat | None" = None  # goaded for the rest of the game by this player (Life of the Party's copies)
    exile_if_dies: int | None = None  # the turn it was marked: exiled instead of dying that turn (Lava Coil)
    unearthed: bool = False  # brought back with unearth: exiled instead of going anywhere else, and at the next end step
    paragon_life: tuple["Seat", int] | None = None  # played with Serra Paragon: (who gains life, how much) when it goes to the graveyard










def _checked(value: _T | None) -> _T:
    """`value` for a caller that has already checked there is one (the action was legal, so the cost can be paid, the card has
    the ability, the spell has targets)."""
    assert value is not None
    return value


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
    cant_be_countered: bool = False  # Cavern of Souls: mana from it was spent to cast this spell
    warped: bool = False  # cast for its warp cost: exiled at the next end step, castable from exile on a later turn
    dashed: bool = False  # cast for its dash cost: haste, and back to its owner's hand at the next end step
    whole: Card | None = None  # cast as one half of this card (an Adventure, a split half): the card that moves between zones
    from_hand: bool = False  # cast from its owner's hand (rebound only works then)
    face_down: tuple[str, "MorphCost"] | None = None  # cast face down: (Morph, Megamorph or Disguise; the cost to turn it face up)
    shuffle_after: bool = False  # Green Sun's Zenith: shuffled into its owner's library once it has resolved
    gift: "Seat | None" = None  # the opponent promised a gift as it was cast
    owner: "Seat | None" = None  # whose card it is when that is not the caster (cast from another player's exile: Plargg and Nassari, Etali)
    foretold: bool = False  # cast from exile after being foretold ("If this spell was foretold")

    @property
    def physical(self) -> Card:
        """The card that leaves the stack: the whole card when one of its halves was cast."""
        return self.whole or self.card

    @property
    def home(self) -> "Seat":
        """Whose zones the card goes to when it leaves the stack: its owner's (CR 108.3, 400.3)."""
        return self.owner or self.controller


GERM = Card(name="Phyrexian Germ", type_line="Token Creature — Phyrexian Germ", colors=("B",), power="0", toughness="0")
RETURN_WHEN_DIES = TriggeredAbility("dies", (ReturnWithCounter("", True),), False,
                                    "When this creature dies, return it to the battlefield tapped under its owner's control.")
EVOKE_SACRIFICE = TriggeredAbility("enters", (SacrificeSelf(),), False,
                                   "When this permanent enters, if its evoke cost was paid, sacrifice it.")


@dataclass(eq=False)
class PendingTrigger:
    ability: TriggeredAbility
    permanent: "Permanent | None"  # None for a dungeon room's ability, which has no permanent behind it (see `card`)
    controller: "Seat"
    x: int = 0  # for "Whenever you cast a spell with {X}, put X counters ...": that spell's X
    subject: "Permanent | None" = None  # what a watching trigger saw happen
    player: "Seat | None" = None  # who did it
    card: Card | None = None  # for a dungeon room's ability, which has no permanent behind it
    spell: "StackItem | Card | tuple | None" = None  # for a cast trigger: the spell that was cast

    @property
    def source(self) -> Card:
        return self.card or _checked(self.permanent).card


@dataclass(eq=False)
class Seat:
    player: Player
    index: int
    life: int = STARTING_LIFE
    library: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    exile_play: list[tuple[Card, int]] = field(default_factory=list)  # exiled cards its owner may play, and the last turn they can
    borrowed: list[tuple[Card, "Seat"]] = field(default_factory=list)  # cards in this exile that belong to other players (Ragavan), and whose
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
    token_turn: int | None = None  # the last turn this player created a token
    damage_taken_turn: int | None = None  # the turn `damage_taken` counts for
    damage_taken: int = 0  # the damage dealt to this player that turn
    attackers_turn: int | None = None  # the turn `most_attackers` counts for
    most_attackers: int = 0  # the creatures this player attacked with that turn
    life_lost_amount: int = 0  # how much they lost on life_lost_turn
    keep_pool_turn: int | None = None  # the turn its mana pool is kept as steps end (Rousing Refrain)
    suspended: list = field(default_factory=list)  # [card, time counters] for each card suspended in exile
    foretold: list = field(default_factory=list)  # (turn, card) for each foretold card in exile (it can be cast from the next turn on)
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
    drawn_turn: int | None = None  # the turn `drawn_cards` are from
    drawn_cards: list = field(default_factory=list)  # the cards it drew that turn (Sylvan Library)
    protected: bool = False  # protection from everything until its next turn begins (The One Ring)
    life_locked: bool = False  # its life total can't change until its next turn begins (Teferi's Protection)
    extra_lands: int = 0  # additional lands this player may play on `extra_lands_turn` (Explore)
    extra_lands_turn: int | None = None
    rebounding: list[tuple[Card, int]] = field(default_factory=list)  # cards exiled by rebound, and the turn they were: cast at the next upkeep
    cast_barred: tuple[int, str] | None = None  # (the turn, "" or "noncreature") this player can't cast spells on (Silence)
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
    wins_game: bool = False  # Laboratory Maniac: it drew from an empty library with the card out
    lost: bool = False

    @property
    def name(self) -> str:
        return self.player.name


class Game:
    # What the mana being paid is for, so "Spend this mana only ..." sources can say whether they qualify: a spell, or an
    # ability whose cost has {X}.

    _draw_step_draw = False  # the turn-based draw of a draw step is in progress (Orcish Bowmasters ignores it)

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
        self.payer = ManaPayer(self)
        self.caster = casting.Caster(self)
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
        self.previous_player: Seat | None = None  # whose turn came before this one, for the day/night rule
        self.day_night: str | None = None  # None until a permanent with daybound or nightbound is around, then "day" or "night"
        self._batch: set[tuple[int, int]] | None = None  # watchers of "one or more ..." already told about this simultaneous event
        self.at_upkeep: list[tuple[int, Callable[[], None]]] = []  # (turn made, what) to do as the next turn's upkeep begins
        self.spectators: list = []  # watchers with notify(event): they see every public event and the board, never a hand
        self.at_end_step: list[tuple[int, Callable[[], None]]] = []  # (turn, what) to do as that turn's next end step begins
        self.at_owner_upkeep: list[tuple[Seat, int, Callable[[], None]]] = []  # (whose upkeep, the turn it was set up, what)
        self.targeting_x = 0  # the X of the spell whose targets are being chosen ("up to X target creatures")
        self.targeting_player: Seat | None = None  # the player a trigger is about while its targets are chosen ("that player controls")
        self.targeting_source: Permanent | None = None  # the permanent whose ability is having its targets chosen ("this creature")
        self.targeting_max: int | None = None  # how many targets "any number of target ..." may have (Strive: what the mana pays for)
        self.cost_sacrificed_power = 0  # the power of what the ability being activated sacrificed
        self.cost_tapped_power = 0  # the power of what the ability being activated tapped as a cost (Station)
        self.x_value = 0  # X of the spell resolving right now
        self.resolving_source: Permanent | None = None  # the source of the ability resolving right now
        self.resolving_item: StackItem | None = None  # what is resolving right now
        self.resolving_damaged: list[Permanent] = []  # the creatures the spell or ability resolving now has dealt damage to
        self.resolving_target: Any = None  # the last target chosen for it, which "that creature" in a condition means
        self.resolving_colors: frozenset[str] = frozenset()  # its colors (for protection from damage)
        self.fog_turn: int | None = None  # the turn all combat damage is prevented (Fog)
        self.shields: list[list] = []  # [what is shielded, damage still to prevent, turn]: "prevent the next 2 damage ... this turn"

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
            self.previous_player = self.seats[self.active]
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
            self._update_day_night()
            seat.protected = seat.life_locked = False  # "until your next turn"
            self.combat = Combat(self)
            seat.battlefield += seat.phased_out  # they phase in first, then untap with everything else
            seat.phased_out = []
            for permanent in seat.battlefield:
                if self.has_keyword(permanent, NO_UNTAP) or "no_untap" in rules_statics(permanent.card) \
                        and not self.loses_abilities(permanent):  # Infinite Coursework; Basalt Monolith
                    pass
                elif permanent.tapped and may_skip_untap(permanent.card) and \
                        seat.player.choose(UNTAP_PROMPT + permanent.card.name, ["Untap", "Leave tapped"]) != 0:
                    pass  # Hollow Trees: left tapped to collect a storage counter at upkeep
                else:
                    self.untap(permanent)
                permanent.sick = False
                permanent.until_next_turn = []
            for other in self.live_seats():  # goad lasts until the goader's next turn
                for permanent in other.battlefield:
                    if permanent.goaded_by is seat:
                        permanent.goaded_by = None
            for other in self.live_seats():  # Seedborn Muse: everything untaps in each other player's untap step
                if other is not seat:
                    for source in other.battlefield:
                        if self.loses_abilities(source):
                            continue
                        for key in rules_statics(source.card):
                            if key == "untap_others":
                                for permanent in other.battlefield:
                                    self.untap(permanent)
                            elif key == "untap_others:artifact":  # Unwinding Clock
                                for permanent in other.battlefield:
                                    if "Artifact" in permanent.card.type_line:
                                        self.untap(permanent)
                            elif key == "untap_others:self":  # Bender's Waterskin
                                self.untap(source)
            for other in self.live_seats():  # Quest for Renewal: untap in each other player's untap step too
                if other is not seat and any(
                        (rule := untaps_in_other_untap_steps(p.card)) and p.counters.get(rule[0], 0) >= rule[1]
                        for p in other.battlefield):
                    for permanent in other.battlefield:
                        if "Creature" in permanent.card.type_line:
                            self.untap(permanent)
        elif self.step == "draw":
            # CR 103.8a: only a two-player game skips the first player's first draw.
            if not (self.turn == 1 and not self.multiplayer):
                self._draw_step_draw = True  # the draw Orcish Bowmasters ignores
                try:
                    self.draw(seat, 1)
                finally:
                    self._draw_step_draw = False
            self.happened("draw_step", seat)  # and "each other player's draw step" (Well of Ideas)
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
                self._rebound(seat)
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
            for holder in self.live_seats():  # "At the beginning of each combat": whoever's turn it is
                for permanent in list(holder.battlefield):
                    self.trigger("each_combat", permanent, holder)
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

    def _rebound(self, seat: Seat) -> None:
        """At the beginning of its owner's next upkeep, a card exiled by rebound may be cast from exile without paying its mana cost."""
        due = [card for card, turn in seat.rebounding if turn < self.turn]
        seat.rebounding = [(card, turn) for card, turn in seat.rebounding if turn >= self.turn]
        for card in due:
            if card in seat.exile and seat.player.choose(REBOUND_PROMPT + card.name, ["Yes", "No"]) == 0:
                self._cast(seat, card, seat.exile, free=True)

    def legal_actions(self, seat: Seat) -> list[str]:
        actions = [PASS]
        if any(not item.ability and has_keyword(item.card, "split second") for item in self.stack):
            return actions  # split second: nobody can cast spells or activate abilities (mana abilities aside) while it is on the stack
        sorcery_timing = seat.index == self.active and self.step in ("main1", "main2") and not self.stack
        if sorcery_timing and seat.lands_played < self._land_drops(seat):
            actions += [PLAY_LAND + c.name for c in _unique(seat.hand) if is_land(c)]
            actions += [PLAY_LAND + c.back.name for c in _unique(seat.hand) if c.back]  # a Pathway's other face
            if self._graveyard_lands(seat):
                actions += [PLAY_GRAVEYARD + c.name for c in _unique(seat.graveyard) if is_land(c)]
        for card in _unique(seat.hand):
            if not is_land(card) and (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, card)) and self._can_cast(seat, card):
                actions.append(CAST + card.name)
            if (other := card.alternate) and not is_aftermath(other) and (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, other)) \
                    and self._can_cast(seat, other):
                actions.append(CAST + other.name)  # the Adventure, or the other half of a split card
        for card in seat.command_zone:
            if (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, card)) and self._can_cast(seat, card, from_command_zone=True):
                actions.append(CAST_COMMANDER + card.name)
        for card in _unique(seat.graveyard):
            for cast in graveyard_casts(card)[:1]:
                if not is_land(card) and (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, card)) and self._can_cast(seat, card, graveyard=cast):
                    actions.append(CAST_GRAVEYARD + card.name)
            if (other := card.alternate) and is_aftermath(other) and (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, other)) \
                    and self._can_cast(seat, other, graveyard=graveyard_casts(other)[0]):
                actions.append(CAST_GRAVEYARD + other.name)  # the Aftermath half
        for card in self._paragon_options(seat):
            if is_land(card):
                if sorcery_timing and seat.lands_played < self._land_drops(seat):
                    actions.append(PLAY_PARAGON + card.name)
            elif (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, card)) and self._can_cast(seat, card):
                actions.append(CAST_PARAGON + card.name)
        for card in _unique(seat.hand):  # Morph: a face-down 2/2 for {3}, as a creature spell
            if (morph := morph_of(card)) and sorcery_timing and not self._cast_barred(seat, card) \
                    and self._payment(seat, FACE_DOWN) is not None:
                actions.append(CAST_FACE_DOWN + card.name)
        actions += [NINJUTSU + c.name for c in self._ninjutsu_cards(seat)]
        if seat.index == self.active:  # Foretell: pay {2} to exile it face down, any time you have priority on your turn
            actions += [FORETELL + c.name for c in _unique(seat.hand)
                        if foretell_of(c) and self._payment(seat, dataclasses.replace(c, mana_cost=FORETELL_COST)) is not None]
        for card in _unique(seat.graveyard):  # Disturb: cast the back face from the graveyard; it is exiled if it would go back
            if (cost := disturb_of(card)) and card.flip is not None \
                    and (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, card.flip)) \
                    and self._can_cast(seat, card.flip, graveyard=GraveyardCast("Disturb", cost)):
                actions.append(CAST_DISTURB + card.name)
        for turn, card in seat.foretold:  # ... and cast it from exile on a later turn for its foretell cost
            if turn < self.turn and card in seat.exile and (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, card)) \
                    and self._can_cast(seat, card, graveyard=GraveyardCast("Foretell", _checked(foretell_of(card)))) \
                    and CAST_FORETOLD + card.name not in actions:
                actions.append(CAST_FORETOLD + card.name)
        for card in _unique(seat.hand):  # Suspend N: pay the cost, exile it with time counters
            if (suspend := suspend_of(card)) and (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, card)) \
                    and self._payment(seat, dataclasses.replace(card, mana_cost=suspend[1])) is not None:
                actions.append(SUSPEND + card.name)
        if sorcery_timing:
            for card in _unique(seat.graveyard):
                if (cost := encore_cost(card)) and self._payment(seat, dataclasses.replace(card, mana_cost=cost)) is not None:
                    actions.append(ENCORE + card.name)
                if (cost := eternalize_cost(card)) and self._payment(seat, dataclasses.replace(card, mana_cost=cost)) is not None \
                        and (seat.hand or not eternalize_discards(card)):
                    actions.append(ETERNALIZE + card.name)
                if (cost := unearth_cost(card)) and self._payment(seat, dataclasses.replace(card, mana_cost=cost)) is not None:
                    actions.append(UNEARTH + card.name)
        for card in _unique([c for c, until in seat.exile_play if self.turn <= until and c in seat.exile]):
            if is_land(card):
                if sorcery_timing and seat.lands_played < self._land_drops(seat):
                    actions.append(PLAY_EXILE + card.name)
            elif (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, card)) and self._can_cast(seat, card, from_hand=False):
                actions.append(CAST_EXILE + card.name)
        for spell in _unique([p.card.prepare for p in seat.battlefield if p.prepared and p.card.prepare]):
            if (sorcery_timing or seat.flash_turn == self.turn or self._instant_speed(seat, spell)) and self._can_cast(seat, spell):
                actions.append(CAST_PREPARED + spell.name)
        actions += [TURN_UP + self.label(p) for p in self._turn_up_options(seat)]  # manifested creature cards
        for card in _unique(seat.hand):
            if (found := cycling(card)) and self._can_cycle(seat, found[1], found[3]):
                actions.append(CYCLE + card.name)
            for ability in hand_abilities(card)[:1]:
                if (not ability.sorcery_speed or sorcery_timing) and self._pay_cost(seat, self._hand_ability_cost(seat, ability)) is not None \
                        and self._effects_possible(seat, ability.effects, source_qualities(card)):
                    actions.append(ACTIVATE_HAND + card.name)
        for card in _unique(seat.graveyard):
            for ability in activated_abilities(card):
                if ability.from_graveyard and self._pay_cost(seat, cost_of(ability.mana_cost)) is not None:
                    actions.append(ACTIVATE_GRAVEYARD + card.name)
                    break
        if sorcery_timing:
            actions += list(self._unlocks(seat))
        actions += list(self._activations(seat, sorcery_timing))
        return actions

    def _door_unlocked(self, room: Permanent, door: Card) -> None:
        """A door of `room` just unlocked: its "When you unlock this door" abilities trigger (and no other door's)."""
        seat = self.controller(room)
        self.broadcast({"event": "door_unlocked", "seat": seat.index, "card": _checked(room.real_card).name, "door": door.name})
        for line in rules_lines(door):
            self.trigger("unlock_door", room, seat, text=line)

    def _unlocks(self, seat: Seat) -> dict[str, tuple[Permanent, Card]]:
        """The locked doors `seat` can unlock now by paying their mana costs, keyed by action text."""
        found = {}
        for room in seat.battlefield:
            if room.real_card is not None and is_room(room.real_card):
                for door in (room.real_card, _checked(room.real_card.alternate)):
                    if door.name not in room.doors and self._payment(seat, door) is not None:
                        found[f"{UNLOCK}{door.name} of {self.label(room)}"] = (room, door)
        return found

    def unlock_door(self, room: Permanent, door: Card) -> None:
        """The door joins the Room's unlocked doors; the Room reads as those doors from now on."""
        room.doors += (door.name,)
        room.card = room_view(room.real_card, room.doors)
        self._door_unlocked(room, door)

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
        if self._ability_barred(permanent):
            return False
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
        if ability.remove_counter and permanent.counters.get(ability.remove_counter, 0) < ability.remove_count:
            return False
        if ability.tap_creatures and len(self._crew_candidates(seat, permanent, ability.tap_legendary, ability.tap_type)) < ability.tap_creatures:
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
        kind = _checked(ability.sacrifice_other)
        return [p for p in seat.battlefield if _permanent_matches(kind, p.card) and not (ability.sacrifice_another and p is source)]

    def _crew_candidates(self, seat: Seat, vehicle: Permanent, legendary: bool = False, kind: str = "") -> list[Permanent]:
        """The untapped creatures that could crew `vehicle` (summoning sickness doesn't matter, CR 702.122); only legendary
        ones, for Relic of Legends."""
        return [p for p in seat.battlefield if p is not vehicle and not p.tapped and "Creature" in p.card.type_line
                and (not legendary or "Legendary" in p.card.type_line) and (not kind or kind in p.card.type_line.partition("\u2014")[2].split())]

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

    def move_counters(self, source: Permanent, destination: Permanent, counter: str | None, count: int | None) -> None:
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
            options = self._crew_candidates(seat, source, ability.tap_legendary, ability.tap_type)
            member = options[seat.player.choose(CREW_PROMPT + name, [self.label(p) for p in options])]
            self.cost_tapped_power += self.power(member)
            self.tap(member)
        if ability.discard_hand:  # Lion's Eye Diamond
            for card in list(seat.hand):
                seat.hand.remove(card)
                self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
                self._discard_into_zone(seat, card)
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
            self.remove_counters(source, ability.remove_counter, ability.remove_count)
        chosen = []
        for _ in range(ability.sacrifice_count if ability.sacrifice_other else 0):
            options = [p for p in self._sacrifice_choices(seat, source, ability) if p not in chosen]
            chosen.append(options[seat.player.choose(SACRIFICE_COST_PROMPT + name, [self.label(p) for p in options])])
        self.cost_sacrificed_power = sum(self.power(p) for p in chosen)
        if chosen:
            self._leave_together([(p, "sacrificed") for p in chosen])

    def _ability_payment(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility,
                         x: int = 0) -> Payment | None:
        cost = (cost_of(ability.mana_cost) if ability.mana_cost else Cost()).with_x(x)
        # A permanent can't tap for mana to pay for its own {T} or sacrifice ability.
        self.payer._spending_x = "{X}" in ability.mana_cost
        try:
            return self._pay_cost(seat, cost, exclude=permanent if ability.tap or ability.sacrifice or ability.exile_source else None)
        finally:
            self.payer._spending_x = False

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

    def _static_rules(self) -> list[tuple[Seat, Permanent, str]]:
        """Every rules-changing static ability on the battlefield: (its controller, the permanent, its key)."""
        return [(s, p, key) for s in self.live_seats() for p in s.battlefield if not self.loses_abilities(p)
                for key in rules_statics(p.card)]

    def _instant_speed(self, seat: Seat, card: Card) -> bool:
        """Whether `seat` may cast `card` at instant speed: an instant, flash, or a permanent that lets it ("You may cast creature
        spells as though they had flash")."""
        if _instant_speed(card):
            return True
        return any(owner is seat and key.startswith("flash:") and _flash_covers(key.removeprefix("flash:"), card)
                   for owner, _, key in self._static_rules())

    def _cast_barred(self, seat: Seat, card: Card) -> bool:
        """Whether a static ability stops `seat` casting `card` now: "Your opponents can't cast spells during your turn" (Kutzil),
        "... during combat" (Marisi), one spell a turn (Rule of Law), "You can't cast creature spells" (Steel Golem)."""
        casts = sum(1 for turn, _ in seat.cast_log if turn == self.turn)
        if seat.cast_barred and seat.cast_barred[0] == self.turn and (not seat.cast_barred[1] or "Creature" not in card.type_line):
            return True  # Silence, Ranger-Captain of Eos
        for owner, _, key in self._static_rules():
            if key == "opp_no_cast:turn" and owner is not seat and self.seats[self.active] is owner:
                return True
            if key == "opp_no_cast:combat" and owner is not seat and self.step in COMBAT_STEPS:
                return True
            if key == "one_spell:each" and casts >= 1 or key == "one_spell:you" and owner is seat and casts >= 1:
                return True
            if owner is seat and key.startswith("no_cast_kind:") and ("Creature" in card.type_line) == (key.endswith(":creature")):
                return True
        return False

    def _land_drops(self, seat: Seat) -> int:
        """How many lands `seat` may play a turn: one, and one more for each "You may play an additional land" it controls."""
        extra = seat.extra_lands if seat.extra_lands_turn == self.turn else 0
        return 1 + extra + sum(1 for owner, _, key in self._static_rules() if owner is seat and key == "extra_land")

    def _graveyard_lands(self, seat: Seat) -> bool:
        return any(owner is seat and key == "graveyard_lands" for owner, _, key in self._static_rules())

    def _land_type_mana(self, land: Permanent) -> frozenset[str]:
        """The mana a land can make because a static ability gives it basic land types: "Each land is a Swamp" (Urborg) for every
        land, "Lands you control are every basic land type" (Dryad of the Ilysian Grove) for its controller's."""
        controller = self.controller_of(land)
        mana: set[str] = set()
        for owner, _, key in self._static_rules():
            if key == "land_type:all_yours" and owner is controller:
                mana |= set("WUBRG")
            elif key.startswith("land_type:") and key != "land_type:all_yours":
                mana.add(key.removeprefix("land_type:"))
        return frozenset(mana)

    def _ability_barred(self, permanent: Permanent) -> bool:
        """Whether a static ability stops the abilities of `permanent` being activated: Stony Silence (artifacts), Grand Abolisher
        (an opponent's artifacts, creatures and enchantments, on its controller's turn). A land's mana ability is not stopped by the
        second."""
        controller = self.controller_of(permanent)
        for owner, _, key in self._static_rules():
            if key == "lock:Artifact" and "Artifact" in permanent.card.type_line:
                return True
            if key.startswith("opp_lock:") and owner is not controller and self.seats[self.active] is owner \
                    and any(t in permanent.card.type_line for t in key.removeprefix("opp_lock:").split(",")):
                return True
        return False

    def uncounterable(self, item: StackItem) -> bool:
        """Whether a permanent its controller has says the spell can't be countered (Rhythm of the Wild, Hexing Squelcher)."""
        if item.cant_be_countered:
            return True
        return any(owner is item.controller and (key == "uncounterable:spell" or key == "uncounterable:creature"
                                                 and "Creature" in item.card.type_line)
                   for owner, _, key in self._static_rules())

    def _can_cast(self, seat: Seat, card: Card, from_command_zone: bool = False,
                  graveyard: GraveyardCast | None = None, from_hand: bool = True) -> bool:
        if self._cast_barred(seat, card):
            return False
        if not self._cast_ways(seat, card, from_command_zone, graveyard, from_hand):
            return False
        effects, colors = kicked_effects(_effects(card), 0) or [], source_qualities(card)
        if not self._effects_possible(seat, effects, colors):
            return False
        cost = parse_cost(card.mana_cost)  # None for a back face, which has no mana cost of its own
        if cost is not None and cost.x and any((kind := target_kind(e)) and kind.endswith(" with mana value x") for e in effects):
            # "target creature with mana value X": some X it can pay for has to match a creature
            return bool(self._x_values_with_targets(seat, effects, colors, self._max_x(seat, card, from_command_zone, ())))
        return True

    def untap(self, permanent: Permanent) -> None:
        """Untap a permanent. One with a stun counter loses a stun counter instead and stays tapped."""
        if not permanent.tapped:
            return
        if permanent.counters.get("stun"):
            self.remove_counters(permanent, "stun", 1)
        else:
            permanent.tapped = False

    def tap(self, permanent: Permanent) -> None:
        """Tap a permanent. A tapped one stays as it is; one that becomes tapped is seen by "Whenever a creature you
        control becomes tapped"."""
        if permanent.tapped:
            return
        permanent.tapped = True
        controller = self.controller_of(permanent)
        if controller is not None:
            self._observe("permanent_taps", permanent.card, controller, subject=permanent)

    def _mana_sources(self, seat: Seat, exclude: Permanent | None = None) -> list[ManaSource]:
        return self.payer._mana_sources(seat, exclude)

    def _convoke_sources(self, seat: Seat, exclude: Permanent | None, taken: list[ManaSource]) -> list[ManaSource]:
        return self.payer._convoke_sources(seat, exclude, taken)

    def _pay_cost(self, seat: Seat, cost: Cost, exclude: Permanent | None = None) -> Payment | None:
        """The permanents to tap for `cost`, or None if it can't be paid (see ManaPayer)."""
        return self.payer._pay_cost(seat, cost, exclude)

    def _spend_mana(self, seat: Seat, sources: list[Permanent]) -> None:
        self.payer._spend_mana(seat, sources)

    def _paying_for(self, seat: Seat, card: Card):
        """While mana is paid for casting `card`, which is still in the zone it is cast from."""
        return self.payer._paying_for(seat, card)

    @staticmethod
    def _restricted_mana_ok(source: Permanent, limited, spell: Card | None) -> bool:
        return ManaPayer._restricted_mana_ok(source, limited, spell)

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







    def _cast(self, seat: Seat, card: Card, zone: list[Card], from_command_zone: bool = False,
              graveyard: GraveyardCast | None = None, prepared: Permanent | None = None, free: bool = False,
              copy: bool = False, bottom_after: bool = False, madness: AlternativeCost | None = None,
              whole: Card | None = None, face_down: tuple[str, MorphCost] | None = None) -> None:
        return self.caster._cast(seat, card, zone, from_command_zone, graveyard, prepared, free, copy, bottom_after, madness, whole, face_down)

    def _cast_ways(self, seat: Seat, card: Card, from_command_zone: bool,
                   graveyard: GraveyardCast | None = None, from_hand: bool = True) -> list[AlternativeCost | None]:
        return self.caster._cast_ways(seat, card, from_command_zone, graveyard, from_hand)

    def cost_reduction(self, seat: Seat, card: Card) -> int:
        """How much less generic mana `card` costs `seat` (Medallions and the like)."""
        return self.caster.cost_reduction(seat, card)

    def _max_x(self, seat: Seat, card: Card, from_command_zone: bool, kickers: tuple[str, ...], extra: str = "") -> int:
        return self.caster._max_x(seat, card, from_command_zone, kickers, extra)

    def _choose_modes(self, seat: Seat, card: Card, modal: Modal, from_command_zone: bool = False,
                      casting: bool = False, source: Permanent | None = None) -> tuple[list, str]:
        return self.caster._choose_modes(seat, card, modal, from_command_zone, casting, source)

    def _choose_targets(self, seat: Seat, effects, source_name: str, source: Permanent | None = None,
                        colors: frozenset[str] = frozenset()) -> tuple[list, list[str]] | None:
        return self.caster._choose_targets(seat, effects, source_name, source, colors)

    def _payment(self, seat: Seat, card: Card, from_command_zone: bool = False, x: int = 0,
                 alternative: AlternativeCost | None = None, kickers: tuple[str, ...] = (), extra: str = "",
                 delve: int = 0) -> Payment | None:
        """The permanents to tap for `card` with X = `x`, or None if it can't be paid for now."""
        return self.caster._payment(seat, card, from_command_zone, x, alternative, kickers, extra, delve)

    def _x_values_with_targets(self, seat: Seat, effects, colors: frozenset[str], most: int) -> list[int]:
        return self.caster._x_values_with_targets(seat, effects, colors, most)






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
        elif action.startswith(PLAY_GRAVEYARD):
            card = _take(seat.graveyard, action.removeprefix(PLAY_GRAVEYARD))
            self._left_graveyard(seat, [card])
            self._enter(seat, Permanent(card, sick=True))
            seat.lands_played += 1
            self.broadcast({"event": "play_land", "seat": seat.index, "card": card.name, "from": "graveyard"})
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
        elif action.startswith(CAST_FACE_DOWN):
            card = next(c for c in seat.hand if c.name == action.removeprefix(CAST_FACE_DOWN))
            kind, cost = _checked(morph_of(card))
            self._cast(seat, FACE_DOWN_DISGUISED if kind == "Disguise" else FACE_DOWN, seat.hand, whole=card, face_down=(kind, cost))
        elif action.startswith(TURN_UP):
            permanent = next(p for p in self._turn_up_options(seat) if self.label(p) == action.removeprefix(TURN_UP))
            self.turn_face_up(seat, permanent)
        elif action.startswith(CYCLE):
            self._cycle(seat, _take(seat.hand, action.removeprefix(CYCLE)))
        elif action.startswith(FORETELL):
            self._foretell(seat, action.removeprefix(FORETELL))
        elif action.startswith(CAST_DISTURB):
            card = next(c for c in seat.graveyard if c.name == action.removeprefix(CAST_DISTURB))
            self._cast(seat, _checked(card.flip), seat.graveyard, graveyard=GraveyardCast("Disturb", _checked(disturb_of(card)), exile_after=True), whole=card)
        elif action.startswith(CAST_FORETOLD):
            self._cast_foretold(seat, action.removeprefix(CAST_FORETOLD))
        elif action.startswith(NINJUTSU):
            self._ninjutsu(seat, action.removeprefix(NINJUTSU))
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
            name = action.removeprefix(CAST_GRAVEYARD)
            card = next((c for c in seat.graveyard if c.name == name), None)
            if card is not None:
                self._cast(seat, card, seat.graveyard, graveyard=graveyard_casts(card)[0])
            else:  # the Aftermath half of a card in the graveyard
                whole = next(c for c in seat.graveyard if c.alternate and c.alternate.name == name)
                half = _checked(whole.alternate)
                self._cast(seat, half, seat.graveyard, graveyard=graveyard_casts(half)[0], whole=whole)
        elif action.startswith(SUSPEND):
            card = next(c for c in seat.hand if c.name == action.removeprefix(SUSPEND))
            counters, cost = _checked(suspend_of(card))
            self._spend_mana(seat, _checked(self._payment(seat, dataclasses.replace(card, mana_cost=cost))))
            seat.hand.remove(card)
            seat.exile.append(card)
            seat.suspended.append([card, counters])
            self.broadcast({"event": "suspended", "seat": seat.index, "card": card.name, "counters": counters})
        elif action.startswith(UNEARTH):
            self._unearth(seat, next(c for c in seat.graveyard if c.name == action.removeprefix(UNEARTH)))
        elif action.startswith(ETERNALIZE):
            self._eternalize(seat, next(c for c in seat.graveyard if c.name == action.removeprefix(ETERNALIZE)))
        elif action.startswith(ENCORE):
            self._encore(seat, next(c for c in seat.graveyard if c.name == action.removeprefix(ENCORE)))
        elif action.startswith(UNLOCK):
            room, door = self._unlocks(seat)[action]
            self._spend_mana(seat, _checked(self._payment(seat, door)))
            self.unlock_door(room, door)
        elif action.startswith(CAST_PREPARED):
            name = action.removeprefix(CAST_PREPARED)
            permanent = next(p for p in seat.battlefield if p.prepared and p.card.prepare and p.card.prepare.name == name)
            prepare = _checked(permanent.card.prepare)
            self._cast(seat, prepare, [prepare], prepared=permanent)
        elif action.startswith(CAST):
            name = action.removeprefix(CAST)
            card = next((c for c in seat.hand if c.name == name), None)
            if card is not None:
                self._cast(seat, card, seat.hand)
            else:  # the other half of a card in hand
                whole = next(c for c in seat.hand if c.alternate and c.alternate.name == name)
                self._cast(seat, _checked(whole.alternate), seat.hand, whole=whole)
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

    def cast_free(self, seat: Seat, card: Card) -> None:
        """Cast `card` from `seat`'s hand without paying its mana cost (it stays in hand if it has no legal target)."""
        self._cast(seat, card, seat.hand, free=True)

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
        return life < seat.life if life else self._pay_cost(seat, cost_of(cost)) is not None

    def _cycle(self, seat: Seat, card: Card) -> None:
        """Cycling: pay the cost, discard the card, and draw a card when the ability resolves."""
        word, cost, effects, life = _checked(cycling(card))
        tapped = _checked(self._pay_cost(seat, cost_of(cost))) if cost else Payment()
        self._spend_mana(seat, tapped)
        if life:
            self.change_life(seat, -life)
        ability = ActivatedAbility(f"{word} {cost}" if cost else f"{word}\u2014Pay {life} life.", effects, mana_cost=cost, life=life)
        self.broadcast({"event": "discard", "seat": seat.index, "card": card.name, "reason": "cycling"})
        self._move_card(seat, card, "graveyard")
        self.stack.append(StackItem(card, seat, list(effects), [], ability))
        self.happened("cycled", seat)
        self.broadcast({"event": "activate", "seat": seat.index, "card": card.name, "ability": _shown(ability.text, card),
                        "targets": [], "tapped": [p.card.name for p in tapped]})

    def _foretell(self, seat: Seat, name: str) -> None:
        """Foretell: a special action. {2} is paid and the card goes from the hand to exile face down; from the next turn it can be cast
        for its foretell cost."""
        card = next(c for c in seat.hand if c.name == name)
        self._spend_mana(seat, _checked(self._payment(seat, dataclasses.replace(card, mana_cost=FORETELL_COST))))
        seat.hand.remove(card)
        seat.exile.append(card)
        seat.foretold.append((self.turn, card))
        self.broadcast({"event": "foretold", "seat": seat.index})
        self.happened("foretold", seat)

    def _cast_foretold(self, seat: Seat, name: str) -> None:
        card = next(c for turn, c in seat.foretold if c.name == name and turn < self.turn and c in seat.exile)
        before = seat.exile.count(card)
        self._cast(seat, card, seat.exile, graveyard=GraveyardCast("Foretell", _checked(foretell_of(card))))
        if seat.exile.count(card) < before:  # it was cast (it stays foretold if it couldn't be)
            seat.foretold.remove(next(entry for entry in seat.foretold if entry[1] == card))

    def _ninjutsu_cards(self, seat: Seat) -> list[Card]:
        """The cards whose ninjutsu `seat` can use right now: after blockers are declared, with an unblocked attacker to return and
        the mana for it. From the hand, or for Commander ninjutsu the command zone too."""
        if self.step != "declare_blockers" or not self._unblocked_attackers(seat):
            return []
        commanders = [c for c in seat.command_zone if (found := ninjutsu_of(c)) and found[1]]
        return [c for c in _unique(seat.hand + commanders)
                if (found := ninjutsu_of(c)) and self._payment(seat, dataclasses.replace(c, mana_cost=found[0])) is not None]

    def _unblocked_attackers(self, seat: Seat) -> list[Attack]:
        return [a for a in self.combat.attacks if a.controller is seat and not a.blocked and not a.blockers and self.on_battlefield(a.attacker)]

    def _ninjutsu(self, seat: Seat, name: str) -> None:
        """Ninjutsu: pay its cost, return an unblocked attacker to its owner's hand, and the ability goes on the stack; when it resolves
        the card comes in tapped and attacking whom the creature attacked."""
        card = next(c for c in self._ninjutsu_cards(seat) if c.name == name)
        cost, _ = _checked(ninjutsu_of(card))
        attacks = self._unblocked_attackers(seat)
        pick = seat.player.choose(NINJUTSU_PROMPT + card.name, [self.label(a.attacker) for a in attacks]) if len(attacks) > 1 else 0
        attack = attacks[pick]
        self._spend_mana(seat, _checked(self._payment(seat, dataclasses.replace(card, mana_cost=cost))))
        self.return_to_hand(attack.attacker)
        ability = ActivatedAbility(f"Ninjutsu {cost}", (NinjutsuEnter(),), mana_cost=cost)
        self.stack.append(StackItem(card, seat, [NinjutsuEnter()], [], ability, player=attack.defender, subject=attack.walker))
        self.broadcast({"event": "ninjutsu", "seat": seat.index, "card": card.name, "returned": attack.attacker.card.name})

    def ninjutsu_enter(self, seat: Seat, item: StackItem) -> None:
        """A ninjutsu ability resolves: the card, if it is still in the hand (or command zone), enters tapped and attacking; it was never
        declared as an attacker, so attack triggers don't see it."""
        card = item.card
        zone = next((z for z in (seat.hand, seat.command_zone) if card in z), None)
        if zone is None:
            return
        zone.remove(card)
        permanent = Permanent(card, sick=True, tapped=True, loyalty=_starting_loyalty(card), owner=seat)
        self._enter(seat, permanent)
        if item.player is not None and self.on_battlefield(permanent):
            self.combat.attacks.append(Attack(permanent, seat, item.player, walker=item.subject))
            self.broadcast({"event": "attack", "seat": seat.index, "card": card.name, "defender": item.player.index})

    def _hand_ability_cost(self, seat: Seat, ability: ActivatedAbility) -> Cost:
        """The mana an ability from the hand costs: Channel abilities cost {1} less for each permanent of a kind they count (Boseiju)."""
        cost = cost_of(ability.mana_cost) if ability.mana_cost else Cost()
        if ability.discount_each:
            cost = cost.reduced(sum(_permanent_matches(ability.discount_each, p.card) for p in seat.battlefield))
        return cost

    def _activate_from_hand(self, seat: Seat, card: Card) -> None:
        """"{U/R}{U/R}, Discard this card: Create a Treasure token.": like cycling, the card is discarded as a cost and
        the ability goes on the stack."""
        ability = hand_abilities(card)[0]
        effects = list(ability.effects)
        if ability.exile_from_hand:  # a Spirit Guide's mana ability: exiled as the cost, and the mana is added at once
            self.broadcast({"event": "exiled_from_hand", "seat": seat.index, "card": card.name})
            self._move_card(seat, card, "exile")
            for effect in effects:
                effect.resolve(self, seat, None)
            return
        targets, labels = _checked(self._choose_targets(seat, effects, card.name, colors=source_qualities(card)))
        tapped = _checked(self._pay_cost(seat, self._hand_ability_cost(seat, ability))) if ability.mana_cost else Payment()
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
        tapped = _checked(self._pay_cost(seat, cost_of(ability.mana_cost))) if ability.mana_cost else Payment()
        self._spend_mana(seat, tapped)
        self.stack.append(StackItem(card, seat, list(ability.effects), [], ability))
        self.broadcast({"event": "activate", "seat": seat.index, "card": card.name, "ability": _shown(ability.text, card),
                        "targets": [], "tapped": [p.card.name for p in tapped]})

    def _activate(self, seat: Seat, permanent: Permanent, ability: ActivatedAbility) -> None:
        effects = list(ability.effects)
        if effects and isinstance(effects[0], Modal):
            effects, _ = self._choose_modes(seat, permanent.card, effects[0], source=permanent)
        targets, labels = _checked(self._choose_targets(seat, effects, permanent.card.name, permanent,
                                                        source_qualities(permanent.card)))
        x = 0
        if ability.mana_cost and cost_of(ability.mana_cost).x:  # "{X}, {T}: ...": X is chosen, then paid
            most = 0
            while most < MAX_X and self._ability_payment(seat, permanent, ability, most + 1) is not None:
                most += 1
            x = seat.player.choose(X_PROMPT + permanent.card.name, [str(n) for n in range(most + 1)])
        tapped = _checked(self._ability_payment(seat, permanent, ability, x))
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
        if ability.mana_cost and cost_of(ability.mana_cost).x:  # Unbound Flourishing
            self.happened("activate_x", seat, spell=item)
        self._check_ward(item)
        if ability.sacrifice:
            self._leave_battlefield(permanent, "sacrificed")
        elif ability.exile_source:  # "Exile this land" (Tomb Fortress)
            self.exile(permanent)


    def _effects_possible(self, seat: Seat, effects, colors: frozenset[str] = frozenset(),
                          source: Permanent | None = None) -> bool:
        """Whether the targets exist: for a modal spell or ability, for enough of its modes."""
        if effects and isinstance(effects[0], Modal):
            modal = effects[0]
            return sum(self._targets_exist(seat, modes, colors, source) for modes in modal.modes) >= (min(modal.min, 1) if modal.repeat else modal.min)
        return self._targets_exist(seat, effects, colors, source)

    @staticmethod
    def option_is_source(option: Any, source: Permanent | None) -> bool:
        """Whether a target option is the source of the ability itself, for an "another" target: the permanent, or (a dies trigger such as
        Myr Retriever's) its own card in a graveyard, unless an identical card is there too."""
        if isinstance(option, GraveyardTarget):
            return (source is not None and option.card == source.card
                    and sum(c == source.card for c in option.seat.graveyard) <= 1)
        return option is source

    def _targets_exist(self, seat: Seat, effects, colors: frozenset[str] = frozenset(),
                       source: Permanent | None = None) -> bool:
        """Whether every targeting effect (but "up to one target") has a legal target; a `distinct` one needs one
        besides the targets chosen for earlier effects of the same kind, and an "another" one can't be `source`."""
        kinds = [(kind, getattr(e, "distinct", False), getattr(e, "another", False)) for e in effects
                 if (kind := target_kind(e)) and not getattr(e, "optional_target", False)]
        saved, self.targeting_source = self.targeting_source, source
        try:
            for i, (kind, distinct, another) in enumerate(kinds):
                needed = 1 + (sum(k == kind for k, _, _ in kinds[:i]) if distinct else 0)
                kind = kind.removesuffix(" with mana value x")  # X isn't chosen yet: any creature could do
                options = [o for _, o in self.target_options(self._fixed_kind(kind, source), seat, colors)
                           if not (another and self.option_is_source(o, source))]
                if len(options) < needed:
                    return False
            return True
        finally:
            self.targeting_source = saved







    def _give_gift(self, item: StackItem) -> None:
        """The promised gift reaches the opponent: a card drawn, a token made (Treasure, Food, a tapped Fish, an 8/8 Octopus) or an extra turn."""
        to, kind = _checked(item.gift), _checked(gift_of(item.card))
        self.broadcast({"event": "gift", "seat": item.controller.index, "to": to.index, "gift": kind})
        if kind == "card":
            self.draw(to, 1)
        elif kind == "extra turn":
            self.extra_turns.append(to.index)
        else:
            token = {"Treasure": TREASURE, "Food": FOOD, "tapped Fish": FISH, "Octopus": OCTOPUS}[kind]
            self.create_tokens(to, token, 1, tapped=kind == "tapped Fish")


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
            if item.face_down is not None:  # cast with morph: it enters face down, the real card kept for turning up
                kind, cost = item.face_down
                entering = Permanent(card, sick=True, cast=not item.is_copy, real_card=item.whole, manifested=True, owner=item.home,
                                     turn_up_cost=cost, megamorph=kind == "Megamorph")
                self._enter(seat, entering, x=item.x)
                return
            whole = item.whole or card  # a Room enters with the door that was cast unlocked (the card itself is its front door)
            door = card if is_room(whole) else None
            if door is not None:
                card = room_view(whole, (door.name,))
            entering = Permanent(card, sick=True, loyalty=_starting_loyalty(card), kicked=item.kicked, kickers=item.kickers,
                                 escaped=item.escaped, cast=not item.is_copy, doors=(door.name,) if door else (),
                                 transformed_from=whole if whole.flip is card else None,
                                 real_card=whole if door else None, owner=item.owner,
                                 extra_counters=item.rider_counters * seat.commander_casts.get(card.name, 0))
            if enters_by_discarding_land(card) and not self._discard_land_to_enter(seat, card):  # Mox Diamond
                return
            if item.evoked:  # queued first, so it resolves after the creature's own "when it enters" abilities
                self._queue(EVOKE_SACRIFICE, entering, seat)
            self._enter(seat, entering, x=item.x)
            if item.gift is not None:  # "when it enters, they draw a card"
                self._give_gift(item)
            if door is not None:
                self._door_unlocked(entering, door)
            if item.warped:  # exiled as the next end step begins, then it may be cast from exile on a later turn
                fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
                self.at_end_step.append((fire_turn, lambda: self._warp_exile(entering, seat)))
            if item.dashed:  # Ragavan: it has haste this turn and is back in its owner's hand at the end step
                self.modify_until_end_of_turn(entering, Modifier(keywords=frozenset({"haste"})))
                self.leave_at_next_end_step([entering], "returned", "hand")
            return
        if item.effects is None:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "unsupported": True})
            if not item.is_copy:
                self._finish_spell(item)
            return
        if item.gift is not None:  # "they draw a card before its other effects"
            self._give_gift(item)
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
        card, home = item.physical, item.home
        if item.bought_back and resolved:
            self.broadcast({"event": "buyback", "seat": item.controller.index, "card": item.card.name})
            self._move_card(home, card, "hand")
            return
        if item.shuffle_after and resolved and not item.is_copy:
            home.library.append(card)
            self.rng.shuffle(home.library)
            return
        if item.bottom_after and card.name not in home.commander_names:
            home.library.append(card)
            return
        if resolved and item.from_hand and has_keyword(item.card, "rebound") and not item.is_copy:
            home.exile.append(card)  # Ephemerate: it comes back at the next upkeep
            item.controller.rebounding.append((card, self.turn))
            self.broadcast({"event": "rebound", "seat": item.controller.index, "card": card.name})
            return
        if resolved and "Adventure" in item.card.type_line:
            # it goes on an adventure: exiled, and its owner may cast the creature from there for as long as it stays
            home.exile.append(card)
            home.exile_play.append((card, FOREVER))
            self.broadcast({"event": "adventure", "seat": item.controller.index, "card": card.name})
            return
        self._move_card(home, card, "exile" if item.exile_after else "graveyard")

    def _discard_land_to_enter(self, seat: Seat, card: Card) -> bool:
        """Mox Diamond: "you may discard a land card instead"; without doing so it goes to its owner's graveyard."""
        lands_in_hand = [c for c in seat.hand if is_land(c)]
        if lands_in_hand:
            choice = seat.player.choose(MOX_DIAMOND_PROMPT + card.name, [c.name for c in lands_in_hand] + ["Don't discard"])
            if choice < len(lands_in_hand):
                land = lands_in_hand[choice]
                seat.hand.remove(land)
                self.broadcast({"event": "discard", "seat": seat.index, "card": land.name})
                self._discard_into_zone(seat, land)
                return True
        self._move_card(seat, card, "graveyard")
        return False

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
            self._enter(seat, Permanent(card, sick=True, owner=item.owner), x=item.x)

    def _resolve_aura(self, item: StackItem) -> None:
        """An Aura spell enters attached to its target, or goes to the graveyard if the target
        is no longer legal (CR 608.3b)."""
        seat, card = item.controller, item.card
        target = item.targets[0] if item.targets else None
        if target is None or not self.is_legal_target(_checked(aura_kind(card)), target, seat, source_qualities(card)):
            self.broadcast({"event": "fizzle", "seat": seat.index, "card": card.name})
            if not item.is_copy:
                self._move_card(seat, item.physical, "exile" if item.exile_after else "graveyard")
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
            self._enter(seat, Permanent(card, sick=True, attached_to=creature, kicked=item.kicked, kickers=item.kickers, owner=item.owner))
            self.broadcast({"event": "attached", "card": card.name, "to": creature.card.name})
            return
        self.broadcast({"event": "resolve", "seat": seat.index, "card": card.name, "to": "battlefield"})
        self._enter(seat, Permanent(card, sick=True, attached_to=target, kicked=item.kicked, kickers=item.kickers, owner=item.owner,
                                    transformed_from=item.whole if item.whole is not None and item.whole.flip is card else None))
        self.broadcast({"event": "attached", "card": card.name, "to": target.card.name})
        if item.gift is not None:
            self._give_gift(item)

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
                self.untap(permanent)

    def detach(self, attachment: Permanent) -> None:
        """An Equipment stops being attached; a Reconfigure creature becomes a creature again."""
        attachment.attached_to = None
        if attachment.reconfigured is not None:
            attachment.card, attachment.reconfigured = attachment.reconfigured, None

    def _resolve_ability(self, item: StackItem) -> None:
        seat, ability = item.controller, _checked(item.ability)
        if getattr(ability, "optional", False) and seat.player.choose(OPTIONAL_PROMPT + item.card.name, YES_NO) != 0:
            self.broadcast({"event": "resolve", "seat": seat.index, "card": item.card.name,
                            "ability": _shown(ability.text, item.card), "declined": True})
            return
        condition = getattr(ability, "condition", None)
        if condition and not self.condition_holds(condition, seat, item.source, item.x, item.player, item.subject):  # checked again on resolution (CR 603.4)
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
        if kind == "devotion":  # Gray Merchant of Asphodel: every {B} (hybrid and Phyrexian too) in the mana costs of your permanents
            return sum(len(re.findall(rf"\{{[^}}]*{amount.what}[^}}]*\}}", p.card.mana_cost)) for p in controller.battlefield)
        if kind == "sacrificed_power":  # the creature sacrificed to pay this ability's cost
            return self.resolving_item.sacrificed_power if self.resolving_item else 0
        if kind == "tapped_power":  # the creature tapped to pay this ability's cost (Station)
            return self.resolving_item.tapped_power if self.resolving_item else 0
        if kind == "source_counters":
            return source.counters.get(amount.what, 0) if source else 0
        if kind == "on_battlefield":
            return sum(has_type(p.card, amount.what) for s in self.live_seats() for p in s.battlefield)
        if kind == "you_control":
            return sum(has_type(p.card, amount.what) for p in controller.battlefield)
        if kind == "greatest_power":
            kind_wanted = amount.what.removeprefix("other ")
            return max((self.power(p) for p in controller.battlefield if has_type(p.card, kind_wanted)
                        and not (kind_wanted != amount.what and p is self.resolving_source)), default=0)
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

    def amount(self, value: Quantity) -> int:
        """A number from an effect; "X" is the resolving spell's X, "2X" twice it."""
        if value == "hX":  # half X, rounded down (Hydroid Krasis, The Goose Mother)
            return self.x_value // 2
        if value == "hX+":  # ... rounded up
            return (self.x_value + 1) // 2
        return self.x_value if value == "X" else 2 * self.x_value if value == "2X" else int(value)

    def _apply_effects(self, item: StackItem) -> bool:
        """Do a spell's or ability's effects; False if it fizzled because every target was gone (CR 608.2b)."""
        self.x_value, self.resolving_source = item.x, item.source
        self.resolving_item, self.resolving_colors = item, source_qualities(item.card)
        self.resolving_damaged = []
        try:
            return self._apply_effects_now(item)
        finally:
            self.x_value, self.resolving_source = 0, None
            self.resolving_item, self.resolving_colors = None, frozenset()
            self.resolving_target = None

    def _apply_effects_now(self, item: StackItem) -> bool:
        effects = item.effects
        assert effects is not None  # a spell whose text isn't understood is not applied (see _resolve)
        seat = item.controller
        colors = source_qualities(item.card)
        declared = {}  # a target list that had targets when the spell was put on the stack
        for index, (e, t) in enumerate(zip([e for e in effects if target_kind(e)], item.targets)):
            if getattr(e, "multi_target", False):  # keep only the targets that are still legal
                declared[index] = bool(t)
                item.targets[index] = [p for p in t if self.is_legal_target(_checked(target_kind(e)), p, seat, colors)]
        legal = [(index in declared and (not declared[index] or bool(t)))  # a list with none chosen still resolves
                 or (t is None and getattr(e, "optional_target", False))
                 or (index not in declared and self.is_legal_target(self._fixed_kind(_checked(target_kind(e)), item.source, item.x), t, seat, colors))
                 for index, (e, t) in enumerate(zip([e for e in effects if target_kind(e)], item.targets))]
        about = {"seat": seat.index, "card": item.card.name}
        if item.ability:
            about["ability"] = _shown(item.ability.text, item.card)
        if legal and not any(legal):
            self.broadcast({"event": "fizzle", **about})
            return False
        self.broadcast({"event": "resolve", **about})
        checks = iter(zip(item.targets, legal))
        previous = None  # the last targeting effect's target, for "Its controller ..." follow-ups
        for effect in effects:
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
                player: Seat | None = None, x: int = 0, spell: "StackItem | Card | tuple | None" = None, text: str | None = None) -> None:
        """Note that `permanent`'s abilities for `event` triggered; they go on the stack
        the next time a player would get priority (CR 603.3). With `text`, only the ability printed as that line (a Room's door)."""
        if event not in EVENTS and not event.startswith("chapter_"):
            raise ValueError(f"{event!r} is not a declared event (effects/events.py)")
        if self.loses_abilities(permanent):
            return
        for ability in triggered_abilities(permanent.card):
            if ability.event == event and ability.watch is None and (text is None or ability.text == text):
                if any(isinstance(e, ReturnThisFromGraveyard) for e in ability.effects) and self.on_battlefield(permanent):
                    continue  # it only works from the graveyard (Squee)
                for _ in range(self._trigger_times(controller, event, permanent.card, source=permanent)):
                    self._queue(ability, permanent, controller, x=x, subject=subject, player=player, spell=spell)

    def happened(self, occurrence: str, seat: Seat, *facts: str, subject: Permanent | None = None,
                 spell: "StackItem | Card | tuple | None" = None, x: int = 0) -> None:
        """`occurrence` happened to `seat` (it drew, discarded, gained life ...): every event declared for it
        (effects/events.py) triggers for whoever hears it, the player's own permanents or those of each opponent. An
        event that needs a fact ("first", "second", "extra") waits for the caller to report it in `facts`. `subject` is
        the permanent it happened to, `spell` the spell (or card) involved, `x` the number it carried."""
        for event in heard_on(occurrence):
            if event.needs and event.needs not in facts:
                continue
            if event.to == "you":
                for permanent in list(seat.battlefield):
                    self.trigger(event.name, permanent, seat, subject, x=x, spell=spell)
            else:
                for opponent in self.opponents(seat):
                    for permanent in list(opponent.battlefield):
                        self.trigger(event.name, permanent, opponent, subject, seat, x=x, spell=spell)

    def _searched(self, seat: Seat) -> None:
        """`seat` searched their library (found something or not)."""
        self.happened("searched", seat)

    def _discarded(self, seat: Seat, card: Card | None = None, together: bool = False) -> None:
        """`seat` discarded a card: "Whenever you discard a card" and "Whenever an opponent discards a card". Cards
        discarded `together` set off "one or more nonland cards" once, which the caller reports (_discarded_nonland)."""
        self.happened("discarded", seat, spell=card)
        if not together and card is not None:
            self._discarded_nonland(seat, [card])

    def _discarded_nonland(self, seat: Seat, cards: list[Card]) -> None:
        """"Whenever you discard one or more nonland cards": once, carrying the nonland cards among those discarded."""
        if nonland := tuple(c for c in cards if "Land" not in c.type_line):
            self.happened("discarded_nonland", seat, spell=nonland)

    def _queue(self, ability: TriggeredAbility, permanent: Permanent, controller: Seat, x: int = 0,
               subject: Permanent | None = None, player: Seat | None = None, spell: "StackItem | Card | tuple | None" = None) -> None:
        if ability.condition and not self.condition_holds(ability.condition, controller, permanent, x, player, subject):
            return
        if ability.once_per_turn:  # "This ability triggers only once each turn."
            if permanent.triggered_turn.get(ability.text) == self.turn:
                return
            permanent.triggered_turn[ability.text] = self.turn
        self.pending.append(PendingTrigger(ability, permanent, controller, x, subject, player, spell=spell))

    def condition_holds(self, condition: Condition, seat: Seat, source: Permanent | None = None, x: int = 0,
                        player: Seat | None = None, subject: Permanent | None = None) -> bool:
        """Whether an intervening "if" clause is true for `seat`, the ability's controller, and `source`. `x` is the
        number the event carried (how many attackers went at the controller, for "two or more of those creatures");
        `player` is the player the trigger is about ("that player"); `subject` the permanent it is about ("that creature")."""
        kind = condition.kind
        if condition.also is not None and not self.condition_holds(condition.also, seat, source, x, player, subject):
            return False
        if kind == "no_spell_cast_turn":
            return not any(turn == self.turn for turn, _ in seat.cast_log)
        if kind == "delirium":  # four or more card types among the cards in the graveyard
            types = {t for c in seat.graveyard for t in ("Artifact", "Battle", "Creature", "Enchantment", "Instant", "Kindred", "Land", "Planeswalker", "Sorcery")
                     if t in c.type_line.partition("\u2014")[0]}
            return len(types) >= 4
        if kind == "each_life_at_most":  # Cryptolith Fragment: every player has that much life or less
            return all(s.life <= condition.count for s in self.live_seats())
        if kind == "source_equipped":
            return source is not None and any(a.attached_to is source and "Equipment" in a.card.type_line for s in self.seats for a in s.battlefield)
        if kind == "foretold":  # the spell resolving was cast from exile for its foretell cost
            return self.resolving_item is not None and self.resolving_item.foretold
        if kind == "no_spells_last_turn":  # the old werewolves: nobody cast a spell in the previous turn
            return not any(turn == self.turn - 1 for other in self.seats for turn, _ in other.cast_log)
        if kind == "two_spells_last_turn":  # ... or one player cast two or more
            return any(sum(1 for turn, _ in other.cast_log if turn == self.turn - 1) >= 2 for other in self.seats)
        if kind in ("day", "night"):
            return self.day_night == kind
        if kind == "subject_greater":  # Evolve: the creature that entered has greater power or toughness than the source
            return (source is not None and subject is not None
                    and (self.power(subject) > self.power(source) or (self.toughness(subject) or 0) > (self.toughness(source) or 0)))
        if kind == "all_hands_empty":  # Howltooth Hollow
            return not any(s.hand for s in self.live_seats())
        if kind == "creature_with_power":  # Garruk's Uprising: a creature you control with power N or greater
            return any(self.power(p) >= condition.count for p in seat.battlefield if "Creature" in p.card.type_line)
        if kind == "created_token":  # Idol of Oblivion
            return seat.token_turn == self.turn
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
        if kind == "cast_it":  # The One Ring: it came from a spell that was cast
            return source is not None and source.cast
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
            return not any(has_type(p.card, condition.what) for p in seat.battlefield if p is not source)
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
        if kind == "not_renowned":
            return source is not None and not source.renowned
        if kind == "graveyard_at_least":
            return sum(_card_matches(condition.what, c) for c in seat.graveyard) >= condition.count
        if kind == "any_hand_at_most":
            return any(len(s.hand) <= condition.count for s in self.live_seats())
        if kind == "opponent_more_cards":
            return any(len(o.hand) > len(seat.hand) for o in self.opponents(seat))
        if kind == "control_none_token":  # Pest Rescuer: "you don't control a Pest creature token"
            return not any(_is_token(p.card) and "Creature" in p.card.type_line and has_type(p.card, condition.what)
                           for p in seat.battlefield)
        matching = sum(has_type(p.card, condition.what) for p in seat.battlefield)
        return matching >= condition.count if kind == "control_at_least" else matching == 0

    def _observe(self, event: str, card: Card, seat: Seat, subject: Permanent | None = None,
                 extra: Sequence[tuple[Permanent, Seat]] = (), x: int = 0, from_hand: bool = False,
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
                if watch.chosen and watcher.chosen_type not in card.type_line.partition("\u2014")[2].split():
                    continue  # "of the chosen type": the type the watcher named as it entered
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
                value = _checked(self.toughness(permanent)) if here else int(permanent.card.toughness or 0) + permanent.counters.get("+1/+1", 0)
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
            self.targeting_player = trigger.player
            try:
                chosen = self._choose_targets(seat, effects, trigger.source.name, trigger.permanent,
                                              source_qualities(trigger.source))
            finally:
                self.targeting_x = 0
                self.targeting_player = None
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
        if kind.startswith("spell or ") and kind not in STACK_TARGET_KINDS:  # Sink into Stupor: a spell or a permanent
            rest = kind.removeprefix("spell or ")
            return (self.target_options("spell you don't control" if "an opponent controls" in rest else "spell", caster, colors)
                    + self.target_options(rest, caster, colors))
        if kind in STACK_TARGET_KINDS:  # Deflection, Bolt Bend, Reroute, Deflecting Swat
            wanted, lone = STACK_TARGET_KINDS[kind]
            me = self._source_now()
            return [(f"{'Ability' if i.ability else 'Spell'}: {i.card.name} (seat {i.controller.index})", i) for i in self.stack
                    if (not lone or self._lone_target(i) is not None)
                    and wanted(i, i.targets[_checked(self._lone_target(i))] if lone else None, me)]
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
            options += [(f"Player: {s.name} (seat {s.index})", s) for s in self.live_seats() if not s.protected]
        elif kind == "opponent":
            options += [(f"Player: {s.name} (seat {s.index})", s) for s in self.opponents(caster) if not s.protected]
        if (spell_filter := parse_filter(kind)) and re.search(r"spell( you control| you don't control)?( with mana value \d+( or less| or greater)?)?$", kind):  # "spell", "noncreature spell", "... spell you control", "spell with mana value 1"
            options += [(f"Spell: {i.card.name} (seat {i.controller.index})", i) for i in self.stack
                        if not i.ability and spell_filter.matches(i.card)
                        and not (spell_filter.controller == "you" and i.controller is not caster)
                        and not (spell_filter.controller == "opponent" and i.controller is caster)]
            return options
        that_player = None
        if kind.endswith(" that player controls"):  # Throat Slitter: what the player this trigger is about controls
            kind = kind.removesuffix(" that player controls")
            that_player = self.resolving_item.player if self.resolving_item is not None else self.targeting_player
            if that_player is None:
                return options
        attacked = kind.endswith(" that attacked this turn")  # "creature that attacked this turn"
        lesser = self._source_now() if kind.endswith(" with lesser power") else None  # Mentor
        wanted = parse_filter(re.sub(r"mana value x\b", lambda m: "mana value %d" % (
            self.x_value if self.resolving_item is not None else self.targeting_x),
            kind.removesuffix(" that attacked this turn").removesuffix(" with lesser power")))
        controller = wanted.controller
        for seat in self.live_seats():
            if (controller == "opponent" and seat is caster) or (controller == "you" and seat is not caster):
                continue
            if that_player is not None and seat is not that_player:
                continue
            for n, permanent in enumerate(seat.battlefield):
                if not wanted.matches(permanent.card) or self.has_keyword(permanent, "shroud"):
                    continue
                if controller == "own" and (permanent.owner or seat) is not caster:
                    continue
                if attacked and permanent.attacked_turn != self.turn:
                    continue
                if kind.endswith(" with lesser power") and (lesser is None or self.power(permanent) >= self.power(lesser)):
                    continue
                if not self._in_state(permanent, wanted.state):
                    continue
                if self.has_keyword(permanent, "hexproof") and seat is not caster:
                    continue
                if self.protected_from(permanent, colors):
                    continue
                options.append((self.label(permanent), permanent))
        return options

    def _lone_target(self, item: StackItem) -> int | None:
        """Which of `item.targets` is the only thing the spell or ability targets; None if it targets nothing or several things."""
        chosen = [i for i, t in enumerate(item.targets) if t is not None and not isinstance(t, list)]
        return chosen[0] if len(chosen) == 1 and not any(isinstance(t, list) and t for t in item.targets) else None

    def _source_now(self) -> Permanent | None:
        """The permanent whose ability is resolving, or whose ability's targets are being chosen ("this creature")."""
        return self.resolving_source if self.resolving_item is not None else self.targeting_source

    def change_target(self, chooser: Seat, item: StackItem, every: bool = False, to: str = "", lone: bool = True) -> None:
        """`chooser` picks a new target for the one target of `item`: another one that is legal for it. With none, nothing changes.
        With `every`, each of its targets may be changed, and may stay (Deflecting Swat). `to` limits the new target: "player",
        "creature" or "this" (the permanent whose ability this is); with `lone` False the chooser picks which target to change
        (Spellskite)."""
        effects = [e for e in item.effects or [] if target_kind(e)]
        me = self.resolving_source

        def new_options(index: int) -> list[tuple[str, Any]]:
            current = item.targets[index]
            kind = self._fixed_kind(_checked(target_kind(effects[index])), item.source, item.x)
            options = self.target_options(kind, item.controller, source_qualities(item.card))
            if to:
                options = [o for o in options if (isinstance(o[1], Seat) if to == "player" else o[1] is me if to == "this"
                                                  else isinstance(o[1], Permanent) and "Creature" in o[1].card.type_line)]
            return sorted(options, key=lambda o: o[1] is not current) if every else [o for o in options if o[1] is not current]

        if every:
            indexes = [i for i, t in enumerate(item.targets) if t is not None and not isinstance(t, list)]
        elif lone:
            indexes = [self._lone_target(item)]
        else:  # "Change a target of target spell or ability": one of its targets that can be changed
            movable = [i for i, t in enumerate(item.targets) if t is not None and not isinstance(t, list) and new_options(i)]
            indexes = movable[:1] if len(movable) < 2 else [movable[chooser.player.choose(
                CHANGE_WHICH_PROMPT + item.card.name, [self._target_label(item.targets[i]) for i in movable])]]
        for index in indexes:
            if index is None:
                return
            current = item.targets[index]
            options = new_options(index)
            if options:
                label, new = options[chooser.player.choose(TARGET_PROMPT + item.card.name, [o[0] for o in options])]
                item.targets[index] = new
                if new is not current:
                    self.broadcast({"event": "target_changed", "seat": chooser.index, "card": item.card.name, "to": label})

    def _target_label(self, target: Any) -> str:
        return self.label(target) if isinstance(target, Permanent) else f"Player: {target.name} (seat {target.index})"

    def label(self, permanent: Permanent) -> str:
        """How a permanent is shown in choices: "Grizzly Bears 2/2 (seat 1, #3)"."""
        seat = self.controller(permanent)
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

    def controller(self, permanent: Permanent) -> Seat:
        """The controller of a permanent the caller knows is on the battlefield (it was just found there, or just checked)."""
        return _checked(self.controller_of(permanent))

    def owner_of(self, permanent: Permanent) -> Seat:
        """Whose card the permanent is: the seat it entered under, else whoever controls it, else whoever last did."""
        return _checked(permanent.owner or self.controller_of(permanent) or permanent.last_controller)

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
            for _ in range(self._cards_per_draw(seat)):
                if not self._draw_one(seat, announce):
                    return

    def _cards_per_draw(self, seat: Seat) -> int:
        """How many cards one draw becomes: "If you would draw a card, draw two cards instead." (Thought Reflection) multiplies, and
        each replacement applies once (CR 614.5), so two of them make four."""
        factor = 1
        for permanent in seat.battlefield:
            if self.loses_abilities(permanent):
                continue
            for kind in replacement_effects(permanent.card).draw_double:
                if kind == "always" or (kind == "extra" and not self._draw_step_draw):
                    factor *= 2
        return factor

    def _draw_one(self, seat: Seat, announce: bool) -> bool:
        """One card drawn (or dredged); False if the draw ended the player's drawing because the library was empty."""
        if self._dredge(seat):
            return True
        if not seat.library:
            if any(replacement_effects(p.card).win_on_empty_draw for p in seat.battlefield if not self.loses_abilities(p)):
                seat.wins_game = True  # Laboratory Maniac
                self.broadcast({"event": "wins_game", "seat": seat.index})
            else:
                seat.drew_from_empty = True
            return False
        card = seat.library.pop(0)
        seat.hand.append(card)
        if seat.drawn_turn != self.turn:
            seat.drawn_turn, seat.drawn_cards = self.turn, []
        seat.drawn_cards.append(card)
        if announce:
            seat.player.notify({"event": "draw", "card": card.name})
            self.broadcast({"event": "drew", "seat": seat.index, "hand_size": len(seat.hand)}, skip=seat)
            if seat.draw_turn != self.turn:
                seat.draw_turn, seat.draw_count = self.turn, 0
            seat.draw_count += 1
            self.happened("drew", seat, *(["extra"] if not self._draw_step_draw else []),
                          *(["second"] if seat.draw_count == 2 else []))
        return True

    def _dredge(self, seat: Seat) -> bool:
        """Dredge: instead of drawing, the player may mill N cards and return a card with "Dredge N" from the graveyard to their
        hand (it takes a library of at least N cards). Whether a draw was replaced."""
        dredgers = [c for c in _unique(seat.graveyard) if (n := dredge_of(c)) is not None and n <= len(seat.library)]
        if not dredgers:
            return False
        pick = seat.player.choose(DREDGE_PROMPT, ["Draw a card"] + [f"Dredge {dredge_of(c)}: {c.name}" for c in dredgers])
        if pick == 0:
            return False
        card = dredgers[pick - 1]
        self.mill(seat, _checked(dredge_of(card)))
        seat.graveyard.remove(card)
        seat.hand.append(card)
        self.broadcast({"event": "dredged", "seat": seat.index, "card": card.name})
        return True

    def sylvan_library(self, seat: Seat, life: int) -> None:
        """Sylvan Library: the player may draw two more cards; if they do they choose two cards of those drawn this turn (the
        draw step's own card too), and for each either pays life or puts it back on top of the library."""
        if seat.player.choose(SYLVAN_PROMPT, ["Yes", "No"]) != 0:
            return
        self.draw(seat, 2)
        remaining = list(seat.hand)
        pool = []
        for card in seat.drawn_cards:  # those still in hand (equal cards are interchangeable)
            if card in remaining:
                remaining.remove(card)
                pool.append(card)
        chosen = []
        for _ in range(min(2, len(pool))):
            pick = pool.pop(seat.player.choose(SYLVAN_CHOOSE_PROMPT, [c.name for c in pool]))
            chosen.append(pick)
        for card in chosen:
            options = ["Put it on top of your library"] + ([f"Pay {life} life"] if seat.life > life else [])
            if seat.player.choose(SYLVAN_PAY_PROMPT + card.name, options) == 0:
                seat.hand.remove(card)
                seat.library.insert(0, card)
            else:
                self.change_life(seat, -life)

    def change_life(self, seat: Seat, amount: int) -> None:
        if seat.life_locked:  # Teferi's Protection: no life is gained or lost
            return
        if amount > 0:  # Pest Rescuer: "you gain that much life plus 1 instead"; then The Wind Crystal: "twice that much"
            amount += sum(replacement_effects(p.card).life_gain_plus for p in seat.battlefield)
            amount *= self._factor(seat, "life_gain_factor")
        if amount < 0:  # Bloodletter of Aclazotz: "twice that much life" during its controller's turn
            active = self.seats[self.active]
            if active is not seat:
                for p in active.battlefield:
                    if not self.loses_abilities(p):
                        amount *= replacement_effects(p.card).opponent_loss_factor
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
            self.happened("life_gained" if amount > 0 else "life_lost", seat, *(["first"] if first_loss or first_gain else []),
                          x=abs(amount))  # x: "that much life"

    def damage(self, target: Seat | Permanent, amount: int, source: Permanent | None = None,
               combat: bool = False) -> None:
        colors = source_qualities(source.card) if source is not None else self.resolving_colors
        if isinstance(target, Permanent) and self.protected_from(target, colors):
            self.broadcast({"event": "damage_prevented", "card": target.card.name, "amount": amount})
            return
        if isinstance(target, Seat) and target.protected:  # protection from everything
            self.broadcast({"event": "damage_prevented", "seat": target.index, "amount": amount})
            return
        amount, prevented = self._damage_replaced(target, amount, source, combat)
        if prevented:
            self.broadcast({"event": "damage_prevented", "amount": prevented,
                            **({"card": target.card.name} if isinstance(target, Permanent) else {"seat": target.index})})
            if amount <= 0:
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
            if amount > 0 and source is not None:  # Curiosity: "Whenever enchanted creature deals damage to an opponent"
                for holder in self.live_seats():
                    for attachment in list(holder.battlefield) if holder is not target else ():
                        if attachment.attached_to is source:
                            self.trigger("host_damage_opponent", attachment, holder, source, player=target)
                            if combat:
                                self.trigger("host_combat_damage_opponent", attachment, holder, source, player=target)
            if combat and amount > 0 and source is not None and not self.loses_abilities(source) \
                    and (toxic := toxic_of(source.card)):
                self.give_poison(target, toxic)  # Toxic N: that many poison counters in addition to the damage
            if combat and controller and source is not None:  # (a controller means there is a source)
                self.trigger("combat_damage_to_player", source, controller, player=target, x=amount)
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
                                    self.controller(watcher))
                self._observe("combat_damage_dealt", source.card, controller, subject=source)  # "Whenever a Ninja you control deals ..."
                for permanent in list(controller.battlefield):  # "Whenever a creature (token) you control deals ..."
                    self.trigger("ally_combat_damage", permanent, controller, subject=source)
                    if _is_token(source.card):
                        self.trigger("token_combat_damage", permanent, controller, subject=source)
            if combat and controller and source is not None and source.card.name in controller.commander_names:
                key = (controller.index, source.card.name)
                target.commander_damage[key] = target.commander_damage.get(key, 0) + amount
                self.broadcast({"event": "commander_damage", "seat": target.index, "from_seat": controller.index,
                                "commander": source.card.name, "total": target.commander_damage[key]})
        else:
            if "Creature" in target.card.type_line:
                if amount > 0 and self.resolving_item is not None:
                    self.resolving_damaged.append(target)
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
        if controller and source is not None and self.has_keyword(source, "lifelink"):
            self.change_life(controller, amount)

    def _damage_modifiers(self, target: Seat | Permanent, source: Permanent | None, combat: bool) -> list[tuple[Permanent, DamageModifier]]:
        """The replacement effects that double, triple or add to this damage (CR 614.1): "If a source you control would deal damage to
        a permanent or player, it deals double that damage instead.", each with the permanent that has it."""
        dealer = self.controller_of(source) if source is not None else (self.resolving_item.controller if self.resolving_item else None)
        victim_seat = target if isinstance(target, Seat) else self.controller_of(target)
        found = []
        for seat in self.live_seats():
            for permanent in seat.battlefield:
                if self.loses_abilities(permanent):
                    continue
                for mod in damage_modifiers(permanent.card):
                    if (mod.kind == "combat" and not combat) or (mod.kind == "noncombat" and combat):
                        continue
                    if mod.source == "you" and dealer is not seat:
                        continue
                    if mod.source == "creature" and (source is None or dealer is not seat or "Creature" not in source.card.type_line):
                        continue
                    if mod.source == "self" and source is not permanent:
                        continue
                    if mod.victim in ("opponent", "opponent_player") and (victim_seat is None or victim_seat is seat):
                        continue
                    if mod.victim in ("opponent_player", "player") and not isinstance(target, Seat):
                        continue
                    if (mod.groups or mod.another or mod.spell) and not self._source_fits(mod, permanent, source):
                        continue
                    found.append((permanent, mod))
        return found

    def _source_fits(self, mod: DamageModifier, owner: Permanent, source: Permanent | None) -> bool:
        """Whether the thing dealing the damage is what the modifier names: a permanent, or the spell that is resolving (a damage
        spell's source is the spell). `owner` is the permanent with the modifier, for "another"."""
        if source is None and (self.resolving_item is None or self.resolving_item.ability):
            return False
        card = source.card if source is not None else _checked(self.resolving_item).card
        if (mod.spell and source is not None) or (mod.another and source is owner):
            return False
        qualities = source_qualities(card)
        subtypes = card.type_line.partition("\u2014")[2].split()
        return all(any(_COLOR_LETTERS.get(word, word.lower()) in qualities or word in subtypes for word in group) for group in mod.groups)

    def _damage_replaced(self, target: Seat | Permanent, amount: int, source: Permanent | None, combat: bool) -> tuple[int, int]:
        """(the damage that is dealt, the damage prevented) once the replacement and prevention effects that apply to `amount` damage
        have been applied. They are all replacement effects, so the player being dealt the damage (or the controller of the permanent)
        chooses the order (CR 616.1): doubling before a shield of 2 against 3 damage is 4, a shield before the doubling is 2. The player is
        asked only when the order changes the result; the least damage is listed first."""
        if amount <= 0:
            return amount, 0
        mods = self._damage_modifiers(target, source, combat)
        if not mods:
            after = self._damage_after_prevention(target, amount, source, combat)
            return after, amount - after
        capacity = self._prevention_capacity(target, source, combat)
        steps: list[tuple[str, int, int]] = [(p.card.name, m.factor, m.plus) for p, m in mods]  # (name, factor, plus)
        if capacity:
            steps.append(("prevention", 0, 0))
        outcomes: dict[int, tuple[list[str], int]] = {}  # damage dealt -> (the order, the damage prevented)
        for order in itertools.permutations(steps):
            dealt, stopped = amount, 0
            for name, factor, plus in order:
                if name == "prevention":
                    used = min(dealt, capacity)
                    dealt, stopped = dealt - used, stopped + used
                elif dealt > 0:  # nothing is left to replace once it is all prevented
                    dealt = dealt * factor + plus
            if dealt not in outcomes or stopped < outcomes[dealt][1]:  # the same damage: the order that keeps more of the shield
                outcomes[dealt] = ([name for name, _, _ in order], stopped)
        ordered = sorted(outcomes)
        pick = 0
        if len(ordered) > 1:
            who = target if isinstance(target, Seat) else self.controller_of(target)
            label = f"player {target.index}" if isinstance(target, Seat) else self.label(target)
            options = [f"{n} damage ({' then '.join(outcomes[n][0])})" for n in ordered]
            pick = (who or self.seats[0]).player.choose(DAMAGE_ORDER_PROMPT + label, options)
        dealt = ordered[pick]
        self._use_shields(target, outcomes[dealt][1])
        return dealt, outcomes[dealt][1]

    def give_poison(self, seat: Seat, count: int) -> None:
        if count > 0:
            seat.player_counters["poison"] = seat.player_counters.get("poison", 0) + count
            self.broadcast({"event": "poison", "seat": seat.index, "added": count, "total": seat.player_counters["poison"]})

    def shield(self, what: Seat | Permanent, amount: int) -> None:
        """Prevent the next `amount` damage that would be dealt to `what` this turn."""
        self.shields.append([what, amount, self.turn])

    def _prevention_capacity(self, target: Seat | Permanent, source: Permanent | None, combat: bool) -> int:
        """How much of this damage can be prevented: none if it can't be prevented, everything for a Fog this turn or a static "prevent
        all damage that would be dealt to this creature", else what the shields made this turn still hold."""
        everyone = [p for s in self.live_seats() for p in s.battlefield if not self.loses_abilities(p)]
        if any("unpreventable" in damage_prevention(p.card) for p in everyone) \
                or (source is not None and "unpreventable:self" in damage_prevention(source.card)):
            return 0
        if combat and self.fog_turn == self.turn:
            return EVERYTHING
        if isinstance(target, Permanent):
            rules = damage_prevention(target.card) if not self.loses_abilities(target) else frozenset()
            if "self:all" in rules or ("self:combat" in rules and combat) \
                    or ("self:creatures" in rules and source is not None and "Creature" in source.card.type_line):
                return EVERYTHING
        elif any("you:all" in damage_prevention(p.card) for p in target.battlefield if not self.loses_abilities(p)):
            return EVERYTHING
        return sum(entry[1] for entry in self.shields if entry[0] is target and entry[2] == self.turn and entry[1] > 0)

    def _use_shields(self, target: Seat | Permanent, used: int) -> None:
        """Use up `used` points of the shields on `target`, in the order they were made."""
        for entry in self.shields:
            if used > 0 and entry[0] is target and entry[2] == self.turn and entry[1] > 0:
                taken = min(used, entry[1])
                entry[1] -= taken
                used -= taken

    def _damage_after_prevention(self, target: Seat | Permanent, amount: int, source: Permanent | None, combat: bool) -> int:
        """How much of `amount` damage is still dealt after prevention."""
        if amount <= 0:
            return amount
        used = min(amount, self._prevention_capacity(target, source, combat))
        self._use_shields(target, used)
        return amount - used

    def prevent_combat_damage(self, seat: Seat, token: Card | None) -> None:
        """Inkshield: no combat damage is dealt to `seat` this turn; `token` is created for each point prevented."""
        seat.combat_shield_turn, seat.combat_shield_token = self.turn, token
        self.broadcast({"event": "combat_shield", "seat": seat.index})

    def destroy(self, permanent: Permanent, no_regen: bool = False) -> None:
        if self.has_keyword(permanent, "indestructible"):
            return
        if self._saved_from_destruction(permanent, no_regen):
            return
        self._leave_battlefield(permanent, "destroyed")

    def _saved_from_destruction(self, permanent: Permanent, no_regen: bool = False) -> bool:
        """Whether a regeneration shield or an Aura with umbra armor stands in for `permanent` being destroyed (the shield
        unless it "can't be regenerated")."""
        return (not no_regen and self._regenerated(permanent)) or self._umbra_armor(permanent)

    def _umbra_armor(self, permanent: Permanent) -> bool:
        """Umbra armor: instead of being destroyed the permanent loses all damage, and the Aura is destroyed."""
        aura = next((a for other in self.seats for a in other.battlefield
                     if a.attached_to is permanent and "umbra_armor" in rules_statics(a.card)), None)
        if aura is None:
            return False
        permanent.damage = 0
        permanent.deathtouched = False
        self._leave_battlefield(aura, "destroyed")
        self.broadcast({"event": "umbra_armor", "card": permanent.card.name, "aura": aura.card.name})
        return True

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
        wanted = parse_filter(kind)  # ... "nonland permanent with mana value 2 or less"
        found: list[Permanent] = []
        for seat in self.live_seats():
            if (wanted.controller == "opponent" and seat is caster) or (wanted.controller == "you" and seat is not caster):
                continue
            found += [p for p in seat.battlefield
                      if wanted.matches(p.card) and self._in_state(p, wanted.state) and self._passes(p, restriction)]
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
            at_most = None if restriction.at_most is None else self.amount(restriction.at_most)
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
                or (restriction.attacking is not None
                    and any(a.attacker is permanent for a in self.combat.attacks) != restriction.attacking)
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
        """Whether a permanent is "attacking", "attacking or blocking", "tapped" or "untapped" (any permanent, if no state is asked for)."""
        if state == "attacking":
            return any(a.attacker is permanent for a in self.combat.attacks)
        if state == "attacking or blocking":  # Eiganjo
            return any(a.attacker is permanent or permanent in a.blockers for a in self.combat.attacks)
        return {"tapped": permanent.tapped, "untapped": not permanent.tapped}.get(state, True)

    def _spared(self, permanent: Permanent, spared: MassFilter) -> bool:
        """Whether an "except for ..." filter describes this permanent (so it is left alone)."""
        return self._passes(permanent, spared)

    def destroy_all(self, permanents: list[Permanent], no_regen: bool = False, gives: GiveBack | None = None,
                    caster: Seat | None = None) -> list[Permanent]:
        """Destroy them all at once; indestructible ones survive, and so do ones with a regeneration shield
        unless they "can't be regenerated". `gives`: tokens for what was destroyed (see _give_back). Returns what was destroyed."""
        doomed = [p for p in permanents if not self.has_keyword(p, "indestructible")
                  and not self._saved_from_destruction(p, no_regen)]
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
                self.create_tokens(seat, gives.token, self.amount(gives.count), (power, "+1/+1") if power else None)
            return
        for permanent in left:
            if gives.who == "you" and permanent.last_controller is not caster:
                continue
            self.create_tokens(_checked(caster) if gives.who == "you" else _checked(permanent.last_controller), gives.token, self.amount(gives.count))

    def return_to_hand(self, permanent: Permanent) -> None:
        """Bounce: a permanent goes to its owner's hand (a token just stops existing)."""
        self._leave_together([(permanent, "returned")], destination="hand")

    def return_all_to_hand(self, permanents: list[Permanent]) -> None:
        self._leave_together([(p, "returned") for p in permanents], destination="hand")

    def return_from_graveyard(self, target: GraveyardTarget, controller: Seat, to: str, tapped: bool = False,
                              finality: bool = False, enchantment: bool = False, transformed: bool = False) -> None:
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
        elif transformed and card.flip is not None:  # a werewolf that died comes back on its other face
            self._enter(controller, self._transformed_permanent(card, seat, tapped))
        elif enchantment:  # the Enduring cycle: back as an enchantment that is no longer a creature
            self._enter(controller, Permanent(dataclasses.replace(card, power=None, toughness=None, type_line="Enchantment"),
                                              sick=True, owner=seat, real_card=card))
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

    def return_dead_to_battlefield(self, dead: Permanent, controller: Seat, under_owner: bool, tapped: bool = False,
                                   enchantment: bool = False, transformed: bool = False) -> None:
        """A creature that just died comes back from its owner's graveyard, under `controller`'s control unless
        `under_owner`."""
        holder = self._graveyard_of(dead.card)
        if holder is not None:
            self.return_from_graveyard(GraveyardTarget(dead.card, holder), holder if under_owner else controller,
                                       "battlefield", tapped, enchantment=enchantment, transformed=transformed)

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
        if seat.library:
            self._manifest_card(seat, seat.library.pop(0))

    def _manifest_card(self, seat: Seat, real: Card) -> Permanent:
        self.broadcast({"event": "manifested", "seat": seat.index})
        entering = Permanent(FACE_DOWN, sick=True, real_card=real, manifested=True, owner=seat)
        self._enter(seat, entering)
        return entering

    def manifest_dread(self, seat: Seat) -> Permanent | None:
        """Look at the top two cards of the library: one is manifested, the other goes to the graveyard. Returns the creature."""
        top = seat.library[:2]
        if not top:
            return None
        chosen = seat.player.choose(MANIFEST_DREAD_PROMPT, [c.name for c in top]) if len(top) > 1 else 0
        del seat.library[:len(top)]
        for index, card in enumerate(top):
            if index != chosen:
                self._move_card(seat, card, "graveyard")
        return self._manifest_card(seat, top[chosen])

    def _turn_up_options(self, seat: Seat) -> list[Permanent]:
        """Face-down creatures of `seat` (manifested, or cast with morph) that it can afford to turn face up."""
        return [p for p in seat.battlefield if p.manifested and p.real_card is not None
                and "Creature" in p.real_card.type_line and self._payment(seat, self._turn_up_card(p)) is not None
                and self._morph_payable(seat, p)]

    @staticmethod
    def _turn_up_card(permanent: Permanent) -> Card:
        """The card to pay for when turning `permanent` face up: its morph cost, or a manifested card's own mana cost."""
        real = _checked(permanent.real_card)
        return dataclasses.replace(real, mana_cost=permanent.turn_up_cost.mana or "{0}") if permanent.turn_up_cost else real

    def _morph_payable(self, seat: Seat, permanent: Permanent) -> bool:
        """Whether `seat` can pay the part of a morph cost that isn't mana: a sacrifice, a card to reveal or discard, a return, life."""
        cost = permanent.turn_up_cost
        if cost is None:
            return True
        if cost.sacrifice and len(self._morph_permanents(seat, permanent, cost.sacrifice)) < cost.count:
            return False
        if cost.bounce and len(self._morph_permanents(seat, permanent, cost.bounce)) < cost.count:
            return False
        if cost.discard and not any(_card_matches(cost.discard, c) for c in seat.hand):
            return False
        return (not cost.reveal or any(cost.reveal in c.colors for c in seat.hand)) and cost.life <= seat.life

    @staticmethod
    def _morph_permanents(seat: Seat, permanent: Permanent, kind: str) -> list[Permanent]:
        """The permanents of `kind` ("another creature", "Mountain") that can pay for turning `permanent` face up."""
        return [p for p in seat.battlefield if p is not permanent and _permanent_matches(kind.removeprefix("another "), p.card)]

    def _pay_morph(self, seat: Seat, permanent: Permanent) -> None:
        cost = permanent.turn_up_cost
        if cost is None:
            return
        for _ in range(cost.count if cost.sacrifice else 0):
            options = self._morph_permanents(seat, permanent, cost.sacrifice)
            self._leave_together([(options[seat.player.choose(SACRIFICE_COST_PROMPT + _checked(permanent.real_card).name,
                                                               [self.label(p) for p in options])], "sacrificed")])
        for _ in range(cost.count if cost.bounce else 0):
            options = self._morph_permanents(seat, permanent, cost.bounce)
            self.return_to_hand(options[seat.player.choose(MORPH_RETURN_PROMPT + _checked(permanent.real_card).name, [self.label(p) for p in options])])
        if cost.discard:
            options = [c for c in seat.hand if _card_matches(cost.discard, c)]
            discarded = options[seat.player.choose(DISCARD_PROMPT, [c.name for c in options])]
            seat.hand.remove(discarded)
            self.broadcast({"event": "discard", "seat": seat.index, "card": discarded.name})
            self._discard_into_zone(seat, discarded)
        if cost.reveal:
            revealed = next(c for c in seat.hand if cost.reveal in c.colors)
            self.broadcast({"event": "revealed", "seat": seat.index, "card": revealed.name})
        if cost.life:
            self.change_life(seat, -cost.life)

    def turn_face_up(self, seat: Seat, permanent: Permanent) -> None:
        self._spend_mana(seat, _checked(self._payment(seat, self._turn_up_card(permanent))))
        self._pay_morph(seat, permanent)
        permanent.card, permanent.real_card, permanent.manifested = _checked(permanent.real_card), None, False
        self.broadcast({"event": "turned_face_up", "seat": seat.index, "card": permanent.card.name})
        if permanent.megamorph:
            self.put_counters(permanent, "+1/+1", 1)
        self.trigger("turned_face_up", permanent, seat)  # "When this creature is turned face up, ..."

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

    def tokens_join_attack(self, seat: Seat, source: Permanent, token: Card, count: int, sacrifice_at_end: bool) -> None:
        """Mobilize: `count` tokens, tapped and attacking whom `source` attacks; they were never declared, so attack triggers don't
        see them. With `sacrifice_at_end` they are sacrificed as the next end step begins."""
        attack = next((a for a in self.combat.attacks if a.attacker is source), None)
        made = self.create_tokens(seat, token, count)
        for permanent in made:
            permanent.tapped = True
            if attack is not None:
                self.combat.attacks.append(Attack(permanent, seat, attack.defender, walker=attack.walker))
                self.broadcast({"event": "attack", "seat": seat.index, "card": permanent.card.name, "defender": attack.defender.index})
        if sacrifice_at_end:
            self.leave_at_next_end_step(made, "sacrificed", "graveyard")

    def token_attacking(self, seat: Seat, token: Card, defender: Seat) -> None:
        """A token created for `seat`, tapped and attacking `defender`; it was never declared, so attack triggers don't see it."""
        for made in self.create_tokens(seat, token, 1):
            made.tapped = True
            self.combat.attacks.append(Attack(made, seat, defender))
            self.broadcast({"event": "attack", "seat": seat.index, "card": made.card.name, "defender": defender.index})

    def exile_dead_make_spirit_copy(self, seat: Seat, dead: Permanent) -> None:
        """Hofri Ghostforge: exile the creature that just died from its owner's graveyard; if that works, `seat` creates a token
        that's a copy of it, a Spirit too, which sends the exiled card back to the graveyard when it leaves."""
        owner = self.owner_of(dead)
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
        self.happened("graveyard_leave", seat, spell=tuple(cards))

    def _exiled_from_library_or_graveyard(self, seat: Seat) -> None:
        """One or more of `seat`'s cards were just put into exile from its library and/or graveyard, as one event (Laelia)."""
        self.happened("exile_library_graveyard", seat)

    def tutor(self, seat: Seat, card_type: str, to: str, reveal: bool, count: int = 1) -> None:
        """Search the library for a card of `card_type`: it goes to the hand (`to` is "hand"), to the graveyard or to the top
        of the library ("top") after shuffling. Only "reveal" shows others which card. With a `count` above one, up to that
        many cards are found (Buried Alive), and the searcher may stop early."""
        chosen = []
        card_type = card_type.replace("mv<=x", f"mv<={self.x_value}")  # Chord of Calling
        if "mv=self" in card_type and self.resolving_item is not None:  # Transmute: the mana value of the card that was discarded
            card_type = card_type.replace("mv=self", f"mv={int(self.resolving_item.card.cmc)}")
        for _ in range(count):
            matches = _unique([c for c in seat.library if _card_matches(card_type, c)])
            if not matches:
                break
            options = [c.name for c in matches] + ([DONE] if count > 1 else [])
            choice = seat.player.choose(SEARCH_CARD_PROMPT, options)
            if choice >= len(matches):
                break
            seat.library.remove(matches[choice])
            chosen.append(matches[choice])
        self.rng.shuffle(seat.library)
        self._searched(seat)
        if not chosen:
            self.broadcast({"event": "searched", "seat": seat.index, "found": False})
            return
        for found in chosen:
            if to == "hand":
                seat.hand.append(found)
            elif to == "battlefield":
                self._enter(seat, Permanent(found, sick=True, owner=seat))
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
        if controller is None:
            return mods
        creature = "Creature" in permanent.card.type_line
        subtypes = self.subtypes(permanent)
        in_graveyards = [(s, Permanent(c)) for s in self.seats for c in s.graveyard if graveyard_statics(c)]  # Anger
        stripped = {id(a.attached_to) for s in self.seats for a in s.battlefield if a.attached_to is not None  # once, not per source
                    and any(LOSES_ALL in b.modifier.keywords for b in attached_abilities(a.card))}
        for owner, source in [(s, p) for s in self.seats for p in s.battlefield] + in_graveyards:
            if id(source) in stripped:
                continue
            for buff in static_abilities(source.card):
                if not creature and not buff.permanents:
                    continue  # (only "Other permanents you control have indestructible" reaches a land or an artifact)
                if buff.opponents:  # Elesh Norn: only the other players' creatures
                    if owner is controller:
                        continue
                elif owner is not controller and not buff.everyone:
                    continue
                if buff.plus_counter and not permanent.counters.get("+1/+1"):
                    continue
                if buff.with_counters and not any(permanent.counters.values()):
                    continue
                wanted = source.chosen_type if buff.subtype == "chosen" else buff.subtype
                if wanted == "Commander":  # Guardian Augmenter: not a creature type, a role
                    if _is_token(permanent.card) or not any(permanent.card.name in s.commander_names for s in self.seats):
                        continue
                elif (buff.other and source is permanent) or (wanted and not any(w in subtypes for w in wanted.split("|"))) or (buff.subtype == "chosen" and not wanted):
                    continue
                if buff.self_only and source is not permanent:
                    continue
                if buff.color and (source.chosen_color if buff.color == "chosen" else buff.color) not in permanent.card.colors:
                    continue
                if buff.token and not _is_token(permanent.card):
                    continue
                if buff.attacking and not any(a.attacker is permanent for a in self.combat.attacks):
                    continue
                if buff.condition and not self.condition_holds(buff.condition, owner, source):
                    continue
                mods.append(self._scaled(buff.modifier, buff.per, permanent, controller, source))
        if not creature:
            return mods
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

    def _scaled(self, modifier: Modifier, per: tuple[str, str] | None, permanent: Permanent, controller: Seat,
                source: Permanent | None = None) -> Modifier:
        """A "for each ..." bonus times how many there are right now."""
        if per is None:
            return modifier
        what, kind = per
        if what == "permanent":
            count = sum(has_type(p.card, kind) for p in controller.battlefield)
        elif what == "commander_casts":
            count = sum(controller.commander_casts.values())
        elif what == "commander_casts":
            count = sum(controller.commander_casts.values())
        elif what == "graveyard":
            count = sum(_card_matches(kind, c) for c in controller.graveyard)
        elif what == "source_counters":  # Door of Destinies: for each charge counter on the permanent that gives the bonus
            count = source.counters.get(kind, 0) if source is not None else 0
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
            self.untap(permanent)
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
        if isinstance(second, Seat):  # "deals damage equal to its power to any target" aimed at a player
            if self.on_battlefield(first):
                self.damage(second, self.power(first), source=first)
            return
        if not (self.on_battlefield(first) and self.on_battlefield(second)):
            return
        hit_second, hit_first = self.power(first), self.power(second)
        self.broadcast({"event": "fight", "card": first.card.name, "against": second.card.name})
        self.damage(second, hit_second, source=first)
        if not one_sided:
            self.damage(first, hit_first, source=second)

    def return_with_counter(self, dead: Permanent | None, counter: str, tapped: bool = False) -> None:
        """Persist and undying: put the card that just died back onto the battlefield with a counter, under its
        owner's control, if it is still in the graveyard (a token or a commander sent elsewhere isn't)."""
        if dead is None:
            return
        seat = dead.owner or dead.last_controller
        if seat is None or dead.card not in seat.graveyard:
            return
        seat.graveyard.remove(dead.card)
        self.broadcast({"event": "left_graveyard", "seat": seat.index, "card": dead.card.name, "to": "battlefield"})
        self._left_graveyard(seat, [dead.card])
        self._enter(seat, Permanent(dead.card, sick=True, tapped=tapped, loyalty=_starting_loyalty(dead.card),
                                    counters={counter: 1} if counter else {}))

    def _unearth(self, seat: Seat, card: Card) -> None:
        """Unearth: pay its cost and return it from the graveyard (it is not cast); it has haste, and is exiled at the beginning
        of the next end step or instead of leaving the battlefield some other way."""
        tapped = _checked(self._payment(seat, dataclasses.replace(card, mana_cost=unearth_cost(card))))
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
        tapped = _checked(self._payment(seat, dataclasses.replace(card, mana_cost=encore_cost(card))))
        self._spend_mana(seat, tapped)
        seat.graveyard.remove(card)
        self.broadcast({"event": "encore", "seat": seat.index, "card": card.name})
        self._move_card(seat, card, "exile")
        self._left_graveyard(seat, [card])
        self.attacking_tokens(seat, dataclasses.replace(card, type_line="Token " + card.type_line), 1, True, "sacrificed")

    def _eternalize(self, seat: Seat, card: Card) -> None:
        """Eternalize: pay its cost and exile it from the graveyard; create a token copy that is a 4/4 black Zombie with no mana
        cost (CR 702.129a). The token is a copy of the card as it is in the graveyard, so it keeps the card's other types."""
        tapped = _checked(self._payment(seat, dataclasses.replace(card, mana_cost=eternalize_cost(card))))
        self._spend_mana(seat, tapped)
        if eternalize_discards(card):  # "Eternalize\u2014{3}{U}{U}, Discard a card."
            self.discard(seat, 1)
        seat.graveyard.remove(card)
        self.broadcast({"event": "eternalize", "seat": seat.index, "card": card.name})
        self._move_card(seat, card, "exile")
        self._left_graveyard(seat, [card])
        kind, _, subtypes = card.type_line.partition(" \u2014 ")
        token = dataclasses.replace(card, type_line=f"Token {kind} \u2014 Zombie {subtypes}".strip(), mana_cost="", cmc=0, colors=("B",),
                                    power="4", toughness="4")
        self.create_tokens(seat, token, 1)

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
        self.broadcast({"event": "copied_permanent", "seat": (seat or self.controller(permanent)).index,
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
        self.happened("conjure", seat)

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
        seat.token_turn = self.turn  # "if you created a token this turn" (Idol of Oblivion)
        if any(replacement_effects(p.card).manufactor for p in seat.battlefield):  # Academy Manufactor
            tokens = [t for token in tokens for t in ((CLUE, FOOD, TREASURE) if token.name in ("Clue", "Food", "Treasure") else (token,))]
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
            self.happened("tokens_created", seat)
        if made:
            self.happened("tokens_enter", seat)
        return made

    def _warp_exile(self, permanent: Permanent, owner: Seat) -> None:
        """Warp: the creature is exiled at the beginning of the next end step; its owner may cast it from exile on a later turn."""
        card = permanent.card
        self._leave_together([(permanent, "exiled")], "exile")
        if card in owner.exile:
            owner.exile_play.append((card, FOREVER))

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
        owner = self.owner_of(dead)
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
        cost = cost_of(card.mana_cost).reduced(reduction) if card.mana_cost else Cost()
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
        owner = self.owner_of(target)
        card, before = target.transformed_from or target.card, len(owner.exile)
        self.exile(target)
        if source is not None and not _is_token(card) and len(owner.exile) > before:
            source.exiled_with.append((owner, card))

    def exile_until_leaves(self, target: Permanent, source: Permanent | None) -> None:
        """Exile `target` until `source` leaves the battlefield. If the source is already gone, nothing
        is exiled. A token is exiled for good, since it would stop existing anyway."""
        if source is not None and not self.on_battlefield(source):
            return
        owner = self.owner_of(target)
        card, before = target.card, len(owner.exile)
        self.exile(target)
        if source is not None and not _is_token(card) and len(owner.exile) > before:  # not sent to the command zone
            source.linked_exile.append((owner, card))

    def transform(self, permanent: Permanent, by_day_night: bool = False) -> None:
        """A double-faced permanent turns over to its other face (CR 701.28); the same permanent, with its counters, damage and
        Auras. A permanent with daybound or nightbound is turned over only by the day/night rule. Anything else (a token, a
        single-faced card, a copy) is left alone."""
        if not self.on_battlefield(permanent):
            return
        front = permanent.transformed_from
        if front is None and (permanent.card.flip is None or _is_token(permanent.card)):
            return
        if not by_day_night and day_night_face(permanent.card) is not None:
            return
        seat = self.controller(permanent)
        if front is None:
            permanent.transformed_from, permanent.card = permanent.card, _checked(permanent.card.flip)
        else:
            permanent.card, permanent.transformed_from = front, None
        permanent.loyalty = _starting_loyalty(permanent.card) if "Planeswalker" in permanent.card.type_line and permanent.loyalty is None \
            else permanent.loyalty if "Planeswalker" in permanent.card.type_line else None
        self.broadcast({"event": "transformed", "seat": seat.index, "card": permanent.card.name})
        self.trigger("transformed", permanent, seat)

    def _transformed_permanent(self, card: Card, owner: Seat, tapped: bool = False) -> Permanent:
        """A new permanent that is `card` on its back face: a Saga that comes back as a creature, a werewolf that died."""
        back = _checked(card.flip)
        return Permanent(back, sick=True, tapped=tapped, loyalty=_starting_loyalty(back), owner=owner, transformed_from=card)

    def _update_day_night(self) -> None:
        """As a turn begins (CR 726.3): day becomes night if the previous turn's player cast no spells, night becomes day if they
        cast two or more."""
        if self.day_night is None or self.previous_player is None:
            return
        cast = sum(1 for turn, _ in self.previous_player.cast_log if turn == self.turn - 1)
        if self.day_night == "day" and cast == 0:
            self._set_day_night("night")
        elif self.day_night == "night" and cast >= 2:
            self._set_day_night("day")

    def _set_day_night(self, new: str) -> None:
        """It becomes day or night: every permanent with the face that goes with the other side turns over."""
        self.day_night = new
        self.broadcast({"event": "day_night", "now": new})
        for seat in self.live_seats():
            for permanent in list(seat.battlefield):
                face = day_night_face(permanent.card)
                if (new == "night" and face == "day") or (new == "day" and face == "night"):
                    self.transform(permanent, by_day_night=True)

    def flicker(self, target: Permanent, controller: Seat, when: str, to: str, under_owner: bool, transformed: bool = False) -> None:
        """Exile `target`, then return it to the battlefield (or its owner's hand) right away (`when` is "now") or as the
        next end step begins ("end_step"). A token is gone for good; it comes back under `controller`'s control if
        the card says "under your control", otherwise under its owner's."""
        owner = self.owner_of(target)
        card, before = target.transformed_from or target.card, len(owner.exile)
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
                self._return_from_exile(owner if under_owner else controller, card, owner, transformed)

        if when == "now":
            bring_back()
        else:
            fire_turn = self.turn + 1 if self.step in ("end", "cleanup") else self.turn
            self.at_end_step.append((fire_turn, bring_back))

    def _return_from_exile(self, seat: Seat, card: Card, owner: Seat | None = None, transformed: bool = False) -> None:
        """A card exiled "until" comes back as a new permanent under its owner's control."""
        holder = owner or seat  # the exile zone it is in belongs to its owner, who may not be the one it returns to
        if seat.lost or card not in holder.exile:
            return
        holder.exile.remove(card)
        self.broadcast({"event": "returned_from_exile", "seat": seat.index, "card": card.name})
        self._enter(seat, self._transformed_permanent(card, holder) if transformed and card.flip is not None
                    else Permanent(card, sick=True, loyalty=_starting_loyalty(card), owner=holder))

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
            self._move_card(item.home, item.physical, "exile" if exile or item.exile_after else "graveyard")

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

    def _ward_payment(self, payer: Seat, fields: dict) -> Payment | None:
        """The permanents to tap for a ward cost's mana (none if it has no mana), or None if it can't be paid."""
        return self._pay_cost(payer, cost_of(fields["mana_cost"])) if fields.get("mana_cost") else Payment()

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
        if ward is None or item is None or item not in self.stack:
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
                         tapped: bool = True, subtypes: tuple[str, ...] | None = None) -> None:
        """Search for a basic land card; with `subtypes`, for any land card with one of those land types (Boseiju)."""
        if optional and seat.player.choose(SEARCH_OPTIONAL_PROMPT, YES_NO) != 0:
            return
        basics = _unique([c for c in seat.library if (_is_searched_land(c, subtypes) if subtypes
                                                       else "Basic" in c.type_line and "Land" in c.type_line)])
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
                         tapped: bool, reveal: bool, basic_only: bool = False, share_type: bool = False) -> None:
        """Search for up to `count` lands (basic lands, or any land with one of `subtypes`): the first
        `battlefield` go onto the battlefield and the rest into the hand, then the library is shuffled. With `share_type`
        every land after the first has a land type the first one has (Myriad Landscape)."""
        to_battlefield: list[Card] = []
        to_hand: list[Card] = []
        for n in range(count):
            matches = _unique([c for c in seat.library if _is_searched_land(c, subtypes) and (not basic_only or "Basic" in c.type_line)])
            if share_type and n:
                first_types = set((to_battlefield + to_hand)[0].type_line.partition("\u2014")[2].split())
                matches = [c for c in matches if first_types & set(c.type_line.partition("\u2014")[2].split())]
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

    def exile_top_of_other(self, seat: Seat, victim: Seat) -> None:
        """Ragavan: exile the top card of `victim`'s library; `seat` may cast it until the turn ends."""
        if not victim.library:
            return
        card = victim.library.pop(0)
        seat.exile.append(card)
        seat.borrowed.append((card, victim))
        seat.exile_play.append((card, self.turn))
        self.broadcast({"event": "exiled_from_library", "seat": victim.index, "cards": [card.name], "may_play": True})

    def exile_top_of_each_cast_free(self, seat: Seat) -> None:
        """Etali, Primal Storm: exile the top card of each library; `seat` may cast any number of the spells among them free."""
        exiled = []
        for owner in self.turn_order_from_active():
            if owner.library:
                card = owner.library.pop(0)
                owner.exile.append(card)
                exiled.append((owner, card))
                self.broadcast({"event": "exiled_from_library", "seat": owner.index, "cards": [card.name], "may_play": True})
        while True:
            options = [(o, c) for o, c in exiled if not is_land(c) and any(x is c for x in o.exile)]
            if not options:
                return
            choice = seat.player.choose(CAST_FREE_PROMPT, [c.name for _, c in options] + [NONE_TAKEN])
            if choice >= len(options):
                return
            owner, card = options[choice]
            self._cast(seat, card, owner.exile, free=True)
            exiled = [(o, c) for o, c in exiled if c is not card]

    def connive(self, seat: Seat, permanent: Permanent) -> None:
        """Connive: draw a card, then discard a card; if it wasn't a land the creature gets a +1/+1 counter."""
        self.draw(seat, 1)
        if not seat.hand:
            return
        card = seat.hand.pop(seat.player.choose(DISCARD_CARD_PROMPT, [c.name for c in seat.hand]))
        self.broadcast({"event": "discard", "seat": seat.index, "card": card.name})
        self._discard_into_zone(seat, card)
        self._discarded(seat, card)
        if not is_land(card) and self.on_battlefield(permanent):
            self.put_counters(permanent, "+1/+1", 1)

    def amass(self, seat: Seat, count: int, kind: str) -> None:
        """Amass N: N +1/+1 counters on an Army you control (a 0/0 black Army token first, if you control none); it is also `kind`."""
        armies = [p for p in seat.battlefield if "Army" in p.card.type_line]
        if not armies:
            armies = self.create_tokens(seat, Card(name=f"{kind or 'Army'} Army", type_line="Token Creature \u2014 Army", colors=("B",),
                                                   power="0", toughness="0"), 1)
        army = armies[0] if len(armies) == 1 else armies[seat.player.choose(AMASS_PROMPT, [self.label(p) for p in armies])]
        if kind and kind not in army.card.type_line.split():
            army.card = dataclasses.replace(army.card, type_line=f"{army.card.type_line} {kind}")
        self.put_counters(army, "+1/+1", count)

    def imprint_from_hand(self, seat: Seat, source: Permanent) -> None:
        """Chrome Mox: exile a nonartifact, nonland card from the hand and keep it with `source` (its colors are the mana)."""
        options = [c for c in seat.hand if "Artifact" not in c.type_line and not is_land(c)]
        if not options:
            return
        card = options[seat.player.choose(IMPRINT_PROMPT, [c.name for c in options])]
        seat.hand.remove(card)
        self._move_card(seat, card, "exile")
        source.exiled_with.append((seat, card))
        self.broadcast({"event": "imprint", "seat": seat.index, "card": card.name})

    def add_devotion_mana(self, seat: Seat) -> None:
        """Nyx Lotus: choose a color; add that much mana of it as your devotion to it."""
        names = {"White": "W", "Blue": "U", "Black": "B", "Red": "R", "Green": "G"}
        color = names[list(names)[seat.player.choose(MANA_COLOR_PROMPT, list(names))]]
        self.add_mana(seat, (frozenset(color),) * self.evaluate(Amount("devotion", color), seat))

    def look_top_take_chosen(self, seat: Seat, source: Permanent | None, creature: bool) -> None:
        """Look at the top card; if it is of the type `source` chose (and a creature card, for Herald's Horn), `seat` may take it."""
        if source is None or not seat.library:
            return
        top = seat.library[0]
        if source.chosen_type not in top.type_line.partition("\u2014")[2].split() or (creature and "Creature" not in top.type_line):
            return
        if seat.player.choose(REVEAL_CHOSEN_PROMPT + top.name, YES_NO) == 0:
            seat.library.pop(0)
            seat.hand.append(top)
            self.broadcast({"event": "revealed", "seat": seat.index, "card": top.name})

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
            self.happened("scried", seat)

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
        owner = self.owner_of(permanent)
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
                paid = self._pay_cost(seat, cost_of(echo))
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
        self.broadcast({"event": "class_level", "seat": self.controller(permanent).index, "card": permanent.real_card.name,
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
            holder = self.controller(one)
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
        self.happened("became_monarch", seat)

    def pays_unless(self, payer: Seat, cost_text: str, source: Card) -> bool:
        """"... unless that player pays {1}": whether `payer` can and chooses to pay the cost (and pays it)."""
        payment = self._pay_cost(payer, cost_of(cost_text))
        if payment is None or payer.player.choose(UNLESS_PROMPT + source.name, [f"Pay {cost_text}", "Don't pay"]) != 0:
            return False
        self._spend_mana(payer, payment)
        self.broadcast({"event": "paid_unless", "seat": payer.index, "card": source.name, "cost": cost_text})
        return True

    def pays_optional(self, payer: Seat, cost_text: str, source: Card | None) -> bool:
        """ "You may pay {2}. If you do, ...": whether `payer` can and chooses to pay the cost (and pays it)."""
        payment = self._pay_cost(payer, cost_of(cost_text))
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
        options: tuple[str, ...] = ROOMS[room].leads_to if room else (START,)
        if not options:
            self.broadcast({"event": "dungeon_completed", "seat": seat.index, "dungeon": "Undercity"})
            options = (START,)
        entered = options[seat.player.choose(VENTURE_PROMPT, list(options)) if len(options) > 1 else 0]
        seat.undercity_room = entered
        self.broadcast({"event": "venture", "seat": seat.index, "room": entered})
        effects = (ThroneOfTheDeadThree(),) if entered == "Throne of the Dead Three" else tuple(line_effects(ROOMS[entered].text) or ())
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
            self.happened("surveilled", seat)

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
        if (face := day_night_face(permanent.card)) is not None:  # daybound: it is day if it was neither; at night it enters transformed
            if self.day_night is None:
                self._set_day_night(face)
            elif face == "day" and self.day_night == "night" and permanent.card.flip is not None and permanent.transformed_from is None:
                permanent.transformed_from, permanent.card = permanent.card, _checked(permanent.card.flip)
        if is_class(permanent.card):  # a Class enters at level 1: it reads as the abilities of that level
            permanent.real_card, permanent.card, permanent.level = permanent.card, class_view(permanent.card, 1), 1
        extra_when_copy = False
        if keyword := temporary_clone_keyword(permanent.card):  # Cursed Mirror
            self._become_temporary_copy(seat, permanent, keyword)
        elif clone := clone_kind(permanent.card):  # "You may have it enter as a copy of ...": decided as it enters
            extra_when_copy = clone_extra_counters(permanent.card)
            artifact_too = clone_is_artifact(permanent.card)
            self._become_copy(seat, permanent, *clone)
            if artifact_too and permanent.real_card is not None and "Artifact" not in permanent.card.type_line:  # Phyrexian Metamorph
                permanent.card = dataclasses.replace(permanent.card, type_line="Artifact " + permanent.card.type_line)
        counters = {counter: (x if count == "X" else 2 * x if count == "2X" else int(count))
                    for counter, count in enters_with_counters(permanent.card, permanent.kicked, permanent.escaped, any(
                        o.damage_taken_turn == self.turn for o in self.opponents(seat))).items()}
        if permanent.extra_counters:  # Opal Palace: mana spent on the commander
            counters["+1/+1"] = counters.get("+1/+1", 0) + permanent.extra_counters
        if extra_when_copy and permanent.real_card is not None:  # Altered Ego: X additional counters on the copy
            counters["+1/+1"] = counters.get("+1/+1", 0) + x
        if "Creature" in permanent.card.type_line:  # Metallic Mimic: other creatures of the type it named come with a counter
            kinds = permanent.card.type_line.partition("\u2014")[2].split()
            counters["+1/+1"] = counters.get("+1/+1", 0) + sum(
                replacement_effects(p.card).enter_counter_chosen for p in seat.battlefield
                if p.chosen_type is not None and p.chosen_type in kinds)
            if not counters["+1/+1"]:
                del counters["+1/+1"]
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
            if is_chosen_type_itself(permanent.card):  # Roaming Throne: it is that type too
                head, dash, tail = permanent.card.type_line.partition("\u2014")
                permanent.real_card = permanent.real_card or permanent.card
                permanent.card = dataclasses.replace(permanent.card, type_line=f"{head.strip()} \u2014 {tail.strip()} {permanent.chosen_type}"
                                                     if dash else f"{head.strip()} \u2014 {permanent.chosen_type}")
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
        if any(key.startswith("enter_tapped:opp:") and owner is not seat and _permanent_matches(key.rpartition(":")[2].replace(",", " or "), permanent.card)
               for owner, _, key in self._static_rules()):
            permanent.tapped = True  # Authority of the Consuls, Blind Obedience
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
        kind = next((target_kind(e) for e in item.effects or () if target_kind(e)), None)
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
            return not any(any(all(has_type(p.card, word) for word in alternative.split("+")) for alternative in rule.types)
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
        if is_a_land and seat.lands_played >= self._land_drops(seat):
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
        options = [p for p in seat.battlefield if p is not source and not p.tapped and has_type(p.card, land_type)]
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
            owner = _checked(permanent.last_controller)
            owner.battlefield = [p for p in owner.battlefield if p is not permanent]
        left = {id(permanent) for permanent, _ in leaving}  # an attacker that leaves is removed from combat
        self.combat.attacks = [a for a in self.combat.attacks if id(a.attacker) not in left]
        gone = [(permanent, _checked(permanent.last_controller)) for permanent, _ in leaving]
        for permanent, reason in leaving:
            self.broadcast({"event": reason, "seat": _checked(permanent.last_controller).index, "card": permanent.card.name})
        # Sacrifice triggers look back in time, so what was sacrificed sees itself go.
        everyone = [(p, s) for s in self.live_seats() for p in s.battlefield] + gone
        for permanent, reason in leaving:
            if reason != "sacrificed":
                continue
            controller = _checked(permanent.last_controller)
            for watcher, watcher_seat in everyone:
                if watcher_seat is controller and "Creature" in permanent.card.type_line:
                    self.trigger("sacrifice_creature", watcher, controller)
                if watcher_seat is not controller and "Creature" in permanent.card.type_line:
                    self.trigger("opponent_sacrifice_creature", watcher, watcher_seat, player=controller)
                self.trigger("any_sacrifice", watcher, watcher_seat)
                if watcher is not permanent:
                    self.trigger("other_sacrifice", watcher, watcher_seat)
            self._observe("sacrifice", permanent.card, controller, subject=permanent, extra=gone)  # Tireless Tracker, Mirkwood Bats
        destination_all = destination
        for permanent, _ in leaving:
            controller = _checked(permanent.last_controller)
            destination = ("exile" if destination_all == "graveyard" and permanent.counters.get("finality")
                           and "Creature" in permanent.card.type_line else destination_all)  # a finality counter: exiled, not dying
            if destination == "graveyard" and replacement_effects(permanent.card).graveyard_self:
                destination = "exile"  # the back of a Disturb card: exiled instead of going to a graveyard
            if destination == "graveyard" and replacement_effects(permanent.card).graveyard_shuffle:
                destination = SHUFFLED  # Blightsteel Colossus: shuffled into its library, so it never dies
            if destination == "graveyard" and "Creature" in permanent.card.type_line and self._dies_exiled(permanent, controller):
                destination = "exile"  # Lava Coil, Liesa, Gloomshrieker: exiled instead of dying
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
                if permanent.returns_when_dies == self.turn:
                    self._queue(RETURN_WHEN_DIES, permanent, controller)
                for attachment, attachment_seat in everyone:  # "When enchanted creature dies"
                    if attachment.attached_to is permanent:
                        self.trigger("host_dies", attachment, attachment_seat, subject=permanent)
                self._observe("creature_dies", permanent.card, controller, subject=permanent, extra=gone)
            elif destination == "graveyard" and "Artifact" in permanent.card.type_line:  # "creature or artifact ... dies", a token too
                self._observe("creature_dies", permanent.card, controller, subject=permanent, extra=gone)
            self._observe("permanent_leaves", permanent.card, controller, subject=permanent, extra=gone)
            if permanent.real_card is not None:  # a Clone goes to the graveyard as itself
                permanent.card, permanent.real_card = permanent.real_card, None
            if permanent.transformed_from is not None:  # a double-faced card is its front face everywhere but the battlefield
                permanent.card, permanent.transformed_from = permanent.transformed_from, None
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

    def _dies_exiled(self, creature: Permanent, controller: Seat) -> bool:
        """Whether a creature that would die is exiled instead: marked by a spell this turn, a replacement effect on itself ("If this
        creature would die, exile it instead."), or one on a permanent that exiles an opponent's creatures."""
        if creature.exile_if_dies == self.turn or replacement_effects(creature.card).die_exile == "self":
            return True
        return any(replacement_effects(p.card).die_exile == "opponent" for s in self.live_seats() if s is not controller
                   for p in s.battlefield)

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
            if creature:
                count *= self._factor(seat, "plus_one_factor")  # Branching Evolution doubles it after the extra ones
        return count * self._factor(seat, "counters")

    def _trigger_times(self, controller: Seat, event: str, entering: Card | None, cause: Seat | None = None,
                       source: Permanent | None = None) -> int:
        """A triggered ability of `source` triggers once, plus once more for each Harmonic Prodigy (another one) when `source` is a
        Shaman or Wizard, plus what _trigger_times_entering adds."""
        times = self._trigger_times_entering(controller, event, entering, cause)
        if source is not None and {"Shaman", "Wizard"} & set(self.subtypes(source)):
            times += sum(replacement_effects(p.card).extra_trigger == "wizard" for p in controller.battlefield if p is not source)
        if source is not None and "Creature" in source.card.type_line:  # Roaming Throne: another creature of the type it named
            kinds = self.subtypes(source)
            times += sum(replacement_effects(p.card).extra_trigger == "chosen_type" and p.chosen_type in kinds
                         for p in controller.battlefield if p is not source)
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
        if zone == "graveyard" and replacement_effects(card).graveyard_shuffle:
            zone = SHUFFLED  # the card's own replacement effect works from every zone (CR 614.12)
        elif zone == "graveyard" and self._exiled_instead(seat):
            zone = "exile"
        if card.name in seat.commander_names:
            if seat.player.choose(COMMAND_ZONE_PROMPT, ["Command zone", "Library" if zone == SHUFFLED else zone.capitalize()]) == 0:
                seat.command_zone.append(card)
                self.broadcast({"event": "to_command_zone", "seat": seat.index, "card": card.name})
                return
        if zone == "library_top":
            seat.library.insert(0, card)
            return
        if zone == SHUFFLED:  # revealed, then shuffled into its owner's library
            self.broadcast({"event": "revealed", "seat": seat.index, "card": card.name})
            seat.library.append(card)
            self.rng.shuffle(seat.library)
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
                reason = ("opponent_won" if any(o.wins_game for o in self.seats if o is not seat)
                          else "life" if seat.life <= 0
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
                        if not self._saved_from_destruction(permanent):
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
    return parse_filter(kind).matches(card)


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
    """Whether a card in a library or graveyard is of `kind`: "card", "permanent", "creature|mv<=3", "basic land", ... (filters.py)."""
    return parse_filter(kind).matches(card)


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
    if kind == "targets a creature":  # Killian, Ink Duelist
        return _targets_a_creature(card)
    return parse_filter(kind).matches(card)


def _targets_a_creature(card: Card) -> bool:
    """Whether casting the card means choosing a creature as a target: an Aura that enchants one, or a spell with such a target."""
    if (enchants := aura_kind(card)) is not None:
        return "creature" in enchants
    return any("creature" in (target_kind(e) or "") for e in (_effects(card) or []))


COMBAT_STEPS = {"beginning_of_combat", "declare_attackers", "declare_blockers", "combat_damage", "end_of_combat"}


def _flash_covers(kind: str, card: Card) -> bool:
    """Whether "You may cast <kind> spells as though they had flash" covers `card`: "spell" is any, "creature", "sorcery", or a
    creature type ("spirit")."""
    return kind == "spell" or kind in card.type_line.lower().replace("\u2014", " ").split()


def _instant_speed(card: Card) -> bool:
    return "Instant" in card.type_line or has_keyword(card, "flash")


def _permanent_matches(kind: str, card: Card) -> bool:
    """Whether a permanent's card is of `kind` ("creature", "nonland permanent", "black creature", "Elf", ...): see filters.py."""
    return parse_filter(kind).matches(card)


def _take(cards: list[Card], name: str) -> Card:
    card = next(c for c in cards if c.name == name)
    cards.remove(card)
    return card


def _take_face(cards: list[Card], name: str) -> Card:
    """The card named `name` leaves the list; if it is the back face of a double-faced card, that face comes out."""
    card = next(c for c in cards if c.name == name or (c.back and c.back.name == name))
    cards.remove(card)
    return card.back if card.back and card.back.name == name else card


def _extra_text(cost) -> str:
    """How an additional cost is shown when there is a choice of two."""
    return (f"Sacrifice a {cost.sacrifice}" if cost.sacrifice else "Discard a card" if cost.discard
            else f"Pay {cost.life} life" if cost.life else f"Pay {cost.mana}")


def _unique(cards: list[Card]) -> list[Card]:
    return list({c.name: c for c in cards}.values())
