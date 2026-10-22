"""Which cards in a deck the engine can't fully play yet, grouped by what's missing.

Run it on a decklist file (cards are fetched from Scryfall and cached):

    python -m infernal_machine.report deck.txt
"""

from __future__ import annotations

import io
import re
import sys
from collections import defaultdict
from dataclasses import dataclass

from .analysis import is_land
from .cards import Card, Deck
from .companion import CONDITIONS as COMPANION_CONDITIONS
from .effects import (PROTECTION, activated_abilities, attached_abilities, is_casting_cost_line, is_cost_reduction_line,
                      is_clone_line, is_replacement_line, is_control_aura_line, is_cycling_line, is_enchant_line, is_granting_line, is_group_mana_grant_line, is_cast_keyword_line, is_cumulative_upkeep_line, is_echo_line, is_reanimation_aura_line, is_enters_prepared_line, is_overload_line, overloaded_effects, is_extra_vote_line, is_graveyard_permission_line, is_graveyard_permit_line, is_library_top_line, is_no_max_hand_line, is_cda_line, is_hand_by_counters_line, is_enters_tapped_line, is_enters_with_counters, is_choose_color_line, is_optional_untap_line, is_station_line, is_hand_ability_line, is_mana_ability, is_modal_header,
                      is_additional_mana_line, is_haste_abilities_line, is_prevention_line, is_restricted_mana_line, is_tap_mana_line, is_rules_static_line, is_choose_type_line, is_chosen_self_line, is_x_discount_line, is_attack_tax_line, is_quest_untap_line, is_combat_restriction_line, is_opening_hand_line, is_return_exiled_line, is_ward_line, line_effects, mode_text, rules_lines, spell_effects, static_abilities,
                      triggered_abilities)
from .mana import parse_cost

# Keywords the engine implements (combat.py, game.py).
SUPPORTED_KEYWORDS = {
    "flying", "reach", "vigilance", "haste", "defender", "menace", "trample", "first strike",
    "double strike", "deathtouch", "lifelink", "indestructible", "hexproof", "shroud", "flash",
    "protection",  # "protection from <color>" only; see _is_keyword_line
    "persist", "undying",
    "prowess", "delve", "cascade", "devoid", "shadow", "skulk", "living weapon",  # devoid: the card data has no color
    "ascend",  # the city's blessing for a permanent that has it
    "split second",  # nothing but mana abilities can be done while the spell is on the stack: see Game.legal_actions
    "rebound",  # exiled as it resolves from the hand, and cast free at the next upkeep: see Game._rebound
    "compleated",  # a Phyrexian symbol paid with life costs the walker two loyalty counters as it enters: see Game._entering_loyalty
    "exalted",
    "daybound", "nightbound",  # the day/night rule: see Game._update_day_night
    "decayed",  # can't block; sacrificed at end of combat when it attacks
    "changeling",  # every creature type: Card lists them all in its type line
    "convoke", "improvise",  # creatures (artifacts) tapped to help pay: see Game._convoke_sources
    "infect", "wither",  # poison counters for a player, -1/-1 counters for a creature (Toxic N is read apart, below)
    "fear", "intimidate", "horsemanship", "flanking",
    "islandwalk", "swampwalk", "mountainwalk", "forestwalk", "plainswalk",  # not "snow landwalk" or "nonbasic landwalk"
    "extort",  # whenever its controller casts a spell they may pay {W/B}: each opponent loses 1 life and they gain that much
    "myriad",  # a tapped and attacking copy for each opponent other than the defending player, exiled at end of combat
}
# Lines that only matter when building the deck, which commander.py checks.
_DECKBUILDING = re.compile(
    r"(partner( with .+|—.+)?|friends forever|choose a background|doctor's companion"
    r"|CARDNAME can be your commander\.|A deck can have (any number of|up to \w+) cards named CARDNAME\.)",
    re.I,
)

