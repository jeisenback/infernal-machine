"""What a spell or ability does: the effect classes and the sentence templates that read rules text into them."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Callable, Literal

from ..cards import Card
from ..characteristics import LOSES_HEXPROOF, Modifier

if TYPE_CHECKING:
    from ..game import Game, Seat

from .common import (
    CANT_BE_BLOCKED,
    CANT_BLOCK,
    _ANY_N,
    _CHANGE,
    _COLOR_LETTER,
    _COUNTER,
    _KEYWORDS,
    _KEYWORDS_BARE,
    _LAND_TYPE,
    _MANA_SYMBOLS,
    _N,
    _N_FIXED,
    _NUM,
    _PT,
    _PT_X,
    _SELF,
    _VOTE_PREFIX,
    _count,
    _counter_name,
    _keyword_list,
    _modifier,
    _number,
    _signed,
    _split_sentences,
    cant_be_countered,
    Quantity,
)
from .targets import (
    MassFilter,
    _CARDS_PLURAL,
    _CARD_TYPE,
    _LAND_TYPES,
    _LAND_TYPES_PLURAL,
    _SEARCH_TYPE,
    _card_kind,
    _graveyard_kind,
    _land_types,
    follows_target,
    target_kind,
    uses_player,
    uses_source,
    uses_subject,
)


@dataclass(frozen=True)
class Draw:
    count: Quantity
    more: int = 0  # Zimone: "If you control eight or more lands, draw two cards instead."
    more_if: "Condition | None" = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = self.more if self.more_if and game.condition_holds(self.more_if, controller, game.resolving_source) else self.count
        game.draw(controller, game.amount(count))


@dataclass(frozen=True)
class GainLife:
    amount: Quantity

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.change_life(controller, game.amount(self.amount))


@dataclass(frozen=True)
class ExileTargetIfDies:
    """ "If that creature would die this turn, exile it instead." (Lava Coil, Bleed Dry): the target the spell just dealt with."""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and hasattr(target, "exile_if_dies") and "Creature" in target.card.type_line:
            target.exile_if_dies = game.turn


@dataclass(frozen=True)
class ExileDamagedIfDie:
    """ "If a creature dealt damage this way would die this turn, exile it instead." (Anger of the Gods): every creature the spell
    has dealt damage to."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for creature in game.resolving_damaged:
            creature.exile_if_dies = game.turn


@dataclass(frozen=True)
class PlayerLosesLife:
    """Afflict N: "defending player loses N life", the player the trigger is about."""
    amount: int
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(target, -self.amount)


@dataclass(frozen=True)
class OpponentsLoseLife:
    amount: Quantity

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            game.change_life(seat, -game.amount(self.amount))


@dataclass(frozen=True)
class Damage:
    amount: Quantity
    target: str
    optional_target: bool = False  # one point of "4 damage divided as you choose among any number of targets"
    distinct: bool = False  # "... to each of up to two targets": the second can't be the first again

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.damage(target, game.amount(self.amount))


@dataclass(frozen=True)
class DamageToYou:
    """Mana Vault: "... it deals 1 damage to you." (the ability's controller, from its source)"""
    amount: Quantity

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.damage(controller, game.amount(self.amount))


@dataclass(frozen=True)
class Destroy:
    target: str
    another: bool = False  # "destroy another target ...": not the source itself
    no_regen: bool = False  # "It can't be regenerated."
    optional_target: bool = False  # "destroy up to two target ...": each target may be left out
    distinct: bool = False  # ... and may not repeat an earlier target of the same effect
    if_color: str = ""  # Pyroblast: "Destroy target permanent if it's blue." (checked as it resolves)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and (not self.if_color or self.if_color in target.card.colors):
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
    if_color: str = ""  # Pyroblast: "Counter target spell if it's blue." (checked as it resolves)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if self.if_color and target is not None and self.if_color not in target.card.colors:
            return
        if target is not None and not cant_be_countered(target.card) and not game.uncounterable(target):
            if self.unless and game.pays_unless(target.controller, self.unless, target.card):
                return
            if self.delayed_mana:
                controller.delayed_mana += int(target.card.cmc) + target.x
            game.counter(target, self.exile)


@dataclass(frozen=True)
class ChangeTarget:
    """Deflection: "Change the target of target spell with a single target." (Divert: "... unless that spell's controller pays {2}.")
    You choose the new target, which must be another legal one for that spell or ability."""
    target: str = "spell with a single target"
    unless: str = ""
    every: bool = False  # Deflecting Swat: "You may choose new targets for target spell or ability." (each may stay)
    to: str = ""  # "The new target must be a player." / "... a creature."; "to this creature": the source of the ability
    optional: bool = False  # Hydroelectric Specimen: "you may change the target ..."
    lone: bool = True  # False: "Change a target of target spell or ability to this creature." (Spellskite) -- one of several

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or (self.unless and game.pays_unless(target.controller, self.unless, target.card)):
            return
        if self.optional and controller.player.choose(CHANGE_TARGET_PROMPT + target.card.name, ["Yes", "No"]) != 0:
            return
        game.change_target(controller, target, self.every, self.to, self.lone)


CHANGE_TARGET_PROMPT = "Change the target of "  # followed by the spell's name; Yes or No


@dataclass(frozen=True)
class NewTargetMustBe:
    """ "The new target must be a player." after a change of target: _merge_new_target folds it into that effect."""
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


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
            game.exile_noting(target, game.resolving_source)


@dataclass(frozen=True)
class ExileControllerDraws:
    """Season of the Burrow: "Exile target nonland permanent. Its controller draws a card." (its controller as it was exiled)"""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            owner = game.controller_of(target)
            game.exile_noting(target, game.resolving_source)
            if owner is not None:
                game.draw(owner, 1)


@dataclass(frozen=True)
class ExiledOwnerGetsToken:
    """Skyclave Apparition: "the exiled card's owner creates an X/X ... token, where X is the mana value of the exiled
    card." The target is the source, which has already left the battlefield."""
    token: Card
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        for owner, card in target.exiled_with:
            size = str(int(card.cmc))
            game.create_tokens(owner, dataclasses.replace(self.token, power=size, toughness=size), 1)


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
class RevealTopTradeLife:
    """Keen Duelist: you and target opponent each reveal the top card, lose life equal to the other's card's mana value, and
    put your own revealed card into your hand."""
    target: str = "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        pair = (controller, target)
        revealed = [(seat, seat.library.pop(0) if seat.library else None) for seat in pair]
        for seat, card in revealed:
            if card is not None:
                game.broadcast({"event": "revealed", "seat": seat.index, "card": card.name})
        for (seat, _), (_, other) in zip(revealed, reversed(revealed)):
            if other is not None:
                game.change_life(seat, -int(other.cmc))
        for seat, card in revealed:
            if card is not None:
                seat.hand.append(card)


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
class MaySacrificeThen:
    """Springbloom Druid: "You may sacrifice a land. If you do, search your library for up to two basic land cards, ..." """
    kind: str
    then: Any

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.may_sacrifice(controller, self.kind):
            self.then.resolve(game, controller, target)


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
    repeat: bool = False  # "You may choose the same mode more than once." (a Confluence): `max` picks, each mode any number of times
    costs: tuple[int, ...] = ()  # pawprint modes (a Season): what each mode costs of the `max` pawprints to spend


_MODAL_COUNTS = {"one": (1, 1), "up to one": (0, 1), "two": (2, 2), "three": (3, 3), "one or both": (1, 2), "one or more": (1, 0)}


_MODAL_HEADER = re.compile(r"Choose (one or both|one or more|up to one|one|two|three) \u2014", re.I)


_MODAL_REPEAT = re.compile(r"Choose (three|four|five|up to four)\. You may choose the same mode more than once\.")


_REPEAT_COUNTS = {"three": (3, 3), "four": (4, 4), "five": (5, 5), "up to four": (0, 4)}


_MODAL_PAWPRINTS = re.compile(r"Choose up to (one|two|three|four|five) \{P\} worth of modes\. You may choose the same mode more than once\.")


_PAWPRINT_MODE = re.compile(r"((?:\{P\})+) \u2014 (.+)")


_PAWPRINT_COUNTS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def _parse_pawprint_modal(how: str, lines: list[str]) -> list | None:
    """A Season: "Choose up to five {P} worth of modes. You may choose the same mode more than once." and modes written "{P}{P} \u2014 ..."."""
    modes, texts, costs = [], [], []
    for line in lines:
        if not (m := _PAWPRINT_MODE.fullmatch(line)):
            return None
        whole = _template(m[2])  # a mode of two sentences that only read together ("Choose artifact or enchantment. Destroy ...")
        effects = ([whole] if not isinstance(whole, list) else whole) if whole is not None else _parse(_split_sentences(m[2]))
        if not effects:
            return None
        modes.append(tuple(effects))
        texts.append(line)
        costs.append(len(m[1]) // 3)
    return [Modal(0, _PAWPRINT_COUNTS[how], tuple(modes), tuple(texts), repeat=True, costs=tuple(costs))] if modes else None


_MODAL_COMMANDER = re.compile(r"Choose one\. If you control a commander as you cast this spell, you may choose both instead\.")


def is_modal_header(line: str) -> bool:
    return (_MODAL_HEADER.fullmatch(line) is not None or _MODAL_REPEAT.fullmatch(line) is not None
            or _MODAL_PAWPRINTS.fullmatch(line) is not None or _MODAL_COMMANDER.fullmatch(line) is not None)


def mode_text(line: str) -> str:
    """A mode of a modal spell without its bullet."""
    return line[2:] if line.startswith("\u2022 ") else line


def _parse_modal(how: str, lines: list[str], repeat: bool = False) -> list | None:
    modes, texts = [], []
    for line in lines:
        if not line.startswith("\u2022 "):
            return None  # something other than modes (entwine, escalate, ...)
        effects = _parse(_split_sentences(mode_text(line)))
        if not effects:
            return None
        modes.append(tuple(effects))
        texts.append(mode_text(line))
    if repeat:  # a mode may be chosen again, so two modes can fill "choose three"
        low, high = _REPEAT_COUNTS[how]
        return [Modal(low, high, tuple(modes), tuple(texts), repeat=True)] if modes else None
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


BASIC_LAND_TYPES = ("Plains", "Island", "Swamp", "Mountain", "Forest")


@dataclass(frozen=True)
class TargetControllerMayFetchBasicLand:
    """Path to Exile: "Its controller may search their library for a basic land card, put it onto the battlefield tapped, ..."
    (Assassin's Trophy puts it onto the battlefield untapped)"""
    tapped: bool = True
    typed: bool = False  # Boseiju: "a land card with a basic land type" (a dual land counts)
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.fetch_basic_land(target.last_controller, optional=True, tapped=self.tapped,
                                  subtypes=BASIC_LAND_TYPES if self.typed else None)


@dataclass(frozen=True)
class PutCounters:
    count: Quantity
    counter: str  # "+1/+1" or "-1/-1"
    target: str
    another: bool = False  # "on another target creature you control": not the source itself
    optional_target: bool = False  # "on each of up to two target creatures": each target may be left out
    distinct: bool = False  # ... and may not repeat an earlier target of the same effect
    grant: frozenset[str] = frozenset()  # Pack a Punch: "It gains trample until end of turn." (it is the creature that got them)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))
            if self.grant:
                game.modify_until_end_of_turn(target, Modifier(keywords=self.grant))


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


EXILE_DISCARDED_PROMPT = "Exile which discarded card from your graveyard?"


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


PUT_COUNTERS_PROMPT = "Put counters on which creature you control for "  # followed by the source's name


@dataclass(frozen=True)
class PutCountersOnChosenCreature:
    """Breena: "you put two +1/+1 counters on a creature you control." Nothing is targeted; you choose as it resolves."""
    count: Quantity
    counter: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = [p for p in controller.battlefield if "Creature" in p.card.type_line]
        if not creatures:
            return
        source = game.resolving_item.card.name if game.resolving_item is not None else "the ability"
        pick = controller.player.choose(PUT_COUNTERS_PROMPT + source, [game.label(p) for p in creatures]) if len(creatures) > 1 else 0
        game.put_counters(creatures[pick], self.counter, game.amount(self.count))


DISTRIBUTE_PROMPT = "Put a counter on which creature for "  # followed by the source's name


@dataclass(frozen=True)
class DistributeCounters:
    """ "Distribute three +1/+1 counters among one, two, or three target creatures you control." The counters are given out one at
    a time as the effect resolves, to any creature of the kind (so any split among any number of them is possible). Nothing is
    targeted, but a creature that couldn't be targeted (hexproof, protection from the source) is left out all the same."""
    count: int | str
    counter: str
    kind: str  # "creature" or "creature you control"
    another: bool = False  # "other target creatures": not the source itself

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_item.card.name if game.resolving_item is not None else "the ability"
        for _ in range(game.amount(self.count)):
            options = [p for _, p in game.target_options(self.kind, controller, game.resolving_colors)]
            options = [p for p in options if not (self.another and p is game.resolving_source)]
            if not options:
                return
            pick = controller.player.choose(DISTRIBUTE_PROMPT + source, [game.label(p) for p in options]) if len(options) > 1 else 0
            game.put_counters(options[pick], self.counter, 1)


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


SHIFT_COUNTERS_PROMPT = "Shift how many counters off "  # then the creature's name; options are "0", "1", ... (a bot keeps them)


SHIFT_ONTO_PROMPT = "Shift them onto which creature? "  # followed by the source's name


@dataclass(frozen=True)
class MoveCountersToOthers:
    """Forgotten Ancient: "you may move any number of +1/+1 counters from this creature onto other creatures." (nothing is
    targeted: you choose how many, and where, as it resolves)"""
    counter: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        while (have := target.counters.get(self.counter, 0)) > 0:
            others = [p for s in game.live_seats() for p in s.battlefield if "Creature" in p.card.type_line and p is not target]
            if not others:
                return
            number = controller.player.choose(SHIFT_COUNTERS_PROMPT + target.card.name, [str(n) for n in range(have + 1)])
            if number == 0:
                return
            pick = controller.player.choose(SHIFT_ONTO_PROMPT + target.card.name, [game.label(p) for p in others])
            game.move_counters(target, others[pick], self.counter, number)


@dataclass(frozen=True)
class MoveCountersOnto:
    """The second target: the counters (up to `count`, or all if None) move from the first target to this one."""
    count: int | Literal["any"] | None  # a number, None for all of them, or "any" for a number the controller chooses
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
class RemoveCountersFromSource:
    """ "Remove two hour counters from this enchantment." (Midnight Oil)"""
    count: int
    counter: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.remove_counters(target, self.counter, self.count)


@dataclass(frozen=True)
class DamageWhatItAttacks:
    """Raid Bombardment: "... deals 1 damage to the player or planeswalker that creature is attacking." The creature that
    attacked is the subject."""
    amount: int
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        attack = next((a for a in game.combat.attacks if a.attacker is target), None) if target is not None else None
        if attack is not None:
            game.damage(attack.walker if attack.walker is not None else attack.defender, self.amount)


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
    count: Quantity
    counter: str
    kind: str = ""  # a creature type, "" for every creature
    grant: frozenset[str] = frozenset()  # Ursine Guide's spell: "They gain trample until end of turn."
    or_vehicle: bool = False  # Ao: "each permanent you control that's a creature or Vehicle"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if ("Creature" in permanent.card.type_line or self.or_vehicle and "Vehicle" in permanent.card.type_line) \
                    and self.kind in permanent.card.type_line:
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
    count: Quantity
    counter: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))


@dataclass(frozen=True)
class Hideaway:
    """Hideaway N: "When this enters, look at the top N cards of your library, exile one face down, then put the rest on
    the bottom in a random order." """
    count: int
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.hideaway(controller, target, self.count)


@dataclass(frozen=True)
class PlayExiledCard:
    """A Hideaway land's "You may play the exiled card without paying its mana cost if <condition>." The condition is
    checked as the ability resolves."""
    condition: "Condition"
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.condition_holds(self.condition, controller, target):
            game.play_hideaway(controller, target)


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


CHOOSE_TYPE_PROMPT = "Choose a type"  # options: the types that can be chosen (Season of Gathering)


CHOOSE_COPY_PROMPT = "Choose a permanent to copy"  # options: the permanents (Season of Weaving)


@dataclass(frozen=True)
class DestroyAllOfChosenType:
    """Season of Gathering: "Choose artifact or enchantment. Destroy all permanents of the chosen type." """
    kinds: tuple[str, ...]  # what can be chosen

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        kind = self.kinds[controller.player.choose(CHOOSE_TYPE_PROMPT, [k.capitalize() for k in self.kinds])]
        game.destroy_all(game.mass_targets(kind, controller), False, None, controller)


@dataclass(frozen=True)
class CopyChosenPermanent:
    """Season of Weaving: "Choose an artifact or creature you control. Create a token that's a copy of it." (chosen on resolution)"""
    kind: str  # "artifact or creature you control"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        options = game.mass_targets(self.kind, controller)
        if not options:
            return
        chosen = options[controller.player.choose(CHOOSE_COPY_PROMPT, [game.label(p) for p in options])]
        card = chosen.card if chosen.card.type_line.startswith("Token") else dataclasses.replace(chosen.card, type_line="Token " + chosen.card.type_line)
        game.create_tokens(controller, card, 1)


@dataclass(frozen=True)
class DoubleStats:
    """ "Double target creature's power and toughness until end of turn." / "Double the power of each creature you control until end of
    turn." / "Double this creature's power until end of turn." / "double target creature's power X times": it gets +P/+T equal to its
    power and toughness as this resolves (again for each time), and several creatures are doubled together."""
    power: bool
    toughness: bool
    target: str | None = None  # "creature", "creature you control"
    each: bool = False  # each creature you control
    subtype: str = ""  # "each Dragon you control" (Thrakkus the Butcher)
    times: Quantity = 1  # "X times" (Exponential Growth)
    uses_source: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = ([p for p in controller.battlefield if "Creature" in p.card.type_line
                      and (not self.subtype or self.subtype in p.card.type_line.partition("\u2014")[2].split())]
                     if self.each else [target] if target is not None else [])
        for _ in range(game.amount(self.times)):
            doubled = [(p, game.power(p) if self.power else 0, (game.toughness(p) or 0) if self.toughness else 0) for p in creatures]
            for permanent, power, toughness in doubled:
                game.modify_until_end_of_turn(permanent, Modifier(power, toughness))
        if target is not None and not self.each and game.resolving_item is not None and game.resolving_item.carried is None:
            game.resolving_item.carried = target  # "Then it fights ...": the creature just doubled


@dataclass(frozen=True)
class CreateDelayedTrigger:
    """ "Until end of turn, whenever you cast a spell, ..." / "Whenever you cast a creature spell this turn, draw a card.": the
    triggered ability it names (read by effects/triggers.py) is set up as this resolves and lasts through the turn, or through
    the controller's next turn (CR 603.7). With `when` it is about the creature targeted just before ("Whenever that creature deals
    combat damage to a player this turn, ..."): it sets off when that creature does one of those things (Game._remembered)."""
    abilities: tuple
    next_turn: bool = False
    when: frozenset = frozenset()

    @property
    def follows_target(self) -> bool:
        return bool(self.when)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is None or (self.when and target is None):
            return
        for ability in self.abilities:
            game.add_delayed(ability, game.resolving_item, controller, self.next_turn, target if self.when else None, self.when)


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
    subtype: str = ""  # "Spirits you control gain double strike and vigilance until end of turn." ("non-Human": all but those)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        seats = game.live_seats() if self.everyone else game.opponents(controller) if self.opponents else [controller]
        for seat in seats:
            for permanent in list(seat.battlefield):
                kinds = permanent.card.type_line.partition("\u2014")[2].split()
                if "Creature" in permanent.card.type_line and (
                        not self.subtype or (self.subtype.removeprefix("non-") in kinds) != self.subtype.startswith("non-")):
                    game.modify_until_end_of_turn(permanent, self.modifier)


