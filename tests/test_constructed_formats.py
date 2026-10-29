"""Pioneer, Modern, Legacy, Vintage and Pauper: Standard's rules with their own pools, read from Scryfall's legalities (#522)."""

import argparse
import dataclasses
import json
import unittest

from infernal_machine.cards import CARD_FORMAT, Card, Deck
from infernal_machine.formats import (FORMATS, LEGACY, MODERN, PAUPER, PIONEER, STANDARD, VINTAGE, add_format_argument, deck_problems,
                                      with_format)
from infernal_machine.tune import candidate_problem
from tests.helpers import FOREST

NEW = (PIONEER, MODERN, LEGACY, VINTAGE, PAUPER)


def scryfall(name, legalities):
    return Card.from_scryfall({"name": name, "mana_cost": "{1}", "cmc": 1, "type_line": "Artifact", "oracle_text": "", "legalities": legalities})


# As Scryfall gives them (every format it lists, here trimmed to the ones that matter).
MODERN_ONLY = scryfall("Modern Card", {"standard": "not_legal", "pioneer": "not_legal", "modern": "legal", "legacy": "legal",
                                       "vintage": "legal", "pauper": "not_legal", "commander": "legal"})
RESTRICTED = scryfall("Restricted Card", {"standard": "not_legal", "pioneer": "not_legal", "modern": "banned", "legacy": "banned",
                                          "vintage": "restricted", "pauper": "not_legal", "commander": "banned"})


def constructed(*cards, fmt):
    return with_format(Deck([], [*cards, *[FOREST] * (60 - len(cards))], []), fmt.name)


class LegalityTests(unittest.TestCase):
    def test_scryfalls_legalities_are_kept_as_the_formats_a_card_is_legal_in(self):
        self.assertEqual(MODERN_ONLY.legal, ("commander", "legacy", "modern", "vintage"))
        self.assertEqual(MODERN_ONLY.restricted, ())
        self.assertEqual((MODERN_ONLY.legal_in("modern"), MODERN_ONLY.legal_in("pioneer")), (True, False))
        self.assertEqual(RESTRICTED.legal, ("vintage",), "a restricted card is legal, one copy of it")
        self.assertEqual(RESTRICTED.restricted, ("vintage",))
        self.assertFalse(scryfall("Nothing", {}).legal_in("commander"), "no legality given is not legal")

    def test_a_card_made_by_hand_is_legal_everywhere(self):
        self.assertIsNone(FOREST.legal)
        self.assertTrue(all(FOREST.legal_in(fmt.legality) for fmt in FORMATS.values()))

    def test_both_survive_the_card_file(self):
        for card in (MODERN_ONLY, RESTRICTED, FOREST):
            again = Card.from_dict(json.loads(json.dumps(card.to_dict())))
            self.assertEqual((again.legal, again.restricted), (card.legal, card.restricted))
        self.assertGreaterEqual(CARD_FORMAT, 7)


class FormatTests(unittest.TestCase):
    def test_each_is_standards_shape_with_its_own_legality(self):
        for fmt in NEW:
            self.assertEqual((fmt.life, fmt.min_deck, fmt.sideboard, fmt.copy_limit, fmt.commander), (20, 60, 15, 4, False), fmt.name)
            self.assertEqual(fmt.legality, fmt.name)
            self.assertIs(FORMATS[fmt.name], fmt)
        self.assertEqual([fmt.label for fmt in NEW], ["Pioneer", "Modern", "Legacy", "Vintage", "Pauper"])

    def test_a_deck_is_checked_against_its_own_pool(self):
        self.assertEqual(deck_problems(constructed(MODERN_ONLY, fmt=MODERN), MODERN), [])
        self.assertEqual(deck_problems(constructed(MODERN_ONLY, fmt=PIONEER), PIONEER), ["Modern Card is not legal in Pioneer"])
        self.assertEqual(deck_problems(constructed(MODERN_ONLY, fmt=STANDARD), STANDARD), ["Modern Card is not legal in Standard"])
        self.assertEqual(deck_problems(constructed(MODERN_ONLY, fmt=PAUPER), PAUPER), ["Modern Card is not legal in Pauper"])

    def test_vintage_allows_one_copy_of_a_restricted_card(self):
        self.assertEqual(deck_problems(constructed(RESTRICTED, fmt=VINTAGE), VINTAGE), [])
        self.assertEqual(deck_problems(constructed(RESTRICTED, RESTRICTED, fmt=VINTAGE), VINTAGE),
                         ["Restricted Card: 2 copies, limit is 1 (restricted)"])
        in_sideboard = dataclasses.replace(constructed(RESTRICTED, fmt=VINTAGE), sideboard=[RESTRICTED])
        self.assertEqual(deck_problems(in_sideboard, VINTAGE), ["Restricted Card: 2 copies, limit is 1 (restricted)"], "the sideboard counts")
        self.assertEqual(deck_problems(constructed(RESTRICTED, fmt=LEGACY), LEGACY), ["Restricted Card is not legal in Legacy"])
        self.assertEqual(deck_problems(constructed(MODERN_ONLY, MODERN_ONLY, MODERN_ONLY, MODERN_ONLY, fmt=VINTAGE), VINTAGE), [],
                         "four copies of a card that is not restricted")

    def test_the_tools_take_the_new_names(self):
        parser = argparse.ArgumentParser()
        add_format_argument(parser)
        self.assertEqual([parser.parse_args(["--format", fmt.name]).format for fmt in NEW], [fmt.name for fmt in NEW])


class TuneTests(unittest.TestCase):
    def test_a_candidate_must_be_legal_in_the_decks_format(self):
        self.assertIsNone(candidate_problem(constructed(fmt=MODERN), MODERN_ONLY))
        self.assertEqual(candidate_problem(constructed(fmt=PIONEER), MODERN_ONLY), "not legal in Pioneer")
        self.assertEqual(candidate_problem(Deck([], [FOREST] * 60, []), MODERN_ONLY), "not legal in Standard", "a deck that names no format")

    def test_a_restricted_candidate_is_limited_to_one_copy(self):
        self.assertIsNone(candidate_problem(constructed(fmt=VINTAGE), RESTRICTED))
        self.assertEqual(candidate_problem(constructed(RESTRICTED, fmt=VINTAGE), RESTRICTED), "already at 1 copies")


if __name__ == "__main__":
    unittest.main()
