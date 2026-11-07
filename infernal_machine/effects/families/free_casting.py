"""Effects of the "free casting" family: casting spells without paying their mana costs, the cascades and look-and-cast effects that
lead to it, and the villainous choice (split from spells_and_misc.py; the sentences that make them are read in outcomes.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..targets import PLAYER, SOURCE, SUBJECT
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class LootCastIfCounters:
    """Malcolm, Alluring Scoundrel: "Draw a card, then discard a card. If there are four or more chorus counters on Malcolm, you may cast
    the discarded card without paying its mana cost." The counters are the source's, as they are once the card is discarded."""
    counter: str
    at_least: int
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        from .exile_and_return import DECLINE, FREE_CAST_PROMPT

        game.draw(controller, 1)
        for card in game.discard(controller, 1):
            if target is not None and target.counters.get(self.counter, 0) >= self.at_least and "Land" not in card.type_line \
                    and any(c is card for c in controller.graveyard) \
                    and controller.player.choose(FREE_CAST_PROMPT, [card.name, DECLINE]) == 0:
                game._cast(controller, card, controller.graveyard, free=True)


@dataclass(frozen=True)
class SubjectControllerMayPayLifeDraw:
    """Gix, Yawgmoth Praetor: "its controller may pay 1 life. If they do, they draw a card." The creature that dealt the damage decides
    who: its controller, whoever that is (CR 119.4: only with that much life to pay)."""
    life: int
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        payer = game.controller_of(target) if target is not None else None
        if payer is not None and payer.life >= self.life \
                and payer.player.choose(PAY_LIFE_DRAW_PROMPT(f"{self.life} life"), ["Yes", "No"]) == 0:
            game.change_life(payer, -self.life)
            game.draw(payer, 1)


PAY_LIFE_DRAW_PROMPT = PromptKind("pay_life_draw", "Pay to draw a card: ")  # followed by the life; Yes or No


@dataclass(frozen=True)
class ExileTopCastOneOfEachType:
    """Aminatou's Augury: "Exile the top eight cards of your library. You may put a land card from among them onto the battlefield. Until
    end of turn, for each nonland card type, you may cast a spell of that type from among the exiled cards without paying its mana
    cost." """
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_top_cast_one_of_each_type(controller, self.count)


@dataclass(frozen=True)
class CascadeOfKind:
    """Jodah, the Unifier: "exile cards from the top of your library until you exile a legendary nonland card with lesser mana value. You
    may cast that card without paying its mana cost. Put the rest on the bottom of your library in a random order." The mana value is the
    spell's that set the trigger off."""
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        spell = item.carried if item is not None else None  # the cast trigger carries the spell that was cast
        card = getattr(spell, "card", spell)
        game.cascade(controller, int(getattr(card, "cmc", 0)), self.kind)


@dataclass(frozen=True)
class ThatPlayerCascades:
    """Gríma, Saruman's Footman: "that player exiles cards from the top of their library until they exile an instant or sorcery card. You
    may cast that card without paying its mana cost. Then that player puts the exiled cards that weren't cast this way on the bottom of
    their library in a random order." (the player dealt damage)"""
    kind: str
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.cascade(controller, None, self.kind, owner=target)


@dataclass(frozen=True)
class CastCommanderFree:
    """Geode Golem: "you may cast your commander from the command zone without paying its mana cost." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.cast_commander_free(controller)


@dataclass(frozen=True)
class MayMillThenPlayHideaway:
    """Cemetery Tampering: "you may mill three cards. Then if there are twenty or more cards in your graveyard, you may play the exiled card
    without paying its mana cost." The mill is optional on its own; the card is the one its Hideaway exiled."""
    count: int
    at_least: int
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if controller.player.choose(MILL_PROMPT(str(self.count)), ["Yes", "No"]) == 0:
            game.mill(controller, self.count)
        if target is not None and len(controller.graveyard) >= self.at_least:
            game.play_hideaway(controller, target)


MILL_PROMPT = PromptKind("may_mill", "Mill cards: ")  # followed by how many; Yes or No


@dataclass(frozen=True)
class LookTopCastFreeOnce:
    """Planetarium of Wan Shi Tong: "look at the top card of your library. You may cast that card without paying its mana cost. Do this
    only once each turn." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.look_top_cast_free_once(controller, target)


@dataclass(frozen=True)
class LookTopCastOneFree:
    """Aetherworks Marvel: "Look at the top six cards of your library. You may cast a spell from among them without paying its mana cost.
    Put the rest on the bottom of your library in a random order." """
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_top_cast_one_free(controller, self.count)


