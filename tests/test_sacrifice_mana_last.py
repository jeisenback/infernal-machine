"""A payment spends a Treasure or an Eldrazi Spawn only when nothing else will pay (issue #302): a Spawn can only make {C}, so the
payer used to take it first for generic mana and leave lands untapped."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from tests.helpers import lands, real, table3

TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure", oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")
SPAWN = Card(name="Eldrazi Spawn", type_line="Token Creature — Eldrazi Spawn", power="0", toughness="1",
             oracle_text="Sacrifice this token: Add {C}.")
SPELL = real("Costly Test", "{1}{B}{G}", "Sorcery", "")


def paid(*battlefield):
    """The names of what pays for SPELL on a table with these permanents (lands first), in tap order."""
    game, _ = table3()
    a = game.seats[0]
    a.battlefield = [p if isinstance(p, Permanent) else Permanent(p, sick=False) for p in battlefield]
    payment = game._payment(a, SPELL)
    return None if payment is None else [p.card.name for p in payment]


class SacrificeLastTests(unittest.TestCase):
    def test_lands_pay_before_a_spawn(self):
        self.assertEqual(paid(*lands(3), SPAWN), ["City of Brass"] * 3)

    def test_lands_pay_before_a_treasure(self):
        self.assertEqual(paid(*lands(3), TREASURE), ["City of Brass"] * 3)

    def test_a_spawn_pays_when_the_lands_fall_short(self):
        self.assertEqual(sorted(paid(*lands(2), SPAWN)), ["City of Brass", "City of Brass", "Eldrazi Spawn"])

    def test_both_pay_when_both_are_needed(self):
        self.assertEqual(sorted(paid(*lands(1), SPAWN, TREASURE)), ["City of Brass", "Eldrazi Spawn", "Treasure"])

    def test_it_is_still_unpayable_when_even_the_sacrifices_fall_short(self):
        self.assertIsNone(paid(*lands(1), SPAWN))

    def test_a_treasure_is_spent_before_life_with_channel(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = lands(2) + [Permanent(TREASURE, sick=False)]
        a.life_mana_turn = game.turn
        payment = game._payment(a, SPELL)
        self.assertEqual((sorted(p.card.name for p in payment), payment.life), (["City of Brass", "City of Brass", "Treasure"], 0))


if __name__ == "__main__":
    unittest.main()
