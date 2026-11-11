"""Effects that return a card or permanent: to the battlefield, to a hand, from a graveyard (split from exile_and_return.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..targets import DEAD_SOURCE, DEAD_SUBJECT, MassFilter, PREVIOUS_TARGET, SOURCE, SOURCE_AND_SUBJECT
from ...prompts import PromptKind
from .base import Condition

if TYPE_CHECKING:
    from ...game import Game, Seat


RETURN_LAND_PROMPT = PromptKind("return_land", "Return which land to your hand? ")


@dataclass(frozen=True)
class ReturnLater:
    """ "Return it to the battlefield under its owner's control at the beginning of the next end step." Only ever the
    end of an Exile (see _merge_exile)."""
    to: str
    under_owner: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone delayed return is never built")


@dataclass(frozen=True)
class CraftReturn:
    """Craft: "Return this card transformed under its owner's control." The card was exiled as a cost; it comes back on its back face."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_source
        if source is None:
            return
        card, owner = source.card, source.owner or controller
        if any(c is card for c in owner.exile):  # (a card that left exile meanwhile stays where it is)
            owner.exile.remove(card)
            game._enter(owner, game._transformed_permanent(card, owner))


@dataclass(frozen=True)
class ReturnExiledToGraveyard:
    """Hofri Ghostforge's token: "When this token leaves the battlefield, return the exiled card to its owner's graveyard." """
    binds = DEAD_SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_exiled_with_to_graveyard(target)


@dataclass(frozen=True)
class ReturnSelfToBattlefield:
    """ "When this creature dies, return it to the battlefield (tapped)." It comes back as a new object under its
    owner's control; a token is gone for good."""
    tapped: bool = False
    binds = DEAD_SOURCE

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
    def binds(self) -> str | None:
        return DEAD_SOURCE if self.dies else SOURCE

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
    binds = DEAD_SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_dead_to_battlefield(target, controller, under_owner=True, enchantment=True)


@dataclass(frozen=True)
class ReturnChosen:
    """ "Return a creature card from your graveyard to your hand.": you choose, it is not targeted."""
    kind: str
    to: str  # "hand"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_chosen(controller, self.kind, self.to)


@dataclass(frozen=True)
class ReturnDeadAtNextUpkeep:
    """Phytotitan: "When this creature dies, return it to the battlefield tapped under its owner's control at the beginning of
    their next upkeep." The card is in the graveyard when this resolves."""
    binds = DEAD_SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_at_next_upkeep(target)


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
class ReturnAnyNumber:
    """Paradoxical Outcome: "Return any number of target nonland, nontoken permanents you control to their owners' hands." and, with
    `draw`, "Draw a card for each card returned to your hand this way." (a card that goes to another owner's hand is not counted)."""
    target: str
    draw: bool = False
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        before = len(controller.hand)
        game.return_all_to_hand([p for p in target or [] if game.on_battlefield(p)])
        if self.draw:
            game.draw(controller, len(controller.hand) - before)


@dataclass(frozen=True)
class _DrawPerReturned:
    """ "Draw a card for each card returned to your hand this way." after ReturnAnyNumber (see _CONDITIONAL)."""


@dataclass(frozen=True)
class ReturnPerOpponent:
    """The Theorist, Jace Beleren: "For each opponent, return up to one target artifact or creature that player controls to its
    owner's hand." The targets are one list, a permanent (or none) for each opponent in turn order."""
    target: str = "artifact or creature"
    per_player = "opponent"
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in target or []:
            game.return_to_hand(permanent)


@dataclass(frozen=True)
class ReturnToHand:
    """Bounce: "Return target nonland permanent you don't control to its owner's hand." """
    target: str
    another: bool = False  # "Return another target creature ...": not the source itself
    optional_target: bool = False  # "Return up to one target creature ...": the target may be left out
    distinct: bool = False  # "Return up to two target creatures ...": the second can't be the first again
    draw_if_yours: bool = False  # Boomerang Basics: "If you controlled that permanent, draw a card."
    counter_on_source: str = ""  # Nurturing Pixie: "If a permanent was returned this way, put a +1/+1 counter on this creature."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        if hasattr(target, "physical"):  # Sink into Stupor: a spell on the stack
            ReturnSpellToHand().resolve(game, controller, target)
        else:
            yours = game.controller_of(target) is controller
            game.return_to_hand(target)
            if self.draw_if_yours and yours:
                game.draw(controller, 1)
            source = game.resolving_source
            if self.counter_on_source and source is not None:
                game.put_counters(source, self.counter_on_source, 1)


