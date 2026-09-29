"""Card effects: reading rules text into things the game does.

Rules text is matched sentence by sentence against known templates. A spell
gets effects only if every sentence is understood; otherwise it resolves with
no effect and the game reports it as unsupported, instead of doing part of
what the card says. Triggered abilities on permanents ("When this creature
enters, draw a card.") use the same templates for what they do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable

from .cards import Card
from .characteristics import Modifier

if TYPE_CHECKING:
    from .game import Game, Seat

_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_N = r"(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+|X)"
_REMINDER = re.compile(r"\s*\([^)]*\)")
_SELF = r"(?:CARDNAME|it|this (?:spell|creature|artifact|enchantment|land|planeswalker|permanent))"


def _count(word: str) -> int | str:
    """A number from rules text; "X" stays "X" and the game fills it in (Game.amount)."""
    if word == "X":
        return "X"
    return int(word) if word.isdigit() else _NUMBERS[word.lower()]


def _rules_text(card: Card) -> str:
    """Oracle text without reminder text, with the card's own name as CARDNAME.

    Legendary cards often call themselves by their short name ("Omnath" for
    "Omnath, Locus of Rage"), and double-faced cards by their front face's name.
    """
    text = _REMINDER.sub("", card.oracle_text)
    front = card.name.split(" // ")[0]
    for name in dict.fromkeys((card.name, front, front.split(",")[0])):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "CARDNAME", text)
    return text


def rules_lines(card: Card) -> list[str]:
    """The card's rules text, one ability per line, as the other functions here see it."""
    return [line.strip() for line in _rules_text(card).splitlines() if line.strip()]


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for line in text.splitlines() for s in re.split(r"(?<=\.)\s+", line) if s.strip()]


def target_kind(effect: Any) -> str | None:
    """What an effect targets ("any", "creature", "spell", ...), or None."""
    return getattr(effect, "target", None)


def uses_source(effect: Any) -> bool:
    """Whether an effect acts on its ability's source ("put a +1/+1 counter on it")."""
    return getattr(effect, "uses_source", False)


def follows_target(effect: Any) -> bool:
    """Whether an effect acts on the previous effect's target ("Its controller gains life ...")."""
    return getattr(effect, "follows_target", False)


@dataclass(frozen=True)
class Draw:
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.draw(controller, game.amount(self.count))


@dataclass(frozen=True)
class GainLife:
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.change_life(controller, game.amount(self.amount))


@dataclass(frozen=True)
class OpponentsLoseLife:
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            game.change_life(seat, -game.amount(self.amount))


@dataclass(frozen=True)
class Damage:
    amount: int
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.damage(target, game.amount(self.amount))


@dataclass(frozen=True)
class Destroy:
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.destroy(target)


@dataclass(frozen=True)
class Counter:
    target: str = "spell"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.counter(target)


@dataclass(frozen=True)
class Exile:
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile(target)


@dataclass(frozen=True)
class ExileGraveyard:
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_graveyard(target)


@dataclass(frozen=True)
class TargetControllerGainsLifeEqualToPower:
    """Swords to Plowshares: "Its controller gains life equal to its power." """
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.change_life(target.last_controller, max(0, target.last_power))


@dataclass(frozen=True)
class TargetControllerMayFetchBasicLand:
    """Path to Exile: "Its controller may search their library for a basic land card, ..." """
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.fetch_basic_land(target.last_controller, optional=True)


@dataclass(frozen=True)
class PutCounters:
    count: int
    counter: str  # "+1/+1" or "-1/-1"
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))


@dataclass(frozen=True)
class PutCountersOnEach:
    """ "Put a +1/+1 counter on each creature you control." """
    count: int
    counter: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line:
                game.put_counters(permanent, self.counter, game.amount(self.count))


@dataclass(frozen=True)
class PutCountersOnSource:
    """ "Whenever this creature attacks, put a +1/+1 counter on it." """
    count: int
    counter: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))


_COUNTER = r"([+\-\u2212]1/[+\-\u2212]1) counters?"


def _counter_name(text: str) -> str:
    return text.replace("\u2212", "-")


_ENTERS_WITH = re.compile(rf"{_SELF} enters with {_N} {_COUNTER} on it\.", re.I)


