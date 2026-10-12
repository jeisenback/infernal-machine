"""Triggered abilities: the events a permanent watches for, conditions, and the sagas' chapters."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from functools import lru_cache

from ..cards import Card
from ..characteristics import Modifier

from .common import _SELF, _rules_text, _split_sentences, rules_lines
from .events import EVENTS
from .targets import follows_target, target_kind, uses_player, uses_source, uses_subject
from .outcomes import (
    _condition,
    _CONTRACT_BODY,
    _MODAL_DIFFERENT,
    _MODAL_INLINE,
    _parse,
    _parse_modal,
    _parse_modal_inline,
    _SPELL_COLORS,
    Backup,
    Condition,
    ContractAttack,
    CreateTokens,
    Drain,
    Draw,
    Exile,
    ExileTopOfThatPlayerMayCast,
    ExileUntilLeaves,
    Hideaway,
    LivingWeapon,
    MayPay,
    MayPayLoot,
    OnPlayer,
    OnSubject,
    OnSubjectController,
    PayToReturnSelf,
    PlayerLosesLife,
    PumpSource,
    PumpSourceX,
    PutCountersOnSource,
    ReturnAuraToBattlefield,
    ReturnDeadToBattlefield,
    ReturnSelfAsEnchantment,
    ReturnSelfToBattlefield,
    ReturnWithCounter,
    SylvanLibrary,
    TREASURE,
    UnlessPays,
)


@dataclass(frozen=True)
class TriggeredAbility:
    event: str  # one of events.EVENTS
    effects: tuple
    optional: bool  # "you may ...": the controller chooses when it resolves
    text: str
    watch: "Watch | None" = None  # set when it watches other objects ("Whenever another creature enters")
    once_per_turn: bool = False  # "This ability triggers only once each turn."
    condition: "Condition | None" = None  # "At the beginning of your upkeep, if ..., ..." (CR 603.4)


@dataclass(frozen=True)
class Watch:
    """What a watching trigger looks for."""
    kind: str  # "creature", "land", "artifact", "enchantment"; for casts "spell", "creature spell", ...
    other: bool = False  # "another": not the source itself
    yours: bool = False  # "you control" / "under your control"
    nontoken: bool = False
    caster: str = "you"  # for casts: "you", "player" (anyone) or "opponent"
    theirs: bool = False  # "an opponent controls"
    nth_each_turn: int = 0  # "your first / second / third ... spell each turn": 1, 2 or 3
    with_copy: bool = False  # "cast or copy" (magecraft)
    mv_at_least: int = 0  # "a spell with mana value 5 or greater"
    from_hand: bool = False  # "... from your hand"
    not_starting_deck: bool = False  # "a spell that isn't from your starting deck": a conjured card
    from_zone: str = ""  # "graveyard" ("from your graveyard", "from their graveyard") or "not_hand" ("from anywhere other than your hand")
    qualifier: str = ""  # "with power 4 or greater" ("power>=4"), "with flying" ("flying"), "with a +1/+1 counter on it" ("counter:+1/+1")
    expend: int = 0  # "Whenever you expend 4": the total mana spent on spells this turn that it waits for
    batch: bool = False  # "Whenever one or more creatures die": once for everything that happens at the same time
    chosen: bool = False  # "of the chosen type": only what is of the creature type the watcher chose as it entered




# One line can name several of a permanent's own events: "When this creature enters or dies, ...".
_SELF_EVENTS = {
    "enters": r"enters(?: the battlefield)?",
    "dies": r"dies",
    "attacks": r"attacks",
    "blocks": r"blocks",
    "becomes_blocked": r"becomes blocked",
    "combat_damage_to_player": r"deals combat damage to a player",
    "targeted": r"becomes the target of an? (?:spell|spell or ability)",
    "transformed": r"transforms into CARDNAME",
}


_ANY_SELF_EVENT = "(?:" + "|".join(_SELF_EVENTS.values()) + ")"


_SEVERAL_EVENTS = re.compile(rf"When(?:ever)? {_SELF} ({_ANY_SELF_EVENT}(?: or {_ANY_SELF_EVENT})+), (.+)", re.I)


_WHO = rf"(?:({_SELF}) or another|(another)|an?)"


_TRIBE = r"(?-i:[A-Z][a-z]+)"  # a creature type: "Pest", "Elf"


_PERMANENT_WATCH = rf"(enchanted creature|nontoken creature|creature token|(?:white|blue|black|red|green) creature|token|creature|land|artifact|enchantment|permanent|{_TRIBE})"


_WATCHES = {
    "permanent_enters": re.compile(
        rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control| an opponent controls)? enters(?: the battlefield)?"
        rf"( under your control| under an opponent's control)?, (.+)", re.I),
    "creature_dies": re.compile(rf"Whenever {_WHO} (enchanted creature|nontoken creature|creature token|token|creature|{_TRIBE})"
                                r"( you control| an opponent controls)? dies, (.+)", re.I),
    "permanent_leaves": re.compile(rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control| an opponent controls)? leaves the battlefield, (.+)", re.I),
    "permanent_taps": re.compile(rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control)? becomes tapped, (.+)", re.I),
    "permanent_to_graveyard": re.compile(rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control| an opponent controls)? is put into (?:a|(your)) "
                                         r"graveyard from the battlefield, (.+)", re.I),
    "cast": re.compile(r"Whenever (you cast or copy|you cast|a player casts|an opponent casts) (?:(an?|another)|(?:your|their) (first|second|third)) "
                       r"((?:white|blue|black|red|green) spell|multicolored spell"
                       r"|spell|creature spell|noncreature spell|instant or sorcery spell|artifact spell|enchantment spell"
                       r"|Aura spell|Aura, Equipment, or Vehicle spell|historic spell|spell with \{X\} in its mana cost|prepared spell"
                       r"|permanent spell with a mana cost that contains \{X\}|instant or sorcery spell with \{X\} in its mana cost"
                       r"|(?-i:[A-Z][a-z]+) spell)"  # a creature type: "another Vampire spell"
                       r"(?: with mana value (\d+) or greater)?"
                       r"( from your hand| from your graveyard| from their graveyard| from anywhere other than your hand"
                       r"| that isn't from your starting deck)?"
                       r"(?(3) each turn), (.+)", re.I),
    "card_to_graveyard": re.compile(rf"Whenever an? ([a-z ]+?) card is put into your graveyard from anywhere, (.+)", re.I),
    "sacrifice": re.compile(r"Whenever you sacrifice (?:an?|another) (token|artifact|land|Clue|Food|Treasure|enchantment), (.+)", re.I),
    "creature_attacks": re.compile(r"Whenever a creature you control attacks, (.+)", re.I),
    "expend": re.compile(r"Whenever you expend (\d+), (.+)", re.I),
}


_WATCH_QUALIFIER = re.compile(r" with ((power|toughness) (\d+) or (greater|less)|flying|a \+1/\+1 counter on it|mana value (\d+) or less)"
                              r"(?= (?:enters|dies|leaves the battlefield|becomes tapped|attacks))")


# "Whenever one or more other creatures you control with mana value 3 or less enter": read as the singular, once per batch
_ONE_OR_MORE = re.compile(r"Whenever one or more (other )?(nontoken creatures|creature tokens|tokens|creatures|lands|artifacts|"
                          r"enchantments|permanents)( you control| an opponent controls)?( with (?:power \d+ or (?:greater|less)|flying|"
                          r"mana value \d+ or less))? (enter(?: the battlefield)?|die|leave the battlefield)(, .+)")


_SINGULAR = {"nontoken creatures": "nontoken creature", "creature tokens": "creature token", "tokens": "token",
             "creatures": "creature", "lands": "land", "artifacts": "artifact", "enchantments": "enchantment",
             "permanents": "permanent"}


# Watching events whose subject is a permanent, so "it" in the effect can mean that permanent.
_SUBJECT_EVENTS = {"permanent_enters", "creature_dies", "permanent_taps", "permanent_to_graveyard", "creature_attacks"}


_THAT_CREATURE = re.compile(r"\bthat (creature|land)\b", re.I)


_CONTROLLER = r"(?:its|that (?:creature|permanent|land)'s) controller"


_PLAYER_PRONOUNS = [
    (re.compile(rf"\b{_CONTROLLER} (loses|gains|draws|discards|mills)\b", re.I), r"target player \1"),
    (re.compile(rf"\bto {_CONTROLLER}\b", re.I), "to target player"),
    (re.compile(r"\bthey (lose|gain|draw|discard|mill)\b", re.I), r"target player \1s"),
    (re.compile(r"\bthat (?:attacking )?player (loses|gains|draws|discards|mills|sacrifices)\b", re.I), r"target player \1"),
    (re.compile(r"\bhave that player (lose|gain|draw|discard|mill)\b", re.I), r"target player \1s"),
    (re.compile(r"\bto that player\b", re.I), "to target player"),
    (re.compile(r"\bthat opponent (loses|gains|draws|discards|mills)\b", re.I), r"target player \1"),  # Tomik
]


_ABILITY_WORD = re.compile(r"^[A-Z][\w' -]* \u2014 ")  # "Landfall — ", "Constellation — "


# What an Aura says when its creature dies, in terms of "it" (the creature, already gone) and "this card" (the Aura).
_AURA_RETURNS = [
    (re.compile(r"return it to the battlefield under your control\.", re.I),
     lambda: [ReturnDeadToBattlefield(under_owner=False)]),
    (re.compile(r"return that card to the battlefield under its owner's control\. Return this card to the battlefield "
                r"attached to that creature at the beginning of the next end step\.", re.I),
     lambda: [ReturnDeadToBattlefield(under_owner=True), ReturnAuraToBattlefield("end_step", to_host=True)]),
    (re.compile(r"return this card to the battlefield at the beginning of the next end step\.", re.I),
     lambda: [ReturnAuraToBattlefield("end_step")]),
    (re.compile(r"return this card from your graveyard to the battlefield\.", re.I),
     lambda: [ReturnAuraToBattlefield("now")]),
]


_CHOSEN_OF = " of the chosen type"


_ENTERS_OR_ATTACKS = " enters or attacks"


def _watch_triggers(line: str) -> list[tuple[str, Watch, str]]:
    """The watching triggers one line is: a line about "... of the chosen type" is read without that phrase and the watch marked
    `chosen`; "a creature you control of the chosen type enters or attacks" is two watches (Kindred Discovery)."""
    bare = _ABILITY_WORD.sub("", line)
    head, sep, tail = bare.partition(", ")
    if head == "Whenever you create or sacrifice a token":  # Mirkwood Bats: a token entering under your control, or one sacrificed
        return [("permanent_enters", Watch("token", yours=True), tail), ("sacrifice", Watch("token", yours=True), tail)]
    if _CHOSEN_OF not in head:
        found = _watch_trigger(line)
        return [found] if found else []
    head = head.replace(_CHOSEN_OF, "", 1)
    if _ENTERS_OR_ATTACKS in head:
        entering = _watch_trigger(head.replace(_ENTERS_OR_ATTACKS, " enters") + sep + tail)
        if entering is None or not (m := re.fullmatch(r"Whenever a creature you control enters", head.replace(_ENTERS_OR_ATTACKS, " enters"))):
            return []
        return [(entering[0], dataclasses.replace(entering[1], chosen=True), entering[2]),
                ("creature_attacks", Watch("creature", yours=True, chosen=True), tail)]
    found = _watch_trigger(head + sep + tail)
    return [(found[0], dataclasses.replace(found[1], chosen=True), found[2])] if found else []


def _watch_trigger(line: str) -> tuple[str, Watch, str] | None:
    if m := _ONE_OR_MORE.fullmatch(_ABILITY_WORD.sub("", line)):
        verb = {"enter": "enters", "die": "dies"}.get(m[5].split(" ")[0], m[5]) if m[5] not in ("enter the battlefield",) else "enters"
        verb = "leaves the battlefield" if m[5] == "leave the battlefield" else verb
        article = "another" if m[1] else "a"
        single = f"Whenever {article} {_SINGULAR[m[2]]}{m[3] or ''}{m[4] or ''} {verb}{m[6]}"
        found = _watch_trigger(single)
        return (found[0], dataclasses.replace(found[1], batch=True), found[2]) if found else None
    line = _ABILITY_WORD.sub("", line)
    qualifier = ""
    if q := _WATCH_QUALIFIER.search(line):  # "a creature you control with power 4 or greater enters"
        qualifier = (f"{q[2]}{'>=' if q[4] == 'greater' else '<='}{q[3]}" if q[2] else "flying" if q[1] == "flying"
                     else f"mv<={q[5]}" if q[5] else "counter:+1/+1")
        line = line[:q.start()] + line[q.end():]
    if " that targets only this creature" in line:  # Mirrorwing Dragon: about the spell's targets
        line = line.replace(" that targets only this creature", "")
        qualifier = "targets_only_source"
    if " that targets a modified permanent you control" in line:  # Pearl-Ear: about the spell's targets
        line = line.replace(" that targets a modified permanent you control", "")
        qualifier = "targets_modified"
    if m := _WATCHES["cast"].fullmatch(line):
        caster = {"you cast or copy": "you", "you cast": "you", "a player casts": "player",
                  "an opponent casts": "opponent"}[m[1].lower()]
        nth = {"first": 1, "second": 2, "third": 3}.get((m[3] or "").lower(), 0)
        origin = (m[6] or "").strip()
        watch = Watch(m[4].lower(), other=(m[2] or "").lower() == "another", caster=caster, nth_each_turn=nth,
                      with_copy=m[1].lower() == "you cast or copy", mv_at_least=int(m[5] or 0),
                      from_hand=origin == "from your hand", qualifier=qualifier,
                      not_starting_deck=origin == "that isn't from your starting deck",
                      from_zone="graveyard" if "graveyard" in origin else "not_hand" if "other than" in origin else "")
        return "cast", watch, m[7]
    if m := _WATCHES["card_to_graveyard"].fullmatch(line):
        return "card_to_graveyard", Watch(m[1].lower(), yours=True), m[2]
    if m := _WATCHES["sacrifice"].fullmatch(line):  # Tireless Tracker: "Whenever you sacrifice a Clue"
        return "sacrifice", Watch(m[1].lower(), yours=True), m[2]
    if qualifier and (m := _WATCHES["creature_attacks"].fullmatch(line)):  # "a creature you control with power 2 or less attacks"
        return "creature_attacks", Watch("creature", yours=True, qualifier=qualifier), m[1]
    if m := _WATCHES["expend"].fullmatch(line):
        return "expend", Watch("expend", yours=True, expend=int(m[1])), m[2]
    for event in ("permanent_enters", "creature_dies", "permanent_leaves", "permanent_taps", "permanent_to_graveyard"):
        if m := _WATCHES[event].fullmatch(line):
            self_or_other, another, kind = m[1], m[2], m[3].lower()
            under = m[5] if event == "permanent_enters" else None
            own_graveyard = event == "permanent_to_graveyard" and m[5] is not None  # Nether Traitor: "into your graveyard"
            yours = m[4] == " you control" or under == " under your control" or own_graveyard
            theirs = m[4] == " an opponent controls" or under == " under an opponent's control"
            if kind == "enchanted creature":  # Hateful Eidolon: a creature, with an Aura on it
                kind, qualifier = "creature", qualifier or "enchanted"
            watch = Watch(kind.removeprefix("nontoken "), other=bool(another) and not self_or_other,
                          yours=yours, nontoken=kind.startswith("nontoken"), theirs=theirs, qualifier=qualifier)
            return event, watch, m[len(m.groups())]
    return None


_RETURN_EXILED = re.compile(rf"When(?:ever)? {_SELF} leaves the battlefield, return the exiled card to the "
                            r"battlefield under its owner's control\.", re.I)


_OPENING_HAND = "If this card is in your opening hand, you may begin the game with it on the battlefield."


def is_opening_hand_line(line: str) -> bool:
    """Leyline of the Void: the card may start the game on the battlefield (the game offers it after the mulligans)."""
    return line == _OPENING_HAND


def begins_on_battlefield(card: Card) -> bool:
    return any(is_opening_hand_line(line) for line in rules_lines(card))


def is_return_exiled_line(line: str) -> bool:
    """The second half of Oblivion Ring: the engine returns the exiled card when the source leaves."""
    return _RETURN_EXILED.fullmatch(line) is not None


_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


_CHAPTER = re.compile(r"((?:I|II|III|IV|V|VI|VII)(?:, (?:I|II|III|IV|V|VI|VII))*) \u2014 (.+)")


@lru_cache(maxsize=None)
def saga_chapters(card: Card) -> dict[int, tuple[tuple, str]]:
    """A Saga's chapters: number -> (its effects, the line it is printed on). All or nothing: if any chapter isn't
    understood the Saga gets none, so it never does half of what it says."""
    found: dict[int, tuple[tuple, str]] = {}
    if "Saga" not in card.type_line:
        return found
    for line in rules_lines(card):
        if m := _CHAPTER.fullmatch(line):
            effects = _parse(_split_sentences(m[2]))
            if not effects:
                return {}
            for numeral in m[1].split(", "):
                found[_ROMAN[numeral]] = (tuple(effects), line)
    return found


@lru_cache(maxsize=None)
def triggered_abilities(card: Card) -> tuple[TriggeredAbility, ...]:
    """The triggered abilities on a permanent whose effects are all understood."""
    abilities = _triggered_abilities(card)
    for number, (effects, line) in saga_chapters(card).items():  # a lore counter makes the chapter trigger
        abilities.append(TriggeredAbility(f"chapter_{number}", effects, False, line))
    lines = rules_lines(card)
    for number, line in enumerate(lines):  # Backup N gives the abilities written below it
        if m := _BACKUP.fullmatch(line):
            abilities.append(TriggeredAbility("enters", (Backup(int(m[1]), "\n".join(lines[number + 1:])),), False, line))
        if m := _HIDEAWAY.fullmatch(line):
            abilities.append(TriggeredAbility("enters", (Hideaway(int(m[1])),), False, line))
    for line in rules_lines(card):  # persist and undying are keywords that come back from the graveyard
        words = {word.strip().lower() for word in line.split(",")}
        if "prowess" in words:  # whenever you cast a noncreature spell, this gets +1/+1 until end of turn
            abilities.append(TriggeredAbility("cast", (PumpSource(Modifier(1, 1)),), False, "Prowess",
                                              Watch("noncreature spell", caster="you")))
        if "extort" in words:  # whenever you cast a spell, you may pay {W/B}: each opponent loses 1 life and you gain that much
            abilities.append(TriggeredAbility("cast", (MayPay("{W/B}", Drain(1)),), False, "Extort", Watch("spell", caster="you")))
        if "exalted" in words:  # whenever a creature you control attacks alone, that creature gets +1/+1 until end of turn
            abilities.append(TriggeredAbility("attack_alone", (OnSubject(PumpSource(Modifier(1, 1))),), False, "Exalted"))
        for word in words:  # Bushido N, Afflict N, Rampage N: abilities of blocking and being blocked
            if m := _BLOCK_KEYWORD.fullmatch(word):
                n = int(m[2])
                if m[1] == "bushido":
                    abilities += [TriggeredAbility(event, (PumpSource(Modifier(n, n)),), False, word.capitalize())
                                  for event in ("blocks", "becomes_blocked")]
                elif m[1] == "afflict":
                    abilities.append(TriggeredAbility("becomes_blocked", (PlayerLosesLife(n),), False, word.capitalize()))
                else:  # rampage: +N/+N for each creature blocking it beyond the first (the trigger carries that number)
                    abilities.append(TriggeredAbility("becomes_blocked", (PumpSourceX(n, n),), False, word.capitalize()))
        if "living weapon" in words:
            abilities.append(TriggeredAbility("enters", (LivingWeapon(),), False, "Living weapon"))
        for keyword, counter in (("persist", "-1/-1"), ("undying", "+1/+1")):
            if keyword in words:
                abilities.append(TriggeredAbility("dies", (ReturnWithCounter(counter),), False, line,
                                                  condition=Condition("no_counter", what=counter)))
    if any(is_return_exiled_line(line) for line in rules_lines(card)):
        # Two-trigger wording: the enters-the-battlefield exile lasts until this permanent leaves.
        abilities = [
            dataclasses.replace(a, effects=tuple(ExileUntilLeaves(e.target, e.another) if isinstance(e, Exile) else e
                                                 for e in a.effects))
            if a.event == "enters" else a
            for a in abilities]
    return tuple(abilities)


_TRIGGERS_ONCE = " This ability triggers only once each turn."


_BACKUP = re.compile(r"Backup (\d+)")


_BLOCK_KEYWORD = re.compile(r"(bushido|afflict|rampage) (\d+)")


_HIDEAWAY = re.compile(r"Hideaway (\d+)")


_PAY_TO_RETURN = re.compile(r"you may pay ((?:\{[^}]+\})+)\. If you do, return this card from your graveyard to the "
                            r"battlefield\.", re.I)


_MAY_PAY_THEN = re.compile(r"you may pay ((?:\{[^}]+\})+)\. If you do, (.+)", re.I)


_MAY_PAY_LOOT = re.compile(r"you may pay ((?:\{[^}]+\})+) and discard a card\. If you do, draw a card\.", re.I)


_ENDURING = re.compile(r"if it was a creature, return it to the battlefield under its owner's control\. It's an enchantment\.", re.I)


_SYLVAN_BODY = re.compile(r"you may draw two additional cards\. If you do, choose two cards in your hand drawn this turn\. "
                         r"For each of those cards, pay (\d+) life or put the card on top of your library\.", re.I)


_RAGAVAN_BODY = ("create a Treasure token and exile the top card of that player's library. Until end of turn, you may cast that card.")


def _trigger_body(rest: str) -> tuple[list | None, bool, bool, Condition | None]:
    """The part of a trigger after its event: (effects, or None if not understood; "you may";
    "only once each turn"; an intervening "if" clause)."""
    if _ENDURING.fullmatch(rest):
        return [ReturnSelfAsEnchantment()], False, False, None
    if m := _SYLVAN_BODY.fullmatch(rest):
        return [SylvanLibrary(int(m[1]))], False, False, None
    if rest == _RAGAVAN_BODY:
        return [CreateTokens(1, TREASURE), ExileTopOfThatPlayerMayCast()], False, False, None
    if m := _PAY_TO_RETURN.fullmatch(rest):
        return [PayToReturnSelf(m[1])], False, False, None
    if m := _MAY_PAY_LOOT.fullmatch(rest):
        return [MayPayLoot(m[1])], False, False, None
    if m := _MAY_PAY_THEN.fullmatch(rest):
        inner = _parse(_split_sentences(m[2][:1].upper() + m[2][1:]))
        if inner and len(inner) == 1 and not follows_target(inner[0]):
            return [MayPay(m[1], inner[0])], False, False, None
        return None, False, False, None
    condition = None
    if m := re.fullmatch(r"(.+?) if (none of those creatures attacked you)\.?", rest):  # Firemane Commando
        rest, condition = m[1] + ".", _condition(m[2])
    elif rest.startswith("if ") and ", " in rest:
        text, rest = rest[3:].split(", ", 1)
        condition = _condition(text)
        if condition is None:
            return None, False, False, None
    if _MODAL_INLINE.fullmatch(rest):
        return _parse_modal_inline(rest), False, False, condition
    if m := _MODAL_DIFFERENT.fullmatch(rest):  # Shadrix Silverquill
        modal = _parse_modal("two", ["\u2022 " + part for part in m[1].removeprefix("\u2022 ").split(" \u2022 ")])
        if modal is None:
            return None, False, False, None
        different = tuple(tuple(dataclasses.replace(e, distinct=True) if hasattr(e, "distinct") else e for e in mode)
                          for mode in modal[0].modes)
        return [dataclasses.replace(modal[0], modes=different, optional=True)], False, False, condition
    once = rest.endswith(_TRIGGERS_ONCE)
    rest = rest.removesuffix(_TRIGGERS_ONCE)
    optional = rest.lower().startswith("you may ")
    if optional and re.match(r"you may (?:discard|sacrifice|remove) [^.]*\. If you do, ", rest, re.I):
        optional = False  # "you may discard a card. If you do, draw a card" is one effect that asks for itself (see _merge_loot)
    else:
        rest = rest[len("you may "):] if optional else rest
    return _parse(_split_sentences(rest[:1].upper() + rest[1:])), optional, once, condition


_MANA_SPENT = re.compile(r"the amount of mana spent to cast that spell", re.I)


_SAME_NAME = re.compile(r"with the same name as that spell", re.I)  # Aven Shrine


_SPELL_MV = re.compile(r"that spell's mana value", re.I)


_MAY_PAY_OR = re.compile(r"that player may pay ((?:\{[^}]+\})+)\. If the player doesn't, (.+)")


_UNLESS_PAYS = re.compile(r"(.+?) unless that player pays ((?:\{[^}]+\})+)\.?", re.I)


# Phrases whose "it" is not the permanent that set the trigger off: the card a search finds, the creature just targeted.
_PUT_IT = re.compile(r"\bif it has greater power or toughness than (?:this creature|CARDNAME)\b"
                     r"|\bsearch your library for [^.]*?, (?:reveal (?:it|them), )?put (?:it|that card|them) (?:onto|into)\b"
                     r"|\btap up to one target creature and goad it\b|\btap (?:[^.]*? )?target [^.]*? and put \w+ stun counters? on it\b|\bif that enchantment is an Aura, you may attach it to the token\b|\bif you don't, put it into your hand\b|\bthat player copies that spell for each other creature they control that the spell could target\b|\bexcept it has [a-z]+\b|\bexile it\. If you do, create a token that's a copy of it, except it's a Spirit in addition to its other types and it has\b", re.I)


_TOKEN_HAS = re.compile(r'(?:It has|They have) "[^"]*"\.?')


_AURAS_ON_IT = re.compile(r"that was attached to it", re.I)  # Hateful Eidolon: "it" is only the creature that died


_HENGE_BODY = "put a +1/+1 counter on it and draw a card."


def _event_body(rest: str, subject_ok: bool, player_ok: bool) -> tuple[list | None, bool, bool, Condition | None]:
    """Like _trigger_body for a trigger about another object or player. "It" means the permanent that set it off
    (only if every effect is about "it"), "that player" / "they" the player who did it (only for effects that
    target a player); where neither can be pointed at, the line isn't understood."""
    about_player = False
    if subject_ok and rest == _CONTRACT_BODY:  # Contract: both sentences are about the enchanted creature
        return [ContractAttack()], False, False, None
    if subject_ok and rest == _HENGE_BODY:  # The Great Henge: a counter on the creature, and a card for you
        return [OnSubject(PutCountersOnSource(1, "+1/+1")), Draw(1)], False, False, None
    if subject_ok and not player_ok and re.search(r"\bits controller (loses|gains|draws|discards|mills)\b", rest, re.I):
        # "Whenever enchanted creature attacks, its controller loses 2 life and you gain 2 life."
        rewritten = re.sub(r"\bits controller (loses|gains|draws|discards|mills)\b", r"target player \1", rest, flags=re.I)
        effects, optional, once, condition = _trigger_body(rewritten)
        if effects is None:
            return None, False, False, None
        return ([OnSubjectController(e) if getattr(e, "target", None) == "player" else e for e in effects],
                optional, once, condition)
    if player_ok and (m := _MAY_PAY_OR.fullmatch(rest)):  # "that player may pay {2}. If the player doesn't, you create ..."
        rest = f"{re.sub('^you ', '', m[2].rstrip('.'))} unless that player pays {m[1]}."
    if player_ok:  # before "that creature" becomes "it": "that creature's controller" names the player who controls it
        before = rest
        for pattern, replacement in _PLAYER_PRONOUNS[:2]:
            rest = pattern.sub(replacement, rest)
        about_player = rest != before
    rest = _THAT_CREATURE.sub("it", rest)
    if player_ok and (m := re.fullmatch(r"(.+?) unless that player pays \{X\}, where X is this creature's power\.", rest, re.I)):  # Esper Sentinel
        effects, optional, once, condition = _trigger_body(m[1] + ".")
        if effects is None or any(target_kind(e) or uses_source(e) or uses_subject(e) or uses_player(e) or follows_target(e) for e in effects):
            return None, False, False, None
        return [UnlessPays(tuple(effects), "", cost_power=True)], optional, once, condition
    if player_ok and (m := _UNLESS_PAYS.fullmatch(rest)):
        effects, optional, once, condition = _trigger_body(m[1] + ".")
        if effects is None or any(target_kind(e) or uses_source(e) or uses_subject(e) or uses_player(e)
                                  or follows_target(e) for e in effects):
            return None, False, False, None
        return [UnlessPays(tuple(effects), m[2])], optional, once, condition
    if player_ok:
        replaced = rest
        for pattern, replacement in _PLAYER_PRONOUNS:
            replaced = pattern.sub(replacement, replaced)
        about_player, rest = about_player or replaced != rest, replaced
    # "the amount of mana spent to cast that spell" is an amount the trigger carries, not an effect on the spell.
    # (a created token's own ability, "It has "Sacrifice this token: Add {C}."", is about the token, not the creature that died)
    without_token_ability = _AURAS_ON_IT.sub("", _TOKEN_HAS.sub("", rest) if re.search(r"\btokens?\b", rest, re.I) else rest)
    about_subject = re.search(r"\bit\b|\bthat spell\b", _PUT_IT.sub("", _MANA_SPENT.sub("", _SPELL_MV.sub("", _SPELL_COLORS.sub("", _SAME_NAME.sub("", without_token_ability))))), re.I) is not None
    copies_spell = re.match(r"(?:you may )?copy (it|that spell)\.", rest, re.I) is not None  # Codie: "it" is the spell cast
    effects, optional, once, condition = _trigger_body(rest)
    if effects is None:
        return None, False, False, None
    if about_subject and any(isinstance(e, CreateTokens) and e.counters for e in effects) \
            and not any(uses_source(e) or follows_target(e) for e in effects):
        about_subject = False  # the "it" was the new token of "Create a ... token. Put X counters on it." (Deekah)
    if about_subject and not subject_ok and not copies_spell:
        return None, False, False, None
    if copies_spell and not subject_ok:
        return effects, optional, once, condition
    if about_player:
        aimed = [getattr(e, "target", None) in ("player", "opponent", "any") for e in effects]
        # An effect not about "that player" (Knights of the Black Rose: "... and you gain 2 life") may share the line.
        if not any(aimed) or any(not a and (target_kind(e) or uses_player(e) or uses_subject(e))
                                 for a, e in zip(aimed, effects)):
            return None, False, False, None
        effects = [OnPlayer(e) if a else e for a, e in zip(aimed, effects)]
    elif about_subject:
        if not all(uses_source(e) or uses_subject(e) for e in effects):
            return None, False, False, None
        effects = [OnSubject(e) if uses_source(e) else e for e in effects]
    return effects, optional, once, condition


