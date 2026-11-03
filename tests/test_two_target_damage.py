"""Two targets, two amounts: "Reckless Rage deals 4 damage to target creature you don't control and 2 damage to target creature you
control."."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, real

RAGE = real("Reckless Rage", "{R}", "Instant", "Reckless Rage deals 4 damage to target creature you don't control and 2 damage to target "
            "creature you control.")


class RecklessRageTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(RAGE), [])

    def test_four_to_theirs_and_two_to_mine(self):
        ogre, bear = Permanent(OGRE), Permanent(BEAR)
        table = Table(RAGE, n=1, mine=[ogre], theirs=[bear]).cast()
        self.assertEqual(table.b.graveyard, [BEAR])
        self.assertEqual(ogre.damage, 2)

    def test_it_needs_a_creature_of_mine(self):
        table = Table(RAGE, n=1, theirs=[Permanent(BEAR)])
        self.assertNotIn(CAST + RAGE.name, table.game.legal_actions(table.a))


if __name__ == "__main__":
    unittest.main()
