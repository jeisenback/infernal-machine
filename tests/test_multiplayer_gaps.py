import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import GoadAll, UnlessPays, spell_effects, triggered_abilities
from infernal_machine.game import Permanent, UNLESS_PROMPT
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, creature
from tests.test_effects import FOREST, lands, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

DISRUPT = Card(name="Disrupt Decorum", mana_cost="{2}{R}", type_line="Sorcery",
               oracle_text="Goad all creatures you don't control.")
QUEEN = Card(name="Queen", mana_cost="{2}", type_line="Enchantment",
             oracle_text="Whenever you become the monarch, draw a card.")
SPITE = REAL["Knights of the Black Rose"]
RHYSTIC = Card(name="Rhystic Study", mana_cost="{2}{U}", type_line="Enchantment",
               oracle_text="Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.")
TITHE = REAL["Smothering Tithe"]
SPELL = Card(name="Spell", mana_cost="{1}", type_line="Sorcery", oracle_text="Draw a card.")


class GoadAllTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(DISRUPT), [GoadAll()])
        self.assertEqual(unsupported_lines(DISRUPT), [])

    def test_goads_every_creature_an_opponent_controls(self):
        game, _ = table3()
        a, b, c = game.seats
        mine, theirs, other = Permanent(BEAR), Permanent(BEAR), Permanent(BEAR)
        a.battlefield, b.battlefield, c.battlefield = [mine], [theirs], [other, Permanent(FOREST)]
        GoadAll().resolve(game, a, None)
        self.assertEqual((mine.goaded_by, theirs.goaded_by, other.goaded_by), (None, a, a))


class MonarchTriggerTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual([t.event for t in triggered_abilities(QUEEN)], ["become_monarch"])
        self.assertIn("opponent_become_monarch", [t.event for t in triggered_abilities(SPITE)])
        self.assertEqual(unsupported_lines(QUEEN) + unsupported_lines(SPITE), [])

    def test_becoming_the_monarch_triggers_you_only(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield, b.battlefield = [Permanent(QUEEN)], [Permanent(QUEEN)]
        a.library = [BEAR] * 3
        game.become_monarch(a)
        run_stack(game)
        self.assertEqual((len(a.hand), len(b.hand)), (1, 0))

    def test_an_opponent_becoming_the_monarch(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(SPITE)]
        game.monarch = game.monarch_at_turn_start = a
        game.become_monarch(b)  # a was the monarch as the turn began
        run_stack(game)
        self.assertEqual((a.life, b.life), (42, 38))

    def test_not_the_monarch_when_the_turn_began_does_nothing(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(SPITE)]
        game.become_monarch(a)  # during the turn, not at its start
        game.become_monarch(b)
        run_stack(game)
        self.assertEqual((a.life, b.life), (40, 40))

    def test_already_the_monarch_does_not_trigger_again(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(QUEEN)]
        a.library = [BEAR] * 3
        game.become_monarch(a)
        game.become_monarch(a)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)


class UnlessPaysTests(unittest.TestCase):
    def cast(self, payer_policy, mana):
        game, _, b = table(lambda prompt, options: 0, payer_policy)
        a = game.seats[0]
        a.battlefield = [Permanent(RHYSTIC)]
        a.library = [BEAR] * 3
        game.seats[1].battlefield = lands(mana, FOREST)
        game._observe("cast", SPELL, game.seats[1])
        run_stack(game)
        return game, a, b

    def test_parse(self):
        ability = triggered_abilities(RHYSTIC)[0]
        self.assertEqual(ability.effects[0].cost, "{1}")
        self.assertTrue(ability.optional)
        self.assertIsInstance(ability.effects[0], UnlessPays)
        self.assertEqual(unsupported_lines(RHYSTIC) + unsupported_lines(TITHE), [])

    def test_paying_stops_the_draw(self):
        game, a, b = self.cast(lambda prompt, options: 0, 1)
        self.assertEqual(a.hand, [])
        self.assertTrue(next(p for p, _ in b.prompts if p.startswith(UNLESS_PROMPT)))
        self.assertEqual([p.tapped for p in game.seats[1].battlefield], [True])

    def test_declining_lets_the_draw_happen(self):
        game, a, b = self.cast(lambda prompt, options: 1, 1)
        self.assertEqual(len(a.hand), 1)
        self.assertEqual([p.tapped for p in game.seats[1].battlefield], [False])

    def test_unable_to_pay_is_not_asked(self):
        game, a, b = self.cast(lambda prompt, options: 0, 0)
        self.assertEqual(len(a.hand), 1)
        self.assertFalse([p for p, _ in b.prompts if p.startswith(UNLESS_PROMPT)])

    def test_a_triggered_token_unless_the_drawer_pays(self):
        game, _, b = table(lambda prompt, options: 0, lambda prompt, options: 1)
        a = game.seats[0]
        a.battlefield = [Permanent(TITHE)]
        game.seats[1].library = [BEAR] * 3
        game.draw(game.seats[1], 1)
        run_stack(game)
        self.assertTrue(any("Treasure" in p.card.name for p in a.battlefield))

    def test_paying_for_the_treasure_trigger_stops_it(self):
        game, _, _ = table(lambda prompt, options: 0, lambda prompt, options: 0)
        a, b = game.seats
        a.battlefield = [Permanent(TITHE)]
        b.battlefield = lands(2, FOREST)
        b.library = [BEAR] * 3
        game.draw(b, 1)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Smothering Tithe"])
