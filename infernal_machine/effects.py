"""Card effects: reading rules text into things the game does.

Rules text is matched sentence by sentence against known templates. A spell
gets effects only if every sentence is understood; otherwise it resolves with
no effect and the game reports it as unsupported, instead of doing part of
what the card says. Triggered abilities on permanents ("When this creature
enters, draw a card.") use the same templates for what they do.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable

from .cards import Card
from .characteristics import LOSES_HEXPROOF, Modifier

if TYPE_CHECKING:
    from .game import Game, Seat

_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_VOTE_PREFIX = r"(?:[A-Z][\w' -]* \u2014 )?"  # "Will of the council — ", "Council's dilemma — "
_N = r"(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+|X)"
_REMINDER = re.compile(r"\s*\([^)]*\)")
_SELF = (r"(?:CARDNAME|it|this (?:spell|creature|artifact|enchantment|land|planeswalker|permanent"
         r"|Aura|Equipment|Class|Vehicle|Saga|token))")


def _count(word: str) -> int | str:
    """A number from rules text; "X" stays "X" ("twice X" is "2X") and the game fills it in (Game.amount)."""
    if word == "X":
        return "X"
    if word == "twice X":
        return "2X"
    if word in ("half X", "half X down"):
        return "hX"
    if word == "half X up":
        return "hX+"
    return int(word) if word.isdigit() else _NUMBERS[word.lower()]


def _rules_text(card: Card) -> str:
    """Oracle text without reminder text, with the card's own name as CARDNAME.

    Legendary cards often call themselves by their short name ("Omnath" for
    "Omnath, Locus of Rage", "Kaalia" for "Kaalia of the Vast"), and double-faced cards by their front face's name.
    """
    text = _REMINDER.sub("", card.oracle_text)
    front = card.name.split(" // ")[0]
    short = front.split(",")[0]
    if "," not in front and "Legendary" in card.type_line and " " in front and front.split(" ")[0] not in ("The", "A", "An"):
        short = front.split(" ")[0]  # "Kaalia" for Kaalia of the Vast, "Edgar" for Edgar Markov
    for name in dict.fromkeys((card.name, front, front.split(",")[0], short)):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "CARDNAME", text)
    return _join_modes(text)


# "When this creature enters, choose one —" and "{T}: Choose one —" are followed by their modes on separate lines.
_MODAL_LEAD = re.compile(r".+[,:] choose (?:one or both|one or more|up to one|one|two|three) \u2014"
                         r"|.+, you may choose two\. Each mode must target a different player\.", re.I)


def _join_modes(text: str) -> str:
    """Put the modes of a modal triggered or activated ability on its own line, so it is one ability like any other
    ("When ... enters, choose one — \u2022 Scry 2. \u2022 You gain 3 life."). A modal spell keeps its lines."""
    lines: list[str] = []
    joining = False
    for line in text.splitlines():
        if joining and line.strip().startswith("\u2022 "):
            lines[-1] += " " + line.strip()
            continue
        joining = _MODAL_LEAD.fullmatch(line.strip()) is not None
        lines.append(line)
    return "\n".join(lines)


def rules_lines(card: Card) -> list[str]:
    """The card's rules text, one ability per line, as the other functions here see it."""
    return [line.strip() for line in _rules_text(card).splitlines() if line.strip()]


_WHOLE_LINE = re.compile(
    r"Each player puts a vow counter on a creature they control and sacrifices the rest\. Each of those creatures can't attack "
    r"you or planeswalkers you control for as long as it has a vow counter on it\."
    r"|Shuffle your library, then reveal cards from the top of it until you reveal a nonland card\. .*"
    r"|Shuffle your library\. As many times as you choose, you may exile the top card of your library\. .*"
    r"|Remove all counters from target nonland permanent you control\. Draw a card for each counter removed this way\."
    r"|When you next cast an instant or sorcery spell this turn, copy that spell\. You may choose new targets for the copy\."
    r"|You gain half X life and draw half X cards\. Round down each time\."
    r"|Mill a card, then exile a card from your graveyard at random\. You may play the exiled card this turn\."
    r"|Exile that card from your graveyard\. If you do, you may (?:play|cast) that card this turn\."
    r"|Look at the top (?:six|seven|eight) cards of your library\. Put (?:two|three) of them into your hand and the rest on the "
    r"bottom of your library in any order\."
    r"|You may put a \+1/\+1 counter on a creature\. Then choose odd or even\. Return each creature with power of the chosen "
    r"quality to its owner's hand\.", re.I)


def _split_sentences(text: str) -> list[str]:
    """The sentences of each line; a few effects (Creative Technique's) are one template across several sentences."""
    return [s.strip() for line in text.splitlines()
            for s in ([line] if _WHOLE_LINE.fullmatch(line.strip()) else re.split(r'(?<=\.)\s+|(?<=\.")\s+(?=[A-Z])', line)) if s.strip()]


def target_kind(effect: Any) -> str | None:
    """What an effect targets ("any", "creature", "spell", ...), or None."""
    return getattr(effect, "target", None)


def uses_source(effect: Any) -> bool:
    """Whether an effect acts on its ability's source ("put a +1/+1 counter on it")."""
    return getattr(effect, "uses_source", False)


def uses_subject(effect: Any) -> bool:
    """Whether an effect acts on the permanent that set off a watching trigger ("... put a counter on it")."""
    return getattr(effect, "uses_subject", False)


def uses_player(effect: Any) -> bool:
    """Whether an effect acts on the player who set off a watching trigger ("... that player loses 2 life")."""
    return getattr(effect, "uses_player", False)


def follows_target(effect: Any) -> bool:
    """Whether an effect acts on the previous effect's target ("Its controller gains life ...")."""
    return getattr(effect, "follows_target", False)


@dataclass(frozen=True)
class Draw:
    count: int
    more: int = 0  # Zimone: "If you control eight or more lands, draw two cards instead."
    more_if: "Condition | None" = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = self.more if self.more_if and game.condition_holds(self.more_if, controller, game.resolving_source) else self.count
        game.draw(controller, game.amount(count))


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
    optional_target: bool = False  # one point of "4 damage divided as you choose among any number of targets"
    distinct: bool = False  # "... to each of up to two targets": the second can't be the first again

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.damage(target, game.amount(self.amount))


@dataclass(frozen=True)
class Destroy:
    target: str
    another: bool = False  # "destroy another target ...": not the source itself
    no_regen: bool = False  # "It can't be regenerated."
    optional_target: bool = False  # "destroy up to two target ...": each target may be left out
    distinct: bool = False  # ... and may not repeat an earlier target of the same effect

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.destroy(target, self.no_regen)


@dataclass(frozen=True)
class WardCounter:
    """The ward trigger of a permanent an opponent targeted: their spell or ability is countered
    unless they pay `cost`."""
    cost: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.resolve_ward(self.cost)


@dataclass(frozen=True)
class Counter:
    target: str = "spell"
    exile: bool = False  # "exile it instead of putting it into its owner's graveyard"
    delayed_mana: bool = False  # Mana Drain: at your next main phase, add {C} equal to that spell's mana value
    unless: str = ""  # "unless its controller pays {2}": the cost

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and not cant_be_countered(target.card):
            if self.unless and game.pays_unless(target.controller, self.unless, target.card):
                return
            if self.delayed_mana:
                controller.delayed_mana += int(target.card.cmc) + target.x
            game.counter(target, self.exile)


@dataclass(frozen=True)
class DelayedDraw:
    """Arcane Denial: "Its controller may draw up to two cards at the beginning of the next turn's upkeep. / You draw a card at the
    beginning of the next turn's upkeep." Its controller is the controller of the spell just countered."""
    count: int
    others: bool  # the countered spell's controller rather than you
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        who = (target.controller if target is not None else None) if self.others else controller
        if who is not None:
            game.draw_at_next_upkeep(who, self.count, up_to=self.others)


@dataclass(frozen=True)
class _DelayedMana:
    """Mana Drain's second sentence (see _merge_exile)."""


@dataclass(frozen=True)
class ChaosWarp:
    """ "The owner of target permanent shuffles it into their library, then reveals the top card of their library. If it's
    a permanent card, they put it onto the battlefield." """
    target: str = "permanent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.chaos_warp(target)


@dataclass(frozen=True)
class _ChaosPut:
    """Chaos Warp's second sentence (see _merge_mana_drain)."""


@dataclass(frozen=True)
class PutSourceOnLibraryTop:
    """Sensei's Divining Top: "... then put this artifact on top of its owner's library." """
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_on_library_top(target)


@dataclass(frozen=True)
class ExileInstead:
    """ "If that spell is countered this way, exile it instead of putting it into its owner's graveyard." Only ever the
    end of a Counter (see _merge_exile)."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone 'exile it instead' is never built")


@dataclass(frozen=True)
class Flicker:
    """Exile a permanent and bring it back: right away ("now") or as the next end step begins ("end_step"), to the
    battlefield or its owner's hand. `under_owner`: "under its owner's control" (otherwise under yours)."""
    target: str
    when: str = "now"
    to: str = "battlefield"
    under_owner: bool = True
    another: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.flicker(target, controller, self.when, self.to, self.under_owner)


@dataclass(frozen=True)
class ReturnLater:
    """ "Return it to the battlefield under its owner's control at the beginning of the next end step." Only ever the
    end of an Exile (see _merge_exile)."""
    to: str
    under_owner: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone delayed return is never built")


@dataclass(frozen=True)
class ExileTop:
    """ "Exile the top two cards of your library. Until the end of your next turn, you may play those cards." (`play` is
    None, "this turn" or "next turn")"""
    count: int | str
    play: str | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top(controller, game.amount(self.count), self.play)


@dataclass(frozen=True)
class PlayExiled:
    """ "You may play it this turn." Only ever the end of an ExileTop (see _merge_exile)."""
    until: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone permission to play exiled cards is never built")


@dataclass(frozen=True)
class Exile:
    target: str
    another: bool = False  # "exile another target ...": not the source itself
    optional_target: bool = False
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile(target)


@dataclass(frozen=True)
class GrantFlash:
    """Alchemist's Refuge: "You may cast spells this turn as though they had flash." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.flash_turn = game.turn


@dataclass(frozen=True)
class ExileEnchanted:
    """Redemption Arc: "Exile enchanted creature." (the Aura's own ability, so no target)"""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.attached_to is not None:
            game.exile(target.attached_to)


@dataclass(frozen=True)
class ExileUntilLeaves:
    """Oblivion Ring, Banishing Light, Fiend Hunter: the target comes back when the source leaves the battlefield."""
    target: str
    another: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_until_leaves(target, game.resolving_source)


@dataclass(frozen=True)
class TargetDraw:
    count: int | str
    target: str = "player"  # "player" or "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.draw(target, game.amount(self.count))


@dataclass(frozen=True)
class TargetDrawLose:
    """ "Target player draws N cards and loses N life." """
    draws: int | str
    loses: int | str
    target: str = "player"
    distinct: bool = False  # "each mode must target a different player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.draw(target, game.amount(self.draws))
            game.change_life(target, -game.amount(self.loses))


@dataclass(frozen=True)
class YouAndTargetDraw:
    """ "You and target opponent each draw three cards." """
    count: int | str
    target: str = "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.draw(controller, game.amount(self.count))
        if target is not None:
            game.draw(target, game.amount(self.count))


@dataclass(frozen=True)
class EachPlayerLosesLife:
    amount: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            game.change_life(seat, -game.amount(self.amount))


@dataclass(frozen=True)
class Drain:
    """ "Each opponent loses X life. You gain life equal to the life lost this way." """
    amount: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        lost = 0
        for seat in game.opponents(controller):
            game.change_life(seat, -game.amount(self.amount))
            lost += game.amount(self.amount)
        game.change_life(controller, lost)


@dataclass(frozen=True)
class MayDiscardThenDraw:
    """ "You may discard a card. If you do, draw a card." (Quintorius: "... draw two cards, then mill a card.")"""
    draw: int = 1
    mill: int = 0

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.may_loot(controller, self.draw, self.mill)


@dataclass(frozen=True)
class EachMayWheel:
    """ "Each player may discard their hand and draw seven cards." """
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.may_wheel(self.count)


@dataclass(frozen=True)
class TapOrUntap:
    """ "You may tap or untap target creature." """
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap_or_untap(controller, target)


@dataclass(frozen=True)
class _MayDiscard:
    """Half of "You may discard a card. If you do, draw a card." (see _merge_loot)."""


@dataclass(frozen=True)
class MaySacrificeThenDraw:
    """Witherbloom Charm: "You may sacrifice a permanent. If you do, draw two cards." """
    kind: str
    draw: int = 1

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.may_sacrifice_draw(controller, self.kind, self.draw)


@dataclass(frozen=True)
class MayRemoveCounterThenDraw:
    """Ingenious Prodigy: "You may remove a +1/+1 counter from it. If you do, draw a card." """
    counter: str
    draw: int = 1
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.may_remove_counter_draw(controller, target, self.counter, self.draw)


@dataclass(frozen=True)
class _MayRemoveCounter:
    counter: str


@dataclass(frozen=True)
class _MaySacrifice:
    """Half of "You may sacrifice a permanent. If you do, draw two cards." (see _merge_loot)."""
    kind: str


@dataclass(frozen=True)
class _IfYouDoDraw:
    """The other half."""
    draw: int = 1
    mill: int = 0


@dataclass(frozen=True)
class _GainLifeLost:
    """ "You gain life equal to the life lost this way." (see _merge_drain) """


@dataclass(frozen=True)
class TargetDrawDiscard:
    """Prismari Command: "Target player draws two cards, then discards two cards." """
    draws: int
    discards: int
    target: str = "player"
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.draw(target, self.draws)
            game.discard(target, self.discards)


@dataclass(frozen=True)
class TargetMillThenReturn:
    """Witherbloom Command: "Target player mills three cards, then you return a land card from your graveyard to your hand." """
    count: int
    kind: str
    target: str = "player"
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.mill(target, self.count)
        game.return_chosen(controller, self.kind, "hand")


@dataclass(frozen=True)
class TargetDrawXPlusCasts:
    """Commander's Insight: "Target player draws X cards plus an additional card for each time they've cast a commander from the
    command zone this game." """
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.draw(target, game.amount("X") + sum(target.commander_casts.values()))


@dataclass(frozen=True)
class TargetGainLife:
    amount: int | str
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(target, game.amount(self.amount))


@dataclass(frozen=True)
class TargetLoseLife:
    amount: int | str
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(target, -game.amount(self.amount))


@dataclass(frozen=True)
class Modal:
    """ "Choose one — • ... • ..." The caster picks between `min` and `max` of the modes when casting (Game
    flattens the chosen ones into the spell's effects); `texts` are the modes as printed."""
    min: int
    max: int
    modes: tuple[tuple, ...]  # the effects of each mode
    texts: tuple[str, ...]
    commander_both: bool = False  # "If you control a commander as you cast this spell, you may choose both instead."
    optional: bool = False  # "you may choose two": the controller may choose none


_MODAL_COUNTS = {"one": (1, 1), "up to one": (0, 1), "two": (2, 2), "three": (3, 3), "one or both": (1, 2), "one or more": (1, 0)}
_MODAL_HEADER = re.compile(r"Choose (one or both|one or more|up to one|one|two|three) \u2014", re.I)
_MODAL_COMMANDER = re.compile(r"Choose one\. If you control a commander as you cast this spell, you may choose both instead\.")


def is_modal_header(line: str) -> bool:
    return _MODAL_HEADER.fullmatch(line) is not None or _MODAL_COMMANDER.fullmatch(line) is not None


def mode_text(line: str) -> str:
    """A mode of a modal spell without its bullet."""
    return line[2:] if line.startswith("\u2022 ") else line


def _parse_modal(how: str, lines: list[str]) -> list | None:
    modes, texts = [], []
    for line in lines:
        if not line.startswith("\u2022 "):
            return None  # something other than modes (entwine, escalate, ...)
        effects = _parse(_split_sentences(mode_text(line)))
        if not effects:
            return None
        modes.append(tuple(effects))
        texts.append(mode_text(line))
    low, high = _MODAL_COUNTS[how]
    high = high or len(modes)
    return [Modal(low, high, tuple(modes), tuple(texts))] if len(modes) >= max(low, 1) else None


_MODAL_DIFFERENT = re.compile(r"you may choose two\. Each mode must target a different player\. (\u2022 .+)")
_MODAL_INLINE = re.compile(r"choose (one or both|one or more|up to one|one|two|three) \u2014 (\u2022 .+)", re.I)


def _parse_modal_inline(text: str) -> list | None:
    """The modes of a modal triggered or activated ability, joined onto its line (see _join_modes), or None if
    the text isn't one."""
    if not (m := _MODAL_INLINE.fullmatch(text)):
        return None
    return _parse_modal(m[1].lower(), ["\u2022 " + part for part in m[2].removeprefix("\u2022 ").split(" \u2022 ")])


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
    another: bool = False  # "on another target creature you control": not the source itself

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))


@dataclass(frozen=True)
class RemoveCounters:
    """ "Remove a +1/+1 counter from target creature." / "Remove all counters from target permanent." (count None: all;
    counter None: of every kind)"""
    count: int | str | None
    counter: str | None
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.remove_counters(target, self.counter, None if self.count is None else game.amount(self.count))


@dataclass(frozen=True)
class RemoveAllCountersDraw:
    """Nexus Mentality: "Remove all counters from target nonland permanent you control. Draw a card for each counter removed
    this way." """
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            removed = sum(target.counters.values())
            game.remove_counters(target, None, None)
            game.draw(controller, removed)


PARITY_PROMPT = "Choose odd or even for "  # followed by the spell's name; options: "Odd", "Even"
HYPOTHESIS_COUNTER_PROMPT = "Put a +1/+1 counter on a creature for "  # followed by the spell's name


@dataclass(frozen=True)
class ZimonesHypothesis:
    """Zimone's Hypothesis: "You may put a +1/+1 counter on a creature. Then choose odd or even. Return each creature with
    power of the chosen quality to its owner's hand." (Zero is even.)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        name = game.resolving_item.card.name if game.resolving_item is not None else "Zimone's Hypothesis"
        creatures = [p for s in game.live_seats() for p in s.battlefield if "Creature" in p.card.type_line]
        if creatures:
            options = [game.label(p) for p in creatures] + ["No counter"]
            pick = controller.player.choose(HYPOTHESIS_COUNTER_PROMPT + name, options)
            if pick < len(creatures):
                game.put_counters(creatures[pick], "+1/+1", 1)
        parity = controller.player.choose(PARITY_PROMPT + name, ["Odd", "Even"])
        chosen = [p for s in game.live_seats() for p in s.battlefield if "Creature" in p.card.type_line
                  and game.power(p) % 2 == (1 if parity == 0 else 0)]
        game.return_all_to_hand(chosen)


@dataclass(frozen=True)
class PutCountersOnEachUpToX:
    """Silkguard: "Put a +1/+1 counter on each of up to X target creatures you control." The targets are one list."""
    counter: str
    target: str = "creature you control"
    grant: frozenset[str] = frozenset()  # "Those creatures gain flying until end of turn."
    up_to_x = True
    multi_target = True  # its one target slot holds a list
    optional_target = True  # it needs no target to be cast

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in target or []:
            game.put_counters(permanent, self.counter, 1)
            if self.grant:
                game.modify_until_end_of_turn(permanent, Modifier(keywords=self.grant))


@dataclass(frozen=True)
class PutCounterPerPlayer:
    """Nils: "For each player, put a +1/+1 counter on up to one target creature that player controls." The targets are one
    list, a creature (or none) for each player in turn order."""
    counter: str
    target: str = "creature"
    per_player = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in target or []:
            game.put_counters(permanent, self.counter, 1)


@dataclass(frozen=True)
class ModifiedGainHexproof:
    """Silkguard: "Auras, Equipment, and modified creatures you control gain hexproof until end of turn." (Counters,
    Equipment and your Auras on a creature are modifications.)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        hexproof = Modifier(keywords=frozenset({"hexproof"}))
        for permanent in list(controller.battlefield):
            attached = any(a.attached_to is permanent for a in controller.battlefield)
            is_attachment = any(t in permanent.card.type_line for t in ("Aura", "Equipment"))
            if is_attachment or ("Creature" in permanent.card.type_line and (any(permanent.counters.values()) or attached)):
                game.modify_until_end_of_turn(permanent, hexproof)


@dataclass(frozen=True)
class MoveCountersFrom:
    """The first target of "Move a +1/+1 counter from target creature onto another target creature." """
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


MOVE_COUNTERS_PROMPT = "Move how many "  # followed by the counter's name; options are "0", "1", ...


@dataclass(frozen=True)
class MoveCountersOnto:
    """The second target: the counters (up to `count`, or all if None) move from the first target to this one."""
    count: int | str | None  # a number, None for all of them, or "any" for a number the controller chooses
    counter: str | None  # None: every kind
    target: str
    another: bool = True
    same_controller: bool = False  # "... with the same controller": the second creature is under the first one's controller
    distinct: bool = True  # "another target": not the creature the counters come from

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        first = game.resolving_item.carried if game.resolving_item is not None else None
        if first is not None and target is not None and first is not target:
            count = self.count
            if count == "any":
                have = first.counters.get(self.counter, 0)
                count = controller.player.choose(f"{MOVE_COUNTERS_PROMPT}{self.counter} counters",
                                                 [str(n) for n in range(have + 1)])
            game.move_counters(first, target, self.counter, count)


@dataclass(frozen=True)
class DoubleCountersOnSource:
    """ "Double the number of +1/+1 counters on this creature." """
    counter: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.counters.get(self.counter):
            game.put_counters(target, self.counter, target.counters[self.counter])


@dataclass(frozen=True)
class DoubleCounters:
    """ "Double the number of +1/+1 counters on each creature you control." """
    counter: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line and permanent.counters.get(self.counter):
                game.put_counters(permanent, self.counter, permanent.counters[self.counter])


@dataclass(frozen=True)
class Animate:
    """ "Until end of turn, this land becomes a 3/3 green Ape creature with trample. It's still a land." (the source:
    uses_source) or "Target land you control becomes ..." (target)."""
    power: int
    toughness: int
    colors: tuple[str, ...]
    subtypes: str
    artifact: bool
    keywords: frozenset[str]
    target: str | None = None
    uses_source: bool = False
    on_your_turn: frozenset[str] = frozenset()  # keywords it has only during its controller's turn (Restless Spire)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.animate(target, self.power, self.toughness, self.colors, self.subtypes, self.artifact, self.keywords,
                         self.on_your_turn)


@dataclass(frozen=True)
class StillALand:
    """ "It's still a land." Only ever the end of an Animate (see _merge_animate)."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone 'still a land' is never built")


@dataclass(frozen=True)
class OnSubject:
    """A watching trigger's effect on "it": the permanent that set it off, not the ability's source."""
    inner: Any
    uses_subject = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        self.inner.resolve(game, controller, target)


@dataclass(frozen=True)
class OnSubjectController:
    """A watching trigger's effect on "its controller": the controller of the permanent that set it off (Parasitic Impetus)."""
    inner: Any
    uses_subject = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        owner = game.controller_of(target) if target is not None else None
        if owner is not None:
            self.inner.resolve(game, controller, owner)


@dataclass(frozen=True)
class OnPlayer:
    """A trigger's effect on "that player" / "they": the player whose action set it off."""
    inner: Any
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        self.inner.resolve(game, controller, target)


@dataclass(frozen=True)
class PutCountersOnEach:
    """ "Put a +1/+1 counter on each creature you control." (or each Vampire you control: `kind`) """
    count: int
    counter: str
    kind: str = ""  # a creature type, "" for every creature
    grant: frozenset[str] = frozenset()  # Ursine Guide's spell: "They gain trample until end of turn."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line and self.kind in permanent.card.type_line:
                game.put_counters(permanent, self.counter, game.amount(self.count))
                if self.grant:
                    game.modify_until_end_of_turn(permanent, Modifier(keywords=self.grant))


@dataclass(frozen=True)
class PutCountersOnEntered:
    """Oran-Rief: "Put a +1/+1 counter on each green creature that entered this turn." (any player's)"""
    counter: str
    color: str = ""  # "G"; "" for any creature

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.live_seats():
            for permanent in list(seat.battlefield):
                if permanent.entered_turn == game.turn and "Creature" in permanent.card.type_line \
                        and (not self.color or self.color in permanent.card.colors):
                    game.put_counters(permanent, self.counter, 1)


@dataclass(frozen=True)
class PutCountersOnSource:
    """ "Whenever this creature attacks, put a +1/+1 counter on it." """
    count: int
    counter: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))


_COUNTER = r"([+\-\u2212]1/[+\-\u2212]1|[a-z]+) counters?"  # "+1/+1", or a named one ("charge")


def _counter_name(text: str) -> str:
    return text.replace("\u2212", "-")


_ENTERS_WITH = re.compile(rf"{_SELF} enters (?:tapped )?with (twice X|{_N}) {_COUNTER} on it\.", re.I)
_ESCAPES_WITH = re.compile(rf"{_SELF} escapes with {_N} {_COUNTER} on it\.", re.I)  # Woe Strider
_CLONE_EXTRA = re.compile(r".*, except it enters with X additional \+1/\+1 counters on it\.")  # Altered Ego
_IF_KICKED = re.compile(rf"if {_SELF} was kicked, ", re.I)
_ENTERS_PER_KICK = re.compile(rf"{_SELF} enters with an? {_COUNTER} on it for each time it was kicked\.", re.I)


def enters_with_counters(card: Card, kicked: int = 0, escaped: bool = False) -> dict[str, int | str]:
    """Counters from "This creature enters with N (or X) +1/+1 counters on it.", plus, when `kicked` (the number
    of times), "If this creature was kicked, it enters with N +1/+1 counters on it." and multikicker's
    "... enters with a +1/+1 counter on it for each time it was kicked." """
    counters: dict[str, int | str] = {}
    for line in rules_lines(card):
        if kicked and (k := _IF_KICKED.match(line)):
            line = line[k.end():]
        if m := _ENTERS_WITH.fullmatch(line):
            name = _counter_name(m[3])
            count = "2X" if m[1].lower() == "twice x" else _count(m[2])  # "2X": twice the X paid
            counters[name] = count if count in ("X", "2X") else counters.get(name, 0) + count
        elif escaped and (m := _ESCAPES_WITH.fullmatch(line)):
            name = _counter_name(m[2])
            counters[name] = counters.get(name, 0) + _count(m[1])
        elif kicked and (m := _ENTERS_PER_KICK.fullmatch(line)):
            name = _counter_name(m[1])
            counters[name] = counters.get(name, 0) + kicked
    return counters


def is_enters_with_counters(line: str) -> bool:
    if k := _IF_KICKED.match(line):
        line = line[k.end():]
    return (_ENTERS_WITH.fullmatch(line) is not None or _ENTERS_PER_KICK.fullmatch(line) is not None
            or _ESCAPES_WITH.fullmatch(line) is not None)


_CANT_COUNTER = re.compile(r"This spell can't be countered\.")


def cant_be_countered(card: Card) -> bool:
    return any(_CANT_COUNTER.fullmatch(line) for line in rules_lines(card))


def _signed(text: str) -> int:
    return int(text.replace("\u2212", "-"))


_COLOR_NAMES = "white|blue|black|red|green"
_COLOR_LETTER = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
_PROTECTION_FROM = (_COLOR_NAMES + "|everything|all colors|monocolored|multicolored|creatures|artifacts|enchantments|instants"
                    "|sorceries|planeswalkers")
_PROT = (rf"protection from (?:{_PROTECTION_FROM})(?:(?:, and |, | and )(?:from )?(?:{_PROTECTION_FROM}))*")
_WARD_MANA = r"(?:\{\d+\}|\{[WUBRGC]\})+"
PROTECTION = re.compile(_PROT, re.I)  # "protection from red", "protection from red and from blue"
_KW = rf"(?:{_PROT}|ward {_WARD_MANA}|annihilator \d+|[a-z]+(?: [a-z]+)?)"  # one keyword


def _protection_keywords(text: str) -> frozenset[str]:
    """ "protection from red and from blue" -> {"protection from red", "protection from blue"}"""
    return frozenset(f"protection from {what.lower()}"
                     for m in PROTECTION.finditer(text) for what in re.findall(_PROTECTION_FROM, m[0], re.I))


# What a source can be protected against: its color letters, its card types, and whether it is mono- or multicolored.
_PROTECTION_TOKENS = {"everything": "everything", "monocolored": "monocolored", "multicolored": "multicolored",
                      "creatures": "creature", "artifacts": "artifact", "enchantments": "enchantment",
                      "instants": "instant", "sorceries": "sorcery", "planeswalkers": "planeswalker"}


def protection_tokens(keyword: str) -> frozenset[str]:
    """ "protection from red" -> {"R"}, "protection from creatures" -> {"creature"}, "protection from all colors" -> WUBRG"""
    what = keyword.removeprefix("protection from ").lower()
    if what == "all colors":
        return frozenset(_COLOR_LETTER.values())
    return frozenset({_COLOR_LETTER.get(what) or _PROTECTION_TOKENS[what]})


def _keyword_list(text: str) -> frozenset[str]:
    """ "flying", "flying and vigilance", "flying, vigilance, and trample" -> {"flying", ...}; a protection
    clause becomes one keyword per color ("protection from red")."""
    rest = PROTECTION.sub("", text)
    return _protection_keywords(text) | frozenset(w.strip().lower() for w in re.split(r",? and |, ", rest) if w.strip())


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


@dataclass(frozen=True)
class Pump:
    """ "Target creature gets +3/+3 (and gains trample) until end of turn." """
    modifier: Modifier
    target: str
    optional_target: bool = False  # "One or two target creatures each get ...": the second may be left out
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.modify_until_end_of_turn(target, self.modifier)


@dataclass(frozen=True)
class GrantProtection:
    """ "Target creature you control gains protection from the color of your choice until end of turn." (Mother of Runes,
    Gods Willing); the controller picks the color as it resolves. With no target it is the source itself."""
    target: str | None = None
    uses_source: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.grant_protection_of_choice(target, controller)


@dataclass(frozen=True)
class PumpSource:
    """ "This creature gets +1/+0 until end of turn." """
    modifier: Modifier
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.modify_until_end_of_turn(target, self.modifier)


@dataclass(frozen=True)
class PumpSourceX:
    """ "This creature gets +X/+0 until end of turn." (X from "where X is ..."): multiples of X, like PumpX."""
    power: int
    toughness: int
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            x = game.amount("X")
            game.modify_until_end_of_turn(target, Modifier(self.power * x, self.toughness * x))


_ATTACK_TAX = re.compile(r"Each creature with one or more counters on it can't attack you or planeswalkers you control unless "
                         r"its controller pays \{X\}, where X is the number of counters on that creature\.")


def attack_tax_per_counter(card: Card) -> int:
    """Nils, Discipline Enforcer: how many times the card taxes each counter on a creature that attacks its controller."""
    return sum(_ATTACK_TAX.fullmatch(line) is not None for line in rules_lines(card))


def is_attack_tax_line(line: str) -> bool:
    return _ATTACK_TAX.fullmatch(line) is not None or _FLAT_ATTACK_TAX.fullmatch(line) is not None


_FLAT_ATTACK_TAX = re.compile(r"Creatures can't attack you(?: or planeswalkers you control)? unless their controller pays "
                              r"\{(\d+)\} for each creature they control that's attacking you(?: or planeswalkers you control)?\.")


def flat_attack_tax(card: Card) -> int:
    """Ghostly Prison: how much each creature attacking its controller costs to attack with."""
    return sum(int(m[1]) for line in rules_lines(card) if (m := _FLAT_ATTACK_TAX.fullmatch(line)))


@dataclass(frozen=True)
class CombatRestriction:
    """A static ability that limits who attacks or blocks: `kind` is "no_attack_tribe" (Inklings can't attack you),
    "no_attack_enchanted" (creatures enchanted by an Aura you control can't attack you), "block_only_flying" (Brazen Borrower)
    or "weaker_cant_block" (Elusive Otter: creatures with less power can't block it)."""
    kind: str
    what: str = ""  # the creature type for "no_attack_tribe"


