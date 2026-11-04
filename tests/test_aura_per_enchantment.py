""""Enchanted creature gets +1/+1 for each enchantment you control and has first strike." (Ethereal Armor), "... +2/+2 for each other
enchantment on the battlefield." (Ancestral Mask), "... +1/+1 for each +1/+1 counter on this Aura and has reach and trample." (Nyxborn
Hydra, bestowed)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, SHRINE, real, table3

ARMOR = real("Ethereal Armor", "{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +1/+1 for each enchantment you control "
             "and has first strike.")
MASK = real("Ancestral Mask", "{2}{G}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +2/+2 for each other enchantment "
            "on the battlefield.")

HYDRA = real("Nyxborn Hydra", "{X}{G}", "Enchantment Creature — Hydra", "Bestow {X}{G}{G} (If you cast this card for its bestow cost, it's "
             "an Aura spell with enchant creature. It becomes a creature again if it's not attached.)\nReach, trample\nThis permanent "
             "enters with X +1/+1 counters on it.\nEnchanted creature gets +1/+1 for each +1/+1 counter on this Aura and has reach and "
             "trample.", "0", "1")


def enchanted(aura, mine=(), theirs=()):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    bear, attached = Permanent(BEAR), Permanent(aura)
    attached.attached_to = bear
    a.battlefield = [bear, attached] + [Permanent(card) for card in mine]
    b.battlefield = [Permanent(card) for card in theirs]
    return game, bear


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (ARMOR, MASK, HYDRA):
            self.assertEqual(unsupported_lines(card), [], card.name)


class EtherealArmorTests(unittest.TestCase):
    def test_it_counts_the_enchantments_you_control_itself_included(self):
        game, bear = enchanted(ARMOR, mine=[SHRINE], theirs=[SHRINE, SHRINE])
        self.assertEqual((game.power(bear), game.toughness(bear)), (4, 4))
        self.assertTrue(game.has_keyword(bear, "first strike"))


class AncestralMaskTests(unittest.TestCase):
    def test_it_counts_every_other_enchantment(self):
        game, bear = enchanted(MASK, mine=[SHRINE], theirs=[SHRINE])
        self.assertEqual((game.power(bear), game.toughness(bear)), (6, 6))

    def test_alone_it_gives_nothing(self):
        game, bear = enchanted(MASK)
        self.assertEqual(game.power(bear), 2)


class NyxbornHydraTests(unittest.TestCase):
    def test_it_counts_the_counters_on_the_aura(self):
        game, _ = table3()
        a = game.seats[0]
        bear, hydra = Permanent(BEAR), Permanent(HYDRA)
        hydra.attached_to, hydra.counters["+1/+1"] = bear, 3
        a.battlefield = [bear, hydra]
        self.assertEqual((game.power(bear), game.toughness(bear)), (5, 5))
        self.assertTrue(game.has_keyword(bear, "trample") and game.has_keyword(bear, "reach"))


if __name__ == "__main__":
    unittest.main()
