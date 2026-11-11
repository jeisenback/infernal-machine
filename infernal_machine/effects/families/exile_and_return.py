"""Effects of the "exile and return" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...analysis import is_land
from ...cards import Card
from ..common import Quantity, colors_spent
from ..targets import MassFilter, PLAYER, PREVIOUS_TARGET, SOURCE, binding, target_kind
from .copying import copy_of
from .base import Condition
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class WishArtifact:
    """Karn, the Great Creator: "You may reveal an artifact card you own from outside the game or choose a face-up artifact card you
    own in exile. Put that card into your hand." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.wish_artifact(controller, game.resolving_source.card.name if game.resolving_source else "")


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
    """Exile a permanent and bring it back: right away ("now") or as the next end step begins ("end_step"), to the battlefield or hand."""
    target: str
    when: str = "now"
    to: str = "battlefield"
    under_owner: bool = True  # "under its owner's control" (otherwise under yours)
    another: bool = False
    counters: int = 0  # Daydream: "... with a +1/+1 counter on it"
    optional_target: bool = False  # The Mind Stone: "up to one other target"
    distinct: bool = False  # Ghostly Flicker: "two target ...": each a different one

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.flicker(target, controller, self.when, self.to, self.under_owner, counters=self.counters)


@dataclass(frozen=True)
class ExileTop:
    """ "Exile the top two cards of your library. Until the end of your next turn, you may play those cards." (`play` is
    None, "this turn", "next turn" or "next end step"). With `choose_one` ("Choose one of them."): only the card its controller
    chooses can be played."""
    count: int | str
    play: str | None = None
    choose_one: bool = False
    leftovers_token: Card | None = None  # Glimpse the Impossible: the cards still exiled at the next end step go to the graveyard, a token each
    free_from_graveyard: bool = False  # Ignite the Future: played without paying their mana costs if this spell was cast from a graveyard
    if_exiled: tuple = ()  # Bonehoard Dracosaur: ("land" | "nonland", effect): "If you exiled a land card this way, create ..."
    spells_only: bool = False  # Apex of Power: "you may cast spells from among them": a land among them can't be played
    only: str = ""  # Rundvelt Hordemaster: "If it's a Goblin creature card, you may cast that card ...": the kind it must be

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        exiled = game.exile_top(controller, game.amount(self.count), self.play, self.choose_one, self.spells_only, self.only)
        for kind, effect in self.if_exiled:
            if any(is_land(card) == (kind == "land") for card in exiled):
                effect.resolve(game, controller, None)
        if self.free_from_graveyard and game.resolving_item is not None and game.resolving_item.from_graveyard:
            controller.exile_free.extend(exiled)
        if self.leftovers_token is not None:
            game.leftovers_to_graveyard_at_end_step(controller, exiled, self.leftovers_token)


@dataclass(frozen=True)
class _LeftoversToGraveyard:
    """ "At the beginning of the next end step, if any of those cards remain exiled, put them into your graveyard, then create a 0/1
    ... Eldrazi Spawn creature token for each card put into your graveyard this way. ..." after an ExileTop (see _merge_exile)."""
    token: Card


@dataclass(frozen=True)
class _FreeIfFromGraveyard:
    """ "If this spell was cast from a graveyard, you may play cards this way without paying their mana costs." after an ExileTop that may
    be played (Ignite the Future; see _merge_exile)."""


@dataclass(frozen=True)
class _ChooseOneOfThem:
    """ "Choose one of them." after an ExileTop of several cards (see _merge_exile)."""


@dataclass(frozen=True)
class PlayExiled:
    """ "You may play it this turn." Only ever the end of an ExileTop (see _merge_exile)."""
    until: str
    spells_only: bool = False  # Apex of Power: "you may cast spells from among them" (not play a land)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone permission to play exiled cards is never built")


@dataclass(frozen=True)
class PhaseOutThat:
    """Slip Out the Back: "Put a +1/+1 counter on target creature. It phases out.": the target of the effect before it."""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.on_battlefield(target):
            game.phase_out(target)


@dataclass(frozen=True)
class ExileThatIf:
    """Dispatch: "Metalcraft \u2014 If you control three or more artifacts, exile that creature.": the target of the effect before it,
    exiled only if the condition holds as it resolves."""
    condition: Condition
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.condition_holds(self.condition, controller, game.resolving_source):
            game.exile_noting(target, game.resolving_source)


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
class ExileUpToXFromGraveyards:
    """Kozilek's Command: "Exile up to X target cards from graveyards." The targets are one list."""
    target: str = "graveyard:card:any"
    up_to_x = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for card in target or []:
            game.exile_from_graveyard(card)


