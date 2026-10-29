"""Escape Tunnel: "target creature with power 2 or less" is checked against the creature's power now (#564)."""

import unittest

from infernal_machine.effects import activated_abilities
from infernal_machine.effects.families.combat_and_pump import Pump
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Permanent, activate, lands, pick, real, table3

ESCAPE_TUNNEL = real("Escape Tunnel", "", "Land",
                     "{T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tapped, then "
                     "shuffle.\n{T}, Sacrifice this land: Target creature with power 2 or less can't be blocked this turn.")
KIND = "creature with power 2 or less"


def board(*policy):
    """Seat A has Escape Tunnel and a Bear; seat B has a Bear and an Ogre."""
    game, (a, b, _) = table3(*policy)
    tunnel = Permanent(ESCAPE_TUNNEL)
    mine, bear, ogre = Permanent(BEAR), Permanent(BEAR), Permanent(OGRE)
    game.seats[0].battlefield = [tunnel, mine] + lands(2)
    game.seats[1].battlefield = [bear, ogre]
    return game, game.seats[0], tunnel, mine, bear, ogre


class ParseTests(unittest.TestCase):
    def test_the_card_is_read(self):
        self.assertEqual(unsupported_lines(ESCAPE_TUNNEL), [])
        ability = activated_abilities(ESCAPE_TUNNEL)[1]
        self.assertEqual(len(ability.effects), 1)
        self.assertIsInstance(ability.effects[0], Pump)
        self.assertEqual(ability.effects[0].target, KIND)
        self.assertIn("can't be blocked", ability.effects[0].modifier.keywords)


class TargetTests(unittest.TestCase):
    def test_only_creatures_with_power_2_or_less_are_offered(self):
        game, a, tunnel, mine, bear, ogre = board()
        self.assertEqual([p for _, p in game.target_options(KIND, a)], [mine, bear])

    def test_a_counter_raises_the_power_past_the_limit(self):
        game, a, tunnel, mine, bear, ogre = board()
        bear.counters["+1/+1"] = 1
        self.assertEqual([p for _, p in game.target_options(KIND, a)], [mine])

    def test_the_target_cannot_be_blocked_and_the_land_is_sacrificed(self):
        game, a, tunnel, mine, bear, ogre = board(pick("Bear"))
        activate(game, a, "can't be blocked")
        self.assertTrue(game.has_keyword(mine, "can't be blocked"))
        self.assertFalse(game.has_keyword(ogre, "can't be blocked"))
        self.assertNotIn(tunnel, a.battlefield)
        self.assertIn(ESCAPE_TUNNEL, a.graveyard)


if __name__ == "__main__":
    unittest.main()
