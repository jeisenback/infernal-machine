"""Damage equal to the number of something you control, dealt by the source: Smaug the Magnificent (#564 row 12)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Amount, Damage, DefineX, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, fire, pick, real, table3

SMAUG = real("Smaug the Magnificent", "{2}{R}{R}", "Legendary Creature — Dragon", "Flying, haste\nWhenever Smaug attacks, he deals damage "
             "equal to the number of Treasures you control to any target.\nAt the beginning of your upkeep, create a Treasure token.", "4", "3")
JET = real("Jet, Freedom Fighter", "{1}{R}", "Legendary Creature — Human Rebel", "When Jet enters, he deals damage equal to the number "
           "of creatures you control to target creature an opponent controls.", "2", "2")
TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure")


def attack(treasures, their_treasures=0):
    """Smaug's attack trigger fires with that many Treasures on each side; the damage goes to player B."""
    game, _ = table3(pick("Player: B"))
    a, b, _ = game.seats
    smaug = Permanent(SMAUG)
    a.battlefield = [smaug] + [Permanent(TREASURE) for _ in range(treasures)]
    b.battlefield = [Permanent(BEAR)] + [Permanent(TREASURE) for _ in range(their_treasures)]
    before = b.life
    fire(game, a, smaug, "attacks")
    return before - b.life


class ParseTests(unittest.TestCase):
    def test_the_cards_are_read(self):
        for card in (SMAUG, JET):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertEqual(list(triggered_abilities(SMAUG)[0].effects), [DefineX(Amount("you_control", "Treasure")), Damage("X", "any")])
        self.assertEqual(list(triggered_abilities(JET)[0].effects),
                         [DefineX(Amount("you_control", "creature")), Damage("X", "creature an opponent controls")])

    def test_an_amount_the_grammar_does_not_know_leaves_the_line_unread(self):
        odd = real("Odd Dragon", "{R}", "Creature — Dragon", "Whenever this creature attacks, it deals damage equal to the brightness "
                                                           "of the moon to any target.", "1", "1")
        self.assertEqual(len(unsupported_lines(odd)), 1)


class DamageTests(unittest.TestCase):
    def test_damage_equal_to_your_treasures(self):
        self.assertEqual(attack(treasures=2), 2)

    def test_no_treasures_no_damage(self):
        self.assertEqual(attack(treasures=0), 0)

    def test_an_opponents_treasures_do_not_count(self):
        self.assertEqual(attack(treasures=1, their_treasures=3), 1)


if __name__ == "__main__":
    unittest.main()