@dataclass(frozen=True)
class EachDamagesItself:
    """Wave of Reckoning: "Each creature deals damage to itself equal to its power." (all at the same time)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = [(p, game.power(p)) for seat in game.live_seats() for p in seat.battlefield if "Creature" in p.card.type_line]
        for permanent, power in creatures:
            game.damage(permanent, max(power, 0), source=permanent)


@dataclass(frozen=True)
class EachCreatureDamagesItsController:
    """Rakdos Charm: "Each creature deals 1 damage to its controller." (all at the same time)"""
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = [(p, seat) for seat in game.live_seats() for p in seat.battlefield if "Creature" in p.card.type_line]
        for permanent, owner in creatures:
            game.damage(owner, self.amount, source=permanent)


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


_ENCHANT_HEAD = (r"(?:(?:non-?[a-z]+|basic|tapped) )?(?:land|creature|artifact|enchantment|planeswalker|permanent|equipment"
                 r"|wall|vehicle|forest|plains|island|swamp|mountain)")
_ENCHANT = re.compile(rf"Enchant (creature card in a graveyard|{_ENCHANT_HEAD}(?:,? (?:or )?{_ENCHANT_HEAD})*"
                      r"(?: an opponent controls| you control| you don't control)?)", re.I)


@dataclass(frozen=True)
class CreateTokens:
    count: Quantity
    token: Card
    counters: tuple[int | str, str] | None = None  # "Create a 0/0 ... token. Put X +1/+1 counters on it."
    tapped: bool = False  # "Create a number of tapped Treasure tokens ..." (Goldvein Hydra)
    more: Quantity = 0  # Prismari Pianist: "If that spell's mana value is 5 or greater, create three of those tokens instead."
    more_if: "Condition | None" = None
    exile_at_end: bool = False  # Manaform Hellkite: "Exile that token at the beginning of the next end step."
    haste: bool = False  # Sokenzan: "They gain haste until end of turn."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = self.more if self.more_if and game.condition_holds(self.more_if, controller, game.resolving_source) else self.count
        token = self.token
        if "X" in (token.power, token.toughness):  # "an X/X ... token": its size is fixed as it's created
            token = dataclasses.replace(token, power=str(game.amount(token.power or 0)),
                                        toughness=str(game.amount(token.toughness or 0)))
        counters = (game.amount(self.counters[0]), self.counters[1]) if self.counters else None
        made = game.create_tokens(controller, token, game.amount(count), counters, tapped=self.tapped)
        if self.haste:
            for permanent in made:
                game.modify_until_end_of_turn(permanent, Modifier(keywords=frozenset({"haste"})))
        if self.exile_at_end and made:
            game.leave_at_next_end_step(made, "exiled", "exile")


@dataclass(frozen=True)
class CopyToken:
    """ "Create a token that's a copy of target creature you control." """
    target: str
    count: int = 1  # Rite of Replication: "If this spell was kicked, create five of those tokens instead."
    another: bool = False  # "a copy of another target creature you control": not the source itself
    haste: bool = False  # Inspired Skypainter's spell: "That token gains haste until end of turn."
    legendary: bool = False  # Adagia: "..., except it's legendary."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            card = target.card
            if not card.type_line.startswith("Token"):
                card = dataclasses.replace(card, type_line="Token " + card.type_line)
            if self.legendary and "Legendary" not in card.type_line:
                card = dataclasses.replace(card, type_line=card.type_line.replace("Token ", "Token Legendary ", 1))
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
    count: Quantity  # for each opponent
    token: Card
    haste: bool = False
    exile_at_end: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.attacking_tokens(controller, self.token, game.amount(self.count), self.haste,
                              "exiled" if self.exile_at_end else None)


@dataclass(frozen=True)
class TokensJoinAttack:
    """Mobilize: "Create two tapped and attacking 1/1 red Warrior creature tokens. Sacrifice them at the beginning of the
    next end step." The second sentence is folded in by _merge_attacking_tokens."""
    count: Quantity
    token: Card
    sacrifice_at_end: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_source is not None:
            game.tokens_join_attack(controller, game.resolving_source, self.token, game.amount(self.count), self.sacrifice_at_end)


@dataclass(frozen=True)
class _SacrificeThemLater:
    """ "Sacrifice them at the beginning of the next end step.": only ever after TokensJoinAttack."""


@dataclass(frozen=True)
class _TheyGainHaste:
    """ "They gain haste until end of turn.": only ever after AttackingTokens."""


@dataclass(frozen=True)
class _ExileThemLater:
    """ "Exile them at the beginning of the next end step.": only ever after AttackingTokens."""


def _merge_attacking_tokens(effects: list) -> list | None:
    merged: list = []
    for effect in effects:
        if isinstance(effect, _TheyGainHaste) and merged and isinstance(merged[-1], CreateTokens):  # Sokenzan
            merged[-1] = dataclasses.replace(merged[-1], haste=True)
        elif isinstance(effect, _SacrificeThemLater):
            if not (merged and isinstance(merged[-1], TokensJoinAttack)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], sacrifice_at_end=True)
        elif isinstance(effect, (_TheyGainHaste, _ExileThemLater)):
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


ALL_DAMAGE = 10 ** 9  # "prevent all damage": a shield too big to use up


@dataclass(frozen=True)
class PreventAllCombatDamage:
    """Fog: "Prevent all combat damage that would be dealt this turn." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fog_turn = game.turn


@dataclass(frozen=True)
class PreventNext:
    """ "Prevent the next 2 damage that would be dealt to any target (target creature, you, this creature) this turn."
    With no `target` and not `uses_source`, it is the controller that is shielded."""
    amount: int
    target: str = ""
    uses_source: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        shielded = target if (self.target or self.uses_source) else controller
        if shielded is not None:
            game.shield(shielded, self.amount)


@dataclass(frozen=True)
class _TokenPerPrevented:
    """ "For each 1 damage prevented this way, create ...": only ever after PreventCombatDamageToYou."""
    token: Card


def _prevent_next(amount: int, whom: str) -> PreventNext:
    whom = whom.lower()
    if whom == "any target":
        return PreventNext(amount, "any")
    if whom == "target creature":
        return PreventNext(amount, "creature")
    return PreventNext(amount) if whom == "you" else PreventNext(amount, uses_source=True)


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
    that token." (two sentences, folded together by _merge_token_copies). The older wording ended "until end of turn"."""
    until_end_of_turn: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tokens_become_copies(controller, self.until_end_of_turn)


@dataclass(frozen=True)
class _ChooseToken:
    """ "Then you may choose a token you control.": only ever before _OthersBecomeCopies."""


@dataclass(frozen=True)
class _OthersBecomeCopies:
    """ "If you do, each other token you control becomes a copy of that token (until end of turn)." """
    until_end_of_turn: bool = False


def _merge_token_copies(effects: list) -> list | None:
    merged: list = []
    i = 0
    while i < len(effects):
        if isinstance(effects[i], _ChooseToken):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _OthersBecomeCopies)):
                return None
            merged.append(TokensBecomeCopies(effects[i + 1].until_end_of_turn))
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
    count: Quantity
    play: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.three_way_split(controller, game.amount(self.count), self.play)


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
class ManifestDread:
    """ "Manifest dread." (twice: `times`), then perhaps "put N +1/+1 counters on that creature" or "attach this Equipment to
    that creature" (the last one manifested)."""
    times: int = 1
    counters: int = 0
    attach: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        made = None
        for _ in range(self.times):
            made = game.manifest_dread(controller)
        if made is None:
            return
        if self.counters:
            game.put_counters(made, "+1/+1", self.counters)
        if self.attach and game.resolving_source is not None:
            game.attach(game.resolving_source, made)


@dataclass(frozen=True)
class DanceWithCalamity:
    """ "Shuffle your library. As many times as you choose, you may exile the top card of your library. If the total mana
    value of the cards exiled this way is 13 or less, you may cast any number of spells from among those cards without
    paying their mana costs." """
    limit: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.dance_with_calamity(controller, self.limit)


@dataclass(frozen=True)
class AttackerCreatesAttackingToken:
    """Combat Calligrapher: "that attacking player creates a tapped 2/1 ... Inkling creature token with flying that's attacking
    that opponent." The target is the player who attacked; the opponent is the seat the trigger carries in x."""
    token: Card
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if target is not None and item is not None and game.combat is not None:
            game.token_attacking(target, self.token, game.seats[item.x])


@dataclass(frozen=True)
class CopySpellForEachOtherCreature:
    """Mirrorwing Dragon: "that player copies that spell for each other creature they control that the spell could target. Each
    copy targets a different one of those creatures." The target is the caster; the spell rides along with the trigger."""
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if target is not None and item is not None and item.source is not None and hasattr(item.carried, "targets"):
            game.copy_spell_for_each_other_creature(item.carried, target, item.source)


@dataclass(frozen=True)
class ExileDeadMakeSpiritCopy:
    """Hofri Ghostforge: "Exile it. If you do, create a token that's a copy of that creature, except it's a Spirit in addition to
    its other types and it has "When this token leaves the battlefield, return the exiled card to its owner's graveyard."" """
    uses_dead_subject = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_dead_make_spirit_copy(controller, target)


@dataclass(frozen=True)
class ReturnExiledToGraveyard:
    """Hofri Ghostforge's token: "When this token leaves the battlefield, return the exiled card to its owner's graveyard." """
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_exiled_with_to_graveyard(target)


@dataclass(frozen=True)
class BecomeCopyUntilEndOfTurn:
    """Muddle, the Ever-Changing: "... becomes a copy of up to one target nonlegendary creature you control until end of turn,
    except it has myriad." The source takes on the target's card (and `keyword`) until cleanup."""
    keyword: str
    target: str = "nonlegendary creature you control"
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_source
        if target is not None and source is not None and game.on_battlefield(source):
            game.become_copy_until_end_of_turn(source, target, self.keyword)


@dataclass(frozen=True)
class CopyEnteredTokensAttacking:
    """Redoubled Stormsinger: "For each creature token you control that entered this turn, create a tapped and attacking token
    that's a copy of that token. At the beginning of the next end step, sacrifice those tokens." The copies attack whom the
    attacking source attacks."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_entered_tokens_attacking(controller, target)


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
class PutExiledWithIntoGraveyard:
    """Currency Converter: "Put a card exiled with this artifact into its owner's graveyard. If it's a land card, create a Treasure
    token. If it's a nonland card, create a 2/2 black Rogue creature token." """
    land_token: Card
    nonland_token: Card
    uses_source = True
    needs_exiled_with = True  # it can only be activated while a card is exiled with it

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        card = game.put_exiled_with_into_graveyard(controller, target)
        if card is not None:
            game.create_tokens(controller, self.land_token if "Land" in card.type_line else self.nonland_token, 1)


_CLASS_LEVEL_LINE = re.compile(r"((?:\{[^}]+\})+): Level (\d)")


@dataclass(frozen=True)
class LevelUp:
    """Class: "{1}{B}: Level 2": the Class gains the next level (only at sorcery speed, and only the level after its own)."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.class_level_up(target)


@dataclass(frozen=True)
class CastExiledWithFree:
    """Quintorius: "Choose target card exiled with Quintorius. You may cast that card this turn without paying its mana cost. If
    that spell would be put into a graveyard, put it on the bottom of its owner's library instead." (chosen as it resolves)"""
    bottom_after: bool = True
    uses_source = True
    needs_exiled_with = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.cast_exiled_with_free(controller, target, self.bottom_after)


@dataclass(frozen=True)
class EachExilesGraveyardCardCounters:
    """Augusta, Order Returned: "each player exiles a card from their graveyard. When one or more nonland cards are exiled this way,
    put that many +1/+1 counters on target attacking creature." (the target is chosen with the trigger)"""
    target: str = "attacking creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = game.each_player_exiles_graveyard_card(controller)
        if count and target is not None and game.on_battlefield(target):
            game.put_counters(target, "+1/+1", count)


@dataclass(frozen=True)
class ExileThenCastCopy:
    """Renegade Bull: "Exile up to one target instant or sorcery card from your graveyard and copy it. You may cast the copy without
    paying its mana cost." """
    target: str = "graveyard:instant or sorcery:yours"
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or not game.exile_from_graveyard(target):
            return
        if controller.player.choose(CAST_COPY_PROMPT + target.card.name, ["Yes", "No"]) == 0:
            game.cast_copy_free(controller, target.card)


@dataclass(frozen=True)
class MayCastFromHandFree:
    """Rishkar's Expertise: "You may cast a spell with mana value 5 or less from your hand without paying its mana cost." """
    max_value: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        spells = [c for c in controller.hand if "Land" not in c.type_line and c.cmc <= self.max_value]
        if not spells:
            return
        pick = controller.player.choose(FREE_CAST_PROMPT, [c.name for c in spells] + [DECLINE])
        if pick < len(spells):
            game.cast_free(controller, spells[pick])


FREE_CAST_PROMPT = "Cast which spell without paying its mana cost? "
DECLINE = "Don't cast"
CAST_COPY_PROMPT = "Cast a copy without paying its mana cost: "  # followed by the card's name; Yes or No


@dataclass(frozen=True)
class MayCopyThisSpellFromGraveyard:
    """Sevinne's Reclamation: "If this spell was cast from a graveyard, you may copy this spell and may choose a new target for the
    copy." The copy is not cast, so it does not copy itself."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if item is not None and item.from_graveyard and controller.player.choose(COPY_THIS_PROMPT + item.card.name, ["Yes", "No"]) == 0:
            game.copy_spell(item, controller, new_targets=True)


COPY_THIS_PROMPT = "Copy this spell: "  # followed by its name; Yes or No


@dataclass(frozen=True)
class DoubleCountersOnTargets:
    """Kinetic Ooze: "If X is 10 or more, double the number of +1/+1 counters on any number of other target creatures." Targets
    are chosen whatever X is; nothing is doubled below `min_x`."""
    counter: str
    target: str
    min_x: int
    another = True
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.x_value < self.min_x:
            return
        for creature in target or []:
            if game.on_battlefield(creature) and creature.counters.get(self.counter):
                game.put_counters(creature, self.counter, creature.counters[self.counter])


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
class ReturnTransformed:
    """Exile this Saga, then return it to the battlefield transformed under your control; or, when this creature dies, return it
    to the battlefield (tapped) transformed under its owner's control."""
    dies: bool = False
    tapped: bool = False
    end_step: bool = False  # ... at the beginning of the next end step (Loyal Cathar)

    @property
    def uses_source(self) -> bool:
        return not self.dies

    @property
    def uses_dead_source(self) -> bool:
        return self.dies

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        if self.dies and self.end_step:
            fire_turn = game.turn + 1 if game.step in ("end", "cleanup") else game.turn
            game.at_end_step.append((fire_turn, lambda: game.return_dead_to_battlefield(
                target, controller, under_owner=True, tapped=self.tapped, transformed=True)))
        elif self.dies:
            game.return_dead_to_battlefield(target, controller, under_owner=True, tapped=self.tapped, transformed=True)
        else:
            game.flicker(target, controller, "now", "battlefield", under_owner=False, transformed=True)


@dataclass(frozen=True)
class ReturnSelfAsEnchantment:
    """The Enduring cycle: "When this creature dies, if it was a creature, return it to the battlefield under its owner's control.
    It's an enchantment." (not a creature any more, so it can't die this way again)"""
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_dead_to_battlefield(target, controller, under_owner=True, enchantment=True)


@dataclass(frozen=True)
class AddDevotionMana:
    """Nyx Lotus: "Choose a color. Add an amount of mana of that color equal to your devotion to that color." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.add_devotion_mana(controller)


@dataclass(frozen=True)
class ImprintFromHand:
    """Chrome Mox: "Imprint \u2014 When this artifact enters, you may exile a nonartifact, nonland card from your hand." The card
    stays with the Mox, whose mana is any of its colors."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.imprint_from_hand(controller, target)


@dataclass(frozen=True)
class LookTopTakeChosen:
    """Herald's Horn, Gathering Stone: "Look at the top card of your library. If it's a creature card of the chosen type, you may
    reveal it and put it into your hand." (the type the source chose as it entered)"""
    creature: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_top_take_chosen(controller, game.resolving_source, self.creature)


@dataclass(frozen=True)
class CreateOneOfTokens:
    """Tireless Provisioner: "Create a Food token or a Treasure token." (you choose)"""
    options: tuple[Card, ...]

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        token = self.options[controller.player.choose(TOKEN_CHOICE_PROMPT, [t.name for t in self.options])]
        game.create_tokens(controller, token, 1)


TOKEN_CHOICE_PROMPT = "Create which token? "


@dataclass(frozen=True)
class TokenOrSelfCopy:
    """Scute Swarm: "Create a 1/1 green Insect creature token. If you control six or more lands, create a token that's a copy of this
    creature instead." """
    token: Card
    lands: int
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and sum("Land" in p.card.type_line for p in controller.battlefield) >= self.lands:
            game.copy_tokens(controller, [target], False, False)
        else:
            game.create_tokens(controller, self.token, 1)


@dataclass(frozen=True)
class Amass:
    """Orcish Bowmasters: "Amass Orcs 1." Put that many +1/+1 counters on an Army you control; without one, create a 0/0 black
    Army creature token first. The Army is also an Orc."""
    count: int
    kind: str = ""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.amass(controller, self.count, self.kind)


@dataclass(frozen=True)
class EachSacrificesOrDiscards:
    """Plaguecrafter: "Each player sacrifices a creature or planeswalker of their choice. Each player who can't discards a card." """
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if not game.sacrifice(seat, self.kind):
                game.discard(seat, 1)


@dataclass(frozen=True)
class ExileTopOfThatPlayerMayCast:
    """Ragavan: "... exile the top card of that player's library. Until end of turn, you may cast that card." (the player dealt damage)"""
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_top_of_other(controller, target)


@dataclass(frozen=True)
class ExileTopOfEachCastFree:
    """Etali, Primal Storm: "exile the top card of each player's library, then you may cast any number of spells from among those
    cards without paying their mana costs." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top_of_each_cast_free(controller)


@dataclass(frozen=True)
class Connive:
    """Ledger Shredder: "this creature connives": draw a card, then discard a card; a nonland card puts a +1/+1 counter on it."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.connive(controller, target)


@dataclass(frozen=True)
class PutFromHand:
    """ "You may put a creature card from your hand onto the battlefield." """
    kind: str
    tapped: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.put_from_hand(controller, self.kind, self.tapped)


@dataclass(frozen=True)
class SearchLandWhileBehind:
    """Claim Jumper: "... search your library for a Plains card and put it onto the battlefield tapped. Then if an opponent
    controls more lands than you, repeat this process once." (The "you may" of the trigger covers both searches.)"""
    subtype: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for _ in range(2):
            game.search_for_lands(controller, 1, (self.subtype,), 1, True, False)
            if not game.condition_holds(Condition("opponent_more_lands"), controller):
                break


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
    count: Quantity
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
    count: Quantity
    token: Card
    target: str  # "player" or "opponent"
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.create_tokens(target, self.token, game.amount(self.count))


@dataclass(frozen=True)
class TargetControllerCreatesTokens:
    """Beast Within: "Its controller creates a 3/3 green Beast creature token." """
    count: Quantity
    token: Card
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        owner = getattr(target, "last_controller", None) or getattr(target, "controller", None)  # a permanent, or a countered spell
        if target is not None and owner is not None:
            game.create_tokens(owner, self.token, game.amount(self.count))


TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure",
                oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")


CLUE = Card(name="Clue", type_line="Token Artifact — Clue", oracle_text="{2}, Sacrifice this artifact: Draw a card.")


FOOD = Card(name="Food", type_line="Token Artifact — Food",
            oracle_text="{2}, {T}, Sacrifice this artifact: You gain 3 life.")


FISH = Card(name="Fish", type_line="Token Creature \u2014 Fish", colors=("U",), power="1", toughness="1")


OCTOPUS = Card(name="Octopus", type_line="Token Creature \u2014 Octopus", colors=("U",), power="8", toughness="8")


HEARTWOOD = Card(name="Heartwood", type_line="Token Artifact — Heartwood", oracle_text="{T}: Add {R} or {G}.",
                 colors=("R", "G"))


_NAMED_TOKENS = {"treasure": TREASURE, "clue": CLUE, "food": FOOD, "heartwood": HEARTWOOD}


_COLOR_WORDS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}


_COLOR = r"(?:white|blue|black|red|green)"


_TOKEN_COUNT = _N.replace("|X)", "|X|twice X|half X up|half X down)")  # "Create twice X 1/1 ... tokens" (Pest Infestation)


_CREATURE_TOKEN = re.compile(
    rf"{_TOKEN_COUNT} (\d+|X)/(\d+|X) (colorless|{_COLOR}(?:(?:,? and |, ){_COLOR})*) ((?:[A-Z][\w'-]* )+)(artifact |enchantment )?"
    r"creature tokens?(?: named ([A-Z][\w'-]*))?"  # "named Cadet"
    r"(?: with (?:([a-z ,]+?)(?:,? and |, |$))?(?:\"(.+)\")?)?"  # keywords and/or a quoted ability
)


_NAMED_TOKEN = re.compile(rf"(?i:{_TOKEN_COUNT}) (Treasure|Clue|Food|Heartwood) tokens?")


def _attacker_token(spec: str) -> "AttackerCreatesAttackingToken | None":
    made = _token(spec)
    return AttackerCreatesAttackingToken(made[1]) if made is not None and made[0] == 1 else None


def _token(spec: str) -> tuple[Quantity, Card] | None:
    """Parse "a 1/1 white Soldier creature token with flying" or "two Treasure tokens"."""
    if ", then " in spec:
        return None  # a second step ("..., then populate") isn't part of the token; _clauses splits it off
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
        type_line=f"Token {artifact.capitalize() if artifact else ''}Creature — {subtypes.strip()}",
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
    from .activated import activated_abilities  # the readers of abilities read effects with this module
    from .mana import is_mana_ability
    from .statics import static_abilities
    from .triggers import triggered_abilities

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
    if any(isinstance(e, _PutCountersAndAttach) for e in effects):  # Fractal Harness
        merged_attach: list = []
        for effect in effects:
            if isinstance(effect, _PutCountersAndAttach):
                if not (merged_attach and isinstance(merged_attach[-1], CreateTokens) and merged_attach[-1].count == 1):
                    return None
                merged_attach[-1] = CreateTokenAttachSource(merged_attach[-1].token, (effect.count, effect.counter))
            else:
                merged_attach.append(effect)
        effects = merged_attach
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


@dataclass(frozen=True)
class PutCounterOnHost:
    """Seismic Tutelage: "When this Aura enters, put a +1/+1 counter on enchanted creature." """
    count: int
    counter: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.attached_to is not None:
            game.put_counters(target.attached_to, self.counter, self.count)


@dataclass(frozen=True)
class OthersBecomeAsBigAsSource:
    """Tanazir Quandrix: "... the base power and toughness of other creatures you control become equal to Tanazir
    Quandrix's power and toughness until end of turn." """
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        size = (game.power(target), game.toughness(target) or 0)
        for permanent in controller.battlefield:
            if permanent is not target and "Creature" in permanent.card.type_line:
                game.modify_until_end_of_turn(permanent, Modifier(set_pt=size))


