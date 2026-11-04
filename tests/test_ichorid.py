""""At the beginning of your upkeep, if this card is in your graveyard, you may exile a black creature card other than this card from your
graveyard. If you do, return this card to the battlefield." (Ichorid)."""

import unittest

from infernal_machine.game import EXILE_COST_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, real, resolve_triggers, table3

ICHORID = real("Ichorid", "{3}{B}", "Creature — Horror", "Haste\nAt the beginning of the end step, sacrifice this creature.\nAt the beginning "
               "of your upkeep, if this card is in your graveyard, you may exile a black creature card other than this card from your "
               "graveyard. If you do, return this card to the battlefield.", "3", "1", colors=("B",))
ZOMBIE = real("Gravecrawler", "{B}", "Creature — Zombie", "", "2", "1", colors=("B",))


def upkeep(graveyard):
    game, _ = table3(lambda prompt, options: 0)
    a = game.seats[0]
    a.graveyard, a.exile, a.battlefield = list(graveyard), [], []
    game.step = "upkeep"
    game._turn_based_actions(a)
    resolve_triggers(game, a)
    return a


class IchoridTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(ICHORID), [])

    def test_exiling_another_black_creature_card_brings_it_back(self):
        a = upkeep([ICHORID, ZOMBIE])
        self.assertEqual([p.card for p in a.battlefield], [ICHORID])
        self.assertEqual((a.graveyard, a.exile), ([], [ZOMBIE]))

    def test_it_cannot_exile_itself_or_a_nonblack_card(self):
        a = upkeep([ICHORID, BEAR])
        self.assertEqual(a.battlefield, [])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Ichorid"])


if __name__ == "__main__":
    unittest.main()
