"""Effects of the "spells and misc" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...characteristics import Modifier
from ..common import cant_be_countered
from ..targets import (DEAD_SUBJECT, PLAYER, PREVIOUS_TARGET, SOURCE, SOURCE_AND_SUBJECT, SUBJECT, binding, target_kind)
from .base import Amount, Condition
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


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
        if self.optional and controller.player.choose(CHANGE_TARGET_PROMPT(target.card.name), ["Yes", "No"]) != 0:
            return
        game.change_target(controller, target, self.every, self.to, self.lone)


CHANGE_TARGET_PROMPT = PromptKind("change_target", "Change the target of ")  # followed by the spell's name; Yes or No


@dataclass(frozen=True)
class NewTargetMustBe:
    """ "The new target must be a player." after a change of target: _merge_new_target folds it into that effect."""
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


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
class _MayRemoveCounter:
    counter: str


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
    mode_costs: tuple[str, ...] = ()  # Spree: the mana each mode adds to the cost of the spell (CR 702.172)


PARITY_PROMPT = PromptKind("parity", "Choose odd or even for ")  # followed by the spell's name; options: "Odd", "Even"


HYPOTHESIS_COUNTER_PROMPT = PromptKind("hypothesis_counter", "Put a +1/+1 counter on a creature for ")  # followed by the spell's name


@dataclass(frozen=True)
class ZimonesHypothesis:
    """Zimone's Hypothesis: "You may put a +1/+1 counter on a creature. Then choose odd or even. Return each creature with
    power of the chosen quality to its owner's hand." (Zero is even.)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        name = game.resolving_item.card.name if game.resolving_item is not None else "Zimone's Hypothesis"
        creatures = [p for s in game.live_seats() for p in s.battlefield if "Creature" in p.card.type_line]
        if creatures:
            options = [game.label(p) for p in creatures] + ["No counter"]
            pick = controller.player.choose(HYPOTHESIS_COUNTER_PROMPT(name), options)
            if pick < len(creatures):
                game.put_counters(creatures[pick], "+1/+1", 1)
        parity = controller.player.choose(PARITY_PROMPT(name), ["Odd", "Even"])
        chosen = [p for s in game.live_seats() for p in s.battlefield if "Creature" in p.card.type_line
                  and game.power(p) % 2 == (1 if parity == 0 else 0)]
        game.return_all_to_hand(chosen)


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
class OnSubject:
    """A watching trigger's effect on "it": the permanent that set it off, not the ability's source."""
    inner: Any
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        self.inner.resolve(game, controller, target)


@dataclass(frozen=True)
class OnSubjectController:
    """A watching trigger's effect on "its controller": the controller of the permanent that set it off (Parasitic Impetus)."""
    inner: Any
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        owner = game.controller_of(target) if target is not None else None
        if owner is not None:
            self.inner.resolve(game, controller, owner)


@dataclass(frozen=True)
class OnPlayer:
    """A trigger's effect on "that player" / "they": the player whose action set it off."""
    inner: Any
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        self.inner.resolve(game, controller, target)


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
    def binds(self) -> str | None:
        return PREVIOUS_TARGET if self.when else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is None or (self.when and target is None):
            return
        for ability in self.abilities:
            game.add_delayed(ability, game.resolving_item, controller, self.next_turn, target if self.when else None, self.when)


@dataclass(frozen=True)
class _TheyGainHaste:
    """ "They gain haste until end of turn.": only ever after AttackingTokens."""


@dataclass(frozen=True)
class _ChooseAnyNumber:
    """ "Choose any number of target creatures you control.": only ever before _CopyEachWithHaste."""
    target: str


@dataclass(frozen=True)
class DefineX:
    """Sets X for the effects after it ("..., where X is the number of Auras you control.")."""
    amount: Amount

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.x_value = game.evaluate(self.amount, controller)


