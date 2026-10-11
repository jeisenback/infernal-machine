"""Activated abilities: the cost fields before the colon, loyalty and equip-like abilities, and what follows."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ..cards import Card

from .common import _COUNTER, _N, _SELF, _THRESHOLD, _count, _counter_name, _split_sentences, rules_lines
from .outcomes import (
    AddMana,
    Amount,
    Attach,
    BecomeCreature,
    Condition,
    DefineX,
    LevelUp,
    PutCountersOnSource,
    ReturnThisFromGraveyard,
    Unattach,
    _MODAL_INLINE,
    _condition,
    _parse,
    _parse_modal_inline,
)
from .mana import is_mana_ability


_EQUIP = re.compile(r"Equip (legendary creature )?((?:\{\d+\}|\{[WUBRGC]\})+)")


_EQUIP_OTHER = re.compile(r"Equip\u2014(.+)\.")


def _equip_other_cost(card: Card) -> ActivatedAbility | None:
    """ "Equip\u2014Pay 3 life." / "Equip\u2014Sacrifice a creature." / "Equip\u2014Discard a card.": an equip cost that isn't plain mana."""
    for line in rules_lines(card):
        if (m := _EQUIP_OTHER.fullmatch(line)) and (fields := _cost_fields(m[1])):
            return ActivatedAbility(line, (Attach(),), sorcery_speed=True, **fields)
    return None


_RECONFIGURE = re.compile(r"Reconfigure ((?:\{\d+\}|\{[WUBRGC]\})+)")


def reconfigure_cost(card: Card) -> str | None:
    """The mana cost from "Reconfigure {2}", or None."""
    return next((m[1] for line in rules_lines(card) if (m := _RECONFIGURE.fullmatch(line))), None)


def is_reconfigure_line(line: str) -> bool:
    return _RECONFIGURE.fullmatch(line) is not None


def equip_abilities(card: Card) -> tuple[ActivatedAbility, ...]:
    """Every "Equip {2}" and "Equip legendary creature {1}" line (Brotherhood Regalia has both)."""
    return tuple(ActivatedAbility(line, (Attach("legendary creature you control" if m[1] else "creature you control"),),
                                  mana_cost=m[2], sorcery_speed=True)
                 for line in rules_lines(card) if (m := _EQUIP.fullmatch(line)))


@dataclass(frozen=True)
class ActivatedAbility:
    text: str
    effects: tuple
    mana_cost: str = ""  # e.g. "{2}{W}"; paid like a spell's cost
    tap: bool = False  # {T}
    sacrifice: bool = False  # sacrifice the source itself
    life: int = 0  # pay N life
    loyalty: int | None = None  # planeswalker loyalty change: +1, -2, 0
    sorcery_speed: bool = False  # "Activate only as a sorcery." (loyalty abilities always)
    once_per_turn: bool = False  # "Activate only once each turn."
    sacrifice_other: str | None = None  # "Sacrifice a creature": the kind ("creature", "artifact or creature", ...)
    sacrifice_another: bool = False  # "Sacrifice another creature": not the source itself
    sacrifice_count: int = 1  # "Sacrifice two creatures"
    discard: int = 0  # "Discard a card": how many
    exile_graveyard: int = 0  # "Exile a card from your graveyard": how many
    exile_graveyard_kind: str = ""  # "Exile a creature card from your graveyard": of this kind ("" for any card)
    crew: int = 0  # "Crew N": tap untapped creatures you control with total power N or more
    reconfigure: str = ""  # "attach" (only with another creature to attach to) or "unattach" (only while attached)
    remove_counter: str = ""  # "Remove a +1/+1 counter from this creature": the kind of counter
    condition: "Condition | None" = None  # "Activate only if you control two or more white permanents."
    discard_self: bool = False  # "Discard this card": activated from the hand, like cycling (Magma Opus)
    exile_source: bool = False  # "Exile this artifact": the source is exiled as a cost (Perpetual Timepiece)
    bounce_source: bool = False  # "Return CARDNAME to its owner's hand": likewise (Rootha)
    tap_creatures: int = 0  # "Tap two untapped creatures you control": other creatures than the source (Harmonized Trio)
    life_identity: bool = False  # "Pay life equal to the number of colors in your commanders' color identity" (War Room)
    from_graveyard: bool = False  # the ability works from the graveyard ("Return this card from your graveyard ...")
    tap_legendary: bool = False  # ... and they have to be legendary (Relic of Legends)
    discard_hand: bool = False  # "Discard your hand" (Lion's Eye Diamond)
    discount_each: str = ""  # "This ability costs {1} less to activate for each legendary creature you control": that kind


_CREW = re.compile(r"Crew (\d+)")


# Station: Adagia, Kavaron and the other Planets. The abilities after it are written "12+ | <ability>".
_STATION = re.compile(r"Station")  # (Tap another creature you control: Put charge counters equal to its power on this Planet. Station only as a sorcery.)


