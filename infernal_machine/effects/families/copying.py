"""Effects of the "copying" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...cards import Card
from ...characteristics import Modifier
from ..common import Quantity
from ..targets import (DEAD_SUBJECT, PLAYER, SOURCE, SOURCE_AND_SUBJECT)
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


CHOOSE_COPY_PROMPT = PromptKind("choose_copy", "Choose a permanent to copy")  # options: the permanents (Season of Weaving)


@dataclass(frozen=True)
class CopyChosenPermanent:
    """Season of Weaving: "Choose an artifact or creature you control. Create a token that's a copy of it." (chosen on resolution)"""
    kind: str  # "artifact or creature you control"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        options = game.mass_targets(self.kind, controller)
        if not options:
            return
        chosen = options[controller.player.choose(CHOOSE_COPY_PROMPT, [game.label(p) for p in options])]
        game.create_tokens(controller, copy_of(chosen.card, as_token=True), 1)


_COPY_CARD_TYPES = {"Artifact", "Enchantment", "Creature", "Land"}


@dataclass(frozen=True)
class CopyChanges:
    """The "except ..." of a copy (CR 707.9): "except it isn't legendary", "except it's 1/1 and it's a Nightmare in addition to
    its other types", "except it has flying and haste". The copy keeps everything else of the original."""
    not_legendary: bool = False
    power_toughness: tuple[str, str] | None = None
    add_types: tuple[str, ...] = ()  # a card type (Enchantment) or a subtype (Spirit), added to the type line
    keywords: tuple[str, ...] = ()  # added as ability lines, as Twinflame's haste is
    add_colors: tuple[str, ...] = ()  # "a 2/2 black Zombie in addition to its other colors and types": W, U, B, R or G
    abilities: tuple[str, ...] = ()  # quoted abilities it has: Phantasmal Image's "When this creature becomes the target ..."
    extra_counters: str = ""  # a clone's "it enters with an additional +1/+1 counter on it" ("1", "2", ...) or "X additional" ("X"); only for a creature
    extra_loyalty: int = 0  # Spark Double: "an additional loyalty counter on it if it's a planeswalker"
    supertypes: tuple[str, ...] = ()  # "it's legendary (and snow) in addition to its other types", Adagia's "except it's legendary"
    set_colors: tuple[str, ...] | None = None  # The Scarab God's "it's a 4/4 black Zombie": that color and no other
    set_subtypes: tuple[str, ...] | None = None  # ... and that creature type and no other
    name: str | None = None  # Sakashima, Superior Spider-Man: "except its name is CARDNAME" (the copy keeps the clone's own name)


def apply_copy_changes(card: Card, changes: CopyChanges | None) -> Card:
    """`card` with the changes of an except clause applied."""
    if changes is None:
        return card
    type_line = card.type_line
    if changes.not_legendary:
        type_line = type_line.replace("Legendary ", "", 1)  # CR 707.9b: the copy is the original with this one value changed
    if changes.set_subtypes is not None:
        type_line = f"{type_line.partition(chr(0x2014))[0].strip()} \u2014 {' '.join(changes.set_subtypes)}"
    for word in changes.add_types:
        head, dash, tail = type_line.partition("\u2014")
        if word in _COPY_CARD_TYPES:
            if word not in head:  # "Artifact Creature": a new card type goes before Creature, as printed
                head = head.replace("Creature", f"{word} Creature") if "Creature" in head else f"{head.strip()} {word}"
                type_line = f"{head.strip()} {dash} {tail.strip()}" if dash else head.strip()
        elif word not in tail.split():
            type_line = f"{head.strip()} {dash} {tail.strip()} {word}" if dash else f"{head.strip()} \u2014 {word}"
    for word in reversed(changes.supertypes):  # before the card types ("Legendary Snow Creature"), after "Token"
        if word not in type_line.partition("\u2014")[0].split():
            prefix = "Token " if type_line.startswith("Token ") else ""
            type_line = f"{prefix}{word} {type_line.removeprefix(prefix)}"
    card = dataclasses.replace(card, type_line=type_line)
    if changes.set_colors is not None:
        card = dataclasses.replace(card, colors=tuple(sorted(changes.set_colors)))
    if changes.add_colors:
        card = dataclasses.replace(card, colors=tuple(sorted(set(card.colors) | set(changes.add_colors))))
    if changes.power_toughness is not None:
        card = dataclasses.replace(card, power=changes.power_toughness[0], toughness=changes.power_toughness[1])
    if changes.name is not None and changes.name != "CARDNAME":  # ("CARDNAME" is filled in by the clone, which knows its own name)
        card = dataclasses.replace(card, name=changes.name)
    extra = [k.capitalize() for k in changes.keywords] + [f'{a}' for a in changes.abilities]
    if extra:
        card = dataclasses.replace(card, oracle_text="\n".join([card.oracle_text, *extra]).strip())
    return card


