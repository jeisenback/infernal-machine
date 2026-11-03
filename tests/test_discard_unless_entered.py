"""Moon-Circuit Hacker: "Whenever this creature deals combat damage to a player, you may draw a card. If you do, discard a card unless this
creature entered this turn." """

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, real, run_stack, script, table3

HACKER = real("Moon-Circuit Hacker", "{1}{U}", "Enchantment Creature — Human Ninja", "Ninjutsu {U} ({U}, Return an unblocked attacker "
              "you control to hand: Put this card onto the battlefield from your hand tapped and attacking.)\nWhenever this creature deals "
              "combat damage to a player, you may draw a card. If you do, discard a card unless this creature entered this turn.", "2", "1")


def hits(entered_this_turn, *answers):
    game, _ = table3(script(*answers))
    a, b = game.seats[0], game.seats[1]
    a.hand, a.library, a.graveyard = [BEAR], [OGRE, OGRE], []
    hacker = Permanent(HACKER)
    hacker.entered_turn = game.turn if entered_this_turn else game.turn - 1
    a.battlefield = [hacker]
    game.damage(b, 2, hacker, combat=True)
    run_stack(game)
    return a


class MoonCircuitHackerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(HACKER), [])

    def test_it_loots_when_it_was_already_out(self):
        a = hits(False, "Yes", "Bear")
        self.assertEqual((a.hand, a.graveyard), ([OGRE], [BEAR]))

    def test_it_only_draws_the_turn_it_entered(self):
        a = hits(True, "Yes")
        self.assertEqual((sorted(c.name for c in a.hand), a.graveyard), (["Bear", "Ogre"], []))

    def test_declining_does_nothing(self):
        a = hits(False, "No")
        self.assertEqual((a.hand, a.graveyard), ([BEAR], []))


if __name__ == "__main__":
    unittest.main()
