"""Effects of the "combat and pump" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...cards import Card
from ...characteristics import Modifier
from ..common import Quantity
from ..targets import PREVIOUS_TARGET, SOURCE, SUBJECT
from .base import Condition
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class GrantFlash:
    """Alchemist's Refuge: "You may cast spells this turn as though they had flash." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.flash_turn = game.turn


@dataclass(frozen=True)
class GrantSorceryFlash:
    """Teferi, Time Raveler: "Until your next turn, you may cast sorcery spells as though they had flash." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.sorcery_flash = True


@dataclass(frozen=True)
class TapOrUntap:
    """ "You may tap or untap target creature." """
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap_or_untap(controller, target)


@dataclass(frozen=True)
class Animate:
    """ "Until end of turn, this land becomes a 3/3 green Ape creature with trample. It's still a land." (the source:
    on_source) or "Target land you control becomes ..." (target)."""
    power: int
    toughness: int
    colors: tuple[str, ...]
    subtypes: str
    artifact: bool
    keywords: frozenset[str]
    target: str | None = None
    on_source: bool = False  # it is about the ability's source, not a chosen target
    on_your_turn: frozenset[str] = frozenset()  # keywords it has only during its controller's turn (Restless Spire)
    for_good: bool = False  # Soulstone Sanctuary: no "until end of turn", so it stays a creature
    grant: str = ""  # Great Hall of the Biblioplex: a quoted ability it gains
    unless_creature: bool = False  # Great Hall: "If this land isn't a creature, ..."

    @property
    def binds(self) -> str | None:
        return SOURCE if self.on_source else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or (self.unless_creature and "Creature" in target.card.type_line):
            return
        if self.for_good:
            game.animate_for_good(target, self.power, self.toughness, self.colors, self.subtypes, self.keywords, self.grant)
        else:
            game.animate(target, self.power, self.toughness, self.colors, self.subtypes, self.artifact, self.keywords,
                         self.on_your_turn)


@dataclass(frozen=True)
class AnimateByManaValue:
    """Karn, the Great Creator: "Until your next turn, up to one target noncreature artifact becomes an artifact creature with power and
    toughness each equal to its mana value." """
    target: str = "noncreature artifact"
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.animate_until_next_turn(controller, target)


@dataclass(frozen=True)
class Earthbend:
    """ "Earthbend 2.": target land you control becomes a 0/0 creature with haste that's still a land, gets that many +1/+1
    counters, and comes back to the battlefield tapped when it dies or is exiled (the keyword action's reminder text)."""
    count: int
    target: str = "land you control"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.earthbend(target, self.count)


@dataclass(frozen=True)
class StillALand:
    """ "It's still a land." Only ever the end of an Animate (see _merge_animate)."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone 'still a land' is never built")


@dataclass(frozen=True)
class Exploit:
    """Exploit: "When this creature enters, you may sacrifice a creature." (it may be itself, CR 702.110); if you do, the creature
    exploited a creature, which the abilities written "When this creature exploits a creature, ..." wait for."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exploit(target, controller)


@dataclass(frozen=True)
class Pump:
    """ "Target creature gets +3/+3 (and gains trample) until end of turn." """
    modifier: Modifier
    target: str
    optional_target: bool = False  # "One or two target creatures each get ...": the second may be left out
    distinct: bool = False
    more_keywords: frozenset[str] = frozenset()  # Violent Urge: "Delirium — If ..., that creature gains double strike until end of turn."
    more_if: Condition | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            modifier = self.modifier
            if self.more_if is not None and game.condition_holds(self.more_if, controller):
                modifier = dataclasses.replace(modifier, keywords=modifier.keywords | self.more_keywords)
            game.modify_until_end_of_turn(target, modifier)
            if game.resolving_item is not None and game.resolving_item.carried is None:
                game.resolving_item.carried = target  # "It fights ...": the creature just pumped


@dataclass(frozen=True)
class GrantProtection:
    """ "Target creature you control gains protection from the color of your choice until end of turn." (Mother of Runes,
    Gods Willing); the controller picks the color as it resolves. With no target it is the source itself."""
    target: str | None = None
    on_source: bool = False  # it is about the ability's source, not a chosen target

    @property
    def binds(self) -> str | None:
        return SOURCE if self.on_source else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.grant_protection_of_choice(target, controller)


