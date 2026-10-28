"""What a spell or ability does: the effect classes and the sentence templates that read rules text into them."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, Literal

from ..cards import Card
from ..characteristics import LOSES_HEXPROOF, Modifier

if TYPE_CHECKING:
    from ..game import Game, Seat

from .common import (
    CANT_BE_BLOCKED,
    CANT_BLOCK,
    _ANY_N,
    _CHANGE,
    _COLOR_LETTER,
    _COUNTER,
    _KEYWORDS,
    _KEYWORDS_BARE,
    _LAND_TYPE,
    _MANA_SYMBOLS,
    _N,
    _N_FIXED,
    _NUM,
    _PT,
    _PT_X,
    _SELF,
    _VOTE_PREFIX,
    _count,
    _counter_name,
    _keyword_list,
    _modifier,
    _number,
    _signed,
    _split_sentences,
    cant_be_countered,
    Quantity,
)
from .families.base import (  # noqa: F401
    Amount,
    Condition,
)
from .families.combat_and_pump import (  # noqa: F401
    Animate,
    Attach,
    AttachAura,
    AttachThisToSubject,
    Backup,
    BecomeCreature,
    BecomePrepared,
    BecomeRenowned,
    DONE,
    DoubleStats,
    EntersTapped,
    Exploit,
    Fight,
    FightFirst,
    FightSourceFirst,
    GainsAbility,
    Goad,
    GoadAll,
    GrantFlash,
    GrantProtection,
    LivingWeapon,
    LureThisTurn,
    MustBlockThisTurn,
    AttackDespiteDefender,
    NinjutsuEnter,
    OthersBecomeAsBigAsSource,
    PlayerProtection,
    PrepareEach,
    Pump,
    PumpEach,
    PumpEachX,
    PumpNamed,
    PumpOtherAttackers,
    PumpSource,
    PumpSourceX,
    PumpX,
    SetBaseEachX,
    StillALand,
    Tap,
    TapAll,
    TapAndGoad,
    TapEnchanted,
    TapOrUntap,
    TapThat,
    TargetPrepared,
    Transform,
    UNTAP_LANDS_PROMPT,
    Unattach,
    Untap,
    UntapAll,
    UntapCreatures,
    UntapLands,
    UntapSource,
    UntapThat,
    _RecallAttachment,
    _UntapThatLand,
    _UntapThoseLands,
)
from .families.copying import (  # noqa: F401
    BecomeCopyUntilEndOfTurn,
    CAST_COPY_PROMPT,
    CHOOSE_COPY_PROMPT,
    COPY_THIS_PROMPT,
    CastExiledCopy,
    CopiesOfAnotherCreature,
    CopyChanges,
    CopyChosenPermanent,
    CopyEachToken,
    CopyEnteredTokensAttacking,
    CopyHostToken,
    CopyNextSpell,
    CopySelfToken,
    CopySpell,
    CopySpellForEachOtherCreature,
    CopySpellTimes,
    CopySubjectToken,
    CopyToken,
    CopyTokenAttacking,
    CopyTokensOfTargets,
    CopyTriggeredAbility,
    CopyTriggeringAbility,
    CopyTriggeringSpell,
    EachOpponentGetsGoadedCopy,
    ExileDeadCopy,
    ExileThenCastCopy,
    MayCopyLeftCard,
    _TwiceFromGraveyard,
    MayCopyThisSpellFromGraveyard,
    TokenOrSelfCopy,
    TokensBecomeCopies,
    _COPY_CARD_TYPES,
    _CopyEachWithHaste,
    _OthersBecomeCopies,
    apply_copy_changes,
    copy_of,
)
from .families.counters import (  # noqa: F401
    Amass,
    DISTRIBUTE_PROMPT,
    DistributeCounters,
    DoubleCounters,
    DoubleCountersOnSource,
    DoubleCountersOnTarget,
    DoubleAllCountersOnTargets,
    DoubleCountersOnTargets,
    EachExilesGraveyardCardCounters,
    ExileWithTimeCounters,
    Hideaway,
    LevelUp,
    MOVE_COUNTERS_PROMPT,
    MoveCountersFrom,
    MoveCountersOnto,
    MoveCountersToOthers,
    OpponentsLoseCounters,
    PUT_COUNTERS_PROMPT,
    Proliferate,
    PutCounterOnHost,
    PutCounterPerPlayer,
    PutCounters,
    PutCountersOnChosenCreature,
    PutCountersOnEach,
    PutCountersOnEachUpToX,
    PutCountersOnEntered,
    PutCountersOnSource,
    PutStunCounters,
    PutStunOnEach,
    PutStunOnSource,
    RemoveAllCountersDraw,
    RemoveCounters,
    RemoveCountersFromSource,
    SHIFT_COUNTERS_PROMPT,
    SHIFT_ONTO_PROMPT,
    TargetPutsCountersOnEach,
    VOW_PROMPT,
    VowCounters,
    _PutCountersAndAttach,
)
from .families.destroy_and_sacrifice import (  # noqa: F401
    CHOOSE_TYPE_PROMPT,
    CannotRegenerate,
    Destroy,
    DestroyAll,
    DestroyAllOfChosenType,
    DestroyUpToX,
    DestroyX,
    EachSacrifices,
    MaySacrificeThen,
    Regenerate,
    RegenerateEach,
    RegenerateSource,
    SacrificeAll,
    SacrificeCreature,
    SacrificeSelf,
    SacrificeUnlessPay,
    TargetSacrifices,
    TragicArrogance,
    _MaySacrifice,
    _SacrificeThemLater,
)
from .families.exile_and_return import (  # noqa: F401
    CastExiledWithFree,
    DECLINE,
    EachSacrificesThenReturn,
    Exile,
    ExileAll,
    ExileAllGraveyards,
    ExileEnchanted,
    ExileFromGraveyard,
    ExileGraveyard,
    ExileInstead,
    ExileOwnGraveyard,
    ExileTargetIfDies,
    ExileThisSpell,
    ExileTop,
    _ChooseOneOfThem,
    ExileTopCastAura,
    ExileTopOfEachCastFree,
    ExileTopOfThatPlayerMayCast,
    ExileUntilLeaves,
    ExileUntilNonlandCast,
    ExileX,
    FREE_CAST_PROMPT,
    Flicker,
    GiveBack,
    MayCastFromHandFree,
    PayToReturnSelf,
    PhaseOut,
    PhaseOutAll,
    PlayExiled,
    PlayExiledCard,
    PutExiledWithIntoGraveyard,
    RETURN_LAND_PROMPT,
    ReturnAllFromGraveyard,
    ReturnAllToHand,
    ReturnAuraToBattlefield,
    ReturnChosen,
    ReturnDeadAtNextUpkeep,
    ReturnDeadToBattlefield,
    ReturnExiledToGraveyard,
    ReturnFromGraveyard,
    ReturnLater,
    ReturnOwnLand,
    ReturnSelfAsEnchantment,
    ReturnSelfToBattlefield,
    ReturnSelfToHand,
    ReturnSpellToHand,
    ReturnThisFromGraveyard,
    ReturnToHand,
    ReturnTransformed,
    ReturnWhenItDiesThisTurn,
    ReturnWithCounter,
    SacrificeToReturnChosen,
    SacrificeUnlessReturnLand,
    _ExileThemLater,
    _IfExiledThen,
    _PlayTheExiledCard,
)
from .families.library_and_hand import (  # noqa: F401
    BASIC_LAND_TYPES,
    GreatestPowerMayDraw,
    Cascade,
    DanceWithCalamity,
    DelayedDraw,
    Discard,
    DiscardChosen,
    DiscardHandsDrawGreatest,
    Draw,
    DrawThenPutBack,
    EXILE_DISCARDED_PROMPT,
    EachDraw,
    EachDrawsThenDiscards,
    EachMayWheel,
    EachSacrificesOrDiscards,
    ExileControllerDraws,
    ExileDiscarded,
    FetchBasicLand,
    ImprintFromHand,
    Impulse,
    LookAtHand,
    LookAtTop,
    LookPutAttachment,
    LookPutPermanents,
    LookTakeRestBottom,
    LookTopTakeChosen,
    MayDiscardThenDraw,
    MayRemoveCounterThenDraw,
    MaySacrificeThenDraw,
    Mill,
    MillThenExileRandomPlay,
    MillThenReturn,
    PilesOfFour,
    PutAttackingFromHand,
    PutBackTop,
    PutCreatureFromHand,
    PutFromHand,
    PutSourceOnLibraryTop,
    RestOnBottom,
    RevealHand,
    RevealLands,
    RevealTop,
    RevealTopPutAll,
    RevealTopStep,
    RevealUntilAura,
    Scry,
    SearchForLands,
    SearchLandWhileBehind,
    SearchLibrary,
    SearchMany,
    ShuffleIntoLibrary,
    ShuffleRevealCast,
    ShuffleThisSpell,
    SurgeToVictory,
    Surveil,
    TakeFromTop,
    TargetChooseDiscard,
    TargetControllerMayFetchBasicLand,
    TargetDiscard,
    TargetDraw,
    TargetDrawDiscard,
    TargetDrawLose,
    TargetDrawXPlusCasts,
    TargetMill,
    TargetMillThenReturn,
    ThreeWaySplit,
    YouAndTargetDraw,
    _IfYouDoDraw,
    _InsteadDraw,
    _InsteadTake,
    _MayDiscard,
    _MayShuffle,
    _PutFromAmongThem,
    _SplitTop,
    _card_matches_kind,
)
from .families.life_and_damage import (  # noqa: F401
    Annihilate,
    Damage,
    DamageFromSubject,
    DamageEach,
    DamageTargetsController,
    DamageToYou,
    DamageWhatItAttacks,
    Drain,
    DrawHalfLibraryLoseHalfLife,
    EachCreatureDamagesItsController,
    EachDamagesItself,
    EachPlayerLosesLife,
    ExileDamagedIfDie,
    GainLife,
    GainLifeItLost,
    GivePoison,
    LifeLocked,
    LoseAllButOneLife,
    LoseLife,
    OpponentsLoseLife,
    PlayerLosesLife,
    PoisonShrinksOpponentsCreatures,
    PowerDamageToEachOther,
    PreventAllCombatDamage,
    WinGame,
    PreventCombatDamageToYou,
    PreventNext,
    RevealTopToHandDrain,
    RevealTopTradeLife,
    TargetControllerGainsLife,
    TargetControllerGainsLifeEqualToPower,
    TargetGainLife,
    TargetLoseHalfLife,
    TargetLoseLife,
    WhenThatDealsCombatDamage,
    _GainLifeLost,
)
from .families.mana import (  # noqa: F401
    AddDevotionMana,
    AddMana,
    AddManaForEach,
    AddManaPerCardInHand,
    AddManaPerTappedLand,
    ExtraMountainMana,
    KeepManaThisTurn,
    LoseLifeEqualToManaValue,
    PayLifeForMana,
    PlayersLoseSacrificeAddManaDraw,
    _DelayedMana,
    _InsteadMana,
    _ManaForEachDestroyed,
)
from .families.spells_and_misc import (  # noqa: F401
    GetEmblem,
    CHANGE_TARGET_PROMPT,
    COMMANDER_HAND_PROMPT,
    ChangeTarget,
    ChaosWarp,
    ChooseFromHand,
    ChooseTarget,
    CommanderToHand,
    PutThisFromCommandZone,
    Conditional,
    Counter,
    CreateDelayedTrigger,
    DefineX,
    DoubleXOfTriggeringSpell,
    HYPOTHESIS_COUNTER_PROMPT,
    IfKicked,
    IfNotKicked,
    KickedInstead,
    KickedReplaces,
    MayPay,
    MayPayCountersOnSubject,
    MayPayLoot,
    Modal,
    ModifiedGainHexproof,
    NewTargetMustBe,
    NewTargets,
    OnPlayer,
    OnSubject,
    OnSubjectController,
    PARITY_PROMPT,
    UnlessPays,
    WardCounter,
    ZimonesHypothesis,
    _ChaosPut,
    _ChooseAnyNumber,
    _GiftMatch,
    _IfYouDo,
    _ItGains,
    _ItHas,
    _KickedInsteadTail,
    _MayRemoveCounter,
    _ThatAlsoGains,
    _TheyGain,
    _TheyGainHaste,
    _TokenAttacksThisCombat,
)
from .families.tokens import (  # noqa: F401
    AttackerCreatesAttackingToken,
    AttackingTokens,
    CONTRACT_TEXT,
    Conjure,
    Connive,
    ContractAttack,
    CreateContract,
    CreateOneOfTokens,
    CreateTokenAttachSource,
    CreateTokenAttachSubject,
    CreateTokenWithGraveyardAttachment,
    CreateTokens,
    EachCreatesTokens,
    ExiledOwnerGetsToken,
    ManifestDread,
    POPULATE_PROMPT,
    Populate,
    TOKEN_CHOICE_PROMPT,
    TargetControllerCreatesTokens,
    TargetControllerManifests,
    TargetCreatesTokens,
    TokensJoinAttack,
    _AttachItToToken,
    _ChooseToken,
    _ExileThoseTokens,
    _ExileTokenAtEnd,
    _InsteadTokens,
    _PopulatedTokenRider,
    _TokenGainsHaste,
    _TokenHasHaste,
    _TokenPerPrevented,
)
from .families.turns_and_control import (  # noqa: F401
    BecomeMonarch,
    DEMONSTRATE_OPPONENT_PROMPT,
    DEMONSTRATE_PROMPT,
    Demonstrate,
    ExtraCombat,
    ExtraLandDrop,
    ExtraTurn,
    GainControl,
    OpponentsCantCast,
    SylvanLibrary,
    TakeInitiative,
    TargetExtraTurn,
)
from .families.votes import (  # noqa: F401
    ExileMostVoted,
    PastOrPresentVote,
    ThroneOfTheDeadThree,
    Vote,
    VoteOutcome,
    VoteStart,
    VoteToExile,
)
from .follow import Follow, Follows, set_fields
from .targets import (
    MassFilter,
    _CARDS_PLURAL,
    _CARD_TYPE,
    _LAND_TYPES,
    _LAND_TYPES_PLURAL,
    _SEARCH_TYPE,
    _SEARCH_TYPES,
    _card_kind,
    _graveyard_kind,
    _land_types,
    CONTEXT_BINDINGS,
    DEAD_SOURCE,
    DEAD_SUBJECT,
    PLAYER,
    PREVIOUS_TARGET,
    SOURCE,
    SOURCE_AND_SUBJECT,
    SUBJECT,
    binding,
    target_kind,
)


_MODAL_COUNTS = {"one": (1, 1), "up to one": (0, 1), "two": (2, 2), "three": (3, 3), "one or both": (1, 2), "one or more": (1, 0)}


_MODAL_HEADER = re.compile(r"Choose (one or both|one or more|up to one|one|two|three) \u2014", re.I)


_MODAL_REPEAT = re.compile(r"Choose (three|four|five|up to four)\. You may choose the same mode more than once\.")


_REPEAT_COUNTS = {"three": (3, 3), "four": (4, 4), "five": (5, 5), "up to four": (0, 4)}


_MODAL_PAWPRINTS = re.compile(r"Choose up to (one|two|three|four|five) \{P\} worth of modes\. You may choose the same mode more than once\.")


_PAWPRINT_MODE = re.compile(r"((?:\{P\})+) \u2014 (.+)")


_PAWPRINT_COUNTS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def _parse_pawprint_modal(how: str, lines: list[str]) -> list | None:
    """A Season: "Choose up to five {P} worth of modes. You may choose the same mode more than once." and modes written "{P}{P} \u2014 ..."."""
    modes, texts, costs = [], [], []
    for line in lines:
        if not (m := _PAWPRINT_MODE.fullmatch(line)):
            return None
        whole = _template(m[2])  # a mode of two sentences that only read together ("Choose artifact or enchantment. Destroy ...")
        effects = ([whole] if not isinstance(whole, list) else whole) if whole is not None else _parse(_split_sentences(m[2]))
        if not effects:
            return None
        modes.append(tuple(effects))
        texts.append(line)
        costs.append(len(m[1]) // 3)
    return [Modal(0, _PAWPRINT_COUNTS[how], tuple(modes), tuple(texts), repeat=True, costs=tuple(costs))] if modes else None


_SPREE_MODE = re.compile(r"\+ ((?:\{[^}]+\})+) \u2014 (.+)")


def _parse_spree(lines: list[str]) -> list | None:
    """Spree: "+ {1}{U} \u2014 Counter target spell." Each mode has its own additional cost; the caster chooses one or more of them (CR 702.172)."""
    modes, texts, costs = [], [], []
    for line in lines:
        if not (m := _SPREE_MODE.fullmatch(line)):
            return None
        whole = _template(m[2])  # a mode of two sentences that only read together
        effects = ([whole] if not isinstance(whole, list) else whole) if whole is not None else _parse(_split_sentences(m[2]))
        if not effects:
            return None
        modes.append(tuple(effects))
        texts.append(line)
        costs.append(m[1])
    return [Modal(1, len(modes), tuple(modes), tuple(texts), mode_costs=tuple(costs))] if modes else None


_MODAL_COMMANDER = re.compile(r"Choose one\. If you control a commander as you cast this spell, you may choose both instead\.")


def is_modal_header(line: str) -> bool:
    return (line == "Spree" or _MODAL_HEADER.fullmatch(line) is not None or _MODAL_REPEAT.fullmatch(line) is not None
            or _MODAL_PAWPRINTS.fullmatch(line) is not None or _MODAL_COMMANDER.fullmatch(line) is not None)


def mode_text(line: str) -> str:
    """A mode of a modal spell without its bullet (or a Spree mode without its cost)."""
    if m := _SPREE_MODE.fullmatch(line):
        return m[2]
    return line[2:] if line.startswith("\u2022 ") else line


def _parse_modal(how: str, lines: list[str], repeat: bool = False) -> list | None:
    modes, texts = [], []
    for line in lines:
        if not line.startswith("\u2022 "):
            return None  # something other than modes (entwine, escalate, ...)
        effects = _parse(_split_sentences(mode_text(line)))
        if not effects:
            return None
        modes.append(tuple(effects))
        texts.append(mode_text(line))
    if repeat:  # a mode may be chosen again, so two modes can fill "choose three"
        low, high = _REPEAT_COUNTS[how]
        return [Modal(low, high, tuple(modes), tuple(texts), repeat=True)] if modes else None
    low, high = _MODAL_COUNTS[how]
    high = high or len(modes)
    return [Modal(low, high, tuple(modes), tuple(texts))] if len(modes) >= max(low, 1) else None


_MODAL_DIFFERENT = re.compile(r"you may choose two\. Each mode must target a different player\. (\u2022 .+)")


_MODAL_INLINE = re.compile(r"choose (one or both|one or more|up to one|one|two|three) \u2014 (\u2022 .+)", re.I)


def _parse_modal_inline(text: str) -> list | None:
    """The modes of a modal triggered or activated ability, joined onto its line (see _join_modes), or None if
    the text isn't one."""
    if not (m := _MODAL_INLINE.fullmatch(text)):
        return None
    return _parse_modal(m[1].lower(), ["\u2022 " + part for part in m[2].removeprefix("\u2022 ").split(" \u2022 ")])


_ENCHANT_HEAD = (r"(?:(?:non-?[a-z]+|basic|tapped) )?(?:land|creature|artifact|enchantment|planeswalker|permanent|equipment"
                 r"|wall|vehicle|forest|plains|island|swamp|mountain)")
_ENCHANT = re.compile(rf"Enchant (creature card in a graveyard|{_ENCHANT_HEAD}(?:,? (?:or )?{_ENCHANT_HEAD})*"
                      r"(?: an opponent controls| you control| you don't control)?)", re.I)


_COPY_COLORS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
_COPY_KEYWORDS = {"flying", "haste", "vigilance", "lifelink", "deathtouch", "trample", "menace", "reach", "first strike", "double strike",
                  "indestructible", "hexproof", "myriad"}


def _understood_ability(text: str) -> bool:
    """Whether the engine understands `text` as the rules text of a creature, so a copy given it does what it says."""
    from ..report import unsupported_lines
    return not unsupported_lines(Card(name="Copy", type_line="Creature", oracle_text=text, power="1", toughness="1"))


_COPY_QUOTE = re.compile(r'"([^"]+)"')
_COPY_SPLIT = re.compile(r",\s*(?:and\s+)?|\s+and,?\s+")  # (Moritte: "... types and, if it's a creature, it enters ...")


def _copy_changes(text: str) -> CopyChanges | None:
    """Read the clauses after "except"; None if any is something the engine does not apply (so the line stays unsupported)."""
    fields: dict[str, Any] = {}
    types: list[str] = []
    supertypes: list[str] = []
    colors: list[str] = []
    keywords: list[str] = []
    abilities: list[str] = []
    quoted: list[str] = []
    text = _COPY_QUOTE.sub(lambda m: quoted.append(m[1]) or f"\x00{len(quoted) - 1}\x00", text.strip().rstrip("."))
    text = text.replace("colors and types", "colors_and_types").replace("it enters with X additional", "it enters with X_additional")
    after_keywords = False
    for clause in _COPY_SPLIT.split(text):
        clause = clause.strip()
        was_keywords, after_keywords = after_keywords, False
        if not clause or re.fullmatch(r"if it's a creature", clause, re.I):  # Moritte: "..., if it's a creature, it enters with ..." (counters only go on a creature anyway)
            continue
        if re.fullmatch(r"(?:it|the token)? ?(?:isn't|is not|'s not) legendary|it's not legendary", clause, re.I):
            fields["not_legendary"] = True
        elif re.fullmatch(r"(?:it|the token)? ?(?:isn't|is not|'s not) legendary if (?:that|equipped|enchanted|the) [A-Za-z]+ is legendary", clause, re.I):
            fields["not_legendary"] = True  # Helm of the Host, Miirym, Spark Double, Double Major: a copy that was never legendary is unchanged
        elif m := re.fullmatch(r"(?:it's |the token is |is )?(\d+)/(\d+)", clause, re.I):
            fields["power_toughness"] = (m[1], m[2])
        elif m := re.fullmatch(r"(?:it's |is )?an? (\d+)/(\d+) (white|blue|black|red|green) ([A-Za-z ]+) in addition to its other colors_and_types",
                               clause, re.I):
            fields["power_toughness"] = (m[1], m[2])
            colors.append(_COPY_COLORS[m[3].lower()])
            types.extend(w.capitalize() for w in m[4].split())
        elif m := re.fullmatch(r"(?:it's |is )?an? (\d+)/(\d+) (white|blue|black|red|green) ([A-Z][a-z]+)", clause):  # The Scarab God
            fields["power_toughness"] = (m[1], m[2])
            fields["set_colors"] = (_COPY_COLORS[m[3].lower()],)
            fields["set_subtypes"] = (m[4],)
        elif m := re.fullmatch(r"(?:it's |is )?(legendary|snow)(?: and (legendary|snow))?(?: in addition to its other types)?", clause, re.I):
            supertypes.extend(w.capitalize() for w in (m[1], m[2]) if w)
        elif m := re.fullmatch(r"(?:it's |is )?an? (artifact|enchantment)", clause, re.I):  # Machine God's Effigy: "it's an artifact"
            types.append(m[1].capitalize())
        elif m := re.fullmatch(r"(?:it's |is )?an? ([A-Za-z ]+?) in addition to its other (?:creature )?types", clause, re.I):
            types.extend(w.capitalize() for w in m[1].split())
        elif m := re.fullmatch(r"(?:it |the token )?has \x00(\d+)\x00", clause, re.I):
            if not _understood_ability(quoted[int(m[1])]):
                return None
            abilities.append(quoted[int(m[1])])
        elif m := re.fullmatch(r"(?:it |the token )?has ([a-z ]+)", clause, re.I):
            if m[1].lower() not in _COPY_KEYWORDS and not _understood_ability(m[1].capitalize()):
                return None
            keywords.append(m[1].lower())
            after_keywords = True
        elif was_keywords and (clause.lower() in _COPY_KEYWORDS or _understood_ability(clause.capitalize())):  # "it has flying and haste"
            keywords.append(clause.lower())
            after_keywords = True
        elif re.fullmatch(r"it enters with an additional \+1/\+1 counter on it if it's a creature", clause, re.I):
            fields["extra_counters"] = "1"
        elif m := re.fullmatch(r"it enters with (two|three) additional \+1/\+1 counters on it", clause, re.I):  # Moritte of the Frost
            fields["extra_counters"] = str(_number(m[1]))
        elif re.fullmatch(r"it enters with X_additional \+1/\+1 counters on it", clause, re.I):
            fields["extra_counters"] = "X"
        elif re.fullmatch(r"it enters with an additional loyalty counter on it if it's a planeswalker", clause, re.I):
            fields["extra_loyalty"] = 1
        else:
            return None
    return CopyChanges(
        not_legendary=fields.get("not_legendary", False), power_toughness=fields.get("power_toughness"),
        add_types=tuple(types), keywords=tuple(keywords), add_colors=tuple(colors), abilities=tuple(abilities),
        extra_counters=fields.get("extra_counters", ""), extra_loyalty=fields.get("extra_loyalty", 0), supertypes=tuple(supertypes),
        set_colors=fields.get("set_colors"), set_subtypes=fields.get("set_subtypes"))