_COMBAT_RESTRICTIONS = [
    (re.compile(r"((?-i:[A-Z][a-z]+))s can't attack you or planeswalkers you control\.", re.I),
     lambda m: CombatRestriction("no_attack_tribe", m[1])),
    (re.compile(r"Each creature that's enchanted by an Aura you control can't attack you or planeswalkers you control\."),
     lambda m: CombatRestriction("no_attack_enchanted")),
    (re.compile(rf"{_SELF} can block only creatures with flying\.", re.I), lambda m: CombatRestriction("block_only_flying")),
    (re.compile(rf"Creatures with power less than {_SELF}'s power can't block it\.|"
                r"Creatures with power less than this creature's power can't block it\.", re.I),
     lambda m: CombatRestriction("weaker_cant_block")),
]


def combat_restrictions(card: Card) -> tuple[CombatRestriction, ...]:
    found = []
    for line in rules_lines(card):
        for pattern, build in _COMBAT_RESTRICTIONS:
            if m := pattern.fullmatch(line):
                found.append(build(m))
    return tuple(found)


def is_combat_restriction_line(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern, _ in _COMBAT_RESTRICTIONS)


@dataclass(frozen=True)
class VowCounters:
    """Promise of Loyalty: "Each player puts a vow counter on a creature they control and sacrifices the rest. Each of
    those creatures can't attack you or planeswalkers you control for as long as it has a vow counter on it." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            creatures = [p for p in seat.battlefield if "Creature" in p.card.type_line]
            if not creatures:
                continue
            keep = creatures[seat.player.choose(VOW_PROMPT, [game.label(p) for p in creatures])]
            keep.counters["vow"] = keep.counters.get("vow", 0) + 1
            keep.vow_of = controller
            game._leave_together([(p, "sacrificed") for p in creatures if p is not keep])


VOW_PROMPT = "Choose the creature that gets the vow counter"

_QUEST_UNTAP = re.compile(r"As long as there are (\w+) or more (\w+) counters on this enchantment, untap all creatures you "
                          r"control during each other player's untap step\.")


def untaps_in_other_untap_steps(card: Card) -> tuple[str, int] | None:
    """Quest for Renewal: (the counter, how many of it) while which your creatures untap in everyone's untap step."""
    for line in rules_lines(card):
        if m := _QUEST_UNTAP.fullmatch(line):
            return m[2], _count(m[1])
    return None


def is_quest_untap_line(line: str) -> bool:
    return _QUEST_UNTAP.fullmatch(line) is not None


_ANNIHILATOR = re.compile(r"Annihilator (\d+)", re.I)


def annihilator_of(card: Card) -> int:
    """The N of the card's own "Annihilator N" keyword lines."""
    return sum(int(m[1]) for line in rules_lines(card) for part in line.split(", ") if (m := _ANNIHILATOR.fullmatch(part)))


@dataclass(frozen=True)
class Annihilate:
    """Annihilator N: "Whenever this creature attacks, defending player sacrifices N permanents." The defending player
    is the player the trigger was about."""
    count: int
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.sacrifice(target, "permanent", self.count)


@dataclass(frozen=True)
class PumpEach:
    """ "Creatures you control get +3/+3 and gain trample until end of turn." Affects only the
    creatures there when it resolves (CR 611.2c). `opponents`: "Creatures your opponents control get -1/-1"."""
    modifier: Modifier
    opponents: bool = False
    everyone: bool = False  # "All creatures get -2/-2 until end of turn."
    subtype: str = ""  # "Spirits you control gain double strike and vigilance until end of turn."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        seats = game.live_seats() if self.everyone else game.opponents(controller) if self.opponents else [controller]
        for seat in seats:
            for permanent in list(seat.battlefield):
                if "Creature" in permanent.card.type_line \
                        and (not self.subtype or self.subtype in permanent.card.type_line.partition("\u2014")[2].split()):
                    game.modify_until_end_of_turn(permanent, self.modifier)


@dataclass(frozen=True)
class EachDamagesItself:
    """Wave of Reckoning: "Each creature deals damage to itself equal to its power." (all at the same time)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = [(p, game.power(p)) for seat in game.live_seats() for p in seat.battlefield if "Creature" in p.card.type_line]
        for permanent, power in creatures:
            game.damage(permanent, max(power, 0), source=permanent)


@dataclass(frozen=True)
class SetBaseEachX:
    """Biomass Mutation: "Creatures you control have base power and toughness X/X until end of turn." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        x = game.amount("X")
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line:
                game.modify_until_end_of_turn(permanent, Modifier(set_pt=(x, x)))


@dataclass(frozen=True)
class PumpNamed:
    """Leitmotif Composer: "Creatures named CARDNAME can't be blocked this turn." Every creature with the source's name,
    whoever controls it."""
    modifier: Modifier

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        for seat in game.live_seats():
            for permanent in list(seat.battlefield):
                if item and permanent.card.name == item.card.name and "Creature" in permanent.card.type_line:
                    game.modify_until_end_of_turn(permanent, self.modifier)


@dataclass(frozen=True)
class PumpOtherAttackers:
    """Martial Impetus: "Each other creature that's attacking one of your opponents gets +1/+1 until end of turn." The
    creature that set the trigger off is the one left out."""
    modifier: Modifier

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        for attack in list(game.combat.attacks):
            if attack.attacker is not (item.subject if item else None) and attack.defender is not controller:
                game.modify_until_end_of_turn(attack.attacker, self.modifier)


@dataclass(frozen=True)
class PumpEachX:
    """ "All creatures get -X/-X until end of turn." (Toxic Deluge) / "Creatures you control get +X/+X ...": `power` and
    `toughness` are multiples of X."""
    power: int
    toughness: int
    opponents: bool = False
    everyone: bool = False
    keywords: frozenset[str] = frozenset()  # Moonshaker Cavalry: "gain flying and get +X/+X"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        x = game.amount("X")
        seats = game.live_seats() if self.everyone else game.opponents(controller) if self.opponents else [controller]
        for seat in seats:
            for permanent in list(seat.battlefield):
                if "Creature" in permanent.card.type_line:
                    game.modify_until_end_of_turn(permanent, Modifier(self.power * x, self.toughness * x, self.keywords))


@dataclass(frozen=True)
class PumpX:
    """ "Target creature gets +X/+X until end of turn." (X from "for each ..." or "where X is ..."): `power` and
    `toughness` are the multiples of X (1, 0 or -1)."""
    power: int
    toughness: int
    target: str
    keywords: frozenset[str] = frozenset()  # Tyvar's Stand: "... and gains hexproof and indestructible"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            x = game.amount("X")
            game.modify_until_end_of_turn(target, Modifier(self.power * x, self.toughness * x, self.keywords))
            if game.resolving_item is not None and game.resolving_item.carried is None:
                game.resolving_item.carried = target  # "Then it fights ...": the creature just pumped


_PT = r"([+\-\u2212]\d+)/([+\-\u2212]\d+)"
_PT_X = r"([+\-\u2212])(\d*X|0)/([+\-\u2212])(\d*X|0)"  # multiples of X: "+X/+X", "+2X/+2X", "-X/-0", "+0/+X"
_KEYWORDS = rf"({_KW}(?:(?:,? and |, ){_KW})*)"
_KEYWORDS_BARE = rf"{_KW}(?:(?:,? and |, ){_KW})*"
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
    self_only: bool = False  # "CARDNAME gets +1/+1 as long as ...": only the source itself
    condition: "Condition | None" = None  # "As long as you control an artifact, ...": applies only while it holds
    color: str | None = None  # "Other red creatures you control": a color letter
    attacking: bool = False  # "Attacking Pests you control": only while they are attacking
    per: tuple[str, str] | None = None  # "... for each artifact you control": (what to count, its type); see Game.modifiers
    everyone: bool = False  # "White creatures get +1/+1": every player's, not just its controller's
    token: bool = False  # "Creature tokens you control have haste": only tokens
    with_counters: bool = False  # "Creatures you control with counters on them have trample"


_CHOOSE_TYPE = re.compile(r"As (?:CARDNAME|this [a-z]+) enters, choose a creature type\.")


def chooses_creature_type(card: Card) -> bool:
    """Patchwork Banner: "As this artifact enters, choose a creature type." """
    return any(_CHOOSE_TYPE.fullmatch(line) for line in rules_lines(card))


def is_choose_type_line(line: str) -> bool:
    return _CHOOSE_TYPE.fullmatch(line) is not None


_AFFECTED = (r"Creatures you control of the chosen type|Creature tokens you control|Creatures you control with counters on them|(?:Other )?(?:Attacking )?(?:(?:white|blue|black|red|green) )?(?:[A-Z][\w'-]* )?[Cc]reatures you control"
             r"|(?:Attacking )?[A-Z][\w'-]*s you control|(?:White|Blue|Black|Red|Green) creatures")
_COMMANDER_SCALED = re.compile(rf"({_AFFECTED}) get {_PT} for each time you've cast your commander from the command zone "
                               r"this game\.")
_STATIC = re.compile(rf"({_AFFECTED}) (?:get {_PT}(?: and have {_KEYWORDS})?|have {_KEYWORDS})\.")
_AFFECTED_WHO = re.compile(r"(?P<chosen>Creatures you control of the chosen type)|(?P<tokens>Creature tokens you control)|(?P<counters>Creatures you control with counters on them)|(?P<other>Other )?(?P<attacking>Attacking )?(?:(?P<color>white|blue|black|red|green) )?"
                  r"(?:(?P<sub>[A-Z][\w'-]*) )?[Cc]reatures you control"
                  r"|(?P<attacking2>Attacking )?(?P<tribe>[A-Z][\w'-]*)s you control"
                  r"|(?P<global>White|Blue|Black|Red|Green) creatures")
_PER = {"artifact you control": ("permanent", "artifact"), "creature you control": ("permanent", "creature"),
        "Aura you control": ("permanent", "Aura"), "creature card in your graveyard": ("graveyard", "creature"),
        "Aura attached to it": ("auras_on_it", ""), "Aura you control that's attached to a creature": ("auras_on_creatures", "")}
_PER_LOWER = {k.lower(): v for k, v in _PER.items()}
_PER_WORDS = "|".join(re.escape(k) for k in _PER)
_SELF_SCALED = re.compile(rf"{_SELF} gets {_PT} for each ({_PER_WORDS})\.", re.I)
# Eidolon of Countless Battles: both the creature and the one it enchants, for two counts added together.
_BOTH_SCALED = re.compile(rf"This creature and enchanted creature each get {_PT} for each creature you control and {_PT} "
                          r"for each Aura you control\.")
_ATTACHED_SCALED = re.compile(rf"Enchanted creature gets {_PT} for each ({_PER_WORDS})\.")
_ATTACHED_TYPED = re.compile(rf"Enchanted creature gets {_PT}, has ({_KW}(?: and {_KW})*), and is an? ([A-Z][a-z]+) in addition "
                             r"to its other types\.")
_ATTACHED_GOADED = re.compile(rf"Enchanted creature gets {_PT}(?:, has ({_KW}),)? and is goaded\.")


_CANT = re.compile(rf"{_SELF} can't (attack or block|attack|block)\.", re.I)
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


@lru_cache(maxsize=None)
def static_abilities(card: Card) -> tuple[StaticBuff, ...]:
    buffs = []
    for line in rules_lines(card):
        sentence, condition = line, None
        if split := _conditional(line):
            sentence, text = split
            if (condition := _condition(text)) is None:
                continue
        if m := _STATIC.fullmatch(sentence):
            who = _AFFECTED_WHO.fullmatch(m[1])
            colors = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
            buffs.append(StaticBuff(_modifier(m, 2), who["other"] is not None,
                                    "chosen" if who["chosen"] else who["sub"] or who["tribe"], line,
                                    condition=condition, color=colors.get((who["color"] or who["global"] or "").lower()),
                                    attacking=bool(who["attacking"] or who["attacking2"]), everyone=bool(who["global"]),
                                    token=bool(who["tokens"]),
                                    with_counters=bool(who["counters"])))
        elif m := _COMMANDER_SCALED.fullmatch(sentence):  # Vanguard of the Restless
            who = _AFFECTED_WHO.fullmatch(m[1])
            buffs.append(StaticBuff(Modifier(_signed(m[2]), _signed(m[3])), who["other"] is not None,
                                    who["sub"] or who["tribe"], line, condition=condition, per=("commander_casts", "")))
        elif m := _BOTH_SCALED.fullmatch(sentence):
            buffs.append(StaticBuff(Modifier(_signed(m[1]), _signed(m[2])), False, None, line, self_only=True, per=_PER["creature you control"]))
            buffs.append(StaticBuff(Modifier(_signed(m[3]), _signed(m[4])), False, None, line, self_only=True, per=_PER["Aura you control"]))
        elif m := _SELF_SCALED.fullmatch(sentence):  # "This creature gets +1/+0 for each artifact you control."
            modifier = Modifier(_signed(m[1]), _signed(m[2]))
            buffs.append(StaticBuff(modifier, False, None, line, self_only=True, condition=condition,
                                    per=_PER_LOWER[m[3].lower()]))
        elif m := _CANT.fullmatch(sentence):  # "This creature can't block." (a token's, for one)
            keywords = {"attack": {CANT_ATTACK}, "block": {CANT_BLOCK}}.get(m[1].lower(), {CANT_ATTACK, CANT_BLOCK})
            buffs.append(StaticBuff(Modifier(0, 0, frozenset(keywords)), False, None, line, self_only=True, condition=condition))
        elif condition and (m := _SELF_STATIC.fullmatch(sentence)):  # unconditional ones would just be printed text
            buffs.append(StaticBuff(_modifier(m, 1), False, None, line, self_only=True, condition=condition))
    return tuple(buffs)


@dataclass(frozen=True)
class Attach:
    """Equip: attach the Equipment that made this ability to the target creature."""
    target: str = "creature you control"
    another: bool = False  # Reconfigure: not the Equipment creature itself

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.resolving_source is not None:
            game.attach(game.resolving_source, target)


@dataclass(frozen=True)
class Unattach:
    """Reconfigure's second ability: unattach this Equipment, which makes it a creature again."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.detach(target)


@dataclass(frozen=True)
class AttachAura:
    """The targeting of an Aura spell. The game attaches the Aura as it enters (Game._resolve)."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


_EQUIP = re.compile(r"Equip ((?:\{\d+\}|\{[WUBRGC]\})+)")
_ENCHANT = re.compile(r"Enchant ((?:land|creature card in a graveyard|creature|artifact|enchantment|planeswalker|permanent"
                      r"|nonland permanent)"
                      r"(?: an opponent controls| you control)?)", re.I)


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


def equip_cost(card: Card) -> str | None:
    """The mana cost from "Equip {2}", or None (other equip costs aren't supported)."""
    return next((m[1] for line in rules_lines(card) if (m := _EQUIP.fullmatch(line))), None)


def aura_kind(card: Card) -> str | None:
    """What an Aura enchants ("creature", "creature you control", "land", ...), or None if it isn't an Aura."""
    if "Aura" not in card.type_line:
        return None
    return next((m[1].lower() for line in rules_lines(card) if (m := _ENCHANT.fullmatch(line))), None)


_REPLACE_ANY_GRAVEYARD = "If a card or token would be put into a graveyard from anywhere, exile it instead."
_REPLACE_OPPONENT_GRAVEYARD = "If a card would be put into an opponent's graveyard from anywhere, exile it instead."
_DOUBLE_TOKENS = ("If an effect would create one or more tokens under your control, it creates twice that many of "
                  "those tokens instead.")
_DOUBLE_COUNTERS = ("If an effect would put one or more counters on a permanent you control, it puts twice that many "
                    "of those counters on that permanent instead.")
_DOUBLE_COUNTERS_OLD = ("If an effect would put one or more counters on a permanent you control, it puts twice that "
                        "many of those counters instead.")  # the wording before the Oracle update
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
    life_gain_plus: int = 0  # Pest Rescuer: its controller gains that much more life whenever they gain life
    extra_trigger: str | None = None  # "artifact or creature" or "permanent": those entering trigger abilities twice;
    #                                    "spell": casting or copying an instant or sorcery does


@lru_cache(maxsize=None)
def replacement_effects(card: Card) -> Replacements:
    found: dict[str, Any] = {}
    for line in rules_lines(card):
        if line == _REPLACE_ANY_GRAVEYARD:
            found["graveyard"] = "any"
        elif line == _REPLACE_OPPONENT_GRAVEYARD:
            found.setdefault("graveyard", "opponent")
        elif line == _DOUBLE_TOKENS:
            found["tokens"] = found.get("tokens", 1) * 2
        elif line in (_DOUBLE_COUNTERS, _DOUBLE_COUNTERS_OLD):
            found["counters"] = found.get("counters", 1) * 2
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
        elif line == _LIFE_GAIN_PLUS_ONE:
            found["life_gain_plus"] = found.get("life_gain_plus", 0) + 1
    return Replacements(**found)


_LIFE_GAIN_PLUS_ONE = "If you would gain life, you gain that much life plus 1 instead."


# Veyran, Voice of Duality (the card's own wording has "you casting").
_EXTRA_TRIGGER_SPELL = re.compile(r"If you casting or copying an instant or sorcery spell causes a triggered ability of a "
                                  r"permanent you control to trigger, that ability triggers an additional time\.")


def is_replacement_line(line: str) -> bool:
    return (_EXTRA_TRIGGER_SPELL.fullmatch(line) is not None or line in (_REPLACE_ANY_GRAVEYARD, _REPLACE_OPPONENT_GRAVEYARD, _DOUBLE_TOKENS, _DOUBLE_COUNTERS,
                     _DOUBLE_COUNTERS_OLD, _PLUS_ONE_COUNTERS, _PLUS_ONE_OTHERS, _PLUS_ONE_PERMANENTS, _PLUS_ONE_ARTIFACTS, _ENTER_PER_DEATH, _LIFE_GAIN_PLUS_ONE) or _EXTRA_TRIGGER.fullmatch(line) is not None)


_CLONE = re.compile(rf"You may have {_SELF} enter(?: the battlefield)? as a copy of "
                    r"(?:any (creature|artifact|enchantment|land) on the battlefield|a (creature) you control)"
                    r"(, except it enters with X additional \+1/\+1 counters on it)?\.")


def clone_extra_counters(card: Card) -> bool:
    """Altered Ego: a copy "except it enters with X additional +1/+1 counters on it"."""
    return any((m := _CLONE.fullmatch(line)) and m[3] for line in rules_lines(card))


def clone_kind(card: Card) -> tuple[str, bool] | None:
    """For Clone: what the card may enter as a copy of ("creature") and whether it must be one you control."""
    for line in rules_lines(card):
        if m := _CLONE.fullmatch(line):
            return (m[1] or m[2]), m[2] is not None
    return None


def is_clone_line(line: str) -> bool:
    return _CLONE.fullmatch(line) is not None


def is_enchant_line(line: str) -> bool:
    return _ENCHANT.fullmatch(line) is not None


# Animate Dead and Dance of the Dead: an Aura cast on a creature card in a graveyard, which comes back with the Aura.
_REANIMATION_AURA = re.compile(
    r"When (?:this Aura|CARDNAME) enters, if it's on the battlefield, it loses \"enchant creature card in a graveyard\" and "
    r"gains \"enchant creature put onto the battlefield with (?:this Aura|CARDNAME)\.\" (?:Return|Put) enchanted creature "
    r"card (?:to|onto) the battlefield( tapped)? under your control and attach (?:this Aura|CARDNAME) to it\. When "
    r"(?:this Aura|CARDNAME) leaves the battlefield, that creature's controller sacrifices it\.")


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


_ATTACHED = re.compile(rf"(?:Equipped|Enchanted) creature (?:gets {_PT}(?: and has {_KEYWORDS})?|has {_KEYWORDS}"
                       r"|can't attack or block)\.")
CANT_ATTACK, CANT_BLOCK = "can't attack", "can't block"  # pseudo-keywords, so combat can ask has_keyword
CANT_BE_BLOCKED = "can't be blocked"


_GRANT = re.compile(rf'(?:Equipped|Enchanted) (?:creature|land|permanent) has (?:{_KEYWORDS_BARE} and )?"(.+)"\.?')
_ATTACHED_AND_GRANT = re.compile(rf'(?:Equipped|Enchanted) creature has ({_KEYWORDS}) and ".+"\.?')  # Fallen Ideal  # the quote's own full stop is inside it


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


_ADDITIONAL_MANA = re.compile(r"Whenever enchanted land is tapped for mana, its controller adds an additional "
                              r"(?:\{([WUBRG])\}|one mana of any color)\.")


def additional_land_mana(card: Card) -> list[frozenset[str]]:
    """Wild Growth and Fertile Ground: the extra mana the enchanted land makes whenever it is tapped for mana."""
    return [frozenset(m[1] or "WUBRG") for line in rules_lines(card) if (m := _ADDITIONAL_MANA.fullmatch(line))]


def is_additional_mana_line(line: str) -> bool:
    return _ADDITIONAL_MANA.fullmatch(line) is not None


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
        elif m := _ATTACHED_GOADED.fullmatch(line):
            keywords = _keyword_list(m[3]) if m[3] else frozenset()
            buffs.append(AttachedBuff(Modifier(_signed(m[1]), _signed(m[2]), keywords), line, goaded=True))
        elif m := _BOTH_SCALED.fullmatch(line):
            buffs.append(AttachedBuff(Modifier(_signed(m[1]), _signed(m[2])), line, per=_PER["creature you control"]))
            buffs.append(AttachedBuff(Modifier(_signed(m[3]), _signed(m[4])), line, per=_PER["Aura you control"]))
        elif m := _ATTACHED_SCALED.fullmatch(line):
            buffs.append(AttachedBuff(Modifier(_signed(m[1]), _signed(m[2])), line, per=_PER[m[3]]))
    return tuple(buffs)


@dataclass(frozen=True)
class CreateTokens:
    count: int
    token: Card
    counters: tuple[int | str, str] | None = None  # "Create a 0/0 ... token. Put X +1/+1 counters on it."
    tapped: bool = False  # "Create a number of tapped Treasure tokens ..." (Goldvein Hydra)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        token = self.token
        if "X" in (token.power, token.toughness):  # "an X/X ... token": its size is fixed as it's created
            token = dataclasses.replace(token, power=str(game.amount(token.power)),
                                        toughness=str(game.amount(token.toughness)))
        counters = (game.amount(self.counters[0]), self.counters[1]) if self.counters else None
        game.create_tokens(controller, token, game.amount(self.count), counters, tapped=self.tapped)


@dataclass(frozen=True)
class CopyToken:
    """ "Create a token that's a copy of target creature you control." """
    target: str
    count: int = 1  # Rite of Replication: "If this spell was kicked, create five of those tokens instead."
    another: bool = False  # "a copy of another target creature you control": not the source itself
    haste: bool = False  # Inspired Skypainter's spell: "That token gains haste until end of turn."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            card = target.card
            if not card.type_line.startswith("Token"):
                card = dataclasses.replace(card, type_line="Token " + card.type_line)
            for token in game.create_tokens(controller, card, game.amount(self.count)):
                if self.haste:
                    game.modify_until_end_of_turn(token, Modifier(keywords=frozenset({"haste"})))


@dataclass(frozen=True)
class _TokenGainsHaste:
    """ "That token gains haste until end of turn." after a CopyToken (see _merge_conditional)."""


@dataclass(frozen=True)
class AttackingTokens:
    """Furygale Flocking: "For each opponent, create two 3/3 blue and red Elemental creature tokens with flying that attack
    that opponent this turn if able. They gain haste until end of turn. Exile them at the beginning of the next end step."
    The second and third sentences are folded in by _merge_attacking_tokens."""
    count: int  # for each opponent
    token: Card
    haste: bool = False
    exile_at_end: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.attacking_tokens(controller, self.token, game.amount(self.count), self.haste,
                              "exiled" if self.exile_at_end else None)


@dataclass(frozen=True)
class _TheyGainHaste:
    """ "They gain haste until end of turn.": only ever after AttackingTokens."""


@dataclass(frozen=True)
class _ExileThemLater:
    """ "Exile them at the beginning of the next end step.": only ever after AttackingTokens."""


def _merge_attacking_tokens(effects: list) -> list | None:
    merged: list = []
    for effect in effects:
        if isinstance(effect, (_TheyGainHaste, _ExileThemLater)):
            if not (merged and isinstance(merged[-1], AttackingTokens)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], **({"haste": True} if isinstance(effect, _TheyGainHaste)
                                                             else {"exile_at_end": True}))
        else:
            merged.append(effect)
    return merged


def _attacking_tokens(m: re.Match) -> AttackingTokens | None:
    parsed = _token(m[1] + '."' if m[2] else m[1])
    return AttackingTokens(*parsed) if parsed else None


@dataclass(frozen=True)
class PreventCombatDamageToYou:
    """Inkshield: "Prevent all combat damage that would be dealt to you this turn. For each 1 damage prevented this way,
    create a 2/1 white and black Inkling creature token with flying." The second sentence is folded in by
    _merge_prevention; the game creates the tokens as the damage is prevented."""
    token: Card | None = None  # one for each point of damage prevented

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.prevent_combat_damage(controller, self.token)


@dataclass(frozen=True)
class _TokenPerPrevented:
    """ "For each 1 damage prevented this way, create ...": only ever after PreventCombatDamageToYou."""
    token: Card


def _merge_prevention(effects: list) -> list | None:
    merged: list = []
    for effect in effects:
        if isinstance(effect, _TokenPerPrevented):
            if not (merged and isinstance(merged[-1], PreventCombatDamageToYou) and merged[-1].token is None):
                return None
            merged[-1] = PreventCombatDamageToYou(effect.token)
        else:
            merged.append(effect)
    return merged


def _token_per_prevented(m: re.Match) -> _TokenPerPrevented | None:
    parsed = _token(m[1] + '."' if m[2] else m[1])
    return _TokenPerPrevented(parsed[1]) if parsed and parsed[0] == 1 else None


@dataclass(frozen=True)
class TokensBecomeCopies:
    """Brudiclad: "Then you may choose a token you control. If you do, each other token you control becomes a copy of
    that token until end of turn." (two sentences, folded together by _merge_token_copies)."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tokens_become_copies(controller)


@dataclass(frozen=True)
class _ChooseToken:
    """ "Then you may choose a token you control.": only ever before _OthersBecomeCopies."""


@dataclass(frozen=True)
class _OthersBecomeCopies:
    """ "If you do, each other token you control becomes a copy of that token until end of turn." """


def _merge_token_copies(effects: list) -> list | None:
    merged: list = []
    i = 0
    while i < len(effects):
        if isinstance(effects[i], _ChooseToken):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _OthersBecomeCopies)):
                return None
            merged.append(TokensBecomeCopies())
            i += 2
            continue
        if isinstance(effects[i], _OthersBecomeCopies):
            return None
        merged.append(effects[i])
        i += 1
    return merged


@dataclass(frozen=True)
class LookTakeRestBottom:
    """Dig Through Time: "Look at the top seven cards of your library. Put two of them into your hand and the rest on the bottom
    of your library in any order." (one template across two sentences)"""
    count: int
    take: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_take(controller, self.count, self.take)


@dataclass(frozen=True)
class ThreeWaySplit:
    """Expressive Iteration: "Look at the top three cards of your library. Put one of them into your hand, put one of them
    on the bottom of your library, and exile one of them. You may play the exiled card this turn." (three sentences, folded
    together by _merge_three_way)"""
    count: int
    play: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.three_way_split(controller, self.count, self.play)


@dataclass(frozen=True)
class _SplitTop:
    """ "Put one of them into your hand, put one of them on the bottom of your library, and exile one of them." """


@dataclass(frozen=True)
class _PlayTheExiledCard:
    """ "You may play the exiled card this turn." """


def _merge_three_way(effects: list) -> list | None:
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, LookAtTop) and i + 1 < len(effects) and isinstance(effects[i + 1], _SplitTop):
            play = i + 2 < len(effects) and isinstance(effects[i + 2], _PlayTheExiledCard)
            merged.append(ThreeWaySplit(effect.count, play))
            i += 3 if play else 2
            continue
        if isinstance(effect, (_SplitTop, _PlayTheExiledCard)):
            return None
        merged.append(effect)
        i += 1
    return merged


@dataclass(frozen=True)
class TargetControllerManifests:
    """Reality Shift: "Exile target creature. Its controller manifests the top card of their library." """
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.manifest(target.last_controller)


@dataclass(frozen=True)
class DanceWithCalamity:
    """ "Shuffle your library. As many times as you choose, you may exile the top card of your library. If the total mana
    value of the cards exiled this way is 13 or less, you may cast any number of spells from among those cards without
    paying their mana costs." """
    limit: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.dance_with_calamity(controller, self.limit)


@dataclass(frozen=True)
class CopyTokenAttacking:
    """ "Create a token that's a copy of it, tapped and attacking." (it: the attacking source). The token attacks the
    same player or planeswalker; it was never declared as an attacker, so attack triggers do not see it."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_attacking(controller, target)


@dataclass(frozen=True)
class TargetLoseHalfLife:
    """ "Target player loses half their life, rounded up (down)." """
    target: str  # "player" or "opponent"
    round_up: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.life > 0:
            game.change_life(target, -((target.life + 1) // 2 if self.round_up else target.life // 2))


@dataclass(frozen=True)
class DoubleCountersOnTarget:
    """ "Double the number of +1/+1 counters on target creature." """
    counter: str
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.counters.get(self.counter):
            game.put_counters(target, self.counter, target.counters[self.counter])


@dataclass(frozen=True)
class ReturnSelfToBattlefield:
    """ "When this creature dies, return it to the battlefield (tapped)." It comes back as a new object under its
    owner's control; a token is gone for good."""
    tapped: bool = False
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_dead_to_battlefield(target, controller, under_owner=True, tapped=self.tapped)


@dataclass(frozen=True)
class PutFromHand:
    """ "You may put a creature card from your hand onto the battlefield." """
    kind: str
    tapped: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.put_from_hand(controller, self.kind, self.tapped)


@dataclass(frozen=True)
class ReturnChosen:
    """ "Return a creature card from your graveyard to your hand.": you choose, it is not targeted."""
    kind: str
    to: str  # "hand"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_chosen(controller, self.kind, self.to)


POPULATE_PROMPT = "Populate: copy which token? "


@dataclass(frozen=True)
class Populate:
    """ "Populate": create a copy of a creature token you control (you choose which). """
    haste: bool = False  # Determined Iteration: "The token created this way gains haste."
    sacrifice_at_end: bool = False  # ... "Sacrifice it at the beginning of the next end step."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        kinds = []
        for permanent in controller.battlefield:
            if permanent.card.type_line.startswith("Token") and "Creature" in permanent.card.type_line \
                    and permanent.card not in kinds:
                kinds.append(permanent.card)
        if kinds:
            pick = 0 if len(kinds) == 1 else controller.player.choose(
                POPULATE_PROMPT, [f"{c.name} {c.power}/{c.toughness}" for c in kinds])
            made = game.create_tokens(controller, kinds[pick], 1)
            for token in made:
                if self.haste:
                    game.modify_until_end_of_turn(token, Modifier(keywords=frozenset({"haste"})))
            if self.sacrifice_at_end:
                game.leave_at_next_end_step(made, "sacrificed", "graveyard")


@dataclass(frozen=True)
class _PopulatedTokenRider:
    """ "The token created this way gains haste." / "Sacrifice it at the beginning of the next end step." after Populate."""
    haste: bool = False
    sacrifice: bool = False


@dataclass(frozen=True)
class EachCreatesTokens:
    """ "Each opponent creates a 1/1 white Spirit creature token with flying." / "Each player creates a Treasure token." """
    count: int
    token: Card
    who: str  # "each opponent" or "each player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "each player" or seat is not controller:
                game.create_tokens(seat, self.token, game.amount(self.count))


@dataclass(frozen=True)
class TargetPutsCountersOnEach:
    """Shadrix Silverquill: "Target player puts a +1/+1 counter on each creature they control." """
    counter: str
    target: str = "player"
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            for permanent in list(target.battlefield):
                if "Creature" in permanent.card.type_line:
                    game.put_counters(permanent, self.counter, 1)