_COMPOUND_TRIGGER = re.compile(r"(When|Whenever) ([^,]+?) and whenever ([^,]+), (.+)")


_UNBOUND_COPY = re.compile(r"Whenever you cast an instant or sorcery spell or activate an ability, if that spell's mana cost or that "
                           r"ability's activation cost contains \{X\}, copy that spell or ability\. You may choose new targets for "
                           r"the copy\.")


def _split_compound_trigger(line: str) -> list[tuple[str, str]]:
    """ "When this creature enters and whenever one or more tokens you control enter, <effect>" is two triggers with the same
    effect; each is read as a line of its own, as (line to read, the card's own line)."""
    if _UNBOUND_COPY.fullmatch(line):  # Unbound Flourishing: one sentence for a spell and for an ability
        return [("Whenever you cast an instant or sorcery spell with {X} in its mana cost, copy that spell. You may choose new targets "
                 "for the copy.", line),
                ("Whenever you activate an ability with {X} in its activation cost, copy that ability. You may choose new targets for "
                 "the copy.", line)]
    if m := _COMPOUND_TRIGGER.fullmatch(line):
        return [(f"{m[1]} {m[2]}, {m[4]}", line), (f"Whenever {m[3]}, {m[4]}", line)]
    return [(line, line)]


def _triggered_abilities(card: Card) -> list[TriggeredAbility]:
    abilities = []
    for raw in _rules_text(card).splitlines():
        parts = [_trigger_part(line, text) for line, text in _split_compound_trigger(raw.strip())]
        # A line that is several triggers ("When this enters and whenever an opponent draws ...") works only if every one of them
        # is understood: half of what it says is not what the card does (and the audit must not call it playable).
        if len(parts) > 1 and any(not found for found in parts):
            continue
        for found in parts:
            abilities.extend(found or ())
    return abilities