def is_station_line(line: str) -> bool:
    return _STATION.fullmatch(line) is not None or (m := _THRESHOLD.fullmatch(line)) is not None and \
        _ACTIVATED.fullmatch(m[2]) is not None


_ACTIVATED = re.compile(r"([^:\"]+): (.+)")


_CHANNEL = re.compile(r"Channel \u2014 (.+)")


_ACTIVATION_DISCOUNT = re.compile(r" This ability costs \{1\} less to activate for each ([a-z ]+) you control\.")


def _channel_body(line: str) -> tuple[str, str]:
    """A channel land's line without the "Channel \u2014" word and the sentence that makes it cheaper, and what that sentence
    counts ("legendary creature"): (the rest of the line, the kind or "")."""
    if m := _CHANNEL.fullmatch(line):
        line = m[1]
    if m := _ACTIVATION_DISCOUNT.search(line):
        return line[:m.start()], m[1]
    return line, ""


_MANA_PART = re.compile(r"(\{(?:\d+|X|S|[WUBRGC]|[WUBRGC]/[WUBRGCP]|2/[WUBRGC])\})+")


_SACRIFICE_SELF = re.compile(rf"Sacrifice {_SELF}", re.I)


_PAY_LIFE_IDENTITY = re.compile(r"Pay life equal to the number of colors in your commanders?'s? color identity")


_PAY_LIFE = re.compile(rf"Pay {_N} life", re.I)


_CARDS = r"(an?|two|three|four)"


_SACRIFICE_OTHER = re.compile(r"Sacrifice (another|an?|two|three|four) (?:other )?(creature|(?:white|blue|black|red|green) creature|artifact|land|enchantment|permanent|artifact or creature|creature or artifact|Food|Treasure|Clue|[A-Z][a-z]+)s?")


_REMOVE_COUNTER_COST = re.compile(rf"Remove an? {_COUNTER} from (?:CARDNAME|this (?:creature|artifact|permanent|enchantment|land))")


_DISCARD_COST = re.compile(rf"Discard {_CARDS} cards?")


_DISCARD_SELF = re.compile(r"Discard (?:CARDNAME|this card)")


_TAP_CREATURES = re.compile(r"Tap (an?|two|three|four) untapped (legendary )?creatures? you control")


_DISCARD_HAND = re.compile(r"Discard your hand")


_EXILE_SELF = re.compile(r"Exile (?:CARDNAME|this (?:artifact|creature|permanent|enchantment|land))")


_BOUNCE_SELF = re.compile(r"Return (?:CARDNAME|this (?:artifact|creature|permanent|enchantment|land)) to its owner's hand")


_EXILE_COST = re.compile(rf"Exile {_CARDS} (?:(creature|artifact|land|instant|sorcery|enchantment) )?cards? from your graveyard")


_NUMBER = {"a": 1, "an": 1, "two": 2, "three": 3, "four": 4}


_LOYALTY = re.compile(r"([+\u2212-]?)(\d+)")


_SORCERY_ONLY = "Activate only as a sorcery."


_ONCE_EACH_TURN = "Activate only once each turn."


_INSTANT_ONLY = "Activate only as an instant."  # what every ability without a timing restriction is already


_ACTIVATE_ONLY_IF = re.compile(r"Activate only (as a sorcery and only )?if (.+)\.")


@lru_cache(maxsize=None)
def activated_abilities(card: Card) -> tuple[ActivatedAbility, ...]:
    """Activated abilities ("{1}, {T}, Sacrifice this artifact: Draw a card.") whose
    costs and effects are all understood. Mana abilities are handled by mana_ability."""
    planeswalker = "Planeswalker" in card.type_line
    abilities = []
    for line in rules_lines(card):
        if m := _CREW.fullmatch(line):  # a Vehicle: tap creatures and it becomes an artifact creature this turn
            abilities.append(ActivatedAbility(line, (BecomeCreature(),), crew=int(m[1])))
            continue
        if _STATION.fullmatch(line):  # Station: tap another creature, charge counters equal to its power, at sorcery speed
            abilities.append(ActivatedAbility(line, (DefineX(Amount("tapped_power")), PutCountersOnSource("X", "charge")),
                                              sorcery_speed=True, tap_creatures=1))
            continue
        body, discount = _channel_body(line)  # Channel \u2014 {1}{G}, Discard this card: ... (Boseiju)
        threshold = _THRESHOLD.fullmatch(body)  # "12+ | {1}{R}, {T}: ...": only with that many charge counters on it
        match = _ACTIVATED.fullmatch(threshold[2] if threshold else body)
        if not match or is_mana_ability(line):
            continue
        ability = _parse_activated(threshold[2] if threshold else body, match[1], match[2], planeswalker)
        if ability is not None and body != line:
            ability = dataclasses.replace(ability, text=line, discount_each=discount)
        if ability is not None and threshold:
            at_least = Condition("source_counters_at_least", int(threshold[1]), "charge", also=ability.condition)
            ability = dataclasses.replace(ability, text=line, condition=at_least)
        if ability is not None:
            abilities.append(ability)
    if equips := equip_abilities(card):
        abilities.extend(equips)
    elif (other := _equip_other_cost(card)) is not None:
        abilities.append(other)
    if cost := reconfigure_cost(card):
        abilities.append(ActivatedAbility(f"Reconfigure {cost}", (Attach(another=True),), mana_cost=cost,
                                          sorcery_speed=True, reconfigure="attach"))
        abilities.append(ActivatedAbility(f"Reconfigure {cost} (unattach)", (Unattach(),), mana_cost=cost,
                                          sorcery_speed=True, reconfigure="unattach"))
    return tuple(abilities)


