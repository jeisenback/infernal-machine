"""Vigorbloom Vanguard and Heartwood Crafter, the last plain lines of issue #85, from their Oracle text on Scryfall.

Each has a case where the condition is false: a creature without a +1/+1 counter, and mana that may not pay for a spell
cast from hand.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import mana_restriction
from infernal_machine.game import CAST, CAST_COMMANDER, Permanent
from infernal_machine.mana import parse_cost
from infernal_machine.report import unsupported_lines
from tests.test_combat import creature
from tests.test_effects import FOREST, table

VANGUARD = creature("Vanguard", 2, 2, "Each creature you control with a +1/+1 counter on it has vigilance.")
CRAFTER = creature("Crafter", 1, 1, "{T}: Add {C}. This mana can't be spent to cast spells from your hand.")
BEAR = creature("Cub", 2, 2)
ONE_DROP = Card(name="One Drop", mana_cost="{1}", cmc=1.0, type_line="Sorcery", oracle_text="Draw a card.")
TWO_DROP = Card(name="Two Drop", mana_cost="{2}", cmc=2.0, type_line="Sorcery", oracle_text="Draw a card.")
COMMANDER = Card(name="Cheap Commander", mana_cost="{1}", cmc=1.0, type_line="Legendary Creature — Elf", power="1", toughness="1")


class VigorbloomVanguardTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats
        self.vanguard = Permanent(VANGUARD)
        self.a.battlefield = [self.vanguard]

    def vigilant(self, permanent):
        return self.game.has_keyword(permanent, "vigilance")

    def test_parse(self):
        self.assertEqual(unsupported_lines(VANGUARD), [])

    def test_a_creature_with_a_plus_one_counter_has_vigilance(self):
        bear = Permanent(BEAR, counters={"+1/+1": 1})
        self.a.battlefield.append(bear)
        self.assertTrue(self.vigilant(bear))

    def test_a_creature_without_one_does_not(self):
        bear = Permanent(BEAR)
        self.a.battlefield.append(bear)
        self.assertFalse(self.vigilant(bear))

    def test_another_kind_of_counter_does_not_count(self):
        bear = Permanent(BEAR, counters={"charge": 2})
        self.a.battlefield.append(bear)
        self.assertFalse(self.vigilant(bear))

    def test_an_opponents_creature_does_not_get_it(self):
        bear = Permanent(BEAR, counters={"+1/+1": 1})
        self.b.battlefield = [bear]
        self.assertFalse(self.vigilant(bear))

    def test_the_vanguard_itself_counts_once_it_has_a_counter(self):
        self.assertFalse(self.vigilant(self.vanguard))
        self.vanguard.counters["+1/+1"] = 1
        self.assertTrue(self.vigilant(self.vanguard))

    def test_the_counter_going_away_ends_it(self):
        bear = Permanent(BEAR, counters={"+1/+1": 1})
        self.a.battlefield.append(bear)
        bear.counters.clear()
        self.assertFalse(self.vigilant(bear))


class HeartwoodCrafterTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a = self.game.seats[0]
        self.game.active, self.game.step = 0, "main1"
        self.crafter = Permanent(CRAFTER, sick=False)

    def actions(self):
        return self.game.legal_actions(self.a)

    def test_parse(self):
        self.assertEqual(unsupported_lines(CRAFTER), [])
        self.assertEqual(mana_restriction(CRAFTER), "not_from_hand")

    def test_its_mana_cannot_cast_a_spell_from_hand(self):
        self.a.battlefield, self.a.hand = [self.crafter], [ONE_DROP]
        self.assertNotIn(CAST + "One Drop", self.actions())

    def test_a_spell_from_hand_needs_other_mana(self):
        self.a.battlefield, self.a.hand = [self.crafter, Permanent(FOREST)], [TWO_DROP]
        self.assertNotIn(CAST + "Two Drop", self.actions())  # the Forest alone is one short
        self.a.battlefield.append(Permanent(FOREST))
        self.assertIn(CAST + "Two Drop", self.actions())

    def test_its_mana_can_cast_a_spell_from_the_command_zone(self):
        self.a.battlefield, self.a.command_zone = [self.crafter], [COMMANDER]
        self.assertIn(CAST_COMMANDER + "Cheap Commander", self.actions())

    def test_its_mana_can_pay_for_an_ability(self):
        self.a.battlefield = [self.crafter]
        self.assertIsNotNone(self.game._pay_cost(self.a, parse_cost("{1}")))
