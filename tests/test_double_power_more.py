"""Doubling power with a trigger or a count: Grunn, the Lonely King (attacks alone), Thrakkus the Butcher (each Dragon you control),
Exponential Growth (X times) and Dragonclaw Strike (then it fights)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, real, run_stack, script, table

GRUNN = real("Grunn, the Lonely King", "{4}{G}{G}", "Legendary Creature — Ape Warrior", "Kicker {3} (You may pay an additional {3} as you cast "
             "this spell.)\nIf Grunn was kicked, it enters with five +1/+1 counters on it.\nWhenever Grunn attacks alone, double its power and "
             "toughness until end of turn.", "5", "5")
THRAKKUS = real("Thrakkus the Butcher", "{3}{R}{G}", "Legendary Creature — Dragon Peasant", "Trample\nWhenever Thrakkus attacks, double the "
                "power of each Dragon you control until end of turn.", "3", "4")
GROWTH = real("Exponential Growth", "{X}{X}{G}{G}", "Sorcery", "Until end of turn, double target creature's power X times.")
STRIKE = real("Dragonclaw Strike", "{2/G}{2/U}{2/R}", "Sorcery", "Double the power and toughness of target creature you control until end of turn. "
              "Then it fights up to one target creature an opponent controls. (Each deals damage equal to its power to the other.)")
WYRM = real("Wyrm", "{4}{R}", "Creature — Dragon", "", "4", "4")
ATTACK_ALL = lambda prompt, options: 1 if prompt.startswith("Attack") and len(options) > 1 else 0


def attack(*creatures):
    game, _, _ = table(ATTACK_ALL)
    a, b = game.seats
    a.battlefield = [Permanent(c, sick=False) for c in creatures]
    game.combat.declare_attackers(a)
    run_stack(game)
    return game, a.battlefield


class DoublePowerMoreTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GRUNN, THRAKKUS, GROWTH, STRIKE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_attacking_alone_doubles_power_and_toughness(self):
        game, (grunn,) = attack(GRUNN)
        self.assertEqual((game.power(grunn), game.toughness(grunn)), (10, 10))

    def test_not_when_something_attacks_with_it(self):
        game, (grunn, bear) = attack(GRUNN, BEAR)
        self.assertEqual((game.power(grunn), game.toughness(grunn)), (5, 5))

    def test_each_dragon_you_control_has_its_power_doubled(self):
        game, (thrakkus, wyrm, ogre) = attack(THRAKKUS, WYRM, OGRE)
        self.assertEqual((game.power(thrakkus), game.toughness(thrakkus)), (6, 4))  # Thrakkus is a Dragon too; toughness stays
        self.assertEqual((game.power(wyrm), game.power(ogre)), (8, 3))

    def test_doubled_x_times(self):
        for x, power in ((0, 3), (1, 6), (2, 12), (3, 24)):
            ogre = Permanent(OGRE)
            t = Table(GROWTH, policy=script(str(x), "Ogre"), n=2 * x + 2, mine=[ogre])
            t.cast()
            self.assertEqual(t.game.power(ogre), power, x)

    def test_then_it_fights_the_creature_it_doubled(self):
        ogre, theirs = Permanent(OGRE), Permanent(BEAR)
        t = Table(STRIKE, policy=script("Ogre", "Bear"), n=6, mine=[ogre], theirs=[theirs])
        t.cast()
        self.assertEqual((t.game.power(ogre), t.game.toughness(ogre)), (6, 6))
        self.assertEqual(ogre.damage, 2)  # the Bear hit back with its power
        self.assertNotIn(theirs, t.b.battlefield)  # 6 damage to a 2/2

    def test_fighting_is_up_to_one_target(self):
        ogre = Permanent(OGRE)
        t = Table(STRIKE, policy=script("Ogre"), n=6, mine=[ogre])
        t.cast()
        self.assertEqual((t.game.power(ogre), ogre.damage), (6, 0))


if __name__ == "__main__":
    unittest.main()
