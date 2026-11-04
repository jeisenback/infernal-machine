""""Whenever you cast an artifact spell, create a 1/1 colorless Drone artifact creature token with flying and "This token can block only
creatures with flying."" (Pinnacle Emissary)."""

import unittest

from infernal_machine.effects import combat_restrictions
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, RELIC, lands, real, run_stack, table3

EMISSARY = real("Pinnacle Emissary", "{1}{U}{R}", "Artifact Creature — Robot", "Whenever you cast an artifact spell, create a 1/1 colorless "
                "Drone artifact creature token with flying and \"This token can block only creatures with flying.\"\nWarp {U/R} (You may "
                "cast this card from your hand for its warp cost. Exile this creature at the beginning of the next end step, then you may "
                "cast it from exile on a later turn.)", "3", "3", colors=("R", "U"))


def cast(card):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.battlefield = [card], [Permanent(EMISSARY)] + lands(2)
    game.active, game.step = 0, "main1"
    game._perform(a, CAST + card.name)
    run_stack(game)
    return [p for p in a.battlefield if p.card.name == "Drone"]


class PinnacleEmissaryTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(EMISSARY), [])

    def test_an_artifact_spell_makes_a_flying_drone_that_blocks_only_fliers(self):
        drones = cast(RELIC)
        self.assertEqual(len(drones), 1)
        self.assertIn("Flying", drones[0].card.oracle_text)
        self.assertEqual([r.kind for r in combat_restrictions(drones[0].card)], ["block_only_flying"])

    def test_another_spell_makes_none(self):
        self.assertEqual(cast(BEAR), [])


if __name__ == "__main__":
    unittest.main()
