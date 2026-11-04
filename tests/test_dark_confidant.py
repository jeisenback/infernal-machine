""""At the beginning of your upkeep, reveal the top card of your library and put that card into your hand. You lose life equal to its mana
value." (Dark Confidant)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BIG, FOREST, fire, real, table3

CONFIDANT = real("Dark Confidant", "{1}{B}", "Creature — Human Wizard", "At the beginning of your upkeep, reveal the top card of your library "
                 "and put that card into your hand. You lose life equal to its mana value.", "2", "1", colors=("B",))


def upkeep(library):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.library = [], list(library)
    bob = Permanent(CONFIDANT)
    a.battlefield = [bob]
    life = a.life
    fire(game, a, bob, "upkeep")
    return a, life


class DarkConfidantTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(CONFIDANT), [])

    def test_the_top_card_goes_to_hand_and_costs_its_mana_value_in_life(self):
        a, life = upkeep([BIG, FOREST])
        self.assertEqual((a.hand, a.library), ([BIG], [FOREST]))
        self.assertEqual(a.life, life - 5)

    def test_a_land_costs_no_life(self):
        a, life = upkeep([FOREST])
        self.assertEqual((a.hand, a.life), ([FOREST], life))


if __name__ == "__main__":
    unittest.main()
