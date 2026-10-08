"""Behavior of real cards, with their exact Oracle text from `real_oracle_texts.json` (issue #97)."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.effects import activated_abilities
from infernal_machine.game import Permanent
from infernal_machine.game import MODE_PROMPT, OPENING_PROMPT
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


class BlinkmothNexusTests(unittest.TestCase):
    def test_it_pumps_a_blinkmoth_and_only_a_blinkmoth(self):
        game, _ = table3()
        a = game.seats[0]
        nexus = Permanent(REAL["Blinkmoth Nexus"])
        moth = Permanent(Card(name="Moth", type_line="Artifact Creature — Blinkmoth", power="1", toughness="1"))
        a.battlefield = [nexus, moth, Permanent(BEAR), *lands(1)]
        [ability] = [x for x in activated_abilities(nexus.card) if x.tap and x.mana_cost]
        options = [p for _, p in game.target_options("Blinkmoth creature", a)]
        self.assertEqual(options, [moth])


class CharmingPrinceTests(unittest.TestCase):
    def test_the_third_mode_blinks_a_creature_you_own_until_the_end_step(self):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Exile another")), 0)
                         if prompt.startswith(MODE_PROMPT) else 0)
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game._enter(a, Permanent(REAL["Charming Prince"]))
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Charming Prince"])
        self.assertEqual(a.exile, [BEAR])
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Bear", "Charming Prince"])
