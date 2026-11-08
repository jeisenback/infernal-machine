"""Effects of the "copying" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...cards import Card
from ...characteristics import Modifier
from ..common import Quantity
from ..targets import (DEAD_SUBJECT, PLAYER, PREVIOUS_TARGET, SOURCE, SOURCE_AND_SUBJECT, SUBJECT)
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
    keeps_ability: bool = False  # Thespian's Stage, Sunfrill Imitator: "except it has this ability" (the effect adds the ability's text)
    vanishing_unless: int = 0  # Flesh Duplicate: "it has vanishing 3 if that creature doesn't have vanishing"
    vehicle_crew: int = 0  # Imposter Mech: "it's a Vehicle artifact with crew 3 and it loses all other card types"
    own_abilities: bool = False  # Sakashima of a Thousand Faces: "it has CARDNAME's other abilities" (the clone adds its own lines)


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
    if changes.vehicle_crew:  # its supertypes stay; its other card types and their subtypes go (CR 205.1b)
        supertypes = [w for w in type_line.partition("\u2014")[0].split() if w in ("Token", "Legendary", "Snow")]
        type_line = " ".join(supertypes + ["Artifact", "\u2014", "Vehicle"])
    card = dataclasses.replace(card, type_line=type_line)
    if changes.vehicle_crew:
        card = dataclasses.replace(card, oracle_text="\n".join([card.oracle_text, f"Crew {changes.vehicle_crew}"]).strip())
    if changes.set_colors is not None:
        card = dataclasses.replace(card, colors=tuple(sorted(changes.set_colors)))
    if changes.add_colors:
        card = dataclasses.replace(card, colors=tuple(sorted(set(card.colors) | set(changes.add_colors))))
    if changes.power_toughness is not None:
        card = dataclasses.replace(card, power=changes.power_toughness[0], toughness=changes.power_toughness[1])
    if changes.name is not None and changes.name != "CARDNAME":  # ("CARDNAME" is filled in by the clone, which knows its own name)
        card = dataclasses.replace(card, name=changes.name)
    extra = [k.capitalize() for k in changes.keywords] + [f'{a}' for a in changes.abilities]
    if changes.vanishing_unless and not re.search(r"^Vanishing \d+", card.oracle_text, re.M):
        extra.append(f"Vanishing {changes.vanishing_unless}")
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
    if getattr(effect, "blitz", False):
        for token in made:
            token.blitzed = True
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
    blitz: bool = False  # Jaxis: "It gains haste and "When this token dies, draw a card."" (Permanent.blitzed)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            made = game.create_tokens(controller, copy_of(target.card, self.changes, as_token=True), game.amount(self.count))
            finish_copies(game, made, self)


@dataclass(frozen=True)
class CopyEachToken:
    """Second Harvest: "For each token you control, create a token that's a copy of that permanent." (Saheeli, the Gifted: "For each
    artifact you control, create a token that's a copy of it. Those tokens gain haste. Exile those tokens at the beginning of the
    next end step.")"""
    kind: str  # "token you control", "artifact you control", "nontoken creature you control"
    changes: CopyChanges | None = None
    haste: bool = False
    sacrifice_at_end: bool = False
    exile_at_end: bool = False
    entered_this_turn: bool = False  # Ocelot Pride: "for each token you control that entered this turn"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        cards = [copy_of(p.card, self.changes, as_token=True) for p in game.mass_targets(self.kind, controller)
                 if not self.entered_this_turn or p.entered_turn == game.turn]
        finish_copies(game, game.create_token_batch(controller, cards), self)


@dataclass(frozen=True)
class CopyEachEnteredToken:
    """Kambal, Profiteering Mayor: "Whenever one or more tokens your opponents control enter, for each of them, create a tapped token
    that's a copy of it." Them are the tokens created together with the one that set the trigger off (still there or not)."""
    binds = DEAD_SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.create_token_batch(controller, [copy_of(p.card, as_token=True) for p in target.entered_with or [target]], tapped=True)


