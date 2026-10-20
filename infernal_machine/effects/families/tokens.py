"""Effects of the "tokens" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...cards import Card
from ...characteristics import Modifier
from ..common import Quantity
from ..targets import (DEAD_SOURCE, PLAYER, PREVIOUS_TARGET, SOURCE, SUBJECT)
from .base import Condition

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class ExiledOwnerGetsToken:
    """Skyclave Apparition: "the exiled card's owner creates an X/X ... token, where X is the mana value of the exiled
    card." The target is the source, which has already left the battlefield."""
    token: Card
    binds = DEAD_SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        for owner, card in target.exiled_with:
            size = str(int(card.cmc))
            game.create_tokens(owner, dataclasses.replace(self.token, power=size, toughness=size), 1)


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
class _TokenHasHaste:
    """ "That token gains haste." with no duration, after a CopyHostToken (see _merge_conditional): it keeps haste."""


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
class _TokenPerPrevented:
    """ "For each 1 damage prevented this way, create ...": only ever after PreventCombatDamageToYou."""
    token: Card


@dataclass(frozen=True)
class _ChooseToken:
    """ "Then you may choose a token you control.": only ever before _OthersBecomeCopies."""


@dataclass(frozen=True)
class TargetControllerManifests:
    """Reality Shift: "Exile target creature. Its controller manifests the top card of their library." """
    binds = PREVIOUS_TARGET

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
class AttackerCreatesAttackingToken:
    """Combat Calligrapher: "that attacking player creates a tapped 2/1 ... Inkling creature token with flying that's attacking
    that opponent." The target is the player who attacked; the opponent is the seat the trigger carries in x."""
    token: Card
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if target is not None and item is not None and game.combat is not None:
            game.token_attacking(target, self.token, game.seats[item.x])


@dataclass(frozen=True)
class CreateOneOfTokens:
    """Tireless Provisioner: "Create a Food token or a Treasure token." (you choose)"""
    options: tuple[Card, ...]

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        token = self.options[controller.player.choose(TOKEN_CHOICE_PROMPT, [t.name for t in self.options])]
        game.create_tokens(controller, token, 1)


TOKEN_CHOICE_PROMPT = "Create which token? "


@dataclass(frozen=True)
class Connive:
    """Ledger Shredder: "this creature connives": draw a card, then discard a card; a nonland card puts a +1/+1 counter on it."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.connive(controller, target)


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
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        owner = getattr(target, "last_controller", None) or getattr(target, "controller", None)  # a permanent, or a countered spell
        if target is not None and owner is not None:
            game.create_tokens(owner, self.token, game.amount(self.count))


@dataclass(frozen=True)
class _ExileThoseTokens:
    """ "Exile those tokens at the beginning of the next end step." """


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
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if target is None or item is None:
            return
        if game.seats[item.x] is not controller:
            game.modify_until_end_of_turn(target, Modifier(2, 0))
        else:
            game.change_life(game.controller(target), -2)


@dataclass(frozen=True)
class CreateTokenAttachSubject:
    """Ajani's Chosen: "Create a 2/2 white Cat creature token. If that enchantment is an Aura, you may attach it to the token." """
    token: Card
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        made = game.create_tokens(controller, self.token, 1)
        if made and target is not None and "Aura" in target.card.type_line and game.on_battlefield(target):
            game.may_attach(controller, target, made[0])


@dataclass(frozen=True)
class CreateTokenAttachSource:
    """Fractal Harness: "Create a 0/0 ... Fractal creature token. Put X +1/+1 counters on it and attach this Equipment to it." """
    token: Card
    counters: tuple[int | str, str]
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for made in game.create_tokens(controller, self.token, 1, (game.amount(self.counters[0]), self.counters[1])):
            if target is not None:
                game.attach(target, made)


@dataclass(frozen=True)
class CreateTokenWithGraveyardAttachment:
    """Forum Filibuster: "Create a 2/1 ... token. When you do, return up to one target Aura or Equipment card from your
    graveyard to the battlefield attached to that token." (chosen as it resolves rather than targeted)"""
    token: Card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for made in game.create_tokens(controller, self.token, 1):
            game.return_attachment_to(controller, made)


@dataclass(frozen=True)
class _AttachItToToken:
    """ "If that enchantment is an Aura, you may attach it to the token." after a CreateTokens (see _merge_conditional)."""


@dataclass(frozen=True)
class _ExileTokenAtEnd:
    """ "Exile that token at the beginning of the next end step." after a token was created (see _merge_conditional)."""


@dataclass(frozen=True)
class _InsteadTokens:
    """ "If that spell's mana value is 5 or greater, create three of those tokens instead." (see _merge_conditional)"""
    condition: "Condition"
    count: Quantity


@dataclass(frozen=True)
class Conjure:
    """Alchemy: "Conjure a card named Storm Crow onto the battlefield." The card was looked up when the deck loaded."""
    name: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.conjure(controller, self.name)
