"""The spell halves of Pyre Rhymer (Molten Tide) and Yavimaya Bloomsage (Channel), the last two prepare cards of issue #85.

Their text is from Scryfall. Each effect lasts until end of turn and only helps whoever cast it.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import spell_effects
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import FOREST, RAINBOW
from tests.test_mass_effects import table3
from tests.test_x_targets import script

MOLTEN_TIDE = Card(name="Molten Tide", mana_cost="{R}", cmc=1.0, type_line="Instant", colors=("R",),
                   oracle_text="Until end of turn, whenever you tap a Mountain for mana, add an additional {R}.")
CHANNEL = Card(name="Channel", mana_cost="{G}{G}", cmc=2.0, type_line="Sorcery", colors=("G",),
               oracle_text="Until end of turn, any time you could activate a mana ability, you may pay 1 life. If you do, add {C}.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
STOMPING_GROUND = Card(name="Stomping Ground", type_line="Land — Mountain Forest", produced_mana=("R", "G"))
RED_RED = Card(name="Red Red", mana_cost="{R}{R}", cmc=2.0, type_line="Sorcery", oracle_text="Draw a card.")
GREEN_GREEN = Card(name="Green Green", mana_cost="{G}{G}", cmc=2.0, type_line="Sorcery", oracle_text="Draw a card.")
ONE = Card(name="One", mana_cost="{1}", cmc=1.0, type_line="Sorcery", oracle_text="Draw a card.")
TWO = Card(name="Two", mana_cost="{2}", cmc=2.0, type_line="Sorcery", oracle_text="Draw a card.")
GREEN = Card(name="Green", mana_cost="{G}", cmc=1.0, type_line="Sorcery", oracle_text="Draw a card.")
GREEN_RED = Card(name="Green Red", mana_cost="{G}{R}", cmc=2.0, type_line="Sorcery", oracle_text="Draw a card.")


class ParseTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for card in (MOLTEN_TIDE, CHANNEL):
            self.assertEqual(unsupported_lines(card), [], card.name)
            self.assertEqual(len(spell_effects(card)), 1)


class MoltenTideTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3()
        self.a, self.b, _ = self.game.seats

    def affordable(self, card, seat=None):
        return self.game._payment(seat or self.a, card) is not None

    def cast_tide(self, seat=None):
        spell_effects(MOLTEN_TIDE)[0].resolve(self.game, seat or self.a, None)

    def test_one_mountain_makes_two_red_once_it_resolves(self):
        self.a.battlefield = [Permanent(MOUNTAIN)]
        self.assertFalse(self.affordable(RED_RED))
        self.cast_tide()
        self.assertTrue(self.affordable(RED_RED))

    def test_a_mountain_is_tapped_once_for_both(self):
        self.a.battlefield = [Permanent(MOUNTAIN)]
        self.cast_tide()
        self.assertEqual(len(self.game._payment(self.a, RED_RED)), 1)

    def test_other_lands_get_nothing(self):
        self.a.battlefield = [Permanent(FOREST)]
        self.cast_tide()
        self.assertFalse(self.affordable(GREEN_GREEN))

    def test_a_forest_does_not_add_red(self):
        self.a.battlefield = [Permanent(FOREST)]
        self.cast_tide()
        self.assertFalse(self.affordable(GREEN_RED))  # the Forest's {G} is all it makes

    def test_a_nonbasic_mountain_counts(self):
        self.a.battlefield = [Permanent(STOMPING_GROUND)]
        self.cast_tide()
        self.assertTrue(self.affordable(RED_RED))

    def test_it_ends_with_the_turn(self):
        self.a.battlefield = [Permanent(MOUNTAIN)]
        self.cast_tide()
        self.game.turn += 1
        self.assertFalse(self.affordable(RED_RED))

    def test_an_opponents_mountain_gets_nothing(self):
        self.b.battlefield = [Permanent(MOUNTAIN)]
        self.cast_tide()
        self.assertFalse(self.affordable(RED_RED, self.b))

    def test_casting_it_from_hand_works(self):
        game, _ = table3(script(CAST + "Molten Tide"))
        a = game.seats[0]
        a.hand, a.battlefield = [MOLTEN_TIDE], [Permanent(MOUNTAIN), Permanent(MOUNTAIN)]
        game.active, game.step = 0, "main1"
        game._priority_round(a)
        self.assertEqual([p.tapped for p in a.battlefield].count(False), 1)
        self.assertTrue(game._payment(a, RED_RED) is not None)


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3()
        self.a, self.b, _ = self.game.seats

    def affordable(self, card, seat=None):
        return self.game._payment(seat or self.a, card) is not None

    def cast_channel(self, seat=None):
        spell_effects(CHANNEL)[0].resolve(self.game, seat or self.a, None)

    def test_life_pays_for_generic_mana_once_it_resolves(self):
        self.assertFalse(self.affordable(TWO))
        self.cast_channel()
        self.assertTrue(self.affordable(TWO))

    def test_paying_costs_one_life_for_each_mana(self):
        game, _ = table3(script(CAST + "Two"))
        a = game.seats[0]
        a.hand, a.life = [TWO], 20
        game.active, game.step = 0, "main1"
        spell_effects(CHANNEL)[0].resolve(game, a, None)
        game._priority_round(a)
        self.assertEqual((a.life, [c.name for c in a.graveyard]), (18, ["Two"]))  # cast and resolved, for two life

    def test_real_mana_is_used_before_life(self):
        game, _ = table3(script(CAST + "One"))
        a = game.seats[0]
        forest = Permanent(FOREST)
        a.hand, a.battlefield, a.life = [ONE], [forest], 20
        game.active, game.step = 0, "main1"
        spell_effects(CHANNEL)[0].resolve(game, a, None)
        game._priority_round(a)
        self.assertEqual((a.life, forest.tapped), (20, True))

    def test_a_land_of_any_color_is_used_before_life(self):
        self.a.battlefield, self.a.life = [Permanent(RAINBOW)], 20
        self.cast_channel()
        payment = self.game._payment(self.a, ONE)
        self.assertEqual((len(payment), payment.life), (1, 0))

    def test_a_forest_and_life_pay_for_two(self):
        self.a.battlefield = [Permanent(FOREST)]
        self.cast_channel()
        payment = self.game._payment(self.a, TWO)
        self.assertEqual((len(payment), payment.life), (1, 1))

    def test_it_is_colorless_so_it_cannot_pay_for_color(self):
        self.cast_channel()
        self.assertFalse(self.affordable(GREEN))

    def test_it_never_pays_down_to_zero_life(self):
        self.a.life = 2
        self.cast_channel()
        self.assertFalse(self.affordable(TWO))  # two life would leave none
        self.a.life = 3
        self.assertTrue(self.affordable(TWO))

    def test_it_ends_with_the_turn(self):
        self.cast_channel()
        self.game.turn += 1
        self.assertFalse(self.affordable(ONE))

    def test_an_opponent_cannot_use_it(self):
        self.cast_channel()
        self.assertFalse(self.affordable(ONE, self.b))