@dataclass(frozen=True)
class DrawHalfLibraryLoseHalfLife:
    """Peer into the Abyss: "Target player draws cards equal to half the number of cards in their library and loses half
    their life. Round up each time." """
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.draw(target, (len(target.library) + 1) // 2)
            TargetLoseHalfLife("player", True).resolve(game, controller, target)


@dataclass(frozen=True)
class LoseAllButOneLife:
    """Soulgorger Orgg: "You lose all but 1 life." The source remembers how much."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        lost = max(0, controller.life - 1)
        if target is not None:
            target.stored = lost
        game.change_life(controller, -lost)


@dataclass(frozen=True)
class GainLifeItLost:
    """Soulgorger Orgg: "you gain life equal to the life you lost when it entered." """
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.stored:
            game.change_life(controller, target.stored)


@dataclass(frozen=True)
class ReturnDeadAtNextUpkeep:
    """Phytotitan: "When this creature dies, return it to the battlefield tapped under its owner's control at the beginning of
    their next upkeep." The card is in the graveyard when this resolves."""
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_at_next_upkeep(target)


@dataclass(frozen=True)
class PutCreatureFromHand:
    """Flash: "You may put a creature card from your hand onto the battlefield. If you do, sacrifice it unless you pay its
    mana cost reduced by {2}." """
    reduction: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.put_creature_from_hand(controller, self.reduction)


@dataclass(frozen=True)
class MillThenReturn:
    """ "Mill four cards, then return a creature card (and a land card) from your graveyard to your hand / the battlefield
    (tapped)." The player picks each card among those in the graveyard, including what was just milled."""
    count: Quantity
    kinds: tuple[str, ...]
    to: str  # "hand" or "battlefield"
    tapped: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.mill_then_return(controller, game.amount(self.count), self.kinds, self.to, self.tapped)


@dataclass(frozen=True)
class EachOpponentGetsGoadedCopy:
    """Life of the Party: "each opponent creates a token that's a copy of it. The tokens are goaded for the rest of the
    game." """
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.goaded_copies_for_opponents(controller, target)


@dataclass(frozen=True)
class CopiesOfAnotherCreature:
    """Orthion, Tempestra: "Create a token that's a copy of another target creature you control. It gains haste.
    Sacrifice it at the beginning of the next end step." (`count` tokens; `not_legendary` for Tempestra)"""
    count: int | str = 1
    not_legendary: bool = False
    target: str = "creature you control"
    exile: bool = False  # Rionya: "Exile them at the beginning of the next end step." instead of sacrificing them
    another = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copies_of_creature(controller, target, game.amount(self.count), self.not_legendary, self.exile)


@dataclass(frozen=True)
class PilesOfFour:
    """Abstract Performance: exile the top four cards face down and the next four face up; an opponent chooses one pile to
    put into your graveyard; you may cast a spell from the other for free and put the rest into your hand."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.choose_piles(controller)


@dataclass(frozen=True)
class PastOrPresentVote:
    """Fateful Tempest: each player votes for past or present. You mill a card for each past vote, then it deals damage to each
    opponent equal to the total mana value of the cards milled; you exile the top card for each present vote and may play
    those cards until the end of your next turn."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        past, present = game.vote(controller, ["past", "present"])
        milled = sum(int(card.cmc) for card in game.mill(controller, past))
        if milled:
            for opponent in game.opponents(controller):
                game.damage(opponent, milled)
        if present:
            game.exile_top(controller, present, "next turn")


@dataclass(frozen=True)
class SurgeToVictory:
    """ "Exile target instant or sorcery card from your graveyard. Creatures you control get +X/+0 until end of turn, where X
    is that card's mana value. Whenever a creature you control deals combat damage to a player this turn, copy the exiled
    card. You may cast the copy without paying its mana cost." """
    target: str = "graveyard:instant or sorcery:yours"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or not game.exile_from_graveyard(target):
            return
        card = target.card
        for permanent in controller.battlefield:
            if "Creature" in permanent.card.type_line:
                game.modify_until_end_of_turn(permanent, Modifier(int(card.cmc), 0))
        controller.surge = (game.turn, card)


@dataclass(frozen=True)
class CastExiledCopy:
    """The delayed trigger of Surge to Victory: cast a copy of the exiled card without paying its mana cost."""
    card: Card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.cast_copy_free(controller, self.card)


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


@dataclass(frozen=True)
class GiveBack:
    """ "For each creature destroyed this way, its controller creates a 1/1 white Spirit creature token." Only ever the
    end of a DestroyAll or ExileAll (see _merge_wipe_gift). Ceaseless Conflict pays only the caster, for their own
    nontoken creatures; Oversimplify gives each player one token with a counter per point of power they lost."""
    count: Quantity
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
    (re.compile(r"your devotion to (white|blue|black|red|green)", re.I), lambda m: Amount("devotion", _COLOR_LETTER[m[1].lower()])),
    (re.compile(r"the tapped creature's power", re.I), lambda m: Amount("tapped_power")),
    (re.compile(r"(?:the number of )?Auras? you controlled that was attached to it", re.I), lambda m: Amount("auras_on_subject")),
    (re.compile(r"(?:the number of )?Auras? you control that's attached to a creature", re.I),
     lambda m: Amount("auras_on_creatures")),
    (re.compile(r"the number of nontoken creatures you had enter the battlefield under your control this turn", re.I),
     lambda m: Amount("creatures_entered")),
    (re.compile(r"(?:the number of )?([+\-\u2212]1/[+\-\u2212]1|[a-z]+) counters? on (?:it|this creature|this artifact|this enchantment|CARDNAME)",
                re.I), lambda m: Amount("source_counters", _counter_name(m[1].lower()))),
    (re.compile(r"(?:the number of )?(?:(creature|land|artifact|enchantment|instant|sorcery|planeswalker) )?cards? in your graveyard",
                re.I), lambda m: Amount("graveyard", (m[1] or "card").lower())),
    (re.compile(r"(?:the number of )?creatures? on the battlefield", re.I), lambda m: Amount("on_battlefield", "creature")),
    (re.compile(r"(?:the number of )?creatures? that died under your control this turn", re.I), lambda m: Amount("creatures_died")),
    (re.compile(r"the amount of life you gained this turn", re.I), lambda m: Amount("life_gained")),
    (re.compile(r"the amount of life you lost this turn", re.I), lambda m: Amount("life_lost")),
    (re.compile(r"half your life total, rounded (down|up)", re.I), lambda m: Amount("half_life", m[1].lower())),
    (re.compile(r"(?:the number of )?spells? you've cast this turn", re.I), lambda m: Amount("spells_cast")),
    (re.compile(r"the greatest power among ((?:other )?(?:non-[A-Za-z]+ )?[A-Za-z]+s) you control", re.I),
     lambda m: Amount("greatest_power", m[1][:-1])),  # "creatures", "other creatures", "non-Human creatures", "Giants"
    (re.compile(r"the greatest mana value among instant and sorcery spells you've cast this turn", re.I),
     lambda m: Amount("greatest_mana_value_cast", "instant or sorcery spell")),
    (re.compile(r"opponents?", re.I), lambda m: Amount("opponents")),
    (re.compile(r"the amount of mana spent to cast that spell", re.I), lambda m: Amount("mana_spent")),
    (re.compile(r"that spell's mana value", re.I), lambda m: Amount("spell_mana_value")),
    (re.compile(r"the number of cards in your hand", re.I), lambda m: Amount("hand_size")),
    (re.compile(r"the number of cards in (?:that player's|their) hand minus (\d+)", re.I),
     lambda m: Amount("player_hand_minus", m[1])),
    (re.compile(r"the number of cards in (?:that player's|their) hand", re.I), lambda m: Amount("player_hand")),
    (re.compile(r"the number of colors that spell is", re.I), lambda m: Amount("spell_colors")),
    (re.compile(r"the number of cards in all graveyards with the same name as that spell", re.I),
     lambda m: Amount("graveyards_same_name")),
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
class EachSacrificesThenReturn:
    """Deadly Brew: "Each player sacrifices a creature or planeswalker of their choice. If you sacrificed a permanent this way, you
    may return another permanent card from your graveyard to your hand." """
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        mine: list = []
        for seat in game.turn_order_from_active():
            gone = game.sacrifice(seat, self.kind)
            if seat is controller:
                mine = gone
        if mine:
            game.may_return_permanent_card(controller, [p.card for p in mine])


@dataclass(frozen=True)
class PlayersLoseSacrificeAddManaDraw:
    """Priest of Forgotten Gods: "Any number of target players each lose 2 life and sacrifice a creature of their choice. You add {B}{B}
    and draw a card." """
    life: int
    units: tuple[frozenset[str], ...]
    target: str = "player"
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in target or []:
            if not seat.lost:
                game.change_life(seat, -self.life)
                game.sacrifice(seat, "creature")
        game.add_mana(controller, self.units)
        game.draw(controller, 1)


_CONTRACT_BODY = "it gets +2/+0 until end of turn if it's attacking one of your opponents. Otherwise, its controller loses 2 life."


CONTRACT_TEXT = ("Enchant creature\nWhenever enchanted creature attacks, it gets +2/+0 until end of turn if it's attacking one of your "
                 "opponents. Otherwise, its controller loses 2 life.")


@dataclass(frozen=True)
class CreateContract:
    """Scriv, the Obligator: "Whenever Scriv enters or attacks, create a white Aura enchantment token named Contract attached to
    target creature an opponent controls. The token has enchant creature and "Whenever enchanted creature attacks, ..."" """
    target: str = "creature an opponent controls"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.on_battlefield(target):
            token = Card(name="Contract", type_line="Token Enchantment \u2014 Aura", colors=("W",), oracle_text=CONTRACT_TEXT)
            game.create_attached_token(controller, token, target)


@dataclass(frozen=True)
class ContractAttack:
    """Contract: "it gets +2/+0 until end of turn if it's attacking one of your opponents. Otherwise, its controller loses 2 life."
    The enchanted creature is the subject; the trigger's X is the seat it attacks."""
    uses_subject = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if target is None or item is None:
            return
        if game.seats[item.x] is not controller:
            game.modify_until_end_of_turn(target, Modifier(2, 0))
        else:
            game.change_life(game.controller(target), -2)


@dataclass(frozen=True)
class PhaseOut:
    """Guardian of Faith: "any number of other target creatures you control phase out." They (and what is attached to them) are treated
    as though they don't exist until their controller's next untap step."""
    target: str = "creature you control"
    another = True
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for creature in target or []:
            game.phase_out(creature)


@dataclass(frozen=True)
class TragicArrogance:
    """Tragic Arrogance: "For each player, you choose from among the permanents that player controls an artifact, a creature, an
    enchantment, and a planeswalker. Then each player sacrifices all other nonland permanents they control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tragic_arrogance(controller)


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
    greatest: bool = False  # "a creature with the greatest power among creatures they control" (Consumed by Greed)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.sacrifice(target, self.kind, greatest=self.greatest)


_MASS_KINDS = {"battles": "battle", "creatures": "creature", "creature tokens": "creature", "artifacts": "artifact", "enchantments": "enchantment",
               "planeswalkers": "planeswalker", "lands": "land", "nonland permanents": "nonland permanent",
               "artifacts and enchantments": "artifact or enchantment",
               "creatures and planeswalkers": "creature or planeswalker"}


_MASS = (r"(battles|artifacts and enchantments|creatures and planeswalkers|nonland permanents|creatures|artifacts"
         r"|enchantments|planeswalkers|lands)( you don't control| you control| an opponent controls| your opponents control)?")


def _mass_kind(m: re.Match) -> str:
    return _MASS_KINDS[m[1].lower()] + (m[2] or "").replace(" your opponents control", " an opponent controls")


_SACRIFICE_KIND = (r"(attacking creature|tapped creature|untapped creature|nontoken creature|creature or planeswalker|creature|artifact or enchantment|nontoken artifact|food|treasure|clue|artifact"
                   r"|enchantment|land|nonland permanent|permanent)")


_FIGHTER = r"(creature(?: you control| you don't control| an opponent controls)?)"


_MASS_KEYWORDS = (r"(?:flying|reach|trample|haste|vigilance|menace|deathtouch|lifelink|first strike|double strike"
                  r"|defender|indestructible|hexproof)")


_RESTRICTION = rf"(with (?:power|toughness|mana value) \d+ or (?:greater|less)|with {_MASS_KEYWORDS}|without {_MASS_KEYWORDS})"


_COLOR_ADJECTIVE = r"(?:(non)?(white|blue|black|red|green|token|legendary|basic|tapped|untapped|attacking) )?"


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


_TRAITS = {"token": "token", "legendary": "legendary", "basic": "basic", "tapped": "tapped", "untapped": "tapped", "attacking": "attacking"}


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
        if target is None:
            return
        if hasattr(target, "physical"):  # Sink into Stupor: a spell on the stack
            ReturnSpellToHand().resolve(game, controller, target)
        else:
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
    finality: bool = False  # Excava: "with a finality counter on it. It's a 1/1 Spirit creature with flying in addition ..."
    another: bool = False  # Myr Retriever: "another target artifact card": not this creature's own card, now in the graveyard
    counter: str = ""  # Season of the Burrow: "... to the battlefield with an indestructible counter on it"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_from_graveyard(target, controller, self.to, self.tapped, self.finality, counter=self.counter)


@dataclass(frozen=True)
class DamageTargetsController:
    """Blooming Blast: "... also deals 3 damage to that creature's controller." (the creature the effect before it targeted)"""
    amount: int
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        owner = game.controller_of(target) if target is not None else None
        if owner is not None:
            game.damage(owner, self.amount, source=game.resolving_source)


@dataclass(frozen=True)
class LoseLifeEqualToManaValue:
    """Reanimate: "You lose life equal to its mana value." (the card the previous effect put onto the battlefield)"""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(controller, -int(target.card.cmc))


@dataclass(frozen=True)
class ShuffleIntoLibrary:
    """Perpetual Timepiece: "Shuffle any number of target cards from your graveyard into your library." Quandrix Command: "Target
    player shuffles up to three target cards from their graveyard into their library." (always you, and your graveyard)"""
    target: str = "graveyard:card:yours"
    max_targets: int = 0  # "up to three"
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
class _ItGains:
    """ "It gains trample until end of turn.": the creature that just got counters, or else the source itself."""
    keywords: frozenset[str]


@dataclass(frozen=True)
class _ThatAlsoGains:
    """ "That creature also gains indestructible until end of turn.": the creature a pump just gave +2/+2 (see _merge_three_way)."""
    keywords: frozenset[str]


@dataclass(frozen=True)
class _TheyGain:
    """ "Those creatures gain flying until end of turn." / "They gain trample ..." after counters on several creatures."""
    keywords: frozenset[str]


@dataclass(frozen=True)
class CopySelfToken:
    """Leitmotif Composer: "Create a token that's a copy of this creature." Offspring: "create a 1/1 token copy of it"."""
    one_by_one: bool = False  # CR 702.175a: the copy is 1/1 instead of the printed size
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            card = target.card if target.card.type_line.startswith("Token") else \
                dataclasses.replace(target.card, type_line="Token " + target.card.type_line)
            if self.one_by_one:
                card = dataclasses.replace(card, power="1", toughness="1")
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
class CreateTokenAttachSource:
    """Fractal Harness: "Create a 0/0 ... Fractal creature token. Put X +1/+1 counters on it and attach this Equipment to it." """
    token: Card
    counters: tuple[int | str, str]
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for made in game.create_tokens(controller, self.token, 1, (game.amount(self.counters[0]), self.counters[1])):
            if target is not None:
                game.attach(target, made)


@dataclass(frozen=True)
class _PutCountersAndAttach:
    """The second sentence of Fractal Harness: "Put X +1/+1 counters on it and attach this Equipment to it." """
    count: int | str
    counter: str


@dataclass(frozen=True)
class CreateTokenWithGraveyardAttachment:
    """Forum Filibuster: "Create a 2/1 ... token. When you do, return up to one target Aura or Equipment card from your
    graveyard to the battlefield attached to that token." (chosen as it resolves rather than targeted)"""
    token: Card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for made in game.create_tokens(controller, self.token, 1):
            game.return_attachment_to(controller, made)


@dataclass(frozen=True)
class _RecallAttachment:
    """The "When you do, return up to one target Aura or Equipment card from your graveyard to the battlefield attached to
    that token." sentence; only ever the second step of a CreateTokenWithGraveyardAttachment (see _merge_conditional)."""


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
        carried = item.carried if item is not None else None
        cards = carried if isinstance(carried, tuple) else (carried,)  # "one of them" when several were discarded together
        options = [c for c in cards if isinstance(c, Card) and any(g is c for g in controller.graveyard)]
        if not options:
            return
        card = options[0]
        if len(options) > 1:
            card = options[controller.player.choose(EXILE_DISCARDED_PROMPT, [c.name for c in options])]
        game.exile_card_from_graveyard(controller, card, play_this_turn=self.play)


@dataclass(frozen=True)
class MayCopyLeftCard:
    """Spirit of Resilience: "... you may have this creature become a copy of an artifact or creature card from among those
    cards until end of turn." (the cards that left the graveyard ride along with the trigger)"""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        carried = item.carried if item is not None else None
        options = [c for c in (carried if isinstance(carried, tuple) else ())
                   if "Creature" in c.type_line or "Artifact" in c.type_line]
        if target is None or not options:
            return
        game.may_become_copy(controller, target, options)


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
class _ExileTokenAtEnd:
    """ "Exile that token at the beginning of the next end step." after a token was created (see _merge_conditional)."""


@dataclass(frozen=True)
class _InsteadTokens:
    """ "If that spell's mana value is 5 or greater, create three of those tokens instead." (see _merge_conditional)"""
    condition: "Condition"
    count: Quantity


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
    return _IfYouDo(inner[0]) if inner and len(inner) == 1 and isinstance(inner[0], (BecomePrepared, SearchForLands)) else None


def _then_if(m: re.Match) -> Any:
    condition = _condition(m[1])
    inner = _parse([m[2][:1].upper() + m[2][1:] + "."]) if condition else None
    if condition is None or not inner or len(inner) != 1 or target_kind(inner[0]):
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
        elif isinstance(effect, _InsteadMana):
            if not (merged and isinstance(merged[-1], AddMana)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], more=effect.units, more_if=effect.condition)
        elif isinstance(effect, _ExileTokenAtEnd):
            if not (merged and isinstance(merged[-1], CreateTokens)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], exile_at_end=True)
        elif isinstance(effect, _InsteadTokens):
            if not (merged and isinstance(merged[-1], CreateTokens)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], more=effect.count, more_if=effect.condition)
        elif isinstance(effect, _UntapThoseLands):
            if not (merged and isinstance(merged[-1], RevealLands)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], untap_if=effect.condition)
        elif isinstance(effect, _UntapThatLand):
            if not (merged and isinstance(merged[-1], FetchBasicLand)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], untap_if=effect.condition)
        elif isinstance(effect, _ManaForEachDestroyed):
            if not (merged and isinstance(merged[-1], DestroyAll)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], mana_each=effect.options)
        elif isinstance(effect, Fight) and effect.optional_target:  # "Then it fights ...": it is the creature just pumped
            if not (merged and isinstance(merged[-1], (PumpX, DoubleStats))):
                return None
            merged.append(effect)
        elif isinstance(effect, _PutFromAmongThem):
            if not (merged and isinstance(merged[-1], Mill)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], put=effect.kind)
        elif isinstance(effect, _ItGains):
            if merged and isinstance(merged[-1], PutCounters) and not merged[-1].grant:
                merged[-1] = dataclasses.replace(merged[-1], grant=effect.keywords)
            else:
                merged.append(PumpSource(Modifier(keywords=effect.keywords)))
        elif isinstance(effect, _ThatAlsoGains):
            if not (merged and isinstance(merged[-1], Pump)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], modifier=dataclasses.replace(
                merged[-1].modifier, keywords=merged[-1].modifier.keywords | effect.keywords))
        elif isinstance(effect, _TheyGain):
            if not (merged and isinstance(merged[-1], (PutCountersOnEach, PutCountersOnEachUpToX))):
                return None
            merged[-1] = dataclasses.replace(merged[-1], grant=effect.keywords)
        elif isinstance(effect, _RecallAttachment):
            if not (merged and isinstance(merged[-1], CreateTokens) and merged[-1].count == 1):
                return None
            merged[-1] = CreateTokenWithGraveyardAttachment(merged[-1].token)
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
    count: int | str  # up to this many ("X")
    subtypes: tuple[str, ...]  # () means basic lands; otherwise lands with one of these land types
    battlefield: int | str  # how many go onto the battlefield (the rest go to the hand); "X": all of them
    tapped: bool
    reveal: bool
    basic_only: bool = False  # "basic Plains cards": the land types and also basic
    share_type: bool = False  # "that share a land type"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = game.amount(self.count)  # Traverse the Outlands: up to X
        game.search_for_lands(controller, count, self.subtypes, count if self.battlefield == "X" else game.amount(self.battlefield), self.tapped,
                              self.reveal, self.basic_only, self.share_type)


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
class RevealLands:
    """Animist's Awakening: "Reveal the top X cards of your library. Put all land cards from among them onto the battlefield tapped
    and the rest on the bottom of your library in a random order." Open the Way (`until_lands`): "Reveal cards from the top of your
    library until you reveal X land cards. Put those land cards ..." Spell mastery (`untap_if`): "... untap those lands." """
    count: int | str
    until_lands: bool = False
    untap_if: "Condition | None" = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.reveal_lands(controller, game.amount(self.count), self.until_lands, self.untap_if)


