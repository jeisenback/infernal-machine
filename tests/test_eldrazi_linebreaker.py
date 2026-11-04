""""At the beginning of combat on your turn, target creature you control gains haste and gets +X/+0 until end of turn, where X is the
number of Eldrazi you control." (Eldrazi Linebreaker)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, pick, real, resolve_triggers, table3

LINEBREAKER = real("Eldrazi Linebreaker", "{1}{C}{R}", "Creature — Eldrazi", "Devoid (This card has no color.)\nTrample\nAt the beginning "
                   "of combat on your turn, target creature you control gains haste and gets +X/+0 until end of turn, where X is the "
                   "number of Eldrazi you control.", "3", "3")
SCION = real("Eldrazi Scion", "", "Token Creature — Eldrazi Scion", "Sacrifice this creature: Add {C}.", "1", "1")


def combat(*others):
    game, _ = table3(pick("Bear"))
    a = game.seats[0]
    bear = Permanent(BEAR)
    bear.sick = True
    a.battlefield = [Permanent(LINEBREAKER), bear] + [Permanent(card) for card in others]
    game.step = "beginning_of_combat"
    game._turn_based_actions(a)
    resolve_triggers(game, a)
    return game, bear


class EldraziLinebreakerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(LINEBREAKER), [])

    def test_plus_one_per_eldrazi_and_haste(self):
        game, bear = combat(SCION)
        self.assertEqual((game.power(bear), game.toughness(bear)), (4, 2))
        self.assertTrue(game.has_keyword(bear, "haste"))

    def test_alone_it_counts_itself(self):
        game, bear = combat()
        self.assertEqual(game.power(bear), 3)


if __name__ == "__main__":
    unittest.main()
