""""This creature can't attack or block unless ..." (CR 508.1c, 509.1b), from the cards' real Oracle text: the condition is checked as
attackers and blockers are declared. Topiary Stomper needs seven lands, Wayward Swordtooth the city's blessing, Slumbering Dragon five
+1/+1 counters on itself; Felhide Brawler only can't block without another Minotaur, and attacks as usual."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, table

STOMPER = real("Topiary Stomper", "{1}{G}{G}", "Creature — Plant Dinosaur", "Vigilance (Attacking doesn't cause this creature to tap.)\nWhen "
               "this creature enters, search your library for a basic land card, put it onto the battlefield tapped, then shuffle.\nThis "
               "creature can't attack or block unless you control seven or more lands.", "4", "4", colors=("G",))
SWORDTOOTH = real("Wayward Swordtooth", "{2}{G}", "Creature — Dinosaur", "Ascend (If you control ten or more permanents, you get the city's "
                  "blessing for the rest of the game.)\nYou may play an additional land on each of your turns.\nThis creature can't attack or "
                  "block unless you have the city's blessing.", "5", "5", colors=("G",))
DRAGON = real("Slumbering Dragon", "{R}", "Creature — Dragon", "Flying\nThis creature can't attack or block unless it has five or more +1/+1 "
              "counters on it.\nWhenever a creature attacks you or a planeswalker you control, put a +1/+1 counter on this creature.", "3", "3",
              colors=("R",))
BRAWLER = real("Felhide Brawler", "{1}{B}", "Creature — Minotaur", "This creature can't block unless you control another Minotaur.", "2", "2",
               colors=("B",))
MINOTAUR = real("Minotaur Sureshot", "{2}{R}", "Creature — Minotaur Archer", "Reach (This creature can block creatures with flying.)\n{1}{R}: "
                "This creature gets +1/+0 until end of turn.", "2", "3", colors=("R",))
OKETRA = real("Oketra the True", "{3}{W}", "Legendary Creature — God", "Double strike, indestructible\nOketra can't attack or block unless you "
              "control at least three other creatures.\n{3}{W}: Create a 1/1 white Warrior creature token with vigilance.", "3", "6",
              colors=("W",))


def can_attack_and_block(card, extra=(), counters=0):
    game, _, _ = table()
    a = game.seats[0]
    creature = Permanent(card)
    creature.counters["+1/+1"] = counters
    a.battlefield = [creature, *extra]
    return game.combat._can_attack(creature), game.combat._can_block(creature, Permanent(BEAR)), game, a


class AttackBlockUnlessTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (STOMPER, SWORDTOOTH, DRAGON, BRAWLER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_condition_the_engine_cant_read_leaves_the_line_unread(self):
        self.assertEqual(unsupported_lines(OKETRA), ["CARDNAME can't attack or block unless you control at least three other creatures."])

    def test_topiary_stomper_needs_seven_lands(self):
        self.assertEqual(can_attack_and_block(STOMPER, lands(6))[:2], (False, False))
        self.assertEqual(can_attack_and_block(STOMPER, lands(7))[:2], (True, True))

    def test_wayward_swordtooth_needs_the_citys_blessing(self):
        self.assertEqual(can_attack_and_block(SWORDTOOTH)[:2], (False, False))
        game, _, _ = table()
        a = game.seats[0]
        a.citys_blessing = True
        tooth = Permanent(SWORDTOOTH)
        a.battlefield = [tooth]
        self.assertEqual((game.combat._can_attack(tooth), game.combat._can_block(tooth, Permanent(BEAR))), (True, True))

    def test_slumbering_dragon_counts_its_own_counters(self):
        self.assertEqual(can_attack_and_block(DRAGON, counters=4)[:2], (False, False))
        self.assertEqual(can_attack_and_block(DRAGON, counters=5)[:2], (True, True))

    def test_felhide_brawler_only_cant_block(self):
        self.assertEqual(can_attack_and_block(BRAWLER)[:2], (True, False))
        self.assertEqual(can_attack_and_block(BRAWLER, [Permanent(MINOTAUR)])[:2], (True, True))


if __name__ == "__main__":
    unittest.main()
