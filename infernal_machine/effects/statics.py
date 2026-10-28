"""Rules text that is always on: static abilities, replacement effects, protection, restrictions, grants."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ..cards import Card
from ..characteristics import Modifier

from .common import (
    CANT_ATTACK,
    CANT_BE_BLOCKED,
    CANT_BLOCK,
    MUST_ATTACK,
    PROTECTION,
    PROTECTION_CHOSEN,
    _COLOR_LETTER,
    _COUNTER,
    _KEYWORDS,
    _KEYWORDS_BARE,
    _KW,
    _LAND_TYPE,
    _N,
    _N_FIXED,
    _NUM,
    _PT,
    _SELF,
    _WARD_MANA,
    _count,
    _number,
    _counter_name,
    _keyword_list,
    _modifier,
    _protection_keywords,
    _signed,
    protection_tokens,
    rules_lines,
)
from .outcomes import Amount, Condition, CopyChanges, EntersTapped, _copy_changes, _CLASS_LEVEL_LINE, _ENCHANT, _amount, _condition
from .activated import ActivatedAbility, _ACTIVATED, _cost_fields, _parse_activated
from .triggers import _ABILITY_WORD
from .mana import _ADD_ANY, _ADD_EITHER, _ADD_SYMBOLS, _mana_from_line, is_mana_ability


_ENTERS_WITH = re.compile(rf"{_SELF} enters (?:tapped )?with (twice X|{_N}) {_COUNTER} on it\.", re.I)


_ESCAPES_WITH = re.compile(rf"{_SELF} escapes with {_N_FIXED} {_COUNTER} on it\.", re.I)  # Woe Strider


_IF_KICKED = re.compile(rf"if {_SELF} was kicked, ", re.I)


_IF_BLOODTHIRSTY = re.compile(r"if an opponent was dealt damage this turn, ", re.I)  # Bloodthirst
_IF_ATTACKED = re.compile(r" if you attacked this turn\.$", re.I)  # Raid: "This creature enters with a +1/+1 counter on it if you attacked this turn."


_ENTERS_PER_KICK = re.compile(rf"{_SELF} enters with an? {_COUNTER} on it for each time it was kicked\.", re.I)


def enters_with_counters(card: Card, kicked: int = 0, escaped: bool = False, bloodthirsty: bool = False,
                         raided: bool = False) -> dict[str, int | str]:
    """Counters from "This creature enters with N (or X) +1/+1 counters on it.", plus, when `kicked` (the number
    of times), "If this creature was kicked, it enters with N +1/+1 counters on it." and multikicker's
    "... enters with a +1/+1 counter on it for each time it was kicked."; and, when `bloodthirsty`, "If an opponent
    was dealt damage this turn, this creature enters with N +1/+1 counters on it."; and, when `raided` (the controller attacked
    this turn), "This creature enters with N +1/+1 counters on it if you attacked this turn." """
    counters: dict[str, int | str] = {}

    def add(name: str, number: int) -> None:
        held = counters.get(name, 0)
        assert isinstance(held, int)  # "X" and "2X" stand alone
        counters[name] = held + number

    for line in rules_lines(card):
        if b := _IF_BLOODTHIRSTY.match(line):
            if not bloodthirsty:
                continue
            line = line[b.end():]
        if r := _IF_ATTACKED.search(line):
            if not raided:
                continue
            line = _ABILITY_WORD.sub("", line[:r.start()] + ".")  # "Raid — ": the word only labels the condition
        if kicked and (k := _IF_KICKED.match(line)):
            line = line[k.end():]
        if m := _ENTERS_WITH.fullmatch(line):
            name = _counter_name(m[3])
            count = "2X" if m[1].lower() == "twice x" else _count(m[2])  # "2X": twice the X paid
            if isinstance(count, int):
                add(name, count)
            else:
                counters[name] = count
        elif escaped and (m := _ESCAPES_WITH.fullmatch(line)):
            name = _counter_name(m[2])
            add(name, _number(m[1]))
        elif kicked and (m := _ENTERS_PER_KICK.fullmatch(line)):
            name = _counter_name(m[1])
            add(name, kicked)
    return counters


def is_enters_with_counters(line: str) -> bool:
    if k := _IF_KICKED.match(line) or _IF_BLOODTHIRSTY.match(line):
        line = line[k.end():]
    if r := _IF_ATTACKED.search(line):
        line = _ABILITY_WORD.sub("", line[:r.start()] + ".")
    return (_ENTERS_WITH.fullmatch(line) is not None or _ENTERS_PER_KICK.fullmatch(line) is not None
            or _ESCAPES_WITH.fullmatch(line) is not None)


@lru_cache(maxsize=None)
def printed_protection(card: Card) -> frozenset[str]:
    """What a card has protection from (color letters, card types, "everything") by its own keyword line, such as
    "Flying, protection from red and from blue". An ability that gives protection to something
    else ("Equipped creature has protection from red") doesn't count."""
    letters: set[str] = set()
    for line in rules_lines(card):
        if PROTECTION.search(line) and re.fullmatch(rf"{_KW}(?:, {_KW})*", line, re.I):
            for keyword in _protection_keywords(line):
                letters |= protection_tokens(keyword)
    return frozenset(letters)


_WARD = re.compile(rf"(?:^|, )ward ({_WARD_MANA})(?:,|$)", re.I)


_WARD_DASH = re.compile(r"ward\u2014(.+?)\.?", re.I)  # "Ward\u2014Pay 3 life."


def ward_fields(cost: str) -> dict[str, Any] | None:
    """A ward cost as the fields of an activated ability's cost: only mana, life, discarding and sacrificing."""
    fields = _cost_fields(cost[:1].upper() + cost[1:])  # the report reads lowercased text
    if fields is None or any(fields.get(key) for key in ("tap", "sacrifice", "exile_graveyard", "tap_creatures", "exile_source",
                                                         "bounce_source", "life_identity")):
        return None
    if fields.get("discard", 0) > 1 or fields.get("sacrifice_count", 1) > 1:  # ward pays one card or permanent
        return None
    return fields


@lru_cache(maxsize=None)
def ward_cost(card: Card) -> str | None:
    """The cost of ward: "{2}" for "Ward {2}", or "Pay 3 life" for "Ward\u2014Pay 3 life." (or None)."""
    for line in rules_lines(card):
        if m := _WARD.search(line):
            return m[1]
        if (m := _WARD_DASH.fullmatch(line)) and ward_fields(m[1]) is not None:
            return m[1]
    return None


def is_ward_line(text: str) -> bool:
    return (re.fullmatch(rf"ward {_WARD_MANA}", text, re.I) is not None
            or ((m := _WARD_DASH.fullmatch(text)) is not None and ward_fields(m[1]) is not None))


_ATTACK_TAX = re.compile(r"Each creature with one or more counters on it can't attack you or planeswalkers you control unless "
                         r"its controller pays \{X\}, where X is the number of counters on that creature\.")


@lru_cache(maxsize=None)
def attack_tax_per_counter(card: Card) -> int:
    """Nils, Discipline Enforcer: how many times the card taxes each counter on a creature that attacks its controller."""
    return sum(_ATTACK_TAX.fullmatch(line) is not None for line in rules_lines(card))


def is_attack_tax_line(line: str) -> bool:
    return _ATTACK_TAX.fullmatch(line) is not None or _attack_tax(line) is not None


@dataclass(frozen=True)
class AttackTax:
    """What each creature that attacks this card's controller costs its controller: the `cost` ({2}, {W/P}), or `amount` generic mana
    when the cost is {X} and X is a count the card's controller works out ("the number of enchantments you control")."""
    cost: str = ""
    amount: Amount | None = None


_FLAT_ATTACK_TAX = re.compile(r"Creatures can't attack you(?: or planeswalkers you control)? unless their controller pays "
                              r"(\{\d+\}|\{[WUBRG]/P\}|\{X\}) for each (?:creature they control that's attacking you(?: or planeswalkers you control)?"
                              r"|of those creatures)(?:, where X is (.+))?\.")


def _attack_tax(line: str) -> AttackTax | None:
    """The tax a "Creatures can't attack you unless their controller pays ..." line sets, or None if it isn't one we understand."""
    if not (m := _FLAT_ATTACK_TAX.fullmatch(line)):
        return None
    if m[1] == "{X}":
        amount = _amount(m[2]) if m[2] else None
        return AttackTax(amount=amount) if amount is not None else None
    return AttackTax(cost=m[1]) if not m[2] else None


def attack_taxes(card: Card) -> list[AttackTax]:
    """Ghostly Prison, Baird, Norn's Annex, Sphere of Safety: the tax on each creature attacking the card's controller."""
    return [tax for line in rules_lines(card) if (tax := _attack_tax(line)) is not None]


@dataclass(frozen=True)
class CombatRestriction:
    """A static ability that limits who attacks or blocks: `kind` is "no_attack_tribe" (Inklings can't attack you),
    "no_attack_enchanted" (creatures enchanted by an Aura you control can't attack you), "block_only_flying" (Brazen Borrower)
    or "weaker_cant_block" (Elusive Otter: creatures with less power can't block it). The blocking ones take a creature test
    in `what` ("power<=2", "type:Artifact", "color:U", "keyword:flying"): "not_blocked_by" (can't be blocked by creatures that
    pass it), "only_blocked_by" (can't be blocked except by creatures that pass it), "cant_block" (can't block attackers that pass
    it); and a number in `what`: "max_blockers" (can't be blocked by more than N creatures), "min_blockers" (can't be blocked
    except by N or more creatures)."""
    kind: str
    what: str = ""  # the creature type for "no_attack_tribe"


_COLORS = "|".join(_COLOR_LETTER)


def _power_test(m: re.Match, first: int) -> str:
    return f"power{'<=' if m[first + 1].lower() == 'less' else '>='}{m[first]}"