@dataclass(frozen=True)
class DoubleStats:
    """ "Double target creature's power and toughness until end of turn." / "Double the power of each creature you control until end of
    turn." / "Double this creature's power until end of turn." / "double target creature's power X times": it gets +P/+T equal to its
    power and toughness as this resolves (again for each time), and several creatures are doubled together."""
    power: bool
    toughness: bool
    target: str | None = None  # "creature", "creature you control"
    each: bool = False  # each creature you control
    subtype: str = ""  # "each Dragon you control" (Thrakkus the Butcher)
    times: Quantity = 1  # "X times" (Exponential Growth)
    on_source: bool = False  # it is about the ability's source, not a chosen target

    @property
    def binds(self) -> str | None:
        return SOURCE if self.on_source else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = ([p for p in controller.battlefield if "Creature" in p.card.type_line
                      and (not self.subtype or self.subtype in p.card.type_line.partition("\u2014")[2].split())]
                     if self.each else [target] if target is not None else [])
        for _ in range(game.amount(self.times)):
            doubled = [(p, game.power(p) if self.power else 0, (game.toughness(p) or 0) if self.toughness else 0) for p in creatures]
            for permanent, power, toughness in doubled:
                game.modify_until_end_of_turn(permanent, Modifier(power, toughness))
        if target is not None and not self.each and game.resolving_item is not None and game.resolving_item.carried is None:
            game.resolving_item.carried = target  # "Then it fights ...": the creature just doubled


@dataclass(frozen=True)
class PumpSource:
    """ "This creature gets +1/+0 until end of turn." """
    modifier: Modifier
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.modify_until_end_of_turn(target, self.modifier)


@dataclass(frozen=True)
class BecomesTypeUntilEndOfTurn:
    """Sarkhan, Dragon Ascendant: "Until end of turn, Sarkhan becomes a Dragon in addition to his other types and gains flying." """
    subtype: str
    keywords: frozenset[str] = frozenset()
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.add_subtype_until_end_of_turn(target, self.subtype)
            if self.keywords:
                game.modify_until_end_of_turn(target, Modifier(keywords=self.keywords))


KEYWORD_CHOICE_PROMPT = PromptKind("keyword_choice", "Choose what it gains for ")  # followed by the source's name; options are the keywords


@dataclass(frozen=True)
class GainChosenKeyword:
    """Practiced Offense: "Target creature gains your choice of double strike or lifelink until end of turn." """
    keywords: tuple[str, ...]
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        name = game.resolving_item.card.name if game.resolving_item is not None else ""
        keyword = self.keywords[controller.player.choose(KEYWORD_CHOICE_PROMPT(name), list(self.keywords))]
        game.modify_until_end_of_turn(target, Modifier(keywords=frozenset({keyword})))


@dataclass(frozen=True)
class PumpSourceX:
    """ "This creature gets +X/+0 until end of turn." (X from "where X is ..."): multiples of X, like PumpX."""
    power: int
    toughness: int
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            x = game.amount("X")
            game.modify_until_end_of_turn(target, Modifier(self.power * x, self.toughness * x))


@dataclass(frozen=True)
class PumpEach:
    """ "Creatures you control get +3/+3 and gain trample until end of turn." Affects only the
    creatures there when it resolves (CR 611.2c). `opponents`: "Creatures your opponents control get -1/-1"."""
    modifier: Modifier
    opponents: bool = False
    everyone: bool = False  # "All creatures get -2/-2 until end of turn."
    subtype: str = ""  # "Spirits you control gain double strike and vigilance until end of turn." ("non-Human": all but those)
    other: bool = False  # Summon: Esper Maduin: "Other creatures you control ...": not its source
    untap: bool = False  # Jeskai Ascendancy: "Untap those creatures."
    attacking: bool = False  # Warren Warleader: "Attacking creatures you control get +1/+1 ..."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        seats = game.live_seats() if self.everyone else game.opponents(controller) if self.opponents else [controller]
        for seat in seats:
            for permanent in list(seat.battlefield):
                kinds = permanent.card.type_line.partition("\u2014")[2].split()
                if (self.other and permanent is game.resolving_source) or (self.attacking and not game._in_state(permanent, "attacking")):
                    continue
                if "Creature" in permanent.card.type_line and (
                        not self.subtype or (self.subtype.removeprefix("non-") in kinds) != self.subtype.startswith("non-")):
                    game.modify_until_end_of_turn(permanent, self.modifier)
                    if self.untap:
                        game.untap(permanent)