# Rough buckets for unsupported lines, checked in order; they point at what to build next.
_CATEGORIES = [
    ("activated abilities", re.compile(r"^[^\"]*\{[^}]+\}[^\"]*:|^[−+]?\d+:|^\+\d+:|^0:")),
    ("triggers (the trigger or its effect)", re.compile(r"^(when|whenever|at the beginning|at end)", re.I)),
    ("tokens", re.compile(r"\btokens?\b", re.I)),
    ("+1/+1 and other counters", re.compile(r"\bcounters?\b(?! target)", re.I)),
    ("exile", re.compile(r"\bexile", re.I)),
    ("return to hand", re.compile(r"return .* to (its|their) owner's hand", re.I)),
    ("pump and static buffs", re.compile(r"get [+-]\d+/[+-]\d+|gets [+-]\d+/[+-]\d+", re.I)),
    ("enters tapped", re.compile(r"enters tapped", re.I)),
    # Keyword abilities, possibly with a cost or number: "Protection from red", "Ward {2}", "Evoke {2}{U}".
    ("other keywords", re.compile(r"^[a-z' ]+((\{[^}]+\})+|\d+)?(, [a-z' ]+((\{[^}]+\})+|\d+)?)*$", re.I)),
]


@dataclass
class CardReport:
    card: Card
    count: int
    problems: list[str]  # rules-text lines or costs the engine doesn't understand


# One line for every card, so the audit counts them together: an Adventure, a split card's other half, a back that isn't a land.
SECOND_FACE = "Second face or half of the card (a back face that is a permanent, a meld): not playable"


def unsupported_lines(card: Card) -> list[str]:
    """What the engine can't do for this card: an empty list means it's fully playable."""
    problems = []
    if not is_land(card) and card.mana_cost and parse_cost(card.mana_cost) is None:
        problems.append(f"mana cost {card.mana_cost}")
    spell = "Instant" in card.type_line or "Sorcery" in card.type_line
    whole_spell = spell and spell_effects(card) is not None  # Animist's Awakening: its Spell mastery line rides on the sentence before
    abilities = {a.text for a in triggered_abilities(card) + activated_abilities(card) + static_abilities(card)
                 + attached_abilities(card)}
    for line in rules_lines(card):
        if (is_cumulative_upkeep_line(line) or is_echo_line(line) or is_reanimation_aura_line(line)
                or is_cast_keyword_line(line)):
            continue
        if is_overload_line(line):
            if overloaded_effects(card) is None:
                problems.append(line)  # the overloaded text ("each" for "target") isn't understood
            continue
        if _is_keyword_line(line) or _DECKBUILDING.fullmatch(line) or is_cycling_line(line) or line == "CARDNAME is every creature type.":
            continue
        if line.startswith("Companion — ") and line.removeprefix("Companion — ").strip() in COMPANION_CONDITIONS:
            continue  # a companion the deck check knows (companion.py)
        if is_casting_cost_line(line) or (spell and is_hand_ability_line(line) and line in abilities):
            continue  # Magma Opus: a spell with an ability that works from the hand
        if spell and (is_modal_header(line) or line_effects(mode_text(line)) is not None or whole_spell):
            continue  # a sentence of the spell, or the "Choose one —" line, or one of its modes, or a line only the whole spell reads
        if not spell and (line in abilities or is_mana_ability(line) or is_enters_with_counters(line)
                          or is_enchant_line(line) or is_clone_line(line) or is_replacement_line(line) or is_control_aura_line(line) or is_enters_tapped_line(line) or is_choose_color_line(line) or is_optional_untap_line(line) or is_station_line(line) or is_enters_prepared_line(line) or is_extra_vote_line(line) or is_graveyard_permission_line(line) or is_graveyard_permit_line(line) or is_library_top_line(line) or is_no_max_hand_line(line) or is_return_exiled_line(line) or is_opening_hand_line(line) or is_additional_mana_line(line) or is_haste_abilities_line(line) or is_choose_type_line(line) or is_chosen_self_line(line) or is_x_discount_line(line) or is_attack_tax_line(line) or is_quest_untap_line(line) or is_cda_line(line) or is_hand_by_counters_line(line) or is_combat_restriction_line(line) or is_prevention_line(line) or is_rules_static_line(line) or is_restricted_mana_line(line) or is_tap_mana_line(line)
                          or is_cost_reduction_line(line) or is_granting_line(line) or is_group_mana_grant_line(line)):
            continue
        problems.append(line)
    if card.other_face:  # only the first face is modeled: the card's other half can't be cast or played
        problems.append(SECOND_FACE)
    if card.alternate is not None:  # the other half is cast from the hand, so its text has to work too
        problems += unsupported_lines(card.alternate)
    if card.flip is not None:  # a transformed permanent plays as the back face, so its text has to work too
        problems += [f"{card.flip.name}: {line}" for line in unsupported_lines(card.flip)]
    if card.prepare is not None:  # a prepared creature casts a copy of this half, so its text has to work too
        problems += [f"{card.prepare.name}: {line}" for line in unsupported_lines(card.prepare)]
    return problems


