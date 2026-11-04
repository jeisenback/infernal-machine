""""Each player may put an artifact, creature, enchantment, or land card from their hand onto the battlefield." (Show and Tell)."""

import unittest

from infernal_machine.game import CAST, NONE_TAKEN, SHOW_AND_TELL_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import BIG, FOREST, lands, real, run_stack, table3

SHOW = real("Show and Tell", "{2}{U}", "Sorcery", "Each player may put an artifact, creature, enchantment, or land card from their hand onto "
            "the battlefield.")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")
RING = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")


def answers(*per_seat):
    """Seat i takes `per_seat[i]` (a card name, or None for nothing) and records what it was offered."""
    offered = {}

    def policy_for(index):
        def policy(prompt, options):
            if SHOW_AND_TELL_PROMPT.matches(prompt):
                offered[index] = list(options)
                want = per_seat[index]
                return options.index(want) if want in options else options.index(NONE_TAKEN)
            return 0
        return policy
    return offered, [policy_for(i) for i in range(3)]


class ShowAndTellTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SHOW), [])

    def test_each_player_may_put_one(self):
        offered, policies = answers("Big", "Sol Ring", None)
        game, _ = table3(*policies)
        a, b, c = game.seats
        a.hand, a.battlefield = [SHOW, BIG, BOLT], lands(3)
        b.hand, c.hand = [RING, FOREST], [BIG]
        game._perform(a, CAST + SHOW.name)
        run_stack(game)
        self.assertEqual(offered[0], ["Big", NONE_TAKEN])  # an instant is not offered
        self.assertIn("Big", [p.card.name for p in a.battlefield])
        self.assertIn("Sol Ring", [p.card.name for p in b.battlefield])
        self.assertEqual((a.hand, b.hand, c.hand), ([BOLT], [FOREST], [BIG]))


if __name__ == "__main__":
    unittest.main()
