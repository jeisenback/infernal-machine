""""Mill four cards. Then put an instant, sorcery, or Faerie card from among the milled cards into your hand." (Free the Fae, Picklock
Prankster's Adventure)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, real, run_stack, scryfall, table3

FREE = real("Free the Fae", "{1}{U}", "Instant — Adventure", "Mill four cards. Then put an instant, sorcery, or Faerie card from among the "
            "milled cards into your hand.")
PRANKSTER = Card.from_scryfall(scryfall(
    "adventure",
    {"name": "Picklock Prankster", "mana_cost": "{1}{U}", "type_line": "Creature — Faerie Rogue", "oracle_text": "Flying, vigilance",
     "power": "1", "toughness": "3"},
    {"name": "Free the Fae", "mana_cost": "{1}{U}", "type_line": "Instant — Adventure", "oracle_text": FREE.oracle_text}, cmc=2.0))
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")
SPRITE = real("Faerie Miscreant", "{U}", "Creature — Faerie Wizard", "Flying", "1", "1")


def cast(library):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.battlefield, a.graveyard, a.library = [FREE], lands(2), [BOLT], list(library)
    game._perform(a, CAST + FREE.name)
    run_stack(game)
    return a


class FreeTheFaeTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(PRANKSTER), [])

    def test_a_faerie_milled_goes_to_the_hand(self):
        a = cast([FOREST, SPRITE, FOREST, FOREST, BOLT])
        self.assertEqual(a.hand, [SPRITE])
        self.assertEqual(a.library, [BOLT])

    def test_only_the_milled_cards_count(self):
        a = cast([FOREST, FOREST, FOREST, FOREST])
        self.assertEqual(a.hand, [])
        self.assertIn(BOLT, a.graveyard)  # the Bolt already in the graveyard stays


if __name__ == "__main__":
    unittest.main()
