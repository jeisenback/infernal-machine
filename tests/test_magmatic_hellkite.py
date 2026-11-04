""""When this creature enters, destroy target nonbasic land an opponent controls. Its controller searches their library for a basic land
card, puts it onto the battlefield tapped with a stun counter on it, then shuffles." (Magmatic Hellkite)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, enter, real, run_stack, table3

HELLKITE = real("Magmatic Hellkite", "{2}{R}{R}", "Creature — Dragon", "Flying\nWhen this creature enters, destroy target nonbasic land an "
                "opponent controls. Its controller searches their library for a basic land card, puts it onto the battlefield tapped with "
                "a stun counter on it, then shuffles. (If a permanent with a stun counter would become untapped, remove one from it "
                "instead.)", "4", "5", colors=("R",))
DUAL = Card(name="Taiga", type_line="Land — Mountain Forest", produced_mana=("R", "G"))


class MagmaticHellkiteTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(HELLKITE), [])

    def test_the_land_is_replaced_by_a_tapped_stunned_basic(self):
        last = lambda prompt, options: len(options) - 1  # noqa: E731 (the search is not "may": a "No" is never asked)
        game, _ = table3(last, last, last)
        a, b = game.seats[0], game.seats[1]
        b.battlefield, b.library = [Permanent(DUAL)], [FOREST, FOREST]
        enter(game, a, HELLKITE)
        run_stack(game)
        self.assertEqual([(p.card, p.tapped, p.counters) for p in b.battlefield], [(FOREST, True, {"stun": 1})])
        self.assertEqual(len(b.library), 1)

    def test_a_basic_land_is_not_a_target(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b = game.seats[0], game.seats[1]
        b.battlefield, b.library = [Permanent(FOREST)], [FOREST]
        enter(game, a, HELLKITE)
        run_stack(game)
        self.assertEqual([p.card for p in b.battlefield], [FOREST])
        self.assertEqual(len(b.library), 1)


if __name__ == "__main__":
    unittest.main()
