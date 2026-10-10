"""The cards of issue #80 whose lines depend on X (Fractal Harness, Kinetic Ooze, Lattice Library, Brass Infiniscope, Open the
Way, Animist's Awakening, Unbound Flourishing, Oversimplify). Lines are the cards' own Oracle text from Scryfall; each has cases
where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire
from tests.test_triggers_80 import FOREST, PLAINS, RELIC, SHRINE, card

HARNESS = Card(name="Fractal Harness", mana_cost="{X}{2}{G}", type_line="Artifact — Equipment",
               oracle_text="When this Equipment enters, create a 0/0 green and blue Fractal creature token. Put X +1/+1 counters on "
                           "it and attach this Equipment to it.\nWhenever equipped creature attacks, double the number of +1/+1 "
                           "counters on it.\nEquip {2}")


class FractalHarnessTests(unittest.TestCase):
    def enter(self, x):
        game, _ = table3(pick())
        a = game.seats[0]
        harness = Permanent(HARNESS, sick=True)
        game._enter(a, harness, x=x)
        run_stack(game)
        game._check_state()
        fractal = next((p for p in a.battlefield if p.card.name == "Fractal"), None)
        return game, a, harness, fractal

    def test_parse(self):
        self.assertEqual(unsupported_lines(HARNESS), [])

    def test_the_fractal_comes_in_with_x_counters_and_the_harness_attached(self):
        game, a, harness, fractal = self.enter(3)
        self.assertEqual((fractal.counters.get("+1/+1"), game.power(fractal)), (3, 3))
        self.assertIs(harness.attached_to, fractal)

    def test_x_of_zero_makes_a_fractal_that_dies(self):
        game, a, harness, fractal = self.enter(0)
        self.assertIsNone(fractal)  # 0/0 with no counters

    def test_each_cast_uses_its_own_x(self):
        game, a, harness, fractal = self.enter(2)
        other = Permanent(HARNESS, sick=True)
        game._enter(a, other, x=5)
        run_stack(game)
        self.assertEqual(sorted(p.counters.get("+1/+1", 0) for p in a.battlefield if p.card.name == "Fractal"), [2, 5])


OOZE = Card(name="Kinetic Ooze", mana_cost="{X}{G}", type_line="Creature — Ooze", power="0", toughness="0",
            oracle_text="This creature enters with X +1/+1 counters on it.\nWhen this creature enters, destroy up to one target "
                        "artifact or enchantment with mana value X or less. If X is 5 or more, you draw a card. If X is 10 or more, "
                        "double the number of +1/+1 counters on any number of other target creatures.")
IDOL3 = Card(name="Idol", mana_cost="{3}", cmc=3.0, type_line="Artifact")
SHRINE6 = Card(name="Big Shrine", mana_cost="{4}{W}{W}", cmc=6.0, type_line="Enchantment")


class KineticOozeTests(unittest.TestCase):
    def enter(self, x, *choices, mine=(), theirs=()):
        game, _ = table3(pick(*choices))
        a, b, _ = game.seats
        a.library = [FOREST] * 10
        ooze = Permanent(OOZE, sick=True)
        a.battlefield = list(mine)
        b.battlefield = list(theirs)
        game._enter(a, ooze, x=x)
        run_stack(game)
        return game, a, b, ooze

    def test_parse(self):
        self.assertEqual(unsupported_lines(OOZE), [])

    def test_it_enters_with_x_counters(self):
        game, a, b, ooze = self.enter(3)
        self.assertEqual(ooze.counters.get("+1/+1"), 3)

    def test_it_destroys_an_artifact_or_enchantment_with_mana_value_x_or_less(self):
        idol = Permanent(IDOL3)
        game, a, b, ooze = self.enter(3, "Idol", theirs=[idol])
        self.assertEqual(b.battlefield, [])

    def test_not_one_with_a_greater_mana_value(self):
        shrine = Permanent(SHRINE6)
        game, a, b, ooze = self.enter(3, "Big Shrine", theirs=[shrine])
        self.assertEqual(b.battlefield, [shrine])

    def test_it_may_destroy_nothing(self):
        idol = Permanent(IDOL3)
        game, a, b, ooze = self.enter(3, "No target", theirs=[idol])
        self.assertEqual(b.battlefield, [idol])

    def test_x_of_five_draws_a_card_and_x_of_four_does_not(self):
        self.assertEqual(len(self.enter(5)[1].hand), 1)
        self.assertEqual(len(self.enter(4)[1].hand), 0)

    def test_x_of_ten_doubles_counters_on_any_number_of_other_creatures(self):
        grown = Permanent(BEAR, counters={"+1/+1": 3})
        theirs = Permanent(OGRE, counters={"+1/+1": 2})
        plain = Permanent(BEAR)
        game, a, b, ooze = self.enter(10, "Bear", "Ogre", mine=[grown, plain], theirs=[theirs])
        self.assertEqual((grown.counters.get("+1/+1"), theirs.counters.get("+1/+1"), plain.counters.get("+1/+1")), (6, 4, None))
        self.assertEqual(ooze.counters.get("+1/+1"), 10)  # "other" creatures only

    def test_below_ten_nothing_is_doubled(self):
        grown = Permanent(BEAR, counters={"+1/+1": 3})
        game, a, b, ooze = self.enter(9, "Bear", mine=[grown])
        self.assertEqual(grown.counters.get("+1/+1"), 3)
