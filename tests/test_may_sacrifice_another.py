"""The Sackville-Bagginses: "When The Sackville-Bagginses enter, you may sacrifice another creature or artifact. If you do, draw a card
and create a Treasure token." """

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, RELIC, real, run_stack, script, table3

SACKVILLES = real("The Sackville-Bagginses", "{1}{B}", "Legendary Creature — Halfling Citizen", "When The Sackville-Bagginses enter, "
                  "you may sacrifice another creature or artifact. If you do, draw a card and create a Treasure token.\nWhenever you "
                  "sacrifice a token, target opponent loses 1 life.", "2", "2")


def enters(others, *answers):
    game, _ = table3(script(*answers))
    a = game.seats[0]
    a.hand, a.library = [], [OGRE, OGRE]
    a.battlefield = [Permanent(card) for card in others]
    game._enter(a, Permanent(SACKVILLES))
    run_stack(game)
    return a


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class SackvilleBagginsesTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SACKVILLES), [])

    def test_sacrificing_another_draws_and_makes_a_treasure(self):
        a = enters([BEAR], "Yes", "Bear")
        self.assertEqual(names(a), ["The Sackville-Bagginses", "Treasure"])
        self.assertEqual(a.hand, [OGRE])

    def test_an_artifact_can_be_sacrificed(self):
        a = enters([RELIC], "Yes", "Relic")
        self.assertEqual(names(a), ["The Sackville-Bagginses", "Treasure"])

    def test_declining_does_nothing(self):
        a = enters([BEAR], "No")
        self.assertEqual(names(a), ["Bear", "The Sackville-Bagginses"])
        self.assertEqual(a.hand, [])

    def test_it_is_not_offered_beside_another_creature(self):
        a = enters([BEAR], "Yes", "The Sackville")  # the answer names it, but only the Bear is offered
        self.assertEqual(names(a), ["The Sackville-Bagginses", "Treasure"])

    def test_it_cannot_sacrifice_itself(self):
        a = enters([], "Yes", "The Sackville")
        self.assertEqual(names(a), ["The Sackville-Bagginses"])
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