@dataclass(frozen=True)
class KindsGainUntilEndOfTurn:
    """Sapling Nursery: "Treefolk and Forests you control gain indestructible until end of turn." (`kind`: "Treefolk or Forest",
    any permanent of those types, a land as well as a creature)"""
    kind: str
    keywords: frozenset[str]
    until_next_turn: bool = False  # For the Common Good: "Then tokens you control gain indestructible until your next turn."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        from ...filters import has_type
        for permanent in list(controller.battlefield):
            if has_type(permanent.card, self.kind):
                if self.until_next_turn:
                    permanent.until_next_turn.append(Modifier(keywords=self.keywords))
                else:
                    game.modify_until_end_of_turn(permanent, Modifier(keywords=self.keywords))


@dataclass(frozen=True)
class SetBaseEachX:
    """Biomass Mutation: "Creatures you control have base power and toughness X/X until end of turn." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        x = game.amount("X")
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line:
                game.modify_until_end_of_turn(permanent, Modifier(set_pt=(x, x)))


@dataclass(frozen=True)
class PumpNamed:
    """Leitmotif Composer: "Creatures named CARDNAME can't be blocked this turn." Every creature with the source's name,
    whoever controls it."""
    modifier: Modifier

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        for seat in game.live_seats():
            for permanent in list(seat.battlefield):
                if item and permanent.card.name == item.card.name and "Creature" in permanent.card.type_line:
                    game.modify_until_end_of_turn(permanent, self.modifier)


@dataclass(frozen=True)
class PumpOtherAttackers:
    """Martial Impetus: "Each other creature that's attacking one of your opponents gets +1/+1 until end of turn." The
    creature that set the trigger off is the one left out."""
    modifier: Modifier

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        for attack in list(game.combat.attacks):
            if attack.attacker is not (item.subject if item else None) and attack.defender is not controller:
                game.modify_until_end_of_turn(attack.attacker, self.modifier)


@dataclass(frozen=True)
class PumpEachX:
    """ "All creatures get -X/-X until end of turn." (Toxic Deluge) / "Creatures you control get +X/+X ...": `power` and
    `toughness` are multiples of X."""
    power: int
    toughness: int
    opponents: bool = False
    everyone: bool = False
    keywords: frozenset[str] = frozenset()  # Moonshaker Cavalry: "gain flying and get +X/+X"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        x = game.amount("X")
        seats = game.live_seats() if self.everyone else game.opponents(controller) if self.opponents else [controller]
        for seat in seats:
            for permanent in list(seat.battlefield):
                if "Creature" in permanent.card.type_line:
                    game.modify_until_end_of_turn(permanent, Modifier(self.power * x, self.toughness * x, self.keywords))


@dataclass(frozen=True)
class PumpX:
    """ "Target creature gets +X/+X until end of turn." (X from "for each ..." or "where X is ..."): `power` and
    `toughness` are the multiples of X (1, 0 or -1)."""
    power: int
    toughness: int
    target: str
    keywords: frozenset[str] = frozenset()  # Tyvar's Stand: "... and gains hexproof and indestructible"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            x = game.amount("X")
            game.modify_until_end_of_turn(target, Modifier(self.power * x, self.toughness * x, self.keywords))
            if game.resolving_item is not None and game.resolving_item.carried is None:
                game.resolving_item.carried = target  # "Then it fights ...": the creature just pumped


@dataclass(frozen=True)
class Attach:
    """Equip: attach the Equipment that made this ability to the target creature."""
    target: str = "creature you control"
    another: bool = False  # Reconfigure: not the Equipment creature itself
    grant: frozenset[str] = frozenset()  # Silver Shroud Costume: "That creature gains shroud until end of turn."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.resolving_source is not None:
            game.attach(game.resolving_source, target)
            if self.grant:
                game.modify_until_end_of_turn(target, Modifier(keywords=self.grant))


@dataclass(frozen=True)
class ChooseEquipmentToAttach:
    """Thorin, Mountain-king: "attach any number of target Equipment you control" (AttachChosenEquipment, after it, names the creature)."""
    target: str = "Equipment you control"
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = list(target or [])


@dataclass(frozen=True)
class AttachChosenEquipment:
    """Thorin, Mountain-king: "... to target creature you control. When one or more Equipment become attached to that creature this way,
    that creature deals damage equal to its power to up to one target creature." (a reflexive trigger, CR 603.12, about that creature)."""
    target: str = "creature you control"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        chosen = game.resolving_item.carried if game.resolving_item is not None else None
        if target is None or not chosen:  # (an Equipment gone by now is no longer among the targets, CR 608.2b)
            return
        for equipment in chosen:
            game.attach(equipment, target)
        game.reflexive_trigger(controller, (SubjectDamagesTargetByPower(),), None, "that creature deals damage equal to its power to "
                               "up to one target creature", subject=target)


