""""Look at the top three cards of your library. Put one of those cards into your hand and the rest on the bottom of your library in any
order. Put each of those cards into your hand instead if there are three or more Lesson cards in your graveyard." (Accumulate Wisdom)."""

import unittest

from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, lands, real, run_stack, table3

WISDOM = real("Accumulate Wisdom", "{1}{U}", "Instant — Lesson", "Look at the top three cards of your library. Put one of those cards into "
              "your hand and the rest on the bottom of your library in any order. Put each of those cards into your hand instead if there "
              "are three or more Lesson cards in your graveyard.")
LESSON = real("Introduction to Annihilation", "{5}", "Sorcery — Lesson", "Exile target nonland permanent. Its controller draws a card.")


def cast(lessons):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.battlefield, a.graveyard, a.library = [WISDOM], lands(2), [LESSON] * lessons, [BEAR, OGRE, FOREST, FOREST]
    game._perform(a, CAST + WISDOM.name)
    run_stack(game)
    return a


class AccumulateWisdomTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(WISDOM), [])

    def test_one_card_normally(self):
        a = cast(lessons=2)
        self.assertEqual(len(a.hand), 1)
        self.assertEqual(a.library[0], FOREST)  # the fourth card stays on top

    def test_all_three_with_three_lessons(self):
        a = cast(lessons=3)
        self.assertEqual(sorted(c.name for c in a.hand), ["Bear", "Forest", "Ogre"])
        self.assertEqual(a.library, [FOREST])


if __name__ == "__main__":
    unittest.main()
