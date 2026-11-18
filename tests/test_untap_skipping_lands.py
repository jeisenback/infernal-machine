"""Issue #835: "{T}: Add {W} or {U}. This land doesn't untap during your next untap step." (Tempest's lands), from the cards' real Oracle
text. All ten cards whose only gap it was are fully playable. Cloudcrest Lake tapped for {W} stays tapped through its controller's next
untap step and untaps in the one after; tapped for generic mana (its {C}) it untaps as usual."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, real, run_stack, table3, untap_step, wording_unlocked
from tests.real import REAL

CARDS = ["Cloudcrest Lake", "Lantern-Lit Graveyard", "Waterveil Cavern", "Tranquil Garden", "Cinder Marsh", "Rootwater Depths",
         "Thalakos Lowlands", "Pinecrest Ridge", "Mogg Hollows", "Vec Townships"]
LAKE = REAL["Cloudcrest Lake"]
LIONS = real("Savannah Lions", "{W}", "Creature — Cat", "", "2", "1", colors=("W",))

# The guards these tests are there to catch (python tools/mutate.py tests.test_untap_skipping_lands).
MUTATIONS = [
    ("infernal_machine/payment.py", "and mana_skips_untap(s.permanent.card) and _painful(s, symbol)}", "and mana_skips_untap(s.permanent.card)}",
     "only the colored mana"),
    ("infernal_machine/payment.py", "            permanent.skips_next_untap = True\n", "            pass\n", "it stays tapped"),
    ("infernal_machine/payment.py", "and mana_skips_untap(s.permanent.card) and _painful(s, symbol)}", "and _painful(s, symbol)}",
     "only a land with the rider"),
]


def tapped_for(card):
    """Seat 0, with only Cloudcrest Lake, casts `card`; its next untap step begins."""
    game, _ = table3()
    a = game.seats[0]
    lake = Permanent(LAKE)
    a.hand, a.battlefield = [card], [lake]
    game._perform(a, CAST + card.name)
    run_stack(game)
    assert lake.tapped
    untap_step(game, a)
    return game, a, lake


class UntapSkippingLandTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_the_colored_mana_keeps_it_tapped_through_the_next_untap_step(self):
        game, a, lake = tapped_for(LIONS)
        self.assertTrue(lake.tapped)
        untap_step(game, a)
        self.assertFalse(lake.tapped)

    def test_its_colorless_mana_does_not(self):
        _, _, lake = tapped_for(BEAR)  # (a {1} spell)
        self.assertFalse(lake.tapped)

    def test_a_painland_with_no_such_rider_untaps(self):
        game, _ = table3()
        a = game.seats[0]
        land = Permanent(REAL["Adarkar Wastes"])  # ({T}: Add {W} or {U}. This land deals 1 damage to you.)
        a.hand, a.battlefield = [LIONS], [land]
        game._perform(a, CAST + LIONS.name)
        untap_step(game, a)
        self.assertFalse(land.tapped)


if __name__ == "__main__":
    unittest.main()