def copy_of(card: Card, changes: CopyChanges | None = None, *, as_token: bool = False) -> Card:
    """The card that a copy of `card` is (CR 707.2): its copiable values with the changes of an "except" clause (CR 707.9). Every
    copy goes through here, so an except clause means the same thing everywhere. `as_token`: the copy is a token ("create a token
    that's a copy of ...", a copy of a permanent spell, CR 707.10f); otherwise it is not one, even if what it copies is (a clone
    entering as a copy of a token, a creature that becomes a copy of one)."""
    if as_token and not card.type_line.startswith("Token"):
        card = dataclasses.replace(card, type_line="Token " + card.type_line)
    elif not as_token:
        card = dataclasses.replace(card, type_line=card.type_line.removeprefix("Token "))
    return apply_copy_changes(card, changes)


# "Create a token that's a copy of <what>(, except <changes>)." is one sentence shape whatever <what> is; the effects below differ only
# in how they find it. The riders that may follow it ("It gains haste (until end of turn).", "Sacrifice it / Exile it at the beginning
# of the next end step.") are folded into the effect by the Follow rows in outcomes.py and applied by `finish_copies`.


def finish_copies(game: Game, made: list, effect: Any) -> None:
    """Apply the riders of a copy sentence to the tokens it made."""
    if effect.haste:
        for token in made:
            game.modify_until_end_of_turn(token, Modifier(keywords=frozenset({"haste"})))
    if made and (effect.sacrifice_at_end or effect.exile_at_end):
        game.leave_at_next_end_step(made, "exiled" if effect.exile_at_end else "sacrificed", "exile" if effect.exile_at_end else "graveyard")


@dataclass(frozen=True)
class CopySubjectToken:
    """Miirym, Impostor Syndrome, Ratadrabik: "Create a token that's a copy of it, except it isn't legendary." The copy is of the
    permanent that set off the trigger, still there or not (it may have just died); for a trigger of the permanent's own ("When this
    creature dies, ... a copy of it") that permanent is the source."""
    changes: CopyChanges | None = None
    count: Quantity = 1
    haste: bool = False  # "That token gains haste until end of turn."
    sacrifice_at_end: bool = False  # "Sacrifice it at the beginning of the next end step."
    exile_at_end: bool = False  # "Exile it at the beginning of the next end step."
    binds = SOURCE_AND_SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            source, subject = target
            made = game.create_tokens(controller, copy_of((subject or source).card, self.changes, as_token=True), game.amount(self.count))
            finish_copies(game, made, self)


@dataclass(frozen=True)
class CopyHostToken:
    """Helm of the Host, Endless Evil: "Create a token that's a copy of equipped creature, except the token isn't legendary." The
    creature this Equipment or Aura is attached to; with nothing attached there is nothing to copy."""
    changes: CopyChanges | None = None
    count: Quantity = 1
    haste: bool = False
    sacrifice_at_end: bool = False
    exile_at_end: bool = False
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.attached_to is not None:
            made = game.create_tokens(controller, copy_of(target.attached_to.card, self.changes, as_token=True), game.amount(self.count))
            finish_copies(game, made, self)


@dataclass(frozen=True)
class CopyToken:
    """ "Create a token that's a copy of target creature you control." (Feldon of the Third Path: "... of target creature card in
    your graveyard", a `graveyard:` target)"""
    target: str
    count: Quantity = 1  # Rite of Replication: "If this spell was kicked, create five of those tokens instead."
    another: bool = False  # "a copy of another target creature you control": not the source itself
    haste: bool = False  # Inspired Skypainter's spell: "That token gains haste until end of turn."
    changes: CopyChanges | None = None  # Helm of the Host, Irenicus's Vile Duplication: "..., except it isn't legendary."
    sacrifice_at_end: bool = False  # Kiki-Jiki: "Sacrifice it at the beginning of the next end step."
    exile_at_end: bool = False  # Felhide Spiritbinder: "Exile it at the beginning of the next end step."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            made = game.create_tokens(controller, copy_of(target.card, self.changes, as_token=True), game.amount(self.count))
            finish_copies(game, made, self)