@dataclass(frozen=True)
class _CounterIfReturned:
    """ "If a permanent was returned this way, put a +1/+1 counter on this creature." after a ReturnToHand (Nurturing Pixie)."""
    counter: str


@dataclass(frozen=True)
class _DrawIfYouControlledIt:
    """ "If you controlled that permanent, draw a card." after a ReturnToHand (see _CONDITIONAL)."""


@dataclass(frozen=True)
class ReturnAllToHand:
    kind: str
    restriction: MassFilter | None = None  # Perplexing Test: "all creature tokens" / "all nontoken creatures"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_all_to_hand(game.mass_targets(self.kind, controller, self.restriction))


@dataclass(frozen=True)
class ReturnUpToTotalManaValue:
    """Lively Dirge: "Return up to two creature cards with total mana value 4 or less from your graveyard to the battlefield." """
    count: int
    kind: str
    total: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_up_to_total_mana_value(controller, self.count, self.kind, self.total)


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
    battlefield_if: Condition | None = None  # Stitch Together: "Return that card ... to the battlefield instead if ..."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            to = "battlefield" if self.battlefield_if is not None and game.condition_holds(self.battlefield_if, controller) else self.to
            game.return_from_graveyard(target, controller, to, self.tapped, self.finality, counter=self.counter)


@dataclass(frozen=True)
class _ToBattlefieldInstead:
    """ "Threshold \u2014 Return that card from your graveyard to the battlefield instead if ..." after a ReturnFromGraveyard to the hand."""
    condition: Condition


@dataclass(frozen=True)
class ReturnOwnLand:
    """Bounceland: "Return a land you control to its owner's hand." (you choose; it can be the land itself). Whitemane Lion: a creature."""
    kind: str = "Land"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        lands = [p for p in controller.battlefield if self.kind in p.card.type_line]
        if lands:
            game.return_to_hand(lands[controller.player.choose(RETURN_LAND_PROMPT, [game.label(p) for p in lands])])


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
class ReturnWithCounter:
    """Persist and undying: the creature that died comes back with a counter on it. With no counter and `tapped`, Malakir Rebirth's
    "return it to the battlefield tapped under its owner's control"."""
    counter: str = ""  # "-1/-1" (persist) or "+1/+1" (undying)
    tapped: bool = False
    binds = DEAD_SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_with_counter(target, self.counter, self.tapped)


@dataclass(frozen=True)
class ReturnWhenItDiesThisTurn:
    """Malakir Rebirth: 'Until end of turn, that creature gains "When this creature dies, return it to the battlefield tapped under its
    owner's control."' (the game puts that trigger on the stack if the creature dies this turn)"""
    binds = PREVIOUS_TARGET

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
class ReturnSelfToHand:
    """Rancor: "When this Aura is put into a graveyard from the battlefield, return it to its owner's hand." (and "When
    enchanted creature dies, return this Aura ..."). It is already in the graveyard when this resolves."""
    binds = DEAD_SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        if game.on_battlefield(target):  # Mana Bloom: "return it to its owner's hand" from the battlefield
            game.return_to_hand(target)
        else:
            game.return_to_hand_from_graveyard(target.card)


@dataclass(frozen=True)
class ReturnDeadToBattlefield:
    """Changing Loyalty and Gift of Immortality: "When enchanted creature dies, return it / that card to the battlefield
    under your / its owner's control." It is already in the graveyard when this resolves."""
    under_owner: bool
    binds = DEAD_SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_dead_to_battlefield(target, controller, self.under_owner)


@dataclass(frozen=True)
class ReturnAuraToBattlefield:
    """Screams from Within, Ghoulish Impetus and Gift of Immortality: "When enchanted creature dies, return this card
    [from your graveyard] to the battlefield [attached to that creature] [at the beginning of the next end step]." """
    when: str = "now"  # or "end_step"
    to_host: bool = False  # it comes back attached to the creature that died (which came back first); otherwise you choose
    binds = SOURCE_AND_SUBJECT  # resolves with (the Aura, the creature that died)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_aura(target[0], controller, self.when, target[1] if self.to_host else None)


@dataclass(frozen=True)
class SacrificeUnlessReturnLand:
    """The Karoo cycle: "When this land enters, sacrifice it unless you return an untapped Mountain you control to its owner's hand." """
    land_type: str
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.karoo(controller, target, self.land_type)


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
