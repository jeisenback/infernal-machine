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


BASIC_LAND_TYPES = ("Plains", "Island", "Swamp", "Mountain", "Forest")


@dataclass(frozen=True)
class TargetControllerMayFetchBasicLand:
    """Path to Exile: "Its controller may search their library for a basic land card, put it onto the battlefield tapped, ..."
    (Assassin's Trophy puts it onto the battlefield untapped)"""
    tapped: bool = True
    typed: bool = False  # Boseiju: "a land card with a basic land type" (a dual land counts)
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.fetch_basic_land(target.last_controller, optional=True, tapped=self.tapped,
                                  subtypes=BASIC_LAND_TYPES if self.typed else None)


EXILE_DISCARDED_PROMPT = PromptKind("exile_discarded", "Exile which discarded card from your graveyard?")


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
class DanceWithCalamity:
    """ "Shuffle your library. As many times as you choose, you may exile the top card of your library. If the total mana
    value of the cards exiled this way is 13 or less, you may cast any number of spells from among those cards without
    paying their mana costs." """
    limit: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.dance_with_calamity(controller, self.limit)


@dataclass(frozen=True)
class ImprintFromHand:
    """Chrome Mox: "Imprint \u2014 When this artifact enters, you may exile a nonartifact, nonland card from your hand." The card
    stays with the Mox, whose mana is any of its colors."""
    binds = SOURCE

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
class RevealTopPutAll:
    """Goblin Ringleader: "Reveal the top four cards of your library. Put all Goblin cards revealed this way into your hand and the
    rest on the bottom of your library in any order." (the order of the rest is the order they were revealed in); Muxus puts
    "all Goblin creature cards with mana value 5 or less from among them onto the battlefield" instead."""
    count: int
    kind: str  # "goblin", "creature", "goblin creature|mv<=5", ...
    to: str = "hand"  # or "battlefield"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        revealed = [controller.library.pop(0) for _ in range(min(self.count, len(controller.library)))]
        game.broadcast({"event": "revealed_top", "seat": controller.index, "cards": [c.name for c in revealed]})
        for card in revealed:
            if not _card_matches_kind(self.kind, card):
                controller.library.append(card)
            elif self.to == "battlefield":
                game.put_onto_battlefield(controller, card)
            else:
                controller.hand.append(card)


def _card_matches_kind(kind: str, card: Card) -> bool:
    from ...filters import parse_filter

    return parse_filter(kind).matches(card)


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
class PilesOfFour:
    """Abstract Performance: exile the top four cards face down and the next four face up; an opponent chooses one pile to
    put into your graveyard; you may cast a spell from the other for free and put the rest into your hand."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.choose_piles(controller)


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
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_attacking_from_hand(controller, target, self.types)


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
    count: int


@dataclass(frozen=True)
class _InsteadDraw:
    """ "If you control eight or more lands, draw two cards instead." (see _merge_conditional)"""
    condition: "Condition"
    count: int


@dataclass(frozen=True)
class SearchLibrary:
    """ "Search your library for a creature card, put it into your hand, then shuffle." """
    card_type: str  # "card", "creature", "instant or sorcery", "basic land", ...
    to: str  # "hand", or "top" of the library after shuffling
    reveal: bool  # "reveal it": everyone sees which card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tutor(controller, self.card_type, self.to, self.reveal)


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
class LookAtHand:
    """Gitaxian Probe: "Look at target player's hand." Only its controller learns anything."""
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            controller.player.notify({"event": "hand", "seat": target.index, "cards": [c.name for c in target.hand]})


@dataclass(frozen=True)
class ShuffleThisSpell:
    """Green Sun's Zenith: "Shuffle CARDNAME into its owner's library." once it has resolved."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.shuffle_after = True


@dataclass(frozen=True)
class SearchMany:
    """Buried Alive: "Search your library for up to three creature cards, put them into your graveyard, then shuffle."; Goblin
    Recruiter finds "any number of Goblin cards" and puts them "on top in any order"; Tiamat finds "up to five Dragon cards not
    named Tiamat that each have different names"."""
    card_type: str
    count: int | None  # up to this many; None: any number
    to: str  # "hand", "battlefield", "graveyard" or "top" (of the library, in the order the player chooses)
    reveal: bool = False
    distinct: bool = False  # "that each have different names"
    not_self: bool = False  # "not named CARDNAME"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = len(controller.library) if self.count is None else self.count
        game.tutor(controller, self.card_type, self.to, self.reveal, count, distinct=self.distinct, not_self=self.not_self)


@dataclass(frozen=True)
class EachDrawsThenDiscards:
    """Geier Reach Sanitarium: "Each player draws a card, then discards a card." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            game.draw(seat, 1)
            game.discard(seat, 1)


@dataclass(frozen=True)
class LookAtTop:
    """ "Look at the top five cards of your library." Only ever a step of an Impulse (see _merge_impulse)."""
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone look at the top of the library is never built")


@dataclass(frozen=True)
class TakeFromTop:
    """The sentence after a look: "Put one of them into your hand and the rest on the bottom of your library in any
    order." (card_type None), "Put two of them into your hand and the rest into your graveyard." (Stock Up's and Glimpse the
    Future's family, #564: `take` of them, the rest to `rest`; "Put one of those cards into your hand." says where the rest go
    in a later sentence, `rest` None), "You may reveal a creature card from among them and put it into your hand." or "You may
    put a Dragon creature card from among them onto the battlefield." """
    card_type: str | None
    to: str = "hand"  # or "battlefield"
    take: int | str = 1
    rest: str | None = "bottom"  # or "graveyard"; None: the rest-on-the-bottom sentence follows

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone take from the top is never built")


@dataclass(frozen=True)
class RestOnBottom:
    """ "Put the rest on the bottom of your library in a random order." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone put-the-rest is never built")


@dataclass(frozen=True)
class Impulse:
    """Look at the top cards, take one or `take` (into the hand, or onto the battlefield: Ureni of the Unwritten; Dig Through Time's two of
    seven), put the rest on the bottom or into the graveyard (`rest`). Flow State: `more` of them instead when `more_if` holds."""
    count: int | str
    card_type: str | None
    to: str = "hand"
    take: int | str = 1
    rest: str = "bottom"
    more: int = 0
    more_if: "Condition | None" = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        take = self.more if self.more_if and game.condition_holds(self.more_if, controller, game.resolving_source) else self.take
        game.look_at_top(controller, game.amount(self.count), self.card_type, self.to, game.amount(take), self.rest)


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
class LookPutPermanents:
    """Ao, the Dawn Sky: "Look at the top seven cards of your library. Put any number of nonland permanent cards with total
    mana value 4 or less from among them onto the battlefield. Put the rest on the bottom of your library in a random
    order." """
    count: int
    total_mv: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_and_put_permanents(controller, self.count, self.total_mv)


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


@dataclass(frozen=True)
class RevealHand:
    """ "Target opponent reveals their hand." Only ever the start of a TargetChooseDiscard (see _merge_hand_discard)."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone reveal of a hand is never built")


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
class FetchBasicLand:
    untap_if: "Condition | None" = None  # Fabled Passage: "Then if you control four or more lands, untap that land."
    tapped: bool = True  # Prismatic Vista puts it onto the battlefield untapped

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fetch_basic_land(controller, untap_if=self.untap_if, tapped=self.tapped)


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