@dataclass(frozen=True)
class CopyEachToken:
    """Second Harvest: "For each token you control, create a token that's a copy of that permanent." (Saheeli, the Gifted: "For each
    artifact you control, create a token that's a copy of it. Those tokens gain haste. Exile those tokens at the beginning of the
    next end step.")"""
    kind: str  # "token", "artifact", "nontoken creature"
    changes: CopyChanges | None = None
    haste: bool = False
    sacrifice_at_end: bool = False
    exile_at_end: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        cards = [copy_of(p.card, self.changes, as_token=True) for p in game.mass_targets(self.kind, controller)]
        finish_copies(game, game.create_token_batch(controller, cards), self)


@dataclass(frozen=True)
class TokensBecomeCopies:
    """Brudiclad: "Then you may choose a token you control. If you do, each other token you control becomes a copy of
    that token." (two sentences, folded together by _merge_token_copies). The older wording ended "until end of turn"."""
    until_end_of_turn: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tokens_become_copies(controller, self.until_end_of_turn)


@dataclass(frozen=True)
class _OthersBecomeCopies:
    """ "If you do, each other token you control becomes a copy of that token (until end of turn)." """
    until_end_of_turn: bool = False


@dataclass(frozen=True)
class CopySpellForEachOtherCreature:
    """Mirrorwing Dragon: "that player copies that spell for each other creature they control that the spell could target. Each
    copy targets a different one of those creatures." The target is the caster; the spell rides along with the trigger."""
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if target is not None and item is not None and item.source is not None and hasattr(item.carried, "targets"):
            game.copy_spell_for_each_other_creature(item.carried, target, item.source)


@dataclass(frozen=True)
class ExileDeadCopy:
    """Nightmare Shepherd, Hofri Ghostforge: "(You may) exile it. If you do, create a token that's a copy of that creature, except
    it's 1/1 and it's a Nightmare in addition to its other types." The creature that just died is exiled from the graveyard; only
    if that works is it copied. A copy given Hofri's "return the exiled card to its owner's graveyard" ability sends the exiled
    card back when it leaves."""
    changes: CopyChanges | None = None
    binds = DEAD_SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_dead_copy(controller, target, self.changes)


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
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_entered_tokens_attacking(controller, target)


@dataclass(frozen=True)
class CopyTokenAttacking:
    """ "Create a token that's a copy of it, tapped and attacking." (it: the attacking source). The token attacks the
    same player or planeswalker; it was never declared as an attacker, so attack triggers do not see it."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_attacking(controller, target)


@dataclass(frozen=True)
class ExileThenCastCopy:
    """Renegade Bull: "Exile up to one target instant or sorcery card from your graveyard and copy it. You may cast the copy without
    paying its mana cost." """
    target: str = "graveyard:instant or sorcery:yours"
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or not game.exile_from_graveyard(target):
            return
        if controller.player.choose(CAST_COPY_PROMPT(target.card.name), ["Yes", "No"]) == 0:
            game.cast_copy_free(controller, target.card)


CAST_COPY_PROMPT = PromptKind("cast_copy", "Cast a copy without paying its mana cost: ")  # followed by the card's name; Yes or No


@dataclass(frozen=True)
class MayCopyThisSpellFromGraveyard:
    """Sevinne's Reclamation: "If this spell was cast from a graveyard, you may copy this spell and may choose a new target for the
    copy." The copy is not cast, so it does not copy itself."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if item is not None and item.from_graveyard and controller.player.choose(COPY_THIS_PROMPT(item.card.name), ["Yes", "No"]) == 0:
            game.copy_spell(item, controller, new_targets=True)


COPY_THIS_PROMPT = PromptKind("copy_this", "Copy this spell: ")  # followed by its name; Yes or No


@dataclass(frozen=True)
class TokenOrSelfCopy:
    """Scute Swarm: "Create a 1/1 green Insect creature token. If you control six or more lands, create a token that's a copy of this
    creature instead." """
    token: Card
    lands: int
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and sum("Land" in p.card.type_line for p in controller.battlefield) >= self.lands:
            game.copy_tokens(controller, [target], False, False)
        else:
            game.create_tokens(controller, self.token, 1)


