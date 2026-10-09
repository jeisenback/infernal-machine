"""Counter-related text of the real cards in issue #76."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.effects import Counter
from infernal_machine.game import Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

RELIC = Card(name="Relic", type_line="Artifact")


class PlusOneReplacementTests(unittest.TestCase):
    def test_kami_adds_one_to_counters_on_any_permanent_you_control(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield = [Permanent(REAL["Kami of Whispered Hopes"])]
        relic, bear, theirs = Permanent(RELIC), Permanent(BEAR), Permanent(BEAR)
        a.battlefield += [relic, bear]
        b.battlefield = [theirs]
        for permanent in (relic, bear, theirs):
            game.put_counters(permanent, "+1/+1", 1)
        self.assertEqual((relic.counters, bear.counters, theirs.counters), ({"+1/+1": 2}, {"+1/+1": 2}, {"+1/+1": 1}))

    def test_ozolith_covers_artifacts_and_creatures_but_not_lands_or_other_counters(self):
        game, _ = table3()
        a = game.seats[0]
        land = Permanent(Card(name="Forest", type_line="Basic Land", produced_mana=("G",)))
        relic, bear = Permanent(RELIC), Permanent(BEAR)
        a.battlefield = [Permanent(REAL["Ozolith, the Shattered Spire"]), relic, bear, land]
        for permanent in (relic, bear, land):
            game.put_counters(permanent, "+1/+1", 1)
        game.put_counters(bear, "charge", 1)
        self.assertEqual((relic.counters, bear.counters, land.counters),
                         ({"+1/+1": 2}, {"+1/+1": 2, "charge": 1}, {"+1/+1": 1}))

    def test_two_of_them_add_up(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(REAL["Kami of Whispered Hopes"]), Permanent(REAL["Ozolith, the Shattered Spire"]), bear]
        game.put_counters(bear, "+1/+1", 1)
        self.assertEqual(bear.counters, {"+1/+1": 3})


class KamiManaTests(unittest.TestCase):
    def test_it_taps_for_as_much_mana_as_its_power(self):
        game, _ = table3()
        a = game.seats[0]
        kami = Permanent(REAL["Kami of Whispered Hopes"], counters={"+1/+1": 2})  # a 1/1 with two counters
        a.battlefield = [kami]
        sorcery = Card(name="Big", mana_cost="{G}{G}{G}", type_line="Sorcery")
        self.assertIsNotNone(game._payment(a, sorcery))
        self.assertIsNone(game._payment(a, replace(sorcery, mana_cost="{G}{G}{G}{G}")))
        kami.sick = True  # a creature that just came in cannot tap for mana
        self.assertIsNone(game._payment(a, sorcery))


class EntersWithCountersTests(unittest.TestCase):
    def test_primo_enters_with_twice_x(self):
        game, _ = table3()
        a = game.seats[0]
        primo = Permanent(REAL["Primo, the Unbounded"])
        game._enter(a, primo, x=3)
        self.assertEqual(primo.counters, {"+1/+1": 6})
        self.assertEqual(game.power(primo), 6)

    def test_primo_makes_a_fractal_as_big_as_the_damage_dealt_by_base_power_zero_creatures(self):
        game, _ = table3()
        a, b, _c = game.seats
        primo = Permanent(REAL["Primo, the Unbounded"], counters={"+1/+1": 4})  # a 4/4 whose base power is 0
        a.battlefield = [primo]
        game.combat.attacks = [Attack(primo, a, b)]
        game.combat.deal_damage(first_strike_step=False)
        run_stack(game)
        [fractal] = [p for p in a.battlefield if p.card.name == "Fractal"]
        self.assertEqual((b.life, fractal.counters), (36, {"+1/+1": 4}))

    def test_woe_strider_escapes_with_two_counters_but_is_not_cast_with_them(self):
        game, _ = table3()
        a = game.seats[0]
        cast = Permanent(REAL["Woe Strider"])
        escaped = Permanent(REAL["Woe Strider"], escaped=True)
        game._enter(a, cast)
        game._enter(a, escaped)
        self.assertEqual((cast.counters, escaped.counters), ({}, {"+1/+1": 2}))


class AlteredEgoTests(unittest.TestCase):
    def test_it_copies_a_creature_with_x_additional_counters(self):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Bear")), 0))
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR)]
        ego = Permanent(REAL["Altered Ego"])
        game._enter(a, ego, x=3)
        self.assertEqual((ego.card.name, ego.counters, game.power(ego)), (BEAR.name, {"+1/+1": 3}, 2 + 3))

    def test_it_cannot_be_countered(self):
        game, _ = table3()
        a, b, _c = game.seats
        spell = StackItem(REAL["Altered Ego"], a, [])
        game.stack.append(spell)
        Counter().resolve(game, b, spell)
        self.assertIn(spell, game.stack)