_COMBAT_RESTRICTIONS = [
    (re.compile(rf"{_SELF} can't be blocked by creatures with power (\d+) or (less|greater)\.", re.I),
     lambda m: CombatRestriction("not_blocked_by", _power_test(m, 1))),
    (re.compile(rf"{_SELF} can't be blocked by (artifact creatures|Walls)\.", re.I),
     lambda m: CombatRestriction("not_blocked_by", "type:" + ("Artifact" if m[1].lower().startswith("a") else "Wall"))),
    (re.compile(rf"{_SELF} can't be blocked by ({_COLORS}) creatures\.", re.I),
     lambda m: CombatRestriction("not_blocked_by", "color:" + _COLOR_LETTER[m[1].lower()])),
    (re.compile(rf"{_SELF} can't be blocked by creatures with flying\.", re.I),
     lambda m: CombatRestriction("not_blocked_by", "keyword:flying")),
    (re.compile(rf"{_SELF} can't be blocked except by ({_COLORS}) creatures\.", re.I),
     lambda m: CombatRestriction("only_blocked_by", "color:" + _COLOR_LETTER[m[1].lower()])),
    (re.compile(rf"{_SELF} can't be blocked except by creatures with flying\.", re.I),
     lambda m: CombatRestriction("only_blocked_by", "keyword:flying")),
    (re.compile(rf"{_SELF} can't block creatures with power (\d+) or (less|greater)\.", re.I),
     lambda m: CombatRestriction("cant_block", _power_test(m, 1))),
    (re.compile(r"All creatures able to block (?:this creature|CARDNAME) do so\.", re.I),
     lambda m: CombatRestriction("all_must_block")),
    (re.compile(r"All creatures able to block (?:enchanted|equipped) creature do so\.", re.I),
     lambda m: CombatRestriction("host_must_be_blocked_by_all")),  # Lure, Nemesis Mask
    (re.compile(rf"{_SELF} must be blocked if able\.", re.I), lambda m: CombatRestriction("must_be_blocked")),
    (re.compile(rf"{_SELF} can't be blocked by more than {_NUM} creatures?\.", re.I),
     lambda m: CombatRestriction("max_blockers", str(_number(m[1])))),
    (re.compile(rf"{_SELF} can't be blocked except by {_NUM} or more creatures\.", re.I),
     lambda m: CombatRestriction("min_blockers", str(_number(m[1])))),
    (re.compile(r"((?-i:[A-Z][a-z]+))s can't attack you or planeswalkers you control\.", re.I),
     lambda m: CombatRestriction("no_attack_tribe", m[1])),
    (re.compile(r"Each creature that's enchanted by an Aura you control can't attack you or planeswalkers you control\."),
     lambda m: CombatRestriction("no_attack_enchanted")),
    (re.compile(rf"{_SELF} can block only creatures with flying\.", re.I), lambda m: CombatRestriction("block_only_flying")),
    (re.compile(rf"Creatures with power less than {_SELF}'s power can't block it\.|"
                r"Creatures with power less than this creature's power can't block it\.", re.I),
     lambda m: CombatRestriction("weaker_cant_block")),
]


_BASIC_LAND_TYPES = "Swamp|Forest|Island|Mountain|Plains"


_RULES_STATICS = [
    (re.compile(r"Your opponents can't cast spells during your turn\.", re.I), "opp_no_cast:turn"),
    (re.compile(r"Your opponents can't cast spells during combat\.", re.I), "opp_no_cast:combat"),
    (re.compile(r"During your turn, your opponents can't cast spells or activate abilities of artifacts, creatures, or enchantments\.", re.I),
     "opp_no_cast:turn|opp_lock:Artifact,Creature,Enchantment"),
    (re.compile(r"Each player can't cast more than one spell each turn\.", re.I), "one_spell:each"),
    (re.compile(r"You can't cast more than one spell each turn\.", re.I), "one_spell:you"),
    (re.compile(r"You can't cast (creature|noncreature) spells\.", re.I), "no_cast_kind"),
    (re.compile(r"Activated abilities of artifacts can't be activated\.", re.I), "lock:Artifact"),
    (re.compile(r"Creature spells you control can't be countered\.", re.I), "uncounterable:creature"),
    (re.compile(r"Spells you control can't be countered\.", re.I), "uncounterable:spell"),
    (re.compile(r"You may cast (spells|creature spells|sorcery spells|Spirit spells) as though they had flash\.", re.I), "flash"),
    (re.compile(rf"Each land is an? ({_BASIC_LAND_TYPES}) in addition to its other land types\.", re.I), "land_type"),
    (re.compile(r"Lands you control are every basic land type in addition to their other types\.", re.I), "land_type:all_yours"),
    (re.compile(r"You may play (an|two|three) additional lands? on each of your turns\.", re.I), "extra_land"),
    (re.compile(r"You may play lands from your graveyard\.", re.I), "graveyard_lands"),
    (re.compile(r"Untap all permanents you control during each other player's untap step\.", re.I), "untap_others"),  # Seedborn Muse
    (re.compile(r"Untap all artifacts you control during each other player's untap step\.", re.I), "untap_others:artifact"),  # Unwinding Clock
    (re.compile(rf"Untap (?:{_SELF}|this artifact) during each other player's untap step\.", re.I), "untap_others:self"),  # Bender's Waterskin
    (re.compile(r"(Creatures|Artifacts and creatures) your opponents control enter tapped\.", re.I), "enter_tapped:opp"),  # Authority of the Consuls
    (re.compile(r"You may look at the top card of your library any time\.", re.I), "look_top"),  # information only: nothing changes
    (re.compile(r"Umbra armor", re.I), "umbra_armor"),  # Auras: an enchanted creature that would be destroyed is saved by one
    (re.compile(rf"{_SELF} doesn't untap during your untap step\.", re.I), "no_untap"),  # Basalt Monolith, Mana Vault
]


_LAND_TYPE_MANA = {"swamp": "B", "forest": "G", "island": "U", "mountain": "R", "plains": "W"}


@lru_cache(maxsize=None)
def rules_statics(card: Card) -> tuple[str, ...]:
    """What a permanent's static rules-changing abilities do, as keys: "opp_no_cast:turn" / ":combat" (its controller's opponents
    can't cast spells during its controller's turn / during combat), "opp_lock:Artifact,Creature,Enchantment" (on its controller's
    turn their abilities of those can't be activated), "one_spell:each" / ":you" (one spell a turn), "no_cast_kind:creature" /
    ":noncreature" (its controller can't cast those), "lock:Artifact" (nobody can activate abilities of those), "uncounterable:spell"
    / ":creature" (its controller's), "flash:spell" / ":creature" / ":sorcery" / ":Spirit" (its controller may cast those at instant
    speed), "land_type:B" (every land taps for that color: Urborg), "land_type:all_yours" (its controller's lands tap for any basic),
    "extra_land" (its controller may play one more land a turn), "graveyard_lands" (its controller may play lands from the graveyard),
    "no_untap" (it stays tapped through its controller's untap step), "umbra_armor" (an Aura that saves what it enchants from being destroyed), "untap_others" (its controller's permanents untap in every other player's untap step; ":artifact" its artifacts, ":self" it
    alone), "enter_tapped:opp:creature" / ":artifact,creature" (those its controller's opponents control enter tapped), "look_top" (its controller may look at their top card: no
    change to the game, and no player here uses it)."""
    found = []
    for line in rules_lines(card):
        for pattern, key in _RULES_STATICS:
            if m := pattern.fullmatch(line):
                if key == "no_cast_kind":
                    key = f"no_cast_kind:{m[1].lower()}"
                elif key == "flash":
                    key = "flash:" + ("spell" if m[1].lower() == "spells" else m[1].lower().removesuffix(" spells"))
                elif key == "land_type":
                    key = f"land_type:{_LAND_TYPE_MANA[m[1].lower()]}"
                elif key == "enter_tapped:opp":
                    key += ":creature" if m[1].lower() == "creatures" else ":artifact,creature"
                elif key == "extra_land":  # Azusa: two additional lands, which is two more land drops
                    key = "|".join(["extra_land"] * {"an": 1, "two": 2, "three": 3}[m[1].lower()])
                found.extend(key.split("|"))
    return tuple(found)


def is_rules_static_line(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern, _ in _RULES_STATICS)


_PREVENTION_STATICS = [
    (re.compile(rf"Prevent all damage that would be dealt to {_SELF}\.", re.I), "self:all"),
    (re.compile(rf"Prevent all combat damage that would be dealt to {_SELF}\.", re.I), "self:combat"),
    (re.compile(rf"Prevent all damage that would be dealt to {_SELF} by creatures\.", re.I), "self:creatures"),
    (re.compile(r"Prevent all damage that would be dealt to you\.", re.I), "you:all"),
    (re.compile(r"Damage can't be prevented\.", re.I), "unpreventable"),
    (re.compile(rf"Damage that would be dealt by {_SELF} can't be prevented\.", re.I), "unpreventable:self"),
]


@lru_cache(maxsize=None)
def damage_prevention(card: Card) -> frozenset[str]:
    """What a permanent's own text prevents or stops from being prevented: "self:all", "self:combat", "self:creatures" (damage dealt
    to it), "you:all" (to its controller), "unpreventable" (nobody's damage can be prevented), "unpreventable:self" (its own)."""
    return frozenset(key for line in rules_lines(card) for pattern, key in _PREVENTION_STATICS if pattern.fullmatch(line))


def is_prevention_line(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern, _ in _PREVENTION_STATICS)


@lru_cache(maxsize=None)
def combat_restrictions(card: Card) -> tuple[CombatRestriction, ...]:
    found = []
    for line in rules_lines(card):
        for pattern, build in _COMBAT_RESTRICTIONS:
            if m := pattern.fullmatch(line):
                found.append(build(m))
    return tuple(found)


def is_combat_restriction_line(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern, _ in _COMBAT_RESTRICTIONS)


_QUEST_UNTAP = re.compile(r"As long as there are (\w+) or more (\w+) counters on this enchantment, untap all creatures you "
                          r"control during each other player's untap step\.")


