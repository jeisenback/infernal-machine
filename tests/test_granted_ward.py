"""Hexing Squelcher: "Other creatures you control have "Ward—Pay 2 life."" """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, run_stack, table3

SQUELCHER = real("Hexing Squelcher", "{1}{R}", "Creature — Goblin Sorcerer", "This spell can't be countered.\nWard—Pay 2 life.\n"
                 "Spells you control can't be countered.\nOther creatures you control have \"Ward—Pay 2 life.\"", "2", "2")
MURDER = Card(name="Murder", mana_cost="{B}", cmc=1.0, type_line="Instant", oracle_text="Destroy target creature.")


def table(squelcher=True):
    game, _ = table3(None, pick("Bear", "Yes", "Pay"))
    a, b = game.seats[0], game.seats[1]
    bear = Permanent(BEAR)
    a.battlefield = [bear] + ([Permanent(SQUELCHER)] if squelcher else [])
    b.hand, b.battlefield = [MURDER], lands(1)
    return game, a, b, bear


class HexingSquelcherTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SQUELCHER), [])

    def test_other_creatures_have_its_ward(self):
        game, _, _, bear = table()
        self.assertEqual(game.ward_of(bear), "Pay 2 life")
        game, _, _, bear = table(squelcher=False)
        self.assertIsNone(game.ward_of(bear))

    def test_an_opponent_targeting_one_pays_two_life(self):
        game, a, b, bear = table()
        game.active = 1
        game._perform(b, CAST + MURDER.name)
        run_stack(game)
        self.assertEqual(b.life, 38)
        self.assertFalse(game.on_battlefield(bear))


if __name__ == "__main__":
    unittest.main()
