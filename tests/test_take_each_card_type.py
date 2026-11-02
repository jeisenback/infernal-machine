"""Atraxa, Grand Unifier: "When Atraxa enters, reveal the top ten cards of your library. For each card type, you may put a card of that
type from among the revealed cards into your hand. Put the rest on the bottom of your library in a random order." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import NONE_TAKEN, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, real, run_stack, script, table3

ATRAXA = real("Atraxa, Grand Unifier", "{3}{G}{W}{U}{B}", "Legendary Creature — Phyrexian Angel", "Flying, vigilance, deathtouch, "
              "lifelink\nWhen Atraxa enters, reveal the top ten cards of your library. For each card type, you may put a card of that type "
              "from among the revealed cards into your hand. Put the rest on the bottom of your library in a random order. (Artifact, "
              "battle, creature, enchantment, instant, land, planeswalker, and sorcery are card types.)", "7", "7")
SHOCK = Card(name="Shock", mana_cost="{R}", type_line="Instant", oracle_text="Shock deals 2 damage to any target.")
GOLEM = Card(name="Golem", mana_cost="{3}", type_line="Artifact Creature — Golem", power="3", toughness="3")
FILLER = Card(name="Filler", mana_cost="{1}", type_line="Sorcery", oracle_text="Draw a card.")


def enters(library, *answers):
    game, _ = table3(script(*answers))  # by default the first card offered for each type
    a = game.seats[0]
    a.hand, a.library = [], list(library)
    game._enter(a, Permanent(ATRAXA))
    run_stack(game)
    return a


class AtraxaTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(ATRAXA), [])

    def test_one_card_of_each_type(self):
        a = enters([BEAR, RELIC, FOREST, SHOCK, FILLER, OGRE, FOREST, SHOCK, FILLER, RELIC, OGRE])
        self.assertEqual(sorted(c.name for c in a.hand), ["Bear", "Filler", "Forest", "Relic", "Shock"])
        self.assertEqual(a.library[0], OGRE)  # the eleventh card; the other five revealed ones went to the bottom
        self.assertEqual(len(a.library), 6)

    def test_declining_one_type_still_offers_the_next(self):
        a = enters([RELIC, BEAR, FOREST], NONE_TAKEN)  # no artifact; then a creature and a land
        self.assertEqual(sorted(c.name for c in a.hand), ["Bear", "Forest"])

    def test_a_card_with_two_types_is_taken_for_one(self):
        a = enters([GOLEM, FOREST])
        self.assertEqual(sorted(c.name for c in a.hand), ["Forest", "Golem"])


if __name__ == "__main__":
    unittest.main()