_ALWAYS_UNTAP = re.compile(r"Untap all creatures you control during each other player's untap step\.")  # Drumbellower


@lru_cache(maxsize=None)
def untaps_in_other_untap_steps(card: Card) -> tuple[str, int] | None:
    """Quest for Renewal: (the counter, how many of it) while which your creatures untap in everyone's untap step.
    Drumbellower does it always: ("", 0), which any permanent satisfies."""
    for line in rules_lines(card):
        if m := _QUEST_UNTAP.fullmatch(line):
            return m[2], _number(m[1])
        if _ALWAYS_UNTAP.fullmatch(line):
            return "", 0
    return None


def is_quest_untap_line(line: str) -> bool:
    return _QUEST_UNTAP.fullmatch(line) is not None or _ALWAYS_UNTAP.fullmatch(line) is not None


_ANNIHILATOR = re.compile(r"Annihilator (\d+)", re.I)


@lru_cache(maxsize=None)
def annihilator_of(card: Card) -> int:
    """The N of the card's own "Annihilator N" keyword lines."""
    return sum(int(m[1]) for line in rules_lines(card) for part in line.split(", ") if (m := _ANNIHILATOR.fullmatch(part)))


_TOXIC = re.compile(r"Toxic (\d+)", re.I)


@lru_cache(maxsize=None)
def toxic_of(card: Card) -> int:
    """The N of the card's own "Toxic N" keywords; each one gives that many poison counters."""
    return sum(int(m[1]) for line in rules_lines(card) for part in line.split(", ") if (m := _TOXIC.fullmatch(part)))


@lru_cache(maxsize=None)
def day_night_face(card: Card) -> str | None:
    """"day" for a card with Daybound, "night" for one with Nightbound (a permanent that flips with the day/night rule)."""
    lines = rules_lines(card)
    return "day" if "Daybound" in lines else "night" if "Nightbound" in lines else None


_DREDGE = re.compile(r"Dredge (\d+)", re.I)


@lru_cache(maxsize=None)
def dredge_of(card: Card) -> int | None:
    """The N of the card's own "Dredge N" keyword: from the graveyard it may replace a draw by milling N cards."""
    return next((int(m[1]) for line in rules_lines(card) if (m := _DREDGE.fullmatch(line))), None)


@lru_cache(maxsize=None)
def graveyard_statics(card: Card) -> bool:
    """Whether the card has a static ability that works from the graveyard ("As long as this card is in your graveyard ...")."""
    return any(b.condition is not None and b.condition.kind == "in_graveyard"
               or b.condition is not None and b.condition.also is not None and b.condition.also.kind == "in_graveyard"
               for b in static_abilities(card))


@dataclass(frozen=True)
class StaticBuff:
    """ "(Other) (Elf) creatures you control get +1/+1 (and have flying)." while its source is on the battlefield."""
    modifier: Modifier
    other: bool  # "Other ...": not the source itself
    subtype: str | None  # "Elf" in "Other Elf creatures you control"
    text: str
    self_only: bool = False  # "CARDNAME gets +1/+1 as long as ...": only the source itself
    condition: "Condition | None" = None  # "As long as you control an artifact, ...": applies only while it holds
    color: str | None = None  # "Other red creatures you control": a color letter
    attacking: bool = False  # "Attacking Pests you control": only while they are attacking
    per: tuple[str, str] | None = None  # "... for each artifact you control": (what to count, its type); see Game.modifiers
    everyone: bool = False  # "White creatures get +1/+1": every player's, not just its controller's
    token: bool = False  # "Creature tokens you control have haste": only tokens
    with_counters: bool = False  # "Creatures you control with counters on them have trample"
    plus_counter: bool = False  # "Each creature you control with a +1/+1 counter on it has vigilance": that counter only
    permanents: bool = False  # "Other permanents you control have indestructible": any permanent, not only creatures (Avacyn)
    opponents: bool = False  # "Creatures your opponents control get -2/-2" (Elesh Norn): only the other players' creatures


_CHOOSE_TYPE = re.compile(r"As (?:CARDNAME|this [a-z]+) enters, choose a creature type\.")


@lru_cache(maxsize=None)
def chooses_creature_type(card: Card) -> bool:
    """Patchwork Banner: "As this artifact enters, choose a creature type." """
    return any(_CHOOSE_TYPE.fullmatch(line) for line in rules_lines(card))


def is_choose_type_line(line: str) -> bool:
    return _CHOOSE_TYPE.fullmatch(line) is not None


_CHOSEN_SELF = re.compile(r"This (?:creature|artifact|enchantment|land) is the chosen type in addition to its other types\.")


def is_chosen_self_line(line: str) -> bool:
    return _CHOSEN_SELF.fullmatch(line) is not None


@lru_cache(maxsize=None)
def is_chosen_type_itself(card: Card) -> bool:
    """Roaming Throne, Metallic Mimic, Adaptive Automaton: it is also the creature type it chose as it entered."""
    return any(_CHOSEN_SELF.fullmatch(line) for line in rules_lines(card))


_AFFECTED = (r"(?:Other c|C)reatures you control of the chosen (?:type|color)|Creatures of the chosen type|Creatures your opponents control"
             r"|(?:Other )?permanents you control|Creature tokens you control|Creatures you control with counters on them|Each creature you control with a \+1/\+1 counter on it|(?:Other )?(?:Attacking )?(?:(?:white|blue|black|red|green) )?(?:[A-Z][\w'-]* )?[Cc]reatures you control"
             r"|(?:Other |Attacking )?[A-Z][\w'-]*s(?: and [A-Z][\w'-]*s)? you control|Other [A-Z][\w'-]*s|(?:White|Blue|Black|Red|Green) creatures")


_COMMANDER_SCALED = re.compile(rf"({_AFFECTED}) get {_PT} for each time you've cast your commander from the command zone "
                               r"this game\.")


_COUNTER_SCALED = re.compile(rf"({_AFFECTED}) get {_PT} for each ([a-z]+) counter on (?:this artifact|CARDNAME|this creature)\.")  # Door of Destinies


_STATIC = re.compile(rf"({_AFFECTED}) (?:get {_PT}(?: and have {_KEYWORDS})?|(?:have|has) {_KEYWORDS})\.")


_AFFECTED_WHO = re.compile(r"(?P<chosen>(?P<other_chosen>Other c|C)reatures (?:you control )?of the chosen (?P<chosen_what>type|color))"
                  r"|(?P<opps>Creatures your opponents control)|(?P<perms>(?P<other_perms>Other )?permanents you control)|(?P<tokens>Creature tokens you control)|(?P<counters>Creatures you control with counters on them)|(?P<plus>Each creature you control with a \+1/\+1 counter on it)|(?P<other>Other )?(?P<attacking>Attacking )?(?:(?P<color>white|blue|black|red|green) )?"
                  r"(?:(?P<sub>[A-Z][\w'-]*) )?[Cc]reatures you control"
                  r"|(?P<other2>Other )?(?P<attacking2>Attacking )?(?P<tribe>[A-Z][\w'-]*)s(?: and (?P<tribe2>[A-Z][\w'-]*)s)? you control"
                  r"|(?P<other3>Other )(?P<tribe3>[A-Z][\w'-]*)s"  # Goblin King, Lord of Atlantis: every player's, not only its controller's
                  r"|(?P<global>White|Blue|Black|Red|Green) creatures")


_PER = {"artifact you control": ("permanent", "artifact"), "creature you control": ("permanent", "creature"),
        "Aura you control": ("permanent", "Aura"), "creature card in your graveyard": ("graveyard", "creature"),
        "Aura attached to it": ("auras_on_it", ""), "Aura you control that's attached to a creature": ("auras_on_creatures", ""),
        "land you control": ("permanent", "land"), "artifact and/or enchantment you control": ("permanent", "artifact or enchantment"),
        "color among permanents you control": ("colors", "")}  # Faeburrow Elder


_PER_LOWER = {k.lower(): v for k, v in _PER.items()}


_PER_WORDS = "|".join(re.escape(k) for k in _PER)


_SELF_SCALED = re.compile(rf"{_SELF} gets {_PT} for each ({_PER_WORDS})\.", re.I)


# Eidolon of Countless Battles: both the creature and the one it enchants, for two counts added together.
_BOTH_SCALED = re.compile(rf"This creature and enchanted creature each get {_PT} for each creature you control and {_PT} "
                          r"for each Aura you control\.")


_ATTACHED_SCALED = re.compile(rf"(?:Enchanted|Equipped) creature gets {_PT} for each ({_PER_WORDS})\.")


# Whispersilk Cloak, Aqueous Form: "can't be blocked" (a pseudo-keyword the combat code asks for), perhaps with real keywords too.
_ATTACHED_UNBLOCKABLE = re.compile(rf"(?:Enchanted|Equipped) creature can't be blocked(?: and has ({_KEYWORDS_BARE}))?\.")


_ATTACHED_TYPED = re.compile(rf"Enchanted creature gets {_PT}, has ({_KW}(?: and {_KW})*), and is an? ([A-Z][a-z]+) in addition "
                             r"to its other types\.")


_ATTACHED_GOADED = re.compile(rf"Enchanted creature gets {_PT}(?:, has ({_KW}),)? and is goaded\.")


_CANT = re.compile(rf"{_SELF} can't (attack or block|attack|block|be blocked|block and can't be blocked)\.", re.I)


_MUST_ATTACK = re.compile(rf"{_SELF} attacks each combat if able\.", re.I)


_SELF_STATIC = re.compile(rf"{_SELF} (?:gets {_PT}(?: and has {_KEYWORDS})?|has {_KEYWORDS})\.", re.I)


_AS_LONG_AS_FIRST = re.compile(r"As long as (.+?), (.+\.)")


_AS_LONG_AS_LAST = re.compile(r"(.+?) as long as (.+)\.")


def _conditional(line: str) -> tuple[str, str] | None:
    """Split "As long as X, Y." or "Y as long as X." into (Y with its full stop, X)."""
    if m := _AS_LONG_AS_FIRST.fullmatch(line):
        return m[2], m[1]
    if m := _AS_LONG_AS_LAST.fullmatch(line):
        return m[1] + ".", m[2]
    return None


