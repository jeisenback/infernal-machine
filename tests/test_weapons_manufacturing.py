""""Whenever a nontoken artifact you control enters, create a colorless artifact token named Munitions with "When this token leaves the
battlefield, it deals 2 damage to any target."" (Weapons Manufacturing)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, RELIC, enter, pick, real, run_stack, table3

MANUFACTURING = real("Weapons Manufacturing", "{1}{R}", "Enchantment", "Whenever a nontoken artifact you control enters, create a colorless "
                     "artifact token named Munitions with \"When this token leaves the battlefield, it deals 2 damage to any target.\"",
                     colors=("R",))


def table(card):
    game, _ = table3(pick("Player: B"))
    a = game.seats[0]
    a.battlefield = [Permanent(MANUFACTURING)]
    enter(game, a, card)
    run_stack(game)
    return game, a


class WeaponsManufacturingTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(MANUFACTURING), [])

    def test_an_artifact_makes_munitions_that_deal_two_damage_as_they_leave(self):
        game, a = table(RELIC)
        munitions = [p for p in a.battlefield if p.card.name == "Munitions"]
        self.assertEqual(len(munitions), 1)
        b = game.seats[1]
        life = b.life
        game.destroy(munitions[0])
        run_stack(game)
        self.assertEqual(b.life, life - 2)

    def test_a_creature_makes_none(self):
        game, a = table(BEAR)
        self.assertFalse(any(p.card.name == "Munitions" for p in a.battlefield))


if __name__ == "__main__":
    unittest.main()
