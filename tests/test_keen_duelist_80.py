"""Keen Duelist (issue #80): both players reveal the top card, lose life equal to the other's, and take the card.

The line is the card's own Oracle text from Scryfall.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import creature
from tests.test_mass_effects import table3
from tests.test_prepare_85 import fire
from tests.test_x_targets import script

DUELIST = creature("Duelist", 3, 2, "First strike\nAt the beginning of your upkeep, you and target opponent each reveal the top "
                   "card of your library. You each lose life equal to the mana value of the card revealed by the other player. "
                   "You each put the card you revealed into your hand.")


def card(name, cmc):
    return Card(name=name, mana_cost="{1}", cmc=float(cmc), type_line="Sorcery")


class KeenDuelistTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3(script("Player: B"))
        self.a, self.b, self.c = self.game.seats
        self.duelist = Permanent(DUELIST)
        self.a.battlefield = [self.duelist]
        self.mine, self.theirs = card("Mine", 2), card("Theirs", 5)
        self.a.library, self.b.library = [self.mine, card("Under", 9)], [self.theirs, card("Below", 9)]

    def test_parse(self):
        self.assertEqual(unsupported_lines(DUELIST), [])

    def test_each_loses_life_equal_to_the_other_players_card(self):
        before = (self.a.life, self.b.life, self.c.life)
        fire(self.game, self.a, self.duelist, "upkeep")
        self.assertEqual((self.a.life, self.b.life, self.c.life), (before[0] - 5, before[1] - 2, before[2]))

    def test_each_puts_the_revealed_card_into_hand(self):
        fire(self.game, self.a, self.duelist, "upkeep")
        self.assertIn(self.mine, self.a.hand)  # each takes back the card they revealed
        self.assertIn(self.theirs, self.b.hand)
        self.assertEqual([c.name for c in self.a.library], ["Under"])

    def test_an_empty_library_reveals_nothing(self):
        self.b.library = []
        before = (self.a.life, self.b.life)
        fire(self.game, self.a, self.duelist, "upkeep")
        self.assertEqual((self.a.life, self.b.life), (before[0], before[1] - 2))
