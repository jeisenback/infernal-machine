"""Xorn, from its real Oracle text: "If you would create one or more Treasure tokens, instead create those tokens plus an additional
Treasure token." Two Treasures become three; a batch with no Treasure gets none; an opponent's Xorn does nothing for you."""

import unittest

from infernal_machine.effects import TREASURE
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import SPIRIT, real, table3

XORN = real("Xorn", "{2}{R}", "Creature — Elemental", "If you would create one or more Treasure tokens, instead create those tokens plus "
            "an additional Treasure token.", "3", "2", colors=("R",))


def treasures(seat):
    return sum(p.card.name == "Treasure" for p in seat.battlefield)


class XornTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(XORN), [])

    def test_two_treasures_become_three(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(XORN)]
        game.create_tokens(a, TREASURE, 2)
        self.assertEqual(treasures(a), 3)

    def test_no_treasure_no_extra(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(XORN)]
        game.create_tokens(a, SPIRIT, 1)
        self.assertEqual((treasures(a), len(a.battlefield)), (0, 2))

    def test_an_opponents_xorn_does_nothing_for_you(self):
        game, _ = table3()
        a = game.seats[0]
        game.seats[1].battlefield = [Permanent(XORN)]
        game.create_tokens(a, TREASURE, 1)
        self.assertEqual(treasures(a), 1)


if __name__ == "__main__":
    unittest.main()
