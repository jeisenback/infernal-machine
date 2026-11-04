""""When this creature enters, you may exile a creature card from your graveyard. If you do, exile target artifact or enchantment an
opponent controls." (Masked Vandal)."""

import unittest

from infernal_machine.game import EXILE_COST_PROMPT, NONE_TAKEN, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, enter, real, run_stack, table3

VANDAL = real("Masked Vandal", "{1}{G}", "Creature — Shapeshifter", "Changeling (This card is every creature type.)\nWhen this creature "
              "enters, you may exile a creature card from your graveyard. If you do, exile target artifact or enchantment an opponent "
              "controls.", "1", "3")
RING = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")


def vandal(graveyard, exile=True):
    def policy(prompt, options):
        if EXILE_COST_PROMPT.matches(prompt):
            return 0 if exile else options.index(NONE_TAKEN)
        return 0
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    ring = Permanent(RING)
    a.graveyard, b.battlefield = list(graveyard), [ring]
    enter(game, a, VANDAL)
    run_stack(game)
    return a, b


class MaskedVandalTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(VANDAL), [])

    def test_exiling_a_creature_card_exiles_their_artifact(self):
        a, b = vandal([BEAR, FOREST])
        self.assertEqual((a.graveyard, a.exile), ([FOREST], [BEAR]))
        self.assertEqual((b.battlefield, b.exile), ([], [RING]))

    def test_without_a_creature_card_nothing_happens(self):
        a, b = vandal([FOREST])
        self.assertEqual(len(b.battlefield), 1)

    def test_declining_keeps_both(self):
        a, b = vandal([BEAR], exile=False)
        self.assertEqual((a.graveyard, len(b.battlefield)), ([BEAR], 1))


if __name__ == "__main__":
    unittest.main()