@dataclass(frozen=True)
class EachOpponentGetsGoadedCopy:
    """Life of the Party: "each opponent creates a token that's a copy of it. The tokens are goaded for the rest of the
    game." """
    binds = SOURCE

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
class CastExiledCopy:
    """The delayed trigger of Surge to Victory: cast a copy of the exiled card without paying its mana cost."""
    card: Card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.cast_copy_free(controller, self.card)


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
class _CopyEachWithHaste:
    """ "For each of them, create a token that's a copy of that creature, except it has haste." """


@dataclass(frozen=True)
class CopySpellTimes:
    """Replicate, Storm and Gravestorm: "When you cast this spell, copy it" `count` times. The spell the ability came from
    is `carried`; the copies may have new targets. Thousand-Year Storm: "copy it for each other instant and sorcery spell you've
    cast before it this turn" (an X set just before)."""
    count: Quantity

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        original = game.resolving_item.carried if game.resolving_item else None
        for _ in range(game.amount(self.count)):
            if original is not None:
                game.copy_spell(original, controller, new_targets=True)


@dataclass(frozen=True)
class CopySelfToken:
    """Leitmotif Composer: "Create a token that's a copy of this creature." Offspring: "create a 1/1 token copy of it". Splinter
    Twin's granted ability: "..., except it has haste. Exile that token at the beginning of the next end step." """
    one_by_one: bool = False  # CR 702.175a: the copy is 1/1 instead of the printed size
    changes: CopyChanges | None = None
    count: Quantity = 1
    haste: bool = False
    sacrifice_at_end: bool = False
    exile_at_end: bool = False
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            changes = CopyChanges(power_toughness=("1", "1")) if self.one_by_one else self.changes
            made = game.create_tokens(controller, copy_of(target.card, changes, as_token=True), game.amount(self.count))
            finish_copies(game, made, self)


@dataclass(frozen=True)
class MayCopyLeftCard:
    """Spirit of Resilience: "... you may have this creature become a copy of an artifact or creature card from among those
    cards until end of turn." (the cards that left the graveyard ride along with the trigger)"""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        carried = item.carried if item is not None else None
        options = [c for c in (carried if isinstance(carried, tuple) else ())
                   if "Creature" in c.type_line or "Artifact" in c.type_line]
        if target is None or not options:
            return
        game.may_become_copy(controller, target, options)


@dataclass(frozen=True)
class CopySpell:
    """ "Copy target instant or sorcery spell. You may choose new targets for the copy." The target may also be a creature or
    permanent spell (Double Major, Lithoform Engine: the copy becomes a token, CR 707.10f) or an ability (Return the Favor)."""
    target: str  # "instant or sorcery spell", optionally "... you control"; "activated or triggered ability you control"
    new_targets: bool = False
    return_to_hand: bool = False  # Narset's Reversal: "..., then return it to its owner's hand."
    color: str | None = None  # Fork: "except that the copy is red"
    twice_from_graveyard: bool = False  # Increasing Vengeance: "If this spell was cast from a graveyard, copy that spell twice instead."
    changes: CopyChanges | None = None  # Double Major: "except it isn't legendary if the spell is legendary"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        if target.ability:
            game.copy_ability(target, controller, self.new_targets)
            return
        item = game.resolving_item
        for _ in range(2 if self.twice_from_graveyard and item is not None and item.from_graveyard else 1):
            game.copy_spell(target, controller, self.new_targets, self.color, self.changes)
        if self.return_to_hand:
            game.return_spell_to_hand(target)


@dataclass(frozen=True)
class _TwiceFromGraveyard:
    """ "If this spell was cast from a graveyard, copy that spell twice instead." after a CopySpell."""


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
    new_targets: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        ability = game.resolving_item.carried if game.resolving_item is not None else None
        if ability is not None:
            game.copy_ability(ability, controller, self.new_targets)


@dataclass(frozen=True)
class CopyTriggeredAbility:
    """Strionic Resonator: "Copy target triggered ability you control. You may choose new targets for the copy." (Mister Fantastic:
    "... twice. ... for the copies.")"""
    target: str = "triggered ability you control"
    new_targets: bool = False
    times: int = 1

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_ability(target, controller, self.new_targets, self.times)