@dataclass(frozen=True)
class TargetCreatesTokens:
    """ "Target opponent creates a Treasure token." """
    count: int
    token: Card
    target: str  # "player" or "opponent"
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.create_tokens(target, self.token, game.amount(self.count))


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
HEARTWOOD = Card(name="Heartwood", type_line="Token Artifact — Heartwood", oracle_text="{T}: Add {R} or {G}.",
                 colors=("R", "G"))
_NAMED_TOKENS = {"treasure": TREASURE, "clue": CLUE, "food": FOOD, "heartwood": HEARTWOOD}
_COLOR_WORDS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
_COLOR = r"(?:white|blue|black|red|green)"
_TOKEN_COUNT = _N.replace("|X)", "|X|twice X|half X up|half X down)")  # "Create twice X 1/1 ... tokens" (Pest Infestation)
_CREATURE_TOKEN = re.compile(
    rf"{_TOKEN_COUNT} (\d+|X)/(\d+|X) (colorless|{_COLOR}(?:(?:,? and |, ){_COLOR})*) ((?:[A-Z][\w'-]* )+)(artifact )?"
    r"creature tokens?(?: named ([A-Z][\w'-]*))?"  # "named Cadet"
    r"(?: with (?:([a-z ,]+?)(?:,? and |, |$))?(?:\"(.+)\")?)?"  # keywords and/or a quoted ability
)
_NAMED_TOKEN = re.compile(rf"(?i:{_TOKEN_COUNT}) (Treasure|Clue|Food|Heartwood) tokens?")


def _token(spec: str) -> tuple[int, Card] | None:
    """Parse "a 1/1 white Soldier creature token with flying" or "two Treasure tokens"."""
    if m := _NAMED_TOKEN.fullmatch(spec):
        return _count(m[1]), _NAMED_TOKENS[m[2].lower()]
    m = _CREATURE_TOKEN.fullmatch(spec)
    if not m:
        return None
    count, power, toughness, colors, subtypes, artifact, named, keywords, quoted = m.groups()
    keyword_line = ""
    if keywords:
        words = [w.strip() for w in re.split(r",? and |, ", keywords) if w.strip()]
        keyword_line = ", ".join(words).capitalize()
    card = Card(
        name=named or subtypes.strip(),
        type_line=f"Token {'Artifact ' if artifact else ''}Creature — {subtypes.strip()}",
        oracle_text="\n".join(line for line in (keyword_line, quoted) if line),
        colors=tuple(_COLOR_WORDS[c] for c in re.findall(_COLOR, colors)),
        power=power,
        toughness=toughness,
    )
    if quoted and not _is_ability(card, quoted):
        return None  # a token ability we can't play: don't create a half-working token
    return _count(count), card


def _is_ability(card: Card, line: str) -> bool:
    """Whether `line` of `card`'s rules text is an ability we understand."""
    known = {a.text for a in (*triggered_abilities(card), *activated_abilities(card), *static_abilities(card))}
    return line in known or is_mana_ability(line)


_ANIMATED = (r"(\d+)/(\d+)(?: ((?:white|blue|black|red|green)(?:(?:,? and |, )(?:white|blue|black|red|green))*))?"
             r"(?: ((?:[A-Z][\w'-]*)(?: [A-Z][\w'-]*)*))?( artifact)? creature(?: with (all creature types|"
             + _KEYWORDS_BARE + r"))?"
             r"(?: with \"During your turn, this creature has (" + _KEYWORDS_BARE + r")(?=\.\"))?")


def _animate(m: re.Match, target: str | None, offset: int = 0) -> Animate:
    power, toughness, colors, subtypes, artifact, keywords, on_your_turn = m.group(*range(offset + 1, offset + 8))
    keywords = None if keywords == "all creature types" else keywords
    return Animate(int(power), int(toughness), tuple(_COLOR_WORDS[c] for c in re.findall(_COLOR, colors or "")),
                   subtypes or "", artifact is not None, _keyword_list(keywords) if keywords else frozenset(),
                   target, uses_source=target is None,
                   on_your_turn=_keyword_list(on_your_turn) if on_your_turn else frozenset())


def _merge_token_counters(effects: list) -> list | None:
    """"Create a 0/0 Fractal creature token. Put X +1/+1 counters on it." is one CreateTokens whose tokens come in with
    the counters (the second sentence means the new token, not the ability's source)."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, PutCountersOnSource) and merged and isinstance(merged[-1], CreateTokens) \
                and merged[-1].counters is None:
            merged[-1] = dataclasses.replace(merged[-1], counters=(effect.count, effect.counter))
        elif isinstance(effect, PutCountersOnSource) and len(merged) > 1 and isinstance(merged[-1], DefineX) \
                and isinstance(merged[-2], CreateTokens) and merged[-2].counters is None:
            # "..., where X is ...": X is worked out first, then the tokens come in with X counters (Deekah)
            merged[-2:] = [merged[-1], dataclasses.replace(merged[-2], counters=(effect.count, effect.counter))]
        else:
            merged.append(effect)
    return merged


def _merge_reveal_top(effects: list) -> list | None:
    """The three sentences of Thrasios's ability become one RevealTop; a step without the others isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, RevealTopStep):
            steps = effects[i:i + 3]
            if [getattr(e, "kind", None) for e in steps] != ["reveal", "land", "otherwise"]:
                return None
            merged.append(RevealTop(steps[0].scry, steps[1].tapped))
            i += 3
            continue
        merged.append(effect)
        i += 1
    return merged


def _merge_wipe_gift(effects: list) -> list | None:
    """"Destroy all creatures. For each creature destroyed this way, its controller creates a token." is one DestroyAll
    with `gives`; the second sentence alone isn't understood."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, GiveBack):
            if not (merged and isinstance(merged[-1], (DestroyAll, ExileAll, ExileX))):
                return None
            merged[-1] = dataclasses.replace(merged[-1], gives=effect)
        else:
            merged.append(effect)
    return merged


def _merge_animate(effects: list) -> list | None:
    """"... becomes a 2/2 creature. It's still a land." is one Animate; the second sentence alone isn't understood."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, StillALand):
            if not (merged and isinstance(merged[-1], Animate)):
                return None
            continue
        merged.append(effect)
    return merged


def _create_for_others(m: re.Match) -> Any:
    parsed = _token(m[2] + '."' if m[3] else m[2])
    if parsed is None:
        return None
    who = m[1].lower()
    return EachCreatesTokens(*parsed, who) if who.startswith("each") else TargetCreatesTokens(*parsed, who)


def _pump_x(sp: str, px: str, st: str, tx: str, target: str, keywords: str | None = None) -> PumpX:
    """+X/+X, -X/-X, +2X/+2X, ... as multiples of X (a plain +0/+0 never gets here: the ordinary pump reads it first)."""
    def multiple(sign: str, part: str) -> int:
        return 0 if part == "0" else (-1 if sign in ("-", "\u2212") else 1) * int(part.removesuffix("X") or 1)
    return PumpX(multiple(sp, px), multiple(st, tx), target, _keyword_list(keywords) if keywords else frozenset())


def _pump_each_x_from(who: str, sp: str, px: str, st: str, tx: str) -> PumpEachX:
    who = who.lower()
    inner = _pump_x(sp, px, st, tx, "creature")
    return PumpEachX(inner.power, inner.toughness, opponents=who.endswith("opponents control"), everyone=who == "all creatures")


def _pump_each_x(m: re.Match) -> PumpEachX:
    return _pump_each_x_from(m[1], m[2], m[3], m[4], m[5])


def _create(m: re.Match, follows: bool) -> Any:
    spec = m[1] + '."' if m[2] else m[1]  # a quoted ability's own full stop comes before its closing quote
    tapped = re.search(r"\btapped (?=[A-Z])", spec) is not None  # "X tapped Treasure tokens"
    parsed = _token(re.sub(r"\btapped (?=[A-Z])", "", spec, count=1))
    if parsed is None:
        return None
    if follows:
        return TargetControllerCreatesTokens(*parsed)
    return CreateTokens(*parsed, tapped=True) if tapped else CreateTokens(*parsed)


@dataclass(frozen=True)
class MassFilter:
    """Which of the permanents of an "all"/"each" effect are affected: "with flying", "without flying",
    "with power 4 or greater", "nonblack"."""
    keyword: str | None = None
    keyword_wanted: bool = True  # False: "without flying"
    stat: str | None = None  # "power" or "toughness"
    at_least: int | None = None  # "with power 4 or greater"
    at_most: "int | str | None" = None  # "with toughness 2 or less"; "X" is the X of the spell or ability
    color: str | None = None  # a color letter
    other_color: bool = False  # "nonblack": every one that isn't that color
    token: bool | None = None  # True: "creature tokens"; False: "nontoken creatures"
    legendary: bool | None = None  # "legendary creatures" / "nonlegendary"
    basic: bool | None = None  # "nonbasic lands"
    tapped: bool | None = None  # "tapped creatures" / "untapped"
    has_type: str | None = None  # "artifact creatures": a card type it must have
    exclude: "MassFilter | None" = None  # "... except for artifact creatures": what is spared
    colors_are: str | None = None  # "that are one or more colors" / "colorless" / "multicolored" / "monocolored"
    enchanted: bool | None = None  # False: "that aren't enchanted" (Winds of Rath)


@dataclass(frozen=True)
class AddManaPerCardInHand:
    """Rousing Refrain: "Add {R} for each card in target opponent's hand." """
    symbol: str
    target: str = "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.add_mana(controller, tuple(frozenset(self.symbol) for _ in target.hand))


@dataclass(frozen=True)
class AddManaPerTappedLand:
    """Mana Geyser: "Add {R} for each tapped land your opponents control." """
    symbol: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = sum(1 for seat in game.opponents(controller) for p in seat.battlefield if p.tapped and "Land" in p.card.type_line)
        game.add_mana(controller, tuple(frozenset(self.symbol) for _ in range(count)))


@dataclass(frozen=True)
class KeepManaThisTurn:
    """ "Until end of turn, you don't lose this mana as steps and phases end." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.keep_pool_turn = game.turn


@dataclass(frozen=True)
class ExileWithTimeCounters:
    """Rousing Refrain: "Exile Rousing Refrain with three time counters on it." The spell is suspended instead of going
    to the graveyard once it has resolved."""
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.suspend_after = self.count


_SUSPEND = re.compile(r"Suspend (\d+)—((?:\{[^}]+\})+)")


def suspend_of(card: Card) -> tuple[int, str] | None:
    """Suspend N—{cost}: (the time counters, the cost to exile it from your hand with them)."""
    return next(((int(m[1]), m[2]) for line in rules_lines(card) if (m := _SUSPEND.fullmatch(line))), None)


@dataclass(frozen=True)
class OpponentsLoseCounters:
    """Final Act: "Each opponent loses all counters." (the counters on players: poison, energy, experience, ...)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for opponent in game.opponents(controller):
            opponent.player_counters.clear()


@dataclass(frozen=True)
class DestroyAll:
    """ "Destroy all creatures." Indestructible permanents survive; they all die together."""
    kind: str  # "creature", "artifact or enchantment", "creature you don't control", ...
    restriction: MassFilter | None = None  # "... with flying"
    no_regen: bool = False  # "They can't be regenerated."
    gives: "GiveBack | None" = None  # "For each creature destroyed this way, its controller creates a 1/1 token"
    mana_each: frozenset[str] = frozenset()  # Culling Ritual: "Add {B} or {G} for each permanent destroyed this way."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        destroyed = game.destroy_all(game.mass_targets(self.kind, controller, self.restriction), self.no_regen, self.gives, controller)
        if self.mana_each:
            game.add_mana(controller, tuple(self.mana_each for _ in destroyed))


@dataclass(frozen=True)
class _ManaForEachDestroyed:
    """ "Add {B} or {G} for each permanent destroyed this way." (see _merge_conditional)"""
    options: frozenset[str]


@dataclass(frozen=True)
class ExileAll:
    kind: str
    restriction: MassFilter | None = None
    gives: "GiveBack | None" = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_all(game.mass_targets(self.kind, controller, self.restriction), self.gives, controller)


@dataclass(frozen=True)
class ExileX:
    """Curse of the Swine: "Exile X target creatures. For each creature exiled this way, its controller creates a 2/2
    Boar." Exactly X targets, in one list; X can't be more than there are legal targets."""
    target: str
    gives: "GiveBack | None" = None
    up_to_x = True
    exact_x = True
    multi_target = True  # its one target slot holds a list

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_all(list(target or []), self.gives, controller)


@dataclass(frozen=True)
class DestroyX:
    """Immoral Bargain: "Destroy X target nonland permanents." Exactly X targets, in one list."""
    target: str
    up_to_x = True
    exact_x = True
    multi_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.destroy_all(list(target or []))


@dataclass(frozen=True)
class DestroyUpToX:
    """Pest Infestation: "Destroy up to X target artifacts and/or enchantments." Up to X targets, in one list."""
    target: str
    up_to_x = True
    multi_target = True
    optional_target = True  # it needs no target to be cast

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.destroy_all(list(target or []))


@dataclass(frozen=True)
class CopyTokensOfTargets:
    """Twinflame: "Choose any number of target creatures you control. For each of them, create a token that's a copy of that
    creature, except it has haste. Exile those tokens at the beginning of the next end step." The three sentences are
    folded together by _merge_target_copies. Each target beyond the first costs the strive cost more (see strive_cost)."""
    target: str
    haste: bool = False
    exile_at_end: bool = False
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.copy_tokens(controller, list(target or []), self.haste, self.exile_at_end)


@dataclass(frozen=True)
class _ChooseAnyNumber:
    """ "Choose any number of target creatures you control.": only ever before _CopyEachWithHaste."""
    target: str


@dataclass(frozen=True)
class _CopyEachWithHaste:
    """ "For each of them, create a token that's a copy of that creature, except it has haste." """


@dataclass(frozen=True)
class _ExileThoseTokens:
    """ "Exile those tokens at the beginning of the next end step." """


def _merge_target_copies(effects: list) -> list | None:
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, _ChooseAnyNumber):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _CopyEachWithHaste)):
                return None
            exile = i + 2 < len(effects) and isinstance(effects[i + 2], _ExileThoseTokens)
            merged.append(CopyTokensOfTargets(effect.target, True, exile))
            i += 3 if exile else 2
            continue
        if isinstance(effect, (_CopyEachWithHaste, _ExileThoseTokens)):
            return None
        merged.append(effect)
        i += 1
    return merged


_STRIVE = re.compile(r"Strive \u2014 This spell costs ((?:\{[^}]+\})+) more to cast for each target beyond the first\.")


def strive_cost(card: Card) -> str | None:
    """Twinflame's "Strive": the mana added for each target beyond the first, or None."""
    return next((m[1] for line in rules_lines(card) if (m := _STRIVE.fullmatch(line))), None)


@dataclass(frozen=True)
class GiveBack:
    """ "For each creature destroyed this way, its controller creates a 1/1 white Spirit creature token." Only ever the
    end of a DestroyAll or ExileAll (see _merge_wipe_gift). Ceaseless Conflict pays only the caster, for their own
    nontoken creatures; Oversimplify gives each player one token with a counter per point of power they lost."""
    count: int
    token: Card
    who: str = "controller"  # "controller": each one's controller gets tokens for it; "you": the caster; "each player"
    nontoken: bool = False  # "for each nontoken creature you controlled that was destroyed this way"
    power_counters: bool = False  # "... puts a number of +1/+1 counters on it equal to the total power of the creatures"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone give-back is never built")


@dataclass(frozen=True)
class CannotRegenerate:
    """ "They can't be regenerated." After a destroy effect it is folded into that effect (see _merge_no_regen);
    anywhere else there is nothing for it to stop."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class Regenerate:
    """ "Regenerate target creature." Gives it a shield: the next time it would be destroyed this turn, it is
    tapped, loses its damage and leaves combat instead."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.regenerate(target)


@dataclass(frozen=True)
class RegenerateSource:
    """ "{B}: Regenerate CARDNAME." """
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.regenerate(target)


@dataclass(frozen=True)
class RegenerateEach:
    """ "Regenerate each creature you control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line:
                game.regenerate(permanent)


@dataclass(frozen=True)
class DamageEach:
    """ "This spell deals 2 damage to each creature (and each player)." Nothing is targeted."""
    amount: int | str
    creatures: str | None  # None, "all", or "opponents" (only creatures you don't control)
    players: str | None  # None, "opponents" or "all"
    restriction: MassFilter | None = None  # "each creature with flying"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        amount = game.amount(self.amount)
        if self.creatures:
            kind = "creature" if self.creatures == "all" else "creature you don't control"
            for permanent in game.mass_targets(kind, controller, self.restriction):
                game.damage(permanent, amount)
            if self.creatures == "opponents and planeswalkers":  # Volcanic Torrent
                for permanent in game.mass_targets("planeswalker you don't control", controller, None):
                    game.damage(permanent, amount)
        if self.players:
            for seat in (game.live_seats() if self.players == "all" else game.opponents(controller)):
                game.damage(seat, amount)


@dataclass(frozen=True)
class Amount:
    """A number that depends on the game, worked out when the effect resolves: "its power",
    "the number of Auras you control", "the amount of life you gained this turn", ..."""
    kind: str  # see Game.evaluate
    what: str = ""  # a type ("Aura"), a counter ("+1/+1") or a spell kind ("instant or sorcery spell")


_AMOUNTS = [
    (re.compile(r"(?:its|this creature's|CARDNAME's) power", re.I), lambda m: Amount("source_power")),
    (re.compile(r"the sacrificed creature's power", re.I), lambda m: Amount("sacrificed_power")),
    (re.compile(r"(?:the number of )?Auras? you control that's attached to a creature", re.I),
     lambda m: Amount("auras_on_creatures")),
    (re.compile(r"the number of nontoken creatures you had enter the battlefield under your control this turn", re.I),
     lambda m: Amount("creatures_entered")),
    (re.compile(r"(?:the number of )?([+\-\u2212]1/[+\-\u2212]1|[a-z]+) counters? on (?:it|this creature|this artifact|CARDNAME)",
                re.I), lambda m: Amount("source_counters", _counter_name(m[1].lower()))),
    (re.compile(r"(?:the number of )?(?:(creature|land|artifact|enchantment|instant|sorcery|planeswalker) )?cards? in your graveyard",
                re.I), lambda m: Amount("graveyard", (m[1] or "card").lower())),
    (re.compile(r"(?:the number of )?creatures? on the battlefield", re.I), lambda m: Amount("on_battlefield", "creature")),
    (re.compile(r"the amount of life you gained this turn", re.I), lambda m: Amount("life_gained")),
    (re.compile(r"the amount of life you lost this turn", re.I), lambda m: Amount("life_lost")),
    (re.compile(r"half your life total, rounded (down|up)", re.I), lambda m: Amount("half_life", m[1].lower())),
    (re.compile(r"(?:the number of )?spells? you've cast this turn", re.I), lambda m: Amount("spells_cast")),
    (re.compile(r"the greatest mana value among instant and sorcery spells you've cast this turn", re.I),
     lambda m: Amount("greatest_mana_value_cast", "instant or sorcery spell")),
    (re.compile(r"opponents?", re.I), lambda m: Amount("opponents")),
    (re.compile(r"the amount of mana spent to cast that spell", re.I), lambda m: Amount("mana_spent")),
    (re.compile(r"that spell's mana value", re.I), lambda m: Amount("spell_mana_value")),
    (re.compile(r"(?:the number of )?([A-Za-z]+) you control", re.I), lambda m: Amount("you_control", _singular(m[1]))),
]


def _amount(text: str) -> Amount | None:
    for pattern, build in _AMOUNTS:
        if m := pattern.fullmatch(text):
            return build(m)
    return None


@dataclass(frozen=True)
class DefineX:
    """Sets X for the effects after it ("..., where X is the number of Auras you control.")."""
    amount: Amount

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.x_value = game.evaluate(self.amount, controller)


@dataclass(frozen=True)
class CopySpellTimes:
    """Replicate, Storm and Gravestorm: "When you cast this spell, copy it" `count` times. The spell the ability came from
    is `carried`; the copies may have new targets."""
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        original = game.resolving_item.carried if game.resolving_item else None
        for _ in range(self.count):
            if original is not None:
                game.copy_spell(original, controller, new_targets=True)


@dataclass(frozen=True)
class LivingWeapon:
    """Living weapon: "When this Equipment enters, create a 0/0 black Phyrexian Germ creature token, then attach this to it." """
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.living_weapon(target)


DEMONSTRATE_PROMPT = "Copy it with demonstrate? "  # followed by the spell's name; options are YES_NO
DEMONSTRATE_OPPONENT_PROMPT = "Choose an opponent to also copy "  # followed by the spell's name


@dataclass(frozen=True)
class Backup:
    """Backup N: "When this creature enters, put N +1/+1 counters on target creature. If that's another creature, it
    gains the following abilities until end of turn." `granted` is the rest of the card's rules text."""
    count: int
    granted: str
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, "+1/+1", self.count)
            if target is not game.resolving_source:
                game.grant_abilities(target, self.granted)


@dataclass(frozen=True)
class Demonstrate:
    """Demonstrate: "When you cast this spell, you may copy it. If you do, choose an opponent to also copy it." The
    spell cast is `carried`; each copy's controller chooses new targets."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        spell = game.resolving_item.carried if game.resolving_item is not None else None
        if spell is None or controller.player.choose(DEMONSTRATE_PROMPT + spell.card.name, ["Yes", "No"]) != 0:
            return
        game.copy_spell(spell, controller, new_targets=True)
        opponents = game.opponents(controller)
        if opponents:
            pick = controller.player.choose(DEMONSTRATE_OPPONENT_PROMPT + spell.card.name,
                                            [f"Player: {o.name} (seat {o.index})" for o in opponents])
            game.copy_spell(spell, opponents[pick], new_targets=True)


@dataclass(frozen=True)
class ShuffleRevealCast:
    """Creative Technique: "Shuffle your library, then reveal cards from the top of it until you reveal a nonland card.
    Exile that card and put the rest on the bottom of your library in a random order. You may cast the exiled card
    without paying its mana cost." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.rng.shuffle(controller.library)
        game.cascade(controller, None)


@dataclass(frozen=True)
class Cascade:
    """Cascade: exile cards from the top of your library until you exile a nonland card that costs less than `value`;
    you may cast it without paying its mana cost."""
    value: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.cascade(controller, self.value)


@dataclass(frozen=True)
class PutAttackingFromHand:
    """Kaalia of the Vast: "put an Angel, Demon, or Dragon creature card from your hand onto the battlefield tapped and
    attacking that opponent." The opponent is the player the trigger was about."""
    types: tuple[str, ...]
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_attacking_from_hand(controller, target, self.types)


@dataclass(frozen=True)
class SacrificeSelf:
    """Evoke: "When this creature enters, sacrifice it." """
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game._leave_battlefield(target, "sacrificed")


@dataclass(frozen=True)
class SacrificeCreature:
    """ "Sacrifice a creature." (you choose which) """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.sacrifice(controller)


@dataclass(frozen=True)
class EachSacrifices:
    """ "Each opponent sacrifices a creature." / "Each player sacrifices a land." """
    who: str  # "opponent", "player" or "you" ("Sacrifice two lands.")
    kind: str = "creature"  # "creature", "artifact", "enchantment", "land", "permanent", "nonland permanent", ...
    count: int | str | None = 1  # "two lands"; None: "all creatures they control"
    greatest: bool = False  # "a creature with the greatest power among creatures they control"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "player" or (self.who == "you") == (seat is controller):
                game.sacrifice(seat, self.kind, None if self.count is None else game.amount(self.count), self.greatest)


@dataclass(frozen=True)
class SacrificeAll:
    """ "Sacrifice all creatures you control." """
    kind: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.sacrifice(controller, self.kind, None)


@dataclass(frozen=True)
class TargetSacrifices:
    """ "Target player sacrifices a creature." (target is "player" or "opponent") """
    target: str
    kind: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.sacrifice(target, self.kind)


_MASS_KINDS = {"battles": "battle", "creatures": "creature", "creature tokens": "creature", "artifacts": "artifact", "enchantments": "enchantment",
               "planeswalkers": "planeswalker", "lands": "land", "nonland permanents": "nonland permanent",
               "artifacts and enchantments": "artifact or enchantment",
               "creatures and planeswalkers": "creature or planeswalker"}
_MASS = (r"(battles|artifacts and enchantments|creatures and planeswalkers|nonland permanents|creatures|artifacts"
         r"|enchantments|planeswalkers|lands)( you don't control| you control| an opponent controls| your opponents control)?")


def _mass_kind(m: re.Match) -> str:
    return _MASS_KINDS[m[1].lower()] + (m[2] or "").replace(" your opponents control", " an opponent controls")


_SACRIFICE_KIND = (r"(attacking creature|tapped creature|untapped creature|creature|artifact or enchantment|nontoken artifact|food|treasure|clue|artifact"
                   r"|enchantment|land|nonland permanent|permanent)")
_FIGHTER = r"(creature(?: you control| you don't control| an opponent controls)?)"
_MASS_KEYWORDS = (r"(?:flying|reach|trample|haste|vigilance|menace|deathtouch|lifelink|first strike|double strike"
                  r"|defender|indestructible|hexproof)")
_RESTRICTION = rf"(with (?:power|toughness|mana value) \d+ or (?:greater|less)|with {_MASS_KEYWORDS}|without {_MASS_KEYWORDS})"
_COLOR_ADJECTIVE = r"(?:(non)?(white|blue|black|red|green|token|legendary|basic|tapped|untapped) )?"
_STAT_RESTRICTION = re.compile(r"with (power|toughness|mana value) (\d+) or (greater|less)")
_EXCEPT = (r"(?: except(?: for)? ((?:(?:artifact|enchantment|legendary|white|blue|black|red|green) )?"
           rf"(?:creatures|lands|permanents|tokens)(?: with {_MASS_KEYWORDS})?))?")
_THAT_ARE = r"(?: that (are (?:one or more colors|colorless|multicolored|monocolored)|aren't enchanted))?"


# The same, with an optional color adjective before and "with flying" etc. after (destroy and exile only).
_MASS_NOUN = (r"(battles|artifacts and enchantments|creatures and planeswalkers|nonland permanents|creature tokens|creatures|artifacts"
              r"|enchantments|planeswalkers|lands)")
_MASS_FILTERED = rf"{_COLOR_ADJECTIVE}{_MASS_NOUN}(?: {_RESTRICTION})?( you don't control| you control| an opponent controls| your opponents control)?{_EXCEPT}{_THAT_ARE}"


def _mass_effect(cls: type, m: re.Match) -> Any:
    kind = _MASS_KINDS[m[3].lower()] + (m[5] or "").replace(" your opponents control", " an opponent controls")
    return cls(kind, _mass_filter(m[1], m[2], m[4], tokens=m[3].lower() == "creature tokens", spared=m[6], colors_are=m[7]))


_TRAITS = {"token": "token", "legendary": "legendary", "basic": "basic", "tapped": "tapped", "untapped": "tapped"}


def _mass_filter(non: str | None, color: str | None, restriction: str | None, tokens: bool = False,
                 spared: str | None = None, colors_are: str | None = None) -> MassFilter | None:
    """The filter for an optional adjective ("nonblack", "nontoken", "legendary", "tapped"), an optional "with ..." /
    "without ..." phrase, "creature tokens", and an optional "except for ..." (what is left alone)."""
    fields: dict[str, Any] = {}
    if color and color.lower() in _COLOR_WORDS:
        fields.update(color=_COLOR_WORDS[color.lower()], other_color=bool(non))
    elif color:
        wanted = not non and color.lower() != "untapped"
        fields[_TRAITS[color.lower()]] = wanted
    if tokens:
        fields["token"] = True
    if restriction:
        if m := _STAT_RESTRICTION.fullmatch(restriction.lower()):
            fields.update(stat=m[1].replace(" ", "_"), **{"at_least" if m[3] == "greater" else "at_most": int(m[2])})
        else:
            fields.update(keyword=restriction.lower().split(" ", 1)[1], keyword_wanted=restriction.lower().startswith("with "))
    if spared:
        fields["exclude"] = _spared_filter(spared.lower())
    if colors_are == "aren't enchanted":
        fields["enchanted"] = False
    elif colors_are:
        fields["colors_are"] = colors_are.lower().removeprefix("are ")
    return MassFilter(**fields) if fields else None


def _spared_filter(text: str) -> MassFilter:
    """What an "except for ..." leaves alone: "artifact creatures", "legendary creatures", "white creatures", "tokens",
    "creatures with flying"."""
    fields: dict[str, Any] = {}
    head, _, keyword = text.partition(" with ")
    if keyword:
        fields.update(keyword=keyword, keyword_wanted=True)
    first = head.split(" ")[0]
    if first in _COLOR_WORDS:
        fields.update(color=_COLOR_WORDS[first])
    elif first == "legendary":
        fields["legendary"] = True
    elif first in ("artifact", "enchantment"):
        fields["has_type"] = first.capitalize()
    elif head == "tokens":
        fields["token"] = True
    return MassFilter(**fields)


_SACRIFICE_PLURAL = r"(creatures|artifacts or enchantments|artifacts|enchantments|lands|nonland permanents|permanents)"
_PLURAL_SACRIFICE = {"creatures": "creature", "artifacts or enchantments": "artifact or enchantment",
                     "artifacts": "artifact", "enchantments": "enchantment", "lands": "land",
                     "nonland permanents": "nonland permanent", "permanents": "permanent"}


class _GiftMatch:
    """A token specification and whether its quoted ability's closing quote was there (see _create)."""
    def __init__(self, spec: str, quote: str):
        self.spec, self.quote = spec, quote


def _gift(m: _GiftMatch, **fields: Any) -> Any:
    parsed = _token(m.spec + '."' if m.quote else m.spec)
    return GiveBack(*parsed, **fields) if parsed else None


def _damage_each(m: re.Match) -> DamageEach | None:
    creatures = players = None
    if m[3] and not m[2].lower().startswith("creature"):
        return None  # "each opponent with flying" isn't a thing
    for part in (m[2].lower(), (m[4] or "").lower()):
        if part == "creature":
            creatures = "all"
        elif part in ("creature you don't control", "creature your opponents control"):
            creatures = "opponents"
        elif part == "creature and planeswalker your opponents control":
            creatures = "opponents and planeswalkers"
        elif part:
            players = "all" if part == "player" else "opponents"
    return DamageEach(_count(m[1]), creatures, players, _mass_filter(None, None, m[3]))


@dataclass(frozen=True)
class ReturnToHand:
    """Bounce: "Return target nonland permanent you don't control to its owner's hand." """
    target: str
    another: bool = False  # "Return another target creature ...": not the source itself
    optional_target: bool = False  # "Return up to one target creature ...": the target may be left out
    distinct: bool = False  # "Return up to two target creatures ...": the second can't be the first again

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_to_hand(target)


@dataclass(frozen=True)
class ReturnAllToHand:
    kind: str
    restriction: MassFilter | None = None  # Perplexing Test: "all creature tokens" / "all nontoken creatures"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_all_to_hand(game.mass_targets(self.kind, controller, self.restriction))


@dataclass(frozen=True)
class ReturnFromGraveyard:
    """ "Return target creature card from your graveyard to your hand / to the battlefield." """
    target: str  # "graveyard:<card type>:<yours|any>"
    to: str  # "hand" or "battlefield"
    tapped: bool = False  # "... to the battlefield tapped"
    optional_target: bool = False  # "Return up to two target creature cards ...": each may be left out
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_from_graveyard(target, controller, self.to, self.tapped)


@dataclass(frozen=True)
class LoseLifeEqualToManaValue:
    """Reanimate: "You lose life equal to its mana value." (the card the previous effect put onto the battlefield)"""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(controller, -int(target.card.cmc))


@dataclass(frozen=True)
class ShuffleIntoLibrary:
    """Perpetual Timepiece: "Shuffle any number of target cards from your graveyard into your library." """
    target: str = "graveyard:card:yours"
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.shuffle_into_library(controller, list(target or []))


