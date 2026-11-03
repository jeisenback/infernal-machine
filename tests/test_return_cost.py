""""Return a Forest you control to its owner's hand: Untap target creature. Activate only once each turn." (Quirion Ranger)."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, SWAMP, activate, pick, real, table3

RANGER = real("Quirion Ranger", "{G}", "Creature — Elf Ranger", "Return a Forest you control to its owner's hand: Untap target creature. "
              "Activate only once each turn.", "1", "1")


def table(*lands):
    game, _ = table3(pick("Bear"))
    a = game.seats[0]
    bear = Permanent(BEAR)
    bear.tapped = True
    a.hand, a.battlefield = [], [Permanent(RANGER), bear] + [Permanent(land) for land in lands]
    return game, a, bear


def offered(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE) and "Quirion Ranger" in x]


class QuirionRangerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(RANGER), [])

    def test_it_returns_a_forest_to_untap_a_creature(self):
        game, a, bear = table(FOREST)
        activate(game, a, "Quirion Ranger")
        self.assertFalse(bear.tapped)
        self.assertEqual(a.hand, [FOREST])
        self.assertNotIn("Forest", [p.card.name for p in a.battlefield])

    def test_it_needs_a_forest(self):
        game, a, bear = table(SWAMP)
        self.assertEqual(offered(game, a), [])

    def test_only_once_each_turn(self):
        game, a, bear = table(FOREST, FOREST)
        activate(game, a, "Quirion Ranger")
        self.assertEqual(offered(game, a), [])


if __name__ == "__main__":
    unittest.main()