def _merge_attacking_tokens(effects: list) -> list | None:
    merged: list = []
    for effect in effects:
        if isinstance(effect, _TheyGainHaste) and merged and isinstance(merged[-1], CreateTokens):  # Sokenzan
            merged[-1] = dataclasses.replace(merged[-1], haste=True)
        elif isinstance(effect, _TokenAttacksThisCombat):
            if not (merged and isinstance(merged[-1], CreateTokens)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], attacks_this_combat=True)
        elif isinstance(effect, _SacrificeThemLater):
            if not (merged and isinstance(merged[-1], TokensJoinAttack)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], sacrifice_at_end=True)
        elif isinstance(effect, (_TheyGainHaste, _ExileThemLater)):
            if not (merged and isinstance(merged[-1], AttackingTokens)):
                return None
            merged[-1] = dataclasses.replace(merged[-1], **({"haste": True} if isinstance(effect, _TheyGainHaste)
                                                             else {"exile_at_end": True}))
        else:
            merged.append(effect)
    return merged


def _attacking_tokens(m: re.Match) -> AttackingTokens | None:
    parsed = _token(m[1] + '."' if m[2] else m[1])
    return AttackingTokens(*parsed) if parsed else None


ALL_DAMAGE = 10 ** 9  # "prevent all damage": a shield too big to use up


def _prevent_next(amount: int, whom: str) -> PreventNext:
    whom = whom.lower()
    if whom == "any target":
        return PreventNext(amount, "any")
    if whom == "target creature":
        return PreventNext(amount, "creature")
    return PreventNext(amount) if whom == "you" else PreventNext(amount, on_source=True)


def _merge_prevention(effects: list) -> list | None:
    merged: list = []
    for effect in effects:
        if isinstance(effect, _TokenPerPrevented):
            if not (merged and isinstance(merged[-1], PreventCombatDamageToYou) and merged[-1].token is None):
                return None
            merged[-1] = PreventCombatDamageToYou(effect.token)
        else:
            merged.append(effect)
    return merged


def _token_per_prevented(m: re.Match) -> _TokenPerPrevented | None:
    parsed = _token(m[1] + '."' if m[2] else m[1])
    return _TokenPerPrevented(parsed[1]) if parsed and parsed[0] == 1 else None


def _merge_token_copies(effects: list) -> list | None:
    merged: list = []
    i = 0
    while i < len(effects):
        if isinstance(effects[i], _ChooseToken):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _OthersBecomeCopies)):
                return None
            merged.append(TokensBecomeCopies(effects[i + 1].until_end_of_turn))
            i += 2
            continue
        if isinstance(effects[i], _OthersBecomeCopies):
            return None
        merged.append(effects[i])
        i += 1
    return merged


def _merge_three_way(effects: list) -> list | None:
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, LookAtTop) and i + 1 < len(effects) and isinstance(effects[i + 1], _SplitTop):
            play = i + 2 < len(effects) and isinstance(effects[i + 2], _PlayTheExiledCard)
            merged.append(ThreeWaySplit(effect.count, play))
            i += 3 if play else 2
            continue
        if isinstance(effect, (_SplitTop, _PlayTheExiledCard)):
            return None
        merged.append(effect)
        i += 1
    return merged


_CLASS_LEVEL_LINE = re.compile(r"((?:\{[^}]+\})+): Level (\d)")


TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure",
                oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")


CLUE = Card(name="Clue", type_line="Token Artifact — Clue", oracle_text="{2}, Sacrifice this artifact: Draw a card.")


FOOD = Card(name="Food", type_line="Token Artifact — Food",
            oracle_text="{2}, {T}, Sacrifice this artifact: You gain 3 life.")


FISH = Card(name="Fish", type_line="Token Creature \u2014 Fish", colors=("U",), power="1", toughness="1")


SQUIRREL = Card(name="Squirrel", type_line="Token Creature \u2014 Squirrel", colors=("G",), power="1", toughness="1")


OCTOPUS = Card(name="Octopus", type_line="Token Creature \u2014 Octopus", colors=("U",), power="8", toughness="8")


HEARTWOOD = Card(name="Heartwood", type_line="Token Artifact — Heartwood", oracle_text="{T}: Add {R} or {G}.",
                 colors=("R", "G"))


_NAMED_TOKENS = {"treasure": TREASURE, "clue": CLUE, "food": FOOD, "heartwood": HEARTWOOD}


_COLOR_WORDS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}


_COLOR = r"(?:white|blue|black|red|green)"


_TOKEN_COUNT = _N.replace("|X)", "|X|twice X|half X up|half X down)")  # "Create twice X 1/1 ... tokens" (Pest Infestation)


_CREATURE_TOKEN = re.compile(
    rf"{_TOKEN_COUNT} (\d+|X)/(\d+|X) (colorless|{_COLOR}(?:(?:,? and |, ){_COLOR})*) ((?:[A-Z][\w'-]* )+)(artifact |enchantment )?"
    r"creature tokens?(?: named ([A-Z][\w'-]*))?"  # "named Cadet"
    r"(?: with (?:([a-z ,]+?)(?:,? and |, |$))?(?:\"(.+)\")?)?"  # keywords and/or a quoted ability
)


_NAMED_TOKEN = re.compile(rf"(?i:{_TOKEN_COUNT}) (Treasure|Clue|Food|Heartwood) tokens?")


def _attacker_token(spec: str) -> "AttackerCreatesAttackingToken | None":
    made = _token(spec)
    return AttackerCreatesAttackingToken(made[1]) if made is not None and made[0] == 1 else None


def _token(spec: str) -> tuple[Quantity, Card] | None:
    """Parse "a 1/1 white Soldier creature token with flying" or "two Treasure tokens"."""
    if ", then " in spec:
        return None  # a second step ("..., then populate") isn't part of the token; _clauses splits it off
    if m := _NAMED_TOKEN.fullmatch(spec):
        return _count(m[1]), _NAMED_TOKENS[m[2].lower()]
    m = _CREATURE_TOKEN.fullmatch(spec)
    if not m:
        return None
    count, power, toughness, colors, subtypes, artifact, named, keywords, quoted = m.groups()
    keyword_line = ""
    if keywords:
        words = [w.strip() for w in re.split(r",? and |, ", keywords) if w.strip()]
        keyword_line = ", ".join(words).capitalize()
    card = Card(
        name=named or subtypes.strip(),
        type_line=f"Token {artifact.capitalize() if artifact else ''}Creature — {subtypes.strip()}",
        oracle_text="\n".join(line for line in (keyword_line, quoted) if line),
        colors=tuple(_COLOR_WORDS[c] for c in re.findall(_COLOR, colors)),
        power=power,
        toughness=toughness,
    )
    if quoted and not _is_ability(card, quoted):
        return None  # a token ability we can't play: don't create a half-working token
    return _count(count), card


def _is_ability(card: Card, line: str) -> bool:
    """Whether `line` of `card`'s rules text is an ability we understand."""
    from .activated import activated_abilities  # the readers of abilities read effects with this module
    from .mana import is_mana_ability
    from .statics import static_abilities
    from .triggers import triggered_abilities

    known = {a.text for a in (*triggered_abilities(card), *activated_abilities(card), *static_abilities(card))}
    return line in known or is_mana_ability(line)


_ANIMATED = (r"(\d+)/(\d+)(?: ((?:white|blue|black|red|green)(?:(?:,? and |, )(?:white|blue|black|red|green))*))?"
             r"(?: ((?:[A-Z][\w'-]*)(?: [A-Z][\w'-]*)*))?( artifact)? creature(?: with (all creature types|"
             + _KEYWORDS_BARE + r"))?"
             r"(?: with \"During your turn, this creature has (" + _KEYWORDS_BARE + r")(?=\.\"))?")


def _animate(m: re.Match, target: str | None, offset: int = 0) -> Animate:
    power, toughness, colors, subtypes, artifact, keywords, on_your_turn = m.group(*range(offset + 1, offset + 8))
    keywords = None if keywords == "all creature types" else keywords
    return Animate(int(power), int(toughness), tuple(_COLOR_WORDS[c] for c in re.findall(_COLOR, colors or "")),
                   subtypes or "", artifact is not None, _keyword_list(keywords) if keywords else frozenset(),
                   target, on_source=target is None,
                   on_your_turn=_keyword_list(on_your_turn) if on_your_turn else frozenset())


def _merge_token_counters(effects: list) -> list | None:
    if any(isinstance(e, _PutCountersAndAttach) for e in effects):  # Fractal Harness
        merged_attach: list = []
        for effect in effects:
            if isinstance(effect, _PutCountersAndAttach):
                if not (merged_attach and isinstance(merged_attach[-1], CreateTokens) and merged_attach[-1].count == 1):
                    return None
                merged_attach[-1] = CreateTokenAttachSource(merged_attach[-1].token, (effect.count, effect.counter))
            else:
                merged_attach.append(effect)
        effects = merged_attach
    """"Create a 0/0 Fractal creature token. Put X +1/+1 counters on it." is one CreateTokens whose tokens come in with
    the counters (the second sentence means the new token, not the ability's source)."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, PutCountersOnSource) and merged and isinstance(merged[-1], CreateTokens) \
                and merged[-1].counters is None:
            merged[-1] = dataclasses.replace(merged[-1], counters=(effect.count, effect.counter))
        elif isinstance(effect, PutCountersOnSource) and len(merged) > 1 and isinstance(merged[-1], DefineX) \
                and isinstance(merged[-2], CreateTokens) and merged[-2].counters is None:
            # "..., where X is ...": X is worked out first, then the tokens come in with X counters (Deekah)
            merged[-2:] = [merged[-1], dataclasses.replace(merged[-2], counters=(effect.count, effect.counter))]
        else:
            merged.append(effect)
    return merged


def _merge_reveal_top(effects: list) -> list | None:
    """The three sentences of Thrasios's ability become one RevealTop; a step without the others isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, RevealTopStep):
            steps = effects[i:i + 3]
            if [getattr(e, "kind", None) for e in steps] != ["reveal", "land", "otherwise"]:
                return None
            merged.append(RevealTop(steps[0].scry, steps[1].tapped))
            i += 3
            continue
        merged.append(effect)
        i += 1
    return merged


def _merge_wipe_gift(effects: list) -> list | None:
    """"Destroy all creatures. For each creature destroyed this way, its controller creates a token." is one DestroyAll
    with `gives`; the second sentence alone isn't understood."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, GiveBack):
            if not (merged and isinstance(merged[-1], (DestroyAll, ExileAll, ExileX))):
                return None
            merged[-1] = dataclasses.replace(merged[-1], gives=effect)
        else:
            merged.append(effect)
    return merged


def _merge_animate(effects: list) -> list | None:
    """"... becomes a 2/2 creature. It's still a land." is one Animate; the second sentence alone isn't understood."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, StillALand):
            if not (merged and isinstance(merged[-1], Animate)):
                return None
            continue
        merged.append(effect)
    return merged


def _create_for_others(m: re.Match) -> Any:
    parsed = _token(m[2] + '."' if m[3] else m[2])
    if parsed is None:
        return None
    who = m[1].lower()
    return EachCreatesTokens(*parsed, who) if who.startswith("each") else TargetCreatesTokens(*parsed, who)


def _pump_x(sp: str, px: str, st: str, tx: str, target: str, keywords: str | None = None) -> PumpX:
    """+X/+X, -X/-X, +2X/+2X, ... as multiples of X (a plain +0/+0 never gets here: the ordinary pump reads it first)."""
    def multiple(sign: str, part: str) -> int:
        return 0 if part == "0" else (-1 if sign in ("-", "\u2212") else 1) * int(part.removesuffix("X") or 1)
    return PumpX(multiple(sp, px), multiple(st, tx), target, _keyword_list(keywords) if keywords else frozenset())


def _pump_each_x_from(who: str, sp: str, px: str, st: str, tx: str) -> PumpEachX:
    who = who.lower()
    inner = _pump_x(sp, px, st, tx, "creature")
    return PumpEachX(inner.power, inner.toughness, opponents=who.endswith("opponents control"), everyone=who == "all creatures")


def _pump_each_x(m: re.Match) -> PumpEachX:
    return _pump_each_x_from(m[1], m[2], m[3], m[4], m[5])


def _create(m: re.Match, follows: bool) -> Any:
    spec = m[1] + '."' if m[2] else m[1]  # a quoted ability's own full stop comes before its closing quote
    tapped = re.search(r"\btapped (?=[A-Z])", spec) is not None  # "X tapped Treasure tokens"
    parsed = _token(re.sub(r"\btapped (?=[A-Z])", "", spec, count=1))
    if parsed is None:
        return None
    if follows:
        return TargetControllerCreatesTokens(*parsed)
    return CreateTokens(*parsed, tapped=True) if tapped else CreateTokens(*parsed)


def _merge_target_copies(effects: list) -> list | None:
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, _ChooseAnyNumber):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _CopyEachWithHaste)):
                return None
            exile = i + 2 < len(effects) and isinstance(effects[i + 2], _ExileThoseTokens)
            merged.append(CopyTokensOfTargets(effect.target, True, exile))
            i += 3 if exile else 2
            continue
        if isinstance(effect, (_CopyEachWithHaste, _ExileThoseTokens)):
            return None
        merged.append(effect)
        i += 1
    return merged


_AMOUNTS = [
    (re.compile(r"(?:its|this creature's|CARDNAME's) power", re.I), lambda m: Amount("source_power")),
    (re.compile(r"the sacrificed creature's power", re.I), lambda m: Amount("sacrificed_power")),
    (re.compile(r"your devotion to (white|blue|black|red|green)", re.I), lambda m: Amount("devotion", _COLOR_LETTER[m[1].lower()])),
    (re.compile(r"the tapped creature's power", re.I), lambda m: Amount("tapped_power")),
    (re.compile(r"(?:the number of )?Auras? you controlled that was attached to it", re.I), lambda m: Amount("auras_on_subject")),
    (re.compile(r"(?:the number of )?Auras? you control that's attached to a creature", re.I),
     lambda m: Amount("auras_on_creatures")),
    (re.compile(r"the number of nontoken creatures you had enter the battlefield under your control this turn", re.I),
     lambda m: Amount("creatures_entered")),
    (re.compile(r"(?:the number of )?([+\-\u2212]1/[+\-\u2212]1|[a-z]+) counters? on (?:it|this creature|this artifact|this enchantment|CARDNAME)",
                re.I), lambda m: Amount("source_counters", _counter_name(m[1].lower()))),
    (re.compile(r"(?:the number of )?(?:(creature|land|artifact|enchantment|instant|sorcery|planeswalker) )?cards? in your graveyard",
                re.I), lambda m: Amount("graveyard", (m[1] or "card").lower())),
    (re.compile(r"(?:the number of )?creatures? on the battlefield", re.I), lambda m: Amount("on_battlefield", "creature")),
    (re.compile(r"(?:the number of )?((?-i:[A-Z][a-z]+)) on the battlefield", re.I), lambda m: Amount("on_battlefield", _singular(m[1]))),  # a creature type
    (re.compile(r"(?:the number of )?creatures? that died under your control this turn", re.I), lambda m: Amount("creatures_died")),
    (re.compile(r"(?:the number of )?creatures? that died this turn", re.I), lambda m: Amount("all_creatures_died")),  # Mahadi: whoever controlled them
    (re.compile(r"the amount of life you gained this turn", re.I), lambda m: Amount("life_gained")),
    (re.compile(r"the amount of life you lost this turn", re.I), lambda m: Amount("life_lost")),
    (re.compile(r"half your life total, rounded (down|up)", re.I), lambda m: Amount("half_life", m[1].lower())),
    (re.compile(r"(?:the number of )?spells? you've cast this turn", re.I), lambda m: Amount("spells_cast")),
    (re.compile(r"the greatest power among ((?:other )?(?:non-[A-Za-z]+ )?[A-Za-z]+s) you control", re.I),
     lambda m: Amount("greatest_power", m[1][:-1])),  # "creatures", "other creatures", "non-Human creatures", "Giants"
    (re.compile(r"the greatest mana value among instant and sorcery spells you've cast this turn", re.I),
     lambda m: Amount("greatest_mana_value_cast", "instant or sorcery spell")),
    (re.compile(r"opponents?", re.I), lambda m: Amount("opponents")),
    (re.compile(r"the amount of mana spent to cast that spell", re.I), lambda m: Amount("mana_spent")),
    (re.compile(r"that spell's mana value", re.I), lambda m: Amount("spell_mana_value")),
    (re.compile(r"the number of cards in your hand", re.I), lambda m: Amount("hand_size")),
    (re.compile(r"the number of cards in (?:that player's|their) hand minus (\d+)", re.I),
     lambda m: Amount("player_hand_minus", m[1])),
    (re.compile(r"the number of cards in (?:that player's|their) hand", re.I), lambda m: Amount("player_hand")),
    (re.compile(r"the number of colors that spell is", re.I), lambda m: Amount("spell_colors")),
    (re.compile(r"the number of cards in all graveyards with the same name as that spell", re.I),
     lambda m: Amount("graveyards_same_name")),
    (re.compile(r"(?:the number of )?([A-Za-z]+) you control", re.I), lambda m: Amount("you_control", _singular(m[1]))),
]


def _amount(text: str) -> Amount | None:
    for pattern, build in _AMOUNTS:
        if m := pattern.fullmatch(text):
            return build(m)
    return None


_CONTRACT_BODY = "it gets +2/+0 until end of turn if it's attacking one of your opponents. Otherwise, its controller loses 2 life."


_MASS_KINDS = {"battles": "battle", "creatures": "creature", "creature tokens": "creature", "artifacts": "artifact", "enchantments": "enchantment",
               "planeswalkers": "planeswalker", "lands": "land", "nonland permanents": "nonland permanent",
               "artifacts and enchantments": "artifact or enchantment",
               "creatures and planeswalkers": "creature or planeswalker"}


_MASS = (r"(battles|artifacts and enchantments|creatures and planeswalkers|nonland permanents|creatures|artifacts"
         r"|enchantments|planeswalkers|lands)( you don't control| you control| an opponent controls| your opponents control)?")


def _mass_kind(m: re.Match) -> str:
    return _MASS_KINDS[m[1].lower()] + (m[2] or "").replace(" your opponents control", " an opponent controls")


_SACRIFICE_KIND = (r"(attacking creature|tapped creature|untapped creature|nontoken creature|creature or planeswalker|creature|artifact or enchantment|nontoken artifact|food|treasure|clue|artifact"
                   r"|enchantment|land|nonland permanent|permanent)")


_FIGHTER = r"(creature(?: you control| you don't control| an opponent controls)?)"


_MASS_KEYWORDS = (r"(?:flying|reach|trample|haste|vigilance|menace|deathtouch|lifelink|first strike|double strike"
                  r"|defender|indestructible|hexproof)")


_RESTRICTION = rf"(with (?:power|toughness|mana value) \d+ or (?:greater|less)|with {_MASS_KEYWORDS}|without {_MASS_KEYWORDS})"


_COLOR_ADJECTIVE = r"(?:(non)?(white|blue|black|red|green|token|legendary|basic|tapped|untapped|attacking) )?"


_STAT_RESTRICTION = re.compile(r"with (power|toughness|mana value) (\d+) or (greater|less)")


_EXCEPT = (r"(?: except(?: for)? ((?:(?:artifact|enchantment|legendary|white|blue|black|red|green) )?"
           rf"(?:creatures|lands|permanents|tokens)(?: with {_MASS_KEYWORDS})?))?")


_THAT_ARE = r"(?: that (are (?:one or more colors|colorless|multicolored|monocolored)|aren't enchanted))?"


# The same, with an optional color adjective before and "with flying" etc. after (destroy and exile only).
_MASS_NOUN = (r"(battles|artifacts and enchantments|creatures and planeswalkers|nonland permanents|creature tokens|creatures|artifacts"
              r"|enchantments|planeswalkers|lands)")


_MASS_FILTERED = rf"{_COLOR_ADJECTIVE}{_MASS_NOUN}(?: {_RESTRICTION})?( you don't control| you control| an opponent controls| your opponents control)?{_EXCEPT}{_THAT_ARE}"


def _mass_effect(cls: type, m: re.Match) -> Any:
    kind = _MASS_KINDS[m[3].lower()] + (m[5] or "").replace(" your opponents control", " an opponent controls")
    return cls(kind, _mass_filter(m[1], m[2], m[4], tokens=m[3].lower() == "creature tokens", spared=m[6], colors_are=m[7]))


_TRAITS = {"token": "token", "legendary": "legendary", "basic": "basic", "tapped": "tapped", "untapped": "tapped", "attacking": "attacking"}


def _mass_filter(non: str | None, color: str | None, restriction: str | None, tokens: bool = False,
                 spared: str | None = None, colors_are: str | None = None) -> MassFilter | None:
    """The filter for an optional adjective ("nonblack", "nontoken", "legendary", "tapped"), an optional "with ..." /
    "without ..." phrase, "creature tokens", and an optional "except for ..." (what is left alone)."""
    fields: dict[str, Any] = {}
    if color and color.lower() in _COLOR_WORDS:
        fields.update(color=_COLOR_WORDS[color.lower()], other_color=bool(non))
    elif color:
        wanted = not non and color.lower() != "untapped"
        fields[_TRAITS[color.lower()]] = wanted
    if tokens:
        fields["token"] = True
    if restriction:
        if m := _STAT_RESTRICTION.fullmatch(restriction.lower()):
            fields.update(stat=m[1].replace(" ", "_"), **{"at_least" if m[3] == "greater" else "at_most": int(m[2])})
        else:
            fields.update(keyword=restriction.lower().split(" ", 1)[1], keyword_wanted=restriction.lower().startswith("with "))
    if spared:
        fields["exclude"] = _spared_filter(spared.lower())
    if colors_are == "aren't enchanted":
        fields["enchanted"] = False
    elif colors_are:
        fields["colors_are"] = colors_are.lower().removeprefix("are ")
    return MassFilter(**fields) if fields else None