def enters_with_counters(card: Card) -> dict[str, int | str]:
    """Counters from "This creature enters with N (or X) +1/+1 counters on it." """
    counters: dict[str, int | str] = {}
    for line in rules_lines(card):
        if m := _ENTERS_WITH.fullmatch(line):
            name, count = _counter_name(m[2]), _count(m[1])
            counters[name] = count if count == "X" else counters.get(name, 0) + count
    return counters


def is_enters_with_counters(line: str) -> bool:
    return _ENTERS_WITH.fullmatch(line) is not None


def _signed(text: str) -> int:
    return int(text.replace("\u2212", "-"))


def _keyword_list(text: str) -> frozenset[str]:
    """ "flying", "flying and vigilance", "flying, vigilance, and trample" -> {"flying", ...}"""
    return frozenset(w.strip().lower() for w in re.split(r",? and |, ", text) if w.strip())


@dataclass(frozen=True)
class Pump:
    """ "Target creature gets +3/+3 (and gains trample) until end of turn." """
    modifier: Modifier
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.modify_until_end_of_turn(target, self.modifier)


@dataclass(frozen=True)
class PumpSource:
    """ "This creature gets +1/+0 until end of turn." """
    modifier: Modifier
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.modify_until_end_of_turn(target, self.modifier)


@dataclass(frozen=True)
class PumpEach:
    """ "Creatures you control get +3/+3 and gain trample until end of turn." Affects only the
    creatures there when it resolves (CR 611.2c)."""
    modifier: Modifier

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line:
                game.modify_until_end_of_turn(permanent, self.modifier)


_PT = r"([+\-\u2212]\d+)/([+\-\u2212]\d+)"
_KEYWORDS = r"([a-z]+(?: [a-z]+)?(?:(?:,? and |, )[a-z]+(?: [a-z]+)?)*)"
# "gets +3/+3", "gets +2/+0 and gains trample", "gains flying" (one or both parts), then "until end of turn."
_CHANGE = rf"(?:gets? {_PT}(?: and gains? {_KEYWORDS})?|gains? {_KEYWORDS}) until end of turn\."


def _modifier(m: re.Match, first: int) -> Modifier:
    p, t, keywords_with_pt, keywords_only = m.group(first, first + 1, first + 2, first + 3)
    keywords = keywords_with_pt or keywords_only
    return Modifier(_signed(p) if p else 0, _signed(t) if t else 0, _keyword_list(keywords) if keywords else frozenset())


@dataclass(frozen=True)
class StaticBuff:
    """ "(Other) (Elf) creatures you control get +1/+1 (and have flying)." while its source is on the battlefield."""
    modifier: Modifier
    other: bool  # "Other ...": not the source itself
    subtype: str | None  # "Elf" in "Other Elf creatures you control"
    text: str


_AFFECTED = r"(?:(Other) )?(?:([A-Z][\w'-]*) )?[Cc]reatures you control"
_STATIC = re.compile(rf"{_AFFECTED} (?:get {_PT}(?: and have {_KEYWORDS})?|have {_KEYWORDS})\.")


@lru_cache(maxsize=None)
def static_abilities(card: Card) -> tuple[StaticBuff, ...]:
    buffs = []
    for line in rules_lines(card):
        if m := _STATIC.fullmatch(line):
            buffs.append(StaticBuff(_modifier(m, 3), m[1] is not None, m[2], line))
    return tuple(buffs)


@dataclass(frozen=True)
class CreateTokens:
    count: int
    token: Card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.create_tokens(controller, self.token, game.amount(self.count))


@dataclass(frozen=True)
class TargetControllerCreatesTokens:
    """Beast Within: "Its controller creates a 3/3 green Beast creature token." """
    count: int
    token: Card
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.create_tokens(target.last_controller, self.token, game.amount(self.count))


TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure",
                oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")
CLUE = Card(name="Clue", type_line="Token Artifact — Clue", oracle_text="{2}, Sacrifice this artifact: Draw a card.")
FOOD = Card(name="Food", type_line="Token Artifact — Food",
            oracle_text="{2}, {T}, Sacrifice this artifact: You gain 3 life.")