@dataclass(frozen=True)
class _UntapThoseLands:
    """Spell mastery: "If there are two or more instant and/or sorcery cards in your graveyard, untap those lands." """
    condition: "Condition"


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
    more: tuple[frozenset[str], ...] = ()  # Cabal Ritual: "Threshold — Add {B}{B}{B}{B}{B} instead if there are seven or more cards in your graveyard."
    more_if: "Condition | None" = None
    per_named: frozenset[str] = frozenset()  # Rite of Flame: one more of these for each card with this spell's name in a graveyard

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        units = self.more if self.more_if and game.condition_holds(self.more_if, controller, game.resolving_source) else self.units
        if self.per_named and game.resolving_item is not None:
            named = sum(c.name == game.resolving_item.card.name for s in game.seats for c in s.graveyard)
            units = units + (self.per_named,) * named
        game.add_mana(controller, units)


@dataclass(frozen=True)
class _InsteadMana:
    """ "Threshold — Add {B}{B}{B}{B}{B} instead if there are seven or more cards in your graveyard." (see _merge_conditional)"""
    condition: "Condition"
    units: tuple[frozenset[str], ...]


@dataclass(frozen=True)
class LookAtHand:
    """Gitaxian Probe: "Look at target player's hand." Only its controller learns anything."""
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            controller.player.notify({"event": "hand", "seat": target.index, "cards": [c.name for c in target.hand]})


@dataclass(frozen=True)
class CommanderToHand:
    """Command Beacon: "Put your commander into your hand from the command zone." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        options = list(controller.command_zone)
        if options:
            chosen = options[controller.player.choose(COMMANDER_HAND_PROMPT, [c.name for c in options])] if len(options) > 1 else options[0]
            controller.command_zone.remove(chosen)
            controller.hand.append(chosen)
            game.broadcast({"event": "from_command_zone", "seat": controller.index, "card": chosen.name})


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
    targets for the copy." (see Game._cast). Thunderclap Drake copies it once for each time you've cast your commander from
    the command zone this game instead (`per_commander_cast`)."""
    per_commander_cast: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.copy_next_turn = game.turn
        controller.copy_next_per_commander = self.per_commander_cast


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
class CopyTriggeringAbility:
    """Unbound Flourishing: "... activate an ability, if that ability's activation cost contains {X}, copy that ability. You may
    choose new targets for the copy." The ability that set the trigger off is `carried`."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        ability = game.resolving_item.carried if game.resolving_item is not None else None
        if ability is not None:
            game.copy_ability(ability, controller)


@dataclass(frozen=True)
class DoubleXOfTriggeringSpell:
    """Unbound Flourishing: "Whenever you cast a permanent spell with a mana cost that contains {X}, double the value of X." The
    spell that set the trigger off is `carried`; it is still on the stack, so what it enters with is doubled."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        spell = game.resolving_item.carried if game.resolving_item is not None else None
        if spell is not None and spell in game.stack:
            spell.x *= 2


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
class GainsAbility:
    """Urza's Saga: 'This Saga gains "{T}: Add {C}."' For as long as it stays on the battlefield its text has the line, as a Class's
    does once it levels up (the card it really is waits in `real_card` until it leaves)."""
    line: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_source
        if source is not None and game.on_battlefield(source):
            source.real_card = source.real_card or source.card
            made = re.match(r"\{T\}: Add ((?:\{[WUBRGC]\})+)\.", self.line)  # a land is told what it makes by its data
            produced = source.card.produced_mana + tuple(s for s in re.findall(r"[WUBRGC]", made[1]) if s not in source.card.produced_mana) if made \
                else source.card.produced_mana
            source.card = dataclasses.replace(source.card, oracle_text=f"{source.card.oracle_text}\n{self.line}", produced_mana=produced)


@dataclass(frozen=True)
class SylvanLibrary:
    """Sylvan Library: "you may draw two additional cards. If you do, choose two cards in your hand drawn this turn. For each of
    those cards, pay 4 life or put the card on top of your library." """
    life: int = 4

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.sylvan_library(controller, self.life)


@dataclass(frozen=True)
class PlayerProtection:
    """The One Ring: "You gain protection from everything until your next turn." Nothing can target you and all damage to you is
    prevented, until your next turn begins."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.protected = True
        game.broadcast({"event": "protected", "seat": controller.index})


@dataclass(frozen=True)
class TargetControllerGainsLife:
    """Nature's Claim: "Its controller gains 4 life." """
    amount: int
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        owner = getattr(target, "last_controller", None) or getattr(target, "controller", None)
        if owner is not None:
            game.change_life(owner, self.amount)


@dataclass(frozen=True)
class LifeLocked:
    """Teferi's Protection: "Your life total can't change" until your next turn: no life is gained or lost."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.life_locked = True


@dataclass(frozen=True)
class PhaseOutAll:
    """Teferi's Protection: "All permanents you control phase out." (They come back at your next untap step.)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            game.phase_out(permanent)


@dataclass(frozen=True)
class ExileThisSpell:
    """ "Exile CARDNAME." as a sentence of the spell: it is exiled, not put into the graveyard, when it has resolved."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.exile_after = True


@dataclass(frozen=True)
class ShuffleThisSpell:
    """Green Sun's Zenith: "Shuffle CARDNAME into its owner's library." once it has resolved."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.shuffle_after = True


@dataclass(frozen=True)
class ExtraLandDrop:
    """Explore: "You may play an additional land this turn." """
    count: int = 1

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if controller.extra_lands_turn != game.turn:
            controller.extra_lands, controller.extra_lands_turn = 0, game.turn
        controller.extra_lands += self.count


@dataclass(frozen=True)
class OpponentsCantCast:
    """Silence: "Your opponents can't cast spells this turn." (Ranger-Captain of Eos: "... noncreature spells ...")"""
    kind: str = ""  # "" for any spell, "noncreature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for opponent in game.opponents(controller):
            opponent.cast_barred = (game.turn, self.kind)


@dataclass(frozen=True)
class ReturnSpellToHand:
    """Reprieve: "Return target spell to its owner's hand." (the spell does not resolve)"""
    target: str = "spell"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target in game.stack:
            game.stack.remove(target)
            if not target.is_copy:
                game._move_card(target.controller, target.physical, "hand")


@dataclass(frozen=True)
class SearchMany:
    """Buried Alive: "Search your library for up to three creature cards, put them into your graveyard, then shuffle." """
    card_type: str
    count: int
    to: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tutor(controller, self.card_type, self.to, False, self.count)


@dataclass(frozen=True)
class EachDrawsThenDiscards:
    """Geier Reach Sanitarium: "Each player draws a card, then discards a card." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            game.draw(seat, 1)
            game.discard(seat, 1)


@dataclass(frozen=True)
class Tap:
    """ "Tap two target permanents.": one effect per target, each a different permanent."""
    target: str
    distinct: bool = False
    optional_target: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)


@dataclass(frozen=True)
class LureThisTurn:
    """Roar of Challenge: "All creatures able to block target creature this turn do so." """
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.lured_turn = game.turn


@dataclass(frozen=True)
class MustBlockThisTurn:
    """ "Target creature blocks this turn if able." / "... blocks this creature this turn if able." (Torchling: that creature in
    particular, the source of the ability)"""
    target: str = "creature"
    source_only: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.must_block_turn = game.turn
            target.must_block_what = game.resolving_source if self.source_only else None


@dataclass(frozen=True)
class PutStunOnSource:
    """ "Put three stun counters on it." in a trigger of the creature itself (Pugnacious Hammerskull, Ambling Stormshell)."""
    count: int | str = 1
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, "stun", game.amount(self.count))


@dataclass(frozen=True)
class PutStunCounters:
    """ "Put a stun counter on it." / "... on that creature.": the target of the effect before it."""
    count: int | str = 1
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, "stun", game.amount(self.count))


@dataclass(frozen=True)
class PutStunOnEach:
    """ "Put a stun counter on each of them." after "Tap up to two target creatures.": _merge_stun puts a stun counter after
    each tap, so this is never resolved itself."""
    count: int | str = 1

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class TapThat:
    """ "Tap it." / "Tap that creature.": the target of the effect before it."""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)


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
class PowerDamageToEachOther:
    """Chandra's Ignition: "Target creature you control deals damage equal to its power to each other creature and each
    opponent." (the creature is the one FightFirst remembered)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_item.carried if game.resolving_item is not None else None
        if source is None or not game.on_battlefield(source):
            return
        power = game.power(source)
        hit = [p for seat in game.live_seats() for p in seat.battlefield if "Creature" in p.card.type_line and p is not source]
        for victim in [*hit, *game.opponents(controller)]:
            game.damage(victim, power, source=source)


@dataclass(frozen=True)
class ReturnWithCounter:
    """Persist and undying: the creature that died comes back with a counter on it. With no counter and `tapped`, Malakir Rebirth's
    "return it to the battlefield tapped under its owner's control"."""
    counter: str = ""  # "-1/-1" (persist) or "+1/+1" (undying)
    tapped: bool = False
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_with_counter(target, self.counter, self.tapped)


@dataclass(frozen=True)
class ChooseTarget:
    """Malakir Rebirth: "Choose target creature." The sentences after it say "that creature"."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class ReturnWhenItDiesThisTurn:
    """Malakir Rebirth: 'Until end of turn, that creature gains "When this creature dies, return it to the battlefield tapped under its
    owner's control."' (the game puts that trigger on the stack if the creature dies this turn)"""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.returns_when_dies = game.turn


@dataclass(frozen=True)
class SacrificeToReturnChosen:
    """Victimize: "Choose two target creature cards in your graveyard. Sacrifice a creature. If you do, return the chosen cards to the
    battlefield tapped." """
    target: str = "graveyard:creature:yours"
    max_targets: int = 2
    any_number = True
    exact_x = True  # two, not fewer by choice
    multi_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.sacrifice(controller):
            for chosen in list(target or []):
                game.return_from_graveyard(chosen, controller, "battlefield", tapped=True)


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
                game.untap(permanent)


@dataclass(frozen=True)
class Untap:
    """ "Untap target land." """
    target: str
    another: bool = False
    optional_target: bool = False  # "Untap up to two target lands"
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.untap(target)


UNTAP_LANDS_PROMPT = "Untap which land? "
COMMANDER_HAND_PROMPT = "Put which commander into your hand? "


DONE = "Done"


@dataclass(frozen=True)
class UntapLands:
    """ "Untap up to three lands." (Frantic Search, Snap): you choose, not a target."""
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for _ in range(self.count):
            tapped = [p for p in controller.battlefield if p.tapped and "Land" in p.card.type_line]
            if not tapped:
                return
            choice = controller.player.choose(UNTAP_LANDS_PROMPT, [game.label(p) for p in tapped] + [DONE])
            if choice >= len(tapped):
                return
            game.untap(tapped[choice])
            game.broadcast({"event": "untapped", "seat": controller.index, "card": tapped[choice].card.name})


@dataclass(frozen=True)
class UntapSource:
    """ "Untap it" / "Untap this creature": the ability's source (or, in a watching trigger, the permanent that set it off)."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.untap(target)


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
class Transform:
    """ "Transform this creature." A daybound permanent only turns over with the day/night rule (see Game.transform)."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.transform(target)


@dataclass(frozen=True)
class RevealTopToHandDrain:
    """Yuriko: "Reveal the top card of your library and put that card into your hand. Each opponent loses life equal to that card's
    mana value." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if not controller.library:
            return
        card = controller.library.pop(0)
        controller.hand.append(card)
        game.broadcast({"event": "revealed", "seat": controller.index, "card": card.name})
        for opponent in game.opponents(controller):
            game.change_life(opponent, -int(card.cmc))


@dataclass(frozen=True)
class NinjutsuEnter:
    """The effect of Ninjutsu: "Put this card onto the battlefield from your hand tapped and attacking." (the game fills in whom)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.ninjutsu_enter(controller, game.resolving_item)


@dataclass(frozen=True)
class BecomeRenowned:
    """Renown: "... and it becomes renowned." It won't trigger again (the condition "if it isn't renowned")."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.renowned = True


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


@dataclass(frozen=True)
class ExtraMountainMana:
    """Pyre Rhymer's Molten Tide: "Until end of turn, whenever you tap a Mountain for mana, add an additional {R}." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.extra_mountain_mana_turn = game.turn


@dataclass(frozen=True)
class PayLifeForMana:
    """Yavimaya Bloomsage's Channel: "Until end of turn, any time you could activate a mana ability, you may pay 1 life. If
    you do, add {C}." Paying for something uses it automatically, after the mana that costs nothing."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.life_mana_turn = game.turn


@dataclass(frozen=True)
class TapEnchanted:
    """An Aura's "When this Aura enters, tap enchanted creature." (Infinite Coursework adds "It becomes unprepared.")"""
    unprepare: bool = False
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        host = target.attached_to if target is not None else None
        if host is not None and game.on_battlefield(host):
            game.tap(host)
            if self.unprepare:
                game.unprepare(host)


@dataclass(frozen=True)
class Conjure:
    """Alchemy: "Conjure a card named Storm Crow onto the battlefield." The card was looked up when the deck loaded."""
    name: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.conjure(controller, self.name)


@dataclass(frozen=True)
class WhenThatDealsCombatDamage:
    """Stensian Sanguinist: "Whenever that creature deals combat damage to a player this combat, this creature becomes
    prepared." The creature is the last one targeted; the watch lives on this combat, so it ends with it."""
    then: Any
    follows_target = True
    text = "Whenever that creature deals combat damage to a player this combat, this creature becomes prepared."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.resolving_source is not None:
            game.combat.damage_watches.append((target, game.resolving_source, self))


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
    cost_power: bool = False  # Esper Sentinel: "{X}, where X is this creature's power"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        cost = self.cost
        if self.cost_power:
            source = game.resolving_source
            cost = "{%d}" % (game.power(source) if source is not None and game.on_battlefield(source) else 0)
        item = game.resolving_item
        if target is not None and item is not None and game.pays_unless(target, cost, item.card):
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
class LookPutAttachment:
    """Armored Skyhunter: "Look at the top six cards of your library. You may put an Aura or Equipment card from among them
    onto the battlefield. If an Equipment is put onto the battlefield this way, you may attach it to a creature you control.
    Put the rest of those cards on the bottom of your library in a random order." """
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_and_put_attachment(controller, self.count)


@dataclass(frozen=True)
class RevealUntilAura:
    """Songbirds' Blessing: "Reveal cards from the top of your library until you reveal an Aura card. You may put that card
    onto the battlefield. If you don't, put it into your hand. Put the rest on the bottom of your library in a random
    order." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.reveal_until_aura(controller)


@dataclass(frozen=True)
class ExileTopCastAura:
    """Herald of Amity: "Exile the top eight cards of your library. You may cast an Aura spell from among them without paying
    its mana cost. Then put the rest on the bottom of your library in a random order." """
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top_cast_aura(controller, self.count)


@dataclass(frozen=True)
class LookPutPermanents:
    """Ao, the Dawn Sky: "Look at the top seven cards of your library. Put any number of nonland permanent cards with total
    mana value 4 or less from among them onto the battlefield. Put the rest on the bottom of your library in a random
    order." """
    count: int
    total_mv: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_and_put_permanents(controller, self.count, self.total_mv)


@dataclass(frozen=True)
class ExileUntilNonlandCast:
    """Plargg and Nassari: "Each player exiles cards from the top of their library until they exile a nonland card. An
    opponent chooses a nonland card exiled this way. You may cast up to two spells from among the other cards exiled this way
    without paying their mana costs." """
    casts: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_until_nonland_and_cast(controller, self.casts)


@dataclass(frozen=True)
class PutBackTop:
    """ "Look at the top three cards of your library, then put them back in any order. (You may shuffle.)" """
    count: Quantity
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
class SacrificeUnlessPay:
    """Gateway Plaza and the like: "When this land enters, sacrifice it unless you pay {1}." """
    cost: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.on_battlefield(target) and not game.pays_unless(controller, self.cost, target.card):
            game._leave_battlefield(target, "sacrificed")


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


@dataclass(frozen=True)
class IfNotKicked:
    """ "If the gift wasn't promised, you lose 2 life.": the effect happens only if the spell was not kicked (or its gift not promised)."""
    effect: Any

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None and not game.resolving_item.kicked:
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class KickedReplaces:
    """ "If the gift was promised, instead counter target spell.": when kicked (or its gift promised) these effects stand in for the
    effect just before."""
    effects: tuple


_KICKED_INSTEAD = [
    (re.compile(rf"if this spell was kicked, {_SELF} deals {_N} damage instead\.", re.I), "amount"),
    (re.compile(rf"if this spell was kicked, create {_N} of those tokens instead\.", re.I), "count"),
    (re.compile(rf"if this spell was kicked, draw {_N} cards instead\.", re.I), "count"),
]


def _kicked_replaces(rest: str) -> KickedReplaces | None:
    effects = _parse(_split_sentences(rest[:1].upper() + rest[1:]))
    return KickedReplaces(tuple(effects)) if effects else None


def _not_kicked(rest: str) -> IfNotKicked | None:
    effects = _parse([rest[:1].upper() + rest[1:]])
    return IfNotKicked(effects[0]) if effects and len(effects) == 1 else None


def _kicked(m: re.Match) -> IfKicked | None:
    kicker, rest = m[1] or "", m[2]
    sentence = rest[:1].upper() + rest[1:]
    effects = _parse([sentence])
    if not effects and isinstance(also := _template(sentence), _ThatAlsoGains):  # joins the pump before it once kicked
        return IfKicked(also, kicker)
    return IfKicked(effects[0], kicker) if effects else None


def kicked_effects(effects: list | None, kicked: int, kickers: tuple[str, ...] = ()) -> list | None:
    """A spell's effects once it's known whether it was kicked: "If this spell was kicked, ..." effects
    become plain effects, or are dropped. This happens before targets are chosen, so kicked effects can target."""
    if effects is None:
        return None
    result = []
    for effect in effects:
        if isinstance(effect, KickedReplaces):
            if kicked:
                result[-1:] = list(effect.effects)
        elif isinstance(effect, IfNotKicked):
            if not kicked:
                result.append(effect.effect)
        elif isinstance(effect, KickedInstead):
            if kicked:
                result[-1] = replace(result[-1], **{effect.field: effect.value})
        elif isinstance(effect, IfKicked):
            if kicked and (not effect.kicker or effect.kicker in kickers):
                if isinstance(effect.effect, _ThatAlsoGains):
                    result[-1] = replace(result[-1], modifier=replace(result[-1].modifier, keywords=result[-1].modifier.keywords | effect.effect.keywords))
                else:
                    result.append(effect.effect)
        else:
            result.append(effect)
    return result


@dataclass(frozen=True)
class FetchBasicLand:
    untap_if: "Condition | None" = None  # Fabled Passage: "Then if you control four or more lands, untap that land."
    tapped: bool = True  # Prismatic Vista puts it onto the battlefield untapped

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fetch_basic_land(controller, untap_if=self.untap_if, tapped=self.tapped)


_PERMANENT_KIND = (r"((?:forest|island|swamp|mountain|plains|attacking or blocking creature|artifact, enchantment, or nonbasic land|artifact, creature, enchantment, or planeswalker"
                   r"|monocolored permanent|(?:white|blue|black|red|green) permanent|creature token|nontoken creature|attacking creature|tapped creature|untapped creature"
                   r"|non(?:white|blue|black|red|green|artifact) creature|noncreature artifact or noncreature enchantment"
                   r"|noncreature, nonland permanent|nonland, nontoken permanent|non-(?-i:[A-Z][a-z]+) creature|artifact, enchantment, or planeswalker|artifact, creature, or planeswalker|creature|artifact"
                   r"|enchantment|planeswalker|nonland permanent|permanent|nonbasic land|land|artifact or enchantment|artifact or creature"
                   r"|creature or planeswalker|creature or enchantment|(?-i:[A-Z][a-z]+) creature|(?-i:[A-Z][a-z]+)(?= you control))(?: an opponent controls| you don't control| you control| you own| that player controls)?"
                   r"(?: with mana value (?:\d+ or (?:less|greater)|X))?)")


# "up to two target creatures": the plural kinds, and the singular they stand for
_PLURAL_KINDS = {"creatures": "creature", "artifacts": "artifact", "enchantments": "enchantment",
                 "planeswalkers": "planeswalker", "permanents": "permanent", "nonland permanents": "nonland permanent",
                 "creature tokens": "creature token", "lands": "land", "artifacts or enchantments": "artifact or enchantment",
                 "artifacts and/or creatures": "artifact or creature",
                 "artifacts and/or enchantments": "artifact or enchantment"}


_PLURAL_KIND = (r"(creature tokens|nonland permanents|artifacts or enchantments|artifacts and/or enchantments|artifacts and/or creatures|creatures|artifacts|enchantments|planeswalkers"
                r"|permanents|lands)( an opponent controls| you don't control| you control| your opponents control)?")


def _suffix(controller: str | None) -> str:
    """The controller phrase after a plural kind, in the singular form targets are written in."""
    return (controller or "").replace("your opponents control", "an opponent controls")


_UP_TO = r"up to (two|three|four)"


def _up_to(cls: type, m: re.Match, **fixed: Any) -> list:
    """"... up to two target creatures ..." is two effects with one optional, distinct target each."""
    kind = _PLURAL_KINDS[m[2].lower()] + _suffix(m[3])
    return [cls(kind, optional_target=True, distinct=n > 0, **fixed) for n in range(_number(m[1]))]


_DAMAGE_KIND = (r"(any target|target attacking or blocking creature|target creature an opponent controls|target creature|target player|target opponent|target creature or planeswalker"
                r"|target player or planeswalker)")


_RETURN_UP_TO_POWER = re.compile(r"return target nonland permanent card with mana value X or less from your graveyard to the "
                                 r"battlefield, where X is (?:this creature's|CARDNAME's|its) power\.", re.I)


_RETURN_UP_TO_DAMAGE = re.compile(r"return target creature card with mana value X or less from your graveyard to the battlefield, "
                                  r"where X is the amount of damage (?:this creature|CARDNAME) dealt to that player\.", re.I)


