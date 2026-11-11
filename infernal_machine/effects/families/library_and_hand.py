"""Effects of the "library and hand" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...analysis import is_land
from ...cards import Card
from ...characteristics import Modifier
from ..common import Quantity
from ..targets import PLAYER, PREVIOUS_TARGET, SOURCE, SUBJECT
from .base import Condition
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class Draw:
    count: Quantity
    more: int = 0  # Zimone: "If you control eight or more lands, draw two cards instead."
    more_if: "Condition | None" = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = self.more if self.more_if and game.condition_holds(self.more_if, controller, game.resolving_source) else self.count
        game.draw(controller, game.amount(count))


@dataclass(frozen=True)
class DelayedDraw:
    """Arcane Denial: "Its controller may draw up to two cards at the beginning of the next turn's upkeep. / You draw a card at the
    beginning of the next turn's upkeep." Its controller is the controller of the spell just countered."""
    count: int
    others: bool  # the countered spell's controller rather than you
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        who = (target.controller if target is not None else None) if self.others else controller
        if who is not None:
            game.draw_at_next_upkeep(who, self.count, up_to=self.others)


@dataclass(frozen=True)
class PutSourceOnLibraryTop:
    """Sensei's Divining Top: "... then put this artifact on top of its owner's library." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_on_library_top(target)


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
class DiscardUnless:
    """Thirst for Knowledge: "Then discard two cards unless you discard an artifact card." (Steamcore Scholar: "... an instant or sorcery
    card or a creature card with flying."): one card of one of `kinds`, or `count` cards."""
    count: int
    kinds: tuple[str, ...]

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.discard_unless(controller, self.count, self.kinds)


@dataclass(frozen=True)
class EachPutsFromHand:
    """Show and Tell: "Each player may put an artifact, creature, enchantment, or land card from their hand onto the battlefield." """
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.each_puts_from_hand(self.kind)


@dataclass(frozen=True)
class MayDiscardOrSacrificeLandThenDraw:
    """Highway Robbery: "You may discard a card or sacrifice a land. If you do, draw two cards." """
    draw: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.may_discard_or_sacrifice_land_to_draw(controller, self.draw)


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
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.may_remove_counter_draw(controller, target, self.counter, self.draw)


@dataclass(frozen=True)
class _IfYouDoDraw:
    """The other half."""
    draw: int = 1
    mill: int = 0


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


EXILE_DISCARDED_PROMPT = PromptKind("exile_discarded", "Exile which discarded card from your graveyard?")


@dataclass(frozen=True)
class ImprintFromHand:
    """Chrome Mox: "Imprint \u2014 When this artifact enters, you may exile a nonartifact, nonland card from your hand." The card
    stays with the Mox, whose mana is any of its colors. Isochron Scepter: "an instant card with mana value 2 or less" (`instant_max_mv`)."""
    instant_max_mv: int | None = None
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.imprint_from_hand(controller, target, self.instant_max_mv)


@dataclass(frozen=True)
class EachSacrificesOrDiscards:
    """Plaguecrafter: "Each player sacrifices a creature or planeswalker of their choice. Each player who can't discards a card." """
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if not game.sacrifice(seat, self.kind):
                game.discard(seat, 1)


@dataclass(frozen=True)
class PutFromHand:
    """ "You may put a creature card from your hand onto the battlefield." """
    kind: str
    tapped: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.put_from_hand(controller, self.kind, self.tapped)


@dataclass(frozen=True)
class PutCreatureFromHand:
    """Flash: "You may put a creature card from your hand onto the battlefield. If you do, sacrifice it unless you pay its
    mana cost reduced by {2}." """
    reduction: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.put_creature_from_hand(controller, self.reduction)


@dataclass(frozen=True)
class MillThenReturn:
    """ "Mill four cards, then (you may) return a creature card (and a land card) from your graveyard to your hand / the battlefield
    (tapped)." The player picks each card among those in the graveyard, including what was just milled."""
    count: Quantity
    kinds: tuple[str, ...]
    to: str  # "hand" or "battlefield"
    tapped: bool = False
    optional: bool = False  # "then you may return" (Tyvar, Jubilant Brawler): the player may take none

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.mill_then_return(controller, game.amount(self.count), self.kinds, self.to, self.tapped, self.optional)


@dataclass(frozen=True)
class ExileTopCastOrDamage:
    """Chandra, Torch of Defiance: "Exile the top card of your library. You may cast that card. If you don't, Chandra deals 2 damage
    to each opponent." """
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top_cast_or_damage(controller, self.amount, game.resolving_source)


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
class PutAttackingFromHand:
    """Kaalia of the Vast: "put an Angel, Demon, or Dragon creature card from your hand onto the battlefield tapped and
    attacking that opponent." The opponent is the player the trigger was about."""
    types: tuple[str, ...]
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_attacking_from_hand(controller, target, self.types)


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
class _InsteadTake:
    """Flow State: "If there is an instant card and a sorcery card in your graveyard, instead put two of them into your hand and the
    rest on the bottom of your library in any order." (folded into the Impulse before it, see _merge_conditional)"""
    condition: "Condition"
    count: int  # 0: every card looked at (Accumulate Wisdom: "Put each of those cards into your hand instead if ...")


@dataclass(frozen=True)
class _InsteadDraw:
    """ "If you control eight or more lands, draw two cards instead." (see _merge_conditional)"""
    condition: "Condition"
    count: int


@dataclass(frozen=True)
class LookAtHand:
    """Gitaxian Probe: "Look at target player's hand." Only its controller learns anything."""
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            controller.player.notify({"event": "hand", "seat": target.index, "cards": [c.name for c in target.hand]})


@dataclass(frozen=True)
class EachDrawsThenDiscards:
    """Geier Reach Sanitarium: "Each player draws a card, then discards a card." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            game.draw(seat, 1)
            game.discard(seat, 1)


@dataclass(frozen=True)
class DrawThenPutBack:
    """Brainstorm: "Draw three cards, then put two cards from your hand on top of your library in any order." """
    draw: int
    put: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.draw(controller, self.draw)
        game.put_back_from_hand(controller, self.put)


@dataclass(frozen=True)
class DiscardUnlessSourceEntered:
    """Moon-Circuit Hacker: "... you may draw a card. If you do, discard a card unless this creature entered this turn." (the "you may"
    is the trigger's own, so "if you do" is always true by now)."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or target.entered_turn != game.turn:
            game.discard(controller, 1)


@dataclass(frozen=True)
class Discard:
    """ "Discard a card." / "Each opponent discards two cards." / "Each player discards their hand." (count None) """
    count: int | str | None
    who: str  # "you", "each opponent" or "each player"
    random: bool = False  # "at random"
    draw_per_unable: bool = False  # Refurbished Familiar: "For each opponent who can't, you draw a card."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        unable = 0
        for seat in game.turn_order_from_active():
            if self.who == "each player" or (self.who == "you") == (seat is controller):
                unable += not seat.hand
                game.discard(seat, None if self.count is None else game.amount(self.count), self.random)
        if self.draw_per_unable and unable:
            game.draw(controller, unable)


@dataclass(frozen=True)
class _DrawPerUnable:
    """ "For each opponent who can't, you draw a card." after an each-opponent Discard (see _CONDITIONAL)."""


@dataclass(frozen=True)
class _StunPerNonlandDiscard:
    """Marker: "When you discard one or more nonland cards this way, tap up to that many target creatures and put a stun counter on
    each of them." (Seasoned Cryomancer); folded into the Discard before it as DiscardThenStun."""
    kind: str = "creature"


@dataclass(frozen=True)
class DiscardThenStun:
    """Seasoned Cryomancer: discard `count` cards, then tap and stun up to as many creatures as nonland cards were discarded. The
    creatures are chosen when the number is known (a reflexive trigger, CR 603.12), so they are not targets of the enters trigger."""
    count: int | str
    kind: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        discarded = game.discard(controller, game.amount(self.count))
        many = sum(1 for card in discarded if not is_land(card))
        if many:
            source = game.resolving_source
            game.tap_and_stun_up_to(controller, many, self.kind, source.card.name if source is not None else "the ability")


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


MAY_DRAW_PROMPT = PromptKind("may_draw", "Draw a card from ")  # followed by the source's name; options are Yes and No


@dataclass(frozen=True)
class GreatestPowerMayDraw:
    """Selvala, Heart of the Wilds: "its controller may draw a card if its power is greater than each other creature's power." The
    creature that entered is the subject; its power is compared, as the trigger resolves, with every other creature's, and its
    controller (not the trigger's) chooses."""
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or (owner := game.controller_of(target)) is None:  # it left the battlefield
            return
        power = game.power(target)
        if any(game.power(p) >= power for seat in game.seats for p in seat.battlefield
               if p is not target and "Creature" in p.card.type_line):
            return
        source = game.resolving_item.card.name if game.resolving_item is not None else "this ability"
        if owner.player.choose(MAY_DRAW_PROMPT(source), ["Yes", "No"]) == 0:
            game.draw(owner, 1)