class _GiftMatch:
    """A token specification and whether its quoted ability's closing quote was there (see _create)."""
    def __init__(self, spec: str, quote: str):
        self.spec, self.quote = spec, quote


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
class _ItHas:
    """ "It has "Sacrifice this token: Add {C}."" after a token was created (see _merge_conditional)."""
    ability: str


@dataclass(frozen=True)
class Conditional:
    """ "Then if there are three or more creature cards in your graveyard, this creature becomes prepared.": the effect
    happens only if the condition holds as it resolves."""
    condition: "Condition"
    effect: Any

    @property
    def binds(self) -> str | None:
        return found if (found := binding(self.effect)) in (SOURCE, SUBJECT, PLAYER) else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.condition_holds(self.condition, controller, game.resolving_source):
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class _IfYouDo:
    """ "If you do, <effect>." after an effect that can be declined or fail (see _merge_conditional)."""
    effect: Any


@dataclass(frozen=True)
class PutThisFromCommandZone:
    """Derevi, Empyrial Tactician: "{1}{G}{W}{U}: Put Derevi onto the battlefield from the command zone." The ability works only
    while the card is in the command zone (ActivatedAbility.from_command_zone); it isn't a cast, so no commander tax is paid or added."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        card = item.card if item is not None else None
        if card is not None and any(c is card for c in controller.command_zone):
            controller.command_zone.remove(card)
            game.put_onto_battlefield(controller, card)


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
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class ChooseTarget:
    """Malakir Rebirth: "Choose target creature." The sentences after it say "that creature"."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


COMMANDER_HAND_PROMPT = PromptKind("commander_hand", "Put which commander into your hand? ")


@dataclass(frozen=True)
class UnlessPays:
    """ "Draw a card unless that player pays {1}": the effects happen unless the player who set the trigger off pays.
    Only for effects that need no target, so they run the same either way."""
    effects: tuple
    cost: str
    binds = PLAYER
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
class ChooseFromHand:
    """ "You choose a nonland card (with mana value 3 or less) from it." """
    excluded: tuple[str, ...]  # card types it can't be, lowercase
    max_mv: int | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone choice from a hand is never built")


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
class _KickedInsteadTail:
    """ "If this spell was kicked, that creature gets -5/-5 until end of turn instead." (see _parse): what stands in for the effect before
    it, with "that creature" the target of that effect."""
    text: str


@dataclass(frozen=True)
class KickedReplaces:
    """ "If the gift was promised, instead counter target spell.": when kicked (or its gift promised) these effects stand in for the
    effect just before."""
    effects: tuple


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
    def binds(self) -> str | None:
        return found if (found := binding(self.effect)) in (SOURCE, SUBJECT, SOURCE_AND_SUBJECT, DEAD_SUBJECT, PLAYER) else None  # as Conditional

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if game.pays_optional(controller, self.cost, item.card if item is not None else None):
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class MayPayCountersOnSubject:
    """Emiel the Blessed: "Whenever another creature you control enters, you may pay {G/W}. If you do, put a +1/+1 counter on it. If
    it's a Unicorn, put two +1/+1 counters on it instead." The creature that entered is the subject; the payment is chosen as the
    ability resolves, and only a Unicorn (a creature with the type) gets the second counter."""
    cost: str
    subtype: str
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:  # it left the battlefield before the ability resolved
            return
        item = game.resolving_item
        if game.pays_optional(controller, self.cost, item.card if item is not None else None):
            game.put_counters(target, "+1/+1", 2 if self.subtype in target.card.type_line.partition("\u2014")[2].split() else 1)


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
class GetEmblem:
    """Elspeth, Sun's Champion: "You get an emblem with "Creatures you control get +2/+2 and have flying."" The emblem goes to the
    command zone (CR 114.1) and its text works like a permanent's static or triggered abilities; only built when the engine reads
    that text (effects/outcomes.py checks), so a walker whose emblem it cannot play is not called playable."""
    text: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.get_emblem(controller, self.text)
