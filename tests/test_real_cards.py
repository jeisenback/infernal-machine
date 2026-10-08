"""Behavior of real cards, with their exact Oracle text from `real_oracle_texts.json` (issue #97)."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from tests.test_combat import BEAR
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.real import REAL

WHITE_BEAR = replace(BEAR, name="White Bear", colors=("W",))


class CrusadeTests(unittest.TestCase):
    def test_every_white_creature_gets_the_bonus_whoever_controls_it(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        mine, theirs, other = Permanent(WHITE_BEAR), Permanent(WHITE_BEAR), Permanent(BEAR)
        a.battlefield, b.battlefield = [Permanent(REAL["Crusade"]), mine, other], [theirs]
        self.assertEqual([game.power(p) for p in (mine, theirs, other)], [3, 3, 2])
        a.battlefield.pop(0)
        self.assertEqual(game.power(mine), 2)


class GoodFortuneUnicornTests(unittest.TestCase):
    def test_another_creature_you_control_enters_with_a_counter(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(REAL["Good-Fortune Unicorn"])]
        bear = Permanent(BEAR)
        game._enter(a, bear)
        run_stack(game)
        self.assertEqual(bear.counters, {"+1/+1": 1})