def _other(who: re.Match) -> bool:
    """Whether the creatures a static ability affects exclude its source: "Other creatures ..."."""
    return who["other"] is not None or (who["other_chosen"] or "").startswith("O") or who["other_perms"] is not None or who["other2"] is not None or who["other3"] is not None


def _who_subtype(who: re.Match) -> str | None:
    """The creature type a static ability affects: "Elf" in "Other Elf creatures", or "Wolf|Werewolf" for "Wolves and Werewolves" (any of them)."""
    if who["sub"]:
        return who["sub"]
    kinds = [t[:-2] + "f" if t.endswith("ve") else t for t in (who["tribe"], who["tribe2"], who["tribe3"]) if t]  # Wolves -> Wolf
    return "|".join(kinds) or None


@lru_cache(maxsize=None)
def static_abilities(card: Card) -> tuple[StaticBuff, ...]:
    buffs = []
    for line in rules_lines(card):
        bare = _ABILITY_WORD.sub("", line)  # "Threshold — ": the word names the condition but changes nothing
        sentence, condition = bare, None
        if split := _conditional(bare):
            sentence, text = split
            if (condition := _condition(text)) is None:
                continue
        if m := _STATIC.fullmatch(sentence):
            who = _AFFECTED_WHO.fullmatch(m[1])
            assert who is not None  # _AFFECTED_WHO describes the same phrases as _AFFECTED
            colors = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
            chosen_color = bool(who["chosen"]) and who["chosen_what"] == "color"
            buffs.append(StaticBuff(_modifier(m, 2), _other(who),
                                    "chosen" if who["chosen"] and not chosen_color else _who_subtype(who), line,
                                    condition=condition,
                                    color="chosen" if chosen_color else colors.get((who["color"] or who["global"] or "").lower()),
                                    attacking=bool(who["attacking"] or who["attacking2"]), everyone=bool(who["global"]) or bool(who["other3"]) or (bool(who["chosen"]) and "you control" not in m[1]),
                                    token=bool(who["tokens"]),
                                    with_counters=bool(who["counters"]), plus_counter=bool(who["plus"]),
                                    permanents=bool(who["perms"]), opponents=bool(who["opps"])))
        elif m := _COUNTER_SCALED.fullmatch(sentence):  # Door of Destinies: +1/+1 for each charge counter on it
            who = _AFFECTED_WHO.fullmatch(m[1])
            assert who is not None
            buffs.append(StaticBuff(Modifier(_signed(m[2]), _signed(m[3])), _other(who),
                                    "chosen" if who["chosen"] else _who_subtype(who), line, condition=condition,
                                    per=("source_counters", m[4])))
        elif m := _COMMANDER_SCALED.fullmatch(sentence):  # Vanguard of the Restless
            who = _AFFECTED_WHO.fullmatch(m[1])
            assert who is not None
            buffs.append(StaticBuff(Modifier(_signed(m[2]), _signed(m[3])), who["other"] is not None,
                                    _who_subtype(who), line, condition=condition, per=("commander_casts", "")))
        elif m := _BOTH_SCALED.fullmatch(sentence):
            buffs.append(StaticBuff(Modifier(_signed(m[1]), _signed(m[2])), False, None, line, self_only=True, per=_PER["creature you control"]))
            buffs.append(StaticBuff(Modifier(_signed(m[3]), _signed(m[4])), False, None, line, self_only=True, per=_PER["Aura you control"]))
        elif m := _SELF_SCALED.fullmatch(sentence):  # "This creature gets +1/+0 for each artifact you control."
            modifier = Modifier(_signed(m[1]), _signed(m[2]))
            buffs.append(StaticBuff(modifier, False, None, line, self_only=True, condition=condition,
                                    per=_PER_LOWER[m[3].lower()]))
        elif m := _CANT.fullmatch(sentence):  # "This creature can't block." (a token's, for one)
            keywords = {"attack": {CANT_ATTACK}, "block": {CANT_BLOCK}, "be blocked": {CANT_BE_BLOCKED},
                        "block and can't be blocked": {CANT_BLOCK, CANT_BE_BLOCKED}}.get(m[1].lower(), {CANT_ATTACK, CANT_BLOCK})
            buffs.append(StaticBuff(Modifier(0, 0, frozenset(keywords)), False, None, line, self_only=True, condition=condition))
        elif _MUST_ATTACK.fullmatch(sentence):
            buffs.append(StaticBuff(Modifier(0, 0, frozenset({MUST_ATTACK})), False, None, line, self_only=True, condition=condition))
        elif condition and (m := _SELF_STATIC.fullmatch(sentence)):  # unconditional ones would just be printed text
            buffs.append(StaticBuff(_modifier(m, 1), False, None, line, self_only=True, condition=condition))
    return tuple(buffs)


@lru_cache(maxsize=None)
def aura_kind(card: Card) -> str | None:
    """What an Aura enchants ("creature", "creature you control", "land", ...), or None if it isn't an Aura."""
    if "Aura" not in card.type_line:
        return None
    return next((m[1].lower() for line in rules_lines(card) if (m := _ENCHANT.fullmatch(line))), None)


_REPLACE_ANY_GRAVEYARD = "If a card or token would be put into a graveyard from anywhere, exile it instead."


_REPLACE_SELF_GRAVEYARD = "If CARDNAME would be put into a graveyard from anywhere, exile it instead."  # the back of a Disturb card


_REPLACE_SHUFFLE_GRAVEYARD = ("If CARDNAME would be put into a graveyard from anywhere, reveal CARDNAME and shuffle it into its "
                              "owner's library instead.")  # Blightsteel Colossus, Progenitus, Nexus of Fate


_REPLACE_OPPONENT_GRAVEYARD = "If a card would be put into an opponent's graveyard from anywhere, exile it instead."


_DOUBLE_TOKENS = ("If an effect would create one or more tokens under your control, it creates twice that many of "
                  "those tokens instead.")


_DOUBLE_COUNTERS = ("If an effect would put one or more counters on a permanent you control, it puts twice that many "
                    "of those counters on that permanent instead.")


_DOUBLE_COUNTERS_OLD = ("If an effect would put one or more counters on a permanent you control, it puts twice that "
                        "many of those counters instead.")  # the wording before the Oracle update


_DOUBLE_YOU_PUT = ("If you would put one or more counters on a permanent or player, put twice that many of each of those kinds of "
                   "counters on that permanent or player instead.")  # Vorinclex, Monstrous Raider; Innkeeper's Talent at level 3


_HALVE_OPPONENTS_PUT = ("If an opponent would put one or more counters on a permanent or player, they put half that many of each of "
                        "those kinds of counters on that permanent or player instead, rounded down.")


_PROLIFERATE_TWICE = "If you would proliferate, proliferate twice instead."  # Tekuthal, Inquiry Dominus


_DOUBLE_TOKENS_NOW = ("If one or more tokens would be created under your control, twice that many of those tokens are created "
                      "instead.")  # the wording since the 2024 Oracle update (Mondrak, Glory Dominus)


_DOUBLE_LIFE = "If you would gain life, you gain twice that much life instead."


_DOUBLE_PLUS_ONE = ("If one or more +1/+1 counters would be put on a creature you control, twice that many +1/+1 counters are "
                    "put on that creature instead.")  # Branching Evolution


_SQUIRRELS = ("If one or more tokens would be created under your control, those tokens plus that many 1/1 green Squirrel creature tokens "
              "are created instead.")  # Chatterfang, Squirrel General


_MANUFACTOR = "If you would create a Clue, Food, or Treasure token, instead create one of each."


_DIE_EXILE_OPPONENT = "If a creature an opponent controls would die, exile it instead."


_DIE_EXILE_SELF = re.compile(rf"If {_SELF} would die, exile it instead\.", re.I)


_PLUS_ONE_OTHERS = ("If one or more +1/+1 counters would be put on another creature you control, that many plus one "
                    "+1/+1 counters are put on it instead.")


_ENTER_PER_DEATH = ("Nontoken creatures you control enter with an additional +1/+1 counter on them for each creature that "
                    "died under your control this turn.")


_PLUS_ONE_PERMANENTS = ("If one or more +1/+1 counters would be put on a permanent you control, that many plus one "
                        "+1/+1 counters are put on that permanent instead.")


_PLUS_ONE_ARTIFACTS = ("If one or more +1/+1 counters would be put on an artifact or creature you control, that many plus "
                       "one +1/+1 counters are put on it instead.")


_PLUS_ONE_COUNTERS = ("If one or more +1/+1 counters would be put on a creature you control, that many plus one "
                      "+1/+1 counters are put on it instead.")


_EXTRA_TRIGGER = re.compile(r"If (an artifact or creature|a permanent) entering(?: the battlefield)? causes a triggered "
                            r"ability of a permanent you control to trigger, that ability triggers an additional time\.")


