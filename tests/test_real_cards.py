"""Behavior of real cards, with their exact Oracle text from `real_oracle_texts.json` (issue #97)."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.effects import activated_abilities
from infernal_machine.game import Permanent
from infernal_machine.game import OPENING_PROMPT
from tests.test_combat import BEAR
from tests.test_effects import lands, table
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


class LeylineOfTheVoidTests(unittest.TestCase):
    def setup_game(self, policy=None):
        game, a, b = table(policy, policy, library=(REAL["Leyline of the Void"],) * 20)
        game.setup()
        return game

    def test_it_may_begin_the_game_on_the_battlefield(self):
        game = self.setup_game()
        for seat in game.seats:
            self.assertEqual((len(seat.battlefield), len(seat.hand)), (7, 0))

    def test_the_player_may_keep_it_in_hand(self):
        game = self.setup_game(lambda prompt, options: 1 if prompt.startswith(OPENING_PROMPT) else 0)
        for seat in game.seats:
            self.assertEqual((len(seat.battlefield), len(seat.hand)), (0, 7))


class DinaTests(unittest.TestCase):
    def test_sacrificing_a_creature_gives_dina_its_power(self):
        game, _ = table3()
        a = game.seats[0]
        dina = Permanent(REAL["Dina, Soul Steeper"])
        ogre = Permanent(replace(BEAR, name="Ogre", power="4", toughness="4"))
        a.battlefield = [dina, ogre, *lands(1)]
        [ability] = [x for x in activated_abilities(dina.card) if x.sacrifice_other]
        game._activate(a, dina, ability)
        run_stack(game)
        self.assertEqual(game.power(dina), 1 + 4)
        self.assertNotIn(ogre, a.battlefield)