@dataclass(frozen=True)
class CopyEachOfTargetPlayer:
    """Clone Legion: "For each creature target player controls, create a token that's a copy of that creature." """
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.create_token_batch(controller, [copy_of(p.card, as_token=True) for p in target.battlefield if "Creature" in p.card.type_line])


@dataclass(frozen=True)
class CopySacrificed:
    """Cleaver Skaab: "Create two tokens that are copies of the sacrificed creature." (as it last existed on the battlefield)"""
    count: Quantity = 1

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        cards = game.resolving_item.sacrificed_cards if game.resolving_item else ()
        game.create_token_batch(controller, [copy_of(card, as_token=True) for card in cards for _ in range(game.amount(self.count))])


@dataclass(frozen=True)
class ExileOthersCopy:
    """Fractured Identity: "Exile target nonland permanent. Each player other than its controller creates a token that's a copy of it."
    (the copy is of the permanent as it last was on the battlefield)"""
    target: str = "nonland permanent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            owner, card = game.controller_of(target), target.card
            game.exile_noting(target, game.resolving_source)
            for seat in game.live_seats():
                if seat is not owner:
                    game.create_tokens(seat, copy_of(card, as_token=True), 1)


@dataclass(frozen=True)
class CopySubjectForItsController:
    """Bramble Sovereign: "... that creature's controller creates a token that's a copy of that creature." """
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and (owner := game.controller_of(target)) is not None:
            game.create_tokens(owner, copy_of(target.card, as_token=True), 1)


@dataclass(frozen=True)
class ImprintDead:
    """Mimic Vat: "Whenever a nontoken creature dies, you may exile that card. If you do, return each other card exiled with this artifact
    to its owner's graveyard." (`Game.imprint_dead`)"""
    binds = SOURCE_AND_SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target[1] is not None:
            game.imprint_dead(target[0], target[1])


@dataclass(frozen=True)
class CopyExiledWith:
    """Mimic Vat: "Create a token that's a copy of a card exiled with this artifact." (its riders: "It gains haste. Exile it at the
    beginning of the next end step.")"""
    changes: CopyChanges | None = None
    count: Quantity = 1
    haste: bool = False
    sacrifice_at_end: bool = False
    exile_at_end: bool = False
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            finish_copies(game, game.copy_exiled_with(controller, target, self.changes), self)


@dataclass(frozen=True)
class DelinaRoll:
    """Delina, Wild Mage: "choose target creature you control, then roll a d20. 1\u201414 | Create a tapped and attacking token that's a
    copy of that creature, except it's not legendary and it has "At end of combat, exile this token." 15\u201420 | Create one of those
    tokens. You may roll again." (`Game.delina_roll`)"""
    target: str = "creature you control"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.resolving_source is not None:
            game.delina_roll(controller, game.resolving_source, target)


@dataclass(frozen=True)
class CopyAnotherAttacker:
    """Flamerush Rider: "create a token that's a copy of another target attacking creature and that's tapped and attacking. Exile the token
    at end of combat." (`Game.copy_attacking_creature`)"""
    target: str = "attacking creature"
    another: bool = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_attacking_creature(controller, target)


@dataclass(frozen=True)
class CopyDiscardedCard:
    """Hashaton, Scarab's Fist: "create a tapped token that's a copy of that card, except it's a 4/4 black Zombie." (that card: the one
    discarded, carried by the trigger)"""
    changes: CopyChanges | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        card = game.resolving_item.carried if game.resolving_item is not None else None
        if isinstance(card, Card):
            for made in game.create_tokens(controller, copy_of(card, self.changes, as_token=True), 1):
                made.tapped = True


def _keeping_this_ability(game: Game, changes: CopyChanges) -> CopyChanges:
    """ "except it has this ability": the text of the ability resolving, added to the copy."""
    if not changes.keeps_ability or game.resolving_item is None or game.resolving_item.ability is None:
        return changes
    return dataclasses.replace(changes, abilities=changes.abilities + (game.resolving_item.ability.text,), keeps_ability=False)


