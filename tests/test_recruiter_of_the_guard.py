""""When this creature enters, you may search your library for a creature card with toughness 2 or less, reveal it, put it into your
hand, then shuffle." (Recruiter of the Guard)."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, creature, enter, real, run_stack, table3

RECRUITER = real("Recruiter of the Guard", "{2}{W}", "Creature — Human Soldier", "When this creature enters, you may search your library for a "
                 "creature card with toughness 2 or less, reveal it, put it into your hand, then shuffle.", "1", "1", colors=("W",))
WALL = creature("Wall", 0, 4)
RAIDER = creature("Raider", 3, 1)


def recruit(library):
    game, _ = table3(lambda prompt, options: 0)
    a = game.seats[0]
    a.hand, a.library = [], list(library)
    enter(game, a, RECRUITER)
    run_stack(game)
    return a


class RecruiterOfTheGuardTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(RECRUITER), [])

    def test_it_finds_a_creature_with_toughness_two_or_less(self):
        a = recruit([WALL, RAIDER, OGRE])
        self.assertEqual(a.hand, [RAIDER])

    def test_a_tougher_creature_is_not_found(self):
        a = recruit([WALL, OGRE])
        self.assertEqual(a.hand, [])
        self.assertEqual(len(a.library), 2)


if __name__ == "__main__":
    unittest.main()
