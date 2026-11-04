""""Spells cost {1} more to cast." (Sphere of Resistance), "Noncreature spells ..." (Thalia), "Spells your opponents cast ..." (Grand
Arbiter Augustin IV). CR 601.2f: increases are added to the total cost before reductions."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, real, table3

SPHERE = real("Sphere of Resistance", "{2}", "Artifact", "Spells cost {1} more to cast.")
THALIA = real("Thalia, Guardian of Thraben", "{1}{W}", "Legendary Creature — Human Soldier", "First strike\nNoncreature spells cost {1} "
              "more to cast.", "2", "1")
AUGUSTIN = real("Grand Arbiter Augustin IV", "{2}{W}{U}", "Legendary Creature — Human Advisor", "White spells you cast cost {1} less to cast.\n"
                "Blue spells you cast cost {1} less to cast.\nSpells your opponents cast cost {1} more to cast.", "2", "3")
DIVINATION = real("Divination", "{2}{U}", "Sorcery", "Draw two cards.")
BEARS = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", "2", "2")


def castable(spell, taxer, mine=False, n=3):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    (a if mine else b).battlefield = [Permanent(taxer)]
    a.hand, a.battlefield = [spell], a.battlefield + lands(n)
    return CAST + spell.name in game.legal_actions(a)


class SpellTaxTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SPHERE, THALIA, AUGUSTIN):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_sphere_taxes_every_spell(self):
        self.assertFalse(castable(DIVINATION, SPHERE))
        self.assertTrue(castable(DIVINATION, SPHERE, n=4))
        self.assertFalse(castable(BEARS, SPHERE, n=2))

    def test_sphere_taxes_its_own_controller_too(self):
        self.assertFalse(castable(DIVINATION, SPHERE, mine=True))

    def test_thalia_taxes_noncreature_spells_only(self):
        self.assertFalse(castable(DIVINATION, THALIA))
        self.assertTrue(castable(BEARS, THALIA, n=2))

    def test_augustin_taxes_only_opponents(self):
        self.assertFalse(castable(DIVINATION, AUGUSTIN))
        self.assertTrue(castable(BEARS, AUGUSTIN, mine=True, n=2))


if __name__ == "__main__":
    unittest.main()