def _spared_filter(text: str) -> MassFilter:
    """What an "except for ..." leaves alone: "artifact creatures", "legendary creatures", "white creatures", "tokens",
    "creatures with flying"."""
    fields: dict[str, Any] = {}
    head, _, keyword = text.partition(" with ")
    if keyword:
        fields.update(keyword=keyword, keyword_wanted=True)
    first = head.split(" ")[0]
    if first in _COLOR_WORDS:
        fields.update(color=_COLOR_WORDS[first])
    elif first == "legendary":
        fields["legendary"] = True
    elif first in ("artifact", "enchantment"):
        fields["has_type"] = first.capitalize()
    elif head == "tokens":
        fields["token"] = True
    return MassFilter(**fields)


_SACRIFICE_PLURAL = r"(creatures|artifacts or enchantments|artifacts|enchantments|lands|nonland permanents|permanents)"


_PLURAL_SACRIFICE = {"creatures": "creature", "artifacts or enchantments": "artifact or enchantment",
                     "artifacts": "artifact", "enchantments": "enchantment", "lands": "land",
                     "nonland permanents": "nonland permanent", "permanents": "permanent"}


def _gift(m: _GiftMatch, **fields: Any) -> Any:
    parsed = _token(m.spec + '."' if m.quote else m.spec)
    return GiveBack(*parsed, **fields) if parsed else None


def _damage_each(m: re.Match) -> DamageEach | None:
    creatures = players = None
    if m[3] and not m[2].lower().startswith("creature"):
        return None  # "each opponent with flying" isn't a thing
    for part in (m[2].lower(), (m[4] or "").lower()):
        if part == "creature":
            creatures = "all"
        elif part in ("creature you don't control", "creature your opponents control"):
            creatures = "opponents"
        elif part == "creature and planeswalker your opponents control":
            creatures = "opponents and planeswalkers"
        elif part:
            players = "all" if part == "player" else "opponents"
    return DamageEach(_count(m[1]), creatures, players, _mass_filter(None, None, m[3]))


def _if_you_do(m: re.Match) -> Any:
    inner = _parse([m[1][:1].upper() + m[1][1:] + "."])
    return _IfYouDo(inner[0]) if inner and len(inner) == 1 and isinstance(inner[0], (BecomePrepared, SearchForLands)) else None


def _then_if(m: re.Match) -> Any:
    condition = _condition(m[1])
    inner = _parse([m[2][:1].upper() + m[2][1:] + "."]) if condition else None
    if condition is None or not inner or len(inner) != 1 or target_kind(inner[0]):
        return None
    return Conditional(condition, inner[0])


def _is_known_ability(text: str) -> bool:
    """Whether a quoted ability is one we understand (the same test a token's own quoted ability has to pass)."""
    return _token(f'a 1/1 colorless Test creature token with "{text}"') is not None


def _merge_conditional(effects: list) -> list | None:
    """The sentences that qualify the effect before them: a bigger draw, an untap, a token for an exiled creature card (the table above),
    and the two that are not just a change to the effect before them."""
    merged: list = []
    for effect in effects:
        if (done := _CONDITIONAL.step(merged, effect)) is False:
            return None
        if done:
            continue
        if isinstance(effect, Fight) and effect.follows:  # "It fights ...": the creature just pumped (or given counters), or the source
            if not merged:
                if effect.then:
                    return None
                merged.append(FightSourceFirst())
            elif not isinstance(merged[-1], (Pump, PumpX, DoubleStats, PutCounters)):
                return None
            merged.append(effect)
        elif isinstance(effect, _ItGains):
            if merged and isinstance(merged[-1], PutCounters) and not merged[-1].grant:
                merged[-1] = dataclasses.replace(merged[-1], grant=effect.keywords)
            else:
                merged.append(PumpSource(Modifier(keywords=effect.keywords)))
        else:
            merged.append(effect)
    return merged


def _if_exiled(m: re.Match) -> Any:
    rest = _parse([m[2][:1].upper() + m[2][1:] + m[3]])
    return _IfExiledThen(m[1], rest[0]) if rest and len(rest) == 1 and not target_kind(rest[0]) else None


_KICKED_INSTEAD = [
    (re.compile(rf"if this spell was kicked, {_SELF} deals {_N} damage instead\.", re.I), "amount"),
    (re.compile(rf"if this spell was kicked, create {_N} of those tokens instead\.", re.I), "count"),
    (re.compile(rf"if this spell was kicked, draw {_N} cards instead\.", re.I), "count"),
    (re.compile(rf"if this spell was kicked, put {_N} of those cards into your hand instead\.", re.I), "take"),  # Consult the Star Charts
]


def _kicked_replaces(rest: str) -> KickedReplaces | None:
    effects = _parse(_split_sentences(rest[:1].upper() + rest[1:]))
    return KickedReplaces(tuple(effects)) if effects else None


def _not_kicked(rest: str) -> IfNotKicked | None:
    effects = _parse([rest[:1].upper() + rest[1:]])
    return IfNotKicked(effects[0]) if effects and len(effects) == 1 else None


def _kicked(m: re.Match) -> IfKicked | None:
    kicker, rest = m[1] or "", m[2]
    sentence = rest[:1].upper() + rest[1:]
    effects = _parse([sentence])
    if not effects and isinstance(also := _template(sentence), _ThatAlsoGains):  # joins the pump before it once kicked
        return IfKicked(also, kicker)
    return IfKicked(effects[0], kicker) if effects else None


def kicked_effects(effects: list | None, kicked: int, kickers: tuple[str, ...] = ()) -> list | None:
    """A spell's effects once it's known whether it was kicked: "If this spell was kicked, ..." effects
    become plain effects, or are dropped. This happens before targets are chosen, so kicked effects can target."""
    if effects is None:
        return None
    result = []
    for effect in effects:
        if isinstance(effect, KickedReplaces):
            if kicked:
                result[-1:] = list(effect.effects)
        elif isinstance(effect, IfNotKicked):
            if not kicked:
                result.append(effect.effect)
        elif isinstance(effect, KickedInstead):
            if kicked:
                result[-1] = replace(result[-1], **{effect.field: effect.value})
        elif isinstance(effect, IfKicked):
            if kicked and (not effect.kicker or effect.kicker in kickers):
                if isinstance(effect.effect, _ThatAlsoGains):
                    result[-1] = replace(result[-1], modifier=replace(result[-1].modifier, keywords=result[-1].modifier.keywords | effect.effect.keywords))
                else:
                    result.append(effect.effect)
        else:
            result.append(effect)
    return result


_PERMANENT_KIND = (r"((?:forest|island|swamp|mountain|plains|attacking or blocking creature|artifact, enchantment, or nonbasic land|artifact, creature, enchantment, or planeswalker"
                   r"|monocolored permanent|(?:white|blue|black|red|green) permanent|creature token|nontoken creature|attacking creature|tapped creature|untapped creature"
                   r"|non(?:white|blue|black|red|green|artifact|legendary) creature|noncreature artifact or noncreature enchantment"
                   r"|noncreature, nonland permanent|nonland, nontoken permanent|non-(?-i:[A-Z][a-z]+) creature|artifact, enchantment, or planeswalker|artifact, creature, or planeswalker|creature|artifact"
                   r"|enchantment|planeswalker|nonland permanent|permanent|nonbasic land|land|artifact or enchantment|artifact or creature"
                   r"|creature or planeswalker|creature or enchantment|(?-i:[A-Z][a-z]+) creature|(?-i:[A-Z][a-z]+)(?= you control))(?: an opponent controls| you don't control| you control| you own| that player controls)?"
                   r"(?: with mana value (?:\d+ or (?:less|greater)|X))?)")


_COPY_TOKEN = re.compile(
    r"create (?:a token that's a copy|(?P<count>two|three|four|five|X) tokens that are copies) of "
    rf"(?:(?P<another>another )?target (?P<kind>{_PERMANENT_KIND})"
    r"|target (?P<grave>creature|artifact) card in your graveyard"
    r"|(?P<subject>it|that (?:creature|permanent|artifact|enchantment|card|token))"
    r"|(?P<host>equipped|enchanted) (?:creature|artifact|permanent)"
    r"|(?P<self>CARDNAME|this (?:creature|artifact|enchantment|land|planeswalker|permanent|Aura|Equipment|Class|Vehicle|Saga|Room|token)))"
    r"(?:, except (?P<changes>.+))?\.(?P<quote>\"?)", re.I)  # (a quoted ability's own full stop comes before its closing quote)


def _copy_token(m: re.Match) -> Any:
    """ "Create a token that's a copy of <what>(, except <changes>)." for every <what> the engine can find: its riders ("It gains
    haste.", "Sacrifice it at the beginning of the next end step.") are folded in by the Follow rows of _CONDITIONAL."""
    changes = _copy_changes(m["changes"] + '."' * bool(m["quote"])) if m["changes"] else None
    if m["changes"] and changes is None:
        return None
    count = _count(m["count"]) if m["count"] else 1
    if m["kind"]:
        return CopyToken(m["kind"].lower(), count, another=bool(m["another"]), changes=changes)
    if m["grave"]:
        return CopyToken(f"graveyard:{m['grave'].lower()}:yours", count, changes=changes)
    if m["subject"]:
        return CopySubjectToken(changes, count)
    if m["host"]:
        return CopyHostToken(changes, count)
    return CopySelfToken(changes=changes, count=count)


# "up to two target creatures": the plural kinds, and the singular they stand for
_PLURAL_KINDS = {"creatures": "creature", "artifacts": "artifact", "enchantments": "enchantment",
                 "planeswalkers": "planeswalker", "permanents": "permanent", "nonland permanents": "nonland permanent",
                 "creature tokens": "creature token", "lands": "land", "artifacts or enchantments": "artifact or enchantment",
                 "artifacts and/or creatures": "artifact or creature",
                 "artifacts and/or enchantments": "artifact or enchantment"}


_PLURAL_KIND = (r"(creature tokens|nonland permanents|artifacts or enchantments|artifacts and/or enchantments|artifacts and/or creatures|creatures|artifacts|enchantments|planeswalkers"
                r"|permanents|lands)( an opponent controls| you don't control| you control| your opponents control)?")


def _suffix(controller: str | None) -> str:
    """The controller phrase after a plural kind, in the singular form targets are written in."""
    return (controller or "").replace("your opponents control", "an opponent controls")


_UP_TO = r"up to (two|three|four)"


def _up_to(cls: type, m: re.Match, **fixed: Any) -> list:
    """"... up to two target creatures ..." is two effects with one optional, distinct target each."""
    kind = _PLURAL_KINDS[m[2].lower()] + _suffix(m[3])
    return [cls(kind, optional_target=True, distinct=n > 0, **fixed) for n in range(_number(m[1]))]


_DAMAGE_KIND = (r"(any target|target attacking or blocking creature|target creature an opponent controls|target creature|target player|target opponent|target creature or planeswalker"
                r"|target player or planeswalker)")


_RETURN_UP_TO_POWER = re.compile(r"return target nonland permanent card with mana value X or less from your graveyard to the "
                                 r"battlefield, where X is (?:this creature's|CARDNAME's|its) power\.", re.I)


_RETURN_UP_TO_DAMAGE = re.compile(r"return target creature card with mana value X or less from your graveyard to the battlefield, "
                                  r"where X is the amount of damage (?:this creature|CARDNAME) dealt to that player\.", re.I)


def _emblem(text: str) -> GetEmblem | None:
    """An emblem whose every line the engine reads as a static or triggered ability (CR 114: it is never a permanent, so an
    activated ability on it would have no battlefield source here and leaves the line unread)."""
    from ..report import unsupported_lines  # the report reads effects; a local import keeps the module graph one way
    from .activated import activated_abilities

    probe = Card(name="Emblem", type_line="Emblem", oracle_text=text)
    if unsupported_lines(probe) or activated_abilities(probe):
        return None
    return GetEmblem(text)

_DESTINATIONS = {"into your hand": "hand", "onto the battlefield": "battlefield", "into your graveyard": "graveyard"}

_MILL_KIND = r"an? [a-z ]+? card(?: with mana value \d+(?: or less| or greater)?)?"  # "a creature card with mana value 2 or less"