_NAMED_TOKENS = {"treasure": TREASURE, "clue": CLUE, "food": FOOD}
_COLOR_WORDS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
_COLOR = r"(?:white|blue|black|red|green)"
_CREATURE_TOKEN = re.compile(
    rf"{_N} (\d+)/(\d+) (colorless|{_COLOR}(?:(?:,? and |, ){_COLOR})*) ((?:[A-Z][\w'-]* )+)(artifact )?"
    r"creature tokens?(?: with ([a-z ,]+))?"
)
_NAMED_TOKEN = re.compile(rf"(?i:{_N}) (Treasure|Clue|Food) tokens?")


def _token(spec: str) -> tuple[int, Card] | None:
    """Parse "a 1/1 white Soldier creature token with flying" or "two Treasure tokens"."""
    if m := _NAMED_TOKEN.fullmatch(spec):
        return _count(m[1]), _NAMED_TOKENS[m[2].lower()]
    m = _CREATURE_TOKEN.fullmatch(spec)
    if not m:
        return None
    count, power, toughness, colors, subtypes, artifact, keywords = m.groups()
    keyword_line = ""
    if keywords:
        words = [w.strip() for w in re.split(r",? and |, ", keywords) if w.strip()]
        keyword_line = ", ".join(words).capitalize()
    card = Card(
        name=subtypes.strip(),
        type_line=f"Token {'Artifact ' if artifact else ''}Creature — {subtypes.strip()}",
        oracle_text=keyword_line,
        colors=tuple(_COLOR_WORDS[c] for c in re.findall(_COLOR, colors)),
        power=power,
        toughness=toughness,
    )
    return _count(count), card


def _create(m: re.Match, follows: bool) -> Any:
    parsed = _token(m[1])
    if parsed is None:
        return None
    return (TargetControllerCreatesTokens if follows else CreateTokens)(*parsed)


@dataclass(frozen=True)
class FetchBasicLand:
    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fetch_basic_land(controller)


_PERMANENT_KIND = (r"((?:creature|artifact|enchantment|planeswalker|nonland permanent|permanent|artifact or enchantment"
                   r"|creature or planeswalker)(?: an opponent controls| you don't control| you control)?)")
_DAMAGE_KIND = r"(any target|target creature|target player|target creature or planeswalker|target player or planeswalker)"

