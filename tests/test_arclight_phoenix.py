""""At the beginning of combat on your turn, if you've cast three or more instant and sorcery spells this turn, return this card from your
graveyard to the battlefield." (Arclight Phoenix)."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, real, resolve_triggers, table3

PHOENIX = real("Arclight Phoenix", "{3}{R}", "Creature — Phoenix", "Flying, haste\nAt the beginning of combat on your turn, if you've cast "
               "three or more instant and sorcery spells this turn, return this card from your graveyard to the battlefield.", "3", "2")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def combat(*cast):
    game, _ = table3()
    a = game.seats[0]
    a.graveyard = [PHOENIX]
    a.cast_log = [(game.turn, card) for card in cast]
    game.step = "beginning_of_combat"
    game._turn_based_actions(a)
    resolve_triggers(game, a)
    return a


class ArclightPhoenixTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(PHOENIX), [])

    def test_three_instants_bring_it_back(self):
        a = combat(BOLT, BOLT, BOLT)
        self.assertEqual([p.card for p in a.battlefield], [PHOENIX])
        self.assertEqual(a.graveyard, [])

    def test_two_are_not_enough(self):
        a = combat(BOLT, BOLT, BEAR)
        self.assertEqual(a.graveyard, [PHOENIX])


if __name__ == "__main__":
    unittest.main()
