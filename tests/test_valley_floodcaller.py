"""Valley Floodcaller, from its real Oracle text: "You may cast noncreature spells as though they had flash." (not creature spells, and
not without it) and "Whenever you cast a noncreature spell, Birds, Frogs, Otters, and Rats you control get +1/+1 until end of turn. Untap
them." (any of the four types; a creature of another type is left alone)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, DIVINATION, FOREST, lands, real, run_stack, table3

FLOODCALLER = real("Valley Floodcaller", "{2}{U}", "Creature — Otter Wizard", "Flash\nYou may cast noncreature spells as though they had flash.\n"
                   "Whenever you cast a noncreature spell, Birds, Frogs, Otters, and Rats you control get +1/+1 until end of turn. Untap them.",
                   "2", "2", colors=("U",))
FROG = Card(name="Frog", type_line="Creature — Frog", power="1", toughness="1", mana_cost="{U}")


class FloodcallerTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(FLOODCALLER), [])

    def test_noncreature_spells_have_flash(self):
        game, _ = table3()
        a = game.seats[0]
        self.assertFalse(game._instant_speed(a, DIVINATION))
        a.battlefield = [Permanent(FLOODCALLER)]
        self.assertEqual((game._instant_speed(a, DIVINATION), game._instant_speed(a, BEAR)), (True, False))

    def test_a_noncreature_spell_pumps_and_untaps_its_kinds(self):
        game, _ = table3()
        a = game.seats[0]
        floodcaller, frog, bear = Permanent(FLOODCALLER, tapped=True), Permanent(FROG, tapped=True), Permanent(BEAR, tapped=True)
        a.battlefield, a.library = [floodcaller, frog, bear, *lands(3)], [FOREST] * 3
        a.hand = [DIVINATION]
        game._perform(a, CAST + DIVINATION.name)
        run_stack(game)
        self.assertEqual(([game.power(p) for p in (floodcaller, frog, bear)], [p.tapped for p in (floodcaller, frog, bear)]),
                         ([3, 2, 2], [False, False, True]))


if __name__ == "__main__":
    unittest.main()
