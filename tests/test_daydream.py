""""Exile target creature you control, then return that card to the battlefield under its owner's control with a +1/+1 counter on it."
(Daydream)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table3

DAYDREAM = real("Daydream", "{W}", "Sorcery", "Exile target creature you control, then return that card to the battlefield under its "
                "owner's control with a +1/+1 counter on it.\nFlashback {2}{W} (You may cast this card from your graveyard for its "
                "flashback cost. Then exile it.)")
CLOUDSHIFT = real("Cloudshift", "{W}", "Instant", "Exile target creature you control, then return that card to the battlefield under "
                  "your control.")


def blink(spell):
    game, _ = table3()
    a = game.seats[0]
    bear = Permanent(BEAR)
    bear.damage = 1
    a.hand, a.battlefield = [spell], [bear] + lands(1)
    game._perform(a, CAST + spell.name)
    run_stack(game)
    return next(p for p in a.battlefield if p.card is BEAR), bear


class DaydreamTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(DAYDREAM), [])

    def test_it_comes_back_new_with_a_counter(self):
        back, old = blink(DAYDREAM)
        self.assertIsNot(back, old)
        self.assertEqual((back.counters.get("+1/+1"), back.damage), (1, 0))

    def test_cloudshift_gives_no_counter(self):
        back, _ = blink(CLOUDSHIFT)
        self.assertEqual(back.counters.get("+1/+1", 0), 0)


if __name__ == "__main__":
    unittest.main()