@dataclass(frozen=True)
class Replacements:
    """What a permanent's static replacement effects do (CR 614), as the game applies them."""
    graveyard: str | None = None  # "any": cards go to exile instead of a graveyard; "opponent": only an opponent's
    tokens: int = 1  # how many times as many tokens its controller creates
    counters: int = 1  # how many times as many counters go on its controller's permanents
    plus_one: int = 0  # extra +1/+1 counters on its controller's creatures
    plus_one_others: int = 0  # the same, but not on the permanent itself (Benevolent Hydra)
    enter_counters_per_death: int = 0  # Gorma: nontoken creatures enter with that many extra counters per death this turn
    plus_one_permanents: int = 0  # the same on any permanent you control (Kami of Whispered Hopes)
    plus_one_artifacts: int = 0  # the same on an artifact or creature you control (Ozolith, the Shattered Spire)
    opponent_loss_factor: int = 1  # Bloodletter of Aclazotz: opponents lose that many times as much life during its controller's turn
    win_on_empty_draw: bool = False  # Laboratory Maniac
    life_gain_plus: int = 0  # Pest Rescuer: its controller gains that much more life whenever they gain life
    life_gain_factor: int = 1  # how many times as much life its controller gains (The Wind Crystal)
    plus_one_factor: int = 1  # how many times as many +1/+1 counters go on its controller's creatures (Branching Evolution)
    squirrels: bool = False  # Chatterfang: as many 1/1 Squirrels as the tokens its controller creates, besides them
    manufactor: bool = False  # Academy Manufactor: a Clue, Food or Treasure token becomes one of each
    graveyard_self: bool = False  # this one is exiled instead of going to a graveyard (a Disturb back)
    draw_double: tuple[str, ...] = ()  # "always", "extra" (not the draw step's first card) or "empty" (no cards in hand): a draw is two cards
    life_gain_factor_low: int = 1  # how many times as much life its controller gains while they have 5 or less life (Phial of Galadriel)
    graveyard_shuffle: bool = False  # this one is revealed and shuffled into its owner's library instead (CR 614.1)
    die_exile: str | None = None  # "opponent": their creatures are exiled instead of dying (Liesa); "self": this one is
    extra_trigger: str | None = None  # "artifact or creature" or "permanent": those entering trigger abilities twice;
    #                                    "spell": casting or copying an instant or sorcery does
    enter_counter_chosen: int = 0  # Metallic Mimic: other creatures of the type it chose enter with that many more +1/+1 counters
    counters_you_put: int = 1  # how many times as many counters its controller puts on any permanent or player (Vorinclex, Monstrous Raider)
    opponents_put_half: bool = False  # Vorinclex: an opponent puts half as many counters, rounded down
    proliferate_factor: int = 1  # how many times its controller's proliferate happens (Tekuthal: "proliferate twice instead")


@lru_cache(maxsize=None)
def replacement_effects(card: Card) -> Replacements:
    found: dict[str, Any] = {}
    for line in rules_lines(card):
        if line == _REPLACE_ANY_GRAVEYARD:
            found["graveyard"] = "any"
        elif line == _REPLACE_OPPONENT_GRAVEYARD:
            found.setdefault("graveyard", "opponent")
        elif line == _REPLACE_SELF_GRAVEYARD:
            found["graveyard_self"] = True
        elif line in (_DOUBLE_DRAW, _DOUBLE_DRAW_EXTRA, _DOUBLE_DRAW_EMPTY):
            found["draw_double"] = (*found.get("draw_double", ()), {_DOUBLE_DRAW: "always", _DOUBLE_DRAW_EXTRA: "extra"}.get(line, "empty"))
        elif line == _DOUBLE_LIFE_LOW:
            found["life_gain_factor_low"] = found.get("life_gain_factor_low", 1) * 2
        elif line == _REPLACE_SHUFFLE_GRAVEYARD:
            found["graveyard_shuffle"] = True
        elif line in (_DOUBLE_TOKENS, _DOUBLE_TOKENS_NOW):
            found["tokens"] = found.get("tokens", 1) * 2
        elif line == _DOUBLE_LIFE:
            found["life_gain_factor"] = found.get("life_gain_factor", 1) * 2
        elif line == _DOUBLE_PLUS_ONE:
            found["plus_one_factor"] = found.get("plus_one_factor", 1) * 2
        elif line == _MANUFACTOR:
            found["manufactor"] = True
        elif line == _SQUIRRELS:
            found["squirrels"] = True
        elif line == _DIE_EXILE_OPPONENT:
            found["die_exile"] = "opponent"
        elif _DIE_EXILE_SELF.fullmatch(line):
            found["die_exile"] = "self"
        elif line in (_DOUBLE_COUNTERS, _DOUBLE_COUNTERS_OLD):
            found["counters"] = found.get("counters", 1) * 2
        elif line == _DOUBLE_YOU_PUT:
            found["counters_you_put"] = found.get("counters_you_put", 1) * 2
        elif line == _HALVE_OPPONENTS_PUT:
            found["opponents_put_half"] = True
        elif line == _PROLIFERATE_TWICE:
            found["proliferate_factor"] = found.get("proliferate_factor", 1) * 2
        elif line == _PLUS_ONE_COUNTERS:
            found["plus_one"] = found.get("plus_one", 0) + 1
        elif line == _ENTER_PER_DEATH:
            found["enter_counters_per_death"] = found.get("enter_counters_per_death", 0) + 1
        elif line == _PLUS_ONE_PERMANENTS:
            found["plus_one_permanents"] = found.get("plus_one_permanents", 0) + 1
        elif line == _PLUS_ONE_ARTIFACTS:
            found["plus_one_artifacts"] = found.get("plus_one_artifacts", 0) + 1
        elif line == _PLUS_ONE_OTHERS:
            found["plus_one_others"] = found.get("plus_one_others", 0) + 1
        elif m := _EXTRA_TRIGGER.fullmatch(line):
            found["extra_trigger"] = m[1].removeprefix("an ").removeprefix("a ")
        elif _EXTRA_TRIGGER_SPELL.fullmatch(line):
            found["extra_trigger"] = "spell"
        elif _EXTRA_TRIGGER_WIZARD.fullmatch(line):
            found["extra_trigger"] = "wizard"
        elif _EXTRA_TRIGGER_CHOSEN.fullmatch(line):
            found["extra_trigger"] = "chosen_type"
        elif line == _ENTER_CHOSEN:
            found["enter_counter_chosen"] = found.get("enter_counter_chosen", 0) + 1
        elif line == _DOUBLE_OPPONENT_LOSS:
            found["opponent_loss_factor"] = found.get("opponent_loss_factor", 1) * 2
        elif line == _WIN_ON_EMPTY_DRAW:
            found["win_on_empty_draw"] = True
        elif line == _LIFE_GAIN_PLUS_ONE:
            found["life_gain_plus"] = found.get("life_gain_plus", 0) + 1
    return Replacements(**found)


@dataclass(frozen=True)
class DamageModifier:
    """A static replacement effect on damage (CR 614.1, 616.1): "If a source you control would deal damage to a permanent or player,
    it deals double that damage instead." (Angrath's Marauders), "... noncombat damage to an opponent or a permanent an opponent
    controls, it deals that much damage plus 1 instead." (Tomik), "If another red source you control would deal damage ..." (Torbran)"""
    source: str  # "any" (a source), "you" (a source you control), "creature" (a creature you control), "self" (this creature)
    victim: str  # "any" (a permanent or player), "opponent" (an opponent or a permanent an opponent controls), "player" (a player),
    #              "opponent_player" (an opponent: a player only), "none" (not said: any damage)
    kind: str  # "any", "combat" or "noncombat" damage
    factor: int = 1  # double: 2, triple: 3
    plus: int = 0  # "that much damage plus N"
    groups: tuple[tuple[str, ...], ...] = ()  # what the source must be: every group needs one of its words (color, card type or subtype)
    another: bool = False  # not the permanent with this ability
    spell: bool = False  # the source is a spell ("a red spell")


_WORD = r"(?:[a-z]+|[A-Z][a-z]+)"


_DESC = rf"(?:(?:white|blue|black|red|green) (?!or\b))?{_WORD}(?:(?:, or |, | or ){_WORD})*"  # "red", "red or artifact", "red instant or sorcery"


_DAMAGE_MODIFIER = re.compile(
    rf"If ((?:a|an|another) (?:{_DESC} )?(?:source|spell)(?: you control)?|a source|a source you control"
    rf"|a creature you control|an? [A-Z][a-z]+(?:, [A-Z][a-z]+)*,? or [A-Z][a-z]+ you control|{_SELF}) would deal (noncombat |combat )?damage"
    r"(?: to (a permanent or player|an opponent or a permanent an opponent controls|an opponent|a player))?, (?:it|that source) deals "
    r"(?:(double|triple) that damage|that much damage plus (\d+))(?: to that [a-z ]+)? instead\.")


_COLOR_WORDS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}


def _parse_source(text: str) -> dict[str, Any]:
    """The DamageModifier fields for who deals the damage: "a source you control", "another red source you control",
    "a Giant source you control", "a red instant or sorcery spell you control", "a Lizard, Mouse, or Otter you control"."""
    simple = {"a source": "any", "a source you control": "you", "a creature you control": "creature"}
    if text in simple:
        return {"source": simple[text]}
    if text.startswith(("a ", "an ", "another ")) and (m := re.fullmatch(rf"(?:a|an) ([A-Z][a-z]+(?:, [A-Z][a-z]+)*,? or [A-Z][a-z]+) you control", text)):
        return {"source": "you", "groups": (tuple(re.split(r", or |, | or ", m[1])), ("creature",))}
    if m := re.fullmatch(rf"(a|an|another) (?:({_DESC}) )?(source|spell)( you control)?", text):
        groups: list[tuple[str, ...]] = []
        if m[2]:
            desc = m[2]
            if peeled := re.match(r"(white|blue|black|red|green) (?!or\b)", desc):  # "red instant or sorcery": red, and an instant or a sorcery
                groups.append((peeled[1],))
                desc = desc[peeled.end():]
            groups.append(tuple(re.split(r", or |, | or ", desc)))
        return {"source": "you" if m[4] else "any", "groups": tuple(groups), "another": m[1] == "another", "spell": m[3] == "spell"}
    return {"source": "self"}


def _damage_modifier(line: str) -> DamageModifier | None:
    if not (m := _DAMAGE_MODIFIER.fullmatch(line)):
        return None
    victim = {"a permanent or player": "any", "an opponent or a permanent an opponent controls": "opponent",
              "an opponent": "opponent_player", "a player": "player"}[m[3]] if m[3] else "any"
    return DamageModifier(victim=victim, kind=(m[2] or "any").strip().replace(" ", "") or "any",
                          factor={"double": 2, "triple": 3}.get(m[4] or "", 1), plus=int(m[5] or 0), **_parse_source(m[1]))  # type: ignore[arg-type]


