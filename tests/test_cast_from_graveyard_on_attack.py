"""Bilbo, Thief in the Night: "Whenever Bilbo attacks, you may cast an artifact, instant, or sorcery spell from your graveyard. If an
instant or sorcery spell cast this way would be put into your graveyard, exile it instead." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, fire, lands, pick, real, table3

BILBO = real("Bilbo, Thief in the Night", "{1}{U}", "Legendary Creature — Halfling Rogue", "Spells you cast from anywhere other than "
             "your hand cost {1} less to cast.\nWhenever Bilbo attacks, you may cast an artifact, instant, or sorcery spell from your "
             "graveyard. If an instant or sorcery spell cast this way would be put into your graveyard, exile it instead.", "2", "2")
GAIN = Card(name="Gain", mana_cost="{2}", cmc=2.0, type_line="Sorcery", oracle_text="You gain 3 life.")
TRINKET = Card(name="Trinket", mana_cost="{2}", cmc=2.0, type_line="Artifact")


def attack(graveyard, mana, choice):
    game, _ = table3(pick("Yes", choice))
    a = game.seats[0]
    a.hand, a.graveyard, a.exile = [], list(graveyard), []
    bilbo = Permanent(BILBO)
    a.battlefield = [bilbo] + lands(mana)
    fire(game, a, bilbo, "attacks")
    return a


class BilboTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(BILBO), [])

    def test_a_sorcery_is_cast_for_its_cost_less_one_and_exiled(self):
        a = attack([GAIN], 1, "Gain")
        self.assertEqual(a.life, 43)
        self.assertEqual((a.graveyard, a.exile), ([], [GAIN]))

    def test_an_artifact_is_cast_onto_the_battlefield(self):
        a = attack([TRINKET], 1, "Trinket")
        self.assertIn("Trinket", [p.card.name for p in a.battlefield])
        self.assertEqual(a.graveyard, [])

    def test_a_creature_card_is_not_offered(self):
        a = attack([BEAR], 5, "Bear")
        self.assertEqual(a.graveyard, [BEAR])

    def test_a_spell_it_cannot_pay_for_is_not_offered(self):
        a = attack([GAIN], 0, "Gain")
        self.assertEqual((a.life, a.graveyard), (40, [GAIN]))


if __name__ == "__main__":
    unittest.main()