@dataclass(frozen=True)
class BecomeCopyOfSubject:
    """Sarkhan, Soul Aflame: "Whenever a Dragon you control enters, you may have CARDNAME become a copy of it until end of turn, except its
    name is CARDNAME and it's legendary in addition to its other types." (`Game.become_copy`)"""
    changes: CopyChanges
    until_end_of_turn: bool = True
    binds = SOURCE_AND_SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target[1] is not None and game.on_battlefield(target[0]):
            game.become_copy(target[0], target[1].card, _keeping_this_ability(game, self.changes), self.until_end_of_turn)


@dataclass(frozen=True)
class BecomeCopyOfTarget:
    """Thespian's Stage: "This land becomes a copy of target land, except it has this ability." Sunfrill Imitator: "... become a copy of
    another target Dinosaur you control, except its name is CARDNAME and it has this ability." (a lasting copy; `Game.become_copy`)"""
    target: str
    changes: CopyChanges
    another: bool = False
    optional_target: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_source
        if target is not None and source is not None and game.on_battlefield(source):
            game.become_copy(source, target.card, _keeping_this_ability(game, self.changes), False)


@dataclass(frozen=True)
class SawInHalf:
    """Saw in Half: "Destroy target creature. If that creature dies this way, its controller creates two tokens that are copies of that
    creature, except their power is half that creature's power and their toughness is half that creature's toughness. Round up each
    time." (`Game.saw_in_half`)"""
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.saw_in_half(target)


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
class CopyForEachOtherCreature:
    """Zada, Hedron Grinder: "copy that spell for each other creature you control that the spell could target. Each copy targets a
    different one of those creatures." (the spell, `carried`, targets only the source; the copies are its controller's)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if item is not None and item.source is not None and hasattr(item.carried, "targets"):
            game.copy_spell_for_each_other_creature(item.carried, controller, item.source)


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
    paying its mana cost." Mizzix's Mastery: "Exile target card that's an instant or sorcery ..." (one target, not "up to one"). Mnemonic
    Deluge: from any graveyard, three copies."""
    target: str = "graveyard:instant or sorcery:yours"
    optional_target: bool = True
    copies: int = 1  # Mnemonic Deluge: "Copy that card three times. You may cast the copies ..." (each one asked for)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or not game.exile_from_graveyard(target):
            return
        for _ in range(self.copies):
            if controller.player.choose(CAST_COPY_PROMPT(target.card.name), ["Yes", "No"]) == 0:
                game.cast_copy_free(controller, target.card)


CAST_COPY_PROMPT = PromptKind("cast_copy", "Cast a copy without paying its mana cost: ")  # followed by the card's name; Yes or No


@dataclass(frozen=True)
class ExileRandomThenCastCopiesOfExiled:
    """Arcane Bombardment: "exile an instant or sorcery card at random from your graveyard. Then copy each card exiled with this
    enchantment. You may cast any number of the copies without paying their mana costs." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        spells = [c for c in controller.graveyard if "Instant" in c.type_line or "Sorcery" in c.type_line]
        if spells:
            game.exile_from_graveyard(game.graveyard_target(game.rng.choice(spells), controller))  # noted as exiled with it
        game.cast_copies_free(controller, [card for owner, card in target.exiled_with if any(c is card for c in owner.exile)])


@dataclass(frozen=True)
class ExileEachThenCastCopies:
    """Mizzix's Mastery overloaded: "Exile each card that's an instant or sorcery from your graveyard. For each card exiled this way,
    copy it, and you may cast the copy without paying its mana cost." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        exiled = [c for c in list(controller.graveyard) if ("Instant" in c.type_line or "Sorcery" in c.type_line)
                  and game.exile_from_graveyard(game.graveyard_target(c, controller))]
        for card in exiled:
            if controller.player.choose(CAST_COPY_PROMPT(card.name), ["Yes", "No"]) == 0:
                game.cast_copy_free(controller, card)