@lru_cache(maxsize=None)
def damage_modifiers(card: Card) -> tuple[DamageModifier, ...]:
    return tuple(mod for line in rules_lines(card) if (mod := _damage_modifier(line)) is not None)


_DOUBLE_DRAW = "If you would draw a card, draw two cards instead."  # Thought Reflection


_DOUBLE_DRAW_EMPTY = "If you would draw a card while you have no cards in hand, draw two cards instead."  # Phial of Galadriel


_DOUBLE_LIFE_LOW = "If you would gain life while you have 5 or less life, you gain twice that much life instead."  # Phial of Galadriel


_DOUBLE_DRAW_EXTRA = ("If you would draw a card except the first one you draw in each of your draw steps, draw two cards "
                      "instead.")  # Alhammarret's Archive, Teferi's Ageless Insight, Bard, King of Dale


_LIFE_GAIN_PLUS_ONE = "If you would gain life, you gain that much life plus 1 instead."


_DOUBLE_OPPONENT_LOSS = "If an opponent would lose life during your turn, they lose twice that much life instead."


_WIN_ON_EMPTY_DRAW = "If you would draw a card while your library has no cards in it, you win the game instead."


# Veyran, Voice of Duality (the card's own wording has "you casting").
_EXTRA_TRIGGER_SPELL = re.compile(r"If you casting or copying an instant or sorcery spell causes a triggered ability of a "
                                  r"permanent you control to trigger, that ability triggers an additional time\.")


# Harmonic Prodigy.
_EXTRA_TRIGGER_WIZARD = re.compile(r"If a triggered ability of a Shaman or another Wizard you control triggers, that ability triggers "
                                   r"an additional time\.")


# Roaming Throne.
_EXTRA_TRIGGER_CHOSEN = re.compile(r"If a triggered ability of another creature you control of the chosen type triggers, it triggers "
                                   r"an additional time\.")


# Metallic Mimic.
_ENTER_CHOSEN = "Each other creature you control of the chosen type enters with an additional +1/+1 counter on it."


# Mox Diamond.
_ENTERS_BY_DISCARD = ("If this artifact would enter, you may discard a land card instead. If you do, put this artifact onto the "
                      "battlefield. If you don't, put it into its owner's graveyard.")


@lru_cache(maxsize=None)
def enters_by_discarding_land(card: Card) -> bool:
    return any(line == _ENTERS_BY_DISCARD for line in rules_lines(card))


def is_replacement_line(line: str) -> bool:
    return (line == _DOUBLE_OPPONENT_LOSS or line == _WIN_ON_EMPTY_DRAW or line == _ENTERS_BY_DISCARD or line == _ENTER_CHOSEN or _EXTRA_TRIGGER_CHOSEN.fullmatch(line) is not None or _EXTRA_TRIGGER_SPELL.fullmatch(line) is not None or _EXTRA_TRIGGER_WIZARD.fullmatch(line) is not None or line in (_REPLACE_ANY_GRAVEYARD, _REPLACE_OPPONENT_GRAVEYARD, _REPLACE_SELF_GRAVEYARD, _REPLACE_SHUFFLE_GRAVEYARD, _DOUBLE_DRAW, _DOUBLE_DRAW_EXTRA, _DOUBLE_DRAW_EMPTY, _DOUBLE_LIFE_LOW, _DOUBLE_TOKENS, _DOUBLE_COUNTERS,
                     _DOUBLE_COUNTERS_OLD, _PLUS_ONE_COUNTERS, _PLUS_ONE_OTHERS, _PLUS_ONE_PERMANENTS, _PLUS_ONE_ARTIFACTS, _ENTER_PER_DEATH, _LIFE_GAIN_PLUS_ONE,
                     _DOUBLE_TOKENS_NOW, _DOUBLE_LIFE, _DOUBLE_PLUS_ONE, _MANUFACTOR, _SQUIRRELS, _DIE_EXILE_OPPONENT, _DOUBLE_YOU_PUT,
                     _HALVE_OPPONENTS_PUT, _PROLIFERATE_TWICE)
            or _DIE_EXILE_SELF.fullmatch(line) is not None or _EXTRA_TRIGGER.fullmatch(line) is not None or _damage_modifier(line) is not None)


_CLONE = re.compile(rf"You may have {_SELF} enter(?: the battlefield)?( tapped)?(?: the battlefield)? as a copy of (.+?)(?:, except (.+))?\.")


_CLONE_KIND = r"(?:nonland permanent|permanent|[A-Za-z]+(?: or [A-Za-z]+)?)"


_CLONE_SOURCE = re.compile(rf"any ({_CLONE_KIND}) on the battlefield(?P<spent> with mana value less than or equal to the amount of mana spent to cast CARDNAME)?"
                           rf"|any ({_CLONE_KIND}) card in a graveyard|any (permanent) that entered this turn"
                           rf"|(an?|another) ({_CLONE_KIND}) (you control|an opponent controls)(?: with power (\d+) or greater)?")


@dataclass(frozen=True)
class CloneRule:
    """"You may have this creature enter as a copy of any creature on the battlefield, except ...": what it may copy and how the
    copy differs (Clone, Phantasmal Image, Spark Double, Vesuva ...)."""
    kind: str  # the filter of what it may copy: "creature", "nonland permanent", "artifact or enchantment"
    yours: bool = False  # "you control"
    opponents: bool = False  # "an opponent controls"
    min_power: int = 0  # "with power 4 or greater"
    tapped: bool = False  # "enter tapped as a copy of any land": tapped when it is a copy
    changes: CopyChanges = CopyChanges()
    zone: str = "battlefield"  # Body Double, Echoing Deeps: "any creature card in a graveyard"
    entered_this_turn: bool = False  # Sakashima's Protege: "any permanent that entered this turn"
    mana_spent_cap: bool = False  # Mockingbird: "with mana value less than or equal to the amount of mana spent to cast CARDNAME"


@lru_cache(maxsize=None)
def _clone_rule_of_line(line: str) -> CloneRule | None:
    if not (m := _CLONE.fullmatch(line + "." if line.endswith('."') else line)):  # (a quoted ability ends the line: ... sacrifice it.")
        return None
    source = _CLONE_SOURCE.fullmatch(m[2])
    changes = _copy_changes(m[3]) if m[3] else CopyChanges()
    if source is None or changes is None:
        return None
    if source[1]:
        return CloneRule(source[1].lower(), tapped=bool(m[1]), changes=changes, mana_spent_cap=bool(source["spent"]))
    if source[3]:
        return CloneRule(source[3].lower(), tapped=bool(m[1]), changes=changes, zone="graveyard")
    if source[4]:
        return CloneRule(source[4].lower(), tapped=bool(m[1]), changes=changes, entered_this_turn=True)
    return CloneRule(source[6].lower(), yours=source[7] == "you control", opponents=source[7] != "you control",
                     min_power=int(source[8] or 0), tapped=bool(m[1]), changes=changes)


# Cursed Mirror: a copy only until end of turn, with a keyword added.
_TEMP_CLONE = re.compile(rf"As {_SELF} enters, you may have it become a copy of any creature on the battlefield until end of turn, "
                         r"except it has ([a-z]+)\.")


@lru_cache(maxsize=None)
def temporary_clone_keyword(card: Card) -> str | None:
    """Cursed Mirror: the keyword a copy "until end of turn" gets, if the card enters that way."""
    return next((m[1].capitalize() for line in rules_lines(card) if (m := _TEMP_CLONE.fullmatch(line))), None)


@lru_cache(maxsize=None)
def clone_rule(card: Card) -> CloneRule | None:
    """What the card may enter as a copy of, if it has such a line."""
    return next((rule for line in rules_lines(card) if (rule := _clone_rule_of_line(line))), None)


def clone_kind(card: Card) -> tuple[str, bool] | None:
    """For Clone: what the card may enter as a copy of ("creature") and whether it must be one you control."""
    rule = clone_rule(card)
    return (rule.kind, rule.yours) if rule else None


def is_clone_line(line: str) -> bool:
    return _clone_rule_of_line(line) is not None or _TEMP_CLONE.fullmatch(line) is not None


def is_enchant_line(line: str) -> bool:
    return _ENCHANT.fullmatch(line) is not None


# Animate Dead and Dance of the Dead: an Aura cast on a creature card in a graveyard, which comes back with the Aura.
_REANIMATION_AURA = re.compile(
    r"When (?:this Aura|CARDNAME) enters, if it's on the battlefield, it loses \"enchant creature card in a graveyard\" and "
    r"gains \"enchant creature put onto the battlefield with (?:this Aura|CARDNAME)\.\" (?:Return|Put) enchanted creature "
    r"card (?:to|onto) the battlefield( tapped)? under your control and attach (?:this Aura|CARDNAME) to it\. When "
    r"(?:this Aura|CARDNAME) leaves the battlefield, that creature's controller sacrifices it\.")


@lru_cache(maxsize=None)
def reanimation_aura(card: Card) -> tuple[bool] | None:
    """(enters tapped,) for Animate Dead and its kind; None for any other card."""
    for line in rules_lines(card):
        if m := _REANIMATION_AURA.fullmatch(line):
            return (bool(m[1]),)
    return None


def is_reanimation_aura_line(line: str) -> bool:
    return _REANIMATION_AURA.fullmatch(line) is not None


@dataclass(frozen=True)
class AttachedBuff:
    """ "Equipped creature gets +1/+1 and has haste." / "Enchanted creature can't attack or block." """
    modifier: Modifier
    text: str
    per: tuple[str, str] | None = None  # "... for each Aura you control that's attached to a creature"
    goaded: bool = False  # "Enchanted creature gets +1/+1 and is goaded."
    subtype: str | None = None  # "... and is an Angel in addition to its other types."


_ATTACHED_LOSES = re.compile(r"(?:Equipped|Enchanted) creature (?:loses all abilities(?: and doesn't untap during its controller's "
                             r"untap step)?|doesn't untap during its controller's untap step)\.")


_ATTACHED_CHOSEN_PROTECTION = re.compile(r"Enchanted creature has protection from the chosen color\. This effect doesn't remove this Aura\.")