_TEMPLATES: list[tuple[re.Pattern, Callable[[re.Match], Any]]] = [
    (re.compile(rf"draw {_N} cards?\.", re.I), lambda m: Draw(_count(m[1]))),
    (re.compile(rf"you gain {_N} life\.", re.I), lambda m: GainLife(_count(m[1]))),
    (re.compile(rf"each opponent loses {_N} life\.", re.I), lambda m: OpponentsLoseLife(_count(m[1]))),
    (re.compile(rf"{_SELF} deals {_N} damage to {_DAMAGE_KIND}\.", re.I),
     lambda m: Damage(_count(m[1]), "any" if m[2].lower() == "any target" else m[2].lower().removeprefix("target "))),
    (re.compile(rf"destroy target {_PERMANENT_KIND}\.", re.I), lambda m: Destroy(m[1].lower())),
    (re.compile(r"counter target spell\.", re.I), lambda m: Counter()),
    (re.compile(rf"exile target {_PERMANENT_KIND}\.", re.I), lambda m: Exile(m[1].lower())),
    (re.compile(r"exile target player's graveyard\.", re.I), lambda m: ExileGraveyard()),
    (re.compile(rf"put {_N} {_COUNTER} on target {_PERMANENT_KIND}\.", re.I),
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"put {_N} {_COUNTER} on each creature you control\.", re.I),
     lambda m: PutCountersOnEach(_count(m[1]), _counter_name(m[2]))),
    (re.compile(rf"put {_N} {_COUNTER} on {_SELF}\.", re.I),
     lambda m: PutCountersOnSource(_count(m[1]), _counter_name(m[2]))),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} {_CHANGE}"), lambda m: Pump(_modifier(m, 2), m[1].lower())),
    (re.compile(rf"(?i:{_SELF}) {_CHANGE}"), lambda m: PumpSource(_modifier(m, 1))),
    (re.compile(rf"(?i:creatures you control) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1))),
    (re.compile(r"(?i:create) (.+)\."), lambda m: _create(m, follows=False)),
    (re.compile(r"(?i:its controller creates) (.+)\."), lambda m: _create(m, follows=True)),
    (re.compile(r"its controller gains life equal to its power\.", re.I), lambda m: TargetControllerGainsLifeEqualToPower()),
    (re.compile(r"its controller may search their library for a basic land card, put (?:it|that card) onto the "
                r"battlefield tapped, then shuffle\.", re.I), lambda m: TargetControllerMayFetchBasicLand()),
    (re.compile(r"search your library for a basic land card, put it onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: FetchBasicLand()),
]


def _parse(sentences: list[str]) -> list | None:
    effects = []
    for sentence in sentences:
        for pattern, build in _TEMPLATES:
            match = pattern.fullmatch(sentence)
            effect = build(match) if match else None
            if effect is not None:
                effects.append(effect)
                break
        else:
            return None
    return effects


def spell_effects(card: Card) -> list | None:
    """Effects of an instant or sorcery, in order; None if any sentence isn't understood."""
    return _parse(_split_sentences(_rules_text(card)))


def line_effects(line: str) -> list | None:
    """Effects of one line of spell text (from rules_lines); None if not understood."""
    return _parse(_split_sentences(line))


@dataclass(frozen=True)
class TriggeredAbility:
    event: str  # one of TRIGGER_EVENTS
    effects: tuple
    optional: bool  # "you may ...": the controller chooses when it resolves
    text: str


_TRIGGERS = {
    "enters": re.compile(rf"When(?:ever)? {_SELF} enters(?: the battlefield)?, (.+)", re.I),
    "dies": re.compile(rf"When(?:ever)? {_SELF} dies, (.+)", re.I),
    "attacks": re.compile(rf"Whenever {_SELF} attacks, (.+)", re.I),
    "combat_damage_to_player": re.compile(rf"Whenever {_SELF} deals combat damage to a player, (.+)", re.I),
    "upkeep": re.compile(r"At the beginning of your upkeep, (.+)", re.I),
    "end_step": re.compile(r"At the beginning of your end step, (.+)", re.I),
}
TRIGGER_EVENTS = tuple(_TRIGGERS)


@lru_cache(maxsize=None)
def triggered_abilities(card: Card) -> tuple[TriggeredAbility, ...]:
    """The triggered abilities on a permanent whose effects are all understood."""
    abilities = []
    for line in _rules_text(card).splitlines():
        line = line.strip()
        for event, pattern in _TRIGGERS.items():
            match = pattern.fullmatch(line)
            if not match:
                continue
            rest = match[1]
            optional = rest.lower().startswith("you may ")
            if optional:
                rest = rest[len("you may "):]
            effects = _parse(_split_sentences(rest[:1].upper() + rest[1:]))
            if effects is not None:
                abilities.append(TriggeredAbility(event, tuple(effects), optional, line))
            break
    return tuple(abilities)


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


_ACTIVATED = re.compile(r"([^:\"]+): (.+)")
_MANA_PART = re.compile(r"(\{(?:\d+|[WUBRGC]|[WUBRGC]/[WUBRGCP])\})+")
_SACRIFICE_SELF = re.compile(rf"Sacrifice {_SELF}", re.I)
_PAY_LIFE = re.compile(rf"Pay {_N} life", re.I)
_LOYALTY = re.compile(r"([+\u2212-]?)(\d+)")
_SORCERY_ONLY = "Activate only as a sorcery."
_ONCE_EACH_TURN = "Activate only once each turn."


@lru_cache(maxsize=None)
def activated_abilities(card: Card) -> tuple[ActivatedAbility, ...]:
    """Activated abilities ("{1}, {T}, Sacrifice this artifact: Draw a card.") whose
    costs and effects are all understood. Mana abilities are handled by mana_ability."""
    planeswalker = "Planeswalker" in card.type_line
    abilities = []
    for line in rules_lines(card):
        match = _ACTIVATED.fullmatch(line)
        if not match or is_mana_ability(line):
            continue
        ability = _parse_activated(line, match[1], match[2], planeswalker)
        if ability is not None:
            abilities.append(ability)
    return tuple(abilities)


def _parse_activated(line: str, cost: str, effect: str, planeswalker: bool) -> ActivatedAbility | None:
    fields: dict[str, Any] = {}
    loyalty = _LOYALTY.fullmatch(cost)
    if planeswalker and loyalty:
        amount = int(loyalty[2])
        fields.update(loyalty=-amount if loyalty[1] in ("\u2212", "-") else amount, sorcery_speed=True)
    else:
        for part in cost.split(", "):
            if _MANA_PART.fullmatch(part):
                fields["mana_cost"] = fields.get("mana_cost", "") + part
            elif part == "{T}":
                fields["tap"] = True
            elif _SACRIFICE_SELF.fullmatch(part):
                fields["sacrifice"] = True
            elif (m := _PAY_LIFE.fullmatch(part)) and m[1] != "X":
                fields["life"] = _count(m[1])
            else:
                return None
    sentences = _split_sentences(effect)
    if _SORCERY_ONLY in sentences:
        fields["sorcery_speed"] = True
        sentences.remove(_SORCERY_ONLY)
    if _ONCE_EACH_TURN in sentences:
        fields["once_per_turn"] = True
        sentences.remove(_ONCE_EACH_TURN)
    effects = _parse(sentences)
    if not effects:
        return None
    return ActivatedAbility(line, tuple(effects), **fields)


_TAP = r"\{T\}(, Sacrifice (?:CARDNAME|this (?:artifact|creature|permanent|land)))?: Add "  # group 1: sacrifice
_ADD_SYMBOLS = re.compile(_TAP + r"((?:\{[WUBRGC]\})+)\.")
_ADD_EITHER = re.compile(_TAP + r"\{([WUBRGC])\} or \{([WUBRGC])\}\.")
_ADD_ANY = re.compile(_TAP + r"one mana of any color\.")
_ADD_IDENTITY = re.compile(_TAP + r"one mana of any color in your commander's color identity\.")


def mana_ability(card: Card, commander_identity: frozenset[str]) -> list[frozenset[str]] | None:
    """The mana a nonland permanent makes when tapped, one set of options per mana.

    Covers "{T}: Add {C}{C}." (Sol Ring), "{T}: Add {G}." (mana creatures),
    "{T}: Add {R} or {G}.", and "one mana of any color" (optionally limited
    to your commander's color identity), each optionally with "Sacrifice this
    artifact" in the cost (Treasure).
    """
    line = _mana_line(card)
    return _mana_from_line(line, commander_identity) if line else None


def mana_ability_sacrifices(card: Card) -> bool:
    """Whether using the card's mana ability sacrifices it (Treasure)."""
    line = _mana_line(card)
    return bool(line and any((m := p.fullmatch(line)) and m[1] for p in _MANA_PATTERNS))


def _mana_line(card: Card) -> str | None:
    """The card's plain "{T}: Add ..." line (Signet-style lines are filter_mana_ability's)."""
    return next((line for line in rules_lines(card) if any(p.fullmatch(line) for p in _MANA_PATTERNS)), None)


_MANA_PATTERNS = (_ADD_SYMBOLS, _ADD_EITHER, _ADD_ANY, _ADD_IDENTITY)


def is_mana_ability(line: str) -> bool:
    return any(p.fullmatch(line) for p in _MANA_PATTERNS) or _FILTER.fullmatch(line) is not None


_FILTER = re.compile(r"((?:\{\d+\}|\{[WUBRGC]\})+), \{T\}: Add ((?:\{[WUBRGC]\})+)\.")


def filter_mana_ability(card: Card) -> tuple[str, list[frozenset[str]]] | None:
    """A mana ability that costs mana, like a Signet's "{1}, {T}: Add {W}{U}.":
    (the mana it costs, the mana it makes, one set per mana)."""
    for line in rules_lines(card):
        if m := _FILTER.fullmatch(line):
            return m[1], [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2])]
    return None


def _mana_from_line(line: str, commander_identity: frozenset[str]) -> list[frozenset[str]] | None:
    if m := _ADD_SYMBOLS.fullmatch(line):
        return [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2])]
    if m := _ADD_EITHER.fullmatch(line):
        return [frozenset((m[2], m[3]))]
    if _ADD_ANY.fullmatch(line):
        return [frozenset("WUBRG")]
    return [commander_identity] if commander_identity else None