@dataclass(frozen=True)
class SubjectDamagesTargetByPower:
    """ "that creature deals damage equal to its power to up to one target creature": the creature the trigger is about."""
    target: str = "creature"
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creature = game.resolving_item.subject if game.resolving_item is not None else None
        if target is not None and creature is not None:  # gone: its last known power (CR 608.2h)
            game.damage(target, game.power(creature), source=creature)


@dataclass(frozen=True)
class Unattach:
    """Reconfigure's second ability: unattach this Equipment, which makes it a creature again."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.detach(target)


@dataclass(frozen=True)
class AttachAura:
    """The targeting of an Aura spell. The game attaches the Aura as it enters (Game._resolve)."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class OthersBecomeAsBigAsSource:
    """Tanazir Quandrix: "... the base power and toughness of other creatures you control become equal to Tanazir
    Quandrix's power and toughness until end of turn." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        size = (game.power(target), game.toughness(target) or 0)
        for permanent in controller.battlefield:
            if permanent is not target and "Creature" in permanent.card.type_line:
                game.modify_until_end_of_turn(permanent, Modifier(set_pt=size))


HERO = Card(name="Hero", type_line="Token Creature \u2014 Hero", power="1", toughness="1")  # Job select's 1/1 colorless Hero


@dataclass(frozen=True)
class LivingWeapon:
    """Living weapon: "When this Equipment enters, create a 0/0 black Phyrexian Germ creature token, then attach this to it." Job select
    (`hero`): the token is a 1/1 colorless Hero."""
    hero: bool = False
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.living_weapon(target, HERO if self.hero else None)


@dataclass(frozen=True)
class Backup:
    """Backup N: "When this creature enters, put N +1/+1 counters on target creature. If that's another creature, it
    gains the following abilities until end of turn." `granted` is the rest of the card's rules text."""
    count: int
    granted: str
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, "+1/+1", self.count)
            if target is not game.resolving_source:
                game.grant_abilities(target, self.granted)


@dataclass(frozen=True)
class AttachThisToSubject:
    """Shielded by Faith: "You may attach this Aura to that creature." (the creature that entered)"""
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.resolving_source is not None:
            game.attach(game.resolving_source, target)


@dataclass(frozen=True)
class _RecallAttachment:
    """The "When you do, return up to one target Aura or Equipment card from your graveyard to the battlefield attached to
    that token." sentence; only ever the second step of a CreateTokenWithGraveyardAttachment (see _merge_conditional)."""


@dataclass(frozen=True)
class TapAndGoad:
    """Killian, Decisive Mentor: "Tap up to one target creature and goad it." """
    target: str = "creature"
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)
            game.goad(target, controller)


@dataclass(frozen=True)
class _UntapThatLand:
    """ "Then if you control four or more lands, untap that land." """
    condition: "Condition"


@dataclass(frozen=True)
class _UntapThoseLands:
    """Spell mastery: "If there are two or more instant and/or sorcery cards in your graveyard, untap those lands." """
    condition: "Condition"


@dataclass(frozen=True)
class UntapThat:
    """ "Untap that creature." Only meaningful right after "Gain control of ...": _merge_control folds it in."""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class GainsAbility:
    """Urza's Saga: 'This Saga gains "{T}: Add {C}."' For as long as it stays on the battlefield its text has the line, as a Class's
    does once it levels up (the card it really is waits in `real_card` until it leaves)."""
    line: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_source
        if source is not None and game.on_battlefield(source):
            source.real_card = source.real_card or source.card
            made = re.match(r"\{T\}: Add ((?:\{[WUBRGC]\})+)\.", self.line)  # a land is told what it makes by its data
            produced = source.card.produced_mana + tuple(s for s in re.findall(r"[WUBRGC]", made[1]) if s not in source.card.produced_mana) if made \
                else source.card.produced_mana
            source.card = dataclasses.replace(source.card, oracle_text=f"{source.card.oracle_text}\n{self.line}", produced_mana=produced)