# Darksteel Mutation. Its card types and creature types are not replaced (only the size, indestructible and the lost abilities are).
_ATTACHED_MUTATION = re.compile(r"Enchanted creature is an Insect artifact creature with base power and toughness 0/1 and has "
                                r"indestructible, and it loses all other abilities, card types, and creature types\.")


_ATTACHED = re.compile(rf"(?:Equipped|Enchanted) creature (?:gets {_PT}(?: and has {_KEYWORDS})?|has {_KEYWORDS}"
                       r"|can't attack or block)\.")


LOSES_ALL, NO_UNTAP = "loses all abilities", "doesn't untap"  # pseudo-keywords of an Aura: Infinite Coursework


_GRANT = re.compile(rf'(?:Equipped|Enchanted) (?:creature|land|permanent) has (?:{_KEYWORDS_BARE} and )?"(.+)"\.?')


_ATTACHED_AND_GRANT = re.compile(rf'(?:Equipped|Enchanted) creature has ({_KEYWORDS}) and ".+"\.?')  # Fallen Ideal  # the quote's own full stop is inside it


_GROUP_GRANT = re.compile(r'(Treasures|Artifacts|Creatures|Lands) you control have "(.+)"\.?')


_GROUP_KIND = {"Treasures": "Treasure", "Artifacts": "Artifact", "Creatures": "Creature", "Lands": "Land"}


def is_group_mana_grant_line(line: str) -> bool:
    """Goldspan Dragon, Galazeth Prismari: "Treasures you control have "{T}, Sacrifice this artifact: Add ..."."; Enduring Vitality:
    "Creatures you control have "{T}: Add one mana of any color."" """
    return (m := _GROUP_GRANT.fullmatch(line)) is not None and is_mana_ability(m[2])


def _group_activated(line: str) -> tuple[str, ActivatedAbility] | None:
    """(type of permanent, the ability) for a line that gives a group of permanents an activated ability we understand."""
    if (m := _GROUP_GRANT.fullmatch(line)) and not is_mana_ability(m[2]) and (a := _ACTIVATED.fullmatch(m[2])):
        if ability := _parse_activated(m[2], a[1], a[2], False):
            return _GROUP_KIND[m[1]], ability
    return None


def is_group_activated_grant_line(line: str) -> bool:
    """Bootleggers' Stash: "Lands you control have "{T}: Create a Treasure token."" where the quoted ability is one we understand."""
    return _group_activated(line) is not None


@lru_cache(maxsize=None)
def group_activated_grants(card: Card) -> tuple[tuple[str, ActivatedAbility], ...]:
    """The activated abilities `card` gives to a group of permanents you control, as (type of permanent, the ability)."""
    return tuple(found for line in rules_lines(card) if (found := _group_activated(line)))


@lru_cache(maxsize=None)
def group_mana_grants(card: Card) -> tuple[tuple[str, str], ...]:
    """The mana abilities `card` gives to a group of permanents you control, as (type of permanent, the ability's line)."""
    return tuple((_GROUP_KIND[m[1]], m[2]) for line in rules_lines(card)
                 if (m := _GROUP_GRANT.fullmatch(line)) and is_mana_ability(m[2]))


@lru_cache(maxsize=None)
def granted_land_mana(lines: tuple[str, ...], commander_identity: frozenset[str]) -> frozenset[str]:
    """The mana types lands make because of what they are given ("Lands you control have "{T}: Add one mana of any color."")."""
    types: set[str] = set()
    for line in lines:
        for unit in _mana_from_line(line, commander_identity) or ():
            types |= unit
    return frozenset(types)


def with_granted_mana(card: Card, lines: tuple[str, ...]) -> Card:
    """`card` as its mana ability reads once it is given `lines`. An unrestricted grant goes first, since it replaces the
    card's own ability (Goldspan Dragon's two mana beat a Treasure's one); one with a spending restriction goes last, so it
    only counts for a card that has no mana ability of its own (Galazeth Prismari)."""
    first = [line for line in lines if "Spend this mana only" not in line]
    last = [line for line in lines if "Spend this mana only" in line]
    return dataclasses.replace(card, oracle_text="\n".join([*first, *rules_lines(card), *last]))


def is_granting_line(line: str) -> bool:
    """ "Enchanted creature has "{T}: Draw a card."" where the quoted ability is one we understand."""
    return (m := _GRANT.fullmatch(line)) is not None and (
        is_mana_ability(m[1]) or (a := _ACTIVATED.fullmatch(m[1])) is not None
        and _parse_activated(m[1], a[1], a[2], False) is not None)


@lru_cache(maxsize=None)
def granted_abilities(card: Card) -> tuple[ActivatedAbility, ...]:
    """The activated abilities an Aura or Equipment gives what it is attached to ("Enchanted creature has "{T}: Draw a
    card."")."""
    found = []
    for line in rules_lines(card):
        if (m := _GRANT.fullmatch(line)) and not is_mana_ability(m[1]) and (a := _ACTIVATED.fullmatch(m[1])):
            if ability := _parse_activated(m[1], a[1], a[2], False):
                found.append(ability)
    return tuple(found)


def granted_mana(card: Card) -> list[frozenset[str]]:
    """The mana an Aura gives a land it enchants ("Enchanted land has "{T}: Add {G}{G}."")."""
    for line in rules_lines(card):
        if (m := _GRANT.fullmatch(line)) and any(p.fullmatch(m[1]) for p in (_ADD_SYMBOLS, _ADD_EITHER, _ADD_ANY)):
            return _mana_from_line(m[1], frozenset()) or []
    return []


_ADDITIONAL_MANA = re.compile(r"Whenever enchanted (?:land|Forest|Island|Plains|Swamp|Mountain) is tapped for mana, its controller adds an additional "
                              r"(?:\{([WUBRG])\}|one mana of (any|the chosen) color)\.")


def additional_land_mana(card: Card, chosen: str | None = None) -> list[frozenset[str]]:
    """Wild Growth and Fertile Ground: the extra mana the enchanted land makes whenever it is tapped for mana.
    `chosen` is the color picked as the Aura entered (Utopia Sprawl)."""
    return [frozenset(m[1] or (chosen if m[2] == "the chosen" and chosen else "WUBRG"))
            for line in rules_lines(card) if (m := _ADDITIONAL_MANA.fullmatch(line))]


def is_additional_mana_line(line: str) -> bool:
    return _ADDITIONAL_MANA.fullmatch(line) is not None


# Tyvar, Jubilant Brawler, Thousand-Year Elixir, Shang-Chi: the creatures' {T} abilities work the turn they come under your control.
_HASTE_ABILITIES = re.compile(r"You may activate abilities of creatures you control as though those creatures had haste\.")


@lru_cache(maxsize=None)
def activates_as_though_haste(card: Card) -> bool:
    """CR 302.6: the card lets its controller use their creatures' {T} abilities as though those creatures had haste (attacking still
    needs haste itself)."""
    return any(_HASTE_ABILITIES.fullmatch(line) for line in rules_lines(card))


def is_haste_abilities_line(line: str) -> bool:
    return _HASTE_ABILITIES.fullmatch(line) is not None


@lru_cache(maxsize=None)
def keeps_its_protection_aura(card: Card) -> bool:
    """Flickering Ward: its protection "doesn't remove this Aura" (CR 704.5m would otherwise)."""
    return any(_ATTACHED_CHOSEN_PROTECTION.fullmatch(line) for line in rules_lines(card))


@lru_cache(maxsize=None)
def attached_abilities(card: Card) -> tuple[AttachedBuff, ...]:
    buffs = []
    for line in rules_lines(card):
        if m := _ATTACHED.fullmatch(line):
            if "can't attack or block" in line:
                modifier = Modifier(keywords=frozenset({CANT_ATTACK, CANT_BLOCK}))
            else:
                modifier = _modifier(m, 1)
            buffs.append(AttachedBuff(modifier, line))
        elif m := _ATTACHED_AND_GRANT.fullmatch(line):  # the keywords; granted_abilities has the quoted ability
            buffs.append(AttachedBuff(Modifier(keywords=_keyword_list(m[1])), line))
        elif m := _ATTACHED_TYPED.fullmatch(line):
            buffs.append(AttachedBuff(Modifier(_signed(m[1]), _signed(m[2]), _keyword_list(m[3])), line, subtype=m[4]))
        elif _ATTACHED_CHOSEN_PROTECTION.fullmatch(line):
            buffs.append(AttachedBuff(Modifier(keywords=frozenset({PROTECTION_CHOSEN})), line))
        elif _ATTACHED_MUTATION.fullmatch(line):
            buffs.append(AttachedBuff(Modifier(keywords=frozenset({"indestructible", LOSES_ALL}), set_pt=(0, 1)), line))
        elif _ATTACHED_LOSES.fullmatch(line):  # Infinite Coursework
            keywords = {LOSES_ALL} if "loses all abilities" in line else set()
            buffs.append(AttachedBuff(Modifier(keywords=frozenset(keywords | ({NO_UNTAP} if "untap" in line else set()))), line))
        elif m := _ATTACHED_GOADED.fullmatch(line):
            keywords = _keyword_list(m[3]) if m[3] else frozenset()
            buffs.append(AttachedBuff(Modifier(_signed(m[1]), _signed(m[2]), keywords), line, goaded=True))
        elif m := _BOTH_SCALED.fullmatch(line):
            buffs.append(AttachedBuff(Modifier(_signed(m[1]), _signed(m[2])), line, per=_PER["creature you control"]))
            buffs.append(AttachedBuff(Modifier(_signed(m[3]), _signed(m[4])), line, per=_PER["Aura you control"]))
        elif m := _ATTACHED_SCALED.fullmatch(line):
            buffs.append(AttachedBuff(Modifier(_signed(m[1]), _signed(m[2])), line, per=_PER[m[3]]))
        elif m := _ATTACHED_UNBLOCKABLE.fullmatch(line):
            buffs.append(AttachedBuff(Modifier(keywords=frozenset({CANT_BE_BLOCKED}) | (_keyword_list(m[1]) if m[1] else frozenset())), line))
    return tuple(buffs)


