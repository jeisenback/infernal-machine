"""Looking at the top cards and putting an Aura or Equipment onto the battlefield (issue #80): Armored Skyhunter first.

Lines are the cards' own Oracle text from Scryfall. Each has cases where nothing is put onto the battlefield.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire
from tests.test_triggers_80 import FOREST, RELIC, card

SKYHUNTER = card("Flying\nWhenever this creature attacks, look at the top six cards of your library. You may put an Aura or "
                 "Equipment card from among them onto the battlefield. If an Equipment is put onto the battlefield this way, "
                 "you may attach it to a creature you control. Put the rest of those cards on the bottom of your library in a "
                 "random order.", "Skyhunter", "Creature — Cat Knight")
BOON = Card(name="Boon", mana_cost="{1}{W}", type_line="Enchantment — Aura", oracle_text="Enchant creature\nEnchanted creature gets +1/+1.")
SWORD = Card(name="Sword", mana_cost="{2}", type_line="Artifact — Equipment", oracle_text="Equipped creature gets +2/+0.\nEquip {2}")
BLIGHT = Card(name="Blight", mana_cost="{1}{B}", type_line="Enchantment — Aura", oracle_text="Enchant land\nEnchanted land has \"{T}: Add {B}.\"")


class SkyhunterTests(unittest.TestCase):
    def attack(self, top, *choices, lands=False):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.hunter = Permanent(SKYHUNTER)
        self.bear = Permanent(BEAR)
        a.battlefield = [self.hunter, self.bear]
        a.library = list(top) + [FOREST] * 10
        fire(game, a, self.hunter, "attacks")
        return a

    def names(self, seat):
        return sorted(p.card.name for p in seat.battlefield)

    def test_parse(self):
        self.assertEqual(unsupported_lines(SKYHUNTER), [])

    def test_an_aura_enters_attached_to_a_creature(self):
        a = self.attack([FOREST, BOON, FOREST, FOREST, FOREST, FOREST], "Boon", "Bear")
        boon = next(p for p in a.battlefield if p.card.name == "Boon")
        self.assertIs(boon.attached_to, self.bear)
        self.assertEqual(len(a.library), 15)  # 16 cards, one taken; the rest went underneath

    def test_an_equipment_enters_and_may_be_attached(self):
        a = self.attack([SWORD, FOREST, FOREST, FOREST, FOREST, FOREST], "Sword", "Bear")
        sword = next(p for p in a.battlefield if p.card.name == "Sword")
        self.assertIs(sword.attached_to, self.bear)

    def test_an_equipment_may_stay_unattached(self):
        a = self.attack([SWORD, FOREST, FOREST, FOREST, FOREST, FOREST], "Sword", "Don't")
        sword = next(p for p in a.battlefield if p.card.name == "Sword")
        self.assertIsNone(sword.attached_to)

    def test_taking_none_puts_everything_underneath(self):
        a = self.attack([BOON, FOREST, FOREST, FOREST, FOREST, FOREST], "Take none")
        self.assertEqual(self.names(a), ["Bear", "Skyhunter"])
        self.assertEqual(len(a.library), 16)

    def test_no_aura_or_equipment_among_them_does_nothing(self):
        a = self.attack([FOREST, RELIC, FOREST, FOREST, FOREST, FOREST], "Relic")
        self.assertEqual(self.names(a), ["Bear", "Skyhunter"])
        self.assertEqual(len(a.library), 16)

    def test_only_the_top_six_are_looked_at(self):
        a = self.attack([FOREST] * 6 + [BOON], "Boon")
        self.assertEqual(self.names(a), ["Bear", "Skyhunter"])

    def test_an_aura_with_nothing_to_enchant_is_not_offered(self):
        a = self.attack([BLIGHT, FOREST, FOREST, FOREST, FOREST, FOREST], "Blight")
        self.assertEqual(self.names(a), ["Bear", "Skyhunter"])
        self.assertEqual(len(a.library), 16)
