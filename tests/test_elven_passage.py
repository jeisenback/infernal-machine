""""{T}, Pay 1 life, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle. You
may behold an Elf. If you do, untap that land." (Elven Passage)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import ELF, FOREST, OGRE, activate, real, table3

PASSAGE = real("Elven Passage", "", "Land", "{T}, Pay 1 life, Sacrifice this land: Search your library for a basic land card, put it onto "
               "the battlefield tapped, then shuffle. You may behold an Elf. If you do, untap that land. (To behold an Elf, choose an Elf "
               "you control or reveal an Elf card from your hand.)")


def crack(hand, battlefield=()):
    game, _ = table3(lambda prompt, options: 0)
    a = game.seats[0]
    a.battlefield, a.library, a.hand = [Permanent(PASSAGE)] + [Permanent(c) for c in battlefield], [FOREST, FOREST], list(hand)
    activate(game, a, "Elven Passage")
    return [(p.card, p.tapped) for p in a.battlefield if p.card is FOREST]


class ElvenPassageTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(PASSAGE), [])

    def test_beholding_an_elf_untaps_the_land(self):
        self.assertEqual(crack([ELF]), [(FOREST, False)])

    def test_an_elf_you_control_counts(self):
        self.assertEqual(crack([], [ELF]), [(FOREST, False)])

    def test_without_an_elf_it_stays_tapped(self):
        self.assertEqual(crack([OGRE]), [(FOREST, True)])


if __name__ == "__main__":
    unittest.main()
