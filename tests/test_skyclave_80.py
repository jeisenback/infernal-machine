"""Skyclave Apparition (issue #80): the card it exiled is paid back as a token when it leaves the battlefield.

Lines are the card's own Oracle text from Scryfall.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import creature
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire
from tests.test_x_targets import script

APPARITION = creature("Apparition", 2, 2,
                      "When this creature enters, exile up to one target nonland, nontoken permanent you don't control with "
                      "mana value 4 or less.\nWhen this creature leaves the battlefield, the exiled card's owner creates an "
                      "X/X blue Illusion creature token, where X is the mana value of the exiled card.")
GOLEM = Card(name="Golem", mana_cost="{3}", cmc=3.0, type_line="Artifact Creature — Golem", power="3", toughness="3")
TOKEN = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")


class SkyclaveTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3(script("Golem"))
        self.a, self.b, _ = self.game.seats
        self.apparition = Permanent(APPARITION)
        self.golem = Permanent(GOLEM)
        self.a.battlefield, self.b.battlefield = [self.apparition], [self.golem]

    def illusions(self, seat):
        return [p for p in seat.battlefield if p.card.name == "Illusion"]

    def test_parse(self):
        self.assertEqual(unsupported_lines(APPARITION), [])

    def test_the_owner_gets_a_token_as_big_as_the_exiled_card_when_it_leaves(self):
        fire(self.game, self.a, self.apparition, "enters")
        self.assertEqual(self.b.battlefield, [])
        self.game._leave_battlefield(self.apparition, "destroyed")
        run_stack(self.game)
        [token] = self.illusions(self.b)
        self.assertEqual((token.card.power, token.card.toughness, token.card.colors), ("3", "3", ("U",)))
        self.assertEqual(self.illusions(self.a), [])
        self.assertIn(GOLEM, self.b.exile)  # the card itself stays exiled

    def test_nothing_exiled_means_no_token(self):
        self.game._leave_battlefield(self.apparition, "destroyed")
        run_stack(self.game)
        self.assertEqual(self.illusions(self.b) + self.illusions(self.a), [])

    def test_a_token_exiled_has_no_mana_value_and_gives_no_token(self):
        self.b.battlefield = [Permanent(TOKEN)]
        fire(self.game, self.a, self.apparition, "enters")
        self.game._leave_battlefield(self.apparition, "destroyed")
        run_stack(self.game)
        self.assertEqual(self.illusions(self.b), [])