_TEMPLATES: list[tuple[re.Pattern, Callable[[re.Match], Any]]] = [
    (re.compile(r'you get an emblem with "(.+)"\.?', re.I), lambda m: _emblem(m[1])),  # Elspeth, Sun's Champion
    *[(pattern, lambda m, field=field: KickedInstead(field, _count(m[1]))) for pattern, field in _KICKED_INSTEAD],
    (re.compile(r"if this spell was kicked, instead (.+)", re.I), lambda m: _kicked_replaces(m[1])),
    (re.compile(r"if this spell was kicked, (.+?) instead\.", re.I), lambda m: _KickedInsteadTail(m[1])),
    (re.compile(r"if this spell wasn't kicked, (.+)", re.I), lambda m: _not_kicked(m[1])),
    (re.compile(rf"if this spell was kicked(?: with its ({_MANA_SYMBOLS}) kicker)?, (.+)", re.I), _kicked),
    (re.compile(rf"draw {_N} cards?\.", re.I), lambda m: Draw(_count(m[1]))),
    (re.compile(r"draw an additional card\.", re.I), lambda m: Draw(1)),
    (re.compile(rf"(?:you )?gain {_N} life\.", re.I), lambda m: GainLife(_count(m[1]))),
    (re.compile(r"exile a nonartifact, nonland card from your hand\.", re.I), lambda m: ImprintFromHand()),
    (re.compile(rf"whenever {_SELF} connives|{_SELF} connives\.", re.I), lambda m: Connive()),
    (re.compile(r"exile the top card of each player's library, then you may cast any number of spells from among those cards without "
                r"paying their mana costs\.", re.I), lambda m: ExileTopOfEachCastFree()),
    (re.compile(r"create a food token or a treasure token\.", re.I), lambda m: CreateOneOfTokens((FOOD, TREASURE))),
    (re.compile(r"create a (\d+)/(\d+) (green|white|blue|black|red) ([A-Z][a-z]+) creature token\. If you control (six|five|seven) or more lands, "
                r"create a token that's a copy of this creature instead\.", re.I),
     lambda m: TokenOrSelfCopy(Card(name=m[4].title(), type_line=f"Token Creature \u2014 {m[4].title()}", power=m[1], toughness=m[2],
                                    colors=(_COLOR_LETTER[m[3].lower()],)), {"five": 5, "six": 6, "seven": 7}[m[5].lower()])),
    (re.compile(r"(?:then )?amass (?:([A-Z][a-z]+) )?(\d+)\.", re.I), lambda m: Amass(int(m[2]), (m[1] or "").rstrip("s"))),
    (re.compile(r"each player sacrifices an? (creature or planeswalker|nontoken creature) of their choice\. Each player who can't discards a "
                r"card\.", re.I), lambda m: EachSacrificesOrDiscards(m[1].lower())),
    (re.compile(r"choose a color\. add an amount of mana of that color equal to your devotion to that color\.", re.I),
     lambda m: AddDevotionMana()),
    (re.compile(r"add one mana of any color\.", re.I), lambda m: AddMana((frozenset("WUBRG"),))),  # Phyrexian Altar, Springleaf Drum
    # the engine keeps one option set per mana, so the three of Lion's Eye Diamond can be spent as different colors
    (re.compile(r"add (two|three|four|five) mana of any one color\.", re.I), lambda m: AddMana((frozenset("WUBRG"),) * _ANY_N[m[1].lower()])),
    (re.compile(r"add (two|three|four|five) mana in any combination of colors\.", re.I),  # Realm-Scorcher Hellkite: each mana its own color
     lambda m: AddMana((frozenset("WUBRG"),) * _ANY_N[m[1].lower()])),
    (re.compile(rf"each opponent loses {_N} life\.", re.I), lambda m: OpponentsLoseLife(_count(m[1]))),

    (re.compile(r"it deals that much damage to any target that isn't an? ([A-Z][a-z]+)\.", re.I),  # Wrathful Raptors
     lambda m: DamageFromSubject("X", f"any non-{m[1].lower()}")),
    (re.compile(rf"{_SELF} deals {_N} damage to you\.", re.I), lambda m: DamageToYou(_count(m[1]))),
    (re.compile(rf"{_SELF} deals {_N} damage to {_DAMAGE_KIND}\.", re.I),
     lambda m: Damage(_count(m[1]), "any" if m[2].lower() == "any target" else m[2].lower().removeprefix("target "))),
    (re.compile(rf"{_SELF} deals {_N} damage to up to one target creature\.", re.I),  # Season of the Bold
     lambda m: Damage(_count(m[1]), "creature", optional_target=True)),
    (re.compile(rf"{_SELF} deals {_N} damage to each of one or two targets\.", re.I),  # Prismari Charm
     lambda m: [Damage(_count(m[1]), "any"), Damage(_count(m[1]), "any", optional_target=True, distinct=True)]),
    (re.compile(rf"{_SELF} deals {_N} damage to each of up to two target creatures and/or planeswalkers\.", re.I),  # Volcanic Salvo
     lambda m: [Damage(_count(m[1]), "creature or planeswalker", optional_target=True),
                Damage(_count(m[1]), "creature or planeswalker", optional_target=True, distinct=True)]),
    (re.compile(rf"{_SELF} deals (\d+) damage divided as you choose among any number of targets\.", re.I),
     lambda m: [Damage(1, "any", optional_target=n > 0) for n in range(int(m[1]))]),  # a point at a time
    (re.compile(rf"tap (two|three) target {_PLURAL_KIND}\.", re.I),
     lambda m: [Tap(_PLURAL_KINDS[m[2].lower()] + _suffix(m[3]), distinct=n > 0) for n in range(_number(m[1]))]),
    (re.compile(rf"destroy (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Destroy(m[2].lower(), bool(m[1]))),
    (re.compile(rf"destroy each {_PERMANENT_KIND}\.", re.I), lambda m: DestroyAll(m[1].lower())),
    (re.compile(r"destroy each artifact, creature, and enchantment with mana value X or less\.", re.I),
     lambda m: DestroyAll("artifact or creature or enchantment", MassFilter(stat="mana_value", at_most="X"))),
    (re.compile(rf"exile each {_PERMANENT_KIND}\.", re.I), lambda m: ExileAll(m[1].lower())),
    (re.compile(rf"return each {_PERMANENT_KIND} to its owner's hand\.", re.I), lambda m: ReturnAllToHand(m[1].lower())),
    (re.compile(rf"destroy {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Destroy, m)),
    (re.compile(rf"destroy (two|three) target {_PLURAL_KIND}\.", re.I),
     lambda m: [Destroy(_PLURAL_KINDS[m[2].lower()] + _suffix(m[3]), distinct=n > 0) for n in range(_number(m[1]))]),
    (re.compile(rf"destroy up to one target {_PERMANENT_KIND}\.", re.I),
     lambda m: Destroy(m[1].lower(), optional_target=True)),
    (re.compile(r"counter target spell if it's (white|blue|black|red|green)\.", re.I),
     lambda m: Counter("spell", if_color=_COLOR_LETTER[m[1].lower()])),
    (re.compile(r"destroy target permanent if it's (white|blue|black|red|green)\.", re.I),
     lambda m: Destroy("permanent", if_color=_COLOR_LETTER[m[1].lower()])),
    (re.compile(r"counter target ((?:noncreature|creature|instant or sorcery|enchantment, instant, or sorcery|artifact or enchantment|artifact|enchantment|white|blue|black|red|green) )?spell"
                rf"(?: with mana value (\d+))?( unless its controller pays ((?:\{{[^}}]+\}})+))?\.", re.I),
     lambda m: Counter(f"{m[1].lower() if m[1] else ''}spell" + (f" with mana value {m[2]}" if m[2] else ""), unless=m[4] or "")),
    (re.compile(r"change the target of target (spell|spell or ability|activated ability) with a single target"
                rf"( unless that spell's controller pays ((?:\{{[^}}]+\}})+))?\.", re.I),
     lambda m: ChangeTarget(f"{m[1].lower()} with a single target", unless=m[3] or "")),
    (re.compile(r"(you may )?change the target of target (instant or sorcery spell) with a single target to (this creature)\.", re.I),
     lambda m: ChangeTarget(f"{m[2].lower()} with a single target", to="this", optional=bool(m[1]))),  # Hydroelectric Specimen
    (re.compile(r"change the target of target (spell or ability|spell) that targets only (a player|a single creature|this creature)( to this creature)?\.", re.I),
     lambda m: ChangeTarget(f"{m[1].lower()} that targets only {m[2].lower()}",
                            to="this" if m[3] else "")),  # Rebound, Muck Drubb, Silver Wyvern, Torchling
    (re.compile(r"the new target must be an? (player|creature)\.", re.I), lambda m: NewTargetMustBe(m[1].lower())),
    (re.compile(r"you may change the targets of target (instant or sorcery spell)\.", re.I),
     lambda m: ChangeTarget(m[1].lower(), every=True)),  # Goblin Flectomancer
    (re.compile(r"change a target of target spell or ability to (this creature)\.", re.I),
     lambda m: ChangeTarget("spell or ability", to="this", lone=False)),  # Spellskite
    (re.compile(r"you may choose new targets for target spell or ability\.", re.I), lambda m: ChangeTarget("spell or ability", every=True)),
    (re.compile(r"return target (spell or nonland permanent an opponent controls) to its owner's hand\.", re.I),
     lambda m: ReturnToHand(m[1].lower())),  # Sink into Stupor
    (re.compile(r"return target spell( you don't control)? to its owner's hand\.", re.I),
     lambda m: ReturnSpellToHand("spell you don't control" if m[1] else "spell")),
    (re.compile(r"its controller gains (\d+) life\.", re.I), lambda m: TargetControllerGainsLife(int(m[1]))),
    (re.compile(r"you may play an additional land this turn\.", re.I), lambda m: ExtraLandDrop()),
    (re.compile(r"your opponents can't cast (noncreature )?spells this turn\.", re.I), lambda m: OpponentsCantCast("noncreature" if m[1] else "")),
    (re.compile(r"search your library for a card, put that card into your graveyard, then shuffle\.", re.I),
     lambda m: SearchLibrary("card", "graveyard", False)),
    (re.compile(r"each player draws a card, then discards a card\.", re.I), lambda m: EachDrawsThenDiscards()),
    (re.compile(rf"tap (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Tap(m[2].lower(), bool(m[1]))),
    (re.compile(rf"tap {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Tap, m)),
    (re.compile(r"its controller may draw a card if its power is greater than each other creature's power\.", re.I),
     lambda m: GreatestPowerMayDraw()),  # Selvala, Heart of the Wilds
    (re.compile(rf"its controller may draw up to {_N_FIXED} cards at the beginning of the next turn's upkeep\.", re.I),
     lambda m: DelayedDraw(_number(m[1]), True)),
    (re.compile(rf"(?:you )?draw {_N_FIXED} cards? at the beginning of the next turn's upkeep\.", re.I),  # Portent: "Draw a card ..."
     lambda m: DelayedDraw(_number(m[1]), False)),
    (re.compile(r"if that (?:creature|permanent|creature or planeswalker) would die this turn, exile it instead\.", re.I),
     lambda m: ExileTargetIfDies()),
    (re.compile(r"if a creature dealt damage this way would die this turn, exile it instead\.", re.I),
     lambda m: ExileDamagedIfDie()),
    (re.compile(r"exile enchanted creature\.", re.I), lambda m: ExileEnchanted()),
    (re.compile(r"that token gains haste until end of turn\.", re.I), lambda m: _TokenGainsHaste()),
    (re.compile(r"(?:it|that token|they|those tokens) gains? haste\.", re.I), lambda m: _TokenHasHaste()),
    (re.compile(r"sacrifice (?:it|this creature)\.", re.I), lambda m: SacrificeSelf()),  # Phantasmal Image's "... becomes the target of a spell or ability, sacrifice it."
    (re.compile(r"mill a card, then exile a card from your graveyard at random\. you may play the exiled card this turn\.", re.I),
     lambda m: MillThenExileRandomPlay()),
    (re.compile(r"exile (?:that card|one of them) from your graveyard\.(?: if you do, you may (?:play|cast) (?:that card|it) this turn\.)?", re.I),
     lambda m: ExileDiscarded(play="you may" in m[0].lower())),
    (re.compile(r"you may have (?:this creature|CARDNAME) become a copy of an artifact or creature card from among those cards "
                r"until end of turn\.", re.I), lambda m: MayCopyLeftCard()),
    (re.compile(r"create Primo, the Indivisible, a legendary 0/0 green and blue Fractal creature token, then put that many "
                r"\+1/\+1 counters on it\.", re.I),
     lambda m: [DefineX(Amount("you_control", "land")),  # "that many": the lands you control
                CreateTokens(1, Card(name="Primo, the Indivisible", type_line="Legendary Token Creature — Fractal",
                                     colors=("G", "U"), power="0", toughness="0"), counters=("X", "+1/+1"))]),
    (re.compile(rf"(?:you )?put {_N} \+1/\+1 counters? on a creature you control\.", re.I),
     lambda m: PutCountersOnChosenCreature(_count(m[1]), "+1/+1")),
    (re.compile(rf"look at the top {_N_FIXED} cards of your library\. you may put an Aura or Equipment card from among them onto the "
                r"battlefield\. If an Equipment is put onto the battlefield this way, you may attach it to a creature you control\. "
                r"Put the rest of those cards on the bottom of your library in a random order\.", re.I),
     lambda m: LookPutAttachment(_number(m[1]))),
    (re.compile(rf"exile the top {_N_FIXED} cards of your library\. You may cast an Aura spell from among them without paying its mana "
                r"cost\. Then put the rest on the bottom of your library in a random order\.", re.I),
     lambda m: ExileTopCastAura(_number(m[1]))),
    (re.compile(rf"look at the top {_N_FIXED} cards of your library\. Put any number of nonland permanent cards with total mana value "
                r"(\d+) or less from among them onto the battlefield\. Put the rest on the bottom of your library in a random order\.",
                re.I), lambda m: LookPutPermanents(_number(m[1]), int(m[2]))),
    (re.compile(rf"put {_N} ([+\-\u2212]1/[+\-\u2212]1) counters? on each permanent you control that's a creature or Vehicle\.", re.I),
     lambda m: PutCountersOnEach(_count(m[1]), _counter_name(m[2]), or_vehicle=True)),
    (re.compile(rf"each player exiles cards from the top of their library until they exile a nonland card\. An opponent chooses a "
                rf"nonland card exiled this way\. You may cast up to {_N_FIXED} spells from among the other cards exiled this way without "
                r"paying their mana costs\.", re.I), lambda m: ExileUntilNonlandCast(_number(m[1]))),
    (re.compile(r"reveal the top X cards of your library\. Put all land cards from among them onto the battlefield tapped and the rest "
                r"on the bottom of your library in a random order\.", re.I), lambda m: RevealLands("X")),
    (re.compile(r"reveal cards from the top of your library until you reveal X land cards\. Put those land cards onto the "
                r"battlefield tapped and the rest on the bottom of your library in a random order\.", re.I),
     lambda m: RevealLands("X", until_lands=True)),
    (re.compile(r"if (there are .+), untap those lands\.", re.I), lambda m: _UntapThoseLands(c) if (c := _condition(m[1])) else None),
    (re.compile(r"reveal cards from the top of your library until you reveal an Aura card\. You may put that card onto the "
                r"battlefield\. If you don't, put it into your hand\. Put the rest on the bottom of your library in a random order\.",
                re.I), lambda m: RevealUntilAura()),
    (re.compile(r"tap up to one target creature and goad it\.", re.I), lambda m: TapAndGoad()),
    (re.compile(r"attach (?:this Aura|CARDNAME) to it\.", re.I), lambda m: AttachThisToSubject()),
    (re.compile(r"if that enchantment is an Aura, you may attach it to the token\.", re.I), lambda m: _AttachItToToken()),
    (re.compile(rf"put {_N} ([+\-\u2212]1/[+\-\u2212]1) counters? on it and attach (?:this Equipment|CARDNAME) to it\.", re.I),
     lambda m: _PutCountersAndAttach(_count(m[1]), _counter_name(m[2]))),
    (re.compile(r"when you do, return up to one target Aura or Equipment card from your graveyard to the battlefield attached to "
                r"that token\.", re.I), lambda m: _RecallAttachment()),
    (re.compile(r"the token created this way gains haste\.", re.I), lambda m: _PopulatedTokenRider(haste=True)),
    (re.compile(r"sacrifice (?:it|that token) at the beginning of the next end step\.", re.I), lambda m: _PopulatedTokenRider(sacrifice=True)),
    (re.compile(r'(?:it has|they have) "(.+)"', re.I), lambda m: _ItHas(m[1]) if _is_known_ability(m[1]) else None),
    (re.compile(r"when you (?:next cast an|cast your next) instant or sorcery spell this turn, copy that spell\. You may choose new targets "
                r"for the copy\.", re.I), lambda m: CopyNextSpell()),
    (re.compile(r"when you next cast an instant or sorcery spell this turn, copy it for each time you've cast your commander from "
                r"the command zone this game\. You may choose new targets for the copies\.", re.I),
     lambda m: CopyNextSpell(per_commander_cast=True)),
    (re.compile(rf"(?:then )?put an? {_CARD_TYPE} from among them onto the battlefield\.", re.I),
     lambda m: _PutFromAmongThem(_card_kind(m[1]))),
    (re.compile(rf"(?:those creatures|they(?! gain haste until end of turn\.)) gain {_KEYWORDS} until end of turn\.", re.I), lambda m: _TheyGain(_keyword_list(m[1]))),
    (re.compile(rf"it gains {_KEYWORDS} until end of turn\.", re.I), lambda m: _ItGains(_keyword_list(m[1]))),
    (re.compile(rf"that creature also gains {_KEYWORDS} until end of turn\.", re.I), lambda m: _ThatAlsoGains(_keyword_list(m[1]))),
    (re.compile(r"you may cast spells this turn as though they had flash\.", re.I), lambda m: GrantFlash()),
    (re.compile(rf"if (.+), draw {_N_FIXED} cards instead\.", re.I),
     lambda m: _InsteadDraw(c, _number(m[2])) if (c := _condition(m[1])) else None),
    (re.compile(r"(?:Threshold \u2014 )?add ((?:\{[WUBRGC]\})+) instead if (there are seven or more cards in your graveyard)\.", re.I),
     lambda m: _InsteadMana(c, tuple(frozenset(s) for s in re.findall(r"[WUBRGC]", m[1].upper()))) if (c := _condition(m[2])) else None),
    (re.compile(r"add ((?:\{[WUBRGC]\})+), then add (\{[WUBRGC]\}) for each card named CARDNAME in each graveyard\.", re.I),
     lambda m: AddMana(tuple(frozenset(s) for s in re.findall(r"[WUBRGC]", m[1].upper())), per_named=frozenset(re.findall(r"[WUBRGC]", m[2].upper())))),
    (re.compile(r"look at target (player|opponent)'s hand\.", re.I), lambda m: LookAtHand(m[1].lower())),
    (re.compile(r"put your commander into your hand from the command zone\.", re.I), lambda m: CommanderToHand()),
    (re.compile(r"put (?:CARDNAME|this card) onto the battlefield from the command zone\.", re.I), lambda m: PutThisFromCommandZone()),
    (re.compile(r"exile (?:it|that token) at the beginning of the next end step\.", re.I), lambda m: _ExileTokenAtEnd()),
    (re.compile(rf"if (.+), create {_N} of those tokens instead\.", re.I),
     lambda m: _InsteadTokens(c, _count(m[2])) if (c := _condition(m[1])) else None),
    (re.compile(r"then if (.+), untap that land\.", re.I), lambda m: _UntapThatLand(c) if (c := _condition(m[1])) else None),
    (re.compile(r"then if (.+?), ((?!untap that land).+)\.", re.I), _then_if),
    (re.compile(r"if (this spell was foretold), (.+)\.", re.I), _then_if),
    (re.compile(r"if (X is \d+ or more), (?!double the number)(.+)\.", re.I), _then_if),
    (re.compile(rf"if X is {_N} or more, double the number of ([+\-\u2212]1/[+\-\u2212]1) counters on any number of other target "
                r"creatures\.", re.I), lambda m: DoubleCountersOnTargets(_counter_name(m[2]), "creature", int(m[1]))),
    (re.compile(r"destroy up to one target (artifact or enchantment) with mana value X or less\.", re.I),
     lambda m: Destroy(f"{m[1].lower()} with mana value x or less", optional_target=True)),
    (re.compile(rf"exile {_N_FIXED} cards from your graveyard\.", re.I), lambda m: ExileOwnGraveyard(_number(m[1]))),
    (re.compile(r"if you do, (.+)\.", re.I), _if_you_do),
    (re.compile(r'if an? (creature) card is exiled this way, (create .+?)(\."?)', re.I), _if_exiled),
    (re.compile(rf"return (?:CARDNAME|this card) from your graveyard to the battlefield( tapped)?\.", re.I),
     lambda m: ReturnThisFromGraveyard(bool(m[1]))),
    (re.compile(rf"return (?:CARDNAME|this card) from your graveyard to your hand\.", re.I),
     lambda m: ReturnThisFromGraveyard(to="hand")),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Exile(m[2].lower(), bool(m[1]))),
    (re.compile(rf"exile {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Exile, m)),
    (re.compile(rf"destroy X target {_PLURAL_KIND}\.", re.I), lambda m: DestroyX(_PLURAL_KINDS[m[1].lower()] + _suffix(m[2]))),
    (re.compile(rf"exile X target {_PLURAL_KIND}\.", re.I), lambda m: ExileX(_PLURAL_KINDS[m[1].lower()] + _suffix(m[2]))),
    (re.compile(r"destroy up to X target artifacts and/or enchantments\.", re.I),
     lambda m: DestroyUpToX("artifact or enchantment")),
    (re.compile(r"choose any number of target creatures you control\.", re.I), lambda m: _ChooseAnyNumber("creature you control")),
    (re.compile(r"for each of them, create a token that's a copy of that creature, except it has haste\.", re.I),
     lambda m: _CopyEachWithHaste()),
    (re.compile(r"exile those tokens at the beginning of the next end step\.", re.I), lambda m: _ExileThoseTokens()),
    (re.compile(rf"exile up to one target {_PERMANENT_KIND}\.", re.I), lambda m: Exile(m[1].lower(), optional_target=True)),
    (re.compile(r"exile target ((?:noncreature|creature|instant or sorcery|artifact|enchantment) )?spell\.", re.I),
     lambda m: Counter(f"{m[1].lower()}spell" if m[1] else "spell", exile=True)),
    (re.compile(r"if that spell is countered this way, exile it instead of putting it into its owner's graveyard\.", re.I),
     lambda m: ExileInstead()),
    (re.compile(r"at the beginning of your next main phase, add an amount of \{C\} equal to that spell's mana value\.", re.I),
     lambda m: _DelayedMana()),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND}, then return (?:it|that card) to the battlefield under "
                r"(your|its owner's) control\.", re.I),
     lambda m: Flicker(m[2].lower(), under_owner=m[3].lower() != "your", another=bool(m[1]))),
    (re.compile(r"return (?:it|that card) to the battlefield under (your|its owner's) control at the beginning of the "
                r"next end step\.", re.I), lambda m: ReturnLater("battlefield", m[1].lower() != "your")),
    (re.compile(r"return (?:it|that card) to its owner's hand at the beginning of the next end step\.", re.I),
     lambda m: ReturnLater("hand", True)),
    (re.compile(rf"exile the top (?:card|{_N} cards) of your library\.", re.I), lambda m: ExileTop(_count(m[1] or "one"))),
    (re.compile(r"you may play (?:it|that card|those cards|them) this turn\.", re.I), lambda m: PlayExiled("this turn")),
    (re.compile(r"until (?:the )?end of turn, you may play (?:it|that card|those cards|them)\.", re.I),
     lambda m: PlayExiled("this turn")),
    (re.compile(r"until (?:the )?end of your next turn, you may play (?:it|that card|those cards|them)\.", re.I),
     lambda m: PlayExiled("next turn")),
    (re.compile(r"you may play (?:it|that card|those cards|them) until (?:the )?end of your next turn\.", re.I),
     lambda m: PlayExiled("next turn")),  # Clockwork Percussionist
    (re.compile(r"you may play (?:it|that card|those cards|them) until your next end step\.", re.I),
     lambda m: PlayExiled("next end step")),  # Opera Love Song
    (re.compile(r"until your next end step, you may play (?:it|that card|those cards|them)\.", re.I),
     lambda m: PlayExiled("next end step")),
    (re.compile(r"choose one of them\.", re.I), lambda m: _ChooseOneOfThem()),  # Heroes' Hangout
    (re.compile(r"the exiled card's owner creates an X/X (\w+) (\w+) creature token, where X is the mana value of the exiled card\.", re.I),
     lambda m: ExiledOwnerGetsToken(Card(name=m[2], type_line=f"Token Creature — {m[2]}", power="0", toughness="0",
                                         colors=(_COLOR_WORDS[m[1].lower()],)))),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND} until {_SELF} leaves the battlefield\.", re.I),
     lambda m: ExileUntilLeaves(m[2].lower(), bool(m[1]))),
    (re.compile(rf"target (player|opponent) draws {_N} cards?\.", re.I), lambda m: TargetDraw(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) draws {_N} cards? and loses {_N} life\.", re.I),
     lambda m: TargetDrawLose(_count(m[2]), _count(m[3]), m[1].lower())),
    (re.compile(r"you and target opponent each reveal the top card of your library\. You each lose life equal to the mana value "
                r"of the card revealed by the other player\. You each put the card you revealed into your hand\.", re.I),
     lambda m: RevealTopTradeLife()),
    (re.compile(rf"you and target opponent each draw {_N} cards?\.", re.I), lambda m: YouAndTargetDraw(_count(m[1]))),
    (re.compile(rf"each player loses {_N} life\.", re.I), lambda m: EachPlayerLosesLife(_count(m[1]))),
    (re.compile(r"you may discard a card\.", re.I), lambda m: _MayDiscard()),
    (re.compile(rf"you may sacrifice an? {_SACRIFICE_KIND}\.", re.I), lambda m: _MaySacrifice(m[1].lower())),
    (re.compile(rf"you may remove an? {_COUNTER} from (?:it|{_SELF})\.", re.I), lambda m: _MayRemoveCounter(_counter_name(m[1]))),
    (re.compile(rf"if you do, draw {_N_FIXED} cards?(?:, then mill {_N_FIXED} cards?)?\.", re.I),
     lambda m: _IfYouDoDraw(_number(m[1]), _number(m[2]) if m[2] else 0)),
    (re.compile(r"you gain life equal to the life lost this way\.", re.I), lambda m: _GainLifeLost()),
    (re.compile(r"each player may discard their hand and draw (seven) cards\.", re.I),
     lambda m: EachMayWheel(_number(m[1]))),
    (re.compile(r"(?:you may )?tap or untap target (creature|permanent)\.", re.I), lambda m: TapOrUntap(m[1].lower())),  # Derevi: permanent
    (re.compile(rf"target (player|opponent) gains {_N} life\.", re.I), lambda m: TargetGainLife(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) loses {_N} life\.", re.I), lambda m: TargetLoseLife(_count(m[2]), m[1].lower())),
    # Sanguine Bond, Exquisite Blood: "that much" is the life the trigger's event carried, which the game keeps as X
    (re.compile(r"target (player|opponent) loses that much life\.", re.I), lambda m: TargetLoseLife("X", m[1].lower())),
    (re.compile(r"each opponent loses that much life\.", re.I), lambda m: OpponentsLoseLife("X")),
    (re.compile(r"you gain (?:that much life|life equal to that damage)\.", re.I), lambda m: GainLife("X")),
    (re.compile(rf"return (another |up to one )?target {_PERMANENT_KIND} to its owner's hand\.", re.I),
     # "Return another target ..." can be neither the source (a trigger's) nor the spell's earlier target (Rushing River).
     lambda m: ReturnToHand(m[2].lower(), (m[1] or "").lower() == "another ", (m[1] or "").lower() == "up to one ",
                            distinct=(m[1] or "").lower() == "another ")),
    (re.compile(rf"return {_UP_TO} target {_PLURAL_KIND} to their owners' hands\.", re.I), lambda m: _up_to(ReturnToHand, m)),
    (re.compile(rf"return (five|six|seven) target {_PLURAL_KIND} to their owners' hands\.", re.I),  # Aether Gale: exactly that many
     lambda m: [ReturnToHand(_PLURAL_KINDS[m[2].lower()] + _suffix(m[3]), distinct=n > 0) for n in range(_number(m[1]))]),
    (re.compile(rf"return all {_CARDS_PLURAL} from your graveyard to (the battlefield|your hand)\.", re.I),
     lambda m: ReturnAllFromGraveyard(_card_kind(re.sub(r"\bcards\b", "card", m[1])), "battlefield" if m[2].lower() == "the battlefield" else "hand")),
    (re.compile(rf"return all {_MASS_FILTERED} to (?:their owners' hands|their owner's hand)\.", re.I), lambda m: _mass_effect(ReturnAllToHand, m)),
    (re.compile(rf"return {_UP_TO} target {_CARDS_PLURAL} from your graveyard to your hand\.", re.I),
     lambda m: [ReturnFromGraveyard(_graveyard_kind(m[2].replace("cards", "card", 1), "yours"), "hand",
                                    optional_target=True, distinct=n > 0) for n in range(_number(m[1]))]),
    (re.compile(rf"return (two|three) target {_CARDS_PLURAL} from your graveyard to your hand\.", re.I),  # exactly that many
     lambda m: [ReturnFromGraveyard(_graveyard_kind(m[2].replace("cards", "card", 1), "yours"), "hand", distinct=n > 0)
                for n in range(_number(m[1]))]),
    (re.compile(rf"return up to one target {_CARD_TYPE} from your graveyard to your hand\.", re.I),  # Witch of the Moors
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "hand", optional_target=True)),
    (re.compile(rf"return target {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "hand")),
    (re.compile(rf"return target {_CARD_TYPE} from your graveyard to the battlefield with an indestructible counter on it\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "battlefield", counter="indestructible")),
    (re.compile(rf"exile target {_PERMANENT_KIND}\. its controller draws a card\.", re.I), lambda m: ExileControllerDraws(m[1].lower())),
    (re.compile(rf"return another target {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "hand", another=True)),
    (re.compile(rf"(?:return|put) target {_CARD_TYPE} from (your|a) graveyard (?:to|onto) the battlefield( tapped)?"
                r"(?: under your control)?\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours" if m[2].lower() == "your" else "any"), "battlefield",
                                   bool(m[3]))),
    (re.compile(rf"put target {_CARD_TYPE} from your graveyard on (the bottom|top) of your library\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "library_bottom" if m[2].lower() == "the bottom" else "library_top")),
    (re.compile(rf"exile target {_CARD_TYPE} from a graveyard\.", re.I),
     lambda m: ExileFromGraveyard(_graveyard_kind(m[1], "any"))),
    (re.compile(rf"exile target {_CARD_TYPE} from your graveyard\.", re.I),
     lambda m: ExileFromGraveyard(_graveyard_kind(m[1], "yours"))),
    (re.compile(rf"search your library for an? {_SEARCH_TYPE}, (?:reveal (?:it|that card), )?(?:put (?:it|that card) into your hand, "
                r"then shuffle|then shuffle and put (?:it|that card|the card) on top(?: of your library)?)\.", re.I),
     lambda m: SearchLibrary(_card_kind(m[1]), "hand" if "into your hand" in m[0] else "top", "reveal" in m[0].lower())),
    (re.compile(r"search your library for a card with the same mana value as (?:this card|CARDNAME), reveal it, put it into your hand, then shuffle\.", re.I),
     lambda m: SearchLibrary("card|mv=self", "hand", True)),  # Transmute
    (re.compile(r"search your library for an? ((?:legendary )?(?:permanent|creature)) card with mana value less than CARDNAME's power, "
                r"put (?:it|that card) (onto the battlefield|into your hand), then shuffle\.", re.I),
     lambda m: SearchLibrary(m[1].lower() + "|mv<power", _DESTINATIONS[m[2]], False)),  # Sisay, Weatherlight Captain
    (re.compile(r"search your library for a land card, put it into your graveyard, then shuffle\.", re.I),
     lambda m: SearchLibrary("land", "graveyard", False)),
    (re.compile(r"search your library for a land card, put (?:it|that card) onto the battlefield( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(1, ("*",), 1, bool(m[1]), False)),  # Crop Rotation
    (re.compile(r"search your library for up to (two|three|four) basic land cards, put them onto the battlefield, then shuffle\.", re.I),
     lambda m: SearchForLands(_count(m[1]), (), _count(m[1]), False, False)),  # Harrow
    (re.compile(r"search your library for a nonbasic land card, put it onto the battlefield( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(1, ("nonbasic",), 1, bool(m[1]), False)),
    (re.compile(rf"search your library for up to (two|three|four) {_LAND_TYPES_PLURAL}, put them onto the battlefield"
                r"( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(_count(m[1]), _land_types(m[2]), _count(m[1]), bool(m[3]), False)),
    (re.compile(rf"search your library for up to (two|three|four) basic {_LAND_TYPES_PLURAL}, reveal (?:them|those cards), put them "
                r"into your hand, then shuffle\.", re.I),  # Archaeomancer's Map
     lambda m: SearchForLands(_count(m[1]), _land_types(m[2]), 0, False, True, basic_only=True)),
    (re.compile(r"search your library for up to (two|three|four) basic land cards, reveal (?:them|those cards), put them into "
                r"your hand, then shuffle\.", re.I),  # Land Tax
     lambda m: SearchForLands(_count(m[1]), (), 0, False, True)),
    (re.compile(rf"search your library for a basic {_LAND_TYPES} card, put it onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: SearchForLands(1, _land_types(m[1]), 1, True, False, basic_only=True)),  # the Landscape cycle
    (re.compile(r"search your library for up to two basic land cards that share a land type, put them onto the battlefield tapped, "
                r"then shuffle\.", re.I),
     lambda m: SearchForLands(2, (), 2, True, False, share_type=True)),  # Myriad Landscape
    (re.compile(rf"untap up to {_NUM} lands\.", re.I), lambda m: UntapLands(_number(m[1]))),
    (re.compile(r"you gain protection from everything until your next turn\.", re.I), lambda m: PlayerProtection()),
    (re.compile(r"(?:this (?:Saga|creature|artifact|enchantment|land)|CARDNAME) gains \"(.+)\"\.?", re.I),  # the ability stays: a Saga's chapter
     lambda m: GainsAbility(line) if _is_known_ability(line := m[1].replace("'", '"')) else None),
    (re.compile(r"search your library for an? ([a-z]+) card with mana cost \{0\} or \{1\}, put it onto the battlefield, then shuffle\.", re.I),
     lambda m: SearchLibrary(f"{m[1].lower()}|mv<=1", "battlefield", False)),  # (mana value 1 or less: the same for every such artifact)
    (re.compile(r"until your next turn, your life total can't change and you gain protection from everything\.", re.I),
     lambda m: [LifeLocked(), PlayerProtection()]),
    (re.compile(r"all permanents you control phase out\.", re.I), lambda m: PhaseOutAll()),
    (re.compile(r"exile CARDNAME\.", re.I), lambda m: ExileThisSpell()),
    (re.compile(r"shuffle CARDNAME into its owner's library\.", re.I), lambda m: ShuffleThisSpell()),
    (re.compile(r"search your library for an? ((?:green |nonland )?(?:creature|artifact)) card( with mana value X or less)?, put it onto "
                r"the battlefield, then shuffle\.", re.I),
     lambda m: SearchLibrary(m[1].lower() + ("|mv<=x" if m[2] else ""), "battlefield", False)),  # Chord of Calling, Natural Order
    (re.compile(r"search your library for a card, put that card into your hand, discard a card at random, then shuffle\.", re.I),
     lambda m: [SearchLibrary("card", "hand", False), Discard(1, "you", True)]),  # Gamble
    (re.compile(r"you lose life equal to (?:its|that card's|that permanent's|that spell's) mana value\.", re.I), lambda m: LoseLifeEqualToManaValue()),
    (re.compile(rf"you lose {_N} life\.", re.I), lambda m: LoseLife(_count(m[1]))),
    (re.compile(r"search your library for up to two basic land cards, reveal those cards, put one onto the battlefield "
                r"tapped and the other into your hand, then shuffle\.", re.I),
     lambda m: SearchForLands(2, (), 1, True, True)),
    (re.compile(r"search your library for up to (two|three|four) basic land cards, (?:reveal (?:them|those cards), )?"
                r"put (?:them|those cards) onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: SearchForLands(_count(m[1]), (), _count(m[1]), True, False)),
    (re.compile(rf"search your library for an? {_LAND_TYPES} card, put (?:it|that card) onto the battlefield( tapped)?, "
                r"then shuffle\.", re.I),
     lambda m: SearchForLands(1, _land_types(m[1]), 1, bool(m[2]), False)),
    (re.compile(rf"search your library for (?:up to {_N_FIXED}|(any number) of) {_SEARCH_TYPES}( not named CARDNAME)?"
                r"( that each have different names)?, (reveal them, )?(?:put them (into your hand|onto the battlefield|into your graveyard), "
                r"then shuffle|then shuffle and put (?:them|those cards) on top(?: of your library)? in any order)\.", re.I),
     lambda m: SearchMany(_card_kind(m[3]), None if m[2] else _number(m[1]), _DESTINATIONS.get(m[7], "top"), reveal=bool(m[6]),
                          distinct=bool(m[5]), not_self=bool(m[4]))),  # Buried Alive, Goblin Recruiter, Tiamat
    (re.compile(r"the owner of target permanent shuffles it into their library, then reveals the top card of their library\.",
                re.I), lambda m: ChaosWarp()),
    (re.compile(r"if it's a permanent card, they put it onto the battlefield\.", re.I), lambda m: _ChaosPut()),
    (re.compile(rf"draw a card, then put {_SELF} on top of its owner's library\.", re.I),
     lambda m: [Draw(1), PutSourceOnLibraryTop()]),
    (re.compile(rf"scry {_N}\.", re.I), lambda m: Scry(_count(m[1]))),
    (re.compile(rf"scry {_N}, then draw (?:a card|{_N} cards)\.", re.I),
     lambda m: [Scry(_count(m[1])), Draw(_count(m[2] or "a"))]),
    (re.compile(rf"scry {_N_FIXED}, then reveal the top card of your library\.", re.I),
     lambda m: RevealTopStep("reveal", _number(m[1]))),
    (re.compile(r"if it's a land card, put it onto the battlefield( tapped)?\.", re.I),
     lambda m: RevealTopStep("land", tapped=bool(m[1]))),
    (re.compile(r"otherwise, draw a card\.", re.I), lambda m: RevealTopStep("otherwise")),
    (re.compile(rf"surveil {_N}\.", re.I), lambda m: Surveil(_count(m[1]))),
    (re.compile(rf"look at the top {_N} cards of your library, then put them back in any order\.", re.I),
     lambda m: PutBackTop(_count(m[1]))),
    (re.compile(r"you may shuffle\.", re.I), lambda m: _MayShuffle()),
    (re.compile(rf"draw {_N_FIXED} cards, then put {_N_FIXED} cards from your hand on top of your library in any order\.", re.I),
     lambda m: DrawThenPutBack(_number(m[1]), _number(m[2]))),
    (re.compile(rf"look at the top (?:{_N} cards?|card) of your library\.", re.I),
     lambda m: LookAtTop(_count(m[1] or "one"))),
    (re.compile(rf"put {_N_FIXED} of (?:them|those cards) into your hand(?: and (?:the rest|the other) (on the bottom of your library"
                r"(?: in (?:any|a random) order)?|into your graveyard))?\.", re.I),
     lambda m: TakeFromTop(None, take=_number(m[1]), rest=None if m[2] is None else "graveyard" if m[2].startswith("into") else "bottom")),
    (re.compile(rf"if (.+), instead put {_N_FIXED} of them into your hand and the rest on the bottom of your library in any order\.", re.I),
     lambda m: _InsteadTake(c, _number(m[2])) if (c := _condition(m[1])) else None),
    (re.compile(rf"you may reveal an? {_SEARCH_TYPE} from among them and put (?:it|that card) into your hand\.", re.I),
     lambda m: TakeFromTop(_card_kind(m[1]))),
    (re.compile(rf"you may put an? {_SEARCH_TYPE} from among them onto the battlefield\.", re.I),
     lambda m: TakeFromTop(_card_kind(m[1]), "battlefield")),  # Ureni of the Unwritten
    (re.compile(r"put the rest on the bottom of your library in (?:a random|any) order\.", re.I),
     lambda m: RestOnBottom()),
    (re.compile(r"return a land you control to its owner's hand\.", re.I), lambda m: ReturnOwnLand()),
    (re.compile(r"add ((?:\{[WUBRGC]\})+)\.", re.I),
     lambda m: AddMana(tuple(frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[1].upper())))),
    (_RETURN_UP_TO_POWER, lambda m: ReturnFromGraveyard("graveyard:nonland permanent|mv<=power:yours", "battlefield")),
    (_RETURN_UP_TO_DAMAGE, lambda m: ReturnFromGraveyard("graveyard:creature|mv<=x:yours", "battlefield")),  # Venerable Warsinger
    (re.compile(r"exile all (?:cards from all )?graveyards\.", re.I), lambda m: ExileAllGraveyards()),
    (re.compile(r"each opponent loses all counters\.", re.I), lambda m: OpponentsLoseCounters()),
    (re.compile(r"you lose all but 1 life\.", re.I), lambda m: LoseAllButOneLife()),
    (re.compile(r"you gain life equal to the life you lost when it entered\.", re.I), lambda m: GainLifeItLost()),
    (re.compile(r"return it to the battlefield tapped under its owner's control at the beginning of their next upkeep\.", re.I),
     lambda m: ReturnDeadAtNextUpkeep()),
    (re.compile(r"you may put a creature card from your hand onto the battlefield\. If you do, sacrifice it unless you pay its "
                r"mana cost reduced by \{(\d+)\}\.", re.I), lambda m: PutCreatureFromHand(int(m[1]))),
    (re.compile(rf"mill {_N} cards?, then (you may )?return ({_MILL_KIND}(?: and {_MILL_KIND})?) from your graveyard to "
                r"(your hand|the battlefield)( tapped)?\.", re.I),
     lambda m: None if " and " not in m[3] and m[4].lower() == "your hand" else  # one kind to hand: Mill, then ReturnChosen
     MillThenReturn(_count(m[1]), tuple(_card_kind(re.sub(r"^an? ", "", part)) for part in re.split(r" and ", m[3])),
                    "hand" if m[4].lower() == "your hand" else "battlefield", bool(m[5]), bool(m[2]))),
    (re.compile(r"each opponent creates a token that's a copy of it\. The tokens are goaded for the rest of the game\.", re.I),
     lambda m: EachOpponentGetsGoadedCopy()),
    (re.compile(r"create (?:a token that's a copy of|(five) tokens that are copies of) another target creature you control"
                r"(, except it isn't legendary)?\. (?:It gains|They gain) haste\. Sacrifice (?:it|them) at the beginning of the "
                r"next end step\.", re.I),
     lambda m: CopiesOfAnotherCreature(5 if m[1] else 1, bool(m[2]))),
    (re.compile(r"that player copies that spell for each other creature they control that the spell could target\. Each copy "
                r"targets a different one of those creatures\.", re.I), lambda m: CopySpellForEachOtherCreature()),
    (re.compile(r"exile (?:it|that creature)\. If you do, create a token that's a copy of (?:it|that creature|that card)(?:, except (.+))?\.(\"?)",
                re.I), lambda m: ExileDeadCopy(c) if (c := _copy_changes(m[1] + '."' * bool(m[2])) if m[1] else CopyChanges()) else None),
    (re.compile(r"return the exiled card to its owner's graveyard\.", re.I), lambda m: ReturnExiledToGraveyard()),
    (re.compile(rf"{_SELF} becomes a copy of up to one target nonlegendary creature you control until end of turn, except it has "
                r"([a-z]+)\.", re.I), lambda m: BecomeCopyUntilEndOfTurn(m[1].capitalize())),
    (re.compile(r"for each creature token you control that entered this turn, create a tapped and attacking token that's a copy of that "
                r"token\. At the beginning of the next end step, sacrifice those tokens\.", re.I),
     lambda m: CopyEnteredTokensAttacking()),
    (re.compile(r"create X tokens that are copies of another target creature you control, where X is one plus the number of instant "
                r"and sorcery spells you've cast this turn\. They gain haste\. Exile them at the beginning of the next end step\.",
                re.I), lambda m: [DefineX(Amount("one_plus_spells", "instant or sorcery spell")),
                                  CopiesOfAnotherCreature("X", exile=True)]),
    (re.compile(r"target player draws cards equal to half the number of cards in their library and loses half their life\. "
                r"Round up each time\.", re.I), lambda m: DrawHalfLibraryLoseHalfLife()),
    (re.compile(r"Exile the top four cards of your library in a face-down pile, then exile the top four cards of your library in a face-up pile\. An opponent chooses one of those piles\. Put that pile into your graveyard\. Look at the cards in the other pile\. You may cast a spell from among them without paying its mana cost\. Put the rest into your hand\.", re.I), lambda m: PilesOfFour()),
    (re.compile(r"Council's dilemma — Starting with you, each player votes for past or present\. You mill a card for each "
                r"past vote, then (?:CARDNAME|[A-Z][\w' ]+) deals damage to each opponent equal to the total mana value of cards milled "
                r"this way\. Exile the top card of your library for each present vote\. Until the end of your next turn, you may "
                r"play the exiled cards\."), lambda m: PastOrPresentVote()),
    (re.compile(r"Exile target instant or sorcery card from your graveyard\. Creatures you control get "
                                     r"\+X/\+0 until end of turn, where X is that card's mana value\. Whenever a creature you control "
                                     r"deals combat damage to a player this turn, copy the exiled card\. You may cast the copy "
                                     r"without paying its mana cost\.", re.I), lambda m: SurgeToVictory()),
    (re.compile(rf"remove {_N_FIXED} ([a-z]+) counters? from (?:{_SELF})\.", re.I),
     lambda m: RemoveCountersFromSource(_number(m[1]), m[2].lower())),
    (re.compile(rf"(?:{_SELF}) deals damage to target (player|opponent) equal to (.+)\.", re.I),
     lambda m: [DefineX(a), Damage("X", m[1].lower())] if (a := _amount(m[2])) else None),
    (re.compile(rf"(?:{_SELF}) deals damage to (any target|target player or planeswalker) equal to (?:the number of |)(.+)\.", re.I),  # Massive Raid, Goblin War Strike
     lambda m: [DefineX(a), Damage("X", "any" if m[1].lower() == "any target" else m[1].lower().removeprefix("target "))]
     if (a := _amount("the number of " + m[2] if not m[2].startswith("the number of") else m[2])) else None),
    (re.compile(rf"(?:{_SELF}) deals (\d+) damage to the player or planeswalker (?:that creature|it) is attacking\.", re.I),
     lambda m: DamageWhatItAttacks(int(m[1]))),
    (re.compile(r"add \{([WUBRGC])\} for each card in target opponent's hand\.", re.I), lambda m: AddManaPerCardInHand(m[1].upper())),
    (re.compile(rf"reveal the top {_N} cards of your library\. Put all ([A-Za-z]+(?: creature)?) cards( with mana value \d+ or less)? "
                r"(?:revealed this way|from among them) (into your hand|onto the battlefield) and the rest on the bottom of your library in "
                r"(?:any|a random) order\.", re.I),
     lambda m: RevealTopPutAll(_number(m[1]), _card_kind(f"{m[2]} card{m[3] or ''}"), _DESTINATIONS[m[4]])),  # Goblin Ringleader, Muxus
    (re.compile(r"add \{([WUBRGC])\} for each (creature you control|(?-i:[A-Z][a-z]+) on the battlefield|(?-i:[A-Z][a-z]+) you control)\.", re.I),
     lambda m: AddManaForEach(m[1].upper(), a) if (a := _amount("the number of " + m[2] if " on the battlefield" in m[2] and not m[2].startswith("the") else m[2])) else None),
    (re.compile(r"until end of turn, you don't lose this mana as steps and phases end\.", re.I), lambda m: KeepManaThisTurn()),
    (re.compile(r"exile (?:CARDNAME|this spell) with (a|two|three|four|five|\d+) time counters? on it\.", re.I),
     lambda m: ExileWithTimeCounters(_number(m[1]))),
    (re.compile(rf"target player puts an? {_COUNTER} on each creature they control\.", re.I),
     lambda m: TargetPutsCountersOnEach(_counter_name(m[1]))),
    (re.compile(rf"for each player, put an? {_COUNTER} on up to one target creature that player controls\.", re.I),
     lambda m: PutCounterPerPlayer(_counter_name(m[1]))),
    (re.compile(r"each player puts a vow counter on a creature they control and sacrifices the rest\. Each of those creatures "
                r"can't attack you or planeswalkers you control for as long as it has a vow counter on it\.", re.I),
     lambda m: VowCounters()),
    (re.compile(rf"put an? {_COUNTER} on each of up to X target creatures( you control)?\.", re.I),
     lambda m: PutCountersOnEachUpToX(_counter_name(m[1]), "creature you control" if m[2] else "creature")),
    (re.compile(r"Auras, Equipment, and modified creatures you control gain hexproof until end of turn\.", re.I),
     lambda m: ModifiedGainHexproof()),
    (re.compile(r"move all counters from target (nonland permanent you control) onto another target (nonland permanent you control)\.",
                re.I), lambda m: [MoveCountersFrom(m[1].lower()), MoveCountersOnto(None, None, m[2].lower())]),
    (re.compile(r"remove all counters from target (nonland permanent you control)\. Draw a card for each counter removed this "
                r"way\.", re.I), lambda m: RemoveAllCountersDraw(m[1].lower())),
    (re.compile(r"you may put a \+1/\+1 counter on a creature\. Then choose odd or even\. Return each creature with power of "
                r"the chosen quality to its owner's hand\.", re.I), lambda m: ZimonesHypothesis()),
    (re.compile(r"shuffle your library, then reveal cards from the top of it until you reveal a nonland card\. Exile that "
                r"card and put the rest on the bottom of your library in a random order\. You may cast the exiled card "
                r"without paying its mana cost\.", re.I), lambda m: ShuffleRevealCast()),
    (re.compile(r"copy target (instant or sorcery spell|instant spell|sorcery spell|creature spell|permanent spell|activated or triggered ability"
                r"|instant spell, sorcery spell, activated ability, or triggered ability)( you control)?"
                r"(?:, except (?:that the copy is (white|blue|black|red|green)|(.+)))?\.", re.I),
     lambda m: CopySpell(m[1].lower() + (m[2] or "").lower(), color=_COPY_COLORS[m[3].lower()] if m[3] else None, changes=c)
     if (c := _copy_changes(m[4]) if m[4] else None) or not m[4] else None),
    (re.compile(r"if this spell was cast from a graveyard, copy that spell twice instead\.", re.I), lambda m: _TwiceFromGraveyard()),
    (re.compile(r"copy it for each other instant and sorcery spell you've cast before it this turn\.", re.I),  # Thousand-Year Storm
     lambda m: [DefineX(Amount("spells_before", "instant or sorcery spell")), CopySpellTimes("X")]),
    (re.compile(r"copy target (instant or sorcery spell), then return it to its owner's hand\.", re.I),
     lambda m: CopySpell(m[1].lower(), return_to_hand=True)),
    (re.compile(r"copy (?:it|that spell)\.", re.I), lambda m: CopyTriggeringSpell()),
    (re.compile(r"double the value of X\.", re.I), lambda m: DoubleXOfTriggeringSpell()),
    (re.compile(r"copy that ability\. You may choose new targets for the copy\.", re.I), lambda m: CopyTriggeringAbility(True)),
    (re.compile(r"copy target triggered ability you control( twice)?\.", re.I), lambda m: CopyTriggeredAbility(times=2 if m[1] else 1)),
    (re.compile(r"any number of other target creatures you control phase out\.", re.I), lambda m: PhaseOut()),
    (re.compile(r"create a white Aura enchantment token named Contract attached to target creature an opponent controls\. The token has "
                r"enchant creature and \"Whenever enchanted creature attacks, it gets \+2/\+0 until end of turn if it's attacking one of "
                r"your opponents\. Otherwise, its controller loses 2 life\.\"", re.I), lambda m: CreateContract()),
    (re.compile(r"it gets \+2/\+0 until end of turn if it's attacking one of your opponents\. Otherwise, its controller loses 2 "
                r"life\.", re.I), lambda m: ContractAttack()),
    (re.compile(r"for each player, you choose from among the permanents that player controls an artifact, a creature, an enchantment, "
                r"and a planeswalker\. Then each player sacrifices all other nonland permanents they control\.", re.I),
     lambda m: TragicArrogance()),
    (re.compile(rf"any number of target players each lose {_N_FIXED} life and sacrifice a creature of their choice\. You add ((?:\{{[WUBRGC]\}})+) and "
                r"draw a card\.", re.I),
     lambda m: PlayersLoseSacrificeAddManaDraw(_number(m[1]), tuple(frozenset(x) for x in re.findall(r"[WUBRGC]", m[2])))),
    (re.compile(r"each player sacrifices a (creature or planeswalker) of their choice\. If you sacrificed a permanent this way, you may "
                r"return another permanent card from your graveyard to your hand\.", re.I),
     lambda m: EachSacrificesThenReturn(m[1].lower())),
    (re.compile(r"move any number of ([+\-\u2212]1/[+\-\u2212]1) counters from (?:this creature|CARDNAME) onto other creatures\.", re.I),
     lambda m: MoveCountersToOthers(_counter_name(m[1]))),
    (re.compile(rf"target player shuffles up to {_N_FIXED} target cards from their graveyard into their library\.", re.I),
     lambda m: ShuffleIntoLibrary(max_targets=_number(m[1]))),
    (re.compile(r"level \d", re.I), lambda m: LevelUp()),
    (re.compile(r"if this spell was cast from a graveyard, you may copy this spell and may choose a new target for the copy\.", re.I),
     lambda m: MayCopyThisSpellFromGraveyard()),
    (re.compile(r"return target permanent card with mana value (\d+) or less from your graveyard to the battlefield\.", re.I),
     lambda m: ReturnFromGraveyard(f"graveyard:permanent|mv<={m[1]}:yours", "battlefield")),
    (re.compile(r"exile up to one target instant or sorcery card from your graveyard and copy it\. You may cast the copy without "
                r"paying its mana cost\.", re.I), lambda m: ExileThenCastCopy()),
    (re.compile(r"each player exiles a card from their graveyard\. When one or more nonland cards are exiled this way, put that many "
                r"\+1/\+1 counters on target attacking creature\.", re.I), lambda m: EachExilesGraveyardCardCounters()),
    (re.compile(r"return up to one target artifact, creature, or non-Aura enchantment card with mana value (\d+) or less from your "
                r"graveyard to the battlefield with a finality counter on it\. It's a 1/1 Spirit creature with flying in addition to "
                r"its other types\.", re.I),
     lambda m: ReturnFromGraveyard(f"graveyard:artifact or creature or non-aura enchantment|mv<={m[1]}:yours", "battlefield",
                                   optional_target=True, finality=True)),
    (re.compile(r"choose target card exiled with (?:CARDNAME|this \w+)\. You may cast that card this turn without paying its mana "
                r"cost\. If that spell would be put into a graveyard, put it on the bottom of its owner's library instead\.", re.I),
     lambda m: CastExiledWithFree()),
    (re.compile(r"put a card exiled with (?:this artifact|CARDNAME) into its owner's graveyard\. If it's a land card, create a "
                r"Treasure token\. If it's a nonland card, create an? (.+ creature token)\.", re.I),
     lambda m: PutExiledWithIntoGraveyard(TREASURE, made[1]) if (made := _token("a " + m[1])) else None),
    (re.compile(r"put a number of \+1/\+1 counters on it equal to the damage dealt\.", re.I),
     lambda m: PutCountersOnSource("X", "+1/+1")),  # X is the damage the trigger saw
    (re.compile(r"you may choose new targets for the cop(?:y|ies)\.", re.I), lambda m: NewTargets()),
    (re.compile(rf"gain control of target {_PERMANENT_KIND}( until end of turn)?\.", re.I),
     lambda m: GainControl(m[1].lower(), until_end_of_turn=bool(m[2]))),
    (re.compile(r"untap that creature\.", re.I), lambda m: UntapThat()),
    (re.compile(rf"untap target {_PERMANENT_KIND} and gain control of it until end of turn\.", re.I),
     lambda m: [GainControl(m[1].lower(), until_end_of_turn=True), UntapThat()]),
    (re.compile(r"that creature gains haste until end of turn\.", re.I),
     lambda m: PumpSource(Modifier(keywords=frozenset({"haste"})))),
    (re.compile(r"tap (?:it|that creature)\.", re.I), lambda m: TapThat()),
    (re.compile(rf"put {_N} stun counters? on (?:it|that creature)\.", re.I), lambda m: PutStunCounters(_count(m[1]))),
    (re.compile(rf"put {_N} stun counters? on (?:this creature|{{self}})\.".replace("{self}", "CARDNAME"), re.I),
     lambda m: PutStunOnSource(_count(m[1]))),
    (re.compile(r"all creatures able to block target (creature) this turn do so\.", re.I), lambda m: LureThisTurn(m[1].lower())),
    (re.compile(rf"{_SELF} can attack this turn as though it didn't have defender\.", re.I), lambda m: AttackDespiteDefender()),
    (re.compile(r"target (creature) blocks this turn if able\.", re.I), lambda m: MustBlockThisTurn(m[1].lower())),
    (re.compile(rf"target (creature) blocks (?:this creature|{{self}}) this turn if able\.".replace("{self}", "CARDNAME"), re.I),
     lambda m: MustBlockThisTurn(m[1].lower(), source_only=True)),
    (re.compile(rf"tap target {_PERMANENT_KIND} and put {_N} stun counters? on (?:it|that creature)\.", re.I),
     lambda m: [Tap(m[1].lower()), PutStunCounters(_count(m[2]))]),
    (re.compile(rf"put {_N} stun counters? on each of them\.", re.I), lambda m: PutStunOnEach(_count(m[1]))),
    (re.compile(rf"tap {_UP_TO} target {_PLURAL_KIND} and put {_N} stun counters? on each of them\.", re.I),
     lambda m: [*_up_to(Tap, m), PutStunOnEach(_count(m[4]))]),
    (re.compile(rf"tap one or two target {_PLURAL_KIND}\.", re.I),
     lambda m: [Tap(_PLURAL_KINDS[m[1].lower()] + _suffix(m[2])),
                Tap(_PLURAL_KINDS[m[1].lower()] + _suffix(m[2]), optional_target=True, distinct=True)]),
    (re.compile(rf"tap up to one target {_PERMANENT_KIND} and put {_N} stun counters? on it\.", re.I),
     lambda m: [Tap(m[1].lower(), optional_target=True), PutStunCounters(_count(m[2]))]),
    (re.compile(r"attach (?:it|this Equipment) to target ((?:legendary )?creature you control)\.", re.I),
     lambda m: Attach(m[1].lower())),  # Mithril Coat
    (re.compile(r"you may cast a spell with mana value (\d+) or less from your hand without paying its mana cost\.", re.I),
     lambda m: MayCastFromHandFree(int(m[1]))),  # Rishkar's Expertise
    (re.compile(r"choose two target creature cards in your graveyard\. sacrifice a creature\. if you do, return the chosen cards to the "
                r"battlefield tapped\.", re.I), lambda m: SacrificeToReturnChosen()),  # Victimize
    (re.compile(r"choose target (creature(?: you control)?)\.", re.I), lambda m: ChooseTarget(m[1].lower())),
    (re.compile(r"draw that many cards\.", re.I), lambda m: Draw("X")),
    (re.compile(r"create that many (Treasure|Clue|Food) tokens\.", re.I), lambda m: CreateTokens("X", _NAMED_TOKENS[m[1].lower()])),  # Old Gnawbone
    (re.compile(r"until end of turn, that creature gains \"when this creature dies, return it to the battlefield tapped under its owner's "
                r"control\.\"", re.I), lambda m: ReturnWhenItDiesThisTurn()),  # Malakir Rebirth
    (re.compile(r"search your library for up to X basic land cards, where X is the greatest power among creatures you control\. put those "
                r"cards onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: [DefineX(Amount("greatest_power", "creature")), SearchForLands("X", (), "X", True, False)]),  # Traverse the Outlands
    (re.compile(r"put a \+1/\+1 counter on target (artifact creature) for each \+1/\+1 counter on (?:this creature|CARDNAME)\.", re.I),
     lambda m: [DefineX(Amount("source_counters", "+1/+1")), PutCounters("X", "+1/+1", m[1].lower())]),  # Modular
    (re.compile(r"proliferate twice\.", re.I), lambda m: Proliferate(2)),
    (re.compile(r"proliferate\.", re.I), lambda m: Proliferate()),
    (re.compile(r"proliferate (X) times\.", re.I), lambda m: Proliferate("X")),
    (re.compile(rf"target {_FIGHTER} fights (another )?target {_FIGHTER}\.", re.I),
     lambda m: [FightFirst(m[1].lower()), Fight(m[3].lower(), another=bool(m[2]))]),
    (re.compile(rf"target {_FIGHTER} deals damage equal to its power to (?:target {_FIGHTER}|(any target)"
                r"|target (creature or planeswalker (?:you don't control|an opponent controls)))\.", re.I),
     lambda m: [FightFirst(m[1].lower()), Fight("any" if m[3] else (m[2] or m[4]).lower(), one_sided=True)]),
    (re.compile(r"target creature you control deals damage equal to its power to each other creature and each opponent\.", re.I),
     lambda m: [FightFirst("creature you control"), PowerDamageToEachOther()]),
    # "It fights ...": the creature the sentence before it targeted (Primal Might, Epic Confrontation), or, with none, the source (Agatha's Champion)
    (re.compile(rf"(then )?(?:it|that creature|this creature) fights (up to one )?target {_FIGHTER}\.", re.I),
     lambda m: Fight(m[3].lower(), optional_target=bool(m[2]), follows=True, then=bool(m[1]))),
    (re.compile(rf"look at the top {_N_FIXED} cards of your library\. Put {_N_FIXED} of them into your hand and the rest on the bottom of your "
                r"library in any order\.", re.I), lambda m: LookTakeRestBottom(_number(m[1]), _number(m[2]))),
    (re.compile(r"target player draws X cards plus an additional card for each time they've cast a commander from the command zone "
                r"this game\.", re.I), lambda m: TargetDrawXPlusCasts()),
    (re.compile(r"add \{([WUBRGC])\} or \{([WUBRGC])\} for each permanent destroyed this way\.", re.I),
     lambda m: _ManaForEachDestroyed(frozenset({m[1].upper(), m[2].upper()}))),
    (re.compile(r"add \{([WUBRGC])\} for each tapped land your opponents control\.", re.I),
     lambda m: AddManaPerTappedLand(m[1].upper())),
    (re.compile(r"creatures you control have base power and toughness X/X until end of turn\.", re.I), lambda m: SetBaseEachX()),
    (re.compile(r"each creature deals damage to itself equal to its power\.", re.I), lambda m: EachDamagesItself()),
    (re.compile(rf"each creature deals {_N_FIXED} damage to its controller\.", re.I), lambda m: EachCreatureDamagesItsController(_number(m[1]))),
    (re.compile(rf"target player draws {_N_FIXED} cards, then discards {_N_FIXED} cards\.", re.I),
     lambda m: TargetDrawDiscard(_number(m[1]), _number(m[2]))),
    (re.compile(rf"target player mills {_N_FIXED} cards, then you return an? {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: TargetMillThenReturn(_number(m[1]), _card_kind(m[2]))),
    (re.compile(r"you gain half X life and draw half X cards\. round down each time\.", re.I),
     lambda m: [GainLife("hX"), Draw("hX")]),
    (re.compile(r"populate\.", re.I), lambda m: Populate()),
    (re.compile(r"(?i:put) an? ((?:[A-Z][a-z]+(?:, (?:or )?| or ))*[A-Z][a-z]+) (?i:creature card from your hand onto the "
                r"battlefield tapped and attacking that opponent\.)"),
     lambda m: PutAttackingFromHand(tuple(re.findall(r"[A-Z][a-z]+", m[1])))),
    (re.compile(rf"{_SELF} becomes prepared\.", re.I), lambda m: BecomePrepared()),
    (re.compile(rf"transform {_SELF}\.", re.I), lambda m: Transform()),
    (re.compile(rf"exile {_SELF}, then return it to the battlefield transformed under your control\.", re.I), lambda m: ReturnTransformed()),
    (re.compile(rf"return it to the battlefield( tapped)? and transformed under (?:its owner's|your) control\.", re.I),
     lambda m: ReturnTransformed(dies=True, tapped=m[1] is not None)),
    (re.compile(r"return it to the battlefield transformed under (?:its owner's|your) control at the beginning of the next end step\.", re.I),
     lambda m: ReturnTransformed(dies=True, end_step=True)),
    (re.compile(r"conjure a card named (.+?) onto the battlefield\.", re.I), lambda m: Conjure(m[1])),
    (re.compile(r"tap enchanted creature\.", re.I), lambda m: TapEnchanted()),
    (re.compile(r"untap enchanted creature\.", re.I), lambda m: TapEnchanted(untap=True)),  # Freed from the Real
    (re.compile(r"tap enchanted creature\. It becomes unprepared\.", re.I), lambda m: TapEnchanted(unprepare=True)),
    (re.compile(r"until end of turn, whenever you tap a mountain for mana, add an additional \{R\}\.", re.I),
     lambda m: ExtraMountainMana()),
    (re.compile(r"until end of turn, any time you could activate a mana ability, you may pay 1 life\. If you do, add \{C\}\.",
                re.I), lambda m: PayLifeForMana()),
    (re.compile(rf"whenever that creature deals combat damage to a player this combat, ({_SELF} becomes prepared)\.", re.I),
     lambda m: WhenThatDealsCombatDamage(BecomePrepared())),
    (re.compile(r"each creature you control becomes prepared\.", re.I), lambda m: PrepareEach()),
    (re.compile(r"target (creature(?: that attacked this turn)?) becomes (prepared|unprepared)\.", re.I),
     lambda m: TargetPrepared(m[1].lower(), m[2].lower() == "prepared")),
    (_COPY_TOKEN, _copy_token),
    (re.compile(r"for each (token|artifact|creature|nontoken creature|enchantment|land|permanent) you control, create a token that's a "
                r"copy of (?:it|that (?:creature|permanent|artifact|token))(?:, except (.+))?\.", re.I),
     lambda m: CopyEachToken(m[1].lower(), c) if (c := _copy_changes(m[2]) if m[2] else CopyChanges()) else None),
    (re.compile(rf"create a token that's a copy of {_SELF}, tapped and attacking\.", re.I), lambda m: CopyTokenAttacking()),
    (re.compile(r"that attacking player creates a tapped (.+? creature token(?: with [a-z, ]+)?) that's attacking that opponent\.",
                re.I), lambda m: _attacker_token("a " + m[1])),
    (re.compile(r"put one of them into your hand, put one of them on the bottom of your library, and exile one of them\.",
                re.I), lambda m: _SplitTop()),
    (re.compile(r"you may play the exiled card this turn\.", re.I), lambda m: _PlayTheExiledCard()),
    (re.compile(r"its controller manifests the top card of their library\.", re.I), lambda m: TargetControllerManifests()),
    (re.compile(r"manifest dread(?: (twice))?\.", re.I), lambda m: ManifestDread(2 if m[1] else 1)),
    (re.compile(rf"manifest dread, then attach {_SELF} to that creature\.", re.I), lambda m: ManifestDread(attach=True)),
    (re.compile(rf"manifest dread, then put {_N_FIXED} \+1/\+1 counters? on that creature\.", re.I), lambda m: ManifestDread(counters=_number(m[1]))),
    (re.compile(rf"shuffle your library\. as many times as you choose, you may exile the top card of your library\. if the "
                rf"total mana value of the cards exiled this way is {_N_FIXED} or less, you may cast any number of spells from among "
                r"those cards without paying their mana costs\.", re.I), lambda m: DanceWithCalamity(_number(m[1]))),
    (re.compile(r"target (player|opponent) loses half their life, rounded (up|down)\.", re.I),
     lambda m: TargetLoseHalfLife(m[1].lower(), m[2].lower() == "up")),
    (re.compile(rf"double the number of each kind of counter on any number of target {_PERMANENT_KIND}s\.", re.I),
     lambda m: DoubleAllCountersOnTargets(m[1].lower())),
    (re.compile(rf"double the number of {_COUNTER} on target {_PERMANENT_KIND}\.", re.I),
     lambda m: DoubleCountersOnTarget(_counter_name(m[1]), m[2].lower())),
    (re.compile(r"look at the top card of your library\. if it's an? (creature )?card of the chosen type, you may reveal it and put it "
                r"into your hand\.", re.I), lambda m: LookTopTakeChosen(bool(m[1]))),
    (re.compile(rf"return {_SELF} to the battlefield( tapped)?( under its owner's control)?\.", re.I),
     lambda m: ReturnSelfToBattlefield(tapped=bool(m[1]))),
    (re.compile(r"search your library for a ([A-Z][a-z]+) card and put it onto the battlefield tapped\. Then if an opponent controls "
                r"more lands than you, repeat this process once\. If you search your library this way, shuffle\.", re.I),
     lambda m: SearchLandWhileBehind(m[1].capitalize())),
    (re.compile(rf"(?:you may )?put an? {_CARD_TYPE} from your hand onto the battlefield( tapped)?\.", re.I),
     lambda m: PutFromHand(_card_kind(m[1]), bool(m[2]))),
    (re.compile(rf"return an? {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: ReturnChosen(_card_kind(m[1]), "hand")),
    (re.compile(r"take an extra turn after this one\.", re.I), lambda m: ExtraTurn()),
    (re.compile(r"you become the monarch\.", re.I), lambda m: BecomeMonarch()),
    (re.compile(rf"return (?:{_SELF}|this card) to its owner's hand\.", re.I), lambda m: ReturnSelfToHand()),
    (re.compile(r"tap all creatures your opponents control\.", re.I), lambda m: TapAll()),
    (re.compile(r"investigate\.", re.I), lambda m: CreateTokens(1, CLUE)),
    (re.compile(rf"{_VOTE_PREFIX}starting with you, each player votes for (\w+) or (\w+)\.", re.I),
     lambda m: VoteStart((m[1].lower(), m[2].lower()))),
    (re.compile(rf"{_VOTE_PREFIX}starting with you, each player votes for a nonland permanent you don't control\.", re.I),
     lambda m: VoteStart(None)),
    (re.compile(r"exile each permanent with the most votes or tied for most votes\.", re.I),
     lambda m: ExileMostVoted()),
    (re.compile(r"for each (\w+) vote, (.+)\.", re.I), lambda m: _vote_outcome("each", m[1], m[2], False)),
    (re.compile(r"(.+?) for each (\w+) vote and (.+?) for each (\w+) vote\.", re.I),
     lambda m: _two_vote_outcomes(m[1], m[2], m[3], m[4])),
    (re.compile(r"if (\w+) gets more votes( or the vote is tied)?, (.+)\.", re.I),
     lambda m: _vote_outcome("more", m[1], m[3], bool(m[2]))),
    (re.compile(r"you take the initiative\.", re.I), lambda m: TakeInitiative()),
    (re.compile(r"target player takes an extra turn after this one\.", re.I), lambda m: TargetExtraTurn()),
    (re.compile(r"after this (?:main )?phase, there is an additional combat phase( followed by an additional main phase)?\.",
                re.I), lambda m: ExtraCombat(bool(m[1]))),
    (re.compile(r"untap all creatures that attacked this turn\.", re.I), lambda m: UntapCreatures("attacked")),
    (re.compile(r"untap all creatures you control\.", re.I), lambda m: UntapCreatures("yours")),
    (re.compile(r"untap all (artifacts|lands|permanents|enchantments|nonland permanents) you control\.", re.I),
     lambda m: UntapAll(_PLURAL_KINDS[m[1].lower()])),
    (re.compile(rf"untap (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Untap(m[2].lower(), bool(m[1]))),
    (re.compile(rf"untap up to one target {_PERMANENT_KIND}\.", re.I), lambda m: Untap(m[1].lower(), optional_target=True)),
    (re.compile(rf"untap {_UP_TO} target {_PLURAL_KIND}\.", re.I), lambda m: _up_to(Untap, m)),
    (re.compile(rf"untap (?:it|{_SELF})\.", re.I), lambda m: UntapSource()),
    (re.compile(r"goad target (creature)\.", re.I), lambda m: Goad(m[1].lower())),
    (re.compile(r"goad (?:all creatures you don't control|each creature your opponents control)\.", re.I),
     lambda m: GoadAll()),
    (re.compile(rf"mill {_N} cards?\.", re.I), lambda m: Mill(_count(m[1]), "you")),
    (re.compile(rf"discard {_N} cards?( at random)?\.", re.I), lambda m: Discard(_count(m[1]), "you", bool(m[2]))),
    (re.compile(r"discard your hand\.", re.I), lambda m: Discard(None, "you")),
    (re.compile(rf"each (opponent|player) discards {_N} cards?( at random)?\.", re.I),
     lambda m: Discard(_count(m[2]), "each " + m[1].lower(), bool(m[3]))),
    (re.compile(r"each (opponent|player) discards their hand\.", re.I), lambda m: Discard(None, "each " + m[1].lower())),
    (re.compile(rf"target (player|opponent) discards {_N} cards?( at random)?\.", re.I),
     lambda m: TargetDiscard(_count(m[2]), m[1].lower(), bool(m[3]))),
    (re.compile(rf"each player draws {_N} cards?\.", re.I), lambda m: EachDraw(_count(m[1]))),
    (re.compile(r"each player discards their hand, then draws cards equal to the greatest number of cards a player "
                r"discarded this way\.", re.I), lambda m: DiscardHandsDrawGreatest()),
    (re.compile(rf"each player discards their hand, then draws {_N} cards?\.", re.I),
     lambda m: [Discard(None, "each player"), EachDraw(_count(m[1]))]),
    (re.compile(rf"draw {_N} cards?, then discard {_N} cards?\.", re.I),
     lambda m: [Draw(_count(m[1])), Discard(_count(m[2]), "you")]),
    (re.compile(rf"discard {_N} cards?, then draw {_N} cards?\.", re.I),
     lambda m: [Discard(_count(m[1]), "you"), Draw(_count(m[2]))]),
    (re.compile(r"target (player|opponent) reveals their hand\.", re.I), lambda m: RevealHand(m[1].lower())),
    (re.compile(r"you choose an? ((?:non[a-z]+(?:, non[a-z]+)*) )?card(?: with mana value (\d+) or less)? from it"
                r"(?: with mana value (\d+) or less)?\.", re.I),
     lambda m: ChooseFromHand(tuple(w.strip(",") for w in m[1].lower().replace("non", "").split()) if m[1] else (),
                              int(m[2] or m[3]) if m[2] or m[3] else None)),
    (re.compile(r"that player discards that card\.", re.I), lambda m: DiscardChosen()),
    (re.compile(rf"each (opponent|player) mills {_N} cards?\.", re.I),
     lambda m: Mill(_count(m[2]), "each " + m[1].lower())),
    (re.compile(rf"target (player|opponent) mills {_N} cards?\.", re.I),
     lambda m: TargetMill(_count(m[2]), m[1].lower())),
    (re.compile(rf"destroy all {_MASS_FILTERED}\.", re.I), lambda m: _mass_effect(DestroyAll, m)),
    (re.compile(r"(?:they|it|a creature destroyed this way) can't be regenerated\.", re.I), lambda m: CannotRegenerate()),
    (re.compile(rf"regenerate target {_PERMANENT_KIND}\.", re.I), lambda m: Regenerate(m[1].lower())),
    (re.compile(rf"regenerate {_SELF}\.", re.I), lambda m: RegenerateSource()),
    (re.compile(r"regenerate each creature you control\.", re.I), lambda m: RegenerateEach()),
    (re.compile(rf"exile all {_MASS_FILTERED}\.", re.I), lambda m: _mass_effect(ExileAll, m)),
    (re.compile(rf"{_SELF} deals {_N} damage to each (creature you don't control|creature your opponents control|creature and planeswalker your opponents control"
                rf"|creature|opponent|player)(?: {_RESTRICTION})?(?: and each (opponent|player))?\.", re.I), _damage_each),
    (re.compile(r"(?:each (opponent|player) gets|each (opponent|player) gets) (a|one|two|three) poison counters?\.", re.I),
     lambda m: GivePoison((m[1] or m[2]).lower(), _number(m[3]))),
    (re.compile(r"then each creature your opponents control gets -1/-1 until end of turn for each poison counter its controller has\.", re.I),
     lambda m: PoisonShrinksOpponentsCreatures()),
    (re.compile(rf"each (opponent|player) sacrifices (a|an) {_SACRIFICE_KIND} of their choice and gets a poison counter\.", re.I),  # Vraska's Fall
     lambda m: [EachSacrifices(m[1].lower(), m[3].lower(), 1), GivePoison(m[1].lower())]),
    (re.compile(rf"each (opponent|player) sacrifices (a|an|one|two|three) {_SACRIFICE_KIND}"
                r"( with the greatest power among creatures they control)?\.", re.I),
     lambda m: EachSacrifices(m[1].lower(), m[3].lower(), _count(m[2]), bool(m[4])) if m[4] is None or m[3].lower() == "creature" else None),
    (re.compile(rf"each (opponent|player) sacrifices (two|three|four|five) {_SACRIFICE_PLURAL}\.", re.I),
     lambda m: EachSacrifices(m[1].lower(), _PLURAL_SACRIFICE[m[3].lower()], _count(m[2]))),
    (re.compile(rf"each (opponent|player) sacrifices all {_SACRIFICE_PLURAL} they control\.", re.I),
     lambda m: EachSacrifices(m[1].lower(), _PLURAL_SACRIFICE[m[2].lower()], None)),
    (re.compile(rf"sacrifice all {_SACRIFICE_PLURAL} you control\.", re.I),
     lambda m: SacrificeAll(_PLURAL_SACRIFICE[m[1].lower()])),
    (re.compile(r"for each (creature|permanent) (?:destroyed|exiled) this way, its controller creates (.+)\.(\"?)", re.I),
     lambda m: _gift(_GiftMatch(m[2], m[3]))),
    (re.compile(r"(?:then )?create (.+) for each nontoken creature you controlled that was destroyed this way\.(\"?)", re.I),
     lambda m: _gift(_GiftMatch(m[1], m[2]), who="you", nontoken=True)),
    (re.compile(r"each player creates (.+) and puts a number of \+1/\+1 counters on it equal to the total power of (?:the )?"
                r"creatures they controlled that were exiled this way\.(\"?)", re.I),
     lambda m: _gift(_GiftMatch(m[1], m[2]), who="each player", power_counters=True)),
    (re.compile(r"sacrifice a creature\.", re.I), lambda m: SacrificeCreature()),
    (re.compile(rf"(?:you )?sacrifice (a|an|one|two|three) {_SACRIFICE_KIND}\.", re.I),
     lambda m: EachSacrifices("you", m[2].lower(), _count(m[1]))),
    (re.compile(rf"(?:you )?sacrifice (two|three|four|five) {_SACRIFICE_PLURAL}\.", re.I),
     lambda m: EachSacrifices("you", _PLURAL_SACRIFICE[m[2].lower()], _count(m[1]))),
    (re.compile(rf"sacrifice {_SELF} unless you return an untapped ({_LAND_TYPE}) you control to its owner's hand\.", re.I),
     lambda m: SacrificeUnlessReturnLand(m[1].capitalize())),
    (re.compile(rf"sacrifice {_SELF} unless you pay ((?:\{{[0-9WUBRGC]+\}})+)\.", re.I), lambda m: SacrificeUnlessPay(m[1])),
    (re.compile(r"you may play the exiled card without paying its mana cost if (.+)\.", re.I),
     lambda m: PlayExiledCard(c) if (c := _condition(m[1])) else None),
    (re.compile(r"Let X be (.+)\."), lambda m: DefineX(a) if (a := _amount(m[1])) else None),
    (re.compile(rf"target (player|opponent) sacrifices an? {_SACRIFICE_KIND}\.", re.I),
     lambda m: TargetSacrifices(m[1].lower(), m[2].lower())),
    (re.compile(rf"{_SELF} also deals {_N_FIXED} damage to that creature's controller\.", re.I), lambda m: DamageTargetsController(_number(m[1]))),
    (re.compile(r"target (player|opponent) sacrifices a creature with the greatest power among creatures they control\.", re.I),
     lambda m: TargetSacrifices(m[1].lower(), greatest=True)),
    (re.compile(r"exile target player's graveyard\.", re.I), lambda m: ExileGraveyard()),
    (re.compile(rf"put a ({_COUNTER}) on each of up to (two|three) target creatures\.", re.I),  # Elegant Rotunda
     lambda m: [PutCounters(1, _counter_name(m[2]), "creature", optional_target=True, distinct=n > 0) for n in range(_number(m[3]))]),
    (re.compile(rf"put {_N} {_COUNTER} on up to one target creature\.", re.I),  # Gideon, Ally of Zendikar's kin: a loyalty ability may pick no one
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), "creature", optional_target=True)),
    (re.compile(rf"put {_N} {_COUNTER} on target {_PERMANENT_KIND}\.", re.I),
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"put {_N} {_COUNTER} on target (attacking creature with lesser power)\.", re.I),  # Mentor
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"distribute {_N} {_COUNTER} among (?:one or two|one, two, or three|up to {_N}|any number of) (other )?(?:target )?"
                r"creatures( you control)?\.", re.I),
     lambda m: DistributeCounters(_count(m[1]), _counter_name(m[2]), "creature" + (" you control" if m[5] else ""), another=m[4] is not None)),
    (re.compile(rf"put {_N} {_COUNTER} on another target {_PERMANENT_KIND}\.", re.I),
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower(), another=True)),
    (re.compile(rf"put {_N} {_COUNTER} on each (creature|(?-i:[A-Z][a-z]+)(?: creature)?|artifact creature) you control\.", re.I),
     lambda m: PutCountersOnEach(_count(m[1]), _counter_name(m[2]), "" if m[3].lower() == "creature" else m[3].removesuffix(" creature").capitalize())),
    (re.compile(rf"put a {_COUNTER} on each (?:(white|blue|black|red|green) )?creature that entered this turn\.", re.I),
     lambda m: PutCountersOnEntered(_counter_name(m[1]), _COLOR_WORDS[m[2].lower()] if m[2] else "")),
    (re.compile(rf"put {_N} {_COUNTER} on {_SELF}\.", re.I),
     lambda m: PutCountersOnSource(_count(m[1]), _counter_name(m[2]))),
    (re.compile(rf"put {_N} {_COUNTER} on {_SELF} and it becomes renowned\.", re.I),  # Renown
     lambda m: [PutCountersOnSource(_count(m[1]), _counter_name(m[2])), BecomeRenowned()]),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} gains protection from the color of your choice until end of turn\."),
     lambda m: GrantProtection(m[1].lower())),
    (re.compile(rf"(?i:{_SELF}) gains protection from the color of your choice until end of turn\."),
     lambda m: GrantProtection(on_source=True)),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} {_CHANGE}"), lambda m: Pump(_modifier(m, 2), m[1].lower())),
    (re.compile(r"choose artifact or enchantment\. destroy all permanents of the chosen type\.", re.I),
     lambda m: DestroyAllOfChosenType(("artifact", "enchantment"))),
    (re.compile(r"choose an artifact or creature you control\. create a token that's a copy of it\.", re.I),
     lambda m: CopyChosenPermanent("artifact or creature you control")),
    (re.compile(r"double the (power|power and toughness) of each creature you control until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[1].lower(), "toughness" in m[1].lower(), each=True)),
    (re.compile(r"double the (power|power and toughness) of each ([A-Z][a-z]+) you control until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[1].lower(), "toughness" in m[1].lower(), each=True, subtype=m[2])),
    (re.compile(rf"until end of turn, double target {_PERMANENT_KIND}'s power X times\.", re.I),
     lambda m: DoubleStats(True, False, target=m[1].lower(), times="X")),
    (re.compile(rf"double the (power|power and toughness) of target {_PERMANENT_KIND} until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[1].lower(), "toughness" in m[1].lower(), target=m[2].lower())),
    (re.compile(rf"double target {_PERMANENT_KIND}'s (power|power and toughness) until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[2].lower(), "toughness" in m[2].lower(), target=m[1].lower())),
    (re.compile(rf"double (?:{_SELF}'s|its) (power|power and toughness) until end of turn\.", re.I),
     lambda m: DoubleStats("power" in m[1].lower(), "toughness" in m[1].lower(), on_source=True)),
    (re.compile(rf"creatures named {_SELF} can't be blocked this turn\.", re.I),
     lambda m: PumpNamed(Modifier(keywords=frozenset({CANT_BE_BLOCKED})))),
    (re.compile(r"shuffle any number of target cards from your graveyard into your library\.", re.I),
     lambda m: ShuffleIntoLibrary()),
    (re.compile(rf"target {_PERMANENT_KIND} can't be blocked this turn\.", re.I),
     lambda m: Pump(Modifier(keywords=frozenset({CANT_BE_BLOCKED})), m[1].lower())),
    (re.compile(rf"target {_PERMANENT_KIND} can't block this turn\.", re.I),
     lambda m: Pump(Modifier(keywords=frozenset({CANT_BLOCK})), m[1].lower())),
    (re.compile(rf"one or two target {_PLURAL_KIND} can't block this turn\.", re.I),
     lambda m: [Pump(Modifier(keywords=frozenset({CANT_BLOCK})), _PLURAL_KINDS[m[1].lower()] + _suffix(m[2])),
                Pump(Modifier(keywords=frozenset({CANT_BLOCK})), _PLURAL_KINDS[m[1].lower()] + _suffix(m[2]),
                     optional_target=True, distinct=True)]),
    (re.compile(rf"{_SELF} can't be blocked this turn\.", re.I),
     lambda m: PumpSource(Modifier(keywords=frozenset({CANT_BE_BLOCKED})))),
    (re.compile(rf"(?i:each other creature that's attacking one of your opponents) {_CHANGE}"),
     lambda m: PumpOtherAttackers(_modifier(m, 1))),
    (re.compile(rf"(?i:one or two target creatures each) {_CHANGE}"),
     lambda m: [Pump(_modifier(m, 1), "creature"), Pump(_modifier(m, 1), "creature", optional_target=True, distinct=True)]),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} gets? {_PT_X}(?: and gains? {_KEYWORDS})? until end of turn\."),
     lambda m: _pump_x(m[2], m[3], m[4], m[5], m[1].lower(), m[6])),
    (re.compile(rf"(?i:target) (creature(?: an opponent controls| you control)?) (?i:becomes) an? (\d+)/(\d+)"
                rf"(?: (?:white|blue|black|red|green|colorless))?(?: [A-Z][\w'-]*)*(?: creature)?(?: with {_KEYWORDS})?"
                r" until end of turn\."),
     lambda m: Pump(Modifier(0, 0, _keyword_list(m[4]) if m[4] else frozenset(), (int(m[2]), int(m[3]))), m[1].lower())),
    (re.compile(rf"target (creature(?: an opponent controls| you control)?) has base power and toughness (\d+)/(\d+)"
                r" until end of turn\.", re.I),
     lambda m: Pump(Modifier(0, 0, frozenset(), (int(m[2]), int(m[3]))), m[1].lower())),
    (re.compile(rf"(?i:(all creatures|creatures you control|creatures your opponents control)) get {_PT_X} until end of turn\."),
     lambda m: _pump_each_x(m)),
    (re.compile(rf"(?:(?i:until end of turn, ))?(?i:(creatures you control)) gain {_KEYWORDS} and get {_PT_X}(?: until end of turn)?\."),
     lambda m: dataclasses.replace(_pump_each_x_from(m[1], m[3], m[4], m[5], m[6]), keywords=_keyword_list(m[2]))),
    (re.compile(r"(?:Until end of turn, )?creatures your opponents control lose hexproof and shroud and can't have hexproof or shroud\."),
     lambda m: PumpEach(Modifier(keywords=frozenset({LOSES_HEXPROOF})), opponents=True)),
    (re.compile(rf"(?i:creatures your opponents control) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1), opponents=True)),
    (re.compile(rf"(?i:all creatures) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1), everyone=True)),
    (re.compile(rf"move (?:{_N_FIXED}|all|any number of) {_COUNTER} from target (creature) onto another target (creature)"
                r"( with the same controller)?\.", re.I),
     lambda m: [MoveCountersFrom(m[3].lower()),
                MoveCountersOnto("any" if m[0].lower().startswith("move any number") else _number(m[1]) if m[1] else None,
                                 _counter_name(m[2]), m[4].lower(), same_controller=bool(m[5]))]),
    (re.compile(rf"(?:Until end of turn, )(?:CARDNAME|this land) becomes an? {_ANIMATED}\.\"?"), lambda m: _animate(m, None)),
    (re.compile(rf"(?i:CARDNAME|this land) becomes an? {_ANIMATED} (?i:until end of turn)\.\"?"), lambda m: _animate(m, None)),
    (re.compile(rf"(?i:target) (land you control) becomes an? {_ANIMATED} (?i:until end of turn)\.\"?"),
     lambda m: _animate(m, m[1].lower(), 1)),
    (re.compile(r"it's still an? (land|artifact)\.", re.I), lambda m: StillALand()),
    (re.compile(rf"remove {_N} {_COUNTER} from target {_PERMANENT_KIND}\.", re.I),
     lambda m: RemoveCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"remove all {_COUNTER} from target {_PERMANENT_KIND}\.", re.I),
     lambda m: RemoveCounters(None, _counter_name(m[1]), m[2].lower())),
    (re.compile(rf"remove all counters from target {_PERMANENT_KIND}\.", re.I),
     lambda m: RemoveCounters(None, None, m[1].lower())),
    (re.compile(rf"put an? {_COUNTER} on enchanted creature\.", re.I), lambda m: PutCounterOnHost(1, _counter_name(m[1]))),
    (re.compile(r"have the base power and toughness of other creatures you control become equal to (?:CARDNAME's|its) "
                r"power and toughness until end of turn\.", re.I), lambda m: OthersBecomeAsBigAsSource()),
    (re.compile(rf"double the number of {_COUNTER} on (?:{_SELF})\.", re.I),
     lambda m: DoubleCountersOnSource(_counter_name(m[1]))),
    (re.compile(rf"double the number of {_COUNTER} on each creature you control\.", re.I),
     lambda m: DoubleCounters(_counter_name(m[1]))),
    (re.compile(r'(each opponent|each player) creates (.+)\.("?)', re.I), lambda m: _create_for_others(m)),
    (re.compile(r'target (player|opponent) creates (.+)\.("?)', re.I), lambda m: _create_for_others(m)),
    (re.compile(rf"(?i:{_SELF}) {_CHANGE}"), lambda m: PumpSource(_modifier(m, 1))),
    (re.compile(rf"(?i:{_SELF}) gets {_PT} until end of turn and can't be blocked this turn\."),  # Nimrodel Watcher
     lambda m: PumpSource(Modifier(_signed(m[1]), _signed(m[2]), frozenset({CANT_BE_BLOCKED})))),
    (re.compile(rf"(?i:{_SELF}) gets? {_PT_X} until end of turn\."),
     lambda m: (lambda x: PumpSourceX(x.power, x.toughness))(_pump_x(m[1], m[2], m[3], m[4], "creature"))),
    (re.compile(rf"(?i:creatures you control) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1))),
    (re.compile(rf"((?-i:[A-Z][a-z]+))s you control {_CHANGE}"), lambda m: PumpEach(_modifier(m, 2), subtype=m[1])),
    (re.compile(rf"(?i:non)-((?-i:[A-Z][a-z]+)) creatures you control {_CHANGE}"),
     lambda m: PumpEach(_modifier(m, 2), subtype="non-" + m[1])),  # Return of the Wildspeaker
    (re.compile(r'for each opponent, create (.+) that attack that opponent this turn if able\.("?)', re.I), _attacking_tokens),
    (re.compile(r"they gain haste until end of turn\.", re.I), lambda m: _TheyGainHaste()),
    (re.compile(r"that token attacks this combat if able\.", re.I), lambda m: _TokenAttacksThisCombat()),  # Howlsquad Heavy
    (re.compile(r"exile them at the beginning of the next end step\.", re.I), lambda m: _ExileThemLater()),
    (re.compile(r"sacrifice them at the beginning of the next end step\.", re.I), lambda m: _SacrificeThemLater()),
    (re.compile(r"create (.+?) tapped and attacking (\d+/\d+ [^.]*? creature tokens?)\.", re.I),  # Mobilize
     lambda m: (lambda parsed: TokensJoinAttack(parsed[0], parsed[1]) if parsed else None)(_token(f"{m[1]} {m[2]}"))),
    (re.compile(r"prevent all combat damage that would be dealt this turn\.", re.I), lambda m: PreventAllCombatDamage()),
    (re.compile(r"you win the game\.", re.I), lambda m: WinGame()),  # Revel in Riches
    (re.compile(rf"prevent the next {_NUM} damage that would be dealt to (any target|target creature|you|{_SELF}) this turn\.", re.I),
     lambda m: _prevent_next(_number(m[1]), m[2])),
    (re.compile(r"prevent all damage that would be dealt to target creature this turn\.", re.I),
     lambda m: PreventNext(ALL_DAMAGE, "creature")),
    (re.compile(r"prevent all combat damage that would be dealt to you this turn\.", re.I),
     lambda m: PreventCombatDamageToYou()),
    (re.compile(r'for each 1 damage prevented this way, create (.+)\.("?)', re.I), _token_per_prevented),
    (re.compile(r"(?:then )?you may choose a token you control\.", re.I), lambda m: _ChooseToken()),
    (re.compile(r"if you do, each other token you control becomes a copy of that token( until end of turn)?\.", re.I),
     lambda m: _OthersBecomeCopies(bool(m[1]))),
    (re.compile(r'(?i:create) (.+)\.("?)'), lambda m: _create(m, follows=False)),
    (re.compile(r'(?i:(?:its|that creature\'s) controller creates) (.+)\.("?)'), lambda m: _create(m, follows=True)),
    (re.compile(r"its controller gains life equal to its power\.", re.I), lambda m: TargetControllerGainsLifeEqualToPower()),
    (re.compile(r"that player may search their library for a land card with a basic land type, put it onto the battlefield, "
                r"then shuffle\.", re.I), lambda m: TargetControllerMayFetchBasicLand(tapped=False, typed=True)),  # Boseiju
    (re.compile(r"its controller may search their library for a basic land card, put (?:it|that card) onto the "
                r"battlefield( tapped)?, then shuffle\.", re.I), lambda m: TargetControllerMayFetchBasicLand(tapped=bool(m[1]))),
    (re.compile(r"search your library for a basic land card, put (?:it|that card) onto the battlefield tapped, "
                r"then shuffle\.", re.I),
     lambda m: FetchBasicLand()),
    (re.compile(r"search your library for a basic land card, put it onto the battlefield, then shuffle\.", re.I),
     lambda m: FetchBasicLand(tapped=False)),
]


_YOUR_ACTION = (rf"(?:draw (?:a card|{_N} cards)|gain {_N} life|lose {_N} life"
                r"|return (?:up to one )?target (?:[a-z]+ )?card from your graveyard to your hand"
                rf"|put {_N} \+1/\+1 counters? on a creature you control"
                r"|create an? (?:Treasure|Food|Clue) token)")  # Witch of the Moors; Breena; Lotho


def _you_do(phrase: str) -> str:
    """A sentence for something you do: "draw a card" -> "Draw a card.", "lose 1 life" -> "You lose 1 life." """
    return phrase[:1].upper() + phrase[1:] + "." if phrase.lower().startswith(("draw", "return", "create")) else f"You {phrase}."


_TIMES_X = [
    (r"\b(draws?) (?:a card|cards)\b", r"\1 X cards"),
    (r"\b(mills?) (?:a card|cards)\b", r"\1 X cards"),
    (r"\b(gains?|loses?) (?:1 )?life\b", r"\1 X life"),
    (r"\b(creates?) (?:a|an|one) (.+?) token\b", r"\1 X \2 tokens"),
    (r"\b(creates?) a number of (.+?) tokens\b", r"\1 X \2 tokens"),
    (r"\b(put) (?:a|one) (\+1/\+1) counter\b", r"\1 X \2 counters"),
    (r"\b(put) a number of (\+1/\+1) counters\b", r"\1 X \2 counters"),
    (r"\b(gets?) ([+\-\u2212])(\d+)/([+\-\u2212])(\d+)\b",  # "+2/+2" for each: +2X/+2X
     lambda m: f"{m[1]} {m[2]}{_times(m[3])}/{m[4]}{_times(m[5])}" if (m[3], m[5]) != ("0", "0") else m[0]),
]


def _times(number: str) -> str:
    """A number as a multiple of X: 0 -> "0", 1 -> "X", 2 -> "2X"."""
    return "0" if number == "0" else "X" if number == "1" else f"{number}X"


def _times_x(text: str) -> tuple[str, int]:
    """"draw a card" -> "draw X cards", "create a 1/1 ... token" -> "create X 1/1 ... tokens", ...;
    and how many replacements were made (0: the amount has nothing to apply to)."""
    total = 0
    parts = re.split(r'("[^"]*")', text)  # what a token says in quotes ("you gain 1 life") is not multiplied
    for pattern, replacement in _TIMES_X:
        for i in range(0, len(parts), 2):
            parts[i], n = re.subn(pattern, replacement, parts[i], flags=re.I)
            total += n
    return "".join(parts), total


def _clauses(sentence: str) -> list[str]:
    """Rewrite wording the templates don't cover into sentences they do: "X and you gain 1 life." is two
    sentences, as is "You draw two cards and lose 2 life."; "of their choice" and a leading "You draw" /
    "You create" add nothing."""
    sentence = sentence.replace(" of their choice.", ".").replace("each other player", "each opponent").replace("Each other player", "Each opponent")
    if m := re.fullmatch(r"(Draw cards equal to [^,]+), then (discard .+\.)", sentence):  # Greater Good
        return _clauses(m[1] + ".") + [m[2][:1].upper() + m[2][1:]]
    if m := re.fullmatch(r"(You (?:lose|gain) \d+ life) and (create .+)", sentence):  # Bitterblossom
        return [m[1] + ".", m[2][:1].upper() + m[2][1:]]
    if m := re.match(r"Then (?!if\b)(\w)", sentence):  # "Then creatures you control gain trample ..." (Blossoming Bogbeast): the order is the list's
        sentence = m[1].upper() + sentence[m.end():]
    sentence = re.sub(r"\b(draws?) (an|a|one|two|three) additional cards?\b",  # Well of Ideas, Midnight Oil
                      lambda m: f"{m[1]} {'a card' if m[2] in ('an', 'a', 'one') else m[2] + ' cards'}", sentence, flags=re.I)
    if m := re.fullmatch(r"(.*)\bhalf X (.+?), rounded (up|down)\.", sentence):  # The Goose Mother: "create half X Food tokens, rounded up."
        return _clauses(f"{m[1]}half X {m[3]} {m[2]}.")
    if _RETURN_UP_TO_POWER.fullmatch(sentence) or _RETURN_UP_TO_DAMAGE.fullmatch(sentence):  # one effect: X is looked at when the target is chosen
        return [sentence]
    if m := re.fullmatch(r"Create a number of (.+?) tokens? equal to (.+)\.", sentence, re.I):  # Gyome's Food
        return [f"Let X be {m[2]}.", f"Create X {m[1]} tokens."] if _amount(m[2]) else [sentence]
    if m := re.fullmatch(r"(.+), where X is (.+)\.", sentence):
        return [f"Let X be {m[2]}."] + _clauses(m[1] + ".") if _amount(m[2]) else [sentence]
    if m := re.fullmatch(r"(.+) (?:equal to|for each) (.+)\.", sentence):
        body, count = _times_x(m[1])
        if not (count and _amount(m[2])):
            return [sentence]
        clauses = _clauses(body + ".")
        # X is worked out when the clause that uses it is done, not before the ones ahead of it ("put a counter on it, then draw a card
        # for each counter on it" draws for the counter just put there).
        at = next((i for i, clause in enumerate(clauses) if re.search(r"\bX\b", clause)), 0)
        return clauses[:at] + [f"Let X be {m[2]}."] + clauses[at:]
    if m := re.fullmatch(r"For each opponent, you (create .+?)(\.\"?)", sentence):  # Eccentric Pestfinder's spell
        return _clauses(f"Create {m[1][len('create '):]}{m[2]} for each opponent.")
    if m := re.fullmatch(r"(Create .+ tokens?), then (put .+ counters? on it\.)", sentence):
        return [m[1] + ".", m[2].capitalize()]
    if m := re.fullmatch(r"(Create .+? tokens?(?: with [a-z, ]+)?), then populate\.", sentence, re.I):  # Horncaller's Chant
        return [m[1] + ".", "Populate."]
    sentence = re.sub(r"^You (draw|create) ", lambda m: m[1].capitalize() + " ", sentence)
    if m := re.fullmatch(rf"(Draw {_N} cards?) and ((?:create|remove) .+)\.", sentence):  # Big Score, Seize the Spoils, Midnight Oil
        return [m[1] + ".", m[3][:1].upper() + m[3][1:] + "."]
    if m := re.fullmatch(rf"(.+) and you ({_YOUR_ACTION})\.", sentence, re.I):
        return _clauses(m[1] + ".") + [_you_do(m[2])]
    if m := re.fullmatch(rf"(?:You )?(gain {_N} life) and (put .+ counters? on .+)\.", sentence):  # Dina, Essence Brewer
        return [_you_do(m[1]), m[3][:1].upper() + m[3][1:] + "."]
    if m := re.fullmatch(rf"(?:you )?(?P<first>{_YOUR_ACTION}) and (?P<second>{_YOUR_ACTION})\.", sentence, re.I):
        return [_you_do(m["first"]), _you_do(m["second"])]
    if m := re.fullmatch(r"(.+?), then (.+)\.", sentence):  # "Mill three cards, then return a creature card ..."
        first, second = m[1] + ".", m[2][:1].upper() + m[2][1:] + "."
        if _template(first) is not None and _template(second) is not None:
            return [first, second]
    return [sentence]


_DELAYED_TRIGGER = re.compile(r"(?:until (?:the )?end of (?:the turn|your next turn|turn), (whenever .+)|(whenever [^,]+?) this turn, (.+))", re.I)


def _delayed_trigger(sentence: str) -> CreateDelayedTrigger | None:
    """ "Until end of turn, whenever ..., ..." and "Whenever ... this turn, ...": the triggered ability the rest of the sentence
    is, set up as the spell or ability resolves. The wording of the trigger itself is the permanents' (effects/triggers.py)."""
    from .triggers import _trigger_part, remembered_ability

    if remembered := remembered_ability(sentence):
        return CreateDelayedTrigger((remembered[0],), when=remembered[1])
    match = _DELAYED_TRIGGER.fullmatch(sentence)
    if not match:
        return None
    body = match[1] or f"{match[2]}, {match[3]}"
    found = _trigger_part(body, body)
    return CreateDelayedTrigger(tuple(found), next_turn="your next turn" in sentence.lower()) if found else None


@lru_cache(maxsize=None)  # a sentence reads the same wherever it is: "Draw a card." is on thousands of cards (issue #441)
def _template(sentence: str) -> Any:
    """The effect of one sentence a template understands as written, or None. Effects are frozen, so the one read is shared."""
    for pattern, build in _TEMPLATES:
        match = pattern.fullmatch(sentence)
        effect = build(match) if match else None
        if effect is not None:
            return effect
    return _delayed_trigger(sentence)


def _merge_hand_discard(effects: list) -> list | None:
    """"Target opponent reveals their hand. You choose a nonland card from it. That player discards that card." becomes
    one TargetChooseDiscard; any one of the three sentences alone isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, RevealHand):
            if not (i + 2 < len(effects) and isinstance(effects[i + 1], ChooseFromHand)
                    and isinstance(effects[i + 2], DiscardChosen)):
                return None
            choose = effects[i + 1]
            merged.append(TargetChooseDiscard(effect.target, choose.excluded, choose.max_mv))
            i += 3
            continue
        if isinstance(effect, (ChooseFromHand, DiscardChosen)):
            return None
        merged.append(effect)
        i += 1
    return merged


def _merge_loot(effects: list) -> list | None:
    """"You may discard a card. If you do, draw a card." is one effect; either sentence alone isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        if isinstance(effects[i], _MayDiscard):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _IfYouDoDraw)):
                return None
            merged.append(MayDiscardThenDraw(effects[i + 1].draw, effects[i + 1].mill))
            i += 2
            continue
        if isinstance(effects[i], _MayRemoveCounter):
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _IfYouDoDraw)):
                return None
            merged.append(MayRemoveCounterThenDraw(effects[i].counter, effects[i + 1].draw))
            i += 2
            continue
        if isinstance(effects[i], _MaySacrifice):
            if i + 1 < len(effects) and isinstance(effects[i + 1], _IfYouDo):  # Springbloom Druid
                merged.append(MaySacrificeThen(effects[i].kind, effects[i + 1].effect))
                i += 2
                continue
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], _IfYouDoDraw)):
                return None
            merged.append(MaySacrificeThenDraw(effects[i].kind, effects[i + 1].draw))
            i += 2
            continue
        if isinstance(effects[i], _IfYouDoDraw):
            return None
        merged.append(effects[i])
        i += 1
    return merged


def _vote_outcome(kind: str, option: str, text: str, tie: bool) -> VoteOutcome | None:
    """What a vote does, read from the sentence's own clause; only for effects that need no target."""
    effects = _parse(_split_sentences(text[:1].upper() + text[1:] + "."))
    if not effects or any(target_kind(e) or binding(e) in CONTEXT_BINDINGS
                          for e in effects):
        return None
    return VoteOutcome(kind, option.lower(), tuple(effects), tie)


def _two_vote_outcomes(first: str, first_option: str, second: str, second_option: str) -> list | None:
    """"Each opponent sacrifices a creature for each death vote and discards a card for each taxes vote." The second
    part has no subject of its own: it shares the first's ("each opponent")."""
    subject = re.match(r"(each opponent|each player|you) ", first, re.I)
    if subject and not re.match(r"(each opponent|each player|you) ", second, re.I):
        second = f"{subject[1]} {second}"
    outcomes = [_vote_outcome("each", first_option, first, False), _vote_outcome("each", second_option, second, False)]
    return None if None in outcomes else outcomes


def _merge_votes(effects: list) -> list | None:
    """"Starting with you, each player votes for X or Y. For each X vote, ..." becomes one Vote, and the permanent vote
    one VoteToExile; a vote with no outcome, or outcomes about other words, isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, VoteStart) and effect.options is None:
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], ExileMostVoted)):
                return None
            merged.append(VoteToExile())
            i += 2
            continue
        if isinstance(effect, VoteStart) and effect.options is not None:
            outcomes = []
            i += 1
            while i < len(effects) and isinstance(effects[i], VoteOutcome):
                outcomes.append(effects[i])
                i += 1
            if not outcomes or any(o.option not in effect.options or o.kind != outcomes[0].kind for o in outcomes):
                return None
            merged.append(Vote(effect.options, tuple(outcomes)))
            continue
        if isinstance(effect, (VoteOutcome, ExileMostVoted)):
            return None
        merged.append(effect)
        i += 1
    return merged


def _parse(sentences: list[str]) -> list | None:
    effects = []
    for sentence in sentences:
        # A sentence a template already reads is taken as written; only the others are rewritten (_clauses).
        found = [effect] if (effect := _template(sentence)) is not None else [_template(c) for c in _clauses(sentence)]
        if None in found:
            return None
        for effect in found:  # one sentence can make several effects (a fight has two targets)
            effects += effect if isinstance(effect, list) else [effect]
    for i, effect in enumerate(effects):
        if isinstance(effect, _KickedInsteadTail):  # "that creature" is what the effect before it targets
            kind = target_kind(effects[i - 1]) if i else None
            about = re.sub(r"\bthat (?:creature|permanent)\b", f"target {kind}", effect.text) if kind else ""
            replaced = _parse(_split_sentences(about[:1].upper() + about[1:] + ".")) if about else None
            if not replaced:
                return None
            effects[i] = KickedReplaces(tuple(replaced))
        if isinstance(effect, KickedInstead) and not (i and hasattr(effects[i - 1], effect.field)):
            return None  # "instead" has to change the effect just before it
        if isinstance(effect, KickedReplaces) and not i:
            return None
    merged: list | None = _merge_no_regen(effects)
    for merge in (_merge_three_way, _merge_copy, _merge_control, _merge_impulse, _merge_votes, _merge_hand_discard, _merge_animate, _merge_mana_drain, _merge_exile, _merge_put_back, _merge_loot, _merge_conditional, _merge_drain, _merge_wipe_gift, _merge_reveal_top, _merge_token_counters, _merge_new_target, _merge_stun_self, _merge_stun, _merge_attacking_tokens, _merge_prevention, _merge_token_copies, _merge_target_copies):  # each returns None for a line it rejects
        if merged is None:
            return None
        merged = merge(merged)
    return merged


def _merge_impulse(effects: list) -> list | None:
    """"Look at the top five cards of your library. You may reveal a creature card from among them and put it into your
    hand. Put the rest on the bottom ..." becomes one Impulse; a look or take that isn't completed isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, LookAtTop) and i + 1 < len(effects) and isinstance(effects[i + 1], TakeFromTop):
            take = effects[i + 1]
            i += 2
            if take.card_type is not None or take.rest is None:  # the optional reveal, and "Put one of those cards into your hand.",
                kicked = i < len(effects) and isinstance(effects[i], KickedInstead)  # need the rest-on-the-bottom sentence (Consult the
                if not (i + kicked < len(effects) and isinstance(effects[i + kicked], RestOnBottom)):  # Star Charts: after its kicked clause)
                    return None
                del effects[i + kicked]
            merged.append(Impulse(effect.count, take.card_type, take.to, take.take, take.rest or "bottom"))
            continue
        if isinstance(effect, (LookAtTop, TakeFromTop, RestOnBottom)):
            return None
        merged.append(effect)
        i += 1
    return merged


def _merge_stun_self(effects: list) -> list:
    """"Whenever this creature attacks, put a stun counter on it.": with no earlier effect to follow, "it" is the creature itself."""
    merged: list = []
    for effect in effects:
        aimed = any(target_kind(e) or binding(e) in (SUBJECT, PLAYER) for e in merged)
        merged.append(PutStunOnSource(effect.count) if isinstance(effect, PutStunCounters) and not aimed else effect)
    return merged


def _merge_stun(effects: list) -> list | None:
    """"Tap up to two target creatures. Put a stun counter on each of them." is a stun counter after each tap; a lone "each of
    them" has nothing to refer to, so the line isn't understood."""
    merged: list = []
    for effect in effects:
        if not isinstance(effect, PutStunOnEach):
            merged.append(effect)
            continue
        taps: list = []
        while merged and isinstance(merged[-1], Tap):
            taps.insert(0, merged.pop())
        if not taps:
            return None
        for tap in taps:
            merged += [tap, PutStunCounters(effect.count)]
    return merged


def _singular(word: str) -> str:
    if word.endswith("ves") and word.lower().removesuffix("ves") in ("el", "wol", "dwar", "werewol"):  # Elves, Wolves, Dwarves, Werewolves
        return word.removesuffix("ves") + "f"
    return word if word.endswith("ss") or word.lower() == "plains" else word.removesuffix("s")


_CONDITIONS = [
    (re.compile(r"each player has no cards in hand"), lambda m: Condition("all_hands_empty")),
    (re.compile(r"creatures you control have total power (\d+) or greater"), lambda m: Condition("creature_power_at_least", int(m[1]))),
    (re.compile(r"you control a creature with power (\d+) or greater"), lambda m: Condition("creature_with_power", int(m[1]))),
    (re.compile(r"you created a token this turn"), lambda m: Condition("created_token")),
    (re.compile(r"you attacked this turn"), lambda m: Condition("attacked_this_turn")),  # Raid
    (re.compile(r"you control your commander"), lambda m: Condition("control_commander")),  # Lieutenant
    (re.compile(r"a library has (twenty|\d+) or fewer cards in it"),
     lambda m: Condition("any_library_at_most", 20 if m[1] == "twenty" else int(m[1]))),
    (re.compile(r"an opponent was dealt (\d+) or more damage this turn"), lambda m: Condition("opponent_damage_at_least", int(m[1]))),
    (re.compile(r"an opponent has (one|two|three|four|five|six|seven|eight|nine|\d+) or more poison counters?"),  # Corrupted
     lambda m: Condition("opponent_poison_at_least", _number(m[1]))),
    (re.compile(rf"you attacked with {_N_FIXED} or more creatures this turn"), lambda m: Condition("attacked_with_at_least", _number(m[1]))),
    (re.compile(r"a card left your graveyard this turn"), lambda m: Condition("graveyard_left")),
    (re.compile(r"a land entered the battlefield under your control this turn"), lambda m: Condition("land_entered")),
    (re.compile(r"you control a prime number of lands"), lambda m: Condition("lands_prime")),
    (re.compile(r"you gained life this turn"), lambda m: Condition("gained_life")),
    (re.compile(rf"you(?:'ve)? gained {_N_FIXED} or more life this turn"), lambda m: Condition("gained_life_at_least", _number(m[1]))),
    (re.compile(rf"{_N_FIXED} or more creatures died this turn"), lambda m: Condition("creatures_died", _number(m[1]))),
    (re.compile(r"an opponent controls more lands than you"), lambda m: Condition("opponent_more_lands")),
    (re.compile(rf"X is {_N_FIXED} or more"), lambda m: Condition("x_at_least", _number(m[1]))),
    (re.compile(r"this card is in your graveyard"), lambda m: Condition("in_graveyard")),
    (re.compile(r"there is an instant card and a sorcery card in your graveyard"), lambda m: Condition("instant_and_sorcery_in_graveyard")),  # Flow State
    (re.compile(r"that player controls more lands than you"), lambda m: Condition("player_more_lands")),
    (re.compile(r"an opponent controls more creatures than you"), lambda m: Condition("opponent_more_creatures")),
    (re.compile(rf"that spell's mana value is {_N_FIXED} or greater"), lambda m: Condition("spell_mv_at_least", _number(m[1]))),
    (re.compile(rf"that creature has power {_N_FIXED} or greater"), lambda m: Condition("target_power_at_least", _number(m[1]))),
    (re.compile(r"you've cast an? (instant or sorcery spell|creature spell|noncreature spell|spell) this turn"),
     lambda m: Condition("cast_this_turn", what=m[1])),
    (re.compile(rf"you control {_N_FIXED} or more (white|blue|black|red|green) permanents"),
     lambda m: Condition("control_color_at_least", _number(m[1]), m[2])),
    (re.compile(rf"you control {_N_FIXED} or more ([A-Za-z]+)"),
     lambda m: Condition("control_at_least", _number(m[1]), _singular(m[2]))),
    (re.compile(r"your speed is 4"), lambda m: Condition("max_speed")),  # Max speed
    (re.compile(r"you control no creatures with ([a-z]+)"), lambda m: Condition("control_none_keyword", what=m[1])),
    (re.compile(r"you control no ([A-Za-z]+)"), lambda m: Condition("control_none", what=_singular(m[1]))),
    (re.compile(r"you don't control an? ([A-Za-z]+) creature token"), lambda m: Condition("control_none_token", what=m[1])),
    (re.compile(r"you control an? ([A-Za-z]+) or an? ([A-Za-z]+)"), lambda m: Condition("control_at_least", 1, f"{m[1]} or {m[2]}")),
    (re.compile(r"you control an? ([A-Za-z]+)"), lambda m: Condition("control_at_least", 1, _singular(m[1]))),
    (re.compile(r"it's your turn"), lambda m: Condition("your_turn")),
    (re.compile(r"it's not a token"), lambda m: Condition("source_not_token")),
    (re.compile(r"you control no other creatures"), lambda m: Condition("control_no_other", what="creature")),
    (re.compile(r"that player didn't cast an? ([a-z]+) spell this turn"), lambda m: Condition("player_cast_none", what=m[1])),
    (re.compile(rf"that player has {_N_FIXED} or fewer cards in hand"), lambda m: Condition("player_hand_at_most", _number(m[1]))),
    (re.compile(rf"(?:{_SELF}) has no {_COUNTER} on it"), lambda m: Condition("source_no_counters", what=_counter_name(m[1]))),
    (re.compile(rf"(?:it|{_SELF}) has {_N_FIXED} or more {_COUNTER} on it"),
     lambda m: Condition("source_counters_at_least", _number(m[1]), _counter_name(m[2]))),
    (re.compile(r"you're the monarch"), lambda m: Condition("monarch")),
    (re.compile(rf"you have {_N_FIXED} or more cards in hand"), lambda m: Condition("hand_at_least", _number(m[1]))),
    (re.compile(r"you have no cards in hand"), lambda m: Condition("hand_none")),
    (re.compile(rf"(?:{_SELF}|he|she) was kicked(?: with its ({_MANA_SYMBOLS}) kicker)?"),
     lambda m: Condition("kicked", what=m[1] or "")),
    (re.compile(r"you have the city's blessing"), lambda m: Condition("citys_blessing")),
    (re.compile(rf"{_SELF} isn't prepared"), lambda m: Condition("not_prepared")),
    (re.compile(r"(?:it|that creature) has greater power or toughness than (?:this creature|CARDNAME)"), lambda m: Condition("subject_greater")),
    (re.compile(rf"{_SELF} isn't renowned"), lambda m: Condition("not_renowned")),
    (re.compile(r"this spell was foretold"), lambda m: Condition("foretold")),
    (re.compile(r"you didn't cast a spell this turn"), lambda m: Condition("no_spell_cast_turn")),
    (re.compile(r"there are four or more card types among cards in your graveyard"), lambda m: Condition("delirium")),
    (re.compile(r"each player has (\d+) or less life"), lambda m: Condition("each_life_at_most", int(m[1]))),
    (re.compile(rf"{_SELF} is equipped"), lambda m: Condition("source_equipped")),
    (re.compile(r"no spells were cast last turn"), lambda m: Condition("no_spells_last_turn")),
    (re.compile(r"a player cast two or more spells last turn"), lambda m: Condition("two_spells_last_turn")),
    (re.compile(r"it's (day|night)"), lambda m: Condition(m[1])),
    (re.compile(rf"{_SELF} is tapped"), lambda m: Condition("source_tapped")),
    (re.compile(r"you control no other ([A-Za-z]+)"), lambda m: Condition("control_no_other", what=_singular(m[1]))),
    (re.compile(r"you cast it"), lambda m: Condition("cast_it")),
    (re.compile(r"a modified creature died under your control this turn"), lambda m: Condition("modified_died")),
    (re.compile(rf"{_N_FIXED} or more of those creatures are attacking you and/or planeswalkers you control"),
     lambda m: Condition("attackers_at_least", _number(m[1]))),
    (re.compile(r"none of those creatures attacked you"), lambda m: Condition("attackers_at_most", 0)),
    (re.compile(r"that opponent has more life than another of your opponents"), lambda m: Condition("defender_more_life")),
    (re.compile(r"you were the monarch as the turn began"), lambda m: Condition("monarch_at_turn_start")),
    # Eminence: the ability only works from those two zones, which is where the game looks for it.
    (re.compile(rf"{_SELF} is in the command zone or on the battlefield"), lambda m: Condition("eminence")),
    (re.compile(rf"(?:there are {_N_FIXED} or more cards in your graveyard|{_N_FIXED} or more cards are in your graveyard)"),
     lambda m: Condition("graveyard_at_least", _number(m[1] or m[2]), "card")),
    (re.compile(r"an opponent was dealt noncombat damage this turn"), lambda m: Condition("opponent_dealt_noncombat_damage")),
    (re.compile(r"an opponent lost life this turn"), lambda m: Condition("opponent_lost_life")),  # Fireglass Mentor
    (re.compile(rf"there are {_N_FIXED} or more ([a-z]+(?: and/or [a-z]+)?) cards in your graveyard"),
     lambda m: Condition("graveyard_at_least", _number(m[1]), m[2].replace(" and/or ", " or "))),
    (re.compile(rf"a player has {_N_FIXED} or fewer cards in hand"), lambda m: Condition("any_hand_at_most", _number(m[1]))),
    (re.compile(r"an opponent has more cards in hand than you"), lambda m: Condition("opponent_more_cards")),
    (re.compile(rf"an opponent has {_N_FIXED} or less life"), lambda m: Condition("opponent_life_at_most", _number(m[1]))),
]


def _condition(text: str) -> Condition | None:
    for pattern, build in _CONDITIONS:
        if m := pattern.fullmatch(text):
            return build(m)
    first, _, rest = text.partition(" and ")  # "if A and B": both must hold (Zimone)
    while rest:
        if (head := _condition(first)) is not None and (tail := _condition(rest)) is not None:
            return dataclasses.replace(head, also=tail)
        more, _, rest = rest.partition(" and ")
        first = f"{first} and {more}"
    return None


_SPELL_MASTERY = re.compile(r"^Spell mastery \u2014 ")  # the condition stays in the sentence; the ability word is only a label


_SPELL_COLORS = re.compile(r"the number of colors that spell is", re.I)  # Mana Cannons


# --- the sentences that only qualify the effect before them (follow.py) ---------------------------------------------------------------
# (here, after every class they name, since each is built as the module loads; `_parse` runs them in the order it lists them)

# "Copy target instant or sorcery spell. You may choose new targets for the copy." is one effect. The second sentence on its own has no
# copy to refer to, so the line isn't understood.
_merge_copy = Follows(Follow(NewTargets, (CopySpell, CopyTriggeringSpell, CopyTriggeredAbility, CopySpellTimes),
                             lambda previous, marker: dataclasses.replace(previous, new_targets=True) if hasattr(previous, "new_targets") else previous),  # (CopySpellTimes's copies always may)
                      Follow(_TwiceFromGraveyard, CopySpell, set_fields(twice_from_graveyard=lambda m: True)))


# Mana Drain's second sentence belongs to the Counter before it, and Chaos Warp's to its ChaosWarp; alone they aren't understood.
_merge_mana_drain = Follows(Follow(_ChaosPut, ChaosWarp), Follow(_DelayedMana, Counter, set_fields(delayed_mana=lambda m: True)))


# "... put them back in any order. You may shuffle." is one effect; "You may shuffle." alone isn't understood.
_merge_put_back = Follows(Follow(_MayShuffle, PutBackTop, set_fields(shuffle=lambda m: True)))


# "Each opponent loses X life. You gain life equal to the life lost this way." is one effect.
_merge_drain = Follows(Follow(_GainLifeLost, OpponentsLoseLife, lambda previous, marker: Drain(previous.amount)))


# "Change the target of target spell that targets only a player. The new target must be a player." is one effect; a lone "The new target
# must be ..." has nothing to refer to, so the line isn't understood.
_merge_new_target = Follows(Follow(NewTargetMustBe, ChangeTarget, set_fields(to=lambda m: m.kind), fits=lambda previous, marker: not previous.to))


# "Destroy all creatures. They can't be regenerated." becomes one destroy effect that skips regeneration.
_merge_no_regen = Follows(Follow(CannotRegenerate, (Destroy, DestroyAll), set_fields(no_regen=lambda m: True), strict=False))


# Threaten: "Gain control of target creature until end of turn. Untap that creature. It gains haste until end of turn." is one effect. A
# lone "Untap that creature." has nothing to refer to, so the line isn't understood; the haste sentence is an effect of its own anywhere else.
_merge_control = Follows(
    Follow(UntapThat, GainControl, set_fields(untap=lambda m: True)),
    Follow(PumpSource, GainControl, set_fields(haste=lambda m: True), strict=False,
           fits=lambda previous, marker: previous.untap and marker.modifier.keywords == frozenset({"haste"})
           and marker.modifier.power == marker.modifier.toughness == 0))


# Counter + "exile it instead" is one Counter(exile); Exile + "return it at the beginning of the next end step" is one Flicker; ExileTop +
# "you may play it" is one ExileTop(play). A leftover second half isn't understood.
_merge_exile = Follows(
    Follow(ExileInstead, Counter, set_fields(exile=lambda m: True)),
    Follow(ReturnLater, Exile, lambda previous, marker: Flicker(previous.target, "end_step", marker.to, marker.under_owner, previous.another)),
    Follow(PlayExiled, ExileTop, set_fields(play=lambda m: m.until), fits=lambda previous, marker: not previous.play),
    Follow(_ChooseOneOfThem, ExileTop, set_fields(choose_one=lambda m: True), fits=lambda previous, marker: previous.count != 1 and not previous.play))


_COPY_SENTENCES = (CopyToken, CopySubjectToken, CopyHostToken, CopySelfToken, CopyEachToken)  # "Create a token that's a copy of ..."


_CONDITIONAL = Follows(
    Follow(_InsteadDraw, Draw, set_fields(more=lambda m: m.count, more_if=lambda m: m.condition)),
    Follow(_InsteadTake, Impulse, set_fields(more=lambda m: m.count, more_if=lambda m: m.condition),
           fits=lambda previous, marker: previous.card_type is None and previous.rest == "bottom"),
    Follow(_InsteadMana, AddMana, set_fields(more=lambda m: m.units, more_if=lambda m: m.condition)),
    Follow(_ExileTokenAtEnd, (CreateTokens, *_COPY_SENTENCES), set_fields(exile_at_end=lambda m: True)),
    Follow(_InsteadTokens, CreateTokens, set_fields(more=lambda m: m.count, more_if=lambda m: m.condition)),
    Follow(_UntapThoseLands, RevealLands, set_fields(untap_if=lambda m: m.condition)),
    Follow(_UntapThatLand, FetchBasicLand, set_fields(untap_if=lambda m: m.condition)),
    Follow(_ManaForEachDestroyed, DestroyAll, set_fields(mana_each=lambda m: m.options)),
    Follow(_PutFromAmongThem, Mill, set_fields(put=lambda m: m.kind)),
    Follow(_ThatAlsoGains, Pump, lambda previous, marker: dataclasses.replace(
        previous, modifier=dataclasses.replace(previous.modifier, keywords=previous.modifier.keywords | marker.keywords))),
    Follow(_TheyGain, (PutCountersOnEach, PutCountersOnEachUpToX), set_fields(grant=lambda m: m.keywords)),
    Follow(_RecallAttachment, CreateTokens, lambda previous, marker: CreateTokenWithGraveyardAttachment(previous.token),
           fits=lambda previous, marker: previous.count == 1),
    Follow(_AttachItToToken, CreateTokens, lambda previous, marker: CreateTokenAttachSubject(previous.token),
           fits=lambda previous, marker: previous.count == 1),
    Follow(_PopulatedTokenRider, (Populate, *_COPY_SENTENCES), lambda previous, marker: dataclasses.replace(
        previous, haste=previous.haste or marker.haste, sacrifice_at_end=previous.sacrifice_at_end or marker.sacrifice)),
    Follow(_ItHas, CreateTokens, lambda previous, marker: dataclasses.replace(
        previous, token=dataclasses.replace(previous.token, oracle_text=marker.ability)),
           fits=lambda previous, marker: not previous.token.oracle_text),
    # The riders of a copy sentence (see `finish_copies`). "They gain haste" and "exile/sacrifice them" also follow attacking tokens
    # (_merge_attacking_tokens) and "exile those tokens" Twinflame's targets (_merge_target_copies), so those rows are not strict.
    Follow(_TokenHasHaste, _COPY_SENTENCES, lambda previous, marker: dataclasses.replace(
        previous, changes=dataclasses.replace(previous.changes or CopyChanges(), keywords=(previous.changes or CopyChanges()).keywords + ("haste",)))),
    Follow(_TokenGainsHaste, _COPY_SENTENCES, set_fields(haste=lambda m: True)),
    Follow((_TheyGainHaste, _ItGains), _COPY_SENTENCES, set_fields(haste=lambda m: True), strict=False,  # "It gains haste until end of turn."
           fits=lambda previous, marker: getattr(marker, "keywords", frozenset({"haste"})) == frozenset({"haste"})),
    Follow(PumpSource, _COPY_SENTENCES, set_fields(haste=lambda m: True), strict=False,  # "It gains haste until end of turn."
           fits=lambda previous, marker: marker.modifier.keywords == frozenset({"haste"}) and marker.modifier.power == marker.modifier.toughness == 0),
    Follow((_ExileThoseTokens, _ExileThemLater), _COPY_SENTENCES, set_fields(exile_at_end=lambda m: True), strict=False),
    Follow(_SacrificeThemLater, _COPY_SENTENCES, set_fields(sacrifice_at_end=lambda m: True), strict=False),
    # Lorehold Archivist's spell, The Scarab God: "Exile target creature card from a graveyard. Create a token that's a copy of it."
    Follow(CopySubjectToken, ExileFromGraveyard, lambda previous, marker: dataclasses.replace(previous, copy_token=True, copy_changes=marker.changes),
           strict=False, fits=lambda previous, marker: marker.count == 1 and not (marker.haste or marker.sacrifice_at_end or marker.exile_at_end)),
    Follow(_IfYouDo, ExileOwnGraveyard, set_fields(then=lambda m: m.effect)),
    Follow(_IfExiledThen, ExileFromGraveyard, set_fields(if_type=lambda m: m.card_type, then=lambda m: m.effect)),
)
