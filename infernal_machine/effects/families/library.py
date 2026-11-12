"""Effects that search, look at, reveal, scry, surveil, mill or shuffle a library (split from library_and_hand.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..common import Quantity
from ..targets import PREVIOUS_TARGET, SOURCE
from .base import Condition
from ...cards import Card

if TYPE_CHECKING:
    from ...game import Game, Seat


BASIC_LAND_TYPES = ("Plains", "Island", "Swamp", "Mountain", "Forest")


def _card_matches_kind(kind: str, card: Card) -> bool:
    from ...filters import parse_filter

    return parse_filter(kind).matches(card)


@dataclass(frozen=True)
class TargetControllerMayFetchBasicLand:
    """Path to Exile: "Its controller may search their library for a basic land card, put it onto the battlefield tapped, ..."
    (Assassin's Trophy puts it onto the battlefield untapped)"""
    tapped: bool = True
    typed: bool = False  # Boseiju: "a land card with a basic land type" (a dual land counts)
    optional: bool = True  # Magmatic Hellkite: "Its controller searches ..." (no "may")
    stun: bool = False  # ... "puts it onto the battlefield tapped with a stun counter on it"
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.fetch_basic_land(target.last_controller, optional=self.optional, tapped=self.tapped,
                                  subtypes=BASIC_LAND_TYPES if self.typed else None, stun=self.stun)


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
class LookTopTakeChosen:
    """Herald's Horn, Gathering Stone: "Look at the top card of your library. If it's a creature card of the chosen type, you may
    reveal it and put it into your hand." (the type the source chose as it entered)"""
    creature: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_top_take_chosen(controller, game.resolving_source, self.creature)


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
            if not _card_matches_kind(self.kind, card) or (self.to == "battlefield" and game.caged(card)):  # (Grafdigger's Cage)
                controller.library.append(card)
            elif self.to == "battlefield":
                game.put_onto_battlefield(controller, card)
            else:
                controller.hand.append(card)


@dataclass(frozen=True)
class RevealTopToHand:
    """Dark Confidant: "Reveal the top card of your library and put that card into your hand." (not a draw); with `lose_life`, "You lose
    life equal to its mana value." after it (see _CONDITIONAL)."""
    lose_life: bool = False
    only: str = ""  # Summon: Esper Maduin: "If it's a permanent card, put it into your hand." (otherwise it stays on top)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if not controller.library:
            return
        card = controller.library[0]
        game.broadcast({"event": "revealed_top", "seat": controller.index, "cards": [card.name]})
        if self.only and not _card_matches_kind(self.only, card):
            return
        controller.hand.append(controller.library.pop(0))
        if self.lose_life:
            game.change_life(controller, -int(card.cmc))


@dataclass(frozen=True)
class EachExilesAllButBottom:
    """Doomsday Excruciator: "each player exiles all but the bottom six cards of their library face down." """
    keep: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            gone = seat.library[:max(0, len(seat.library) - self.keep)]
            del seat.library[:len(gone)]
            seat.exile.extend(gone)
            game.broadcast({"event": "exiled_from_library", "seat": seat.index, "count": len(gone), "face_down": True})
            if gone:
                game._exiled_from_library_or_graveyard(seat)


@dataclass(frozen=True)
class PilesOfFour:
    """Abstract Performance: exile the top four cards face down and the next four face up; an opponent chooses one pile to
    put into your graveyard; you may cast a spell from the other for free and put the rest into your hand."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.choose_piles(controller)


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
class ShuffleSourceAndTarget:
    """Floodpits Drowner: "Shuffle this creature and target creature with a stun counter on it into their owners' libraries." (With its
    target no longer legal the ability does nothing at all, CR 608.2b, so the creature stays too.)"""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.shuffle_permanents_into_libraries([p for p in (game.resolving_source, target) if p is not None])


@dataclass(frozen=True)
class _InsteadSearch:
    """ "Delirium \u2014 If there are four or more card types among cards in your graveyard, instead search your library for any card, put it
    into your hand, then shuffle." after a SearchLibrary (Demonic Counsel, Traverse the Ulvenwald): the second search replaces the first."""
    condition: Any
    search: Any


@dataclass(frozen=True)
class SearchLibrary:
    """ "Search your library for a creature card, put it into your hand, then shuffle." """
    card_type: str  # "card", "creature", "instant or sorcery", "basic land", ...
    to: str  # "hand", or "top" of the library after shuffling
    reveal: bool  # "reveal it": everyone sees which card
    counters: int = 0  # Neoform: "onto the battlefield with an additional +1/+1 counter on it"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tutor(controller, self.card_type, self.to, self.reveal, counters=self.counters)


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
    each_type: bool = False  # "a Forest card and a Plains card" (Krosan Verge): the nth land has the nth land type

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = game.amount(self.count)  # Traverse the Outlands: up to X
        game.search_for_lands(controller, count, self.subtypes, count if self.battlefield == "X" else game.amount(self.battlefield), self.tapped,
                              self.reveal, self.basic_only, self.share_type, self.each_type)


@dataclass(frozen=True)
class SacrificeLandsSearch:
    """Scapeshift: "Sacrifice any number of lands. Search your library for up to that many land cards, put them onto the battlefield
    tapped, then shuffle." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.sacrifice_lands_then_search(controller)


@dataclass(frozen=True)
class Scry:
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.scry(controller, game.amount(self.count))


@dataclass(frozen=True)
class TargetScriesThenDraws:
    """Kozilek's Command: "Target player scries X, then draws a card." """
    count: int | str
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.scry(target, game.amount(self.count))
            game.draw(target, 1)


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
    Otherwise, draw a card." (Thrasios), built by _merge_reveal_top; "... Otherwise, put that card into your hand." (Coiling Oracle):
    `to_hand`, put there, not drawn."""
    scry: int
    tapped: bool
    to_hand: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.reveal_top_land_or_draw(controller, self.scry, self.tapped, self.to_hand)


@dataclass(frozen=True)
class RevealTopStep:
    """One sentence of RevealTop; alone it isn't understood. kind: "reveal" (with scry), "land" or "otherwise"."""
    kind: str
    scry: int = 0
    tapped: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone reveal-the-top step is never built")


@dataclass(frozen=True)
class LookAtTopOfLibrary:
    """Mishra's Bauble: "Look at the top card of target player's library." Only its controller learns anything."""
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.library:
            controller.player.notify({"event": "library_top", "seat": target.index, "cards": [target.library[0].name]})


@dataclass(frozen=True)
class ShuffleSelfAndGraveyard:
    """Elixir of Immortality: "Shuffle this artifact and your graveyard into their owner's library." The artifact goes only if it is
    still on the battlefield; the library is shuffled either way."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game._leave_together([(target, "returned")], destination="library")
            game.rng.shuffle(game.owner_of(target).library)
        game.shuffle_into_library(controller, [game.graveyard_target(card, controller) for card in controller.graveyard])
        game.rng.shuffle(controller.library)


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
    """ "Put the rest on the bottom of your library in a random order." or, with `to` "graveyard", "Put the rest into your graveyard."
    (Malevolent Rumble)."""
    to: str = "bottom"

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
class LookPutUpTo:
    """Collected Company: "Look at the top six cards of your library. Put up to two creature cards with mana value 3 or less from among
    them onto the battlefield. Put the rest on the bottom of your library in any order." (also "permanent", "noncreature, nonland
    permanent")."""
    count: int
    up_to: int
    kind: str
    mv_max: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_and_put_up_to(controller, self.count, self.up_to, self.kind, self.mv_max)


@dataclass(frozen=True)
class PutBackTop:
    """ "Look at the top three cards of your library, then put them back in any order. (You may shuffle.)" """
    count: Quantity
    shuffle: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.rearrange_top(controller, game.amount(self.count), self.shuffle)


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
    put_to: str = "battlefield"  # Free the Fae: "... from among the milled cards into your hand." ("hand")
    play_this_turn: bool = False  # Tablet of Discovery: "You may play that card this turn."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "each player" or (self.who == "you") == (seat is controller):
                milled = game.mill(seat, game.amount(self.count))
                if self.put:
                    game.return_chosen_from(seat, milled, self.put, self.put_to)
                if self.play_this_turn:
                    seat.graveyard_play += [(card, game.turn) for card in milled]


@dataclass(frozen=True)
class _PutFromAmongThem:
    """ "Then put a creature card from among them onto the battlefield." after a Mill (see _merge_conditional)."""
    kind: str
    to: str = "battlefield"


@dataclass(frozen=True)
class TargetMill:
    """ "Target player (or opponent) mills three cards." ("half": "... mills half their library, rounded down.", Traumatize)"""
    count: int | str
    target: str  # "player" or "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.mill(target, len(target.library) // 2 if self.count == "half" else game.amount(self.count))


@dataclass(frozen=True)
class FetchBasicLand:
    untap_if: "Condition | None" = None  # Fabled Passage: "Then if you control four or more lands, untap that land."
    tapped: bool = True  # Prismatic Vista puts it onto the battlefield untapped

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fetch_basic_land(controller, untap_if=self.untap_if, tapped=self.tapped)


@dataclass(frozen=True)
class OwnerPutsSecondOrBottom:
    """Deem Inferior: "The owner of target nonland permanent puts it into their library second from the top or on the bottom." """
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_second_or_bottom(target)
