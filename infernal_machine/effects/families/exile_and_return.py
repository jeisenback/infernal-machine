"""Effects of the "exile and return" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...cards import Card
from ..common import Quantity
from ..targets import (DEAD_SOURCE, DEAD_SUBJECT, MassFilter, PLAYER, PREVIOUS_TARGET, SOURCE, SOURCE_AND_SUBJECT, binding)
from .copying import copy_of
from .base import Condition
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class ExileTargetIfDies:
    """ "If that creature would die this turn, exile it instead." (Lava Coil, Bleed Dry): the target the spell just dealt with."""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and hasattr(target, "exile_if_dies") and "Creature" in target.card.type_line:
            target.exile_if_dies = game.turn


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
    None, "this turn", "next turn" or "next end step"). With `choose_one` ("Choose one of them."): only the card its controller
    chooses can be played."""
    count: int | str
    play: str | None = None
    choose_one: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top(controller, game.amount(self.count), self.play, self.choose_one)


@dataclass(frozen=True)
class _ChooseOneOfThem:
    """ "Choose one of them." after an ExileTop of several cards (see _merge_exile)."""


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
class ExileEnchanted:
    """Redemption Arc: "Exile enchanted creature." (the Aura's own ability, so no target)"""
    binds = SOURCE

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
class ExileGraveyard:
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_graveyard(target)


@dataclass(frozen=True)
class TargetExiles:
    """ "Target opponent exiles a creature they control and their graveyard." (Strategic Betrayal): the player chooses the
    creature, as for an edict, so hexproof and indestructible don't help; with none, the graveyard still goes."""
    target: str  # "player" or "opponent"
    kind: str = "creature"
    graveyard: bool = False  # "... and their graveyard"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_chosen(target, self.kind)
            if self.graveyard:
                game.exile_graveyard(target)


@dataclass(frozen=True)
class PlayExiledCard:
    """A Hideaway land's "You may play the exiled card without paying its mana cost if <condition>." The condition is
    checked as the ability resolves."""
    condition: "Condition"
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.condition_holds(self.condition, controller, target):
            game.play_hideaway(controller, target)


@dataclass(frozen=True)
class _ExileThemLater:
    """ "Exile them at the beginning of the next end step.": only ever after AttackingTokens."""


@dataclass(frozen=True)
class _PlayTheExiledCard:
    """ "You may play the exiled card this turn." """


@dataclass(frozen=True)
class ReturnExiledToGraveyard:
    """Hofri Ghostforge's token: "When this token leaves the battlefield, return the exiled card to its owner's graveyard." """
    binds = DEAD_SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_exiled_with_to_graveyard(target)


@dataclass(frozen=True)
class PutExiledWithIntoGraveyard:
    """Currency Converter: "Put a card exiled with this artifact into its owner's graveyard. If it's a land card, create a Treasure
    token. If it's a nonland card, create a 2/2 black Rogue creature token." """
    land_token: Card
    nonland_token: Card
    binds = SOURCE
    needs_exiled_with = True  # it can only be activated while a card is exiled with it

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        card = game.put_exiled_with_into_graveyard(controller, target)
        if card is not None:
            game.create_tokens(controller, self.land_token if "Land" in card.type_line else self.nonland_token, 1)


@dataclass(frozen=True)
class CastExiledWithFree:
    """Quintorius: "Choose target card exiled with Quintorius. You may cast that card this turn without paying its mana cost. If
    that spell would be put into a graveyard, put it on the bottom of its owner's library instead." (chosen as it resolves)"""
    bottom_after: bool = True
    binds = SOURCE
    needs_exiled_with = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.cast_exiled_with_free(controller, target, self.bottom_after)


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


FREE_CAST_PROMPT = PromptKind("free_cast", "Cast which spell without paying its mana cost? ")


DECLINE = "Don't cast"


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
class ExileTopOfThatPlayerMayCast:
    """Ragavan: "... exile the top card of that player's library. Until end of turn, you may cast that card." (the player dealt damage)"""
    binds = PLAYER

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
    copy_changes: Any = None  # The Scarab God: "..., except it's a 4/4 black Zombie." (a CopyChanges)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or not game.exile_from_graveyard(target):
            return
        if self.then and self.if_type.capitalize() in target.card.type_line:
            self.then.resolve(game, controller, None)
        if self.copy_token:
            game.create_tokens(controller, copy_of(target.card, self.copy_changes, as_token=True), 1)


@dataclass(frozen=True)
class _IfExiledThen:
    """ "If a creature card is exiled this way, create a ... token." """
    card_type: str
    effect: Any


@dataclass(frozen=True)
class ExileOwnGraveyard:
    """Emeritus of Ideation: "Exile eight cards from your graveyard. If you do, this creature becomes prepared." (the
    trigger is "you may"); nothing happens if there are fewer cards than that."""
    count: int
    then: Any = None

    @property
    def binds(self) -> str | None:
        return SOURCE if self.then and binding(self.then) == SOURCE else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.exile_own_graveyard(controller, self.count) and self.then:
            self.then.resolve(game, controller, target)


RETURN_LAND_PROMPT = PromptKind("return_land", "Return which land to your hand? ")


@dataclass(frozen=True)
class ReturnOwnLand:
    """Bounceland: "Return a land you control to its owner's hand." (you choose; it can be the land itself)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        lands = [p for p in controller.battlefield if "Land" in p.card.type_line]
        if lands:
            game.return_to_hand(lands[controller.player.choose(RETURN_LAND_PROMPT, [game.label(p) for p in lands])])


@dataclass(frozen=True)
class ExileAllGraveyards:
    """ "Exile all cards from all graveyards." (Rest in Peace) """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_all_graveyards()


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
class ExileTopCastAura:
    """Herald of Amity: "Exile the top eight cards of your library. You may cast an Aura spell from among them without paying
    its mana cost. Then put the rest on the bottom of your library in a random order." """
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top_cast_aura(controller, self.count)


@dataclass(frozen=True)
class ExileUntilNonlandCast:
    """Plargg and Nassari: "Each player exiles cards from the top of their library until they exile a nonland card. An
    opponent chooses a nonland card exiled this way. You may cast up to two spells from among the other cards exiled this way
    without paying their mana costs." """
    casts: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_until_nonland_and_cast(controller, self.casts)


@dataclass(frozen=True)
class SacrificeUnlessReturnLand:
    """The Karoo cycle: "When this land enters, sacrifice it unless you return an untapped Mountain you control to its
    owner's hand." """
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