@dataclass(frozen=True)
class CopyImprintedCastFree:
    """Isochron Scepter: "You may copy the exiled card. If you do, you may cast the copy without paying its mana cost." The card is the
    one exiled with the source, while it is still in exile; copying it without casting does nothing, so it is one question."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        for owner, card in list(target.exiled_with):
            if any(c is card for c in owner.exile) and controller.player.choose(CAST_COPY_PROMPT(card.name), ["Yes", "No"]) == 0:
                game.cast_copy_free(controller, card)


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
class ExileEachTypeCastCopies:
    """Uldaros Theorix: "exile up to one target nonland card of each card type from your graveyard. Copy those cards. You may cast any
    number of spells with total mana value 6 or less from among the copies without paying their mana costs." The cards are chosen as it
    resolves."""
    total: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_each_type_cast_copies(controller, self.total)


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
        count = game.amount(self.count)
        for i in range(count):
            if original is not None:
                game.copy_spell(original, controller, new_targets=True, extra=i == count - 1)  # (one copying: Twinning Staff adds one)


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
    the trigger off is `carried`. Storm of Saruman: "copy it, except the copy isn't legendary" (`changes`). Nalfeshnee: "If it's a
    permanent spell, the copy gains haste and ..." (`permanent_changes`, only for a permanent spell)."""
    new_targets: bool = False
    changes: CopyChanges | None = None
    permanent_changes: CopyChanges | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        spell = game.resolving_item.carried if game.resolving_item is not None else None
        if spell is not None:
            permanent = not any(t in spell.card.type_line for t in ("Instant", "Sorcery"))
            game.copy_spell(spell, controller, self.new_targets,
                            changes=self.permanent_changes if self.permanent_changes and permanent else self.changes)


@dataclass(frozen=True)
class _IfPermanentCopyGains:
    """Nalfeshnee: "If it's a permanent spell, the copy gains haste and "At the beginning of the end step, sacrifice this permanent."" after
    a CopyTriggeringSpell (see _merge_copy)."""
    changes: CopyChanges


@dataclass(frozen=True)
class ReturnTriggeringSpellToHand:
    """Krark, the Thumbless: "If you lose the flip, return that spell to its owner's hand." (the spell that set the trigger off)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        spell = game.resolving_item.carried if game.resolving_item is not None else None
        if spell is not None and spell in game.stack:
            game.stack.remove(spell)
            if not spell.is_copy:
                game._move_card(spell.controller, spell.physical, "hand")


@dataclass(frozen=True)
class CasterCopiesSpell:
    """Bonus Round: "whenever a player casts an instant or sorcery spell, that player copies it and may choose new targets for the
    copy." The copy is the caster's, not the controller's of the ability (the spell is `carried`)."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        spell = game.resolving_item.carried if game.resolving_item is not None else None
        if spell is not None:
            game.copy_spell(spell, spell.controller, new_targets=True)


@dataclass(frozen=True)
class CopyPreviousTarget:
    """Wild Ricochet: "You may choose new targets for target instant or sorcery spell. Then copy that spell." (the spell just targeted)"""
    new_targets: bool = False
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_spell(target, controller, self.new_targets)


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


@dataclass(frozen=True)
class BecomeCard:
    """The Irencrag: "you may have The Irencrag become a legendary Equipment artifact named Everflame, Heroes' Legacy. If you do, it
    gains equip {3} and "Equipped creature gets +3/+3" and loses all other abilities." (the trigger asks the "you may"). For good;
    it keeps its mana cost and colors, and the card it was is what leaves the battlefield (Game.become_card)."""
    card: Card
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.on_battlefield(target):
            was = target.card
            game.become_card(target, dataclasses.replace(self.card, mana_cost=was.mana_cost, cmc=was.cmc, colors=was.colors,
                                                         color_identity=was.color_identity))
