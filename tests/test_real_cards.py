"""Behavior of real cards, with their exact Oracle text from `real_oracle_texts.json` (issue #97)."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
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


class BenevolentHydraTests(unittest.TestCase):
    def test_other_creatures_get_one_more_counter_but_not_the_hydra(self):
        game, _ = table3()
        a = game.seats[0]
        hydra, bear = Permanent(REAL["Benevolent Hydra"]), Permanent(BEAR)
        a.battlefield = [hydra, bear]
        game.put_counters(bear, "+1/+1", 1)
        game.put_counters(hydra, "+1/+1", 1)
        self.assertEqual((bear.counters, hydra.counters), ({"+1/+1": 2}, {"+1/+1": 1}))


class StaffOfTheStorytellerTests(unittest.TestCase):
    def test_creating_creature_tokens_adds_a_story_counter(self):
        game, _ = table3()
        a = game.seats[0]
        staff = Permanent(REAL["Staff of the Storyteller"])
        game._enter(a, staff)  # its own Spirit token is the first one
        run_stack(game)
        self.assertEqual(staff.counters, {"story": 1})
        game.create_tokens(a, Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1"), 3)
        run_stack(game)
        self.assertEqual(staff.counters, {"story": 2})  # once for the whole batch
        game.create_tokens(a, Card(name="Treasure", type_line="Token Artifact — Treasure"), 1)
        run_stack(game)
        self.assertEqual(staff.counters, {"story": 2})


class MistveilPlainsTests(unittest.TestCase):
    def test_a_card_from_the_graveyard_goes_to_the_bottom_of_the_library(self):
        game, _ = table3()
        a = game.seats[0]
        white = replace(BEAR, colors=("W",))
        a.battlefield = [Permanent(REAL["Mistveil Plains"]), Permanent(white), Permanent(white), *lands(1)]
        a.graveyard, a.library = [BEAR], [Card(name="Top"), Card(name="Bottom")]
        [ability] = [x for x in activated_abilities(REAL["Mistveil Plains"]) if x.tap and x.mana_cost]
        game._activate(a, a.battlefield[0], ability)
        run_stack(game)
        self.assertEqual(([c.name for c in a.library], a.graveyard), (["Top", "Bottom", "Bear"], []))


class MysticSanctuaryTests(unittest.TestCase):
    def test_entering_untapped_puts_a_spell_from_the_graveyard_on_top(self):
        game, _ = table3()
        a = game.seats[0]
        bolt = Card(name="Bolt", mana_cost="{R}", type_line="Instant", oracle_text="Draw a card.")
        a.battlefield = [Permanent(Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",)))] * 3
        a.graveyard, a.library = [BEAR, bolt], [Card(name="Top")]
        game._enter(a, Permanent(REAL["Mystic Sanctuary"]))
        run_stack(game)
        self.assertEqual(([c.name for c in a.library], a.graveyard), (["Bolt", "Top"], [BEAR]))

    def test_entering_tapped_does_nothing(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard, a.library = [Card(name="Bolt", type_line="Instant")], []
        land = Permanent(REAL["Mystic Sanctuary"])
        land.tapped = True  # the game taps it as it enters; here that is stated by hand
        game._enter(a, land)
        run_stack(game)
        self.assertEqual(a.library, [])


class GyomeTests(unittest.TestCase):
    def test_the_end_step_makes_a_food_for_each_nontoken_creature_that_entered(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(REAL["Gyome, Master Chef"])]
        game.turn = 5
        for creature in (BEAR, BEAR):
            game._enter(a, Permanent(creature))
        game.create_tokens(a, Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1"), 2)
        run_stack(game)
        game._trigger_each("end_step", a)
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Food" for p in a.battlefield), 2)


class WildGrowthTests(unittest.TestCase):
    def test_the_enchanted_land_makes_an_extra_green_mana(self):
        game, _ = table3()
        a = game.seats[0]
        plains = Permanent(Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",)))
        a.battlefield = [plains]
        self.assertIsNone(game._payment(a, Card(name="Two", mana_cost="{W}{G}", type_line="Sorcery")))
        a.battlefield.append(Permanent(REAL["Wild Growth"], attached_to=plains))
        self.assertIsNotNone(game._payment(a, Card(name="Two", mana_cost="{W}{G}", type_line="Sorcery")))
        self.assertIsNone(game._payment(a, Card(name="Three", mana_cost="{W}{G}{G}", type_line="Sorcery")))


class SagesReverieTests(unittest.TestCase):
    def test_it_draws_a_card_for_each_aura_attached_to_a_creature(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(REAL["Pacifism"], attached_to=bear)]
        a.library = [BEAR] * 5
        game._enter(a, Permanent(REAL["Sage's Reverie"], attached_to=bear))
        run_stack(game)
        self.assertEqual(len(a.hand), 2)


class MartialImpetusTests(unittest.TestCase):
    def test_the_other_attackers_get_a_bonus(self):
        game, _ = table3()
        a, b, c = game.seats
        host, friend = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [host, friend, Permanent(REAL["Martial Impetus"], attached_to=host)]
        game.combat.attacks = [Attack(host, a, b), Attack(friend, a, c)]
        game.trigger("host_attacks", a.battlefield[2], a, host)
        run_stack(game)
        self.assertEqual((game.power(host), game.power(friend)), (3, 3))  # +1/+1 from the Aura itself, and from the trigger