@dataclass(frozen=True)
class PutSourceThirdFromTop:
    """Braided Quipu: "put this artifact into its owner's library third from the top." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game._leave_together([(target, "returned")], destination="library_third")


@dataclass(frozen=True)
class GrantFlashback:
    """Snapcaster Mage, Flashback: "Target instant or sorcery card in your graveyard gains flashback until end of turn. The flashback
    cost is equal to its mana cost." (Game.graveyard_casts_for)"""
    target: str = "graveyard:instant or sorcery:yours"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.seat.flashback_granted.append((target.card, game.turn))


@dataclass(frozen=True)
class ExileUpToNFromGraveyards:
    """Pit of Offerings: "Exile up to three target cards from graveyards." The targets are one list."""
    max_targets: int
    target: str = "graveyard:card:any"
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for card in target or []:
            game.exile_from_graveyard(card)


@dataclass(frozen=True)
class MayExileFromGraveyardThen:
    """Masked Vandal: "You may exile a creature card from your graveyard. If you do, exile target artifact or enchantment an opponent
    controls." The target is chosen as the ability goes on the stack; `then` happens only if a card was exiled."""
    kind: str
    then: Any
    other: bool = False  # Ichorid: "other than this card"

    @property
    def target(self) -> str | None:
        return target_kind(self.then)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if game.may_exile_from_graveyard(controller, self.kind, item.card if self.other and item is not None else None):
            self.then.resolve(game, controller, target)


@dataclass(frozen=True)
class ExileIfConverge:
    """Prismatic Ending: "Converge \u2014 Exile target nonland permanent if its mana value is less than or equal to the number of colors
    of mana spent to cast this spell." """
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if target is not None and item is not None and target.card.cmc <= colors_spent(item.mana_types_spent):
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
class PlayVoidCardFree:
    """Dauthi Voidwalker: "Choose an exiled card an opponent owns with a void counter on it. You may play it this turn without paying its
    mana cost." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.play_void_card_free(controller)


@dataclass(frozen=True)
class MayCastFromHandFree:
    """Rishkar's Expertise: "You may cast a spell with mana value 5 or less from your hand without paying its mana cost." """
    max_value: Quantity  # "X": the damage the trigger saw (Buster Sword)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        most = game.amount(self.max_value)
        spells = [c for c in controller.hand if "Land" not in c.type_line and c.cmc <= most]
        if not spells:
            return
        pick = controller.player.choose(FREE_CAST_PROMPT, [c.name for c in spells] + [DECLINE])
        if pick < len(spells):
            game.cast_free(controller, spells[pick])


FREE_CAST_PROMPT = PromptKind("free_cast", "Cast which spell without paying its mana cost? ")


@dataclass(frozen=True)
class MayCastFromGraveyard:
    """Bilbo, Thief in the Night: "you may cast an artifact, instant, or sorcery spell from your graveyard." Its mana cost is paid. With
    `exile_after`: "If an instant or sorcery spell cast this way would be put into your graveyard, exile it instead." """
    kinds: tuple[str, ...]
    exile_after: bool = False
    free: bool = False  # Sword of Once and Future: "... with mana value 2 or less from your graveyard without paying its mana cost."
    most: int | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.may_cast_from_graveyard(controller, self.kinds, self.exile_after, self.free, self.most)


@dataclass(frozen=True)
class _ExileCastThisWay:
    """ "If an instant or sorcery spell cast this way (that spell) would be put into your graveyard, exile it instead." (Bilbo, Gearhulk)"""


DECLINE = "Don't cast"


@dataclass(frozen=True)
class ExileTopOfThatPlayerMayCast:
    """Ragavan: "... exile the top card of that player's library. Until end of turn, you may cast that card." (the player dealt damage)
    Fallen Shinobi: "that player exiles the top two cards of their library. Until end of turn, you may play those cards without paying their
    mana costs." (`count`, `free`)"""
    count: int = 1
    free: bool = False
    forever: bool = False  # Cunning Rhetoric: "for as long as it remains exiled"
    any_mana: bool = False  # ... and Grenzo, Havoc Raiser: "you may spend mana as though it were mana of any color"
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_top_of_other(controller, target, self.count, self.free, self.forever, any_mana=self.any_mana)


@dataclass(frozen=True)
class ExileTopOfTargetPlayFree:
    """Gix, Yawgmoth Praetor: "Exile the top X cards of target opponent's library. You may play lands and cast spells from among cards
    exiled this way without paying their mana costs." (as the ability resolves)"""
    count: Quantity
    target: str = "opponent"
    spells_most: Quantity | None = None  # Villainous Wealth: "You may cast any number of spells with mana value X or less from among them"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_top_play_free(controller, target, game.amount(self.count), None if self.spells_most is None else game.amount(self.spells_most))


