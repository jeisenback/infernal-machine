"""The one-off lines of issue #80 that no other card shares (Blossoming Bogbeast first). Lines are the cards' own Oracle text from
Scryfall; each has cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import activate, fire
from tests.test_triggers_80 import FOREST, RELIC, SHRINE, card

BOGBEAST = Card(name="Blossoming Bogbeast", mana_cost="{4}{G}", type_line="Creature — Beast", power="5", toughness="5",
                oracle_text="Whenever this creature attacks, you gain 2 life. Then creatures you control gain trample and get +X/+X "
                            "until end of turn, where X is the amount of life you gained this turn.")


class BlossomingBogbeastTests(unittest.TestCase):
    def attack(self, gained_before=0):
        game, _ = table3(pick())
        a = game.seats[0]
        self.beast, self.bear = Permanent(BOGBEAST), Permanent(BEAR)
        a.battlefield = [self.beast, self.bear]
        if gained_before:
            game.change_life(a, gained_before)
        fire(game, a, self.beast, "attacks")
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(BOGBEAST), [])

    def test_it_gains_two_life_and_every_creature_gets_plus_two(self):
        game, a = self.attack()
        self.assertEqual((a.life, game.power(self.beast), game.power(self.bear)), (42, 7, 4))
        self.assertTrue(game.has_keyword(self.bear, "trample"))

    def test_the_bonus_counts_all_the_life_gained_this_turn(self):
        game, a = self.attack(gained_before=3)
        self.assertEqual((game.power(self.beast), game.power(self.bear)), (10, 7))  # 3 + 2
