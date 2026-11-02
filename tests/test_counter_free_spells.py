"""Vexing Bauble: "Whenever a player casts a spell, if no mana was spent to cast it, counter that spell." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, real, run_stack, table3

BAUBLE = real("Vexing Bauble", "{1}", "Artifact", "Whenever a player casts a spell, if no mana was spent to cast it, counter that spell.\n"
              "{1}, {T}, Sacrifice this artifact: Draw a card.")
FREE = Card(name="Free Thing", mana_cost="{0}", type_line="Artifact")
PAID = Card(name="Paid Thing", mana_cost="{1}", cmc=1.0, type_line="Artifact")


def cast_by_opponent(card, mana):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(BAUBLE)]
    b.hand, b.battlefield, b.graveyard = [card], lands(mana), []
    game.active = 1
    game._perform(b, CAST + card.name)
    run_stack(game)
    return b


class VexingBaubleTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(BAUBLE), [])

    def test_a_spell_cast_without_mana_is_countered(self):
        b = cast_by_opponent(FREE, 0)
        self.assertEqual(b.graveyard, [FREE])
        self.assertFalse(any(p.card is FREE for p in b.battlefield))

    def test_a_spell_paid_for_with_mana_resolves(self):
        b = cast_by_opponent(PAID, 1)
        self.assertEqual(b.graveyard, [])
        self.assertTrue(any(p.card is PAID for p in b.battlefield))


if __name__ == "__main__":
    unittest.main()