def is_class(card: Card) -> bool:
    return "Class" in card.type_line


@lru_cache(maxsize=None)
def class_view(card: Card, level: int) -> Card:
    """A Class card as it reads at `level`: the abilities of the levels up to it, and the "{cost}: Level N" line that gains the next
    level (rules_lines has the reminder text already removed)."""
    kept, at = [], 1
    for line in rules_lines(card):
        if m := _CLASS_LEVEL_LINE.fullmatch(line):
            at = int(m[2])
            if at == level + 1:
                kept.append(line)
        elif at <= level:
            kept.append(line)
    return dataclasses.replace(card, oracle_text="\n".join(kept))


def is_room(card: Card) -> bool:
    """A Room: one card with two doors, the second being `alternate`."""
    return "Room" in card.type_line and card.alternate is not None


@lru_cache(maxsize=None)
def room_view(whole: Card, doors: tuple[str, ...]) -> Card:
    """A Room as it reads with the doors named in `doors` unlocked: only an unlocked door's abilities are there."""
    halves = [half for half in (whole, whole.alternate) if half is not None and half.name in doors]
    colors = tuple(color for color in "WUBRG" if any(color in half.colors for half in halves))
    return dataclasses.replace(whole, oracle_text="\n".join(half.oracle_text for half in halves), colors=colors, alternate=None)


_CONTROL_AURA = "You control enchanted creature."


@lru_cache(maxsize=None)
def aura_controls(card: Card) -> bool:
    """Control Magic: an Aura that gives its controller control of the enchanted creature."""
    return "Aura" in card.type_line and _CONTROL_AURA in rules_lines(card)


def is_control_aura_line(line: str) -> bool:
    return line == _CONTROL_AURA


_CDA = re.compile(r"(?:CARDNAME's|This creature's) power and toughness are each equal to (.+)\.")


@lru_cache(maxsize=None)
def power_toughness_amount(card: Card) -> "Amount | None":
    """Overbeing of Myth: a characteristic-defining "power and toughness are each equal to ..." line."""
    for line in rules_lines(card):
        if (m := _CDA.fullmatch(line)) and (amount := _amount(m[1])):
            return amount
    return None


def is_cda_line(line: str) -> bool:
    return (m := _CDA.fullmatch(line)) is not None and _amount(m[1]) is not None


_HAND_BY_COUNTERS = re.compile(r"Your maximum hand size is equal to the number of (\w+) counters on (?:CARDNAME|this \w+)\.")


@lru_cache(maxsize=None)
def hand_size_counter(card: Card) -> str | None:
    """Midnight Oil: "Your maximum hand size is equal to the number of hour counters on this enchantment." """
    return next((m[1] for line in rules_lines(card) if (m := _HAND_BY_COUNTERS.fullmatch(line))), None)


def is_hand_by_counters_line(line: str) -> bool:
    return _HAND_BY_COUNTERS.fullmatch(line) is not None


_NO_MAX_HAND = "You have no maximum hand size."


_NO_MAX_HAND_ALL = "Players have no maximum hand size."


@lru_cache(maxsize=None)
def players_have_no_max_hand(card: Card) -> bool:
    """Price of Knowledge: no player has a maximum hand size."""
    return any(line == _NO_MAX_HAND_ALL for line in rules_lines(card))


@lru_cache(maxsize=None)
def no_max_hand_size(card: Card) -> bool:
    """Reliquary Tower, Thought Vessel: their controller discards nothing down to seven at the end of turn."""
    return any(line == _NO_MAX_HAND for line in rules_lines(card))


def is_no_max_hand_line(line: str) -> bool:
    return line in (_NO_MAX_HAND, _NO_MAX_HAND_ALL)


_EXTRA_VOTE = "While voting, you may vote an additional time."


@lru_cache(maxsize=None)
def extra_votes(card: Card) -> int:
    """Tivit, Seller of Secrets: how many additional times its controller may vote (the votes can differ)."""
    return int(any(line == _EXTRA_VOTE for line in rules_lines(card)))


def is_extra_vote_line(line: str) -> bool:
    return line == _EXTRA_VOTE


_ENTERS_PREPARED = re.compile(rf"{_SELF} enters prepared\.", re.I)


@lru_cache(maxsize=None)
def enters_prepared(card: Card) -> bool:
    """Whether a prepare creature "enters prepared"."""
    return card.prepare is not None and any(_ENTERS_PREPARED.fullmatch(line) for line in rules_lines(card))


def is_enters_prepared_line(line: str) -> bool:
    return _ENTERS_PREPARED.fullmatch(line) is not None


_ENTERS_TAPPED = [
    (re.compile(rf"{_SELF} enters tapped\.", re.I), lambda m: EntersTapped("always")),
    (re.compile(rf"{_SELF} enters tapped unless you control an? ({_LAND_TYPE}) or an? ({_LAND_TYPE})\.", re.I),
     lambda m: EntersTapped("unless_land_types", types=(m[1].capitalize(), m[2].capitalize()))),
    (re.compile(rf"{_SELF} enters tapped unless you control {_N_FIXED} or (fewer|more) other lands\.", re.I),
     lambda m: EntersTapped("unless_lands_at_most" if m[2].lower() == "fewer" else "unless_lands_at_least",
                            count=_number(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless you have {_N_FIXED} or more opponents\.", re.I),
     lambda m: EntersTapped("unless_opponents", count=_number(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless you control {_N_FIXED} or more basic lands\.", re.I),
     lambda m: EntersTapped("unless_basic_lands", count=_number(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless you control {_N_FIXED} or more other ({_LAND_TYPE})s?\.", re.I),
     lambda m: EntersTapped("unless_land_type_count", types=(m[2].capitalize(),), count=_number(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless your opponents control {_N_FIXED} or more lands\.", re.I),
     lambda m: EntersTapped("unless_opponent_lands", count=_number(m[1]))),
    (re.compile(rf"As {_SELF} enters, you may reveal an? ({_LAND_TYPE}) or ({_LAND_TYPE}) card from your hand\. "
                rf"If you don't, {_SELF} enters tapped\.", re.I),
     lambda m: EntersTapped("reveal", types=(m[1].capitalize(), m[2].capitalize()))),
    (re.compile(rf"As {_SELF} enters, you may pay {_N_FIXED} life\. If you don't, it enters tapped\.", re.I),
     lambda m: EntersTapped("shock", life=_number(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless you control an? ({_LAND_TYPE})\.", re.I),
     lambda m: EntersTapped("unless_control", types=(m[1].capitalize(),))),
    (re.compile(rf"{_SELF} enters tapped unless you control a planeswalker\.", re.I),
     lambda m: EntersTapped("unless_control", types=("Planeswalker",))),
    (re.compile(rf"{_SELF} enters tapped unless you control a basic land\.", re.I),
     lambda m: EntersTapped("unless_control", types=("Basic+Land",))),
    (re.compile(rf"{_SELF} enters tapped unless you control a legendary creature\.", re.I),
     lambda m: EntersTapped("unless_control", types=("Legendary+Creature",))),
    (re.compile(rf"{_SELF} enters tapped unless you control a Mount or Vehicle\.", re.I),
     lambda m: EntersTapped("unless_control", types=("Mount", "Vehicle"))),
    (re.compile(rf"{_SELF} enters tapped unless a player has {_N_FIXED} or less life\.", re.I),
     lambda m: EntersTapped("unless_a_player_life", count=_number(m[1]))),
    (re.compile(rf"If you control {_N_FIXED} or more other lands, {_SELF} enters tapped\.", re.I),
     lambda m: EntersTapped("if_lands_at_least", count=_number(m[1]))),
    (re.compile(rf"If you were the starting player, {_SELF} enters tapped\.", re.I),
     lambda m: EntersTapped("if_starting_player")),
    (re.compile(rf"{_SELF} enters tapped if you were the starting player\.", re.I),
     lambda m: EntersTapped("if_starting_player")),
    (re.compile(rf"As {_SELF} enters, you may reveal an? ([A-Z][a-z]+) card from your hand\. "
                rf"If you don't, {_SELF} enters tapped\.", re.I),
     lambda m: EntersTapped("reveal", types=(m[1].capitalize(),))),
    (re.compile(rf"{_SELF} enters tapped with {_N_FIXED} {_COUNTER} on it\.", re.I), lambda m: EntersTapped("always")),
    (re.compile(rf"{_SELF} enters tapped\. As (?:it|{_SELF}) enters, choose a color(?: other than (?:white|blue|black|red|green))?\.", re.I),
     lambda m: EntersTapped("always")),
]


_CHOOSE_COLOR = re.compile(rf"(?:{_SELF} enters tapped\. )?As (?:it|{_SELF}) enters, choose a color(?: other than (white|blue|black|red|green))?\.", re.I)


@lru_cache(maxsize=None)
def chooses_color(card: Card) -> bool:
    """Room of Refuge and the like: "As it enters, choose a color." (the choice is kept on the permanent)."""
    return any(_CHOOSE_COLOR.fullmatch(line) for line in rules_lines(card))


@lru_cache(maxsize=None)
def color_choice_excludes(card: Card) -> str | None:
    """A Thriving land or Gate: "choose a color other than red" leaves out R."""
    return next((_COLOR_LETTER[m[1].lower()] for line in rules_lines(card) if (m := _CHOOSE_COLOR.fullmatch(line)) and m[1]), None)


def is_choose_color_line(line: str) -> bool:
    return _CHOOSE_COLOR.fullmatch(line) is not None


@lru_cache(maxsize=None)
def enters_tapped_rule(card: Card) -> EntersTapped | None:
    for line in rules_lines(card):
        for pattern, build in _ENTERS_TAPPED:
            if m := pattern.fullmatch(line):
                return build(m)
    return None


def is_enters_tapped_line(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern, _ in _ENTERS_TAPPED)