@dataclass(frozen=True)
class PlayerProtection:
    """The One Ring: "You gain protection from everything until your next turn." Nothing can target you and all damage to you is
    prevented, until your next turn begins."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.protected = True
        game.broadcast({"event": "protected", "seat": controller.index})


@dataclass(frozen=True)
class Tap:
    """ "Tap two target permanents.": one effect per target, each a different permanent."""
    target: str
    distinct: bool = False
    optional_target: bool = False
    strip_while_source: bool = False  # The Wondrous Wasp: "It loses all abilities for as long as CARDNAME remains on the battlefield."
    lock_while_tapped: bool = False  # Braided Net: "Its activated abilities can't be activated for as long as it remains tapped."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)
            if self.lock_while_tapped:
                target.locked_while_tapped = True
            if self.strip_while_source:
                game.strip_while(target, game.resolving_source)


@dataclass(frozen=True)
class VehicleBecomesCreature:
    """Bladewheel Chariot: "This Vehicle becomes an artifact creature until end of turn." (as crewing makes it)"""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.become_creature(target)


@dataclass(frozen=True)
class _LockedWhileTapped:
    """ "Its activated abilities can't be activated for as long as it remains tapped." after a Tap (Braided Net)."""


@dataclass(frozen=True)
class _LosesAbilitiesWhileSource:
    """ "It loses all abilities for as long as CARDNAME remains on the battlefield." after a Tap (The Wondrous Wasp)."""


@dataclass(frozen=True)
class LureThisTurn:
    """Roar of Challenge: "All creatures able to block target creature this turn do so." """
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.lured_turn = game.turn


@dataclass(frozen=True)
class AttackDespiteDefender:
    """ "This creature can attack this turn as though it didn't have defender." (Skyclave Squid, Krotiq Nestguard): the ability's source."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.defender_ok_turn = game.turn  # CR 702.3b: it attacks as though it had no defender, this turn only


@dataclass(frozen=True)
class MustBlockThisTurn:
    """ "Target creature blocks this turn if able." / "... blocks this creature this turn if able." (Torchling: that creature in
    particular, the source of the ability)"""
    target: str = "creature"
    source_only: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.must_block_turn = game.turn
            target.must_block_what = game.resolving_source if self.source_only else None


@dataclass(frozen=True)
class TapThat:
    """ "Tap it." / "Tap that creature.": the target of the effect before it."""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)


@dataclass(frozen=True)
class DoesntUntapNext:
    """Sleep of the Dead: "Tap target creature. It doesn't untap during its controller's next untap step." (Permanent.skips_next_untap)"""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.skips_next_untap = True


@dataclass(frozen=True)
class AttackersDontUntapNext:
    """Tangle: "Each attacking creature doesn't untap during its controller's next untap step." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for attack in game.combat.attacks:
            attack.attacker.skips_next_untap = True


@dataclass(frozen=True)
class BecomeCreature:
    """Crewing a Vehicle: until end of turn it is an artifact creature."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.become_creature(target)


@dataclass(frozen=True)
class FightFirst:
    """The first target of a fight ("Target creature you control ... fights ..."): remembered for the second."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


@dataclass(frozen=True)
class FightSourceFirst:
    """ "When this creature enters, it fights up to one target creature you don't control.": the creature that fights is the source."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


@dataclass(frozen=True)
class FightSubjectFirst:
    """Frontier Siege: "Whenever a creature you control with flying enters, you may have it fight target creature you don't control.":
    the creature that set the trigger off is the one that fights."""
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


@dataclass(frozen=True)
class Fight:
    """The second target of a fight. Each deals damage equal to its power to the other; with `one_sided` only the
    first does ("Target creature you control deals damage equal to its power to target creature you don't control")."""
    target: str
    one_sided: bool = False
    another: bool = False  # "fights another target creature": not the first target
    optional_target: bool = False  # "fights up to one target creature"
    follows: bool = False  # "It fights ...": the creature the sentence before it targeted, or the source if nothing did (see _merge_conditional)
    then: bool = False  # "Then it fights ...": there has to be a sentence before it, it is never the source

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        first = game.resolving_item.carried if game.resolving_item is not None else None
        if first is not None and target is not None and first is not target:
            game.fight(first, target, self.one_sided)


