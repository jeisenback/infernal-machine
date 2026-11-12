"""Deck composition: how many cards of each role a Commander deck holds, against the Command Zone's deckbuilding template.

    python -m infernal_machine.composition DECKLIST

The template is the one from The Command Zone's episode 658, "Commander Deckbuilding Template for the New Era" (February 2025): about
38 lands, 10 ramp, 12 card advantage, 12 targeted disruption and 6 mass disruption, the rest of the 99 for the deck's own plan. The
numbers are a starting point, not a rule, and one card may fill several roles (a creature that draws and ramps counts for both).

A card's roles are read from the effects the engine parsed from it, not from words in its text, so "destroy target creature you control"
is not removal and a land that taps for mana is a land, not ramp:

- **ramp**: a nonland permanent with a mana ability; a land search that puts lands onto the battlefield; Treasure tokens.
- **card advantage**: drawing cards (yours, or a target player's), impulse draw (exile the top cards and play them), look at the top
  cards and take some.
- **targeted disruption**: destroying, exiling or bouncing a permanent the card targets (not one you control), damage to a creature or
  "any target", counterspells, a targeted -X/-X, an opponent sacrificing a creature.
- **mass disruption**: destroying, exiling or bouncing all of a kind, damage to each creature, each player sacrificing all of a kind,
  -X/-X to every creature or to the opponents' creatures.

Only the effects the engine understands are seen: a card with a line it can't read is listed apart and given no role (a land is still a
land). Its roles may be missing, so the counts are a floor.
"""

from __future__ import annotations

import dataclasses
import io
import sys
from dataclasses import dataclass, field

from .cards import Card, Deck
from .effects import activated_abilities, is_mana_ability, rules_lines, spell_effects, triggered_abilities
from .effects.targets import target_kind
from .report import unsupported_lines

RAMP, DRAW, TARGETED, MASS = "ramp", "card advantage", "targeted disruption", "mass disruption"
ROLES = (RAMP, DRAW, TARGETED, MASS)
TEMPLATE = {"lands": 38, RAMP: 10, DRAW: 12, TARGETED: 12, MASS: 6}  # The Command Zone, episode 658 (February 2025)
SOURCE = "The Command Zone, episode 658, \"Commander Deckbuilding Template for the New Era\" (2025)"

_DRAW = {"Draw", "TargetDraw", "TargetDrawDiscard", "TargetDrawLose", "TargetDrawXPlusCasts", "YouAndTargetDraw", "DrawUnlessFromHand",
         "DrawOrCountersByPower", "Impulse", "ExileTop", "DelayedDraw", "MayDiscardThenDraw", "MaySacrificeThenDraw", "ThreeWaySplit",
         "PlayersLoseSacrificeAddManaDraw"}
_RAMP = {"FetchBasicLand", "RevealLands"}  # lands onto the battlefield (Animist's Awakening)
_SPOT = {"Destroy", "Exile", "ReturnToHand", "DestroyUpToX", "DestroyX", "ExileX", "ExileUntilLeaves"}  # a permanent it targets, taken away
_TARGETED = {"Counter", "CounterAbility", "ChaosWarp", "Fight", "EachSacrificesThenReturn", "PlayersLoseSacrificeAddManaDraw"}
_MASS = {"DestroyAll", "ExileAll", "ReturnAllToHand", "SacrificeAll", "DestroyAllOfChosenType", "ExileAttackers", "TragicArrogance",
         "EachDamagesItself", "VowCounters"}
_DAMAGE_TARGETS = ("any", "creature", "planeswalker", "creature or planeswalker")


def _effects(effect: object) -> list[object]:
    """The effect and every effect it wraps (the branches of an if, the modes of a modal spell, what a "may pay" buys, ...)."""
    found = [effect]
    if dataclasses.is_dataclass(effect) and not isinstance(effect, type):
        for f in dataclasses.fields(effect):
            value = getattr(effect, f.name)
            for item in value if isinstance(value, (tuple, list)) else (value,):
                if hasattr(item, "resolve"):
                    found += _effects(item)
                elif isinstance(item, (tuple, list)):  # Modal's modes: a tuple of effect tuples
                    found += [e for inner in item if hasattr(inner, "resolve") for e in _effects(inner)]
    return found


