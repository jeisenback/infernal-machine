""""Target player can't cast spells this turn. If this spell was kicked, creatures can't attack this turn." (Orim's Chant)."""

import unittest

from infernal_machine.game import CAST, KICKER_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table3

CHANT = real("Orim's Chant", "{W}", "Instant", "Kicker {W} (You may pay an additional {W} as you cast this spell.)\nTarget player can't cast "
             "spells this turn. If this spell was kicked, creatures can't attack this turn.")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def chant(kick):
    def policy(prompt, options):
        if KICKER_PROMPT.matches(prompt):
            return 0 if kick else 1
        return next((i for i, o in enumerate(options) if o.startswith("Player: B")), 0)
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    bear = Permanent(BEAR)
    a.hand, a.battlefield = [CHANT], lands(2) + [bear]
    b.hand, b.battlefield = [BOLT], lands(1)
    game._perform(a, CAST + CHANT.name)
    run_stack(game)
    return game, b, bear


class OrimsChantTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(CHANT), [])

    def test_the_target_cannot_cast_spells_this_turn(self):
        game, b, _ = chant(kick=False)
        self.assertNotIn(CAST + BOLT.name, game.legal_actions(b))
        game.turn += 1
        self.assertIn(CAST + BOLT.name, game.legal_actions(b))

    def test_unkicked_creatures_still_attack(self):
        game, _, bear = chant(kick=False)
        self.assertTrue(game.combat._can_attack(bear))

    def test_kicked_no_creature_can_attack_this_turn(self):
        game, _, bear = chant(kick=True)
        self.assertFalse(game.combat._can_attack(bear))
        game.turn += 1
        self.assertTrue(game.combat._can_attack(bear))


if __name__ == "__main__":
    unittest.main()