def _is_keyword_line(line: str) -> bool:
    if is_ward_line(line):  # "Ward\u2014{1}, Pay 2 life." has a comma that isn't between keywords
        return True
    line = PROTECTION.sub("protection", line.lower())  # "protection from red and from blue" is one keyword
    return all(part in SUPPORTED_KEYWORDS or is_ward_line(part) or re.fullmatch(r"(annihilator|toxic|bushido|afflict|rampage|dredge) \d+", part)
               for part in line.split(", "))


def category(line: str) -> str:
    if line.startswith("mana cost"):
        return "mana costs"
    for name, pattern in _CATEGORIES:
        if pattern.search(line):
            return name
    return "other rules text"


def deck_report(deck: Deck) -> list[CardReport]:
    counts: dict[str, int] = defaultdict(int)
    cards: dict[str, Card] = {}
    for card in deck.commanders + deck.main:
        counts[card.name] += 1
        cards[card.name] = card
    return [CardReport(card, counts[name], unsupported_lines(card)) for name, card in cards.items()]


def unplayable_cards(deck: Deck) -> list[tuple[str, int, str]]:
    """(name, copies, first unsupported line) for each card of the deck the engine can't fully play, most copies first."""
    found = [(r.card.name, r.count, r.problems[0]) for r in deck_report(deck) if r.problems]
    return sorted(found, key=lambda item: (-item[1], item[0]))


IN_A_GAME = "It casts them but ignores the text it can't read, so a spell does nothing and a creature has none of that ability."


def unplayable_note(cards: list[tuple[str, int, str]] | tuple[tuple[str, int], ...], subject: str, consequence: str = IN_A_GAME,
                    shown: int = 5) -> str:
    """One sentence for a report: how many cards the engine can't fully play, the first few, and what that means (`consequence`;
    by default, what happens when the card is played in a game)."""
    names = [item[0] for item in cards]
    copies = sum(item[1] for item in cards)
    listed = ", ".join(names[:shown]) + (f" and {len(names) - shown} more" if len(names) > shown else "")
    return (f"{subject} has {len(names)} card{'s' if len(names) != 1 else ''} ({copies} cop{'ies' if copies != 1 else 'y'}) the engine can't fully "
            f"play: {listed}. {consequence}")


def format_report(reports: list[CardReport]) -> str:
    total = sum(r.count for r in reports)
    playable = sum(r.count for r in reports if not r.problems)
    lines = [f"Fully playable: {playable}/{total} cards"]
    by_category: dict[str, list[str]] = defaultdict(list)
    for report in reports:
        for problem in report.problems:
            if report.card.name not in by_category[category(problem)]:
                by_category[category(problem)].append(report.card.name)
    if by_category:
        lines.append("\nMissing, by kind (most cards first):")
        for name, card_names in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"  {name} ({len(card_names)}): {', '.join(sorted(card_names))}")
        lines.append("\nDetails:")
        for report in sorted(reports, key=lambda r: r.card.name):
            for problem in report.problems:
                lines.append(f"  {report.card.name}: {problem}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")  # card text has characters like − that the Windows console can't print
    if len(argv) != 2:
        print("usage: python -m infernal_machine.report DECKLIST", file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        deck = load_deck(f.read(), BulkSource(".cache/oracle_bulk.json"))
    print(format_report(deck_report(deck)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