@dataclass(frozen=True)
class ReturnAllFromGraveyard:
    """Eiganjo Dynastorian's spell: "Return all enchantment cards from your graveyard to the battlefield." (or to your hand)"""
    kind: str  # a card kind, "enchantment"
    to: str = "battlefield"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_all_from_graveyard(controller, self.kind, self.to)


@dataclass(frozen=True)
class ExileFromGraveyard:
    target: str
    if_type: str = ""  # Feral Appetite: "If a creature card is exiled this way, create a ... token": the card type
    then: Any = None  # ... and what happens then
    copy_token: bool = False  # Lorehold Archivist's spell: "Create a token that's a copy of it."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or not game.exile_from_graveyard(target):
            return
        if self.then and self.if_type.capitalize() in target.card.type_line:
            self.then.resolve(game, controller, None)
        if self.copy_token:
            card = target.card
            game.create_tokens(controller, card if card.type_line.startswith("Token") else
                               dataclasses.replace(card, type_line="Token " + card.type_line), 1)


@dataclass(frozen=True)
class _TheyGain:
    """ "Those creatures gain flying until end of turn." / "They gain trample ..." after counters on several creatures."""
    keywords: frozenset[str]


@dataclass(frozen=True)
class CopySelfToken:
    """Leitmotif Composer: "Create a token that's a copy of this creature." """
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            card = target.card if target.card.type_line.startswith("Token") else \
                dataclasses.replace(target.card, type_line="Token " + target.card.type_line)
            game.create_tokens(controller, card, 1)


@dataclass(frozen=True)
class AttachThisToSubject:
    """Shielded by Faith: "You may attach this Aura to that creature." (the creature that entered)"""
    uses_subject = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.resolving_source is not None:
            game.attach(game.resolving_source, target)


@dataclass(frozen=True)
class CreateTokenAttachSubject:
    """Ajani's Chosen: "Create a 2/2 white Cat creature token. If that enchantment is an Aura, you may attach it to the token." """
    token: Card
    uses_subject = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        made = game.create_tokens(controller, self.token, 1)
        if made and target is not None and "Aura" in target.card.type_line and game.on_battlefield(target):
            game.may_attach(controller, target, made[0])


@dataclass(frozen=True)
class _AttachItToToken:
    """ "If that enchantment is an Aura, you may attach it to the token." after a CreateTokens (see _merge_conditional)."""


@dataclass(frozen=True)
class MillThenExileRandomPlay:
    """Advanced Reconstruction: "Mill a card, then exile a card from your graveyard at random. You may play the exiled card this
    turn." (one template across two sentences)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.mill(controller, 1)
        game.exile_random_from_graveyard(controller, play_this_turn=True)


@dataclass(frozen=True)
class ExileDiscarded:
    """Containment Construct: "Whenever you discard a card, you may exile that card from your graveyard. If you do, you may play
    that card this turn." (the trigger is "you may")"""
    play: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        card = item.carried if item is not None else None
        if isinstance(card, Card) and any(c is card for c in controller.graveyard):
            game.exile_card_from_graveyard(controller, card, play_this_turn=self.play)


@dataclass(frozen=True)
class TapAndGoad:
    """Killian, Decisive Mentor: "Tap up to one target creature and goad it." """
    target: str = "creature"
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)
            game.goad(target, controller)


@dataclass(frozen=True)
class _ItHas:
    """ "It has "Sacrifice this token: Add {C}."" after a token was created (see _merge_conditional)."""
    ability: str


@dataclass(frozen=True)
class _CopyOfIt:
    """ "Create a token that's a copy of it." after an exile (see _merge_conditional)."""


@dataclass(frozen=True)
class _InsteadDraw:
    """ "If you control eight or more lands, draw two cards instead." (see _merge_conditional)"""
    condition: "Condition"
    count: int


@dataclass(frozen=True)
class _UntapThatLand:
    """ "Then if you control four or more lands, untap that land." """
    condition: "Condition"


@dataclass(frozen=True)
class _IfExiledThen:
    """ "If a creature card is exiled this way, create a ... token." """
    card_type: str
    effect: Any


@dataclass(frozen=True)
class Conditional:
    """ "Then if there are three or more creature cards in your graveyard, this creature becomes prepared.": the effect
    happens only if the condition holds as it resolves."""
    condition: "Condition"
    effect: Any

    @property
    def uses_source(self) -> bool:
        return uses_source(self.effect)

    @property
    def uses_subject(self) -> bool:
        return uses_subject(self.effect)

    @property
    def uses_player(self) -> bool:
        return uses_player(self.effect)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.condition_holds(self.condition, controller, game.resolving_source):
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class ExileOwnGraveyard:
    """Emeritus of Ideation: "Exile eight cards from your graveyard. If you do, this creature becomes prepared." (the
    trigger is "you may"); nothing happens if there are fewer cards than that."""
    count: int
    then: Any = None

    @property
    def uses_source(self) -> bool:
        return uses_source(self.then) if self.then else False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.exile_own_graveyard(controller, self.count) and self.then:
            self.then.resolve(game, controller, target)


@dataclass(frozen=True)
class _IfYouDo:
    """ "If you do, <effect>." after an effect that can be declined or fail (see _merge_conditional)."""
    effect: Any


def _if_you_do(m: re.Match) -> Any:
    inner = _parse([m[1][:1].upper() + m[1][1:] + "."])
    return _IfYouDo(inner[0]) if inner and len(inner) == 1 and isinstance(inner[0], BecomePrepared) else None


def _then_if(m: re.Match) -> Any:
    condition = _condition(m[1])
    inner = _parse([m[2][:1].upper() + m[2][1:] + "."]) if condition else None
    if not inner or len(inner) != 1 or target_kind(inner[0]):
        return None
    return Conditional(condition, inner[0])


def _is_known_ability(text: str) -> bool:
    """Whether a quoted ability is one we understand (the same test a token's own quoted ability has to pass)."""
    return _token(f'a 1/1 colorless Test creature token with "{text}"') is not None


def _merge_conditional(effects: list) -> list | None:
    """The sentences that qualify the effect before them: a bigger draw, an untap, a token for an exiled creature card."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, _InsteadDraw):
            if not (merged and isinstance(merged[-1], Draw)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], more=effect.count, more_if=effect.condition)
        elif isinstance(effect, _UntapThatLand):
            if not (merged and isinstance(merged[-1], FetchBasicLand)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], untap_if=effect.condition)
        elif isinstance(effect, _ManaForEachDestroyed):
            if not (merged and isinstance(merged[-1], DestroyAll)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], mana_each=effect.options)
        elif isinstance(effect, Fight) and effect.optional_target:  # "Then it fights ...": it is the creature just pumped
            if not (merged and isinstance(merged[-1], PumpX)):
                return None
            merged.append(effect)
        elif isinstance(effect, _PutFromAmongThem):
            if not (merged and isinstance(merged[-1], Mill)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], put=effect.kind)
        elif isinstance(effect, _TheyGain):
            if not (merged and isinstance(merged[-1], (PutCountersOnEach, PutCountersOnEachUpToX))):
                return None
            merged[-1] = dataclasses.replace(merged[-1], grant=effect.keywords)
        elif isinstance(effect, _AttachItToToken):
            if not (merged and isinstance(merged[-1], CreateTokens) and merged[-1].count == 1):
                return None
            merged[-1] = CreateTokenAttachSubject(merged[-1].token)
        elif isinstance(effect, _PopulatedTokenRider):
            if not (merged and isinstance(merged[-1], Populate)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], haste=merged[-1].haste or effect.haste,
                                             sacrifice_at_end=merged[-1].sacrifice_at_end or effect.sacrifice)
        elif isinstance(effect, _ItHas):
            if not (merged and isinstance(merged[-1], CreateTokens) and not merged[-1].token.oracle_text):
                return None
            merged[-1] = dataclasses.replace(merged[-1], token=dataclasses.replace(merged[-1].token, oracle_text=effect.ability))
        elif isinstance(effect, _CopyOfIt):
            if not (merged and isinstance(merged[-1], ExileFromGraveyard)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], copy_token=True)
        elif isinstance(effect, _TokenGainsHaste):
            if not (merged and isinstance(merged[-1], CopyToken)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], haste=True)
        elif isinstance(effect, _IfYouDo):
            if not (merged and isinstance(merged[-1], ExileOwnGraveyard)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], then=effect.effect)
        elif isinstance(effect, _IfExiledThen):
            if not (merged and isinstance(merged[-1], ExileFromGraveyard)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], if_type=effect.card_type, then=effect.effect)
        else:
            merged.append(effect)
    return merged


def _if_exiled(m: re.Match) -> Any:
    rest = _parse([m[2][:1].upper() + m[2][1:] + m[3]])
    return _IfExiledThen(m[1], rest[0]) if rest and len(rest) == 1 and not target_kind(rest[0]) else None


@dataclass(frozen=True)
class SearchLibrary:
    """ "Search your library for a creature card, put it into your hand, then shuffle." """
    card_type: str  # "card", "creature", "instant or sorcery", "basic land", ...
    to: str  # "hand", or "top" of the library after shuffling
    reveal: bool  # "reveal it": everyone sees which card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tutor(controller, self.card_type, self.to, self.reveal)


@dataclass(frozen=True)
class LoseLife:
    amount: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.change_life(controller, -game.amount(self.amount))


@dataclass(frozen=True)
class SearchForLands:
    """Land ramp: "Search your library for up to two basic land cards, reveal those cards, put one onto
    the battlefield tapped and the other into your hand, then shuffle." (Cultivate)"""
    count: int  # up to this many
    subtypes: tuple[str, ...]  # () means basic lands; otherwise lands with one of these land types
    battlefield: int  # how many go onto the battlefield (the rest go to the hand)
    tapped: bool
    reveal: bool
    basic_only: bool = False  # "basic Plains cards": the land types and also basic

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.search_for_lands(controller, self.count, self.subtypes, self.battlefield, self.tapped, self.reveal, self.basic_only)


RETURN_LAND_PROMPT = "Return which land to your hand? "


@dataclass(frozen=True)
class ReturnOwnLand:
    """Bounceland: "Return a land you control to its owner's hand." (you choose; it can be the land itself)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        lands = [p for p in controller.battlefield if "Land" in p.card.type_line]
        if lands:
            game.return_to_hand(lands[controller.player.choose(RETURN_LAND_PROMPT, [game.label(p) for p in lands])])


@dataclass(frozen=True)
class Scry:
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.scry(controller, game.amount(self.count))


@dataclass(frozen=True)
class RevealTop:
    """ "Scry 1, then reveal the top card of your library. If it's a land card, put it onto the battlefield tapped.
    Otherwise, draw a card." (Thrasios). Only built by _merge_reveal_top."""
    scry: int
    tapped: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.reveal_top_land_or_draw(controller, self.scry, self.tapped)


@dataclass(frozen=True)
class RevealTopStep:
    """One sentence of RevealTop; alone it isn't understood. kind: "reveal" (with scry), "land" or "otherwise"."""
    kind: str
    scry: int = 0
    tapped: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone reveal-the-top step is never built")


@dataclass(frozen=True)
class AddMana:
    """Ritual: "Add {B}{B}{B}." The mana waits in its controller's pool until the step ends."""
    units: tuple[frozenset[str], ...]

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.add_mana(controller, self.units)


@dataclass(frozen=True)
class ExileAllGraveyards:
    """ "Exile all cards from all graveyards." (Rest in Peace) """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_all_graveyards()


@dataclass(frozen=True)
class CopySpell:
    """ "Copy target instant or sorcery spell. You may choose new targets for the copy." """
    target: str  # "instant or sorcery spell", optionally "... you control"
    new_targets: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_spell(target, controller, self.new_targets)


@dataclass(frozen=True)
class CopyNextSpell:
    """Pigment Wrangler's spell: "When you next cast an instant or sorcery spell this turn, copy that spell. You may choose new
    targets for the copy." (see Game._cast)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.copy_next_turn = game.turn


@dataclass(frozen=True)
class CopyTriggeringSpell:
    """Codie: "Whenever you cast a prepared spell, copy it. You may choose new targets for the copy." The spell that set
    the trigger off is `carried`."""
    new_targets: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        spell = game.resolving_item.carried if game.resolving_item is not None else None
        if spell is not None:
            game.copy_spell(spell, controller, self.new_targets)


@dataclass(frozen=True)
class NewTargets:
    """ "You may choose new targets for the copy." Only meaningful after a copy effect (_merge_copy folds it in)."""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class GainControl:
    """ "Gain control of target creature (until end of turn). (Untap that creature. It gains haste until end of
    turn.)" """
    target: str
    until_end_of_turn: bool = False
    untap: bool = False
    haste: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.gain_control(target, controller, until_eot=self.until_end_of_turn, untap=self.untap, haste=self.haste)


@dataclass(frozen=True)
class UntapThat:
    """ "Untap that creature." Only meaningful right after "Gain control of ...": _merge_control folds it in."""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class Tap:
    """ "Tap two target permanents.": one effect per target, each a different permanent."""
    target: str
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)


@dataclass(frozen=True)
class TapThat:
    """ "Tap it." / "Tap that creature.": the target of the effect before it."""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)


_CONTROL_AURA = "You control enchanted creature."


def aura_controls(card: Card) -> bool:
    """Control Magic: an Aura that gives its controller control of the enchanted creature."""
    return "Aura" in card.type_line and _CONTROL_AURA in rules_lines(card)


def is_control_aura_line(line: str) -> bool:
    return line == _CONTROL_AURA


@dataclass(frozen=True)
class BecomeCreature:
    """Crewing a Vehicle: until end of turn it is an artifact creature."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.become_creature(target)


@dataclass(frozen=True)
class Proliferate:
    """ "Proliferate.": choose any permanents with counters; each gets one more counter of each kind it has."""
    times: int | str = 1  # "Proliferate X times."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for _ in range(game.amount(self.times)):
            game.proliferate(controller)


@dataclass(frozen=True)
class FightFirst:
    """The first target of a fight ("Target creature you control ... fights ..."): remembered for the second."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


@dataclass(frozen=True)
class Fight:
    """The second target of a fight. Each deals damage equal to its power to the other; with `one_sided` only the
    first does ("Target creature you control deals damage equal to its power to target creature you don't control")."""
    target: str
    one_sided: bool = False
    another: bool = False  # "fights another target creature": not the first target
    optional_target: bool = False  # "fights up to one target creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        first = game.resolving_item.carried if game.resolving_item is not None else None
        if first is not None and target is not None and first is not target:
            game.fight(first, target, self.one_sided)


@dataclass(frozen=True)
class ReturnWithCounter:
    """Persist and undying: the creature that died comes back with a counter on it."""
    counter: str  # "-1/-1" (persist) or "+1/+1" (undying)
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_with_counter(target, self.counter)


@dataclass(frozen=True)
class ExtraTurn:
    """ "Take an extra turn after this one." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.extra_turns.append(controller.index)


@dataclass(frozen=True)
class TargetExtraTurn:
    """ "Target player takes an extra turn after this one." """
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.extra_turns.append(target.index)


@dataclass(frozen=True)
class ExtraCombat:
    """ "After this phase, there is an additional combat phase (followed by an additional main phase)." """
    main: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.add_combat(self.main)


@dataclass(frozen=True)
class UntapCreatures:
    which: str  # "attacked": the creatures that attacked this turn; "yours": every creature you control

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in controller.battlefield:
            if "Creature" in permanent.card.type_line and (self.which == "yours" or permanent.attacked_turn == game.turn):
                permanent.tapped = False


@dataclass(frozen=True)
class Untap:
    """ "Untap target land." """
    target: str
    another: bool = False
    optional_target: bool = False  # "Untap up to two target lands"
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.tapped = False


@dataclass(frozen=True)
class UntapSource:
    """ "Untap it" / "Untap this creature": the ability's source (or, in a watching trigger, the permanent that set it off)."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.tapped = False


@dataclass(frozen=True)
class UntapAll:
    """ "Untap all lands you control." """
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.untap_all(controller, self.kind)


@dataclass(frozen=True)
class TapAll:
    """ "Tap all creatures your opponents control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            for permanent in seat.battlefield:
                if "Creature" in permanent.card.type_line:
                    game.tap(permanent)


@dataclass(frozen=True)
class BecomeMonarch:
    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.become_monarch(controller)


@dataclass(frozen=True)
class VoteStart:
    """ "Starting with you, each player votes for X or Y." (options), or for a nonland permanent (None). Only ever a
    step of a Vote or VoteToExile (see _merge_votes)."""
    options: tuple[str, str] | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone vote is never built")


@dataclass(frozen=True)
class VoteOutcome:
    """ "For each X vote, ..." (each) or "If X gets more votes [or the vote is tied], ..." (more): what happens."""
    kind: str  # "each" or "more"
    option: str
    effects: tuple
    tie: bool = False  # "or the vote is tied"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone vote outcome is never built")


@dataclass(frozen=True)
class ExileMostVoted:
    """ "Exile each permanent with the most votes or tied for most votes." Only ever the end of a permanent vote."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone exile of the most voted is never built")


@dataclass(frozen=True)
class Vote:
    """Each player votes for one of two words; the outcomes follow the votes (the effects need no target)."""
    options: tuple[str, str]
    outcomes: tuple[VoteOutcome, ...]

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        counts = dict(zip(self.options, game.vote(controller, list(self.options))))
        for outcome in self.outcomes:
            if outcome.kind == "each":
                times = counts[outcome.option]
            else:
                other = next(o for o in self.options if o != outcome.option)
                times = int(counts[outcome.option] > counts[other]
                            or (outcome.tie and counts[outcome.option] == counts[other]))
            for _ in range(times):
                for effect in outcome.effects:
                    effect.resolve(game, controller, None)


_NO_MAX_HAND = "You have no maximum hand size."


def no_max_hand_size(card: Card) -> bool:
    """Reliquary Tower, Thought Vessel: their controller discards nothing down to seven at the end of turn."""
    return any(line == _NO_MAX_HAND for line in rules_lines(card))


def is_no_max_hand_line(line: str) -> bool:
    return line == _NO_MAX_HAND


_EXTRA_VOTE = "While voting, you may vote an additional time."


def extra_votes(card: Card) -> int:
    """Tivit, Seller of Secrets: how many additional times its controller may vote (the votes can differ)."""
    return int(any(line == _EXTRA_VOTE for line in rules_lines(card)))


def is_extra_vote_line(line: str) -> bool:
    return line == _EXTRA_VOTE


@dataclass(frozen=True)
class VoteToExile:
    """Council's Judgment."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.vote_to_exile(controller)


@dataclass(frozen=True)
class TakeInitiative:
    """ "You take the initiative." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.take_initiative(controller)


