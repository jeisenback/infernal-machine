""""Combustion Technique deals damage equal to 2 plus the number of Lesson cards in your graveyard to target creature. If that creature
would die this turn, exile it instead." (Combustion Technique)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BIG, lands, pick, real, run_stack, table3

TECHNIQUE = real("Combustion Technique", "{1}{R}", "Instant — Lesson", "Combustion Technique deals damage equal to 2 plus the number of "
                 "Lesson cards in your graveyard to target creature. If that creature would die this turn, exile it instead.")
LESSON = real("Introduction to Annihilation", "{5}", "Sorcery — Lesson", "Exile target nonland permanent. Its controller draws a card.")


def cast(lessons):
    game, _ = table3(pick("Big"))
    a, b = game.seats[0], game.seats[1]
    giant = Permanent(BIG)
    a.hand, a.battlefield, a.graveyard = [TECHNIQUE], lands(2), [LESSON] * lessons
    b.battlefield = [giant]
    game._perform(a, CAST + TECHNIQUE.name)
    run_stack(game)
    game._check_state()
    return b, giant


class CombustionTechniqueTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(TECHNIQUE), [])

    def test_two_plus_the_lessons(self):
        b, giant = cast(lessons=2)
        self.assertEqual(giant.damage, 4)

    def test_lethal_damage_exiles_it(self):
        b, giant = cast(lessons=3)
        self.assertEqual((b.battlefield, b.exile), ([], [BIG]))


if __name__ == "__main__":
    unittest.main()
