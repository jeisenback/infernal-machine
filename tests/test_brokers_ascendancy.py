"""Brokers Ascendancy, from its real Oracle text: "At the beginning of your end step, put a +1/+1 counter on each creature you control and
a loyalty counter on each planeswalker you control." Only yours, and an opponent's end step passes it by."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, real, run_stack, table3

ASCENDANCY = real("Brokers Ascendancy", "{G}{W}{U}", "Enchantment", "At the beginning of your end step, put a +1/+1 counter on each creature "
                  "you control and a loyalty counter on each planeswalker you control.", None, None, colors=("G", "U", "W"))
JACE = real("Jace Beleren", "{1}{U}{U}", "Legendary Planeswalker — Jace", "+2: Each player draws a card.\n−1: Target player draws a "
            "card.\n−10: Target player mills twenty cards.", None, None, colors=("U",))


def end_step(whose):
    """Seat 0 has Brokers Ascendancy, a Bear and Jace (3 loyalty); seat 1 has the same Bear and Jace; `whose` end step begins."""
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(ASCENDANCY), Permanent(BEAR), Permanent(JACE, loyalty=3)]
    b.battlefield = [Permanent(BEAR), Permanent(JACE, loyalty=3)]
    game.step = "end"
    game._turn_based_actions(game.seats[whose])
    run_stack(game)
    return a, b


class BrokersAscendancyTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(ASCENDANCY), [])

    def test_your_end_step_counters_your_creatures_and_planeswalkers(self):
        a, b = end_step(0)
        self.assertEqual(([p.counters.get("+1/+1", 0) for p in a.battlefield[1:2]], a.battlefield[2].loyalty), ([1], 4))
        self.assertEqual((b.battlefield[0].counters, b.battlefield[1].loyalty), ({}, 3))  # not an opponent's

    def test_an_opponents_end_step_passes_it_by(self):
        a, _ = end_step(1)
        self.assertEqual((a.battlefield[1].counters, a.battlefield[2].loyalty), ({}, 3))


if __name__ == "__main__":
    unittest.main()
