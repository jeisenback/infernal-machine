"""The events a permanent's abilities can wait for, each declared once.

An event is declared with the rules text that names it ("Whenever you draw a card, ...") and, when the game announces it to
every permanent of a player instead of to one permanent, with the occurrence that sets it off and who hears it:

    declare("opponent_discard", re.compile(r"Whenever an opponent discards a card, (.+)", re.I),
            to="opponents", happens="discarded")

The game then only says that the occurrence happened (`Game.happened("discarded", seat)`), and every event declared for it
fires for whoever hears it. A new "Whenever ..." that an existing occurrence already covers needs a declaration here and
nothing in the game; a new occurrence needs one `happened` call where it happens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from .common import _SELF


# Which hearers an occurrence concerns, beyond who they are: (the permanent hearing it, the subject the occurrence is about, the facts the
# occurrence reported) -> whether it triggers. It replaced a string `needs` that `Game.happened` had a branch for (issue #439).
Accepts = Callable[[Any, Any, tuple[str, ...]], bool]


def fact(name: str) -> Accepts:
    """The occurrence reported `name` ("first": the first time this turn, "second", "extra")."""
    return lambda hearer, subject, facts: name in facts


def about_artifact(hearer: Any, subject: Any, facts: tuple[str, ...]) -> bool:
    """The subject is an artifact ("Whenever you activate an ability of an artifact")."""
    return subject is not None and "Artifact" in subject.card.type_line


def on_the_subject(hearer: Any, subject: Any, facts: tuple[str, ...]) -> bool:
    """The hearer is attached to the subject: only the Equipment (or Aura) on a creature hears what happens to it."""
    return subject is not None and hearer.attached_to is subject


@dataclass(frozen=True)
class Event:
    name: str
    text: re.Pattern  # the rules text; group 1 is what follows the comma
    to: str = "direct"  # "you": the player it happened to; "opponents": each of their opponents; "direct": the game triggers it itself
    happens: tuple[str, ...] = ()  # the occurrences that set it off (the event's own name when not given)
    accepts: Accepts | None = None  # which hearers it concerns, beyond who they are (see Accepts); None: all
    about_creature: bool = False  # it is about some other creature: there "it" and "that creature" mean that creature
    about_player: bool = False  # it is about what another player did: there "that player" and "they" mean that player
    host_gone: bool = False  # the enchanted or equipped creature is gone by the time it resolves
    maybe_player: bool = False  # it may be about "that player" (the one dealt damage); read as about the player only if that is needed


EVENTS: dict[str, Event] = {}
_HEARD: dict[str, list[Event]] = {}


def declare(name: str, text: re.Pattern, to: str = "direct", happens: str | tuple[str, ...] = (), accepts: Accepts | None = None,
            about_creature: bool = False, about_player: bool = False, host_gone: bool = False,
            maybe_player: bool = False) -> Event:
    occurrences = (happens,) if isinstance(happens, str) else tuple(happens)
    event = Event(name, text, to, occurrences or (name,), accepts, about_creature, about_player, host_gone, maybe_player)
    EVENTS[name] = event
    if to != "direct":
        for occurrence in event.happens:
            _HEARD.setdefault(occurrence, []).append(event)
    return event


def heard_on(occurrence: str) -> tuple[Event, ...]:
    """The events that `occurrence` sets off, in the order they were declared."""
    return tuple(_HEARD.get(occurrence, ()))


declare("enters", re.compile(rf"When(?:ever)? {_SELF} enters(?: the battlefield)?, (.+)", re.I))
declare("targeted", re.compile(rf"When(?:ever)? {_SELF} becomes the target of an? (?:spell|spell or ability), (.+)", re.I))
declare("cast_self", re.compile(r"When you cast this spell, (.+)", re.I))  # goes on the stack above the spell (Game._cast)
declare("dies", re.compile(rf"When(?:ever)? {_SELF} dies, (.+)", re.I))
declare("attacks", re.compile(rf"Whenever {_SELF} attacks, (.+)", re.I))
declare("attacks_alone", re.compile(rf"Whenever {_SELF} attacks alone, (.+)", re.I))  # Grunn, the Lonely King
declare("damaged", re.compile(rf"When(?:ever)? {_SELF} is dealt damage, (.+)", re.I))  # Enrage; Game.deal_damage
declare("attacks_player", re.compile(rf"Whenever {_SELF} attacks an opponent, (.+)", re.I))
declare("blocks", re.compile(rf"Whenever {_SELF} blocks, (.+)", re.I))
declare("becomes_blocked", re.compile(rf"Whenever {_SELF} becomes blocked, (.+)", re.I))
declare("ally_attacks", re.compile(r"Whenever a creature you control attacks, (.+)", re.I), to="you", about_creature=True)
declare("attacked", re.compile(r"Whenever a creature attacks you, (.+)", re.I), to="you", about_creature=True)
declare("attacked_or_walker", re.compile(r"Whenever a creature attacks you or a planeswalker you control, (.+)", re.I),
        to="you", about_creature=True)
declare("transformed", re.compile(rf"When(?:ever)? {_SELF} transforms into (?:{_SELF}|[A-Z][^,]*), (.+)", re.I))
declare("enters_untapped", re.compile(rf"When {_SELF} enters untapped, (.+)", re.I))
declare("leaves", re.compile(rf"When(?:ever)? {_SELF} leaves the battlefield, (.+)", re.I))
declare("tokens_created", re.compile(r"Whenever you create one or more creature tokens, (.+)", re.I), to="you")
declare("tokens_enter", re.compile(r"Whenever one or more tokens you control enter, (.+)", re.I), to="you")
declare("foretold", re.compile(r"Whenever you foretell a card, (.+)", re.I), to="you")  # Game._foretell
declare("draw", re.compile(r"Whenever you draw a card, (.+)", re.I), to="you", happens="drew")
declare("opponent_draw", re.compile(r"Whenever an opponent draws a card, (.+)", re.I),
        to="opponents", happens="drew", about_player=True)
# Orcish Bowmasters: every draw but the one in their draw step
declare("opponent_extra_draw", re.compile(r"Whenever an opponent draws a card except the first one they draw in each of their draw steps, (.+)", re.I),
        to="opponents", happens="drew", accepts=fact("extra"), about_player=True)
declare("opponent_gain_life", re.compile(r"Whenever an opponent gains life, (.+)", re.I),
        to="opponents", happens="life_gained", about_player=True)
declare("opponent_lose_life", re.compile(r"Whenever an opponent loses life, (.+)", re.I),
        to="opponents", happens="life_lost", about_player=True)
declare("become_monarch", re.compile(r"Whenever you become the monarch, (.+)", re.I), to="you", happens="became_monarch")
declare("opponent_become_monarch", re.compile(r"Whenever an opponent becomes the monarch, (.+)", re.I),
        to="opponents", happens="became_monarch", about_player=True)
declare("discard", re.compile(r"Whenever you discard a card, (.+)", re.I), to="you", happens="discarded")
declare("exile_library_graveyard", re.compile(
        r"Whenever one or more cards are put into exile from your library and/or your graveyard, (.+)", re.I), to="you")
declare("discard_nonland", re.compile(r"Whenever you discard one or more nonland cards, (.+)", re.I),
        to="you", happens="discarded_nonland")
declare("opponent_discard", re.compile(r"Whenever an opponent discards a card, (.+)", re.I),
        to="opponents", happens="discarded", about_player=True)
declare("opponent_search", re.compile(r"Whenever an opponent searches their library, (.+)", re.I),
        to="opponents", happens="searched", about_player=True)
declare("opponent_sacrifice_creature", re.compile(r"Whenever an opponent sacrifices a creature, (.+)", re.I))
declare("second_draw", re.compile(r"Whenever you draw your second card each turn, (.+)", re.I),
        to="you", happens="drew", accepts=fact("second"))
declare("combat_damage_to_player", re.compile(rf"When(?:ever)? {_SELF} deals combat damage to a player, (.+)", re.I), maybe_player=True)
declare("upkeep", re.compile(r"At the beginning of your upkeep, (.+)", re.I))
declare("end_step", re.compile(r"At the beginning of your end step, (.+)", re.I))
declare("each_upkeep", re.compile(r"At the beginning of each upkeep, (.+)", re.I))
declare("each_end_step", re.compile(r"At the beginning of (?:each|the) end step, (.+)", re.I))
declare("combat", re.compile(r"At the beginning of combat on your turn, (.+)", re.I))
declare("each_combat", re.compile(r"At the beginning of each combat, (.+)", re.I))  # Unnatural Growth: every player's combat
declare("gain_life", re.compile(r"Whenever you gain life, (.+)", re.I), to="you", happens="life_gained")
declare("lose_life", re.compile(r"Whenever you lose life, (.+)", re.I), to="you", happens="life_lost")
declare("exploits", re.compile(rf"When(?:ever)? {_SELF} exploits a creature, (.+)", re.I))  # the Exploit keyword (Game.exploit)
declare("sacrifice_creature", re.compile(r"Whenever you sacrifice a creature, (.+)", re.I))
declare("ally_combat_damage", re.compile(r"Whenever a creature you control deals combat damage to a player, (.+)", re.I), about_creature=True)
declare("ally_noncombat_damage", re.compile(r"Whenever a source you control deals noncombat damage to an opponent, (.+)", re.I), about_creature=True)  # Niv-Mizzet, Visionary
declare("token_combat_damage", re.compile(r"Whenever a creature token you control deals combat damage to a player, (.+)",
                                      re.I), about_creature=True)
declare("host_attacks", re.compile(r"Whenever (?:equipped|enchanted) creature attacks, (.+)", re.I), about_creature=True)
declare("attack_with_two", re.compile(r"Whenever you attack with two or more creatures, (.+)", re.I))
declare("attack_with_three", re.compile(r"When(?:ever)? you attack with three or more creatures, (.+)", re.I))  # Legion's Landing
declare("attack_alone", re.compile(r"Whenever (?:you attack with a creature alone|a creature you control attacks alone), (.+)", re.I),
        to="you", about_creature=True)
declare("conjure", re.compile(r"Whenever you conjure one or more cards, (.+)", re.I), to="you")
declare("proliferate", re.compile(r"Whenever you proliferate, (.+)", re.I), to="you")
declare("enchanted_attack", re.compile(r"Whenever one or more creatures that are enchanted by an Aura you control attack, (.+)", re.I))
declare("creatures_attack", re.compile(r"Whenever (?:one or more creatures you control attack|you attack), (.+)", re.I))
declare("opponent_attacks", re.compile(r"Whenever an opponent attacks with creatures, (.+)", re.I), about_player=True)
declare("activate_x", re.compile(r"Whenever you activate an ability with \{X\} in its activation cost, (.+)", re.I), to="you")
# Rings of Brighthearth and kin: any activated ability that isn't a mana ability, which the game raises as "activated" (the ability is `spell`)
declare("activate_any", re.compile(r"Whenever you activate an ability, if it isn't a mana ability, (.+)", re.I), to="you", happens="activated")
declare("activate_artifact", re.compile(r"Whenever you activate an ability of an artifact, if it isn't a mana ability, (.+)", re.I),
        to="you", happens="activated", accepts=about_artifact)
declare("activate_host", re.compile(r"Whenever an ability of equipped creature is activated, if it isn't a mana ability, (.+)", re.I),
        to="you", happens="activated", accepts=on_the_subject)  # only the Equipment attached to the creature hears it
declare("other_attacks_two", re.compile(r"Whenever another player attacks with two or more creatures, (.+)", re.I), about_player=True)
declare("attacks_opponent", re.compile(r"Whenever a player attacks one of your opponents, (.+)", re.I), about_player=True)  # x: the seat attacked
declare("cycle", re.compile(r"Whenever you cycle (?:a|another) card, (.+)", re.I), to="you", happens="cycled")
declare("cycle_or_discard", re.compile(r"Whenever you cycle or discard (?:a|another) card, (.+)", re.I),
        to="you", happens=("cycled", "discarded"))
declare("scry_or_surveil", re.compile(r"Whenever you scry or surveil, (.+)", re.I), to="you", happens=("scried", "surveilled"))
declare("scry", re.compile(r"Whenever you scry, (.+)", re.I), to="you", happens="scried")
declare("surveil", re.compile(r"Whenever you surveil, (.+)", re.I), to="you", happens="surveilled")
declare("draw_step", re.compile(r"At the beginning of your draw step, (.+)", re.I), to="you", happens="draw_step")
declare("other_draw_step", re.compile(r"At the beginning of each other player's draw step, (.+)", re.I),
        to="opponents", happens="draw_step", about_player=True)
declare("opponent_upkeep", re.compile(r"At the beginning of each opponent's upkeep, (.+)", re.I), about_player=True)
declare("opponent_end_step", re.compile(r"At the beginning of (?:each|an) opponent's end step, (.+)", re.I), about_player=True)
declare("graveyard_leave", re.compile(r"Whenever one or more cards leave your graveyard, (.+)", re.I), to="you")
declare("any_sacrifice", re.compile(r"Whenever a player sacrifices a permanent, (.+)", re.I))
declare("other_sacrifice", re.compile(r"Whenever a player sacrifices another permanent, (.+)", re.I))
declare("host_dies", re.compile(r"When(?:ever)? (?:enchanted|equipped) creature dies, (.+)", re.I), host_gone=True)
declare("host_combat_damage", re.compile(r"Whenever (?:enchanted|equipped) creature deals combat damage to a player, (.+)", re.I), about_creature=True, about_player=True)
declare("host_damage_opponent", re.compile(r"Whenever (?:enchanted|equipped) creature deals damage to an opponent, (.+)", re.I),
        about_creature=True, about_player=True)  # Curiosity: any damage, to an opponent of the Aura's controller
declare("host_combat_damage_opponent", re.compile(r"Whenever (?:enchanted|equipped) creature deals combat damage to an opponent, (.+)", re.I),
        about_creature=True, about_player=True)  # Sleeper's Robe
declare("put_into_graveyard", re.compile(rf"When {_SELF} is put into a graveyard from the battlefield, (.+)", re.I))
declare("first_life_loss", re.compile(r"Whenever you lose life for the first time each turn, (.+)", re.I),
        to="you", happens="life_lost", accepts=fact("first"))
declare("creatures_combat_damage", re.compile(r"Whenever one or more creatures you control deal combat damage to a player, (.+)",
                                          re.I))
declare("zero_power_combat_damage", re.compile(r"Whenever one or more creatures you control with base power 0 deal combat damage "
                                           r"to a player, (.+)", re.I))
declare("tokens_combat_damage", re.compile(r"Whenever one or more creature tokens you control deal combat damage to a player, "
                                       r"(.+)", re.I))
declare("first_life_gain", re.compile(r"Whenever you gain life for the first time each turn, (.+)", re.I),
        to="you", happens="life_gained", accepts=fact("first"))
declare("opponent_second_draw", re.compile(r"Whenever an opponent draws their second card each turn, (.+)", re.I),
        to="opponents", happens="drew", accepts=fact("second"), about_player=True)
declare("turned_face_up", re.compile(rf"(?:When(?:ever)?|As) {_SELF} is turned face up, (.+)", re.I))  # Morph: see Game.turn_face_up
declare("unlock_door", re.compile(r"When you unlock this door, (.+)", re.I))  # a Room's door: see Game.unlock_door
declare("first_main", re.compile(r"At the beginning of your first main phase, (.+)", re.I))
declare("second_main", re.compile(r"At the beginning of your second main phase, (.+)", re.I))