@dataclass(frozen=True)
class ThatPlayerExilesTopCastFree:
    """Mind's Dilation: "that player exiles the top card of their library. If it's a nonland card, you may cast it without paying its mana
    cost." (the player who cast the spell)"""
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_top_cast_nonland_free(controller, target)


@dataclass(frozen=True)
class RevealTopCastKindredFree:
    """Descendants' Path: "reveal the top card of your library. If it's a creature card that shares a creature type with a creature you
    control, you may cast it without paying its mana cost. If you don't cast it, put it on the bottom of your library." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.reveal_top_cast_kindred_free(controller)


@dataclass(frozen=True)
class ExileUntilTotalCastFree:
    """Improvisation Capstone: "Exile cards from the top of your library until you exile cards with total mana value 4 or greater. You may
    cast any number of spells from among them without paying their mana costs." """
    total: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_until_total_cast_free(controller, self.total)


@dataclass(frozen=True)
class ExileTopOfEachCastFree:
    """Etali, Primal Storm: "exile the top card of each player's library, then you may cast any number of spells from among those
    cards without paying their mana costs." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top_of_each_cast_free(controller)


@dataclass(frozen=True)
class ExileAll:
    kind: str
    restriction: MassFilter | None = None
    gives: "GiveBack | None" = None
    until_leaves: bool = False  # Pinnacle Starcage: "... until this artifact leaves the battlefield."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        exiled = game.mass_targets(self.kind, controller, self.restriction)
        if not self.until_leaves:
            game.exile_all(exiled, self.gives, controller)
            return
        source = game.resolving_source
        for permanent in exiled:
            if permanent is not source:
                game.exile_until_leaves(permanent, source)


@dataclass(frozen=True)
class PutLinkedExileIntoGraveyards:
    """Pinnacle Starcage: "Put each card exiled with this artifact into its owner's graveyard, then create a 2/2 ... Robot artifact
    creature token for each card put into a graveyard this way." The cards it holds "until it leaves" go for good."""
    token: Card
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.create_tokens(controller, self.token, game.put_linked_exile_into_graveyards(target))


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
class ExileAttackers:
    """Settle the Wreckage: "Exile all attacking creatures target player controls. That player may search their library for that many
    basic land cards, put those cards onto the battlefield tapped, then shuffle." """
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_attackers(target)


@dataclass(frozen=True)
class ExileFromGraveyard:
    target: str
    if_type: str = ""  # Feral Appetite: "If a creature card is exiled this way, create a ... token": the card type
    then: Any = None  # ... and what happens then
    copy_token: bool = False  # Lorehold Archivist's spell: "Create a token that's a copy of it."
    copy_changes: Any = None  # The Scarab God: "..., except it's a 4/4 black Zombie." (a CopyChanges)
    optional_target: bool = False  # Restless Cottage: "exile up to one target card from a graveyard"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or not game.exile_from_graveyard(target):
            return
        if self.then and self.if_type.capitalize() in target.card.type_line:
            source = game.resolving_source  # Scavenging Ooze: "put a +1/+1 counter on this creature"
            for effect in self.then if isinstance(self.then, tuple) else (self.then,):
                effect.resolve(game, controller, source if binding(effect) == SOURCE and source is not None and game.on_battlefield(source)
                               else None)
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
class ExileTopCastAura:
    """Herald of Amity: "Exile the top eight cards of your library. You may cast an Aura spell from among them without paying
    its mana cost. Then put the rest on the bottom of your library in a random order." """
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top_cast_aura(controller, self.count)


@dataclass(frozen=True)
class SearchExileCastIfKicked:
    """Beseech the Mirror: "Search your library for a card, exile it face down, then shuffle. If this spell was bargained, you may cast
    the exiled card without paying its mana cost if that spell's mana value is 4 or less. Put the exiled card into your hand if it
    wasn't cast this way." (bargain is read as kicker)"""
    max_value: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        for card in game.tutor(controller, "card", "exile", reveal=False):
            if not any(c is card for c in controller.exile):
                continue
            if item is not None and item.kicked and "Land" not in card.type_line and card.cmc <= self.max_value \
                    and controller.player.choose(FREE_CAST_PROMPT, [card.name, DECLINE]) == 0:
                game._cast(controller, card, controller.exile, free=True)
            else:
                controller.exile.remove(card)
                controller.hand.append(card)


@dataclass(frozen=True)
class ExileThisFromGraveyardThen:
    """Creeping Chill: "When this card is put into your graveyard from your library, you may exile it. If you do, ..." (the "may" is the
    trigger's): `then` happens only if the card was still there to exile."""
    then: tuple

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        card = item.card if item is not None else None
        if card is not None and any(c is card for c in controller.graveyard):
            game.exile_card_from_graveyard(controller, card, False)
            for effect in self.then:
                effect.resolve(game, controller, target)