@dataclass(frozen=True)
class UntapCreatures:
    which: str  # "attacked": the creatures that attacked this turn; "yours": every creature you control

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in controller.battlefield:
            if "Creature" in permanent.card.type_line and (self.which == "yours" or permanent.attacked_turn == game.turn):
                game.untap(permanent)


UNTAP_CREATURE_PROMPT = PromptKind("untap_creature", "Untap which creature? ")


@dataclass(frozen=True)
class UntapACreature:
    """White Plume Adventurer: "Untap a creature you control." (you choose, not a target); with `all_if`, "If you've completed a dungeon,
    untap all creatures you control instead." (see _CONDITIONAL)."""
    all_if: Condition | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if self.all_if is not None and game.condition_holds(self.all_if, controller):
            UntapCreatures("yours").resolve(game, controller, target)
            return
        tapped = [p for p in controller.battlefield if p.tapped and "Creature" in p.card.type_line]
        if tapped:
            game.untap(tapped[controller.player.choose(UNTAP_CREATURE_PROMPT, [game.label(p) for p in tapped])])


@dataclass(frozen=True)
class _InsteadUntapAll:
    """ "If you've completed a dungeon, untap all creatures you control instead." after UntapACreature."""
    condition: Condition


@dataclass(frozen=True)
class Untap:
    """ "Untap target land." """
    target: str
    another: bool = False
    optional_target: bool = False  # "Untap up to two target lands"
    distinct: bool = False
    counter_if_artifact_creature: bool = False  # Tezzeret, Cruel Captain: "If it's an artifact creature, put a +1/+1 counter on it."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.untap(target)
            if self.counter_if_artifact_creature and "Artifact" in target.card.type_line and "Creature" in target.card.type_line:
                game.put_counters(target, "+1/+1", 1)


@dataclass(frozen=True)
class Explore:
    """ "Target creature you control explores." (CR 701.44; the Map token's ability)"""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.explore(controller, target)


UNTAP_LANDS_PROMPT = PromptKind("untap_lands", "Untap which land? ")


DONE = "Done"


@dataclass(frozen=True)
class UntapLands:
    """ "Untap up to three lands." (Frantic Search, Snap): you choose, not a target."""
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for _ in range(self.count):
            tapped = [p for p in controller.battlefield if p.tapped and "Land" in p.card.type_line]
            if not tapped:
                return
            choice = controller.player.choose(UNTAP_LANDS_PROMPT, [game.label(p) for p in tapped] + [DONE])
            if choice >= len(tapped):
                return
            game.untap(tapped[choice])
            game.broadcast({"event": "untapped", "seat": controller.index, "card": tapped[choice].card.name})


@dataclass(frozen=True)
class UntapSource:
    """ "Untap it" / "Untap this creature": the ability's source (or, in a watching trigger, the permanent that set it off)."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.untap(target)


@dataclass(frozen=True)
class UntapAll:
    """ "Untap all lands you control." """
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.untap_all(controller, self.kind)


@dataclass(frozen=True)
class TapAll:
    """ "Tap all creatures your opponents control." Naya Charm: "... target player controls." (`target` "player")"""
    target: str | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in ([target] if target is not None else []) if self.target else game.opponents(controller):
            for permanent in seat.battlefield:
                if "Creature" in permanent.card.type_line:
                    game.tap(permanent)


@dataclass(frozen=True)
class BecomePrepared:
    """ "This creature becomes prepared." While it is, its controller may cast a copy of its spell half (see
    Game.legal_actions); doing so unprepares it. Only creatures with a prepare spell can become prepared."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.prepare(target)