@dataclass(frozen=True)
class ShuffleExileTopPlayFree:
    """Mind's Desire: "Shuffle your library. Then exile the top card of your library. Until end of turn, you may play that card without
    paying its mana cost." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.rng.shuffle(controller.library)
        controller.exile_free.extend(game.exile_top(controller, 1, "this turn"))


@dataclass(frozen=True)
class ExileUntilNonlandCastOrTake:
    """Breaching Dragonstorm: "exile cards from the top of your library until you exile a nonland card. You may cast it without paying its
    mana cost if that spell's mana value is 8 or less. If you don't, put that card into your hand." """
    most: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_until_nonland_cast_or_take(controller, self.most)


@dataclass(frozen=True)
class CastTwoFreeFromHandOrGraveyard:
    """Invoke Calamity: "You may cast up to two instant and/or sorcery spells with total mana value 6 or less from your graveyard and/or
    hand without paying their mana costs. If those spells would be put into your graveyard, exile them instead." """
    total: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.cast_two_free_from_hand_or_graveyard(controller, self.total)


@dataclass(frozen=True)
class TargetCascades:
    """Chaos Wand: "Target opponent exiles cards from the top of their library until they exile an instant or sorcery card. You may cast
    that card without paying its mana cost. Then put the exiled cards that weren't cast this way on the bottom of that library in a random
    order." """
    kind: str
    target: str = "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.cascade(controller, None, self.kind, owner=target)


@dataclass(frozen=True)
class CastTargetFromGraveyardFree:
    """Memory Plunder: "You may cast target instant or sorcery card from an opponent's graveyard without paying its mana cost." """
    target: str = "graveyard:instant or sorcery:opponents"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        from .copying import CAST_COPY_PROMPT

        if target is not None and controller.player.choose(CAST_COPY_PROMPT(target.card.name), ["Yes", "No"]) == 0:  # (a target gone: it fizzles)
            game._cast(controller, target.card, target.seat.graveyard, free=True)


@dataclass(frozen=True)
class ExileRandomFromOpponentsCast:
    """Kefka, Dancing Mad: "exile a card at random from each opponent's graveyard. You may cast any number of spells from among cards
    exiled this way without paying their mana costs. Then each player who owns a spell you cast this way loses life equal to its mana
    value." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_random_from_opponents_cast(controller)


@dataclass(frozen=True)
class PossibilityStorm:
    """Possibility Storm: "that player exiles it, then exiles cards from the top of their library until they exile a card that shares a
    card type with it. That player may cast that card without paying its mana cost. Then they put all cards exiled with this enchantment
    on the bottom of their library in a random order." (the player who cast the spell; the trigger carries the spell)"""
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if target is not None and item is not None:
            game.possibility_storm(target, item.carried)


@dataclass(frozen=True)
class VillainousChoice:
    """ "Each opponent faces a villainous choice — A, or B." (CR 701.56): each player facing it chooses A or B for themselves; "they" and
    "that player" in the options are that player. `target` is "opponent" for "Target opponent faces ...", else every opponent faces it."""
    labels: tuple[str, str]
    options: tuple[tuple, tuple]
    target: str | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        facing = ([target] if target is not None else []) if self.target else game.opponents(controller)
        for seat in facing:
            game.villainous_choice(controller, seat, self.labels, self.options)


@dataclass(frozen=True)
class ThatPlayerExilesUntilNonlandYouCast:
    """Ensnared by the Mara: "They exile cards from the top of their library until they exile a nonland card, then you may cast that card
    without paying its mana cost" (a villainous choice's option: the player is the one facing it)."""
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_until_nonland_may_cast(controller, target)


@dataclass(frozen=True)
class ThatPlayerExilesTopDamaged:
    """Ensnared by the Mara: "that player exiles the top four cards of their library and Ensnared by the Mara deals damage equal to the
    total mana value of those exiled cards to that player." """
    count: int
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_top_damage_by_value(target, self.count)


@dataclass(frozen=True)
class FlickerSelf:
    """Jin-Gitaxias: "Exile Jin-Gitaxias, then return it to the battlefield transformed under its owner's control." The Great Synthesis:
    "Exile this Saga, then return it to the battlefield (front face up)." (`transformed` False: the front face)"""
    transformed: bool
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.flicker(target, controller, "now", "battlefield", True, self.transformed)


@dataclass(frozen=True)
class NoMaxHandWhileControlled:
    """The Great Synthesis: "You have no maximum hand size for as long as you control this Saga." (kept on the permanent)"""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.no_max_hand = True


@dataclass(frozen=True)
class CastAnyFromHandFree:
    """The Great Synthesis: "You may cast any number of spells from your hand without paying their mana costs." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.cast_any_from_hand_free(controller)


@dataclass(frozen=True)
class CourtExileTopPlay:
    """Court of Locthwain: "exile the top card of target opponent's library. You may play that card for as long as it remains exiled, and
    mana of any type can be spent to cast it. If you're the monarch, until end of turn, you may cast a spell from among cards exiled with
    this enchantment without paying its mana cost." """
    target: str = "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.court_of_locthwain(controller, target, game.resolving_source)
