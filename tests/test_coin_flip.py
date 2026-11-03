""""Flip a coin. If you lose the flip, ..." (Mana Crypt, CR 705)."""

import unittest
from unittest import mock

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import real, resolve_triggers, table3

CRYPT = real("Mana Crypt", "{0}", "Artifact", "At the beginning of your upkeep, flip a coin. If you lose the flip, this artifact deals 3 "
             "damage to you.\n{T}: Add {C}{C}.")


def upkeep(roll):
    game, _ = table3()
    a = game.seats[0]
    a.battlefield = [Permanent(CRYPT)]
    game.step = "upkeep"
    with mock.patch.object(game.rng, "random", return_value=roll):
        game._turn_based_actions(a)
        resolve_triggers(game, a)
    return game, a


class ManaCryptTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(CRYPT), [])

    def test_a_lost_flip_deals_3_damage_to_you(self):
        game, a = upkeep(0.9)
        self.assertEqual([s.life for s in game.seats], [37, 40, 40])

    def test_a_won_flip_does_nothing(self):
        game, a = upkeep(0.1)
        self.assertEqual([s.life for s in game.seats], [40, 40, 40])


if __name__ == "__main__":
    unittest.main()
