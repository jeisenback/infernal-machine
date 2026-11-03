""""Whenever this creature is dealt damage, it deals that much damage to any other target. If a player is dealt damage this way, they
can't gain life for the rest of the game." (Screaming Nemesis)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, pick, real, run_stack, table3

NEMESIS = real("Screaming Nemesis", "{2}{R}", "Creature — Spirit", "Haste\nWhenever this creature is dealt damage, it deals that much damage "
               "to any other target. If a player is dealt damage this way, they can't gain life for the rest of the game.", "3", "3")


def damaged(answer, amount=2):
    game, _ = table3(pick(answer))
    a, b = game.seats[0], game.seats[1]
    nemesis, ogre = Permanent(NEMESIS), Permanent(OGRE)
    a.battlefield, b.battlefield = [nemesis], [ogre]
    game.damage(nemesis, amount, Permanent(BEAR))
    run_stack(game)
    return game, b, nemesis, ogre


class ScreamingNemesisTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(NEMESIS), [])

    def test_it_deals_that_much_to_a_player_who_then_cannot_gain_life(self):
        game, b, nemesis, _ = damaged("Player: B")
        self.assertEqual(b.life, 38)
        game.change_life(b, 5)
        self.assertEqual(b.life, 38)

    def test_damage_to_a_creature_locks_no_one(self):
        game, b, nemesis, ogre = damaged("Ogre", amount=2)
        self.assertEqual(ogre.damage, 2)
        game.change_life(b, 5)
        self.assertEqual(b.life, 45)
        self.assertFalse(hasattr(ogre, "no_life_gain"))

    def test_it_cannot_target_itself(self):
        game, _ = table3(pick("Screaming Nemesis"))
        a = game.seats[0]
        nemesis = Permanent(NEMESIS)
        a.battlefield = [nemesis]
        game.damage(nemesis, 1, Permanent(BEAR))
        game._put_triggers_on_stack()
        self.assertNotIn(nemesis, game.stack[-1].targets)


if __name__ == "__main__":
    unittest.main()