def _all_effects(card: Card) -> list[object]:
    """Every effect of the card's triggered and activated abilities and of the spell, and of its other half (an Adventure, a split card)."""
    effects: list[object] = _all_effects(card.alternate) if card.alternate is not None else []
    for ability in triggered_abilities(card):
        effects += ability.effects
    for ability in activated_abilities(card):
        effects += ability.effects
    if "Instant" in card.type_line or "Sorcery" in card.type_line:
        effects += spell_effects(card) or []
    return effects


def _theirs(target: str | None) -> bool:
    """A target that can be an opponent's permanent (or spell): not "... you control"."""
    return bool(target) and "you control" not in str(target)


def _shrinks(modifier: object) -> bool:
    return getattr(modifier, "toughness", 0) < 0


def roles(card: Card) -> set[str]:
    """The template roles `card` fills, by the effects the engine read from it (see the module's docstring)."""
    found: set[str] = set()
    if "Land" not in card.type_line and any(is_mana_ability(line) for line in rules_lines(card)):
        found.add(RAMP)
    for effect in [e for top in _all_effects(card) for e in _effects(top)]:
        kind, target = type(effect).__name__, target_kind(effect)
        if kind == "SearchForLands" and getattr(effect, "battlefield", False) or kind in _RAMP \
                or kind == "PutFromHand" and getattr(effect, "kind", "") == "land" \
                or kind == "SearchLibrary" and getattr(effect, "to", "") == "battlefield" and "land" in getattr(effect, "card_type", "") \
                or kind == "CreateTokens" and getattr(getattr(effect, "token", None), "name", "") == "Treasure":
            found.add(RAMP)
        if kind in _DRAW:
            found.add(DRAW)
        if kind in _SPOT and _theirs(target) or kind in _TARGETED or kind == "Damage" and target in _DAMAGE_TARGETS \
                or kind == "Pump" and _shrinks(getattr(effect, "modifier", None)) and _theirs(target) \
                or kind == "EachSacrifices" and getattr(effect, "who", "") in ("opponent", "target opponent", "target player"):
            found.add(TARGETED)
        if kind in _MASS or kind == "DamageEach" and getattr(effect, "creatures", False) \
                or kind in ("PumpEach", "PumpEachX") and (getattr(effect, "everyone", False) or getattr(effect, "opponents", False)) \
                and (_shrinks(getattr(effect, "modifier", None)) if kind == "PumpEach" else getattr(effect, "toughness", 0) < 0):
            found.add(MASS)
    return found


@dataclass
class Composition:
    lands: list[str] = field(default_factory=list)
    roles: dict[str, list[str]] = field(default_factory=lambda: {role: [] for role in ROLES})
    plan: list[str] = field(default_factory=list)  # read, but in no role: the deck's own plan
    unread: list[str] = field(default_factory=list)  # a line the engine can't read: no role given

    def count(self, role: str) -> int:
        return len(self.lands) if role == "lands" else len(self.roles[role])


def analyze_composition(deck: Deck) -> Composition:
    """The roles of the 99 (the main deck: the commander is not counted, as the template counts the 99)."""
    result = Composition()
    for card in deck.main:
        if "Land" in card.type_line:
            result.lands.append(card.name)
            continue
        if unsupported_lines(card):
            result.unread.append(card.name)
            continue
        found = roles(card)
        for role in found:
            result.roles[role].append(card.name)
        if not found:
            result.plan.append(card.name)
    return result


def format_composition(result: Composition) -> str:
    rows = [f"{'role':<20} {'have':>4} {'template':>8}"]
    for role in ("lands", *ROLES):
        have, want = result.count(role), TEMPLATE[role]
        note = f"  {want - have} short" if have < want else ""
        rows.append(f"{role:<20} {have:>4} {want:>8}{note}")
    rows.append(f"{'plan (other)':<20} {len(result.plan):>4}")
    if result.unread:
        rows.append(f"{'not read':<20} {len(result.unread):>4}  (no role given: the counts above are a floor)")
    rows.append("")
    rows += [f"{role}: {', '.join(sorted(names))}" for role, names in result.roles.items() if names]
    if result.unread:
        rows.append(f"not read: {', '.join(sorted(result.unread))}")
    rows.append(f"\nTemplate: {SOURCE}. A card can fill several roles.")
    return "\n".join(rows)


def main(argv: list[str]) -> int:
    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) != 2:
        print("usage: python -m infernal_machine.composition DECKLIST", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(".cache/oracle_bulk.json"))
    print(format_composition(analyze_composition(deck)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