_TEMPLATES: list[tuple[re.Pattern, Callable[[re.Match], Any]]] = [
    *[(pattern, lambda m, field=field: KickedInstead(field, _count(m[1]))) for pattern, field in _KICKED_INSTEAD],
    (re.compile(r"if this spell was kicked, instead (.+)", re.I), lambda m: _kicked_replaces(m[1])),
    (re.compile(r"if this spell wasn't kicked, (.+)", re.I), lambda m: _not_kicked(m[1])),
    (re.compile(rf"if this spell was kicked(?: with its ({_MANA_SYMBOLS}) kicker)?, (.+)", re.I), _kicked),
    (re.compile(rf"draw {_N} cards?\.", re.I), lambda m: Draw(_count(m[1]))),
    (re.compile(r"draw an additional card\.", re.I), lambda m: Draw(1)),
    (re.compile(rf"(?:you )?gain {_N} life\.", re.I), lambda m: GainLife(_count(m[1]))),
    (re.compile(r"exile a nonartifact, nonland card from your hand\.", re.I), lambda m: ImprintFromHand()),
    (re.compile(rf"whenever {_SELF} connives|{_SELF} connives\.", re.I), lambda m: Connive()),
    (re.compile(r"exile the top card of each player's library, then you may cast any number of spells from among those cards without "
                r"paying their mana costs\.", re.I), lambda m: ExileTopOfEachCastFree()),
    (re.compile(r"create a food token or a treasure token\.", re.I), lambda m: CreateOneOfTokens((FOOD, TREASURE))),
    (re.compile(r"create a (\d+)/(\d+) (green|white|blue|black|red) ([A-Z][a-z]+) creature token\. If you control (six|five|seven) or more lands, "
                r"create a token that's a copy of this creature instead\.", re.I),
     lambda m: TokenOrSelfCopy(Card(name=m[4].title(), type_line=f"Token Creature \u2014 {m[4].title()}", power=m[1], toughness=m[2],
                                    colors=(_COLOR_LETTER[m[3].lower()],)), {"five": 5, "six": 6, "seven": 7}[m[5].lower()])),
    (re.compile(r"(?:then )?amass (?:([A-Z][a-z]+) )?(\d+)\.", re.I), lambda m: Amass(int(m[2]), (m[1] or "").rstrip("s"))),
    (re.compile(r"each player sacrifices an? (creature or planeswalker|nontoken creature) of their choice\. Each player who can't discards a "
                r"card\.", re.I), lambda m: EachSacrificesOrDiscards(m[1].lower())),
    (re.compile(r"choose a color\. add an amount of mana of that color equal to your devotion to that color\.", re.I),
     lambda m: AddDevotionMana()),
    (re.compile(r"add one mana of any color\.", re.I), lambda m: AddMana((frozenset("WUBRG"),))),  # Phyrexian Altar, Springleaf Drum
    # the engine keeps one option set per mana, so the three of Lion's Eye Diamond can be spent as different colors
    (re.compile(r"add (two|three|four|five) mana of any one color\.", re.I), lambda m: AddMana((frozenset("WUBRG"),) * _ANY_N[m[1].lower()])),
    (re.compile(rf"each opponent loses {_N} life\.", re.I), lambda m: OpponentsLoseLife(_count(m[1]))),

    (re.compile(rf"{_SELF} deals {_N} damage to you\.", re.I), lambda m: DamageToYou(_count(m[1]))),
    (re.compile(rf"{_SELF} deals {_N} damage to {_DAMAGE_KIND}\.", re.I),
     lambda m: Damage(_count(m[1]), "any" if m[2].lower() == "any target" else m[2].lower().removeprefix("target "))),
    (re.compile(rf"{_SELF} deals {_N} damage to up to one target creature\.", re.I),  # Season of the Bold
     lambda m: Damage(_count(m[1]), "creature", optional_target=True)),
    (re.compile(rf"{_SELF} deals {_N} damage to each of one or two targets\.", re.I),  # Prismari Charm
     lambda m: [Damage(_count(m[1]), "any"), Damage(_count(m[1]), "any", optional_target=True, distinct=True)]),
    (re.compile(rf"{_SELF} deals {_N} damage to each of up to two target creatures and/or planeswalkers\.", re.I),  # Volcanic Salvo
     lambda m: [Damage(_count(m[1]), "creature or planeswalker", optional_target=True),
                Damage(_count(m[1]), "creature or planeswalker", optional_target=True, distinct=True)]),
    (re.compile(rf"{_SELF} deals (\d+) damage divided as you choose among any number of targets\.", re.I),
     lambda m: [Damage(1, "any", optional_target=n > 0) for n in range(int(m[1]))]),  # a point at a time
    (re.compile(rf"tap (two|three) target {_PLURAL_KIND}\.", re.I),
     lambda m: [Tap(_PLURAL_KINDS[m[2].lower()] + _suffix(m[3]), distinct=n > 0) for n in range(_number(m[1]))]),
    (re.compile(rf"destroy (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Destroy(m[2].lower(), bool(m[1]))),
    (re.compile(rf"destroy each {_PERMANENT_KIND}\.", re.I), lambda m: DestroyAll(m[1].lower())),
    (re.compile(r"destroy each artifact, creature, and enchantment with mana value X or less\.", re.I),
     lambda m: DestroyAll("artifact or creature or enchantment", MassFilter(stat="mana_value", at_most="X"))),
    (re.compile(rf"exile each {_PERMANENT_KIND}\.", re.I), lambda m: ExileAll(m[1].lower())),
    (re.compile(rf"return each {_PERMANENT_KIND} to its owner's hand\.", re.I), lambda m: ReturnAllToHand(m[1].lower())),
    (re.compile(rf"destroy {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Destroy, m)),
    (re.compile(rf"destroy (two|three) target {_PLURAL_KIND}\.", re.I),
     lambda m: [Destroy(_PLURAL_KINDS[m[2].lower()] + _suffix(m[3]), distinct=n > 0) for n in range(_number(m[1]))]),
    (re.compile(rf"destroy up to one target {_PERMANENT_KIND}\.", re.I),
     lambda m: Destroy(m[1].lower(), optional_target=True)),
    (re.compile(r"counter target spell if it's (white|blue|black|red|green)\.", re.I),
     lambda m: Counter("spell", if_color=_COLOR_LETTER[m[1].lower()])),
    (re.compile(r"destroy target permanent if it's (white|blue|black|red|green)\.", re.I),
     lambda m: Destroy("permanent", if_color=_COLOR_LETTER[m[1].lower()])),
    (re.compile(r"counter target ((?:noncreature|creature|instant or sorcery|enchantment, instant, or sorcery|artifact or enchantment|artifact|enchantment|white|blue|black|red|green) )?spell"
                rf"(?: with mana value (\d+))?( unless its controller pays ((?:\{{[^}}]+\}})+))?\.", re.I),
     lambda m: Counter(f"{m[1].lower() if m[1] else ''}spell" + (f" with mana value {m[2]}" if m[2] else ""), unless=m[4] or "")),
    (re.compile(r"change the target of target (spell|spell or ability|activated ability) with a single target"
                rf"( unless that spell's controller pays ((?:\{{[^}}]+\}})+))?\.", re.I),
     lambda m: ChangeTarget(f"{m[1].lower()} with a single target", unless=m[3] or "")),
    (re.compile(r"(you may )?change the target of target (instant or sorcery spell) with a single target to (this creature)\.", re.I),
     lambda m: ChangeTarget(f"{m[2].lower()} with a single target", to="this", optional=bool(m[1]))),  # Hydroelectric Specimen
    (re.compile(r"change the target of target (spell or ability|spell) that targets only (a player|a single creature|this creature)( to this creature)?\.", re.I),
     lambda m: ChangeTarget(f"{m[1].lower()} that targets only {m[2].lower()}",
                            to="this" if m[3] else "")),  # Rebound, Muck Drubb, Silver Wyvern, Torchling
    (re.compile(r"the new target must be an? (player|creature)\.", re.I), lambda m: NewTargetMustBe(m[1].lower())),
    (re.compile(r"you may change the targets of target (instant or sorcery spell)\.", re.I),
     lambda m: ChangeTarget(m[1].lower(), every=True)),  # Goblin Flectomancer
    (re.compile(r"change a target of target spell or ability to (this creature)\.", re.I),
     lambda m: ChangeTarget("spell or ability", to="this", lone=False)),  # Spellskite
    (re.compile(r"you may choose new targets for target spell or ability\.", re.I), lambda m: ChangeTarget("spell or ability", every=True)),
    (re.compile(r"return target (spell or nonland permanent an opponent controls) to its owner's hand\.", re.I),
     lambda m: ReturnToHand(m[1].lower())),  # Sink into Stupor
    (re.compile(r"return target spell( you don't control)? to its owner's hand\.", re.I),
     lambda m: ReturnSpellToHand("spell you don't control" if m[1] else "spell")),
    (re.compile(r"its controller gains (\d+) life\.", re.I), lambda m: TargetControllerGainsLife(int(m[1]))),
    (re.compile(r"you may play an additional land this turn\.", re.I), lambda m: ExtraLandDrop()),
    (re.compile(r"your opponents can't cast (noncreature )?spells this turn\.", re.I), lambda m: OpponentsCantCast("noncreature" if m[1] else "")),
    (re.compile(r"search your library for a card, put that card into your graveyard, then shuffle\.", re.I),
     lambda m: SearchLibrary("card", "graveyard", False)),
    (re.compile(r"search your library for up to (two|three|four) ([a-z]+) cards, put them into your graveyard, then shuffle\.", re.I),
     lambda m: SearchMany(m[2].lower(), _number(m[1]), "graveyard")),
    (re.compile(r"each player draws a card, then discards a card\.", re.I), lambda m: EachDrawsThenDiscards()),
    (re.compile(rf"tap (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Tap(m[2].lower(), bool(m[1]))),
    (re.compile(rf"tap {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Tap, m)),
    (re.compile(rf"its controller may draw up to {_N_FIXED} cards at the beginning of the next turn's upkeep\.", re.I),
     lambda m: DelayedDraw(_number(m[1]), True)),
    (re.compile(rf"(?:you )?draw {_N_FIXED} cards? at the beginning of the next turn's upkeep\.", re.I),  # Portent: "Draw a card ..."
     lambda m: DelayedDraw(_number(m[1]), False)),
    (re.compile(r"if that (?:creature|permanent|creature or planeswalker) would die this turn, exile it instead\.", re.I),
     lambda m: ExileTargetIfDies()),
    (re.compile(r"if a creature dealt damage this way would die this turn, exile it instead\.", re.I),
     lambda m: ExileDamagedIfDie()),
    (re.compile(r"exile enchanted creature\.", re.I), lambda m: ExileEnchanted()),
    (re.compile(r"that token gains haste until end of turn\.", re.I), lambda m: _TokenGainsHaste()),
    (re.compile(r"create a token that's a copy of it\.", re.I), lambda m: _CopyOfIt()),
    (re.compile(r"mill a card, then exile a card from your graveyard at random\. you may play the exiled card this turn\.", re.I),
     lambda m: MillThenExileRandomPlay()),
    (re.compile(rf"create a token that's a copy of {_SELF}\.", re.I), lambda m: CopySelfToken()),
    (re.compile(r"exile (?:that card|one of them) from your graveyard\.(?: if you do, you may (?:play|cast) (?:that card|it) this turn\.)?", re.I),
     lambda m: ExileDiscarded(play="you may" in m[0].lower())),
    (re.compile(r"you may have (?:this creature|CARDNAME) become a copy of an artifact or creature card from among those cards "
                r"until end of turn\.", re.I), lambda m: MayCopyLeftCard()),
    (re.compile(r"create Primo, the Indivisible, a legendary 0/0 green and blue Fractal creature token, then put that many "
                r"\+1/\+1 counters on it\.", re.I),
     lambda m: [DefineX(Amount("you_control", "land")),  # "that many": the lands you control
                CreateTokens(1, Card(name="Primo, the Indivisible", type_line="Legendary Token Creature — Fractal",
                                     colors=("G", "U"), power="0", toughness="0"), counters=("X", "+1/+1"))]),
    (re.compile(rf"(?:you )?put {_N} \+1/\+1 counters? on a creature you control\.", re.I),
     lambda m: PutCountersOnChosenCreature(_count(m[1]), "+1/+1")),
    (re.compile(rf"look at the top {_N_FIXED} cards of your library\. you may put an Aura or Equipment card from among them onto the "
                r"battlefield\. If an Equipment is put onto the battlefield this way, you may attach it to a creature you control\. "
                r"Put the rest of those cards on the bottom of your library in a random order\.", re.I),
     lambda m: LookPutAttachment(_number(m[1]))),
    (re.compile(rf"exile the top {_N_FIXED} cards of your library\. You may cast an Aura spell from among them without paying its mana "
                r"cost\. Then put the rest on the bottom of your library in a random order\.", re.I),
     lambda m: ExileTopCastAura(_number(m[1]))),
    (re.compile(rf"look at the top {_N_FIXED} cards of your library\. Put any number of nonland permanent cards with total mana value "
                r"(\d+) or less from among them onto the battlefield\. Put the rest on the bottom of your library in a random order\.",
                re.I), lambda m: LookPutPermanents(_number(m[1]), int(m[2]))),
    (re.compile(rf"put {_N} ([+\-\u2212]1/[+\-\u2212]1) counters? on each permanent you control that's a creature or Vehicle\.", re.I),
     lambda m: PutCountersOnEach(_count(m[1]), _counter_name(m[2]), or_vehicle=True)),
    (re.compile(rf"each player exiles cards from the top of their library until they exile a nonland card\. An opponent chooses a "
                rf"nonland card exiled this way\. You may cast up to {_N_FIXED} spells from among the other cards exiled this way without "
                r"paying their mana costs\.", re.I), lambda m: ExileUntilNonlandCast(_number(m[1]))),
    (re.compile(r"reveal the top X cards of your library\. Put all land cards from among them onto the battlefield tapped and the rest "
                r"on the bottom of your library in a random order\.", re.I), lambda m: RevealLands("X")),
    (re.compile(r"reveal cards from the top of your library until you reveal X land cards\. Put those land cards onto the "
                r"battlefield tapped and the rest on the bottom of your library in a random order\.", re.I),
     lambda m: RevealLands("X", until_lands=True)),
    (re.compile(r"if (there are .+), untap those lands\.", re.I), lambda m: _UntapThoseLands(c) if (c := _condition(m[1])) else None),
    (re.compile(r"reveal cards from the top of your library until you reveal an Aura card\. You may put that card onto the "
                r"battlefield\. If you don't, put it into your hand\. Put the rest on the bottom of your library in a random order\.",
                re.I), lambda m: RevealUntilAura()),
    (re.compile(r"tap up to one target creature and goad it\.", re.I), lambda m: TapAndGoad()),
    (re.compile(r"attach (?:this Aura|CARDNAME) to it\.", re.I), lambda m: AttachThisToSubject()),
    (re.compile(r"if that enchantment is an Aura, you may attach it to the token\.", re.I), lambda m: _AttachItToToken()),
    (re.compile(rf"put {_N} ([+\-\u2212]1/[+\-\u2212]1) counters? on it and attach (?:this Equipment|CARDNAME) to it\.", re.I),
     lambda m: _PutCountersAndAttach(_count(m[1]), _counter_name(m[2]))),
    (re.compile(r"when you do, return up to one target Aura or Equipment card from your graveyard to the battlefield attached to "
                r"that token\.", re.I), lambda m: _RecallAttachment()),
    (re.compile(r"the token created this way gains haste\.", re.I), lambda m: _PopulatedTokenRider(haste=True)),
    (re.compile(r"sacrifice it at the beginning of the next end step\.", re.I), lambda m: _PopulatedTokenRider(sacrifice=True)),
    (re.compile(r'(?:it has|they have) "(.+)"', re.I), lambda m: _ItHas(m[1]) if _is_known_ability(m[1]) else None),
    (re.compile(r"when you next cast an instant or sorcery spell this turn, copy that spell\. You may choose new targets for the "
                r"copy\.", re.I), lambda m: CopyNextSpell()),
    (re.compile(r"when you next cast an instant or sorcery spell this turn, copy it for each time you've cast your commander from "
                r"the command zone this game\. You may choose new targets for the copies\.", re.I),
     lambda m: CopyNextSpell(per_commander_cast=True)),
    (re.compile(rf"(?:then )?put an? {_CARD_TYPE} from among them onto the battlefield\.", re.I),
     lambda m: _PutFromAmongThem(_card_kind(m[1]))),
    (re.compile(rf"(?:those creatures|they(?! gain haste until end of turn\.)) gain {_KEYWORDS} until end of turn\.", re.I), lambda m: _TheyGain(_keyword_list(m[1]))),
    (re.compile(rf"it gains {_KEYWORDS} until end of turn\.", re.I), lambda m: _ItGains(_keyword_list(m[1]))),
    (re.compile(rf"that creature also gains {_KEYWORDS} until end of turn\.", re.I), lambda m: _ThatAlsoGains(_keyword_list(m[1]))),
    (re.compile(r"you may cast spells this turn as though they had flash\.", re.I), lambda m: GrantFlash()),
    (re.compile(rf"if (.+), draw {_N_FIXED} cards instead\.", re.I),
     lambda m: _InsteadDraw(c, _number(m[2])) if (c := _condition(m[1])) else None),
    (re.compile(r"(?:Threshold \u2014 )?add ((?:\{[WUBRGC]\})+) instead if (there are seven or more cards in your graveyard)\.", re.I),
     lambda m: _InsteadMana(c, tuple(frozenset(s) for s in re.findall(r"[WUBRGC]", m[1].upper()))) if (c := _condition(m[2])) else None),
    (re.compile(r"add ((?:\{[WUBRGC]\})+), then add (\{[WUBRGC]\}) for each card named CARDNAME in each graveyard\.", re.I),
     lambda m: AddMana(tuple(frozenset(s) for s in re.findall(r"[WUBRGC]", m[1].upper())), per_named=frozenset(re.findall(r"[WUBRGC]", m[2].upper())))),
    (re.compile(r"look at target (player|opponent)'s hand\.", re.I), lambda m: LookAtHand(m[1].lower())),
    (re.compile(r"put your commander into your hand from the command zone\.", re.I), lambda m: CommanderToHand()),
    (re.compile(r"exile that token at the beginning of the next end step\.", re.I), lambda m: _ExileTokenAtEnd()),
    (re.compile(rf"if (.+), create {_N} of those tokens instead\.", re.I),
     lambda m: _InsteadTokens(c, _count(m[2])) if (c := _condition(m[1])) else None),
    (re.compile(r"then if (.+), untap that land\.", re.I), lambda m: _UntapThatLand(c) if (c := _condition(m[1])) else None),
    (re.compile(r"then if (.+?), ((?!untap that land).+)\.", re.I), _then_if),
    (re.compile(r"if (this spell was foretold), (.+)\.", re.I), _then_if),
    (re.compile(r"if (X is \d+ or more), (?!double the number)(.+)\.", re.I), _then_if),
    (re.compile(rf"if X is {_N} or more, double the number of ([+\-\u2212]1/[+\-\u2212]1) counters on any number of other target "
                r"creatures\.", re.I), lambda m: DoubleCountersOnTargets(_counter_name(m[2]), "creature", int(m[1]))),
    (re.compile(r"destroy up to one target (artifact or enchantment) with mana value X or less\.", re.I),
     lambda m: Destroy(f"{m[1].lower()} with mana value x or less", optional_target=True)),
    (re.compile(rf"exile {_N_FIXED} cards from your graveyard\.", re.I), lambda m: ExileOwnGraveyard(_number(m[1]))),
    (re.compile(r"if you do, (.+)\.", re.I), _if_you_do),
    (re.compile(r'if an? (creature) card is exiled this way, (create .+?)(\."?)', re.I), _if_exiled),
    (re.compile(rf"return (?:CARDNAME|this card) from your graveyard to the battlefield( tapped)?\.", re.I),
     lambda m: ReturnThisFromGraveyard(bool(m[1]))),
    (re.compile(rf"return (?:CARDNAME|this card) from your graveyard to your hand\.", re.I),
     lambda m: ReturnThisFromGraveyard(to="hand")),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Exile(m[2].lower(), bool(m[1]))),
    (re.compile(rf"exile {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Exile, m)),
    (re.compile(rf"destroy X target {_PLURAL_KIND}\.", re.I), lambda m: DestroyX(_PLURAL_KINDS[m[1].lower()] + _suffix(m[2]))),
    (re.compile(rf"exile X target {_PLURAL_KIND}\.", re.I), lambda m: ExileX(_PLURAL_KINDS[m[1].lower()] + _suffix(m[2]))),
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
    (re.compile(r"the exiled card's owner creates an X/X (\w+) (\w+) creature token, where X is the mana value of the exiled card\.", re.I),
     lambda m: ExiledOwnerGetsToken(Card(name=m[2], type_line=f"Token Creature — {m[2]}", power="0", toughness="0",
                                         colors=(_COLOR_WORDS[m[1].lower()],)))),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND} until {_SELF} leaves the battlefield\.", re.I),
     lambda m: ExileUntilLeaves(m[2].lower(), bool(m[1]))),
    (re.compile(rf"target (player|opponent) draws {_N} cards?\.", re.I), lambda m: TargetDraw(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) draws {_N} cards? and loses {_N} life\.", re.I),
     lambda m: TargetDrawLose(_count(m[2]), _count(m[3]), m[1].lower())),
    (re.compile(r"you and target opponent each reveal the top card of your library\. You each lose life equal to the mana value "
                r"of the card revealed by the other player\. You each put the card you revealed into your hand\.", re.I),
     lambda m: RevealTopTradeLife()),
    (re.compile(rf"you and target opponent each draw {_N} cards?\.", re.I), lambda m: YouAndTargetDraw(_count(m[1]))),
    (re.compile(rf"each player loses {_N} life\.", re.I), lambda m: EachPlayerLosesLife(_count(m[1]))),
    (re.compile(r"you may discard a card\.", re.I), lambda m: _MayDiscard()),
    (re.compile(rf"you may sacrifice an? {_SACRIFICE_KIND}\.", re.I), lambda m: _MaySacrifice(m[1].lower())),
    (re.compile(rf"you may remove an? {_COUNTER} from (?:it|{_SELF})\.", re.I), lambda m: _MayRemoveCounter(_counter_name(m[1]))),
    (re.compile(rf"if you do, draw {_N_FIXED} cards?(?:, then mill {_N_FIXED} cards?)?\.", re.I),
     lambda m: _IfYouDoDraw(_number(m[1]), _number(m[2]) if m[2] else 0)),
    (re.compile(r"you gain life equal to the life lost this way\.", re.I), lambda m: _GainLifeLost()),
    (re.compile(r"each player may discard their hand and draw (seven) cards\.", re.I),
     lambda m: EachMayWheel(_number(m[1]))),
    (re.compile(r"you may tap or untap target creature\.", re.I), lambda m: TapOrUntap()),
    (re.compile(rf"target (player|opponent) gains {_N} life\.", re.I), lambda m: TargetGainLife(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) loses {_N} life\.", re.I), lambda m: TargetLoseLife(_count(m[2]), m[1].lower())),
    # Sanguine Bond, Exquisite Blood: "that much" is the life the trigger's event carried, which the game keeps as X
    (re.compile(r"target (player|opponent) loses that much life\.", re.I), lambda m: TargetLoseLife("X", m[1].lower())),
    (re.compile(r"each opponent loses that much life\.", re.I), lambda m: OpponentsLoseLife("X")),
    (re.compile(r"you gain (?:that much life|life equal to that damage)\.", re.I), lambda m: GainLife("X")),
    (re.compile(rf"return (another |up to one )?target {_PERMANENT_KIND} to its owner's hand\.", re.I),
     # "Return another target ..." can be neither the source (a trigger's) nor the spell's earlier target (Rushing River).
     lambda m: ReturnToHand(m[2].lower(), (m[1] or "").lower() == "another ", (m[1] or "").lower() == "up to one ",
                            distinct=(m[1] or "").lower() == "another ")),
    (re.compile(rf"return {_UP_TO} target {_PLURAL_KIND} to their owners' hands\.", re.I), lambda m: _up_to(ReturnToHand, m)),
    (re.compile(rf"return (five|six|seven) target {_PLURAL_KIND} to their owners' hands\.", re.I),  # Aether Gale: exactly that many
     lambda m: [ReturnToHand(_PLURAL_KINDS[m[2].lower()] + _suffix(m[3]), distinct=n > 0) for n in range(_number(m[1]))]),
    (re.compile(rf"return all {_CARDS_PLURAL} from your graveyard to (the battlefield|your hand)\.", re.I),
     lambda m: ReturnAllFromGraveyard(_card_kind(re.sub(r"\bcards\b", "card", m[1])), "battlefield" if m[2].lower() == "the battlefield" else "hand")),
    (re.compile(rf"return all {_MASS_FILTERED} to (?:their owners' hands|their owner's hand)\.", re.I), lambda m: _mass_effect(ReturnAllToHand, m)),
    (re.compile(rf"return {_UP_TO} target {_CARDS_PLURAL} from your graveyard to your hand\.", re.I),
     lambda m: [ReturnFromGraveyard(_graveyard_kind(m[2].replace("cards", "card", 1), "yours"), "hand",
                                    optional_target=True, distinct=n > 0) for n in range(_number(m[1]))]),
    (re.compile(rf"return (two|three) target {_CARDS_PLURAL} from your graveyard to your hand\.", re.I),  # exactly that many
     lambda m: [ReturnFromGraveyard(_graveyard_kind(m[2].replace("cards", "card", 1), "yours"), "hand", distinct=n > 0)
                for n in range(_number(m[1]))]),
    (re.compile(rf"return up to one target {_CARD_TYPE} from your graveyard to your hand\.", re.I),  # Witch of the Moors
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "hand", optional_target=True)),
    (re.compile(rf"return target {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "hand")),
    (re.compile(rf"return target {_CARD_TYPE} from your graveyard to the battlefield with an indestructible counter on it\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "battlefield", counter="indestructible")),
    (re.compile(rf"exile target {_PERMANENT_KIND}\. its controller draws a card\.", re.I), lambda m: ExileControllerDraws(m[1].lower())),
    (re.compile(rf"return another target {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "hand", another=True)),
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
    (re.compile(rf"search your library for an? {_SEARCH_TYPE}, (?:reveal (?:it|that card), )?(?:put (?:it|that card) into your hand, "
                r"then shuffle|then shuffle and put (?:it|that card|the card) on top(?: of your library)?)\.", re.I),
     lambda m: SearchLibrary(_card_kind(m[1]), "hand" if "into your hand" in m[0] else "top", "reveal" in m[0].lower())),
    (re.compile(r"search your library for a card with the same mana value as (?:this card|CARDNAME), reveal it, put it into your hand, then shuffle\.", re.I),
     lambda m: SearchLibrary("card|mv=self", "hand", True)),  # Transmute
    (re.compile(r"search your library for a land card, put it into your graveyard, then shuffle\.", re.I),
     lambda m: SearchLibrary("land", "graveyard", False)),
    (re.compile(r"search your library for a land card, put (?:it|that card) onto the battlefield( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(1, ("*",), 1, bool(m[1]), False)),  # Crop Rotation
    (re.compile(r"search your library for up to (two|three|four) basic land cards, put them onto the battlefield, then shuffle\.", re.I),
     lambda m: SearchForLands(_count(m[1]), (), _count(m[1]), False, False)),  # Harrow
    (re.compile(r"search your library for a nonbasic land card, put it onto the battlefield( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(1, ("nonbasic",), 1, bool(m[1]), False)),
    (re.compile(rf"search your library for up to (two|three|four) {_LAND_TYPES_PLURAL}, put them onto the battlefield"
                r"( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(_count(m[1]), _land_types(m[2]), _count(m[1]), bool(m[3]), False)),
    (re.compile(rf"search your library for up to (two|three|four) basic {_LAND_TYPES_PLURAL}, reveal (?:them|those cards), put them "
                r"into your hand, then shuffle\.", re.I),  # Archaeomancer's Map
     lambda m: SearchForLands(_count(m[1]), _land_types(m[2]), 0, False, True, basic_only=True)),
    (re.compile(r"search your library for up to (two|three|four) basic land cards, reveal (?:them|those cards), put them into "
                r"your hand, then shuffle\.", re.I),  # Land Tax
     lambda m: SearchForLands(_count(m[1]), (), 0, False, True)),
    (re.compile(rf"search your library for a basic {_LAND_TYPES} card, put it onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: SearchForLands(1, _land_types(m[1]), 1, True, False, basic_only=True)),  # the Landscape cycle
    (re.compile(r"search your library for up to two basic land cards that share a land type, put them onto the battlefield tapped, "
                r"then shuffle\.", re.I),
     lambda m: SearchForLands(2, (), 2, True, False, share_type=True)),  # Myriad Landscape
    (re.compile(rf"untap up to {_NUM} lands\.", re.I), lambda m: UntapLands(_number(m[1]))),
    (re.compile(r"you gain protection from everything until your next turn\.", re.I), lambda m: PlayerProtection()),
    (re.compile(r"(?:this (?:Saga|creature|artifact|enchantment|land)|CARDNAME) gains \"(.+)\"\.?", re.I),  # the ability stays: a Saga's chapter
     lambda m: GainsAbility(line) if _is_known_ability(line := m[1].replace("'", '"')) else None),
    (re.compile(r"search your library for an? ([a-z]+) card with mana cost \{0\} or \{1\}, put it onto the battlefield, then shuffle\.", re.I),
     lambda m: SearchLibrary(f"{m[1].lower()}|mv<=1", "battlefield", False)),  # (mana value 1 or less: the same for every such artifact)
    (re.compile(r"until your next turn, your life total can't change and you gain protection from everything\.", re.I),
     lambda m: [LifeLocked(), PlayerProtection()]),
    (re.compile(r"all permanents you control phase out\.", re.I), lambda m: PhaseOutAll()),
    (re.compile(r"exile CARDNAME\.", re.I), lambda m: ExileThisSpell()),
    (re.compile(r"shuffle CARDNAME into its owner's library\.", re.I), lambda m: ShuffleThisSpell()),
    (re.compile(r"search your library for an? ((?:green |nonland )?(?:creature|artifact)) card( with mana value X or less)?, put it onto "
                r"the battlefield, then shuffle\.", re.I),
     lambda m: SearchLibrary(m[1].lower() + ("|mv<=x" if m[2] else ""), "battlefield", False)),  # Chord of Calling, Natural Order
    (re.compile(r"search your library for a card, put that card into your hand, discard a card at random, then shuffle\.", re.I),
     lambda m: [SearchLibrary("card", "hand", False), Discard(1, "you", True)]),  # Gamble
    (re.compile(r"you lose life equal to (?:its|that card's|that permanent's|that spell's) mana value\.", re.I), lambda m: LoseLifeEqualToManaValue()),
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
    (re.compile(rf"scry {_N_FIXED}, then reveal the top card of your library\.", re.I),
     lambda m: RevealTopStep("reveal", _number(m[1]))),
    (re.compile(r"if it's a land card, put it onto the battlefield( tapped)?\.", re.I),
     lambda m: RevealTopStep("land", tapped=bool(m[1]))),
    (re.compile(r"otherwise, draw a card\.", re.I), lambda m: RevealTopStep("otherwise")),
    (re.compile(rf"surveil {_N}\.", re.I), lambda m: Surveil(_count(m[1]))),
    (re.compile(rf"look at the top {_N} cards of your library, then put them back in any order\.", re.I),
     lambda m: PutBackTop(_count(m[1]))),
    (re.compile(r"you may shuffle\.", re.I), lambda m: _MayShuffle()),
    (re.compile(rf"draw {_N_FIXED} cards, then put {_N_FIXED} cards from your hand on top of your library in any order\.", re.I),
     lambda m: DrawThenPutBack(_number(m[1]), _number(m[2]))),
    (re.compile(rf"look at the top (?:{_N} cards?|card) of your library\.", re.I),
     lambda m: LookAtTop(_count(m[1] or "one"))),
    (re.compile(r"put one of them into your hand and the rest on the bottom of your library in any order\.", re.I),
     lambda m: TakeFromTop(None)),
    (re.compile(rf"you may reveal an? {_SEARCH_TYPE} from among them and put (?:it|that card) into your hand\.", re.I),
     lambda m: TakeFromTop(_card_kind(m[1]))),
    (re.compile(r"put the rest on the bottom of your library in (?:a random|any) order\.", re.I),
     lambda m: RestOnBottom()),
    (re.compile(r"return a land you control to its owner's hand\.", re.I), lambda m: ReturnOwnLand()),
    (re.compile(r"add ((?:\{[WUBRGC]\})+)\.", re.I),
     lambda m: AddMana(tuple(frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[1].upper())))),
    (_RETURN_UP_TO_POWER, lambda m: ReturnFromGraveyard("graveyard:nonland permanent|mv<=power:yours", "battlefield")),
    (_RETURN_UP_TO_DAMAGE, lambda m: ReturnFromGraveyard("graveyard:creature|mv<=x:yours", "battlefield")),  # Venerable Warsinger
    (re.compile(r"exile all (?:cards from all )?graveyards\.", re.I), lambda m: ExileAllGraveyards()),
    (re.compile(r"each opponent loses all counters\.", re.I), lambda m: OpponentsLoseCounters()),
    (re.compile(r"you lose all but 1 life\.", re.I), lambda m: LoseAllButOneLife()),
    (re.compile(r"you gain life equal to the life you lost when it entered\.", re.I), lambda m: GainLifeItLost()),
    (re.compile(r"return it to the battlefield tapped under its owner's control at the beginning of their next upkeep\.", re.I),
     lambda m: ReturnDeadAtNextUpkeep()),
    (re.compile(r"you may put a creature card from your hand onto the battlefield\. If you do, sacrifice it unless you pay its "
                r"mana cost reduced by \{(\d+)\}\.", re.I), lambda m: PutCreatureFromHand(int(m[1]))),
    (re.compile(rf"mill {_N} cards?, then return (an? [a-z ]+? card(?: and an? [a-z ]+? card)?) from your graveyard to "
                r"(your hand|the battlefield)( tapped)?\.", re.I),
     lambda m: None if " and " not in m[2] and m[3].lower() == "your hand" else  # one kind to hand: Mill, then ReturnChosen
     MillThenReturn(_count(m[1]), tuple(_card_kind(re.sub(r"^an? ", "", part)) for part in re.split(r" and ", m[2])),
                    "hand" if m[3].lower() == "your hand" else "battlefield", bool(m[4]))),
    (re.compile(r"each opponent creates a token that's a copy of it\. The tokens are goaded for the rest of the game\.", re.I),
     lambda m: EachOpponentGetsGoadedCopy()),
    (re.compile(r"create (?:a token that's a copy of|(five) tokens that are copies of) another target creature you control"
                r"(, except it isn't legendary)?\. (?:It gains|They gain) haste\. Sacrifice (?:it|them) at the beginning of the "
                r"next end step\.", re.I),
     lambda m: CopiesOfAnotherCreature(5 if m[1] else 1, bool(m[2]))),
    (re.compile(r"that player copies that spell for each other creature they control that the spell could target\. Each copy "
                r"targets a different one of those creatures\.", re.I), lambda m: CopySpellForEachOtherCreature()),
    (re.compile(r"exile (?:it|that creature)\. If you do, create a token that's a copy of (?:it|that creature), except it's a Spirit in "
                r"addition to its other types and it has \"When this token leaves the battlefield, return the exiled card to its "
                r"owner's graveyard\.\"", re.I), lambda m: ExileDeadMakeSpiritCopy()),
    (re.compile(r"return the exiled card to its owner's graveyard\.", re.I), lambda m: ReturnExiledToGraveyard()),
    (re.compile(rf"{_SELF} becomes a copy of up to one target nonlegendary creature you control until end of turn, except it has "
                r"([a-z]+)\.", re.I), lambda m: BecomeCopyUntilEndOfTurn(m[1].capitalize())),
    (re.compile(r"for each creature token you control that entered this turn, create a tapped and attacking token that's a copy of that "
                r"token\. At the beginning of the next end step, sacrifice those tokens\.", re.I),
     lambda m: CopyEnteredTokensAttacking()),
    (re.compile(r"create X tokens that are copies of another target creature you control, where X is one plus the number of instant "
                r"and sorcery spells you've cast this turn\. They gain haste\. Exile them at the beginning of the next end step\.",
                re.I), lambda m: [DefineX(Amount("one_plus_spells", "instant or sorcery spell")),
                                  CopiesOfAnotherCreature("X", exile=True)]),
    (re.compile(r"target player draws cards equal to half the number of cards in their library and loses half their life\. "
                r"Round up each time\.", re.I), lambda m: DrawHalfLibraryLoseHalfLife()),
    (re.compile(r"Exile the top four cards of your library in a face-down pile, then exile the top four cards of your library in a face-up pile\. An opponent chooses one of those piles\. Put that pile into your graveyard\. Look at the cards in the other pile\. You may cast a spell from among them without paying its mana cost\. Put the rest into your hand\.", re.I), lambda m: PilesOfFour()),
    (re.compile(r"Council's dilemma — Starting with you, each player votes for past or present\. You mill a card for each "
                r"past vote, then (?:CARDNAME|[A-Z][\w' ]+) deals damage to each opponent equal to the total mana value of cards milled "
                r"this way\. Exile the top card of your library for each present vote\. Until the end of your next turn, you may "
                r"play the exiled cards\."), lambda m: PastOrPresentVote()),
    (re.compile(r"Exile target instant or sorcery card from your graveyard\. Creatures you control get "
                                     r"\+X/\+0 until end of turn, where X is that card's mana value\. Whenever a creature you control "
                                     r"deals combat damage to a player this turn, copy the exiled card\. You may cast the copy "
                                     r"without paying its mana cost\.", re.I), lambda m: SurgeToVictory()),
    (re.compile(rf"remove {_N_FIXED} ([a-z]+) counters? from (?:{_SELF})\.", re.I),
     lambda m: RemoveCountersFromSource(_number(m[1]), m[2].lower())),
    (re.compile(rf"(?:{_SELF}) deals damage to target (player|opponent) equal to (.+)\.", re.I),
     lambda m: [DefineX(a), Damage("X", m[1].lower())] if (a := _amount(m[2])) else None),
    (re.compile(rf"(?:{_SELF}) deals (\d+) damage to the player or planeswalker (?:that creature|it) is attacking\.", re.I),
     lambda m: DamageWhatItAttacks(int(m[1]))),
    (re.compile(r"add \{([WUBRGC])\} for each card in target opponent's hand\.", re.I), lambda m: AddManaPerCardInHand(m[1].upper())),
    (re.compile(r"until end of turn, you don't lose this mana as steps and phases end\.", re.I), lambda m: KeepManaThisTurn()),
    (re.compile(r"exile (?:CARDNAME|this spell) with (a|two|three|four|five|\d+) time counters? on it\.", re.I),
     lambda m: ExileWithTimeCounters(_number(m[1]))),
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
    (re.compile(r"double the value of X\.", re.I), lambda m: DoubleXOfTriggeringSpell()),
    (re.compile(r"copy that ability\. You may choose new targets for the copy\.", re.I), lambda m: CopyTriggeringAbility()),
    (re.compile(r"any number of other target creatures you control phase out\.", re.I), lambda m: PhaseOut()),
    (re.compile(r"create a white Aura enchantment token named Contract attached to target creature an opponent controls\. The token has "
                r"enchant creature and \"Whenever enchanted creature attacks, it gets \+2/\+0 until end of turn if it's attacking one of "
                r"your opponents\. Otherwise, its controller loses 2 life\.\"", re.I), lambda m: CreateContract()),
    (re.compile(r"it gets \+2/\+0 until end of turn if it's attacking one of your opponents\. Otherwise, its controller loses 2 "
                r"life\.", re.I), lambda m: ContractAttack()),
    (re.compile(r"for each player, you choose from among the permanents that player controls an artifact, a creature, an enchantment, "
                r"and a planeswalker\. Then each player sacrifices all other nonland permanents they control\.", re.I),
     lambda m: TragicArrogance()),
    (re.compile(rf"any number of target players each lose {_N_FIXED} life and sacrifice a creature of their choice\. You add ((?:\{{[WUBRGC]\}})+) and "
                r"draw a card\.", re.I),
     lambda m: PlayersLoseSacrificeAddManaDraw(_number(m[1]), tuple(frozenset(x) for x in re.findall(r"[WUBRGC]", m[2])))),
    (re.compile(r"each player sacrifices a (creature or planeswalker) of their choice\. If you sacrificed a permanent this way, you may "
                r"return another permanent card from your graveyard to your hand\.", re.I),
     lambda m: EachSacrificesThenReturn(m[1].lower())),
    (re.compile(r"move any number of ([+\-\u2212]1/[+\-\u2212]1) counters from (?:this creature|CARDNAME) onto other creatures\.", re.I),
     lambda m: MoveCountersToOthers(_counter_name(m[1]))),
    (re.compile(rf"target player shuffles up to {_N_FIXED} target cards from their graveyard into their library\.", re.I),
     lambda m: ShuffleIntoLibrary(max_targets=_number(m[1]))),
    (re.compile(r"level \d", re.I), lambda m: LevelUp()),
    (re.compile(r"if this spell was cast from a graveyard, you may copy this spell and may choose a new target for the copy\.", re.I),
     lambda m: MayCopyThisSpellFromGraveyard()),
    (re.compile(r"return target permanent card with mana value (\d+) or less from your graveyard to the battlefield\.", re.I),
     lambda m: ReturnFromGraveyard(f"graveyard:permanent|mv<={m[1]}:yours", "battlefield")),
    (re.compile(r"exile up to one target instant or sorcery card from your graveyard and copy it\. You may cast the copy without "
                r"paying its mana cost\.", re.I), lambda m: ExileThenCastCopy()),
    (re.compile(r"each player exiles a card from their graveyard\. When one or more nonland cards are exiled this way, put that many "
                r"\+1/\+1 counters on target attacking creature\.", re.I), lambda m: EachExilesGraveyardCardCounters()),
    (re.compile(r"return up to one target artifact, creature, or non-Aura enchantment card with mana value (\d+) or less from your "
                r"graveyard to the battlefield with a finality counter on it\. It's a 1/1 Spirit creature with flying in addition to "
                r"its other types\.", re.I),
     lambda m: ReturnFromGraveyard(f"graveyard:artifact or creature or non-aura enchantment|mv<={m[1]}:yours", "battlefield",
                                   optional_target=True, finality=True)),
    (re.compile(r"choose target card exiled with (?:CARDNAME|this \w+)\. You may cast that card this turn without paying its mana "
                r"cost\. If that spell would be put into a graveyard, put it on the bottom of its owner's library instead\.", re.I),
     lambda m: CastExiledWithFree()),
    (re.compile(r"put a card exiled with (?:this artifact|CARDNAME) into its owner's graveyard\. If it's a land card, create a "
                r"Treasure token\. If it's a nonland card, create an? (.+ creature token)\.", re.I),
     lambda m: PutExiledWithIntoGraveyard(TREASURE, made[1]) if (made := _token("a " + m[1])) else None),
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
    (re.compile(rf"put {_N} stun counters? on (?:it|that creature)\.", re.I), lambda m: PutStunCounters(_count(m[1]))),
    (re.compile(rf"put {_N} stun counters? on (?:this creature|{{self}})\.".replace("{self}", "CARDNAME"), re.I),
     lambda m: PutStunOnSource(_count(m[1]))),
    (re.compile(r"all creatures able to block target (creature) this turn do so\.", re.I), lambda m: LureThisTurn(m[1].lower())),
    (re.compile(r"target (creature) blocks this turn if able\.", re.I), lambda m: MustBlockThisTurn(m[1].lower())),
    (re.compile(rf"target (creature) blocks (?:this creature|{{self}}) this turn if able\.".replace("{self}", "CARDNAME"), re.I),
     lambda m: MustBlockThisTurn(m[1].lower(), source_only=True)),
    (re.compile(rf"tap target {_PERMANENT_KIND} and put {_N} stun counters? on (?:it|that creature)\.", re.I),
     lambda m: [Tap(m[1].lower()), PutStunCounters(_count(m[2]))]),
    (re.compile(rf"put {_N} stun counters? on each of them\.", re.I), lambda m: PutStunOnEach(_count(m[1]))),
    (re.compile(rf"tap {_UP_TO} target {_PLURAL_KIND} and put {_N} stun counters? on each of them\.", re.I),
     lambda m: [*_up_to(Tap, m), PutStunOnEach(_count(m[4]))]),
    (re.compile(rf"tap one or two target {_PLURAL_KIND}\.", re.I),
     lambda m: [Tap(_PLURAL_KINDS[m[1].lower()] + _suffix(m[2])),
                Tap(_PLURAL_KINDS[m[1].lower()] + _suffix(m[2]), optional_target=True, distinct=True)]),
    (re.compile(rf"tap up to one target {_PERMANENT_KIND} and put {_N} stun counters? on it\.", re.I),
     lambda m: [Tap(m[1].lower(), optional_target=True), PutStunCounters(_count(m[2]))]),
    (re.compile(r"attach (?:it|this Equipment) to target ((?:legendary )?creature you control)\.", re.I),
     lambda m: Attach(m[1].lower())),  # Mithril Coat
    (re.compile(r"you may cast a spell with mana value (\d+) or less from your hand without paying its mana cost\.", re.I),
     lambda m: MayCastFromHandFree(int(m[1]))),  # Rishkar's Expertise
    (re.compile(r"choose two target creature cards in your graveyard\. sacrifice a creature\. if you do, return the chosen cards to the "
                r"battlefield tapped\.", re.I), lambda m: SacrificeToReturnChosen()),  # Victimize
    (re.compile(r"choose target (creature(?: you control)?)\.", re.I), lambda m: ChooseTarget(m[1].lower())),
    (re.compile(r"draw that many cards\.", re.I), lambda m: Draw("X")),
    (re.compile(r"until end of turn, that creature gains \"when this creature dies, return it to the battlefield tapped under its owner's "
                r"control\.\"", re.I), lambda m: ReturnWhenItDiesThisTurn()),  # Malakir Rebirth
    (re.compile(r"search your library for up to X basic land cards, where X is the greatest power among creatures you control\. put those "
                r"cards onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: [DefineX(Amount("greatest_power", "creature")), SearchForLands("X", (), "X", True, False)]),  # Traverse the Outlands
    (re.compile(r"put a \+1/\+1 counter on target (artifact creature) for each \+1/\+1 counter on (?:this creature|CARDNAME)\.", re.I),
     lambda m: [DefineX(Amount("source_counters", "+1/+1")), PutCounters("X", "+1/+1", m[1].lower())]),  # Modular
    (re.compile(r"proliferate\.", re.I), lambda m: Proliferate()),
    (re.compile(r"proliferate (X) times\.", re.I), lambda m: Proliferate("X")),
    (re.compile(rf"target {_FIGHTER} fights (another )?target {_FIGHTER}\.", re.I),
     lambda m: [FightFirst(m[1].lower()), Fight(m[3].lower(), another=bool(m[2]))]),
    (re.compile(rf"target {_FIGHTER} deals damage equal to its power to (?:target {_FIGHTER}|(any target)"
                r"|target (creature or planeswalker (?:you don't control|an opponent controls)))\.", re.I),
     lambda m: [FightFirst(m[1].lower()), Fight("any" if m[3] else (m[2] or m[4]).lower(), one_sided=True)]),
    (re.compile(r"target creature you control deals damage equal to its power to each other creature and each opponent\.", re.I),
     lambda m: [FightFirst("creature you control"), PowerDamageToEachOther()]),
    (re.compile(rf"then it fights up to one target {_FIGHTER}\.", re.I),  # Primal Might: after a pump of the first creature
     lambda m: Fight(m[1].lower(), optional_target=True)),
    (re.compile(rf"look at the top {_N_FIXED} cards of your library\. Put {_N_FIXED} of them into your hand and the rest on the bottom of your "
                r"library in any order\.", re.I), lambda m: LookTakeRestBottom(_number(m[1]), _number(m[2]))),
    (re.compile(r"target player draws X cards plus an additional card for each time they've cast a commander from the command zone "
                r"this game\.", re.I), lambda m: TargetDrawXPlusCasts()),
    (re.compile(r"add \{([WUBRGC])\} or \{([WUBRGC])\} for each permanent destroyed this way\.", re.I),
     lambda m: _ManaForEachDestroyed(frozenset({m[1].upper(), m[2].upper()}))),
    (re.compile(r"add \{([WUBRGC])\} for each tapped land your opponents control\.", re.I),
     lambda m: AddManaPerTappedLand(m[1].upper())),
    (re.compile(r"creatures you control have base power and toughness X/X until end of turn\.", re.I), lambda m: SetBaseEachX()),
    (re.compile(r"each creature deals damage to itself equal to its power\.", re.I), lambda m: EachDamagesItself()),
    (re.compile(rf"each creature deals {_N_FIXED} damage to its controller\.", re.I), lambda m: EachCreatureDamagesItsController(_number(m[1]))),
    (re.compile(rf"target player draws {_N_FIXED} cards, then discards {_N_FIXED} cards\.", re.I),
     lambda m: TargetDrawDiscard(_number(m[1]), _number(m[2]))),
    (re.compile(rf"target player mills {_N_FIXED} cards, then you return an? {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: TargetMillThenReturn(_number(m[1]), _card_kind(m[2]))),
    (re.compile(r"you gain half X life and draw half X cards\. round down each time\.", re.I),
     lambda m: [GainLife("hX"), Draw("hX")]),
    (re.compile(r"populate\.", re.I), lambda m: Populate()),
    (re.compile(r"(?i:put) an? ((?:[A-Z][a-z]+(?:, (?:or )?| or ))*[A-Z][a-z]+) (?i:creature card from your hand onto the "
                r"battlefield tapped and attacking that opponent\.)"),
     lambda m: PutAttackingFromHand(tuple(re.findall(r"[A-Z][a-z]+", m[1])))),
    (re.compile(rf"{_SELF} becomes prepared\.", re.I), lambda m: BecomePrepared()),
    (re.compile(rf"transform {_SELF}\.", re.I), lambda m: Transform()),
    (re.compile(rf"exile {_SELF}, then return it to the battlefield transformed under your control\.", re.I), lambda m: ReturnTransformed()),
    (re.compile(rf"return it to the battlefield( tapped)? and transformed under (?:its owner's|your) control\.", re.I),
     lambda m: ReturnTransformed(dies=True, tapped=m[1] is not None)),
    (re.compile(r"return it to the battlefield transformed under (?:its owner's|your) control at the beginning of the next end step\.", re.I),
     lambda m: ReturnTransformed(dies=True, end_step=True)),
    (re.compile(r"conjure a card named (.+?) onto the battlefield\.", re.I), lambda m: Conjure(m[1])),
    (re.compile(r"tap enchanted creature\.", re.I), lambda m: TapEnchanted()),
    (re.compile(r"tap enchanted creature\. It becomes unprepared\.", re.I), lambda m: TapEnchanted(unprepare=True)),
    (re.compile(r"until end of turn, whenever you tap a mountain for mana, add an additional \{R\}\.", re.I),
     lambda m: ExtraMountainMana()),
    (re.compile(r"until end of turn, any time you could activate a mana ability, you may pay 1 life\. If you do, add \{C\}\.",
                re.I), lambda m: PayLifeForMana()),
    (re.compile(rf"whenever that creature deals combat damage to a player this combat, ({_SELF} becomes prepared)\.", re.I),
     lambda m: WhenThatDealsCombatDamage(BecomePrepared())),
    (re.compile(r"each creature you control becomes prepared\.", re.I), lambda m: PrepareEach()),
    (re.compile(r"target (creature(?: that attacked this turn)?) becomes (prepared|unprepared)\.", re.I),
     lambda m: TargetPrepared(m[1].lower(), m[2].lower() == "prepared")),
    (re.compile(rf"create a token that's a copy of target {_PERMANENT_KIND}\.", re.I), lambda m: CopyToken(m[1].lower())),
    (re.compile(rf"create a token that's a copy of target {_PERMANENT_KIND}, except it's legendary\.", re.I),
     lambda m: CopyToken(m[1].lower(), legendary=True)),
    (re.compile(rf"create a token that's a copy of another target {_PERMANENT_KIND}\.", re.I),
     lambda m: CopyToken(m[1].lower(), another=True)),
    (re.compile(rf"create a token that's a copy of {_SELF}, tapped and attacking\.", re.I), lambda m: CopyTokenAttacking()),
    (re.compile(r"that attacking player creates a tapped (.+? creature token(?: with [a-z, ]+)?) that's attacking that opponent\.",
                re.I), lambda m: _attacker_token("a " + m[1])),
    (re.compile(r"put one of them into your hand, put one of them on the bottom of your library, and exile one of them\.",
                re.I), lambda m: _SplitTop()),
    (re.compile(r"you may play the exiled card this turn\.", re.I), lambda m: _PlayTheExiledCard()),
    (re.compile(r"its controller manifests the top card of their library\.", re.I), lambda m: TargetControllerManifests()),
    (re.compile(r"manifest dread(?: (twice))?\.", re.I), lambda m: ManifestDread(2 if m[1] else 1)),
    (re.compile(rf"manifest dread, then attach {_SELF} to that creature\.", re.I), lambda m: ManifestDread(attach=True)),
    (re.compile(rf"manifest dread, then put {_N_FIXED} \+1/\+1 counters? on that creature\.", re.I), lambda m: ManifestDread(counters=_number(m[1]))),
    (re.compile(rf"shuffle your library\. as many times as you choose, you may exile the top card of your library\. if the "
                rf"total mana value of the cards exiled this way is {_N_FIXED} or less, you may cast any number of spells from among "
                r"those cards without paying their mana costs\.", re.I), lambda m: DanceWithCalamity(_number(m[1]))),
    (re.compile(r"target (player|opponent) loses half their life, rounded (up|down)\.", re.I),
     lambda m: TargetLoseHalfLife(m[1].lower(), m[2].lower() == "up")),
    (re.compile(rf"double the number of {_COUNTER} on target {_PERMANENT_KIND}\.", re.I),
     lambda m: DoubleCountersOnTarget(_counter_name(m[1]), m[2].lower())),
    (re.compile(r"look at the top card of your library\. if it's an? (creature )?card of the chosen type, you may reveal it and put it "
                r"into your hand\.", re.I), lambda m: LookTopTakeChosen(bool(m[1]))),
    (re.compile(rf"return {_SELF} to the battlefield( tapped)?( under its owner's control)?\.", re.I),
     lambda m: ReturnSelfToBattlefield(tapped=bool(m[1]))),
    (re.compile(r"search your library for a ([A-Z][a-z]+) card and put it onto the battlefield tapped\. Then if an opponent controls "
                r"more lands than you, repeat this process once\. If you search your library this way, shuffle\.", re.I),
     lambda m: SearchLandWhileBehind(m[1].capitalize())),
    (re.compile(rf"(?:you may )?put an? {_CARD_TYPE} from your hand onto the battlefield( tapped)?\.", re.I),
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
    (re.compile(r"untap all (artifacts|lands|permanents|enchantments|nonland permanents) you control\.", re.I),
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
    (re.compile(r"(?:they|it|a creature destroyed this way) can't be regenerated\.", re.I), lambda m: CannotRegenerate()),
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
    (re.compile(r"each player creates (.+) and puts a number of \+1/\+1 counters on it equal to the total power of (?:the )?"
                r"creatures they controlled that were exiled this way\.(\"?)", re.I),
     lambda m: _gift(_GiftMatch(m[1], m[2]), who="each player", power_counters=True)),
    (re.compile(r"sacrifice a creature\.", re.I), lambda m: SacrificeCreature()),
    (re.compile(rf"(?:you )?sacrifice (a|an|one|two|three) {_SACRIFICE_KIND}\.", re.I),
     lambda m: EachSacrifices("you", m[2].lower(), _count(m[1]))),
    (re.compile(rf"(?:you )?sacrifice (two|three|four|five) {_SACRIFICE_PLURAL}\.", re.I),
     lambda m: EachSacrifices("you", _PLURAL_SACRIFICE[m[2].lower()], _count(m[1]))),
    (re.compile(rf"sacrifice {_SELF} unless you return an untapped ({_LAND_TYPE}) you control to its owner's hand\.", re.I),
     lambda m: SacrificeUnlessReturnLand(m[1].capitalize())),
    (re.compile(rf"sacrifice {_SELF} unless you pay ((?:\{{[0-9WUBRGC]+\}})+)\.", re.I), lambda m: SacrificeUnlessPay(m[1])),
    (re.compile(r"you may play the exiled card without paying its mana cost if (.+)\.", re.I),
     lambda m: PlayExiledCard(c) if (c := _condition(m[1])) else None),
    (re.compile(r"Let X be (.+)\."), lambda m: DefineX(a) if (a := _amount(m[1])) else None),
    (re.compile(rf"target (player|opponent) sacrifices an? {_SACRIFICE_KIND}\.", re.I),
     lambda m: TargetSacrifices(m[1].lower(), m[2].lower())),
    (re.compile(rf"{_SELF} also deals {_N_FIXED} damage to that creature's controller\.", re.I), lambda m: DamageTargetsController(_number(m[1]))),
    (re.compile(r"target (player|opponent) sacrifices a creature with the greatest power among creatures they control\.", re.I),
     lambda m: TargetSacrifices(m[1].lower(), greatest=True)),
    (re.compile(r"exile target player's graveyard\.", re.I), lambda m: ExileGraveyard()),
    (re.compile(rf"put a ({_COUNTER}) on each of up to (two|three) target creatures\.", re.I),  # Elegant Rotunda
     lambda m: [PutCounters(1, _counter_name(m[2]), "creature", optional_target=True, distinct=n > 0) for n in range(_number(m[3]))]),
    (re.compile(rf"put {_N} {_COUNTER} on target {_PERMANENT_KIND}\.", re.I),
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"put {_N} {_COUNTER} on target (attacking creature with lesser power)\.", re.I),  # Mentor
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"distribute {_N} {_COUNTER} among (?:one or two|one, two, or three|up to {_N}|any number of) (other )?(?:target )?"
                r"creatures( you control)?\.", re.I),
     lambda m: DistributeCounters(_count(m[1]), _counter_name(m[2]), "creature" + (" you control" if m[5] else ""), another=m[4] is not None)),
    (re.compile(rf"put {_N} {_COUNTER} on another target {_PERMANENT_KIND}\.", re.I),
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower(), another=True)),
    (re.compile(rf"put {_N} {_COUNTER} on each (creature|(?-i:[A-Z][a-z]+)(?: creature)?|artifact creature) you control\.", re.I),
     lambda m: PutCountersOnEach(_count(m[1]), _counter_name(m[2]), "" if m[3].lower() == "creature" else m[3].removesuffix(" creature").capitalize())),
    (re.compile(rf"put a {_COUNTER} on each (?:(white|blue|black|red|green) )?creature that entered this turn\.", re.I),
     lambda m: PutCountersOnEntered(_counter_name(m[1]), _COLOR_WORDS[m[2].lower()] if m[2] else "")),
    (re.compile(rf"put {_N} {_COUNTER} on {_SELF}\.", re.I),
     lambda m: PutCountersOnSource(_count(m[1]), _counter_name(m[2]))),
    (re.compile(rf"put {_N} {_COUNTER} on {_SELF} and it becomes renowned\.", re.I),  # Renown
     lambda m: [PutCountersOnSource(_count(m[1]), _counter_name(m[2])), BecomeRenowned()]),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} gains protection from the color of your choice until end of turn\."),
     lambda m: GrantProtection(m[1].lower())),
    (re.compile(rf"(?i:{_SELF}) gains protection from the color of your choice until end of turn\."),
     lambda m: GrantProtection(uses_source=True)),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} {_CHANGE}"), lambda m: Pump(_modifier(m, 2), m[1].lower())),
    (re.compile(r"choose artifact or enchantment\. destroy all permanents of the chosen type\.", re.I),
     lambda m: DestroyAllOfChosenType(("artifact", "enchantment"))),
    (re.compile(r"choose an artifact or creature you control\. create a token that's a copy of it\.", re.I),
     lambda m: CopyChosenPermanent("artifact or creature you control")),
    (re.compile(r"double the (power|power and toughness) of each creature you control until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[1].lower(), "toughness" in m[1].lower(), each=True)),
    (re.compile(r"double the (power|power and toughness) of each ([A-Z][a-z]+) you control until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[1].lower(), "toughness" in m[1].lower(), each=True, subtype=m[2])),
    (re.compile(rf"until end of turn, double target {_PERMANENT_KIND}'s power X times\.", re.I),
     lambda m: DoubleStats(True, False, target=m[1].lower(), times="X")),
    (re.compile(rf"double the (power|power and toughness) of target {_PERMANENT_KIND} until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[1].lower(), "toughness" in m[1].lower(), target=m[2].lower())),
    (re.compile(rf"double target {_PERMANENT_KIND}'s (power|power and toughness) until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[2].lower(), "toughness" in m[2].lower(), target=m[1].lower())),
    (re.compile(rf"double (?:{_SELF}'s|its) (power|power and toughness) until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[1].lower(), "toughness" in m[1].lower(), uses_source=True)),
    (re.compile(rf"creatures named {_SELF} can't be blocked this turn\.", re.I),
     lambda m: PumpNamed(Modifier(keywords=frozenset({CANT_BE_BLOCKED})))),
    (re.compile(r"shuffle any number of target cards from your graveyard into your library\.", re.I),
     lambda m: ShuffleIntoLibrary()),
    (re.compile(rf"target {_PERMANENT_KIND} can't be blocked this turn\.", re.I),
     lambda m: Pump(Modifier(keywords=frozenset({CANT_BE_BLOCKED})), m[1].lower())),
    (re.compile(rf"target {_PERMANENT_KIND} can't block this turn\.", re.I),
     lambda m: Pump(Modifier(keywords=frozenset({CANT_BLOCK})), m[1].lower())),
    (re.compile(rf"one or two target {_PLURAL_KIND} can't block this turn\.", re.I),
     lambda m: [Pump(Modifier(keywords=frozenset({CANT_BLOCK})), _PLURAL_KINDS[m[1].lower()] + _suffix(m[2])),
                Pump(Modifier(keywords=frozenset({CANT_BLOCK})), _PLURAL_KINDS[m[1].lower()] + _suffix(m[2]),
                     optional_target=True, distinct=True)]),
    (re.compile(rf"{_SELF} can't be blocked this turn\.", re.I),
     lambda m: PumpSource(Modifier(keywords=frozenset({CANT_BE_BLOCKED})))),
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
    (re.compile(rf"(?:(?i:until end of turn, ))?(?i:(creatures you control)) gain {_KEYWORDS} and get {_PT_X}(?: until end of turn)?\."),
     lambda m: dataclasses.replace(_pump_each_x_from(m[1], m[3], m[4], m[5], m[6]), keywords=_keyword_list(m[2]))),
    (re.compile(r"(?:Until end of turn, )?creatures your opponents control lose hexproof and shroud and can't have hexproof or shroud\."),
     lambda m: PumpEach(Modifier(keywords=frozenset({LOSES_HEXPROOF})), opponents=True)),
    (re.compile(rf"(?i:creatures your opponents control) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1), opponents=True)),
    (re.compile(rf"(?i:all creatures) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1), everyone=True)),
    (re.compile(rf"move (?:{_N_FIXED}|all|any number of) {_COUNTER} from target (creature) onto another target (creature)"
                r"( with the same controller)?\.", re.I),
     lambda m: [MoveCountersFrom(m[3].lower()),
                MoveCountersOnto("any" if m[0].lower().startswith("move any number") else _number(m[1]) if m[1] else None,
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
    (re.compile(rf"put an? {_COUNTER} on enchanted creature\.", re.I), lambda m: PutCounterOnHost(1, _counter_name(m[1]))),
    (re.compile(r"have the base power and toughness of other creatures you control become equal to (?:CARDNAME's|its) "
                r"power and toughness until end of turn\.", re.I), lambda m: OthersBecomeAsBigAsSource()),
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
    (re.compile(rf"(?i:non)-((?-i:[A-Z][a-z]+)) creatures you control {_CHANGE}"),
     lambda m: PumpEach(_modifier(m, 2), subtype="non-" + m[1])),  # Return of the Wildspeaker
    (re.compile(r'for each opponent, create (.+) that attack that opponent this turn if able\.("?)', re.I), _attacking_tokens),
    (re.compile(r"they gain haste until end of turn\.", re.I), lambda m: _TheyGainHaste()),
    (re.compile(r"exile them at the beginning of the next end step\.", re.I), lambda m: _ExileThemLater()),
    (re.compile(r"sacrifice them at the beginning of the next end step\.", re.I), lambda m: _SacrificeThemLater()),
    (re.compile(r"create (.+?) tapped and attacking (\d+/\d+ [^.]*? creature tokens?)\.", re.I),  # Mobilize
     lambda m: (lambda parsed: TokensJoinAttack(parsed[0], parsed[1]) if parsed else None)(_token(f"{m[1]} {m[2]}"))),
    (re.compile(r"prevent all combat damage that would be dealt this turn\.", re.I), lambda m: PreventAllCombatDamage()),
    (re.compile(rf"prevent the next {_NUM} damage that would be dealt to (any target|target creature|you|{_SELF}) this turn\.", re.I),
     lambda m: _prevent_next(_number(m[1]), m[2])),
    (re.compile(r"prevent all damage that would be dealt to target creature this turn\.", re.I),
     lambda m: PreventNext(ALL_DAMAGE, "creature")),
    (re.compile(r"prevent all combat damage that would be dealt to you this turn\.", re.I),
     lambda m: PreventCombatDamageToYou()),
    (re.compile(r'for each 1 damage prevented this way, create (.+)\.("?)', re.I), _token_per_prevented),
    (re.compile(r"(?:then )?you may choose a token you control\.", re.I), lambda m: _ChooseToken()),
    (re.compile(r"if you do, each other token you control becomes a copy of that token( until end of turn)?\.", re.I),
     lambda m: _OthersBecomeCopies(bool(m[1]))),
    (re.compile(r'(?i:create) (.+)\.("?)'), lambda m: _create(m, follows=False)),
    (re.compile(r'(?i:(?:its|that creature\'s) controller creates) (.+)\.("?)'), lambda m: _create(m, follows=True)),
    (re.compile(r"its controller gains life equal to its power\.", re.I), lambda m: TargetControllerGainsLifeEqualToPower()),
    (re.compile(r"that player may search their library for a land card with a basic land type, put it onto the battlefield, "
                r"then shuffle\.", re.I), lambda m: TargetControllerMayFetchBasicLand(tapped=False, typed=True)),  # Boseiju
    (re.compile(r"its controller may search their library for a basic land card, put (?:it|that card) onto the "
                r"battlefield( tapped)?, then shuffle\.", re.I), lambda m: TargetControllerMayFetchBasicLand(tapped=bool(m[1]))),
    (re.compile(r"search your library for a basic land card, put (?:it|that card) onto the battlefield tapped, "
                r"then shuffle\.", re.I),
     lambda m: FetchBasicLand()),
    (re.compile(r"search your library for a basic land card, put it onto the battlefield, then shuffle\.", re.I),
     lambda m: FetchBasicLand(tapped=False)),
]


_YOUR_ACTION = (rf"(?:draw (?:a card|{_N} cards)|gain {_N} life|lose {_N} life"
                r"|return (?:up to one )?target (?:[a-z]+ )?card from your graveyard to your hand"
                rf"|put {_N} \+1/\+1 counters? on a creature you control"
                r"|create an? (?:Treasure|Food|Clue) token)")  # Witch of the Moors; Breena; Lotho


def _you_do(phrase: str) -> str:
    """A sentence for something you do: "draw a card" -> "Draw a card.", "lose 1 life" -> "You lose 1 life." """
    return phrase[:1].upper() + phrase[1:] + "." if phrase.lower().startswith(("draw", "return", "create")) else f"You {phrase}."


_TIMES_X = [
    (r"\b(draws?) (?:a card|cards)\b", r"\1 X cards"),
    (r"\b(mills?) (?:a card|cards)\b", r"\1 X cards"),
    (r"\b(gains?|loses?) (?:1 )?life\b", r"\1 X life"),
    (r"\b(creates?) (?:a|an|one) (.+?) token\b", r"\1 X \2 tokens"),
    (r"\b(creates?) a number of (.+?) tokens\b", r"\1 X \2 tokens"),
    (r"\b(put) (?:a|one) (\+1/\+1) counter\b", r"\1 X \2 counters"),
    (r"\b(put) a number of (\+1/\+1) counters\b", r"\1 X \2 counters"),
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
    sentence = sentence.replace(" of their choice.", ".").replace("each other player", "each opponent").replace("Each other player", "Each opponent")
    if m := re.fullmatch(r"(Draw cards equal to [^,]+), then (discard .+\.)", sentence):  # Greater Good
        return _clauses(m[1] + ".") + [m[2][:1].upper() + m[2][1:]]
    if m := re.fullmatch(r"(You (?:lose|gain) \d+ life) and (create .+)", sentence):  # Bitterblossom
        return [m[1] + ".", m[2][:1].upper() + m[2][1:]]
    if m := re.match(r"Then (?!if\b)(\w)", sentence):  # "Then creatures you control gain trample ..." (Blossoming Bogbeast): the order is the list's
        sentence = m[1].upper() + sentence[m.end():]
    sentence = re.sub(r"\b(draws?) (an|a|one|two|three) additional cards?\b",  # Well of Ideas, Midnight Oil
                      lambda m: f"{m[1]} {'a card' if m[2] in ('an', 'a', 'one') else m[2] + ' cards'}", sentence, flags=re.I)
    if m := re.fullmatch(r"(.*)\bhalf X (.+?), rounded (up|down)\.", sentence):  # The Goose Mother: "create half X Food tokens, rounded up."
        return _clauses(f"{m[1]}half X {m[3]} {m[2]}.")
    if _RETURN_UP_TO_POWER.fullmatch(sentence) or _RETURN_UP_TO_DAMAGE.fullmatch(sentence):  # one effect: X is looked at when the target is chosen
        return [sentence]
    if m := re.fullmatch(r"Create a number of (.+?) tokens? equal to (.+)\.", sentence, re.I):  # Gyome's Food
        return [f"Let X be {m[2]}.", f"Create X {m[1]} tokens."] if _amount(m[2]) else [sentence]
    if m := re.fullmatch(r"(.+), where X is (.+)\.", sentence):
        return [f"Let X be {m[2]}."] + _clauses(m[1] + ".") if _amount(m[2]) else [sentence]
    if m := re.fullmatch(r"(.+) (?:equal to|for each) (.+)\.", sentence):
        body, count = _times_x(m[1])
        if not (count and _amount(m[2])):
            return [sentence]
        clauses = _clauses(body + ".")
        # X is worked out when the clause that uses it is done, not before the ones ahead of it ("put a counter on it, then draw a card
        # for each counter on it" draws for the counter just put there).
        at = next((i for i, clause in enumerate(clauses) if re.search(r"\bX\b", clause)), 0)
        return clauses[:at] + [f"Let X be {m[2]}."] + clauses[at:]
    if m := re.fullmatch(r"For each opponent, you (create .+?)(\.\"?)", sentence):  # Eccentric Pestfinder's spell
        return _clauses(f"Create {m[1][len('create '):]}{m[2]} for each opponent.")
    if m := re.fullmatch(r"(Create .+ tokens?), then (put .+ counters? on it\.)", sentence):
        return [m[1] + ".", m[2].capitalize()]
    if m := re.fullmatch(r"(Create .+? tokens?(?: with [a-z, ]+)?), then populate\.", sentence, re.I):  # Horncaller's Chant
        return [m[1] + ".", "Populate."]
    sentence = re.sub(r"^You (draw|create) ", lambda m: m[1].capitalize() + " ", sentence)
    if m := re.fullmatch(rf"(Draw {_N} cards?) and ((?:create|remove) .+)\.", sentence):  # Big Score, Seize the Spoils, Midnight Oil
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


_DELAYED_TRIGGER = re.compile(r"(?:until (?:the )?end of (?:the turn|your next turn|turn), (whenever .+)|(whenever [^,]+?) this turn, (.+))", re.I)


def _delayed_trigger(sentence: str) -> CreateDelayedTrigger | None:
    """ "Until end of turn, whenever ..., ..." and "Whenever ... this turn, ...": the triggered ability the rest of the sentence
    is, set up as the spell or ability resolves. The wording of the trigger itself is the permanents' (effects/triggers.py)."""
    from .triggers import _trigger_part, remembered_ability

    if remembered := remembered_ability(sentence):
        return CreateDelayedTrigger((remembered[0],), when=remembered[1])
    match = _DELAYED_TRIGGER.fullmatch(sentence)
    if not match:
        return None
    body = match[1] or f"{match[2]}, {match[3]}"
    found = _trigger_part(body, body)
    return CreateDelayedTrigger(tuple(found), next_turn="your next turn" in sentence.lower()) if found else None


def _template(sentence: str) -> Any:
    """The effect of one sentence a template understands as written, or None."""
    for pattern, build in _TEMPLATES:
        match = pattern.fullmatch(sentence)
        effect = build(match) if match else None
        if effect is not None:
            return effect
    return _delayed_trigger(sentence)


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
            if i + 1 < len(effects) and isinstance(effects[i + 1], _IfYouDo):  # Springbloom Druid
                merged.append(MaySacrificeThen(effects[i].kind, effects[i + 1].effect))
                i += 2
                continue
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
        if isinstance(effect, VoteStart) and effect.options is not None:
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
        if isinstance(effect, KickedReplaces) and not i:
            return None
    merged = _merge_no_regen(effects)
    for merge in (_merge_three_way, _merge_copy, _merge_control, _merge_impulse, _merge_votes, _merge_hand_discard, _merge_animate, _merge_mana_drain, _merge_exile, _merge_put_back, _merge_loot, _merge_conditional, _merge_drain, _merge_wipe_gift, _merge_reveal_top, _merge_token_counters, _merge_new_target, _merge_stun_self, _merge_stun, _merge_attacking_tokens, _merge_prevention, _merge_token_copies, _merge_target_copies):  # each returns None for a line it rejects
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


def _merge_stun_self(effects: list) -> list:
    """"Whenever this creature attacks, put a stun counter on it.": with no earlier effect to follow, "it" is the creature itself."""
    merged: list = []
    for effect in effects:
        aimed = any(target_kind(e) or uses_subject(e) or uses_player(e) for e in merged)
        merged.append(PutStunOnSource(effect.count) if isinstance(effect, PutStunCounters) and not aimed else effect)
    return merged


def _merge_new_target(effects: list) -> list | None:
    """"Change the target of target spell that targets only a player. The new target must be a player." is one effect; a lone
    "The new target must be ..." has nothing to refer to, so the line isn't understood."""
    merged: list = []
    for effect in effects:
        if not isinstance(effect, NewTargetMustBe):
            merged.append(effect)
        elif merged and isinstance(merged[-1], ChangeTarget) and not merged[-1].to:
            merged[-1] = dataclasses.replace(merged[-1], to=effect.kind)
        else:
            return None
    return merged


def _merge_stun(effects: list) -> list | None:
    """"Tap up to two target creatures. Put a stun counter on each of them." is a stun counter after each tap; a lone "each of
    them" has nothing to refer to, so the line isn't understood."""
    merged: list = []
    for effect in effects:
        if not isinstance(effect, PutStunOnEach):
            merged.append(effect)
            continue
        taps: list = []
        while merged and isinstance(merged[-1], Tap):
            taps.insert(0, merged.pop())
        if not taps:
            return None
        for tap in taps:
            merged += [tap, PutStunCounters(effect.count)]
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


@dataclass(frozen=True)
class Condition:
    """An intervening "if" clause, checked when the ability triggers and again when it resolves."""
    kind: str  # "graveyard_left", "gained_life", "opponent_more_lands", "opponent_more_creatures", "spell_mv_at_least", "target_power_at_least", "opponent_dealt_noncombat_damage", "cast_this_turn", "control_at_least",
    #            "control_none", "control_none_token", "kicked", "your_turn", "monarch", "hand_at_least", "hand_none", "no_counter",
    #            "gained_life_at_least", "creatures_died", "control_color_at_least", "not_prepared", "not_renowned", "foretold", "no_spell_cast_turn", "delirium", "each_life_at_most", "source_equipped", "no_spells_last_turn", "two_spells_last_turn", "day", "night", "subject_greater", "citys_blessing", "graveyard_at_least", "any_hand_at_most", "opponent_more_cards", "land_entered", "lands_prime", "attackers_at_most", "defender_more_life", "player_more_lands", "x_at_least", "has_exiled_with", "in_graveyard"
    count: int = 0
    what: str = ""  # a spell kind ("instant or sorcery spell") or a type ("Plains", "Snake", "creature")
    also: "Condition | None" = None  # "if A and B": this one and that one must both hold


def _singular(word: str) -> str:
    return word if word.endswith("ss") or word.lower() == "plains" else word.removesuffix("s")


_CONDITIONS = [
    (re.compile(r"each player has no cards in hand"), lambda m: Condition("all_hands_empty")),
    (re.compile(r"creatures you control have total power (\d+) or greater"), lambda m: Condition("creature_power_at_least", int(m[1]))),
    (re.compile(r"you control a creature with power (\d+) or greater"), lambda m: Condition("creature_with_power", int(m[1]))),
    (re.compile(r"you created a token this turn"), lambda m: Condition("created_token")),
    (re.compile(r"a library has (twenty|\d+) or fewer cards in it"),
     lambda m: Condition("any_library_at_most", 20 if m[1] == "twenty" else int(m[1]))),
    (re.compile(r"an opponent was dealt (\d+) or more damage this turn"), lambda m: Condition("opponent_damage_at_least", int(m[1]))),
    (re.compile(rf"you attacked with {_N_FIXED} or more creatures this turn"), lambda m: Condition("attacked_with_at_least", _number(m[1]))),
    (re.compile(r"a card left your graveyard this turn"), lambda m: Condition("graveyard_left")),
    (re.compile(r"a land entered the battlefield under your control this turn"), lambda m: Condition("land_entered")),
    (re.compile(r"you control a prime number of lands"), lambda m: Condition("lands_prime")),
    (re.compile(r"you gained life this turn"), lambda m: Condition("gained_life")),
    (re.compile(rf"you(?:'ve)? gained {_N_FIXED} or more life this turn"), lambda m: Condition("gained_life_at_least", _number(m[1]))),
    (re.compile(rf"{_N_FIXED} or more creatures died this turn"), lambda m: Condition("creatures_died", _number(m[1]))),
    (re.compile(r"an opponent controls more lands than you"), lambda m: Condition("opponent_more_lands")),
    (re.compile(rf"X is {_N_FIXED} or more"), lambda m: Condition("x_at_least", _number(m[1]))),
    (re.compile(r"this card is in your graveyard"), lambda m: Condition("in_graveyard")),
    (re.compile(r"that player controls more lands than you"), lambda m: Condition("player_more_lands")),
    (re.compile(r"an opponent controls more creatures than you"), lambda m: Condition("opponent_more_creatures")),
    (re.compile(rf"that spell's mana value is {_N_FIXED} or greater"), lambda m: Condition("spell_mv_at_least", _number(m[1]))),
    (re.compile(rf"that creature has power {_N_FIXED} or greater"), lambda m: Condition("target_power_at_least", _number(m[1]))),
    (re.compile(r"you've cast an? (instant or sorcery spell|creature spell|noncreature spell|spell) this turn"),
     lambda m: Condition("cast_this_turn", what=m[1])),
    (re.compile(rf"you control {_N_FIXED} or more (white|blue|black|red|green) permanents"),
     lambda m: Condition("control_color_at_least", _number(m[1]), m[2])),
    (re.compile(rf"you control {_N_FIXED} or more ([A-Za-z]+)"),
     lambda m: Condition("control_at_least", _number(m[1]), _singular(m[2]))),
    (re.compile(r"you control no creatures with ([a-z]+)"), lambda m: Condition("control_none_keyword", what=m[1])),
    (re.compile(r"you control no ([A-Za-z]+)"), lambda m: Condition("control_none", what=_singular(m[1]))),
    (re.compile(r"you don't control an? ([A-Za-z]+) creature token"), lambda m: Condition("control_none_token", what=m[1])),
    (re.compile(r"you control an? ([A-Za-z]+) or an? ([A-Za-z]+)"), lambda m: Condition("control_at_least", 1, f"{m[1]} or {m[2]}")),
    (re.compile(r"you control an? ([A-Za-z]+)"), lambda m: Condition("control_at_least", 1, _singular(m[1]))),
    (re.compile(r"it's your turn"), lambda m: Condition("your_turn")),
    (re.compile(r"it's not a token"), lambda m: Condition("source_not_token")),
    (re.compile(r"you control no other creatures"), lambda m: Condition("control_no_other", what="creature")),
    (re.compile(r"that player didn't cast an? ([a-z]+) spell this turn"), lambda m: Condition("player_cast_none", what=m[1])),
    (re.compile(rf"that player has {_N_FIXED} or fewer cards in hand"), lambda m: Condition("player_hand_at_most", _number(m[1]))),
    (re.compile(rf"(?:{_SELF}) has no {_COUNTER} on it"), lambda m: Condition("source_no_counters", what=_counter_name(m[1]))),
    (re.compile(rf"(?:it|{_SELF}) has {_N_FIXED} or more {_COUNTER} on it"),
     lambda m: Condition("source_counters_at_least", _number(m[1]), _counter_name(m[2]))),
    (re.compile(r"you're the monarch"), lambda m: Condition("monarch")),
    (re.compile(rf"you have {_N_FIXED} or more cards in hand"), lambda m: Condition("hand_at_least", _number(m[1]))),
    (re.compile(r"you have no cards in hand"), lambda m: Condition("hand_none")),
    (re.compile(rf"(?:{_SELF}|he|she) was kicked(?: with its ({_MANA_SYMBOLS}) kicker)?"),
     lambda m: Condition("kicked", what=m[1] or "")),
    (re.compile(r"you have the city's blessing"), lambda m: Condition("citys_blessing")),
    (re.compile(rf"{_SELF} isn't prepared"), lambda m: Condition("not_prepared")),
    (re.compile(r"(?:it|that creature) has greater power or toughness than (?:this creature|CARDNAME)"), lambda m: Condition("subject_greater")),
    (re.compile(rf"{_SELF} isn't renowned"), lambda m: Condition("not_renowned")),
    (re.compile(r"this spell was foretold"), lambda m: Condition("foretold")),
    (re.compile(r"you didn't cast a spell this turn"), lambda m: Condition("no_spell_cast_turn")),
    (re.compile(r"there are four or more card types among cards in your graveyard"), lambda m: Condition("delirium")),
    (re.compile(r"each player has (\d+) or less life"), lambda m: Condition("each_life_at_most", int(m[1]))),
    (re.compile(rf"{_SELF} is equipped"), lambda m: Condition("source_equipped")),
    (re.compile(r"no spells were cast last turn"), lambda m: Condition("no_spells_last_turn")),
    (re.compile(r"a player cast two or more spells last turn"), lambda m: Condition("two_spells_last_turn")),
    (re.compile(r"it's (day|night)"), lambda m: Condition(m[1])),
    (re.compile(rf"{_SELF} is tapped"), lambda m: Condition("source_tapped")),
    (re.compile(r"you control no other ([A-Za-z]+)"), lambda m: Condition("control_no_other", what=_singular(m[1]))),
    (re.compile(r"you cast it"), lambda m: Condition("cast_it")),
    (re.compile(r"a modified creature died under your control this turn"), lambda m: Condition("modified_died")),
    (re.compile(rf"{_N_FIXED} or more of those creatures are attacking you and/or planeswalkers you control"),
     lambda m: Condition("attackers_at_least", _number(m[1]))),
    (re.compile(r"none of those creatures attacked you"), lambda m: Condition("attackers_at_most", 0)),
    (re.compile(r"that opponent has more life than another of your opponents"), lambda m: Condition("defender_more_life")),
    (re.compile(r"you were the monarch as the turn began"), lambda m: Condition("monarch_at_turn_start")),
    # Eminence: the ability only works from those two zones, which is where the game looks for it.
    (re.compile(rf"{_SELF} is in the command zone or on the battlefield"), lambda m: Condition("eminence")),
    (re.compile(rf"(?:there are {_N_FIXED} or more cards in your graveyard|{_N_FIXED} or more cards are in your graveyard)"),
     lambda m: Condition("graveyard_at_least", _number(m[1] or m[2]), "card")),
    (re.compile(r"an opponent was dealt noncombat damage this turn"), lambda m: Condition("opponent_dealt_noncombat_damage")),
    (re.compile(rf"there are {_N_FIXED} or more ([a-z]+(?: and/or [a-z]+)?) cards in your graveyard"),
     lambda m: Condition("graveyard_at_least", _number(m[1]), m[2].replace(" and/or ", " or "))),
    (re.compile(rf"a player has {_N_FIXED} or fewer cards in hand"), lambda m: Condition("any_hand_at_most", _number(m[1]))),
    (re.compile(r"an opponent has more cards in hand than you"), lambda m: Condition("opponent_more_cards")),
    (re.compile(rf"an opponent has {_N_FIXED} or less life"), lambda m: Condition("opponent_life_at_most", _number(m[1]))),
]


def _condition(text: str) -> Condition | None:
    for pattern, build in _CONDITIONS:
        if m := pattern.fullmatch(text):
            return build(m)
    first, _, rest = text.partition(" and ")  # "if A and B": both must hold (Zimone)
    while rest:
        if (head := _condition(first)) is not None and (tail := _condition(rest)) is not None:
            return dataclasses.replace(head, also=tail)
        more, _, rest = rest.partition(" and ")
        first = f"{first} and {more}"
    return None


_SPELL_MASTERY = re.compile(r"^Spell mastery \u2014 ")  # the condition stays in the sentence; the ability word is only a label


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


_SPELL_COLORS = re.compile(r"the number of colors that spell is", re.I)  # Mana Cannons
