"""Narset, Parter of Veils: "Each opponent can't draw more than one card each turn." """

import dataclasses
import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, real, table3

NARSET = dataclasses.replace(real("Narset, Parter of Veils", "{1}{U}{U}", "Legendary Planeswalker — Narset", "Each opponent can't draw "
                                  "more than one card each turn.\n−2: Look at the top four cards of your library. You may reveal a "
                                  "noncreature, nonland card from among them and put it into your hand. Put the rest on the bottom of "
                                  "your library in a random order."), loyalty="5")


def table():
    game, _ = table3()
    for seat in game.seats:
        seat.hand, seat.library = [], [OGRE] * 6
    game.seats[0].battlefield = [Permanent(NARSET)]
    return game, game.seats[0], game.seats[1]


class NarsetTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(NARSET), [])

    def test_an_opponent_draws_only_one_card_a_turn(self):
        game, _, b = table()
        game.draw(b, 3)
        game.draw(b, 1)
        self.assertEqual(len(b.hand), 1)
        game.turn += 1
        game.draw(b, 2)
        self.assertEqual(len(b.hand), 2)

    def test_its_controller_draws_freely(self):
        game, a, _ = table()
        game.draw(a, 3)
        self.assertEqual(len(a.hand), 3)

    def test_without_narset_nothing_is_limited(self):
        game, _, b = table()
        game.seats[0].battlefield = []
        game.draw(b, 3)
        self.assertEqual(len(b.hand), 3)


if __name__ == "__main__":
    unittest.main()