def hand_abilities(card: Card) -> tuple[ActivatedAbility, ...]:
    """The activated abilities a card has in your hand: those whose cost discards it (Magma Opus)."""
    return tuple(a for a in activated_abilities(card) if a.discard_self)


def _cost_fields(cost: str) -> dict[str, Any] | None:
    """The fields of an ActivatedAbility that a cost sets ("{1}, {T}, Pay 2 life"), or None if any part isn't understood."""
    fields: dict[str, Any] = {}
    for part in cost.split(", "):
        if _MANA_PART.fullmatch(part):
            fields["mana_cost"] = fields.get("mana_cost", "") + part
        elif part == "{T}":
            fields["tap"] = True
        elif _SACRIFICE_SELF.fullmatch(part):
            fields["sacrifice"] = True
        elif (m := _PAY_LIFE.fullmatch(part)) and m[1] != "X":
            fields["life"] = _count(m[1])
        elif _PAY_LIFE_IDENTITY.fullmatch(part):
            fields["life_identity"] = True
        elif m := _SACRIFICE_OTHER.fullmatch(part):
            fields.update(sacrifice_other=m[2], sacrifice_another=m[1] == "another" or " other " in part, sacrifice_count=_NUMBER.get(m[1], 1))
        elif m := _DISCARD_COST.fullmatch(part):
            fields["discard"] = _NUMBER[m[1]]
        elif _DISCARD_SELF.fullmatch(part):
            fields["discard_self"] = True
        elif m := _TAP_CREATURES.fullmatch(part):
            fields["tap_creatures"] = _NUMBER[m[1]]
            fields["tap_legendary"] = m[2] is not None
        elif _DISCARD_HAND.fullmatch(part):
            fields["discard_hand"] = True  # Lion's Eye Diamond
        elif _EXILE_SELF.fullmatch(part):
            fields["exile_source"] = True
        elif _BOUNCE_SELF.fullmatch(part):
            fields["bounce_source"] = True
        elif m := _EXILE_COST.fullmatch(part):
            fields.update(exile_graveyard=_NUMBER[m[1]], exile_graveyard_kind=m[2] or "")
        elif m := _REMOVE_COUNTER_COST.fullmatch(part):
            fields["remove_counter"] = _counter_name(m[1])
        else:
            return None
    return fields


def _parse_activated(line: str, cost: str, effect: str, planeswalker: bool) -> ActivatedAbility | None:
    fields: dict[str, Any] = {}
    loyalty = _LOYALTY.fullmatch(cost)
    if planeswalker and loyalty:
        amount = int(loyalty[2])
        fields.update(loyalty=-amount if loyalty[1] in ("\u2212", "-") else amount, sorcery_speed=True)
    elif (paid := _cost_fields(cost)) is None:
        return None
    else:
        fields.update(paid)
    if _MODAL_INLINE.fullmatch(effect):
        effects = _parse_modal_inline(effect)
        return ActivatedAbility(line, tuple(effects), **fields) if effects else None
    sentences = _split_sentences(effect)
    if _SORCERY_ONLY in sentences:
        fields["sorcery_speed"] = True
        sentences.remove(_SORCERY_ONLY)
    if _ONCE_EACH_TURN in sentences:
        fields["once_per_turn"] = True
        sentences.remove(_ONCE_EACH_TURN)
    if _INSTANT_ONLY in sentences:
        sentences.remove(_INSTANT_ONLY)
    for sentence in list(sentences):
        if m := _ACTIVATE_ONLY_IF.fullmatch(sentence):
            if (condition := _condition(m[2])) is None:
                return None
            fields.update(condition=condition, sorcery_speed=fields.get("sorcery_speed", False) or bool(m[1]))
            sentences.remove(sentence)
    effects = _parse(sentences)
    if not effects:
        return None
    if any(isinstance(e, ReturnThisFromGraveyard) for e in effects):
        fields["from_graveyard"] = True
    if any(isinstance(e, LevelUp) for e in effects):
        fields["sorcery_speed"] = True
    if any(getattr(e, "needs_exiled_with", False) for e in effects):
        fields["condition"] = Condition("has_exiled_with")
    if fields.get("condition") and any(isinstance(e, AddMana) for e in effects):
        return None  # a conditional mana ability (Temple of the False God) isn't a stack ability: auto-pay couldn't use it
    return ActivatedAbility(line, tuple(effects), **fields)
