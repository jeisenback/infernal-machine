"""Lander tokens (Biotech Specialist: "When this creature enters, create a Lander token.") and "scry 1 and create a Treasure token"
(Greedy Freebooter)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, OGRE, activate, lands, real, run_stack, table3

BIOTECH = real("Biotech Specialist", "{R}{G}", "Creature — Insect Scientist", "When this creature enters, create a Lander token. (It's an "
               "artifact with \"{2}, {T}, Sacrifice this token: Search your library for a basic land card, put it onto the battlefield tapped, "
               "then shuffle.\")\nWhenever you sacrifice an artifact, this creature deals 2 damage to target opponent.", "1", "3")
FREEBOOTER = real("Greedy Freebooter", "{B}", "Creature — Human Pirate", "When this creature dies, scry 1 and create a Treasure token. "
                  "(To scry 1, look at the top card of your library. You may put that card on the bottom. A Treasure token is an artifact with "
                  "\"{T}, Sacrifice this token: Add one mana of any color.\")", "1", "1")


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class TokenTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (BIOTECH, FREEBOOTER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_biotech_specialist_makes_a_lander_that_fetches_a_basic_land_tapped(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [OGRE, FOREST, OGRE]
        a.battlefield = lands(2)
        game._enter(a, Permanent(BIOTECH))
        run_stack(game)
        self.assertIn("Lander", names(a))
        activate(game, a, "Lander")
        forest = [p for p in a.battlefield if p.card is FOREST]
        self.assertEqual(len(forest), 1)
        self.assertTrue(forest[0].tapped)
        self.assertNotIn("Lander", names(a))
        self.assertEqual(game.seats[1].life, 38)  # Biotech Specialist: an artifact was sacrificed

    def test_greedy_freebooter_scries_and_makes_a_treasure_when_it_dies(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [OGRE, OGRE]
        freebooter = Permanent(FREEBOOTER)
        a.battlefield = [freebooter]
        game._leave_battlefield(freebooter, "destroyed")
        run_stack(game)
        self.assertEqual(names(a), ["Treasure"])


if __name__ == "__main__":
    unittest.main()
