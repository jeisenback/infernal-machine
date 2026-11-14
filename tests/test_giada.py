"""Giada, Font of Hope, a tracked deck's commander, from its real Oracle text: "Each other Angel you control enters with an additional +1/+1
counter on it for each Angel you already control." Giada counts herself; a non-Angel gets nothing, and so does Giada as she enters."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, enter, real, table3

GIADA = real("Giada, Font of Hope", "{1}{W}", "Legendary Creature — Angel", "Flying, vigilance\nEach other Angel you control enters with an "
             "additional +1/+1 counter on it for each Angel you already control.\n{T}: Add {W}. Spend this mana only to cast an Angel spell.",
             "2", "2", colors=("W",))
SERRA = real("Serra Angel", "{3}{W}{W}", "Creature — Angel", "Flying\nVigilance (Attacking doesn't cause this creature to tap.)", "4", "4",
             colors=("W",))


class GiadaTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(GIADA), [])

    def test_an_angel_enters_with_a_counter_for_each_angel_already_there(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(GIADA), Permanent(SERRA), Permanent(BEAR)]
        angel = enter(game, a, SERRA)
        self.assertEqual(angel.counters.get("+1/+1"), 2)  # Giada and the Serra Angel already there; the Bear doesn't count

    def test_a_non_angel_gets_nothing(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(GIADA), Permanent(SERRA)]
        self.assertEqual(enter(game, a, BEAR).counters.get("+1/+1"), None)

    def test_giada_herself_enters_without_one(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(SERRA)]
        self.assertEqual(enter(game, a, GIADA).counters.get("+1/+1"), None)

    def test_an_opponents_giada_does_nothing_for_you(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        b.battlefield = [Permanent(GIADA)]
        a.battlefield = [Permanent(SERRA)]
        self.assertEqual(enter(game, a, SERRA).counters.get("+1/+1"), None)


if __name__ == "__main__":
    unittest.main()