def _trigger_part(line: str, text: str) -> list[TriggeredAbility] | None:
    """The triggered abilities one line (or one half of a compound line) is: [] if it is not a trigger, None if it is
    one that isn't fully understood."""
    bare = _ABILITY_WORD.sub("", line)  # patterns read the line without "Council's dilemma — "; its text stays whole
    if watched := _watch_triggers(line):
        found = []
        for event, watch, rest in watched:
            effects, optional, once, condition = _event_body(
                rest, event in _SUBJECT_EVENTS,
                (event == "cast" and watch.caster != "you") or event in _SUBJECT_EVENTS)
            if effects is None:
                return None
            found.append(TriggeredAbility(event, tuple(effects), optional, text, watch, once, condition))
        return found
    if several := _SEVERAL_EVENTS.fullmatch(bare):
        effects, optional, once, condition = _trigger_body(several[2])
        if effects is None:
            return None
        names = several[1].split(" or ")
        return [TriggeredAbility(event, tuple(effects), optional, text, once_per_turn=once, condition=condition)
                for event, pattern in _SELF_EVENTS.items() if any(re.fullmatch(pattern, part, re.I) for part in names)]
    for event in EVENTS.values():
        match = event.text.fullmatch(bare)
        if not match:
            continue
        aura_return = next((build() for pattern, build in _AURA_RETURNS if event.name == "host_dies"
                            and pattern.fullmatch(match[1])), None)
        if aura_return is not None:
            effects, optional, once, condition = aura_return, False, False, None
        elif event.about_creature or event.about_player or event.host_gone:
            effects, optional, once, condition = _event_body(match[1], event.about_creature, event.about_player)
        else:
            effects, optional, once, condition = _trigger_body(match[1])
        if effects is not None and event.name != "dies" and any(isinstance(e, (ReturnSelfToBattlefield, ReturnSelfAsEnchantment)) for e in effects):
            effects = None  # "return it to the battlefield": it is only gone when the creature has died
        if effects is None:
            return None
        return [TriggeredAbility(event.name, tuple(effects), optional, text, once_per_turn=once, condition=condition)]
    return []
