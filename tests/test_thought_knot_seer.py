""""When this creature enters, target opponent reveals their hand. You choose a nonland card from it and exile that card." (Thought-Knot
Seer)."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, OGRE, enter, pick, real, run_stack, table3

SEER = real("Thought-Knot Seer", "{3}{C}", "Creature — Eldrazi", "({C} represents colorless mana.)\nWhen this creature enters, target "
            "opponent reveals their hand. You choose a nonland card from it and exile that card.\nWhen this creature leaves the battlefield, "
            "target opponent draws a card.", "4", "4")


class ThoughtKnotSeerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SEER), [])

    def test_it_exiles_a_nonland_card_from_their_hand(self):
        game, _ = table3(pick("Player: B", "Ogre"))
        a, b = game.seats[0], game.seats[1]
        b.hand, b.graveyard, b.exile = [FOREST, OGRE], [], []
        enter(game, a, SEER)
        run_stack(game)
        self.assertEqual((b.hand, b.exile, b.graveyard), ([FOREST], [OGRE], []))


if __name__ == "__main__":
    unittest.main()