@dataclass(frozen=True)
class Transform:
    """ "Transform this creature." A daybound permanent only turns over with the day/night rule (see Game.transform)."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.transform(target)


REMOVE_TRANSFORM_PROMPT = PromptKind("remove_transform", "Remove the counters and transform ")  # followed by the name; Yes or No


@dataclass(frozen=True)
class MayRemoveCountersTransform:
    """Primal Amulet: "Then if there are four or more charge counters on it, you may remove those counters and transform it." (the
    counter is the condition's, filled in as the sentence is read)"""
    counter: str = ""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and self.counter and controller.player.choose(REMOVE_TRANSFORM_PROMPT(target.card.name), ["Yes", "No"]) == 0:
            target.counters.pop(self.counter, None)
            game.transform(target)


@dataclass(frozen=True)
class RevealTopTransform:
    """Delver of Secrets: "Look at the top card of your library. You may reveal that card. If an instant or sorcery card is revealed this
    way, transform this creature." Such a card is always revealed: nothing else happens if it is."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        top = controller.library[0] if controller.library else None
        if target is not None and top is not None and ("Instant" in top.type_line or "Sorcery" in top.type_line):
            game.broadcast({"event": "revealed", "seat": controller.index, "card": top.name})
            game.transform(target)


@dataclass(frozen=True)
class NinjutsuEnter:
    """The effect of Ninjutsu: "Put this card onto the battlefield from your hand tapped and attacking." (the game fills in whom)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.ninjutsu_enter(controller, game.resolving_item)


@dataclass(frozen=True)
class BecomeRenowned:
    """Renown: "... and it becomes renowned." It won't trigger again (the condition "if it isn't renowned")."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.renowned = True


@dataclass(frozen=True)
class TargetPrepared:
    """ "Target creature becomes prepared / unprepared." Only a creature with a prepare spell can become prepared."""
    target: str  # "creature" or "creature that attacked this turn"
    prepared: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.prepare(target) if self.prepared else game.unprepare(target)


@dataclass(frozen=True)
class PrepareEach:
    """ "Each creature you control becomes prepared." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            game.prepare(permanent)


@dataclass(frozen=True)
class TapEnchanted:
    """An Aura's "When this Aura enters, tap enchanted creature." (Infinite Coursework adds "It becomes unprepared.") With `untap`,
    Freed from the Real's "{U}: Untap enchanted creature." """
    unprepare: bool = False
    untap: bool = False
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        host = target.attached_to if target is not None else None
        if host is not None and game.on_battlefield(host) and self.untap:
            game.untap(host)
        elif host is not None and game.on_battlefield(host):
            game.tap(host)
            if self.unprepare:
                game.unprepare(host)


@dataclass(frozen=True)
class Goad:
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.goad(target, controller)


@dataclass(frozen=True)
class GoadAll:
    """ "Goad all creatures you don't control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            for permanent in list(seat.battlefield):
                if "Creature" in permanent.card.type_line:
                    game.goad(permanent, controller)


@dataclass(frozen=True)
class EntersTapped:
    """How a permanent (usually a land) may enter tapped. `kind` is one of: "always",
    "unless_land_types" (checklands), "unless_lands_at_most" (fastlands), "unless_lands_at_least"
    (slowlands), "unless_opponents" (bond lands), "unless_basic_lands" (Port-style lands), "unless_land_type_count"
    ("three or more other Islands"), "unless_opponent_lands" (Turbulent lands), "reveal" (Snarls: reveal a card from your
    hand or it enters tapped), "shock" (pay life or it enters tapped),
    "unless_control" (`types` are alternatives, each "Legendary+Creature"-style words that must all be types of one
    permanent you control), "unless_a_player_life" (a player has `count` or less life), "if_lands_at_least" (tapped if
    you control `count` or more other lands), "if_starting_player", and the two that carry a `condition` of the intervening-if grammar
    (#569): "unless_condition" (tapped unless it holds: Starting Town's "it's your first, second, or third turn of the game", The Lonely
    Mountain's "you control an Equipment") and "if_condition" (tapped if it holds: Eddymurk Crab's "it's not your turn"). A new wording
    is a row of `_CONDITIONS`, not a kind here; the kinds above are the older wordings, each with its own branch."""
    kind: str
    types: tuple[str, ...] = ()
    count: int = 0
    life: int = 0
    condition: "Condition | None" = None


@dataclass(frozen=True)
class BecomeLandUntilNextTurn:
    """Hydro-Man: "Until your next turn, he becomes a land and gains "{T}: Add {U}." (He's not a creature during that time.)"
    (Game.become_land_until_next_turn)"""
    color: str
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.on_battlefield(target):
            game.become_land_until_next_turn(controller, target, self.color)
