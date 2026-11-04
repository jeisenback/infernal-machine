""""When you draw your third card in a turn, return this card from your graveyard to the battlefield tapped." (Sneaky Snacker)."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, run_stack, real, table3

SNACKER = real("Sneaky Snacker", "{U}{B}", "Creature — Faerie Rogue", "Flying\nWhen you draw your third card in a turn, return this card from "
               "your graveyard to the battlefield tapped.", "2", "1", colors=("B", "U"))


def draw(times):
    game, _ = table3()
    a = game.seats[0]
    a.graveyard, a.battlefield, a.library, a.hand = [SNACKER], [], [OGRE] * 5, []
    for _ in range(times):
        game.draw(a, 1)
    run_stack(game)
    return a


class SneakySnackerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SNACKER), [])

    def test_the_third_card_drawn_returns_it_tapped(self):
        a = draw(3)
        self.assertEqual([(p.card, p.tapped) for p in a.battlefield], [(SNACKER, True)])
        self.assertEqual(a.graveyard, [])

    def test_two_cards_drawn_leave_it_in_the_graveyard(self):
        a = draw(2)
        self.assertEqual((a.battlefield, a.graveyard), ([], [SNACKER]))


if __name__ == "__main__":
    unittest.main()
