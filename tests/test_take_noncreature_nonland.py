"""Thundertrap Trainer: "When this creature enters, look at the top four cards of your library. You may reveal a noncreature, nonland card
from among them and put it into your hand. Put the rest on the bottom of your library in a random order." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, lands, pick, real, run_stack, table3

TRAINER = real("Thundertrap Trainer", "{1}{U}", "Creature — Otter Wizard", "Offspring {4} (You may pay an additional {4} as you cast this "
               "spell. If you do, when this creature enters, create a 1/1 token copy of it.)\nWhen this creature enters, look at the top four "
               "cards of your library. You may reveal a noncreature, nonland card from among them and put it into your hand. Put the rest on "
               "the bottom of your library in a random order.", "1", "2")


def cast(library, take):
    game, _ = table3(pick(take))
    a = game.seats[0]
    a.hand, a.library = [TRAINER], list(library)
    a.battlefield = lands(2)
    game._perform(a, CAST + TRAINER.name)
    run_stack(game)
    return a


class ThundertrapTrainerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(TRAINER), [])

    def test_it_takes_a_noncreature_nonland_card(self):
        a = cast([BEAR, FOREST, RELIC, OGRE, BEAR], "Relic")
        self.assertEqual(a.hand, [RELIC])
        self.assertEqual(a.library[0], BEAR)  # the fifth card; the other three went to the bottom
        self.assertEqual(len(a.library), 4)

    def test_creatures_and_lands_cannot_be_taken(self):
        a = cast([BEAR, FOREST, OGRE, FOREST], "Bear")
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