@dataclass(frozen=True)
class ThroneOfTheDeadThree:
    """The last room of the Undercity; the engine puts it on the stack itself."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.throne_of_the_dead_three(controller)


@dataclass(frozen=True)
class ReturnSelfToHand:
    """Rancor: "When this Aura is put into a graveyard from the battlefield, return it to its owner's hand." (and "When
    enchanted creature dies, return this Aura ..."). It is already in the graveyard when this resolves."""
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        if game.on_battlefield(target):  # Mana Bloom: "return it to its owner's hand" from the battlefield
            game.return_to_hand(target)
        else:
            game.return_to_hand_from_graveyard(target.card)


@dataclass(frozen=True)
class BecomePrepared:
    """ "This creature becomes prepared." While it is, its controller may cast a copy of its spell half (see
    Game.legal_actions); doing so unprepares it. Only creatures with a prepare spell can become prepared."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.prepare(target)


@dataclass(frozen=True)
class TargetPrepared:
    """ "Target creature becomes prepared / unprepared." Only a creature with a prepare spell can become prepared."""
    target: str  # "creature" or "creature that attacked this turn"
    prepared: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.prepare(target) if self.prepared else game.unprepare(target)


@dataclass(frozen=True)
class PrepareEach:
    """ "Each creature you control becomes prepared." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            game.prepare(permanent)


_ENTERS_PREPARED = re.compile(rf"{_SELF} enters prepared\.", re.I)


def enters_prepared(card: Card) -> bool:
    """Whether a prepare creature "enters prepared"."""
    return card.prepare is not None and any(_ENTERS_PREPARED.fullmatch(line) for line in rules_lines(card))


def is_enters_prepared_line(line: str) -> bool:
    return _ENTERS_PREPARED.fullmatch(line) is not None


@dataclass(frozen=True)
class ReturnDeadToBattlefield:
    """Changing Loyalty and Gift of Immortality: "When enchanted creature dies, return it / that card to the battlefield
    under your / its owner's control." It is already in the graveyard when this resolves."""
    under_owner: bool
    uses_dead_subject = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_dead_to_battlefield(target, controller, self.under_owner)


@dataclass(frozen=True)
class ReturnAuraToBattlefield:
    """Screams from Within, Ghoulish Impetus and Gift of Immortality: "When enchanted creature dies, return this card
    [from your graveyard] to the battlefield [attached to that creature] [at the beginning of the next end step]." """
    when: str = "now"  # or "end_step"
    to_host: bool = False  # it comes back attached to the creature that died (which came back first); otherwise you choose
    uses_dead_both = True  # resolves with (the Aura, the creature that died)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_aura(target[0], controller, self.when, target[1] if self.to_host else None)


@dataclass(frozen=True)
class Goad:
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.goad(target, controller)


@dataclass(frozen=True)
class GoadAll:
    """ "Goad all creatures you don't control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            for permanent in list(seat.battlefield):
                if "Creature" in permanent.card.type_line:
                    game.goad(permanent, controller)


@dataclass(frozen=True)
class UnlessPays:
    """ "Draw a card unless that player pays {1}": the effects happen unless the player who set the trigger off pays.
    Only for effects that need no target, so they run the same either way."""
    effects: tuple
    cost: str
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.pays_unless(target, self.cost, game.resolving_item.card):
            return
        for effect in self.effects:
            effect.resolve(game, controller, None)


@dataclass(frozen=True)
class LookAtTop:
    """ "Look at the top five cards of your library." Only ever a step of an Impulse (see _merge_impulse)."""
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone look at the top of the library is never built")


@dataclass(frozen=True)
class TakeFromTop:
    """The sentence after a look: "Put one of them into your hand and the rest on the bottom of your library in any
    order." (card_type None) or "You may reveal a creature card from among them and put it into your hand." """
    card_type: str | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone take from the top is never built")


@dataclass(frozen=True)
class RestOnBottom:
    """ "Put the rest on the bottom of your library in a random order." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone put-the-rest is never built")


@dataclass(frozen=True)
class Impulse:
    """Look at the top cards, take one, put the rest on the bottom."""
    count: int | str
    card_type: str | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_at_top(controller, game.amount(self.count), self.card_type)


@dataclass(frozen=True)
class PutBackTop:
    """ "Look at the top three cards of your library, then put them back in any order. (You may shuffle.)" """
    count: int
    shuffle: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.rearrange_top(controller, game.amount(self.count), self.shuffle)


@dataclass(frozen=True)
class DrawThenPutBack:
    """Brainstorm: "Draw three cards, then put two cards from your hand on top of your library in any order." """
    draw: int
    put: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.draw(controller, self.draw)
        game.put_back_from_hand(controller, self.put)


@dataclass(frozen=True)
class _MayShuffle:
    """ "You may shuffle." after putting cards back (see _merge_put_back)."""


@dataclass(frozen=True)
class Surveil:
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.surveil(controller, game.amount(self.count))


@dataclass(frozen=True)
class Mill:
    """ "Mill three cards." / "Each opponent mills three cards." / "Each player mills three cards." """
    count: int | str
    who: str  # "you", "each opponent" or "each player"
    put: str = ""  # Vastlands Scavenger: "Then put a creature card from among them onto the battlefield." (the card kind)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "each player" or (self.who == "you") == (seat is controller):
                milled = game.mill(seat, game.amount(self.count))
                if self.put:
                    game.return_chosen_from(seat, milled, self.put, "battlefield")


@dataclass(frozen=True)
class _PutFromAmongThem:
    """ "Then put a creature card from among them onto the battlefield." after a Mill (see _merge_conditional)."""
    kind: str


@dataclass(frozen=True)
class Discard:
    """ "Discard a card." / "Each opponent discards two cards." / "Each player discards their hand." (count None) """
    count: int | str | None
    who: str  # "you", "each opponent" or "each player"
    random: bool = False  # "at random"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "each player" or (self.who == "you") == (seat is controller):
                game.discard(seat, None if self.count is None else game.amount(self.count), self.random)


@dataclass(frozen=True)
class DiscardHandsDrawGreatest:
    """Windfall: "Each player discards their hand, then draws cards equal to the greatest number of cards a player
    discarded this way." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        seats = game.turn_order_from_active()
        discarded = {seat.index: len(seat.hand) for seat in seats}
        for seat in seats:
            game.discard(seat, None)
        most = max(discarded.values(), default=0)
        for seat in seats:
            game.draw(seat, most)


@dataclass(frozen=True)
class TargetDiscard:
    """ "Target player (or opponent) discards two cards." """
    count: int | str
    target: str  # "player" or "opponent"
    random: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.discard(target, game.amount(self.count), self.random)


@dataclass(frozen=True)
class EachDraw:
    """ "Each player draws seven cards." """
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            game.draw(seat, game.amount(self.count))


@dataclass(frozen=True)
class RevealHand:
    """ "Target opponent reveals their hand." Only ever the start of a TargetChooseDiscard (see _merge_hand_discard)."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone reveal of a hand is never built")


@dataclass(frozen=True)
class ChooseFromHand:
    """ "You choose a nonland card (with mana value 3 or less) from it." """
    excluded: tuple[str, ...]  # card types it can't be, lowercase
    max_mv: int | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone choice from a hand is never built")


@dataclass(frozen=True)
class DiscardChosen:
    """ "That player discards that card." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone discard of the chosen card is never built")


@dataclass(frozen=True)
class TargetChooseDiscard:
    """Thoughtseize, Duress, Inquisition of Kozilek: look at their hand and make them discard a card you choose."""
    target: str  # "player" or "opponent"
    excluded: tuple[str, ...]
    max_mv: int | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.reveal_and_discard(controller, target, self.excluded, self.max_mv)


@dataclass(frozen=True)
class TargetMill:
    """ "Target player (or opponent) mills three cards." """
    count: int | str
    target: str  # "player" or "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.mill(target, game.amount(self.count))


@dataclass(frozen=True)
class SacrificeUnlessReturnLand:
    """The Karoo cycle: "When this land enters, sacrifice it unless you return an untapped Mountain you control to its
    owner's hand." """
    land_type: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.karoo(controller, target, self.land_type)


@dataclass(frozen=True)
class EntersTapped:
    """How a permanent (usually a land) may enter tapped. `kind` is one of: "always",
    "unless_land_types" (checklands), "unless_lands_at_most" (fastlands), "unless_lands_at_least"
    (slowlands), "unless_opponents" (bond lands), "unless_basic_lands" (Port-style lands), "unless_land_type_count"
    ("three or more other Islands"), "unless_opponent_lands" (Turbulent lands), "reveal" (Snarls: reveal a card from your
    hand or it enters tapped), "shock" (pay life or it enters tapped),
    "unless_control" (`types` are alternatives, each "Legendary+Creature"-style words that must all be types of one
    permanent you control), "unless_a_player_life" (a player has `count` or less life), "if_lands_at_least" (tapped if
    you control `count` or more other lands) and "if_starting_player"."""
    kind: str
    types: tuple[str, ...] = ()
    count: int = 0
    life: int = 0


_LAND_TYPE = r"(?:Plains|Island|Swamp|Mountain|Forest)"
_ENTERS_TAPPED = [
    (re.compile(rf"{_SELF} enters tapped\.", re.I), lambda m: EntersTapped("always")),
    (re.compile(rf"{_SELF} enters tapped unless you control an? ({_LAND_TYPE}) or an? ({_LAND_TYPE})\.", re.I),
     lambda m: EntersTapped("unless_land_types", types=(m[1].capitalize(), m[2].capitalize()))),
    (re.compile(rf"{_SELF} enters tapped unless you control {_N} or (fewer|more) other lands\.", re.I),
     lambda m: EntersTapped("unless_lands_at_most" if m[2].lower() == "fewer" else "unless_lands_at_least",
                            count=_count(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless you have {_N} or more opponents\.", re.I),
     lambda m: EntersTapped("unless_opponents", count=_count(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless you control {_N} or more basic lands\.", re.I),
     lambda m: EntersTapped("unless_basic_lands", count=_count(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless you control {_N} or more other ({_LAND_TYPE})s?\.", re.I),
     lambda m: EntersTapped("unless_land_type_count", types=(m[2].capitalize(),), count=_count(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless your opponents control {_N} or more lands\.", re.I),
     lambda m: EntersTapped("unless_opponent_lands", count=_count(m[1]))),
    (re.compile(rf"As {_SELF} enters, you may reveal an? ({_LAND_TYPE}) or ({_LAND_TYPE}) card from your hand\. "
                rf"If you don't, {_SELF} enters tapped\.", re.I),
     lambda m: EntersTapped("reveal", types=(m[1].capitalize(), m[2].capitalize()))),
    (re.compile(rf"As {_SELF} enters, you may pay {_N} life\. If you don't, it enters tapped\.", re.I),
     lambda m: EntersTapped("shock", life=_count(m[1]))),
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
    (re.compile(rf"{_SELF} enters tapped unless a player has {_N} or less life\.", re.I),
     lambda m: EntersTapped("unless_a_player_life", count=_count(m[1]))),
    (re.compile(rf"If you control {_N} or more other lands, {_SELF} enters tapped\.", re.I),
     lambda m: EntersTapped("if_lands_at_least", count=_count(m[1]))),
    (re.compile(rf"If you were the starting player, {_SELF} enters tapped\.", re.I),
     lambda m: EntersTapped("if_starting_player")),
    (re.compile(rf"{_SELF} enters tapped if you were the starting player\.", re.I),
     lambda m: EntersTapped("if_starting_player")),
    (re.compile(rf"As {_SELF} enters, you may reveal an? ([A-Z][a-z]+) card from your hand\. "
                rf"If you don't, {_SELF} enters tapped\.", re.I),
     lambda m: EntersTapped("reveal", types=(m[1].capitalize(),))),
    (re.compile(rf"{_SELF} enters tapped with {_N} {_COUNTER} on it\.", re.I), lambda m: EntersTapped("always")),
    (re.compile(rf"{_SELF} enters tapped\. As (?:it|{_SELF}) enters, choose a color\.", re.I),
     lambda m: EntersTapped("always")),
]

_CHOOSE_COLOR = re.compile(rf"(?:{_SELF} enters tapped\. )?As (?:it|{_SELF}) enters, choose a color\.", re.I)


def chooses_color(card: Card) -> bool:
    """Room of Refuge and the like: "As it enters, choose a color." (the choice is kept on the permanent)."""
    return any(_CHOOSE_COLOR.fullmatch(line) for line in rules_lines(card))


def is_choose_color_line(line: str) -> bool:
    return _CHOOSE_COLOR.fullmatch(line) is not None


def enters_tapped_rule(card: Card) -> EntersTapped | None:
    for line in rules_lines(card):
        for pattern, build in _ENTERS_TAPPED:
            if m := pattern.fullmatch(line):
                return build(m)
    return None


def is_enters_tapped_line(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern, _ in _ENTERS_TAPPED)


_CYCLING = re.compile(r"(Cycling|Basic landcycling|(?:Plains|Island|Swamp|Mountain|Forest)cycling)"
                      r"(?: ((?:\{\d+\}|\{[WUBRGC]\})+)|\u2014Pay (\d+) life\.?)")
_CYCLING_LAND_TYPES = {"plainscycling": "Plains", "islandcycling": "Island", "swampcycling": "Swamp",
                       "mountaincycling": "Mountain", "forestcycling": "Forest"}


def cycling(card: Card) -> tuple[str, str, tuple, int] | None:
    """A card's cycling: (its name, like "Forestcycling", the mana cost, what the ability does when it resolves,
    the life it costs instead of mana). Plain cycling draws a card; basic landcycling and Forestcycling-style abilities fetch a land to your hand."""
    for line in rules_lines(card):
        if m := _CYCLING.fullmatch(line):
            word = m[1]
            if word == "Cycling":
                effects: tuple = (Draw(1),)
            elif word == "Basic landcycling":
                effects = (SearchForLands(1, (), 0, False, True),)
            else:
                effects = (SearchForLands(1, (_CYCLING_LAND_TYPES[word.lower()],), 0, False, True),)
            return word, m[2] or "", effects, int(m[3] or 0)
    return None


def is_cycling_line(line: str) -> bool:
    return _CYCLING.fullmatch(line) is not None


@dataclass(frozen=True)
class AlternativeCost:
    """A way to cast a spell instead of paying its mana cost (CR 118.9)."""
    text: str  # how it's offered to the caster
    commander: bool = False  # "If you control a commander, ..."
    not_your_turn: bool = False  # "If it's not your turn, ..."
    life: int = 0
    exile_color: str | None = None  # exile a card of this color (a letter) from your hand
    mana_cost: str = ""  # an alternative cost that is mana ("Evoke {2}{U}", "Overload {6}{U}"), paid instead of the mana cost
    evoke: bool = False  # the creature is sacrificed when it enters
    overload: bool = False  # every "target" in the spell becomes "each"
    bestow: bool = False  # cast as an Aura spell with enchant creature


@dataclass(frozen=True)
class AdditionalCost:
    """"As an additional cost to cast this spell, ..." (CR 601.2b)."""
    sacrifice: str | None = None  # the kind of permanent: "creature", "artifact or creature", ...
    discard: bool = False
    life: int = 0
    life_x: bool = False  # "pay X life" (Toxic Deluge): X is chosen as the spell is cast
    sacrifice_x: bool = False  # "sacrifice X creatures" (Immoral Bargain): `sacrifice` is the kind, X of them


_MANA_SYMBOLS = r"(?:\{\d+\}|\{[WUBRGC]\})+"
_KICKER = re.compile(rf"(?:Multik|K)icker ({_MANA_SYMBOLS})(?: and/or ({_MANA_SYMBOLS}))?")
_KICKER_OTHER = re.compile(rf"Kicker\u2014(?:Sacrifice an? (creature|artifact|land|artifact or creature|permanent)"
                           rf"|(Discard a card)|Pay (?!X ){_N} life)\.")
_FREE_WITH_COMMANDER = re.compile(r"If you control a commander, you may cast this spell without paying its mana cost\.")
_PITCH = re.compile(rf"(If it's not your turn, )?(?i:you) may (?:pay {_N} life and )?exile an? ({_COLOR_NAMES}) card "
                    r"from your hand rather than pay this spell's mana cost\.")
_ADDITIONAL = re.compile(rf"As an additional cost to cast this spell, (?:sacrifice an? (creature|artifact|land|artifact or "
                         rf"creature|permanent)|(discard a card)|pay {_N} life|sacrifice (X) (creatures|artifacts|lands|permanents))\.")
_X_LIMIT = re.compile(r"X can't be greater than the number of players in the game\.")  # Open the Way
_ENTWINE = re.compile(r"Entwine ((?:\{[^}]+\})+)")
_ESCALATE = re.compile(r"Escalate ((?:\{[^}]+\})+)")  # "Escalate\u2014Discard a card." (a cost that isn't mana) isn't supported
_FLASHBACK = re.compile(r"Flashback ((?:\{[^}]+\})+)")
_FLASHBACK_LIFE = re.compile(r"Flashback\u2014((?:\{[^}]+\})+), Pay (\d+) life\.")  # Deep Analysis
_FROM_GRAVEYARD_BY_PAYING = re.compile(r"You may cast this card from your graveyard by paying ((?:\{[^}]+\})+) rather than paying "
                                       r"its mana cost\.")  # Raffine's Guidance
_RETRACE = re.compile(r"Retrace")
_BESTOW = re.compile(r"Bestow ((?:\{[^}]+\})+)")
_ENCORE = re.compile(r"Encore ((?:\{[^}]+\})+)")


def bestow_aura(card: Card) -> Card:
    """The card as it is while a bestow spell or an Aura permanent: an Aura with enchant creature, not a creature."""
    return dataclasses.replace(card, type_line="Enchantment " + chr(0x2014) + " Aura", oracle_text=card.oracle_text + chr(10) + "Enchant creature")


def encore_cost(card: Card) -> str | None:
    """Encore {cost}: from the graveyard, for each opponent a token copy attacks that opponent this turn."""
    return next((m[1] for line in rules_lines(card) if (m := _ENCORE.fullmatch(line))), None)
_ESCAPE = re.compile(r"Escape\u2014((?:\{[^}]+\})+), Exile (a|one|two|three|four|five|six) other cards? from your graveyard\.")
_REDUCTION = re.compile(rf"(?:({_COLOR_NAMES}|creature|artifact|enchantment|noncreature|instant and sorcery|Aura) )?spells "
                        r"you cast( that target a creature)? cost \{(\d+)\} less to cast\.", re.I)


def kicker_costs(card: Card) -> tuple[str, ...]:
    """The mana kicker costs: one for "Kicker {1}{U}" or "Multikicker {1}{G}", two for "Kicker {R} and/or {W}",
    none if there's no kicker or it isn't mana."""
    for line in rules_lines(card):
        if m := _KICKER.fullmatch(line):
            return tuple(cost for cost in m.groups() if cost)
    return ()


def kicker_other_cost(card: Card) -> AdditionalCost | None:
    """A kicker cost that isn't mana: "Kicker—Sacrifice a land.", "Kicker—Discard a card.", "Kicker—Pay 3 life." """
    for line in rules_lines(card):
        if m := _KICKER_OTHER.fullmatch(line):
            return AdditionalCost(sacrifice=m[1], discard=bool(m[2]), life=_count(m[3]) if m[3] else 0)
    return None


def entwine_cost(card: Card) -> str | None:
    """The mana cost from "Entwine {2}": pay it to choose all the modes of a modal spell."""
    return next((m[1] for line in rules_lines(card) if (m := _ENTWINE.fullmatch(line))), None)


def escalate_cost(card: Card) -> str | None:
    """The mana cost from "Escalate {1}": pay it for each mode chosen beyond the first."""
    return next((m[1] for line in rules_lines(card) if (m := _ESCALATE.fullmatch(line))), None)


def is_multikicker(card: Card) -> bool:
    """Multikicker: the kicker cost can be paid any number of times (CR 702.33c)."""
    return any(line.startswith("Multikicker ") and _KICKER.fullmatch(line) for line in rules_lines(card))


_DEVOUR = re.compile(r"Devour (\d+)")
_REPLICATE = re.compile(r"Replicate ((?:\{[^}]+\})+)")
_AFFINITY = re.compile(r"Affinity for ([a-z]+?)s?")
_STORM_LIKE = re.compile(r"(Storm|Gravestorm)")


def devour(card: Card) -> int:
    """Devour N: as it enters you may sacrifice creatures; it enters with N +1/+1 counters for each. 0 if it has none."""
    for line in rules_lines(card):
        if m := _DEVOUR.fullmatch(line):
            return int(m[1])
    return 0


def replicate_cost(card: Card) -> str | None:
    for line in rules_lines(card):
        if m := _REPLICATE.fullmatch(line):
            return m[1]
    return None


def affinity_for(card: Card) -> str | None:
    """Affinity for planeswalkers: costs {1} less for each planeswalker you control ("planeswalker")."""
    for line in rules_lines(card):
        if m := _AFFINITY.fullmatch(line):
            return m[1]
    return None


def storm_kind(card: Card) -> str | None:
    """"storm" or "gravestorm" for a spell that copies itself when cast."""
    for line in rules_lines(card):
        if m := _STORM_LIKE.fullmatch(line):
            return m[1].lower()
    return None


def is_cast_keyword_line(line: str) -> bool:
    """Replicate, Storm, Gravestorm, Affinity and Devour lines: rules the game applies itself."""
    return any(p.fullmatch(line) for p in (_DEVOUR, _REPLICATE, _AFFINITY, _STORM_LIKE))


_ECHO = re.compile(r"Echo ((?:\{[^}]+\})+)")


def echo_cost(card: Card) -> str | None:
    """Karmic Guide: the mana to pay at your next upkeep after it comes under your control, or sacrifice it."""
    for line in rules_lines(card):
        if m := _ECHO.fullmatch(line):
            return m[1]
    return None


def is_echo_line(line: str) -> bool:
    return _ECHO.fullmatch(line) is not None


_CUMULATIVE_UPKEEP = re.compile(r"Cumulative upkeep ((?:\{[^}]+\})+)")


def cumulative_upkeep(card: Card) -> str | None:
    """Mystic Remora: the mana to pay for each age counter at the beginning of your upkeep, or None."""
    for line in rules_lines(card):
        if m := _CUMULATIVE_UPKEEP.fullmatch(line):
            return m[1]
    return None


def is_cumulative_upkeep_line(line: str) -> bool:
    return _CUMULATIVE_UPKEEP.fullmatch(line) is not None


_EVOKE = re.compile(r"Evoke ((?:\{[^}]+\})+)")
_OVERLOAD = re.compile(r"Overload ((?:\{[^}]+\})+)")


def overloaded_effects(card: Card) -> list | None:
    """What an overloaded spell does: the same text with every "target" read as "each" (Cyclonic Rift), or None if
    the card has no Overload or that text isn't understood."""
    if not any(_OVERLOAD.fullmatch(line) for line in rules_lines(card)):
        return None
    lines = [line for line in rules_lines(card) if not is_casting_cost_line(line)]
    return _parse(_split_sentences(re.sub(r"\btarget\b", "each", "\n".join(lines))))


def is_overload_line(line: str) -> bool:
    return _OVERLOAD.fullmatch(line) is not None


def alternative_costs(card: Card) -> list[AlternativeCost]:
    costs = []
    for line in rules_lines(card):
        if m := _EVOKE.fullmatch(line):
            costs.append(AlternativeCost(f"Evoke {m[1]}", mana_cost=m[1], evoke=True))
            continue
        if m := _OVERLOAD.fullmatch(line):
            if overloaded_effects(card):
                costs.append(AlternativeCost(f"Overload {m[1]}", mana_cost=m[1], overload=True))
            continue
        if m := _BESTOW.fullmatch(line):
            costs.append(AlternativeCost(f"Bestow {m[1]}", mana_cost=m[1], bestow=True))
            continue
        if _FREE_WITH_COMMANDER.fullmatch(line):
            costs.append(AlternativeCost("Cast without paying its mana cost", commander=True))
        elif m := _PITCH.fullmatch(line):
            life = _count(m[2]) if m[2] else 0
            text = f"Pay {life} life and exile a {m[3]} card" if life else f"Exile a {m[3]} card"
            costs.append(AlternativeCost(text, not_your_turn=bool(m[1]), life=life, exile_color=_COLOR_LETTER[m[3]]))
    return costs


@dataclass(frozen=True)
class GraveyardCast:
    """A way to cast a card from the graveyard: Flashback (then it is exiled) or Escape (exile other cards too)."""
    word: str  # "Flashback" or "Escape"
    cost: str  # the mana cost to pay instead of the card's own
    exile: int = 0  # other cards to exile from the graveyard (Escape)
    exile_after: bool = False  # exile it instead of putting it in the graveyard when it leaves the stack (Flashback)
    discard_land: bool = False  # Retrace: discard a land card in addition to the cost
    life: int = 0  # "Flashback\u2014{1}{U}, Pay 3 life."


def graveyard_casts(card: Card) -> list[GraveyardCast]:
    found = []
    for line in rules_lines(card):
        if m := _FLASHBACK.fullmatch(line):
            found.append(GraveyardCast("Flashback", m[1], exile_after=True))
        elif m := _FLASHBACK_LIFE.fullmatch(line):
            found.append(GraveyardCast("Flashback", m[1], exile_after=True, life=int(m[2])))
        elif m := _FROM_GRAVEYARD_BY_PAYING.fullmatch(line):
            found.append(GraveyardCast("From the graveyard", m[1]))
        elif m := _ESCAPE.fullmatch(line):
            found.append(GraveyardCast("Escape", m[1], exile=_count(m[2])))
        elif _RETRACE.fullmatch(line):
            found.append(GraveyardCast("Retrace", card.mana_cost, discard_land=True))
    return found


def additional_costs(card: Card) -> list[AdditionalCost]:
    costs = []
    for line in rules_lines(card):
        if m := _ADDITIONAL.fullmatch(line):
            life_x = (m[3] or "").upper() == "X"
            costs.append(AdditionalCost(sacrifice=m[1] or (m[5].removesuffix("s") if m[5] else None), discard=bool(m[2]),
                                        life=0 if life_x or not m[3] else _count(m[3]), life_x=life_x, sacrifice_x=bool(m[5])))
    return costs


def x_limited_by_players(card: Card) -> bool:
    """Open the Way: "X can't be greater than the number of players in the game." """
    return any(_X_LIMIT.fullmatch(line) for line in rules_lines(card))


def cost_reductions(card: Card) -> list[tuple[str, int]]:
    """Static "Green spells you cast cost {1} less to cast." abilities (Medallions): (what kind of spell, how much).
    The kind is a color letter, a card type ("creature", "noncreature", "instant and sorcery") or "spell"."""
    found = []
    for line in rules_lines(card):
        if m := _REDUCTION.fullmatch(line):
            kind = (m[1] or "spell").lower()
            found.append(("targets a creature" if m[2] else _COLOR_LETTER.get(kind, kind), int(m[3])))
    return found


_SPELL_KEYWORDS = re.compile(r"(?:Delve|Cascade|Devoid|Demonstrate)(?:, (?:Delve|Cascade|Devoid|Demonstrate))*")  # rules for casting, not effects


def is_casting_cost_line(line: str) -> bool:
    """Kicker, alternative and additional costs: rules for casting the spell rather than what it does."""
    return any(p.fullmatch(line) for p in (_KICKER, _KICKER_OTHER, _FREE_WITH_COMMANDER, _PITCH, _ADDITIONAL, _FLASHBACK, _RETRACE, _ENCORE, _BESTOW, _CANT_COUNTER, _SUSPEND, _ESCAPE, _ENTWINE, _ESCALATE,
                                           _PER_REDUCTION, _X_LIMIT, _EVOKE, _OVERLOAD, _SPELL_KEYWORDS, _REPLICATE, _STORM_LIKE,
                                           _AFFINITY, _STRIVE, _FLASHBACK_LIFE, _FROM_GRAVEYARD_BY_PAYING, _POWER_REDUCTION)) \
        or ((m := _IF_REDUCTION.fullmatch(line)) is not None and _condition(m[2]) is not None)


_X_DISCOUNT = re.compile(r"The first spell you cast with \{X\} in its mana cost each turn costs \{1\} less to cast for each "
                         r"\+1/\+1 counter on (?:CARDNAME|this creature)\.")


def is_x_discount_line(line: str) -> bool:
    return _X_DISCOUNT.fullmatch(line) is not None


def x_spell_discount(card: Card) -> bool:
    """Zimone, Infinite Analyst: its first X spell each turn costs {1} less for each +1/+1 counter on it."""
    return any(_X_DISCOUNT.fullmatch(line) for line in rules_lines(card))


_PER_REDUCTION = re.compile(r"This spell costs \{(\d+)\} less to cast for each "
                            r"(creature on the battlefield|instant and sorcery card in your graveyard)\.")


def self_cost_reduction(card: Card) -> tuple[int, str] | None:
    """Blasphemous Act: "This spell costs {1} less to cast for each creature on the battlefield." (how much each,
    what is counted: "creature" on the battlefield or "instant or sorcery" card in your graveyard)."""
    for line in rules_lines(card):
        if m := _PER_REDUCTION.fullmatch(line):
            return int(m[1]), "creature" if m[2].startswith("creature") else "instant or sorcery"
    return None


_IF_REDUCTION = re.compile(r"This spell costs \{(\d+)\} less to cast if (.+)\.")  # Mortality Spear
_POWER_REDUCTION = re.compile(r"This spell costs \{X\} less to cast, where X is the total power of creatures you control\.")
_GRANTED_AFFINITY = re.compile(r"(Enchantment) spells you cast have affinity for Auras\.")  # Pearl-Ear, Imperial Advisor


def conditional_cost_reduction(card: Card) -> tuple[int, Condition] | None:
    """Mortality Spear: "This spell costs {2} less to cast if you gained life this turn." (how much, and when)"""
    for line in rules_lines(card):
        if (m := _IF_REDUCTION.fullmatch(line)) and (condition := _condition(m[2])):
            return int(m[1]), condition
    return None


def reduced_by_total_power(card: Card) -> bool:
    """Volcanic Salvo: "This spell costs {X} less to cast, where X is the total power of creatures you control." """
    return any(_POWER_REDUCTION.fullmatch(line) for line in rules_lines(card))


def granted_affinity(card: Card) -> str | None:
    """Pearl-Ear: the kind of spell you cast that has affinity for Auras ("enchantment")."""
    return next((m[1].lower() for line in rules_lines(card) if (m := _GRANTED_AFFINITY.fullmatch(line))), None)


def is_cost_reduction_line(line: str) -> bool:
    return any(p.fullmatch(line) for p in (_REDUCTION, _PER_REDUCTION, _POWER_REDUCTION, _GRANTED_AFFINITY)) \
        or (m := _IF_REDUCTION.fullmatch(line)) is not None and _condition(m[2]) is not None


@dataclass(frozen=True)
class IfKicked:
    """"If this spell was kicked, draw a card.": the effect happens only if the kicker cost was paid.
    `kicker` names one of two kicker costs: "If this spell was kicked with its {1}{B} kicker, ..." """
    effect: Any
    kicker: str = ""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None and game.resolving_item.kicked:
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class KickedInstead:
    """"If this spell was kicked, it deals 4 damage instead.": when kicked, the previous effect's `field`
    (its damage, number of tokens or cards) becomes `value`."""
    field: str
    value: int | str


_KICKED_INSTEAD = [
    (re.compile(rf"if this spell was kicked, {_SELF} deals {_N} damage instead\.", re.I), "amount"),
    (re.compile(rf"if this spell was kicked, create {_N} of those tokens instead\.", re.I), "count"),
    (re.compile(rf"if this spell was kicked, draw {_N} cards instead\.", re.I), "count"),
]


def _kicked(m: re.Match) -> IfKicked | None:
    kicker, rest = m[1] or "", m[2]
    effects = _parse([rest[:1].upper() + rest[1:]])
    return IfKicked(effects[0], kicker) if effects else None


def kicked_effects(effects: list | None, kicked: int, kickers: tuple[str, ...] = ()) -> list | None:
    """A spell's effects once it's known whether it was kicked: "If this spell was kicked, ..." effects
    become plain effects, or are dropped. This happens before targets are chosen, so kicked effects can target."""
    if effects is None:
        return None
    result = []
    for effect in effects:
        if isinstance(effect, KickedInstead):
            if kicked:
                result[-1] = replace(result[-1], **{effect.field: effect.value})
        elif isinstance(effect, IfKicked):
            if kicked and (not effect.kicker or effect.kicker in kickers):
                result.append(effect.effect)
        else:
            result.append(effect)
    return result
_LAND_TYPES = rf"({_LAND_TYPE}(?:, {_LAND_TYPE})*(?:,? or {_LAND_TYPE})?)"


_LAND_TYPES_PLURAL = rf"({_LAND_TYPE}(?:, {_LAND_TYPE})*(?:,? or {_LAND_TYPE})?) cards"


def _land_types(text: str) -> tuple[str, ...]:
    return tuple(t.capitalize() for t in re.findall(_LAND_TYPE, text, re.I))


_MANA_VALUE = r"(?: with mana value \d+(?: or less| or greater)?)?"
_SUBTYPE_WORD = r"(?-i:[A-Z][a-z]+)"  # a creature type or other subtype, capitalized: "an Elf card", "a Dragon card"
_SUBTYPE_CARDS = "aura or equipment|aura|equipment|vehicle|saga|" + _SUBTYPE_WORD
_CARD_TYPE = (r"((?:(?:legendary creature|legendary|nonbasic land|noncreature, nonland|nonland permanent|artifact or creature|creature|artifact|enchantment|land|permanent"
              rf"|instant or sorcery|instant|sorcery|{_SUBTYPE_CARDS}) )?card{_MANA_VALUE})")
_SEARCH_TYPE = (r"((?:(?:legendary creature|legendary|nonbasic land|creature|land|artifact|enchantment|planeswalker"
                rf"|instant or sorcery|instant|sorcery|artifact or enchantment|basic land|{_SUBTYPE_CARDS}) )?card{_MANA_VALUE})")
_CARDS_PLURAL = (r"((?:(?:legendary creature|legendary|nonbasic land|creature|artifact|enchantment|land|permanent"
                 rf"|instant or sorcery|instant|sorcery|{_SUBTYPE_CARDS}) )?cards{_MANA_VALUE})")
_CARD_PHRASE = re.compile(r"(?:(.+?) )?card(?: with mana value (\d+)(?: (or less|or greater))?)?")


def _card_kind(phrase: str | None) -> str:
    """"creature card with mana value 3 or less" -> "creature|mv<=3"; "card" -> "card". The kind is what the
    game matches library and graveyard cards against."""
    m = _CARD_PHRASE.fullmatch((phrase or "card").lower())
    kind = m[1] or "card"
    if m[2]:
        kind += "|mv" + {"or less": "<=", "or greater": ">="}.get(m[3], "=") + m[2]
    return kind


def _graveyard_kind(phrase: str | None, whose: str) -> str:
    return f"graveyard:{_card_kind(phrase)}:{whose}"


@dataclass(frozen=True)
class FetchBasicLand:
    untap_if: "Condition | None" = None  # Fabled Passage: "Then if you control four or more lands, untap that land."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fetch_basic_land(controller, untap_if=self.untap_if)


_PERMANENT_KIND = (r"((?:monocolored permanent|creature token|nontoken creature|attacking creature|tapped creature|untapped creature"
                   r"|non(?:white|blue|black|red|green|artifact) creature|noncreature artifact or noncreature enchantment"
                   r"|noncreature, nonland permanent|nonland, nontoken permanent|non-(?-i:[A-Z][a-z]+) creature|artifact, enchantment, or planeswalker|creature|artifact"
                   r"|enchantment|planeswalker|nonland permanent|permanent|nonbasic land|land|artifact or enchantment|artifact or creature"
                   r"|creature or planeswalker|(?-i:[A-Z][a-z]+) creature)(?: an opponent controls| you don't control| you control| you own)?"
                   r"(?: with mana value (?:\d+ or (?:less|greater)|X))?)")
# "up to two target creatures": the plural kinds, and the singular they stand for
_PLURAL_KINDS = {"creatures": "creature", "artifacts": "artifact", "enchantments": "enchantment",
                 "planeswalkers": "planeswalker", "permanents": "permanent", "nonland permanents": "nonland permanent",
                 "creature tokens": "creature token", "lands": "land", "artifacts or enchantments": "artifact or enchantment"}
_PLURAL_KIND = (r"(creature tokens|nonland permanents|artifacts or enchantments|creatures|artifacts|enchantments|planeswalkers"
                r"|permanents|lands)( an opponent controls| you don't control| you control)?")
_UP_TO = r"up to (two|three|four)"


def _up_to(cls: type, m: re.Match, **fixed: Any) -> list:
    """"... up to two target creatures ..." is two effects with one optional, distinct target each."""
    kind = _PLURAL_KINDS[m[2].lower()] + (m[3] or "")
    return [cls(kind, optional_target=True, distinct=n > 0, **fixed) for n in range(_count(m[1]))]
_DAMAGE_KIND = (r"(any target|target creature|target player|target opponent|target creature or planeswalker"
                r"|target player or planeswalker)")

_RETURN_UP_TO_POWER = re.compile(r"return target nonland permanent card with mana value X or less from your graveyard to the "
                                 r"battlefield, where X is (?:this creature's|CARDNAME's|its) power\.", re.I)

_TEMPLATES: list[tuple[re.Pattern, Callable[[re.Match], Any]]] = [
    *[(pattern, lambda m, field=field: KickedInstead(field, _count(m[1]))) for pattern, field in _KICKED_INSTEAD],
    (re.compile(rf"if this spell was kicked(?: with its ({_MANA_SYMBOLS}) kicker)?, (.+)", re.I), _kicked),
    (re.compile(rf"draw {_N} cards?\.", re.I), lambda m: Draw(_count(m[1]))),
    (re.compile(r"draw an additional card\.", re.I), lambda m: Draw(1)),
    (re.compile(rf"you gain {_N} life\.", re.I), lambda m: GainLife(_count(m[1]))),
    (re.compile(rf"each opponent loses {_N} life\.", re.I), lambda m: OpponentsLoseLife(_count(m[1]))),
    (re.compile(rf"{_SELF} deals {_N} damage to {_DAMAGE_KIND}\.", re.I),
     lambda m: Damage(_count(m[1]), "any" if m[2].lower() == "any target" else m[2].lower().removeprefix("target "))),
    (re.compile(rf"{_SELF} deals {_N} damage to each of one or two targets\.", re.I),  # Prismari Charm
     lambda m: [Damage(_count(m[1]), "any"), Damage(_count(m[1]), "any", optional_target=True, distinct=True)]),
    (re.compile(rf"{_SELF} deals {_N} damage to each of up to two target creatures and/or planeswalkers\.", re.I),  # Volcanic Salvo
     lambda m: [Damage(_count(m[1]), "creature or planeswalker", optional_target=True),
                Damage(_count(m[1]), "creature or planeswalker", optional_target=True, distinct=True)]),
    (re.compile(rf"{_SELF} deals (\d+) damage divided as you choose among any number of targets\.", re.I),
     lambda m: [Damage(1, "any", optional_target=n > 0) for n in range(int(m[1]))]),  # a point at a time
    (re.compile(rf"tap (two|three) target {_PLURAL_KIND}\.", re.I),
     lambda m: [Tap(_PLURAL_KINDS[m[2].lower()] + (m[3] or ""), distinct=n > 0) for n in range(_count(m[1]))]),
    (re.compile(rf"destroy (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Destroy(m[2].lower(), bool(m[1]))),
    (re.compile(rf"destroy each {_PERMANENT_KIND}\.", re.I), lambda m: DestroyAll(m[1].lower())),
    (re.compile(r"destroy each artifact, creature, and enchantment with mana value X or less\.", re.I),
     lambda m: DestroyAll("artifact or creature or enchantment", MassFilter(stat="mana_value", at_most="X"))),
    (re.compile(rf"exile each {_PERMANENT_KIND}\.", re.I), lambda m: ExileAll(m[1].lower())),
    (re.compile(rf"return each {_PERMANENT_KIND} to its owner's hand\.", re.I), lambda m: ReturnAllToHand(m[1].lower())),
    (re.compile(rf"destroy {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Destroy, m)),
    (re.compile(rf"destroy up to one target {_PERMANENT_KIND}\.", re.I),
     lambda m: Destroy(m[1].lower(), optional_target=True)),
    (re.compile(r"counter target ((?:noncreature|creature|instant or sorcery|artifact or enchantment|artifact|enchantment) )?spell"
                rf"( unless its controller pays ((?:\{{[^}}]+\}})+))?\.", re.I),
     lambda m: Counter(f"{m[1].lower()}spell" if m[1] else "spell", unless=m[3] or "")),
    (re.compile(rf"its controller may draw up to {_N} cards at the beginning of the next turn's upkeep\.", re.I),
     lambda m: DelayedDraw(_count(m[1]), True)),
    (re.compile(r"you draw a card at the beginning of the next turn's upkeep\.", re.I), lambda m: DelayedDraw(1, False)),
    (re.compile(r"exile enchanted creature\.", re.I), lambda m: ExileEnchanted()),
    (re.compile(r"that token gains haste until end of turn\.", re.I), lambda m: _TokenGainsHaste()),
    (re.compile(r"create a token that's a copy of it\.", re.I), lambda m: _CopyOfIt()),
    (re.compile(r"mill a card, then exile a card from your graveyard at random\. you may play the exiled card this turn\.", re.I),
     lambda m: MillThenExileRandomPlay()),
    (re.compile(rf"create a token that's a copy of {_SELF}\.", re.I), lambda m: CopySelfToken()),
    (re.compile(r"exile that card from your graveyard\.(?: if you do, you may (?:play|cast) that card this turn\.)?", re.I),
     lambda m: ExileDiscarded(play="you may" in m[0].lower())),
    (re.compile(r"tap up to one target creature and goad it\.", re.I), lambda m: TapAndGoad()),
    (re.compile(r"attach (?:this Aura|CARDNAME) to it\.", re.I), lambda m: AttachThisToSubject()),
    (re.compile(r"if that enchantment is an Aura, you may attach it to the token\.", re.I), lambda m: _AttachItToToken()),
    (re.compile(r"the token created this way gains haste\.", re.I), lambda m: _PopulatedTokenRider(haste=True)),
    (re.compile(r"sacrifice it at the beginning of the next end step\.", re.I), lambda m: _PopulatedTokenRider(sacrifice=True)),
    (re.compile(r'it has "(.+)"', re.I), lambda m: _ItHas(m[1]) if _is_known_ability(m[1]) else None),
    (re.compile(r"when you next cast an instant or sorcery spell this turn, copy that spell\. You may choose new targets for the "
                r"copy\.", re.I), lambda m: CopyNextSpell()),
    (re.compile(rf"(?:then )?put an? {_CARD_TYPE} from among them onto the battlefield\.", re.I),
     lambda m: _PutFromAmongThem(_card_kind(m[1]))),
    (re.compile(rf"(?:those creatures|they(?! gain haste until end of turn\.)) gain {_KEYWORDS} until end of turn\.", re.I), lambda m: _TheyGain(_keyword_list(m[1]))),
    (re.compile(r"you may cast spells this turn as though they had flash\.", re.I), lambda m: GrantFlash()),
    (re.compile(rf"if (.+), draw {_N} cards instead\.", re.I),
     lambda m: _InsteadDraw(c, _count(m[2])) if (c := _condition(m[1])) else None),
    (re.compile(r"then if (.+), untap that land\.", re.I), lambda m: _UntapThatLand(c) if (c := _condition(m[1])) else None),
    (re.compile(r"then if (.+?), ((?!untap that land).+)\.", re.I), _then_if),
    (re.compile(rf"exile {_N} cards from your graveyard\.", re.I), lambda m: ExileOwnGraveyard(_count(m[1]))),
    (re.compile(r"if you do, (.+)\.", re.I), _if_you_do),
    (re.compile(r'if an? (creature) card is exiled this way, (create .+?)(\."?)', re.I), _if_exiled),
    (re.compile(rf"return (?:CARDNAME|this card) from your graveyard to the battlefield( tapped)?\.", re.I),
     lambda m: ReturnThisFromGraveyard(bool(m[1]))),
    (re.compile(rf"return (?:CARDNAME|this card) from your graveyard to your hand\.", re.I),
     lambda m: ReturnThisFromGraveyard(to="hand")),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Exile(m[2].lower(), bool(m[1]))),
    (re.compile(rf"exile {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Exile, m)),
    (re.compile(rf"destroy X target {_PLURAL_KIND}\.", re.I), lambda m: DestroyX(_PLURAL_KINDS[m[1].lower()] + (m[2] or ""))),
    (re.compile(rf"exile X target {_PLURAL_KIND}\.", re.I), lambda m: ExileX(_PLURAL_KINDS[m[1].lower()] + (m[2] or ""))),
    (re.compile(r"destroy up to X target artifacts and/or enchantments\.", re.I),
     lambda m: DestroyUpToX("artifact or enchantment")),
    (re.compile(r"choose any number of target creatures you control\.", re.I), lambda m: _ChooseAnyNumber("creature you control")),
    (re.compile(r"for each of them, create a token that's a copy of that creature, except it has haste\.", re.I),
     lambda m: _CopyEachWithHaste()),
    (re.compile(r"exile those tokens at the beginning of the next end step\.", re.I), lambda m: _ExileThoseTokens()),
    (re.compile(rf"exile up to one target {_PERMANENT_KIND}\.", re.I), lambda m: Exile(m[1].lower(), optional_target=True)),
    (re.compile(r"exile target ((?:noncreature|creature|instant or sorcery|artifact|enchantment) )?spell\.", re.I),
     lambda m: Counter(f"{m[1].lower()}spell" if m[1] else "spell", exile=True)),
    (re.compile(r"if that spell is countered this way, exile it instead of putting it into its owner's graveyard\.", re.I),
     lambda m: ExileInstead()),
    (re.compile(r"at the beginning of your next main phase, add an amount of \{C\} equal to that spell's mana value\.", re.I),
     lambda m: _DelayedMana()),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND}, then return (?:it|that card) to the battlefield under "
                r"(your|its owner's) control\.", re.I),
     lambda m: Flicker(m[2].lower(), under_owner=m[3].lower() != "your", another=bool(m[1]))),
    (re.compile(r"return (?:it|that card) to the battlefield under (your|its owner's) control at the beginning of the "
                r"next end step\.", re.I), lambda m: ReturnLater("battlefield", m[1].lower() != "your")),
    (re.compile(r"return (?:it|that card) to its owner's hand at the beginning of the next end step\.", re.I),
     lambda m: ReturnLater("hand", True)),
    (re.compile(rf"exile the top (?:card|{_N} cards) of your library\.", re.I), lambda m: ExileTop(_count(m[1] or "one"))),
    (re.compile(r"you may play (?:it|that card|those cards|them) this turn\.", re.I), lambda m: PlayExiled("this turn")),
    (re.compile(r"until (?:the )?end of turn, you may play (?:it|that card|those cards|them)\.", re.I),
     lambda m: PlayExiled("this turn")),
    (re.compile(r"until (?:the )?end of your next turn, you may play (?:it|that card|those cards|them)\.", re.I),
     lambda m: PlayExiled("next turn")),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND} until {_SELF} leaves the battlefield\.", re.I),
     lambda m: ExileUntilLeaves(m[2].lower(), bool(m[1]))),
    (re.compile(rf"target (player|opponent) draws {_N} cards?\.", re.I), lambda m: TargetDraw(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) draws {_N} cards? and loses {_N} life\.", re.I),
     lambda m: TargetDrawLose(_count(m[2]), _count(m[3]), m[1].lower())),
    (re.compile(rf"you and target opponent each draw {_N} cards?\.", re.I), lambda m: YouAndTargetDraw(_count(m[1]))),
    (re.compile(rf"each player loses {_N} life\.", re.I), lambda m: EachPlayerLosesLife(_count(m[1]))),
    (re.compile(r"you may discard a card\.", re.I), lambda m: _MayDiscard()),
    (re.compile(rf"you may sacrifice an? {_SACRIFICE_KIND}\.", re.I), lambda m: _MaySacrifice(m[1].lower())),
    (re.compile(rf"you may remove an? {_COUNTER} from (?:it|{_SELF})\.", re.I), lambda m: _MayRemoveCounter(_counter_name(m[1]))),
    (re.compile(rf"if you do, draw {_N} cards?(?:, then mill {_N} cards?)?\.", re.I),
     lambda m: _IfYouDoDraw(_count(m[1]), _count(m[2]) if m[2] else 0)),
    (re.compile(r"you gain life equal to the life lost this way\.", re.I), lambda m: _GainLifeLost()),
    (re.compile(r"each player may discard their hand and draw (seven) cards\.", re.I),
     lambda m: EachMayWheel(_count(m[1]))),
    (re.compile(r"you may tap or untap target creature\.", re.I), lambda m: TapOrUntap()),
    (re.compile(rf"target (player|opponent) gains {_N} life\.", re.I), lambda m: TargetGainLife(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) loses {_N} life\.", re.I), lambda m: TargetLoseLife(_count(m[2]), m[1].lower())),
    (re.compile(rf"return (another |up to one )?target {_PERMANENT_KIND} to its owner's hand\.", re.I),
     # "Return another target ..." can be neither the source (a trigger's) nor the spell's earlier target (Rushing River).
     lambda m: ReturnToHand(m[2].lower(), (m[1] or "").lower() == "another ", (m[1] or "").lower() == "up to one ",
                            distinct=(m[1] or "").lower() == "another ")),
    (re.compile(rf"return {_UP_TO} target {_PLURAL_KIND} to their owners' hands\.", re.I), lambda m: _up_to(ReturnToHand, m)),
    (re.compile(rf"return (five|six|seven) target {_PLURAL_KIND} to their owners' hands\.", re.I),  # Aether Gale: exactly that many
     lambda m: [ReturnToHand(_PLURAL_KINDS[m[2].lower()] + (m[3] or ""), distinct=n > 0) for n in range(_count(m[1]))]),
    (re.compile(rf"return all {_CARDS_PLURAL} from your graveyard to (the battlefield|your hand)\.", re.I),
     lambda m: ReturnAllFromGraveyard(_card_kind(m[1].removesuffix("s")), "battlefield" if m[2].lower() == "the battlefield" else "hand")),
    (re.compile(rf"return all {_MASS_FILTERED} to their owners' hands\.", re.I), lambda m: _mass_effect(ReturnAllToHand, m)),
    (re.compile(rf"return {_UP_TO} target {_CARDS_PLURAL} from your graveyard to your hand\.", re.I),
     lambda m: [ReturnFromGraveyard(_graveyard_kind(m[2].replace("cards", "card", 1), "yours"), "hand",
                                    optional_target=True, distinct=n > 0) for n in range(_count(m[1]))]),
    (re.compile(rf"return target {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "hand")),
    (re.compile(rf"(?:return|put) target {_CARD_TYPE} from (your|a) graveyard (?:to|onto) the battlefield( tapped)?"
                r"(?: under your control)?\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours" if m[2].lower() == "your" else "any"), "battlefield",
                                   bool(m[3]))),
    (re.compile(rf"put target {_CARD_TYPE} from your graveyard on (the bottom|top) of your library\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "library_bottom" if m[2].lower() == "the bottom" else "library_top")),
    (re.compile(rf"exile target {_CARD_TYPE} from a graveyard\.", re.I),
     lambda m: ExileFromGraveyard(_graveyard_kind(m[1], "any"))),
    (re.compile(rf"exile target {_CARD_TYPE} from your graveyard\.", re.I),
     lambda m: ExileFromGraveyard(_graveyard_kind(m[1], "yours"))),
    (re.compile(rf"search your library for an? {_SEARCH_TYPE}, (?:reveal it, )?(?:put (?:it|that card) into your hand, "
                r"then shuffle|then shuffle and put (?:it|that card|the card) on top(?: of your library)?)\.", re.I),
     lambda m: SearchLibrary(_card_kind(m[1]), "hand" if "into your hand" in m[0] else "top", "reveal it" in m[0].lower())),
    (re.compile(r"search your library for a land card, put it into your graveyard, then shuffle\.", re.I),
     lambda m: SearchLibrary("land", "graveyard", False)),
    (re.compile(r"search your library for a land card, put it onto the battlefield( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(1, ("*",), 1, bool(m[1]), False)),
    (re.compile(r"search your library for a nonbasic land card, put it onto the battlefield( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(1, ("nonbasic",), 1, bool(m[1]), False)),
    (re.compile(rf"search your library for up to (two|three|four) {_LAND_TYPES_PLURAL}, put them onto the battlefield"
                r"( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(_count(m[1]), _land_types(m[2]), _count(m[1]), bool(m[3]), False)),
    (re.compile(rf"search your library for up to (two|three|four) basic {_LAND_TYPES_PLURAL}, reveal (?:them|those cards), put them "
                r"into your hand, then shuffle\.", re.I),  # Archaeomancer's Map
     lambda m: SearchForLands(_count(m[1]), _land_types(m[2]), 0, False, True, basic_only=True)),
    (re.compile(r"you lose life equal to (?:its|that card's) mana value\.", re.I), lambda m: LoseLifeEqualToManaValue()),
    (re.compile(rf"you lose {_N} life\.", re.I), lambda m: LoseLife(_count(m[1]))),
    (re.compile(r"search your library for up to two basic land cards, reveal those cards, put one onto the battlefield "
                r"tapped and the other into your hand, then shuffle\.", re.I),
     lambda m: SearchForLands(2, (), 1, True, True)),
    (re.compile(r"search your library for up to (two|three|four) basic land cards, (?:reveal (?:them|those cards), )?"
                r"put (?:them|those cards) onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: SearchForLands(_count(m[1]), (), _count(m[1]), True, False)),
    (re.compile(rf"search your library for an? {_LAND_TYPES} card, put (?:it|that card) onto the battlefield( tapped)?, "
                r"then shuffle\.", re.I),
     lambda m: SearchForLands(1, _land_types(m[1]), 1, bool(m[2]), False)),
    (re.compile(r"the owner of target permanent shuffles it into their library, then reveals the top card of their library\.",
                re.I), lambda m: ChaosWarp()),
    (re.compile(r"if it's a permanent card, they put it onto the battlefield\.", re.I), lambda m: _ChaosPut()),
    (re.compile(rf"draw a card, then put {_SELF} on top of its owner's library\.", re.I),
     lambda m: [Draw(1), PutSourceOnLibraryTop()]),
    (re.compile(rf"scry {_N}\.", re.I), lambda m: Scry(_count(m[1]))),
    (re.compile(rf"scry {_N}, then draw (?:a card|{_N} cards)\.", re.I),
     lambda m: [Scry(_count(m[1])), Draw(_count(m[2] or "a"))]),
    (re.compile(rf"scry {_N}, then reveal the top card of your library\.", re.I),
     lambda m: RevealTopStep("reveal", _count(m[1]))),
    (re.compile(r"if it's a land card, put it onto the battlefield( tapped)?\.", re.I),
     lambda m: RevealTopStep("land", tapped=bool(m[1]))),
    (re.compile(r"otherwise, draw a card\.", re.I), lambda m: RevealTopStep("otherwise")),
    (re.compile(rf"surveil {_N}\.", re.I), lambda m: Surveil(_count(m[1]))),
    (re.compile(rf"look at the top {_N} cards of your library, then put them back in any order\.", re.I),
     lambda m: PutBackTop(_count(m[1]))),
    (re.compile(r"you may shuffle\.", re.I), lambda m: _MayShuffle()),
    (re.compile(rf"draw {_N} cards, then put {_N} cards from your hand on top of your library in any order\.", re.I),
     lambda m: DrawThenPutBack(_count(m[1]), _count(m[2]))),
    (re.compile(rf"look at the top (?:{_N} cards?|card) of your library\.", re.I),
     lambda m: LookAtTop(_count(m[1] or "one"))),
    (re.compile(r"put one of them into your hand and the rest on the bottom of your library in any order\.", re.I),
     lambda m: TakeFromTop(None)),
    (re.compile(rf"you may reveal an? {_SEARCH_TYPE} from among them and put it into your hand\.", re.I),
     lambda m: TakeFromTop(_card_kind(m[1]))),
    (re.compile(r"put the rest on the bottom of your library in (?:a random|any) order\.", re.I),
     lambda m: RestOnBottom()),
    (re.compile(r"return a land you control to its owner's hand\.", re.I), lambda m: ReturnOwnLand()),
    (re.compile(r"add ((?:\{[WUBRGC]\})+)\.", re.I),
     lambda m: AddMana(tuple(frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[1].upper())))),
    (_RETURN_UP_TO_POWER, lambda m: ReturnFromGraveyard("graveyard:nonland permanent|mv<=power:yours", "battlefield")),
    (re.compile(r"exile all (?:cards from all )?graveyards\.", re.I), lambda m: ExileAllGraveyards()),
    (re.compile(r"each opponent loses all counters\.", re.I), lambda m: OpponentsLoseCounters()),
    (re.compile(r"add \{([WUBRGC])\} for each card in target opponent's hand\.", re.I), lambda m: AddManaPerCardInHand(m[1].upper())),
    (re.compile(r"until end of turn, you don't lose this mana as steps and phases end\.", re.I), lambda m: KeepManaThisTurn()),
    (re.compile(r"exile (?:CARDNAME|this spell) with (a|two|three|four|five|\d+) time counters? on it\.", re.I),
     lambda m: ExileWithTimeCounters(_count(m[1]))),
    (re.compile(rf"target player puts an? {_COUNTER} on each creature they control\.", re.I),
     lambda m: TargetPutsCountersOnEach(_counter_name(m[1]))),
    (re.compile(rf"for each player, put an? {_COUNTER} on up to one target creature that player controls\.", re.I),
     lambda m: PutCounterPerPlayer(_counter_name(m[1]))),
    (re.compile(r"each player puts a vow counter on a creature they control and sacrifices the rest\. Each of those creatures "
                r"can't attack you or planeswalkers you control for as long as it has a vow counter on it\.", re.I),
     lambda m: VowCounters()),
    (re.compile(rf"put an? {_COUNTER} on each of up to X target creatures( you control)?\.", re.I),
     lambda m: PutCountersOnEachUpToX(_counter_name(m[1]), "creature you control" if m[2] else "creature")),
    (re.compile(r"Auras, Equipment, and modified creatures you control gain hexproof until end of turn\.", re.I),
     lambda m: ModifiedGainHexproof()),
    (re.compile(r"move all counters from target (nonland permanent you control) onto another target (nonland permanent you control)\.",
                re.I), lambda m: [MoveCountersFrom(m[1].lower()), MoveCountersOnto(None, None, m[2].lower())]),
    (re.compile(r"remove all counters from target (nonland permanent you control)\. Draw a card for each counter removed this "
                r"way\.", re.I), lambda m: RemoveAllCountersDraw(m[1].lower())),
    (re.compile(r"you may put a \+1/\+1 counter on a creature\. Then choose odd or even\. Return each creature with power of "
                r"the chosen quality to its owner's hand\.", re.I), lambda m: ZimonesHypothesis()),
    (re.compile(r"shuffle your library, then reveal cards from the top of it until you reveal a nonland card\. Exile that "
                r"card and put the rest on the bottom of your library in a random order\. You may cast the exiled card "
                r"without paying its mana cost\.", re.I), lambda m: ShuffleRevealCast()),
    (re.compile(r"copy target (instant or sorcery spell|instant spell|sorcery spell)( you control)?\.", re.I),
     lambda m: CopySpell(m[1].lower() + (m[2] or "").lower())),
    (re.compile(r"copy (?:it|that spell)\.", re.I), lambda m: CopyTriggeringSpell()),
    (re.compile(r"put a number of \+1/\+1 counters on it equal to the damage dealt\.", re.I),
     lambda m: PutCountersOnSource("X", "+1/+1")),  # X is the damage the trigger saw
    (re.compile(r"you may choose new targets for the copy\.", re.I), lambda m: NewTargets()),
    (re.compile(rf"gain control of target {_PERMANENT_KIND}( until end of turn)?\.", re.I),
     lambda m: GainControl(m[1].lower(), until_end_of_turn=bool(m[2]))),
    (re.compile(r"untap that creature\.", re.I), lambda m: UntapThat()),
    (re.compile(rf"untap target {_PERMANENT_KIND} and gain control of it until end of turn\.", re.I),
     lambda m: [GainControl(m[1].lower(), until_end_of_turn=True), UntapThat()]),
    (re.compile(r"that creature gains haste until end of turn\.", re.I),
     lambda m: PumpSource(Modifier(keywords=frozenset({"haste"})))),
    (re.compile(r"tap (?:it|that creature)\.", re.I), lambda m: TapThat()),
    (re.compile(r"proliferate\.", re.I), lambda m: Proliferate()),
    (re.compile(r"proliferate (X) times\.", re.I), lambda m: Proliferate("X")),
    (re.compile(rf"target {_FIGHTER} fights (another )?target {_FIGHTER}\.", re.I),
     lambda m: [FightFirst(m[1].lower()), Fight(m[3].lower(), another=bool(m[2]))]),
    (re.compile(rf"target {_FIGHTER} deals damage equal to its power to target {_FIGHTER}\.", re.I),
     lambda m: [FightFirst(m[1].lower()), Fight(m[2].lower(), one_sided=True)]),
    (re.compile(rf"then it fights up to one target {_FIGHTER}\.", re.I),  # Primal Might: after a pump of the first creature
     lambda m: Fight(m[1].lower(), optional_target=True)),
    (re.compile(rf"look at the top {_N} cards of your library\. Put {_N} of them into your hand and the rest on the bottom of your "
                r"library in any order\.", re.I), lambda m: LookTakeRestBottom(_count(m[1]), _count(m[2]))),
    (re.compile(r"target player draws X cards plus an additional card for each time they've cast a commander from the command zone "
                r"this game\.", re.I), lambda m: TargetDrawXPlusCasts()),
    (re.compile(r"add \{([WUBRGC])\} or \{([WUBRGC])\} for each permanent destroyed this way\.", re.I),
     lambda m: _ManaForEachDestroyed(frozenset({m[1].upper(), m[2].upper()}))),
    (re.compile(r"add \{([WUBRGC])\} for each tapped land your opponents control\.", re.I),
     lambda m: AddManaPerTappedLand(m[1].upper())),
    (re.compile(r"creatures you control have base power and toughness X/X until end of turn\.", re.I), lambda m: SetBaseEachX()),
    (re.compile(r"each creature deals damage to itself equal to its power\.", re.I), lambda m: EachDamagesItself()),
    (re.compile(rf"target player draws {_N} cards, then discards {_N} cards\.", re.I),
     lambda m: TargetDrawDiscard(_count(m[1]), _count(m[2]))),
    (re.compile(rf"target player mills {_N} cards, then you return an? {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: TargetMillThenReturn(_count(m[1]), _card_kind(m[2]))),
    (re.compile(r"you gain half X life and draw half X cards\. round down each time\.", re.I),
     lambda m: [GainLife("hX"), Draw("hX")]),
    (re.compile(r"populate\.", re.I), lambda m: Populate()),
    (re.compile(r"(?i:put) an? ((?:[A-Z][a-z]+(?:, (?:or )?| or ))*[A-Z][a-z]+) (?i:creature card from your hand onto the "
                r"battlefield tapped and attacking that opponent\.)"),
     lambda m: PutAttackingFromHand(tuple(re.findall(r"[A-Z][a-z]+", m[1])))),
    (re.compile(rf"{_SELF} becomes prepared\.", re.I), lambda m: BecomePrepared()),
    (re.compile(r"each creature you control becomes prepared\.", re.I), lambda m: PrepareEach()),
    (re.compile(r"target (creature(?: that attacked this turn)?) becomes (prepared|unprepared)\.", re.I),
     lambda m: TargetPrepared(m[1].lower(), m[2].lower() == "prepared")),
    (re.compile(rf"create a token that's a copy of target {_PERMANENT_KIND}\.", re.I), lambda m: CopyToken(m[1].lower())),
    (re.compile(rf"create a token that's a copy of another target {_PERMANENT_KIND}\.", re.I),
     lambda m: CopyToken(m[1].lower(), another=True)),
    (re.compile(rf"create a token that's a copy of {_SELF}, tapped and attacking\.", re.I), lambda m: CopyTokenAttacking()),
    (re.compile(r"put one of them into your hand, put one of them on the bottom of your library, and exile one of them\.",
                re.I), lambda m: _SplitTop()),
    (re.compile(r"you may play the exiled card this turn\.", re.I), lambda m: _PlayTheExiledCard()),
    (re.compile(r"its controller manifests the top card of their library\.", re.I), lambda m: TargetControllerManifests()),
    (re.compile(rf"shuffle your library\. as many times as you choose, you may exile the top card of your library\. if the "
                rf"total mana value of the cards exiled this way is {_N} or less, you may cast any number of spells from among "
                r"those cards without paying their mana costs\.", re.I), lambda m: DanceWithCalamity(_count(m[1]))),
    (re.compile(r"target (player|opponent) loses half their life, rounded (up|down)\.", re.I),
     lambda m: TargetLoseHalfLife(m[1].lower(), m[2].lower() == "up")),
    (re.compile(rf"double the number of {_COUNTER} on target {_PERMANENT_KIND}\.", re.I),
     lambda m: DoubleCountersOnTarget(_counter_name(m[1]), m[2].lower())),
    (re.compile(rf"return {_SELF} to the battlefield( tapped)?( under its owner's control)?\.", re.I),
     lambda m: ReturnSelfToBattlefield(tapped=bool(m[1]))),
    (re.compile(rf"you may put an? {_CARD_TYPE} from your hand onto the battlefield( tapped)?\.", re.I),
     lambda m: PutFromHand(_card_kind(m[1]), bool(m[2]))),
    (re.compile(rf"return an? {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: ReturnChosen(_card_kind(m[1]), "hand")),
    (re.compile(r"take an extra turn after this one\.", re.I), lambda m: ExtraTurn()),
    (re.compile(r"you become the monarch\.", re.I), lambda m: BecomeMonarch()),
    (re.compile(rf"return (?:{_SELF}|this card) to its owner's hand\.", re.I), lambda m: ReturnSelfToHand()),
    (re.compile(r"tap all creatures your opponents control\.", re.I), lambda m: TapAll()),
    (re.compile(r"investigate\.", re.I), lambda m: CreateTokens(1, CLUE)),
    (re.compile(rf"{_VOTE_PREFIX}starting with you, each player votes for (\w+) or (\w+)\.", re.I),
     lambda m: VoteStart((m[1].lower(), m[2].lower()))),
    (re.compile(rf"{_VOTE_PREFIX}starting with you, each player votes for a nonland permanent you don't control\.", re.I),
     lambda m: VoteStart(None)),
    (re.compile(r"exile each permanent with the most votes or tied for most votes\.", re.I),
     lambda m: ExileMostVoted()),
    (re.compile(r"for each (\w+) vote, (.+)\.", re.I), lambda m: _vote_outcome("each", m[1], m[2], False)),
    (re.compile(r"(.+?) for each (\w+) vote and (.+?) for each (\w+) vote\.", re.I),
     lambda m: _two_vote_outcomes(m[1], m[2], m[3], m[4])),
    (re.compile(r"if (\w+) gets more votes( or the vote is tied)?, (.+)\.", re.I),
     lambda m: _vote_outcome("more", m[1], m[3], bool(m[2]))),
    (re.compile(r"you take the initiative\.", re.I), lambda m: TakeInitiative()),
    (re.compile(r"target player takes an extra turn after this one\.", re.I), lambda m: TargetExtraTurn()),
    (re.compile(r"after this (?:main )?phase, there is an additional combat phase( followed by an additional main phase)?\.",
                re.I), lambda m: ExtraCombat(bool(m[1]))),
    (re.compile(r"untap all creatures that attacked this turn\.", re.I), lambda m: UntapCreatures("attacked")),
    (re.compile(r"untap all creatures you control\.", re.I), lambda m: UntapCreatures("yours")),
    (re.compile(r"untap all (artifacts|lands|permanents|enchantments) you control\.", re.I),
     lambda m: UntapAll(_PLURAL_KINDS[m[1].lower()])),
    (re.compile(rf"untap (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Untap(m[2].lower(), bool(m[1]))),
    (re.compile(rf"untap up to one target {_PERMANENT_KIND}\.", re.I), lambda m: Untap(m[1].lower(), optional_target=True)),
    (re.compile(rf"untap {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Untap, m)),
    (re.compile(rf"untap (?:it|{_SELF})\.", re.I), lambda m: UntapSource()),
    (re.compile(r"goad target (creature)\.", re.I), lambda m: Goad(m[1].lower())),
    (re.compile(r"goad (?:all creatures you don't control|each creature your opponents control)\.", re.I),
     lambda m: GoadAll()),
    (re.compile(rf"mill {_N} cards?\.", re.I), lambda m: Mill(_count(m[1]), "you")),
    (re.compile(rf"discard {_N} cards?( at random)?\.", re.I), lambda m: Discard(_count(m[1]), "you", bool(m[2]))),
    (re.compile(r"discard your hand\.", re.I), lambda m: Discard(None, "you")),
    (re.compile(rf"each (opponent|player) discards {_N} cards?( at random)?\.", re.I),
     lambda m: Discard(_count(m[2]), "each " + m[1].lower(), bool(m[3]))),
    (re.compile(r"each (opponent|player) discards their hand\.", re.I), lambda m: Discard(None, "each " + m[1].lower())),
    (re.compile(rf"target (player|opponent) discards {_N} cards?( at random)?\.", re.I),
     lambda m: TargetDiscard(_count(m[2]), m[1].lower(), bool(m[3]))),
    (re.compile(rf"each player draws {_N} cards?\.", re.I), lambda m: EachDraw(_count(m[1]))),
    (re.compile(r"each player discards their hand, then draws cards equal to the greatest number of cards a player "
                r"discarded this way\.", re.I), lambda m: DiscardHandsDrawGreatest()),
    (re.compile(rf"each player discards their hand, then draws {_N} cards?\.", re.I),
     lambda m: [Discard(None, "each player"), EachDraw(_count(m[1]))]),
    (re.compile(rf"draw {_N} cards?, then discard {_N} cards?\.", re.I),
     lambda m: [Draw(_count(m[1])), Discard(_count(m[2]), "you")]),
    (re.compile(rf"discard {_N} cards?, then draw {_N} cards?\.", re.I),
     lambda m: [Discard(_count(m[1]), "you"), Draw(_count(m[2]))]),
    (re.compile(r"target (player|opponent) reveals their hand\.", re.I), lambda m: RevealHand(m[1].lower())),
    (re.compile(r"you choose an? ((?:non[a-z]+(?:, non[a-z]+)*) )?card(?: with mana value (\d+) or less)? from it"
                r"(?: with mana value (\d+) or less)?\.", re.I),
     lambda m: ChooseFromHand(tuple(w.strip(",") for w in m[1].lower().replace("non", "").split()) if m[1] else (),
                              int(m[2] or m[3]) if m[2] or m[3] else None)),
    (re.compile(r"that player discards that card\.", re.I), lambda m: DiscardChosen()),
    (re.compile(rf"each (opponent|player) mills {_N} cards?\.", re.I),
     lambda m: Mill(_count(m[2]), "each " + m[1].lower())),
    (re.compile(rf"target (player|opponent) mills {_N} cards?\.", re.I),
     lambda m: TargetMill(_count(m[2]), m[1].lower())),
    (re.compile(rf"destroy all {_MASS_FILTERED}\.", re.I), lambda m: _mass_effect(DestroyAll, m)),
    (re.compile(r"(?:they|it) can't be regenerated\.", re.I), lambda m: CannotRegenerate()),
    (re.compile(rf"regenerate target {_PERMANENT_KIND}\.", re.I), lambda m: Regenerate(m[1].lower())),
    (re.compile(rf"regenerate {_SELF}\.", re.I), lambda m: RegenerateSource()),
    (re.compile(r"regenerate each creature you control\.", re.I), lambda m: RegenerateEach()),
    (re.compile(rf"exile all {_MASS_FILTERED}\.", re.I), lambda m: _mass_effect(ExileAll, m)),
    (re.compile(rf"{_SELF} deals {_N} damage to each (creature you don't control|creature your opponents control|creature and planeswalker your opponents control"
                rf"|creature|opponent|player)(?: {_RESTRICTION})?(?: and each (opponent|player))?\.", re.I), _damage_each),
    (re.compile(rf"each (opponent|player) sacrifices (a|an|one|two|three) {_SACRIFICE_KIND}"
                r"( with the greatest power among creatures they control)?\.", re.I),
     lambda m: EachSacrifices(m[1].lower(), m[3].lower(), _count(m[2]), bool(m[4])) if m[4] is None or m[3].lower() == "creature" else None),
    (re.compile(rf"each (opponent|player) sacrifices (two|three|four|five) {_SACRIFICE_PLURAL}\.", re.I),
     lambda m: EachSacrifices(m[1].lower(), _PLURAL_SACRIFICE[m[3].lower()], _count(m[2]))),
    (re.compile(rf"each (opponent|player) sacrifices all {_SACRIFICE_PLURAL} they control\.", re.I),
     lambda m: EachSacrifices(m[1].lower(), _PLURAL_SACRIFICE[m[2].lower()], None)),
    (re.compile(rf"sacrifice all {_SACRIFICE_PLURAL} you control\.", re.I),
     lambda m: SacrificeAll(_PLURAL_SACRIFICE[m[1].lower()])),
    (re.compile(r"for each (creature|permanent) (?:destroyed|exiled) this way, its controller creates (.+)\.(\"?)", re.I),
     lambda m: _gift(_GiftMatch(m[2], m[3]))),
    (re.compile(r"(?:then )?create (.+) for each nontoken creature you controlled that was destroyed this way\.(\"?)", re.I),
     lambda m: _gift(_GiftMatch(m[1], m[2]), who="you", nontoken=True)),
    (re.compile(r"each player creates (.+) and puts a number of \+1/\+1 counters on it equal to the total power of the "
                r"creatures they controlled that were exiled this way\.(\"?)", re.I),
     lambda m: _gift(_GiftMatch(m[1], m[2]), who="each player", power_counters=True)),
    (re.compile(r"sacrifice a creature\.", re.I), lambda m: SacrificeCreature()),
    (re.compile(rf"(?:you )?sacrifice (a|an|one|two|three) {_SACRIFICE_KIND}\.", re.I),
     lambda m: EachSacrifices("you", m[2].lower(), _count(m[1]))),
    (re.compile(rf"(?:you )?sacrifice (two|three|four|five) {_SACRIFICE_PLURAL}\.", re.I),
     lambda m: EachSacrifices("you", _PLURAL_SACRIFICE[m[2].lower()], _count(m[1]))),
    (re.compile(rf"sacrifice {_SELF} unless you return an untapped ({_LAND_TYPE}) you control to its owner's hand\.", re.I),
     lambda m: SacrificeUnlessReturnLand(m[1].capitalize())),
    (re.compile(r"Let X be (.+)\."), lambda m: DefineX(a) if (a := _amount(m[1])) else None),
    (re.compile(rf"target (player|opponent) sacrifices an? {_SACRIFICE_KIND}\.", re.I),
     lambda m: TargetSacrifices(m[1].lower(), m[2].lower())),
    (re.compile(r"exile target player's graveyard\.", re.I), lambda m: ExileGraveyard()),
    (re.compile(rf"put {_N} {_COUNTER} on target {_PERMANENT_KIND}\.", re.I),
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"put {_N} {_COUNTER} on another target {_PERMANENT_KIND}\.", re.I),
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower(), another=True)),
    (re.compile(rf"put {_N} {_COUNTER} on each (creature|(?-i:[A-Z][a-z]+)) you control\.", re.I),
     lambda m: PutCountersOnEach(_count(m[1]), _counter_name(m[2]), "" if m[3].lower() == "creature" else m[3])),
    (re.compile(rf"put a {_COUNTER} on each (?:(white|blue|black|red|green) )?creature that entered this turn\.", re.I),
     lambda m: PutCountersOnEntered(_counter_name(m[1]), _COLOR_WORDS[m[2].lower()] if m[2] else "")),
    (re.compile(rf"put {_N} {_COUNTER} on {_SELF}\.", re.I),
     lambda m: PutCountersOnSource(_count(m[1]), _counter_name(m[2]))),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} gains protection from the color of your choice until end of turn\."),
     lambda m: GrantProtection(m[1].lower())),
    (re.compile(rf"(?i:{_SELF}) gains protection from the color of your choice until end of turn\."),
     lambda m: GrantProtection(uses_source=True)),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} {_CHANGE}"), lambda m: Pump(_modifier(m, 2), m[1].lower())),
    (re.compile(rf"creatures named {_SELF} can't be blocked this turn\.", re.I),
     lambda m: PumpNamed(Modifier(keywords=frozenset({CANT_BE_BLOCKED})))),
    (re.compile(r"shuffle any number of target cards from your graveyard into your library\.", re.I),
     lambda m: ShuffleIntoLibrary()),
    (re.compile(rf"target {_PERMANENT_KIND} can't be blocked this turn\.", re.I),
     lambda m: Pump(Modifier(keywords=frozenset({CANT_BE_BLOCKED})), m[1].lower())),
    (re.compile(rf"(?i:each other creature that's attacking one of your opponents) {_CHANGE}"),
     lambda m: PumpOtherAttackers(_modifier(m, 1))),
    (re.compile(rf"(?i:one or two target creatures each) {_CHANGE}"),
     lambda m: [Pump(_modifier(m, 1), "creature"), Pump(_modifier(m, 1), "creature", optional_target=True, distinct=True)]),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} gets? {_PT_X}(?: and gains? {_KEYWORDS})? until end of turn\."),
     lambda m: _pump_x(m[2], m[3], m[4], m[5], m[1].lower(), m[6])),
    (re.compile(rf"(?i:target) (creature(?: an opponent controls| you control)?) (?i:becomes) an? (\d+)/(\d+)"
                rf"(?: (?:white|blue|black|red|green|colorless))?(?: [A-Z][\w'-]*)*(?: creature)?(?: with {_KEYWORDS})?"
                r" until end of turn\."),
     lambda m: Pump(Modifier(0, 0, _keyword_list(m[4]) if m[4] else frozenset(), (int(m[2]), int(m[3]))), m[1].lower())),
    (re.compile(rf"target (creature(?: an opponent controls| you control)?) has base power and toughness (\d+)/(\d+)"
                r" until end of turn\.", re.I),
     lambda m: Pump(Modifier(0, 0, frozenset(), (int(m[2]), int(m[3]))), m[1].lower())),
    (re.compile(rf"(?i:(all creatures|creatures you control|creatures your opponents control)) get {_PT_X} until end of turn\."),
     lambda m: _pump_each_x(m)),
    (re.compile(rf"(?i:(creatures you control)) gain {_KEYWORDS} and get {_PT_X} until end of turn\."),
     lambda m: dataclasses.replace(_pump_each_x_from(m[1], m[3], m[4], m[5], m[6]), keywords=_keyword_list(m[2]))),
    (re.compile(r"(?:Until end of turn, )?creatures your opponents control lose hexproof and shroud and can't have hexproof or shroud\."),
     lambda m: PumpEach(Modifier(keywords=frozenset({LOSES_HEXPROOF})), opponents=True)),
    (re.compile(rf"(?i:creatures your opponents control) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1), opponents=True)),
    (re.compile(rf"(?i:all creatures) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1), everyone=True)),
    (re.compile(rf"move (?:{_N}|all|any number of) {_COUNTER} from target (creature) onto another target (creature)"
                r"( with the same controller)?\.", re.I),
     lambda m: [MoveCountersFrom(m[3].lower()),
                MoveCountersOnto("any" if m[0].lower().startswith("move any number") else _count(m[1]) if m[1] else None,
                                 _counter_name(m[2]), m[4].lower(), same_controller=bool(m[5]))]),
    (re.compile(rf"(?:Until end of turn, )(?:CARDNAME|this land) becomes an? {_ANIMATED}\.\"?"), lambda m: _animate(m, None)),
    (re.compile(rf"(?i:CARDNAME|this land) becomes an? {_ANIMATED} (?i:until end of turn)\.\"?"), lambda m: _animate(m, None)),
    (re.compile(rf"(?i:target) (land you control) becomes an? {_ANIMATED} (?i:until end of turn)\.\"?"),
     lambda m: _animate(m, m[1].lower(), 1)),
    (re.compile(r"it's still an? (land|artifact)\.", re.I), lambda m: StillALand()),
    (re.compile(rf"remove {_N} {_COUNTER} from target {_PERMANENT_KIND}\.", re.I),
     lambda m: RemoveCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"remove all {_COUNTER} from target {_PERMANENT_KIND}\.", re.I),
     lambda m: RemoveCounters(None, _counter_name(m[1]), m[2].lower())),
    (re.compile(rf"remove all counters from target {_PERMANENT_KIND}\.", re.I),
     lambda m: RemoveCounters(None, None, m[1].lower())),
    (re.compile(rf"double the number of {_COUNTER} on (?:{_SELF})\.", re.I),
     lambda m: DoubleCountersOnSource(_counter_name(m[1]))),
    (re.compile(rf"double the number of {_COUNTER} on each creature you control\.", re.I),
     lambda m: DoubleCounters(_counter_name(m[1]))),
    (re.compile(r'(each opponent|each player) creates (.+)\.("?)', re.I), lambda m: _create_for_others(m)),
    (re.compile(r'target (player|opponent) creates (.+)\.("?)', re.I), lambda m: _create_for_others(m)),
    (re.compile(rf"(?i:{_SELF}) {_CHANGE}"), lambda m: PumpSource(_modifier(m, 1))),
    (re.compile(rf"(?i:{_SELF}) gets {_PT} until end of turn and can't be blocked this turn\."),  # Nimrodel Watcher
     lambda m: PumpSource(Modifier(_signed(m[1]), _signed(m[2]), frozenset({CANT_BE_BLOCKED})))),
    (re.compile(rf"(?i:{_SELF}) gets? {_PT_X} until end of turn\."),
     lambda m: (lambda x: PumpSourceX(x.power, x.toughness))(_pump_x(m[1], m[2], m[3], m[4], "creature"))),
    (re.compile(rf"(?i:creatures you control) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1))),
    (re.compile(rf"((?-i:[A-Z][a-z]+))s you control {_CHANGE}"), lambda m: PumpEach(_modifier(m, 2), subtype=m[1])),
    (re.compile(r'for each opponent, create (.+) that attack that opponent this turn if able\.("?)', re.I), _attacking_tokens),
    (re.compile(r"they gain haste until end of turn\.", re.I), lambda m: _TheyGainHaste()),
    (re.compile(r"exile them at the beginning of the next end step\.", re.I), lambda m: _ExileThemLater()),
    (re.compile(r"prevent all combat damage that would be dealt to you this turn\.", re.I),
     lambda m: PreventCombatDamageToYou()),
    (re.compile(r'for each 1 damage prevented this way, create (.+)\.("?)', re.I), _token_per_prevented),
    (re.compile(r"(?:then )?you may choose a token you control\.", re.I), lambda m: _ChooseToken()),
    (re.compile(r"if you do, each other token you control becomes a copy of that token until end of turn\.", re.I),
     lambda m: _OthersBecomeCopies()),
    (re.compile(r'(?i:create) (.+)\.("?)'), lambda m: _create(m, follows=False)),
    (re.compile(r'(?i:(?:its|that creature\'s) controller creates) (.+)\.("?)'), lambda m: _create(m, follows=True)),
    (re.compile(r"its controller gains life equal to its power\.", re.I), lambda m: TargetControllerGainsLifeEqualToPower()),
    (re.compile(r"its controller may search their library for a basic land card, put (?:it|that card) onto the "
                r"battlefield tapped, then shuffle\.", re.I), lambda m: TargetControllerMayFetchBasicLand()),
    (re.compile(r"search your library for a basic land card, put (?:it|that card) onto the battlefield tapped, "
                r"then shuffle\.", re.I),
     lambda m: FetchBasicLand()),
]


_YOUR_ACTION = rf"(?:draw (?:a card|{_N} cards)|gain {_N} life|lose {_N} life)"


def _you_do(phrase: str) -> str:
    """A sentence for something you do: "draw a card" -> "Draw a card.", "lose 1 life" -> "You lose 1 life." """
    return phrase[:1].upper() + phrase[1:] + "." if phrase.lower().startswith("draw") else f"You {phrase}."


_TIMES_X = [
    (r"\b(draws?) (?:a card|cards)\b", r"\1 X cards"),
    (r"\b(gains?|loses?) (?:1 )?life\b", r"\1 X life"),
    (r"\b(creates?) (?:a|an|one) (.+?) token\b", r"\1 X \2 tokens"),
    (r"\b(creates?) a number of (.+?) tokens\b", r"\1 X \2 tokens"),
    (r"\b(put) (?:a|one) (\+1/\+1) counter\b", r"\1 X \2 counters"),
    (r"\b(gets?) ([+\-\u2212])(\d+)/([+\-\u2212])(\d+)\b",  # "+2/+2" for each: +2X/+2X
     lambda m: f"{m[1]} {m[2]}{_times(m[3])}/{m[4]}{_times(m[5])}" if (m[3], m[5]) != ("0", "0") else m[0]),
]


def _times(number: str) -> str:
    """A number as a multiple of X: 0 -> "0", 1 -> "X", 2 -> "2X"."""
    return "0" if number == "0" else "X" if number == "1" else f"{number}X"


def _times_x(text: str) -> tuple[str, int]:
    """"draw a card" -> "draw X cards", "create a 1/1 ... token" -> "create X 1/1 ... tokens", ...;
    and how many replacements were made (0: the amount has nothing to apply to)."""
    total = 0
    parts = re.split(r'("[^"]*")', text)  # what a token says in quotes ("you gain 1 life") is not multiplied
    for pattern, replacement in _TIMES_X:
        for i in range(0, len(parts), 2):
            parts[i], n = re.subn(pattern, replacement, parts[i], flags=re.I)
            total += n
    return "".join(parts), total


def _clauses(sentence: str) -> list[str]:
    """Rewrite wording the templates don't cover into sentences they do: "X and you gain 1 life." is two
    sentences, as is "You draw two cards and lose 2 life."; "of their choice" and a leading "You draw" /
    "You create" add nothing."""
    sentence = sentence.replace(" of their choice.", ".")
    if m := re.fullmatch(r"(.*)\bhalf X (.+?), rounded (up|down)\.", sentence):  # The Goose Mother: "create half X Food tokens, rounded up."
        return _clauses(f"{m[1]}half X {m[3]} {m[2]}.")
    if _RETURN_UP_TO_POWER.fullmatch(sentence):  # one effect: X is looked at when the target is chosen
        return [sentence]
    if m := re.fullmatch(r"Create a number of (.+?) tokens? equal to (.+)\.", sentence, re.I):  # Gyome's Food
        return [f"Let X be {m[2]}.", f"Create X {m[1]} tokens."] if _amount(m[2]) else [sentence]
    if m := re.fullmatch(r"(.+), where X is (.+)\.", sentence):
        return [f"Let X be {m[2]}."] + _clauses(m[1] + ".") if _amount(m[2]) else [sentence]
    if m := re.fullmatch(r"(.+) (?:equal to|for each) (.+)\.", sentence):
        body, count = _times_x(m[1])
        return [f"Let X be {m[2]}."] + _clauses(body + ".") if count and _amount(m[2]) else [sentence]
    if m := re.fullmatch(r"For each opponent, you (create .+?)(\.\"?)", sentence):  # Eccentric Pestfinder's spell
        return _clauses(f"Create {m[1][len('create '):]}{m[2]} for each opponent.")
    if m := re.fullmatch(r"(Create .+ tokens?), then (put .+ counters? on it\.)", sentence):
        return [m[1] + ".", m[2].capitalize()]
    if m := re.fullmatch(r"(Create .+ tokens?), then populate\.", sentence):
        return [m[1] + ".", "Populate."]
    sentence = re.sub(r"^You (draw|create) ", lambda m: m[1].capitalize() + " ", sentence)
    if m := re.fullmatch(rf"(Draw {_N} cards?) and (create .+)\.", sentence):  # Big Score, Seize the Spoils
        return [m[1] + ".", m[3][:1].upper() + m[3][1:] + "."]
    if m := re.fullmatch(rf"(.+) and you ({_YOUR_ACTION})\.", sentence, re.I):
        return _clauses(m[1] + ".") + [_you_do(m[2])]
    if m := re.fullmatch(rf"(?:You )?(gain {_N} life) and (put .+ counters? on .+)\.", sentence):  # Dina, Essence Brewer
        return [_you_do(m[1]), m[3][:1].upper() + m[3][1:] + "."]
    if m := re.fullmatch(rf"(?:you )?(?P<first>{_YOUR_ACTION}) and (?P<second>{_YOUR_ACTION})\.", sentence, re.I):
        return [_you_do(m["first"]), _you_do(m["second"])]
    if m := re.fullmatch(r"(.+?), then (.+)\.", sentence):  # "Mill three cards, then return a creature card ..."
        first, second = m[1] + ".", m[2][:1].upper() + m[2][1:] + "."
        if _template(first) is not None and _template(second) is not None:
            return [first, second]
    return [sentence]


def _template(sentence: str) -> Any:
    """The effect of one sentence a template understands as written, or None."""
    for pattern, build in _TEMPLATES:
        match = pattern.fullmatch(sentence)
        effect = build(match) if match else None
        if effect is not None:
            return effect
    return None


def _merge_mana_drain(effects: list) -> list | None:
    """Mana Drain's second sentence belongs to the Counter before it, and Chaos Warp's to its ChaosWarp; alone they
    aren't understood."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, _ChaosPut):
            if not (merged and isinstance(merged[-1], ChaosWarp)):
                return None
        elif isinstance(effect, _DelayedMana):
            if not (merged and isinstance(merged[-1], Counter)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], delayed_mana=True)
        else:
            merged.append(effect)
    return merged


def _merge_exile(effects: list) -> list | None:
    """Counter + "exile it instead" is one Counter(exile); Exile + "return it at the beginning of the next end step" is
    one Flicker; ExileTop + "you may play it" is one ExileTop(play). A leftover second half isn't understood."""
    merged: list = []
    for effect in effects:
        before = merged[-1] if merged else None
        if isinstance(effect, ExileInstead):
            if not isinstance(before, Counter):
                return None
            merged[-1] = dataclasses.replace(before, exile=True)
        elif isinstance(effect, ReturnLater):
            if not isinstance(before, Exile):
                return None
            merged[-1] = Flicker(before.target, "end_step", effect.to, effect.under_owner, before.another)
        elif isinstance(effect, PlayExiled):
            if not isinstance(before, ExileTop) or before.play:
                return None
            merged[-1] = dataclasses.replace(before, play=effect.until)
        else:
            merged.append(effect)
    return merged


def _merge_hand_discard(effects: list) -> list | None:
    """"Target opponent reveals their hand. You choose a nonland card from it. That player discards that card." becomes
    one TargetChooseDiscard; any one of the three sentences alone isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, RevealHand):
            if not (i + 2 < len(effects) and isinstance(effects[i + 1], ChooseFromHand)
                    and isinstance(effects[i + 2], DiscardChosen)):
                return None
            choose = effects[i + 1]
            merged.append(TargetChooseDiscard(effect.target, choose.excluded, choose.max_mv))
            i += 3
            continue
        if isinstance(effect, (ChooseFromHand, DiscardChosen)):
            return None
        merged.append(effect)
        i += 1
    return merged


def _merge_put_back(effects: list) -> list | None:
    """"... put them back in any order. You may shuffle." is one effect; "You may shuffle." alone isn't understood."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, _MayShuffle):
            if not (merged and isinstance(merged[-1], PutBackTop)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], shuffle=True)
        else:
            merged.append(effect)
    return merged


def _merge_loot(effects: list) -> list | None:
    """"You may discard a card. If you do, draw a card." is one effect; either sentence alone isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        if isinstance(effects[i], _MayDiscard):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _IfYouDoDraw)):
                return None
            merged.append(MayDiscardThenDraw(effects[i + 1].draw, effects[i + 1].mill))
            i += 2
            continue
        if isinstance(effects[i], _MayRemoveCounter):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _IfYouDoDraw)):
                return None
            merged.append(MayRemoveCounterThenDraw(effects[i].counter, effects[i + 1].draw))
            i += 2
            continue
        if isinstance(effects[i], _MaySacrifice):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _IfYouDoDraw)):
                return None
            merged.append(MaySacrificeThenDraw(effects[i].kind, effects[i + 1].draw))
            i += 2
            continue
        if isinstance(effects[i], _IfYouDoDraw):
            return None
        merged.append(effects[i])
        i += 1
    return merged


def _merge_drain(effects: list) -> list | None:
    """"Each opponent loses X life. You gain life equal to the life lost this way." is one effect."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, _GainLifeLost):
            if not (merged and isinstance(merged[-1], OpponentsLoseLife)):
                return None
            merged[-1] = Drain(merged[-1].amount)
        else:
            merged.append(effect)
    return merged


def _vote_outcome(kind: str, option: str, text: str, tie: bool) -> VoteOutcome | None:
    """What a vote does, read from the sentence's own clause; only for effects that need no target."""
    effects = _parse(_split_sentences(text[:1].upper() + text[1:] + "."))
    if not effects or any(target_kind(e) or uses_source(e) or uses_subject(e) or uses_player(e) or follows_target(e)
                          for e in effects):
        return None
    return VoteOutcome(kind, option.lower(), tuple(effects), tie)


def _two_vote_outcomes(first: str, first_option: str, second: str, second_option: str) -> list | None:
    """"Each opponent sacrifices a creature for each death vote and discards a card for each taxes vote." The second
    part has no subject of its own: it shares the first's ("each opponent")."""
    subject = re.match(r"(each opponent|each player|you) ", first, re.I)
    if subject and not re.match(r"(each opponent|each player|you) ", second, re.I):
        second = f"{subject[1]} {second}"
    outcomes = [_vote_outcome("each", first_option, first, False), _vote_outcome("each", second_option, second, False)]
    return None if None in outcomes else outcomes


def _merge_votes(effects: list) -> list | None:
    """"Starting with you, each player votes for X or Y. For each X vote, ..." becomes one Vote, and the permanent vote
    one VoteToExile; a vote with no outcome, or outcomes about other words, isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, VoteStart) and effect.options is None:
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], ExileMostVoted)):
                return None
            merged.append(VoteToExile())
            i += 2
            continue
        if isinstance(effect, VoteStart):
            outcomes = []
            i += 1
            while i < len(effects) and isinstance(effects[i], VoteOutcome):
                outcomes.append(effects[i])
                i += 1
            if not outcomes or any(o.option not in effect.options or o.kind != outcomes[0].kind for o in outcomes):
                return None
            merged.append(Vote(effect.options, tuple(outcomes)))
            continue
        if isinstance(effect, (VoteOutcome, ExileMostVoted)):
            return None
        merged.append(effect)
        i += 1
    return merged


def _parse(sentences: list[str]) -> list | None:
    effects = []
    for sentence in sentences:
        # A sentence a template already reads is taken as written; only the others are rewritten (_clauses).
        found = [effect] if (effect := _template(sentence)) is not None else [_template(c) for c in _clauses(sentence)]
        if None in found:
            return None
        for effect in found:  # one sentence can make several effects (a fight has two targets)
            effects += effect if isinstance(effect, list) else [effect]
    for i, effect in enumerate(effects):
        if isinstance(effect, KickedInstead) and not (i and hasattr(effects[i - 1], effect.field)):
            return None  # "instead" has to change the effect just before it
    merged = _merge_no_regen(effects)
    for merge in (_merge_three_way, _merge_copy, _merge_control, _merge_impulse, _merge_votes, _merge_hand_discard, _merge_animate, _merge_mana_drain, _merge_exile, _merge_put_back, _merge_loot, _merge_conditional, _merge_drain, _merge_wipe_gift, _merge_reveal_top, _merge_token_counters, _merge_attacking_tokens, _merge_prevention, _merge_token_copies, _merge_target_copies):  # each returns None for a line it rejects
        merged = merge(merged)
        if merged is None:
            return None
    return merged


def _merge_impulse(effects: list) -> list | None:
    """"Look at the top five cards of your library. You may reveal a creature card from among them and put it into your
    hand. Put the rest on the bottom ..." becomes one Impulse; a look or take that isn't completed isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, LookAtTop) and i + 1 < len(effects) and isinstance(effects[i + 1], TakeFromTop):
            take = effects[i + 1]
            i += 2
            if take.card_type is not None:  # the optional reveal needs the rest-on-the-bottom sentence
                if not (i < len(effects) and isinstance(effects[i], RestOnBottom)):
                    return None
                i += 1
            merged.append(Impulse(effect.count, take.card_type))
            continue
        if isinstance(effect, (LookAtTop, TakeFromTop, RestOnBottom)):
            return None
        merged.append(effect)
        i += 1
    return merged


def _merge_copy(effects: list) -> list | None:
    """"Copy target instant or sorcery spell. You may choose new targets for the copy." is one effect. The second
    sentence on its own has no copy to refer to, so the line isn't understood."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, NewTargets):
            if not merged or not isinstance(merged[-1], (CopySpell, CopyTriggeringSpell)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], new_targets=True)
        else:
            merged.append(effect)
    return merged


def _merge_control(effects: list) -> list | None:
    """Threaten: "Gain control of target creature until end of turn. Untap that creature. It gains haste until end
    of turn." is one effect. A lone "Untap that creature." has nothing to refer to, so the line isn't understood."""
    merged: list = []
    for effect in effects:
        after_control = bool(merged) and isinstance(merged[-1], GainControl)
        if isinstance(effect, UntapThat):
            if not after_control:
                return None
            merged[-1] = dataclasses.replace(merged[-1], untap=True)
        elif (isinstance(effect, PumpSource) and effect.modifier.keywords == frozenset({"haste"})
              and effect.modifier.power == effect.modifier.toughness == 0 and after_control and merged[-1].untap):
            merged[-1] = dataclasses.replace(merged[-1], haste=True)
        else:
            merged.append(effect)
    return merged


def _merge_no_regen(effects: list) -> list:
    """"Destroy all creatures. They can't be regenerated." becomes one destroy effect that skips regeneration."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, CannotRegenerate) and merged and isinstance(merged[-1], (Destroy, DestroyAll)):
            merged[-1] = dataclasses.replace(merged[-1], no_regen=True)
        else:
            merged.append(effect)
    return merged


def spell_effects(card: Card) -> list | None:
    """Effects of an instant or sorcery, in order; None if any sentence isn't understood. A modal spell
    ("Choose one — ...") gives a single Modal effect."""
    lines = [line for line in rules_lines(card) if not is_casting_cost_line(line) and not is_hand_ability_line(line)]
    if lines and (m := _MODAL_HEADER.fullmatch(lines[0])):
        return _parse_modal(m[1].lower(), lines[1:])
    if lines and _MODAL_COMMANDER.fullmatch(lines[0]):
        modal = _parse_modal("one", lines[1:])
        return [dataclasses.replace(modal[0], commander_both=True)] if modal else None
    return _parse(_split_sentences("\n".join(lines)))


def is_hand_ability_line(line: str) -> bool:
    """Magma Opus's "{U/R}{U/R}, Discard this card: ...": an ability of the card, not a sentence of the spell."""
    m = _ACTIVATED.fullmatch(line)
    return m is not None and bool((_cost_fields(m[1]) or {}).get("discard_self"))


def line_effects(line: str) -> list | None:
    """Effects of one line of spell text (from rules_lines); None if not understood."""
    return _parse(_split_sentences(line))


@dataclass(frozen=True)
class TriggeredAbility:
    event: str  # one of TRIGGER_EVENTS
    effects: tuple
    optional: bool  # "you may ...": the controller chooses when it resolves
    text: str
    watch: "Watch | None" = None  # set when it watches other objects ("Whenever another creature enters")
    once_per_turn: bool = False  # "This ability triggers only once each turn."
    condition: "Condition | None" = None  # "At the beginning of your upkeep, if ..., ..." (CR 603.4)


@dataclass(frozen=True)
class Condition:
    """An intervening "if" clause, checked when the ability triggers and again when it resolves."""
    kind: str  # "graveyard_left", "gained_life", "opponent_more_lands", "cast_this_turn", "control_at_least",
    #            "control_none", "kicked", "your_turn", "monarch", "hand_at_least", "hand_none", "no_counter",
    #            "gained_life_at_least", "creatures_died", "control_color_at_least", "not_prepared", "citys_blessing", "graveyard_at_least", "any_hand_at_most", "opponent_more_cards"
    count: int = 0
    what: str = ""  # a spell kind ("instant or sorcery spell") or a type ("Plains", "Snake", "creature")


def _singular(word: str) -> str:
    return word if word.endswith("ss") or word.lower() == "plains" else word.removesuffix("s")


_CONDITIONS = [
    (re.compile(r"a card left your graveyard this turn"), lambda m: Condition("graveyard_left")),
    (re.compile(r"you gained life this turn"), lambda m: Condition("gained_life")),
    (re.compile(rf"you gained {_N} or more life this turn"), lambda m: Condition("gained_life_at_least", _count(m[1]))),
    (re.compile(rf"{_N} or more creatures died this turn"), lambda m: Condition("creatures_died", _count(m[1]))),
    (re.compile(r"an opponent controls more lands than you"), lambda m: Condition("opponent_more_lands")),
    (re.compile(r"you've cast an? (instant or sorcery spell|creature spell|noncreature spell|spell) this turn"),
     lambda m: Condition("cast_this_turn", what=m[1])),
    (re.compile(rf"you control {_N} or more (white|blue|black|red|green) permanents"),
     lambda m: Condition("control_color_at_least", _count(m[1]), m[2])),
    (re.compile(rf"you control {_N} or more ([A-Za-z]+)"),
     lambda m: Condition("control_at_least", _count(m[1]), _singular(m[2]))),
    (re.compile(r"you control no creatures with ([a-z]+)"), lambda m: Condition("control_none_keyword", what=m[1])),
    (re.compile(r"you control no ([A-Za-z]+)"), lambda m: Condition("control_none", what=_singular(m[1]))),
    (re.compile(r"you control an? ([A-Za-z]+)"), lambda m: Condition("control_at_least", 1, _singular(m[1]))),
    (re.compile(r"it's your turn"), lambda m: Condition("your_turn")),
    (re.compile(rf"(?:{_SELF}) has no {_COUNTER} on it"), lambda m: Condition("source_no_counters", what=_counter_name(m[1]))),
    (re.compile(rf"(?:it|{_SELF}) has {_N} or more {_COUNTER} on it"),
     lambda m: Condition("source_counters_at_least", _count(m[1]), _counter_name(m[2]))),
    (re.compile(r"you're the monarch"), lambda m: Condition("monarch")),
    (re.compile(rf"you have {_N} or more cards in hand"), lambda m: Condition("hand_at_least", _count(m[1]))),
    (re.compile(r"you have no cards in hand"), lambda m: Condition("hand_none")),
    (re.compile(rf"(?:{_SELF}|he|she) was kicked(?: with its ({_MANA_SYMBOLS}) kicker)?"),
     lambda m: Condition("kicked", what=m[1] or "")),
    (re.compile(r"you have the city's blessing"), lambda m: Condition("citys_blessing")),
    (re.compile(rf"{_SELF} isn't prepared"), lambda m: Condition("not_prepared")),
    (re.compile(rf"{_SELF} is tapped"), lambda m: Condition("source_tapped")),
    (re.compile(r"you control no other ([A-Za-z]+)"), lambda m: Condition("control_no_other", what=_singular(m[1]))),
    (re.compile(r"a modified creature died under your control this turn"), lambda m: Condition("modified_died")),
    (re.compile(rf"{_N} or more of those creatures are attacking you and/or planeswalkers you control"),
     lambda m: Condition("attackers_at_least", _count(m[1]))),
    (re.compile(r"you were the monarch as the turn began"), lambda m: Condition("monarch_at_turn_start")),
    # Eminence: the ability only works from those two zones, which is where the game looks for it.
    (re.compile(rf"{_SELF} is in the command zone or on the battlefield"), lambda m: Condition("eminence")),
    (re.compile(rf"there are {_N} or more ([a-z]+(?: and/or [a-z]+)?) cards in your graveyard"),
     lambda m: Condition("graveyard_at_least", _count(m[1]), m[2].replace(" and/or ", " or "))),
    (re.compile(rf"a player has {_N} or fewer cards in hand"), lambda m: Condition("any_hand_at_most", _count(m[1]))),
    (re.compile(r"an opponent has more cards in hand than you"), lambda m: Condition("opponent_more_cards")),
    (re.compile(rf"an opponent has {_N} or less life"), lambda m: Condition("opponent_life_at_most", _count(m[1]))),
]


def _condition(text: str) -> Condition | None:
    for pattern, build in _CONDITIONS:
        if m := pattern.fullmatch(text):
            return build(m)
    return None


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
    from_zone: str = ""  # "graveyard" ("from your graveyard", "from their graveyard") or "not_hand" ("from anywhere other than your hand")
    qualifier: str = ""  # "with power 4 or greater" ("power>=4"), "with flying" ("flying"), "with a +1/+1 counter on it" ("counter:+1/+1")
    expend: int = 0  # "Whenever you expend 4": the total mana spent on spells this turn that it waits for
    batch: bool = False  # "Whenever one or more creatures die": once for everything that happens at the same time


_TRIGGERS = {
    "enters": re.compile(rf"When(?:ever)? {_SELF} enters(?: the battlefield)?, (.+)", re.I),
    "targeted": re.compile(rf"When(?:ever)? {_SELF} becomes the target of an? (?:spell|spell or ability), (.+)", re.I),
    "cast_self": re.compile(r"When you cast this spell, (.+)", re.I),  # goes on the stack above the spell (Game._cast)
    "dies": re.compile(rf"When(?:ever)? {_SELF} dies, (.+)", re.I),
    "attacks": re.compile(rf"Whenever {_SELF} attacks, (.+)", re.I),
    "attacks_player": re.compile(rf"Whenever {_SELF} attacks an opponent, (.+)", re.I),
    "blocks": re.compile(rf"Whenever {_SELF} blocks, (.+)", re.I),
    "ally_attacks": re.compile(r"Whenever a creature you control attacks, (.+)", re.I),
    "attacked": re.compile(r"Whenever a creature attacks you, (.+)", re.I),
    "attacked_or_walker": re.compile(r"Whenever a creature attacks you or a planeswalker you control, (.+)", re.I),
    "enters_untapped": re.compile(rf"When {_SELF} enters untapped, (.+)", re.I),
    "tokens_created": re.compile(r"Whenever you create one or more creature tokens, (.+)", re.I),
    "tokens_enter": re.compile(r"Whenever one or more tokens you control enter, (.+)", re.I),
    "draw": re.compile(r"Whenever you draw a card, (.+)", re.I),
    "opponent_draw": re.compile(r"Whenever an opponent draws a card, (.+)", re.I),
    "opponent_gain_life": re.compile(r"Whenever an opponent gains life, (.+)", re.I),
    "opponent_lose_life": re.compile(r"Whenever an opponent loses life, (.+)", re.I),
    "become_monarch": re.compile(r"Whenever you become the monarch, (.+)", re.I),
    "opponent_become_monarch": re.compile(r"Whenever an opponent becomes the monarch, (.+)", re.I),
    "discard": re.compile(r"Whenever you discard a card, (.+)", re.I),
    "opponent_discard": re.compile(r"Whenever an opponent discards a card, (.+)", re.I),
    "opponent_search": re.compile(r"Whenever an opponent searches their library, (.+)", re.I),
    "opponent_sacrifice_creature": re.compile(r"Whenever an opponent sacrifices a creature, (.+)", re.I),
    "second_draw": re.compile(r"Whenever you draw your second card each turn, (.+)", re.I),
    "combat_damage_to_player": re.compile(rf"Whenever {_SELF} deals combat damage to a player, (.+)", re.I),
    "upkeep": re.compile(r"At the beginning of your upkeep, (.+)", re.I),
    "end_step": re.compile(r"At the beginning of your end step, (.+)", re.I),
    "each_upkeep": re.compile(r"At the beginning of each upkeep, (.+)", re.I),
    "each_end_step": re.compile(r"At the beginning of each end step, (.+)", re.I),
    "combat": re.compile(r"At the beginning of combat on your turn, (.+)", re.I),
    "gain_life": re.compile(r"Whenever you gain life, (.+)", re.I),
    "lose_life": re.compile(r"Whenever you lose life, (.+)", re.I),
    "sacrifice_creature": re.compile(r"Whenever you sacrifice a creature, (.+)", re.I),
    "ally_combat_damage": re.compile(r"Whenever a creature you control deals combat damage to a player, (.+)", re.I),
    "token_combat_damage": re.compile(r"Whenever a creature token you control deals combat damage to a player, (.+)",
                                      re.I),
    "host_attacks": re.compile(r"Whenever (?:equipped|enchanted) creature attacks, (.+)", re.I),
    "attack_with_two": re.compile(r"Whenever you attack with two or more creatures, (.+)", re.I),
    "attack_alone": re.compile(r"Whenever (?:you attack with a creature alone|a creature you control attacks alone), (.+)", re.I),
    "creatures_attack": re.compile(r"Whenever one or more creatures you control attack, (.+)", re.I),
    "opponent_attacks": re.compile(r"Whenever an opponent attacks with creatures, (.+)", re.I),
    "cycle": re.compile(r"Whenever you cycle (?:a|another) card, (.+)", re.I),
    "cycle_or_discard": re.compile(r"Whenever you cycle or discard (?:a|another) card, (.+)", re.I),
    "scry_or_surveil": re.compile(r"Whenever you scry or surveil, (.+)", re.I),
    "scry": re.compile(r"Whenever you scry, (.+)", re.I),
    "surveil": re.compile(r"Whenever you surveil, (.+)", re.I),
    "draw_step": re.compile(r"At the beginning of your draw step, (.+)", re.I),
    "opponent_upkeep": re.compile(r"At the beginning of each opponent's upkeep, (.+)", re.I),
    "opponent_end_step": re.compile(r"At the beginning of (?:each|an) opponent's end step, (.+)", re.I),
    "graveyard_leave": re.compile(r"Whenever one or more cards leave your graveyard, (.+)", re.I),
    "any_sacrifice": re.compile(r"Whenever a player sacrifices a permanent, (.+)", re.I),
    "other_sacrifice": re.compile(r"Whenever a player sacrifices another permanent, (.+)", re.I),
    "host_dies": re.compile(r"When(?:ever)? (?:enchanted|equipped) creature dies, (.+)", re.I),
    "host_combat_damage": re.compile(r"Whenever (?:enchanted|equipped) creature deals combat damage to a player, (.+)", re.I),
    "put_into_graveyard": re.compile(rf"When {_SELF} is put into a graveyard from the battlefield, (.+)", re.I),
    "first_life_loss": re.compile(r"Whenever you lose life for the first time each turn, (.+)", re.I),
    "creatures_combat_damage": re.compile(r"Whenever one or more creatures you control deal combat damage to a player, (.+)",
                                          re.I),
    "zero_power_combat_damage": re.compile(r"Whenever one or more creatures you control with base power 0 deal combat damage "
                                           r"to a player, (.+)", re.I),
    "tokens_combat_damage": re.compile(r"Whenever one or more creature tokens you control deal combat damage to a player, "
                                       r"(.+)", re.I),
    "first_life_gain": re.compile(r"Whenever you gain life for the first time each turn, (.+)", re.I),
    "opponent_second_draw": re.compile(r"Whenever an opponent draws their second card each turn, (.+)", re.I),
    "first_main": re.compile(r"At the beginning of your first main phase, (.+)", re.I),
    "second_main": re.compile(r"At the beginning of your second main phase, (.+)", re.I),
}
TRIGGER_EVENTS = tuple(_TRIGGERS)

# One line can name several of a permanent's own events: "When this creature enters or dies, ...".
_SELF_EVENTS = {
    "enters": r"enters(?: the battlefield)?",
    "dies": r"dies",
    "attacks": r"attacks",
    "blocks": r"blocks",
    "combat_damage_to_player": r"deals combat damage to a player",
    "targeted": r"becomes the target of an? (?:spell|spell or ability)",
}
_ANY_SELF_EVENT = "(?:" + "|".join(_SELF_EVENTS.values()) + ")"
_SEVERAL_EVENTS = re.compile(rf"When(?:ever)? {_SELF} ({_ANY_SELF_EVENT}(?: or {_ANY_SELF_EVENT})+), (.+)", re.I)


_WHO = rf"(?:({_SELF}) or another|(another)|an?)"
_TRIBE = r"(?-i:[A-Z][a-z]+)"  # a creature type: "Pest", "Elf"
_PERMANENT_WATCH = rf"(nontoken creature|creature token|token|creature|land|artifact|enchantment|permanent|{_TRIBE})"
_WATCHES = {
    "permanent_enters": re.compile(
        rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control| an opponent controls)? enters(?: the battlefield)?"
        rf"( under your control| under an opponent's control)?, (.+)", re.I),
    "creature_dies": re.compile(rf"Whenever {_WHO} (nontoken creature|creature token|token|creature|{_TRIBE})"
                                r"( you control| an opponent controls)? dies, (.+)", re.I),
    "permanent_leaves": re.compile(rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control| an opponent controls)? leaves the battlefield, (.+)", re.I),
    "permanent_taps": re.compile(rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control)? becomes tapped, (.+)", re.I),
    "permanent_to_graveyard": re.compile(rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control| an opponent controls)? is put into a graveyard "
                                         r"from the battlefield, (.+)", re.I),
    "cast": re.compile(r"Whenever (you cast or copy|you cast|a player casts|an opponent casts) (?:(an?|another)|(?:your|their) (first|second|third)) "
                       r"((?:white|blue|black|red|green) spell|multicolored spell"
                       r"|spell|creature spell|noncreature spell|instant or sorcery spell|artifact spell|enchantment spell"
                       r"|Aura spell|Aura, Equipment, or Vehicle spell|historic spell|spell with \{X\} in its mana cost|prepared spell"
                       r"|(?-i:[A-Z][a-z]+) spell)"  # a creature type: "another Vampire spell"
                       r"(?: with mana value (\d+) or greater)?"
                       r"( from your hand| from your graveyard| from their graveyard| from anywhere other than your hand)?"
                       r"(?(3) each turn), (.+)", re.I),
    "card_to_graveyard": re.compile(rf"Whenever an? ([a-z ]+?) card is put into your graveyard from anywhere, (.+)", re.I),
    "expend": re.compile(r"Whenever you expend (\d+), (.+)", re.I),
}
_WATCH_QUALIFIER = re.compile(r" with (power (\d+) or greater|flying|a \+1/\+1 counter on it|mana value (\d+) or less)"
                              r"(?= (?:enters|dies|leaves the battlefield|becomes tapped))")
# "Whenever one or more other creatures you control with mana value 3 or less enter": read as the singular, once per batch
_ONE_OR_MORE = re.compile(r"Whenever one or more (other )?(nontoken creatures|creature tokens|tokens|creatures|lands|artifacts|"
                          r"enchantments|permanents)( you control| an opponent controls)?( with (?:power \d+ or greater|flying|"
                          r"mana value \d+ or less))? (enter(?: the battlefield)?|die|leave the battlefield)(, .+)")
_SINGULAR = {"nontoken creatures": "nontoken creature", "creature tokens": "creature token", "tokens": "token",
             "creatures": "creature", "lands": "land", "artifacts": "artifact", "enchantments": "enchantment",
             "permanents": "permanent"}
# Watching events whose subject is a permanent, so "it" in the effect can mean that permanent.
_SUBJECT_EVENTS = {"permanent_enters", "creature_dies", "permanent_taps", "permanent_to_graveyard"}
# Triggers about some other creature: there "it" and "that creature" mean that creature, not the source.
_OBJECT_EVENTS = {"ally_attacks", "attacked", "attacked_or_walker", "ally_combat_damage", "token_combat_damage",
                  "host_attacks", "host_combat_damage", "attack_alone"}
# The creature is already gone when it dies, so "it" there has nothing to point at (the line isn't understood).
_HOST_GONE = {"host_dies"}
# Triggers about what some other player did: there "that player" and "they" mean that player.
_PLAYER_EVENTS = {"opponent_draw", "opponent_second_draw", "opponent_gain_life", "opponent_lose_life", "opponent_become_monarch",
                  "opponent_discard", "opponent_search", "opponent_attacks"}
_THAT_CREATURE = re.compile(r"\bthat (creature|land)\b", re.I)
_CONTROLLER = r"(?:its|that (?:creature|permanent|land)'s) controller"
_PLAYER_PRONOUNS = [
    (re.compile(rf"\b{_CONTROLLER} (loses|gains|draws|discards|mills)\b", re.I), r"target player \1"),
    (re.compile(rf"\bto {_CONTROLLER}\b", re.I), "to target player"),
    (re.compile(r"\bthey (lose|gain|draw|discard|mill)\b", re.I), r"target player \1s"),
    (re.compile(r"\bthat player (loses|gains|draws|discards|mills)\b", re.I), r"target player \1"),
    (re.compile(r"\bhave that player (lose|gain|draw|discard|mill)\b", re.I), r"target player \1s"),
    (re.compile(r"\bto that player\b", re.I), "to target player"),
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
        qualifier = (f"power>={q[2]}" if q[2] else "flying" if q[1] == "flying" else f"mv<={q[3]}" if q[3] else "counter:+1/+1")
        line = line[:q.start()] + line[q.end():]
    if m := _WATCHES["cast"].fullmatch(line):
        caster = {"you cast or copy": "you", "you cast": "you", "a player casts": "player",
                  "an opponent casts": "opponent"}[m[1].lower()]
        nth = {"first": 1, "second": 2, "third": 3}.get((m[3] or "").lower(), 0)
        origin = (m[6] or "").strip()
        watch = Watch(m[4].lower(), other=(m[2] or "").lower() == "another", caster=caster, nth_each_turn=nth,
                      with_copy=m[1].lower() == "you cast or copy", mv_at_least=int(m[5] or 0),
                      from_hand=origin == "from your hand",
                      from_zone="graveyard" if "graveyard" in origin else "not_hand" if "other than" in origin else "")
        return "cast", watch, m[7]
    if m := _WATCHES["card_to_graveyard"].fullmatch(line):
        return "card_to_graveyard", Watch(m[1].lower(), yours=True), m[2]
    if m := _WATCHES["expend"].fullmatch(line):
        return "expend", Watch("expend", yours=True, expend=int(m[1])), m[2]
    for event in ("permanent_enters", "creature_dies", "permanent_leaves", "permanent_taps", "permanent_to_graveyard"):
        if m := _WATCHES[event].fullmatch(line):
            self_or_other, another, kind = m[1], m[2], m[3].lower()
            under = m[5] if event == "permanent_enters" else None
            yours = m[4] == " you control" or under == " under your control"
            theirs = m[4] == " an opponent controls" or under == " under an opponent's control"
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
    for line in rules_lines(card):  # persist and undying are keywords that come back from the graveyard
        words = {word.strip().lower() for word in line.split(",")}
        if "prowess" in words:  # whenever you cast a noncreature spell, this gets +1/+1 until end of turn
            abilities.append(TriggeredAbility("cast", (PumpSource(Modifier(1, 1)),), False, "Prowess",
                                              Watch("noncreature spell", caster="you")))
        if "exalted" in words:  # whenever a creature you control attacks alone, that creature gets +1/+1 until end of turn
            abilities.append(TriggeredAbility("attack_alone", (OnSubject(PumpSource(Modifier(1, 1))),), False, "Exalted"))
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


_PAY_TO_RETURN = re.compile(r"you may pay ((?:\{[^}]+\})+)\. If you do, return this card from your graveyard to the "
                            r"battlefield\.", re.I)


@dataclass(frozen=True)
class PayToReturnSelf:
    """Vanguard of the Restless: "you may pay {2}{W}. If you do, return this card from your graveyard to the
    battlefield." It works from the graveyard, so the game looks for it there."""
    cost: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        card = item.card if item is not None else None
        if card is not None and any(c is card for c in controller.graveyard) \
                and game.pays_unless(controller, self.cost, card):
            game.return_from_graveyard(game.graveyard_target(card, controller), controller, "battlefield")


@dataclass(frozen=True)
class MayPay:
    """Trudge Garden, Veinwitch Coven: "You may pay {2}. If you do, <effect>." The effect is one that may have a target, chosen
    when the ability goes on the stack either way."""
    cost: str
    effect: Any

    @property
    def target(self) -> str | None:
        return target_kind(self.effect)

    @property
    def uses_source(self) -> bool:
        return uses_source(self.effect)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if game.pays_optional(controller, self.cost, item.card if item is not None else None):
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class MayPayLoot:
    """Conspiracy Theorist: "You may pay {1} and discard a card. If you do, draw a card." """
    cost: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if controller.hand and game.pays_optional(controller, self.cost, item.card if item is not None else None):
            game.discard(controller, 1)
            game.draw(controller, 1)


_MAY_PAY_THEN = re.compile(r"you may pay ((?:\{[^}]+\})+)\. If you do, (.+)", re.I)
_MAY_PAY_LOOT = re.compile(r"you may pay ((?:\{[^}]+\})+) and discard a card\. If you do, draw a card\.", re.I)


@dataclass(frozen=True)
class ReturnThisFromGraveyard:
    """Teacher's Pest: "{B}{G}: Return this card from your graveyard to the battlefield tapped." It works from the
    graveyard, so the game offers it there (ActivatedAbility.from_graveyard). Squee's upkeep trigger returns it to the hand."""
    tapped: bool = False
    to: str = "battlefield"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        card = item.card if item is not None else None
        if card is not None and any(c is card for c in controller.graveyard):
            game.return_from_graveyard(game.graveyard_target(card, controller), controller, self.to, self.tapped)


def _trigger_body(rest: str) -> tuple[list | None, bool, bool, Condition | None]:
    """The part of a trigger after its event: (effects, or None if not understood; "you may";
    "only once each turn"; an intervening "if" clause)."""
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
    if rest.startswith("if ") and ", " in rest:
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
_SPELL_MV = re.compile(r"that spell's mana value", re.I)
_MAY_PAY_OR = re.compile(r"that player may pay ((?:\{[^}]+\})+)\. If the player doesn't, (.+)")
_UNLESS_PAYS = re.compile(r"(.+?) unless that player pays ((?:\{[^}]+\})+)\.?", re.I)


# Phrases whose "it" is not the permanent that set the trigger off: the card a search finds, the creature just targeted.
_PUT_IT = re.compile(r"\bsearch your library for [^.]*?, (?:reveal (?:it|them), )?put (?:it|that card|them) (?:onto|into)\b"
                     r"|\btap up to one target creature and goad it\b|\bif that enchantment is an Aura, you may attach it to the token\b", re.I)


def _event_body(rest: str, subject_ok: bool, player_ok: bool) -> tuple[list | None, bool, bool, Condition | None]:
    """Like _trigger_body for a trigger about another object or player. "It" means the permanent that set it off
    (only if every effect is about "it"), "that player" / "they" the player who did it (only for effects that
    target a player); where neither can be pointed at, the line isn't understood."""
    about_player = False
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
    about_subject = re.search(r"\bit\b|\bthat spell\b", _PUT_IT.sub("", _MANA_SPENT.sub("", _SPELL_MV.sub("", rest))), re.I) is not None
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


def _split_compound_trigger(line: str) -> list[tuple[str, str]]:
    """ "When this creature enters and whenever one or more tokens you control enter, <effect>" is two triggers with the same
    effect; each is read as a line of its own, as (line to read, the card's own line)."""
    if m := _COMPOUND_TRIGGER.fullmatch(line):
        return [(f"{m[1]} {m[2]}, {m[4]}", line), (f"Whenever {m[3]}, {m[4]}", line)]
    return [(line, line)]


def _triggered_abilities(card: Card) -> list[TriggeredAbility]:
    abilities = []
    lines = [part for raw in _rules_text(card).splitlines() for part in _split_compound_trigger(raw.strip())]
    for line, text in lines:
        bare = _ABILITY_WORD.sub("", line)  # patterns read the line without "Council's dilemma — "; its text stays whole
        if watched := _watch_trigger(line):
            event, watch, rest = watched
            effects, optional, once, condition = _event_body(
                rest, event in _SUBJECT_EVENTS,
                (event == "cast" and watch.caster != "you") or event in _SUBJECT_EVENTS)
            if effects is not None:
                abilities.append(TriggeredAbility(event, tuple(effects), optional, text, watch, once, condition))
            continue
        if several := _SEVERAL_EVENTS.fullmatch(bare):
            effects, optional, once, condition = _trigger_body(several[2])
            if effects is not None:
                for event, pattern in _SELF_EVENTS.items():
                    if any(re.fullmatch(pattern, part, re.I) for part in several[1].split(" or ")):
                        abilities.append(TriggeredAbility(event, tuple(effects), optional, text, once_per_turn=once,
                                                          condition=condition))
            continue
        for event, pattern in _TRIGGERS.items():
            match = pattern.fullmatch(bare)
            if not match:
                continue
            aura_return = next((build() for pattern, build in _AURA_RETURNS if event == "host_dies"
                                and pattern.fullmatch(match[1])), None)
            if aura_return is not None:
                effects, optional, once, condition = aura_return, False, False, None
            elif event in _OBJECT_EVENTS or event in _PLAYER_EVENTS or event in _HOST_GONE:
                effects, optional, once, condition = _event_body(match[1], event in _OBJECT_EVENTS,
                                                                 event in _PLAYER_EVENTS)
            else:
                effects, optional, once, condition = _trigger_body(match[1])
            if effects is not None and event != "dies" and any(isinstance(e, ReturnSelfToBattlefield) for e in effects):
                effects = None  # "return it to the battlefield": it is only gone when the creature has died
            if effects is not None:
                abilities.append(TriggeredAbility(event, tuple(effects), optional, text, once_per_turn=once,
                                                  condition=condition))
            break
    return abilities


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


_CREW = re.compile(r"Crew (\d+)")
_ACTIVATED = re.compile(r"([^:\"]+): (.+)")
_MANA_PART = re.compile(r"(\{(?:\d+|X|S|[WUBRGC]|[WUBRGC]/[WUBRGCP]|2/[WUBRGC])\})+")
_SACRIFICE_SELF = re.compile(rf"Sacrifice {_SELF}", re.I)
_PAY_LIFE_IDENTITY = re.compile(r"Pay life equal to the number of colors in your commanders?'s? color identity")
_PAY_LIFE = re.compile(rf"Pay {_N} life", re.I)
_CARDS = r"(an?|two|three|four)"
_SACRIFICE_OTHER = re.compile(r"Sacrifice (another|an?|two|three|four) (creature|artifact|land|enchantment|permanent|artifact or creature|creature or artifact|Food|Treasure|Clue)s?")
_REMOVE_COUNTER_COST = re.compile(rf"Remove an? {_COUNTER} from (?:CARDNAME|this (?:creature|artifact|permanent|enchantment|land))")
_DISCARD_COST = re.compile(rf"Discard {_CARDS} cards?")
_DISCARD_SELF = re.compile(r"Discard (?:CARDNAME|this card)")
_TAP_CREATURES = re.compile(r"Tap (an?|two|three|four) untapped creatures? you control")
_EXILE_SELF = re.compile(r"Exile (?:CARDNAME|this (?:artifact|creature|permanent|enchantment|land))")
_BOUNCE_SELF = re.compile(r"Return (?:CARDNAME|this (?:artifact|creature|permanent|enchantment|land)) to its owner's hand")
_EXILE_COST = re.compile(rf"Exile {_CARDS} (?:(creature|artifact|land|instant|sorcery|enchantment) )?cards? from your graveyard")
_NUMBER = {"a": 1, "an": 1, "two": 2, "three": 3, "four": 4}
_LOYALTY = re.compile(r"([+\u2212-]?)(\d+)")
_SORCERY_ONLY = "Activate only as a sorcery."
_ONCE_EACH_TURN = "Activate only once each turn."
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
        match = _ACTIVATED.fullmatch(line)
        if not match or is_mana_ability(line):
            continue
        ability = _parse_activated(line, match[1], match[2], planeswalker)
        if ability is not None:
            abilities.append(ability)
    if cost := equip_cost(card):
        abilities.append(ActivatedAbility(f"Equip {cost}", (Attach(),), mana_cost=cost, sorcery_speed=True))
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
            fields.update(sacrifice_other=m[2], sacrifice_another=m[1] == "another", sacrifice_count=_NUMBER.get(m[1], 1))
        elif m := _DISCARD_COST.fullmatch(part):
            fields["discard"] = _NUMBER[m[1]]
        elif _DISCARD_SELF.fullmatch(part):
            fields["discard_self"] = True
        elif m := _TAP_CREATURES.fullmatch(part):
            fields["tap_creatures"] = _NUMBER[m[1]]
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
    if fields.get("condition") and any(isinstance(e, AddMana) for e in effects):
        return None  # a conditional mana ability (Temple of the False God) isn't a stack ability: auto-pay couldn't use it
    return ActivatedAbility(line, tuple(effects), **fields)


_TAP = r"\{T\}(, Sacrifice (?:CARDNAME|this (?:artifact|creature|permanent|land)))?: Add "  # group 1: sacrifice
# Each may end with "Activate only if <condition>." (Temple of the False God, Spire of Industry): that is always the
# last group of the match, None when it is absent.
_IF_TAIL = r"(?: Activate only if (.+)\.)?"
_ADD_SYMBOLS = re.compile(_TAP + r"((?:\{[WUBRGC]\})+)\." + _IF_TAIL)
_ADD_EITHER = re.compile(_TAP + r"\{([WUBRGC])\} or \{([WUBRGC])\}\." + _IF_TAIL)
_ADD_ANY = re.compile(_TAP + r"one mana of any color\." + _IF_TAIL)
_ADD_IDENTITY = re.compile(_TAP + r"one mana of any color in your commander's color identity\." + _IF_TAIL)
# Gilded Lotus. The engine keeps one option set per mana, so the three are chosen independently: auto-pay may spend
# them as different colors, which the card does not allow.
_ADD_ANY_N = re.compile(_TAP + r"(two|three|four|five) mana of any one color\." + _IF_TAIL)
_ANY_N = {"two": 2, "three": 3, "four": 4, "five": 5}


# Study Hall, Path of Ancestry: a mana ability with a rider that triggers when the mana is spent on the right spell.
_SPENT_RIDER = re.compile(r"(.+\.) When (?:you spend this mana|that mana is spent) to cast "
                          r"(your commander|a creature spell that shares a creature type with your commander), "
                          r"scry (1|X, where X is the number of times it's been cast from the command zone this game)\.")


@dataclass(frozen=True)
class ManaSpentTrigger:
    """ "When that mana is spent to cast <spell>, scry <n>." on a mana ability."""
    spell: str  # "commander" (your commander) or "shares_type_with_commander" (a creature spell sharing a type)
    scry: int | str  # a number, or "commander_casts": the times that commander has been cast from the command zone


def mana_spent_trigger(card: Card) -> ManaSpentTrigger | None:
    for line in rules_lines(card):
        if m := _SPENT_RIDER.fullmatch(line):
            return ManaSpentTrigger("commander" if m[2] == "your commander" else "shares_type_with_commander",
                                    1 if m[3] == "1" else "commander_casts")
    return None


def _without_spent_rider(line: str) -> str:
    """The mana ability alone, without its "When that mana is spent ..." sentence."""
    m = _SPENT_RIDER.fullmatch(line)
    return m[1] if m else line


def mana_ability(card: Card, commander_identity: frozenset[str]) -> list[frozenset[str]] | None:
    """The mana a nonland permanent makes when tapped, one set of options per mana.

    Covers "{T}: Add {C}{C}." (Sol Ring), "{T}: Add {G}." (mana creatures),
    "{T}: Add {R} or {G}.", and "one mana of any color" (optionally limited
    to your commander's color identity), each optionally with "Sacrifice this
    artifact" in the cost (Treasure).
    """
    line = _mana_line(card)
    for rule in rules_lines(card):  # Ancient Tomb-style "{T}: Add {C}{C}. ... deals 2 damage to you."
        if m := _PAIN_MULTI.fullmatch(rule):
            return [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[1])]
    units = _mana_from_line(line, commander_identity) if line else None
    if pain := mana_pain(card):  # a Talisman's colored ability joins its colorless one as a single mana
        units = [units[0] | pain[0]] + units[1:] if units else [pain[0]]
    return units


_COUNTER_MANA = re.compile(r"Remove an? ([a-z]+) counter from (?:CARDNAME|this [a-z]+): Add one mana of any color\. "
                           r"Activate only once each turn\.")


def counter_mana(card: Card) -> str | None:
    """Mana Bloom: the counter its mana ability removes (it makes one mana of any color, once each turn)."""
    return next((m[1] for line in rules_lines(card) if (m := _COUNTER_MANA.fullmatch(line))), None)


_ADD_POWER = re.compile(_TAP + r"X mana of any one color, where X is this creature's power\." + _IF_TAIL)


def makes_mana_by_power(card: Card) -> bool:
    """Kami of Whispered Hopes: "{T}: Add X mana of any one color, where X is this creature's power." """
    return any(_ADD_POWER.fullmatch(line) for line in rules_lines(card))


def mana_ability_sacrifices(card: Card) -> bool:
    """Whether using the card's mana ability sacrifices it (Treasure)."""
    line = _mana_line(card)
    return bool(line and any((m := p.fullmatch(line)) and m[1] for p in _MANA_PATTERNS))


def _mana_match(line: str) -> re.Match | None:
    """The match of a plain "{T}: Add ..." line, unless its "Activate only if" condition isn't understood."""
    line = _without_spent_rider(line)
    for pattern in _MANA_PATTERNS:
        if (m := pattern.fullmatch(line)) and (m.group(pattern.groups) is None or _condition(m.group(pattern.groups))):
            return m
    return None


def _mana_line(card: Card) -> str | None:
    """The card's plain "{T}: Add ..." line (Signet-style lines are filter_mana_ability's)."""
    return next((line for line in rules_lines(card) if _mana_match(line)), None)


def mana_condition(card: Card) -> "Condition | None":
    """The "Activate only if ..." condition on the card's plain mana ability, if it has one."""
    line = _mana_line(card)
    m = _mana_match(line) if line else None
    text = m.group(m.re.groups) if m else None
    return _condition(text) if text else None


_MANA_PATTERNS = (_ADD_SYMBOLS, _ADD_EITHER, _ADD_ANY, _ADD_IDENTITY, _ADD_ANY_N)
_PAIN = re.compile(rf"\{{T\}}: Add \{{([WUBRGC])\}} or \{{([WUBRGC])\}}\. {_SELF} deals {_N} damage to you\.", re.I)
# Ancient Tomb: two mana, and the damage is dealt once however much of it is used.
_PAIN_MULTI = re.compile(rf"\{{T\}}: Add ((?:\{{[WUBRGC]\}}){{2,}})\. {_SELF} deals {_N} damage to you\.", re.I)
# City of Brass: the damage comes from the land becoming tapped.
_TAPPED_PAIN = re.compile(rf"Whenever {_SELF} becomes tapped, it deals {_N} damage to you\.", re.I)
# Mana Confluence: paying life, not damage.
_PAY_LIFE_ANY = re.compile(rf"\{{T\}}, Pay {_N} life: Add (one mana of any color|\{{([WUBRG])\}}(?: or \{{([WUBRG])\}})?)\.", re.I)


def is_mana_ability(line: str) -> bool:
    line = _without_spent_rider(line)
    return (_mana_match(line) is not None or _ADD_POWER.fullmatch(line) is not None
            or _COUNTER_MANA.fullmatch(line) is not None or _PER_COUNT.fullmatch(line) is not None
            or _FILTER.fullmatch(line) is not None
            or _FILTER_ANY.fullmatch(line) is not None or _FILTER_LAND.fullmatch(line) is not None or _REFLECT.fullmatch(line) is not None
            or any(p.fullmatch(line) for p in (_PAIN, _PAIN_MULTI, _TAPPED_PAIN, _PAY_LIFE_ANY)))


def mana_pain(card: Card) -> tuple[frozenset[str], int] | None:
    """For painlands and Talismans ("{T}: Add {G} or {U}. This land deals 1 damage to you."): the types
    that cost damage when produced, and how much."""
    for line in rules_lines(card):
        if m := _PAIN.fullmatch(line):
            return frozenset((m[1], m[2])), _count(m[3])
        if m := _PAIN_MULTI.fullmatch(line):
            return frozenset(re.findall(r"[WUBRGC]", m[1])), _count(m[2])
        if m := _TAPPED_PAIN.fullmatch(line):  # every color it makes hurts
            return frozenset("WUBRGC"), _count(m[1])
    return None


_REFLECT = re.compile(r"\{T\}: Add one mana of any (color|type) that a land (an opponent controls|you control) could produce\.")


def reflected_mana(card: Card) -> tuple[bool, bool] | None:
    """Exotic Orchard ("... any color that a land an opponent controls could produce") and Reflecting Pool ("... any
    type that a land you control could produce"): (looks at opponents' lands, colorless counts), or None."""
    for line in rules_lines(card):
        if m := _REFLECT.fullmatch(line):
            return m[2] == "an opponent controls", m[1] == "type"
    return None


def mana_life_cost(card: Card) -> int:
    """Life paid each time a land is tapped for mana ("{T}, Pay 1 life: Add one mana of any color."), or 0."""
    return next((_count(m[1]) for line in rules_lines(card) if (m := _PAY_LIFE_ANY.fullmatch(line))), 0)


def mana_life_types(card: Card) -> frozenset[str]:
    """The mana a land with a life-cost mana ability makes: any color (Mana Confluence) or the listed ones (Horizon lands)."""
    for line in rules_lines(card):
        if m := _PAY_LIFE_ANY.fullmatch(line):
            return frozenset("WUBRG") if m[2].startswith("one") else frozenset(c for c in (m[3], m[4]) if c)
    return frozenset()


def land_mana_units(card: Card) -> list[frozenset[str]] | None:
    """The mana a land makes in one tap when that's more than one ("{T}: Add {B}{G}.", Ancient Tomb's
    {C}{C}), one set per mana; None for the usual one mana, which comes from the card's data."""
    for line in rules_lines(card):
        m = _ADD_SYMBOLS.fullmatch(line) or _PAIN_MULTI.fullmatch(line)
        if m:
            symbols = re.findall(r"[WUBRGC]", m[2] if m.re is _ADD_SYMBOLS else m[1])
            return [frozenset(symbol) for symbol in symbols] if len(symbols) > 1 else None
    return None


def is_identity_mana_land(card: Card) -> bool:
    """Command Tower: a land that makes one mana of any color in your commander's color identity."""
    return "Land" in card.type_line and any(_ADD_IDENTITY.fullmatch(_without_spent_rider(line)) for line in rules_lines(card))


_FILTER = re.compile(r"((?:\{\d+\}|\{[WUBRGC]\}|\{[WUBRG]/[WUBRG]\})+), \{T\}: Add ((?:\{[WUBRGC]\})+)\.")
# Gaea's Cradle, Cabal Coffers, Elvish Archdruid: "{T}: Add {G} for each creature you control." (maybe with a mana cost)
_PER_COUNT = re.compile(r"(?:((?:\{\d+\}|\{[WUBRGC]\})+), )?\{T\}: Add \{([WUBRGC])\} for each ([A-Za-z]+) you control\.")


def mana_per_count(card: Card) -> tuple[str, str, str] | None:
    """(the mana it costs, '' if none; the color it makes; what it counts) for a "Add {G} for each creature you
    control" ability."""
    for line in rules_lines(card):
        if m := _PER_COUNT.fullmatch(line):
            return m[1] or "", m[2], m[3]
    return None


_FILTER_ANY = re.compile(r"((?:\{\d+\}|\{[WUBRGC]\})+), \{T\}: Add one mana of any color\.")  # Hall of Oracles
# A filter land: "{W/B}, {T}: Add {W}{W}, {W}{B}, or {B}{B}." Two mana, each of either color.
_FILTER_LAND = re.compile(r"(\{[WUBRG]/[WUBRG]\}), \{T\}: Add \{([WUBRG])\}\{\2\}, \{\2\}\{([WUBRG])\}, or \{\3\}\{\3\}\.")


def filter_mana_ability(card: Card) -> tuple[str, list[frozenset[str]]] | None:
    """A mana ability that costs mana, like a Signet's "{1}, {T}: Add {W}{U}.":
    (the mana it costs, the mana it makes, one set per mana)."""
    for line in map(_without_spent_rider, rules_lines(card)):
        if m := _FILTER.fullmatch(line):
            return m[1], [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2])]
        if m := _FILTER_ANY.fullmatch(line):
            return m[1], [frozenset("WUBRG")]
        if m := _FILTER_LAND.fullmatch(line):
            return m[1], [frozenset((m[2], m[3]))] * 2
    return None


def _mana_from_line(line: str, commander_identity: frozenset[str]) -> list[frozenset[str]] | None:
    if m := _ADD_SYMBOLS.fullmatch(line):
        return [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2])]
    if m := _ADD_EITHER.fullmatch(line):
        return [frozenset((m[2], m[3]))]
    if _ADD_ANY.fullmatch(line):
        return [frozenset("WUBRG")]
    if m := _ADD_ANY_N.fullmatch(line):
        return [frozenset("WUBRG")] * _ANY_N[m[2]]
    return [commander_identity] if commander_identity else None
