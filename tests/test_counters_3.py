"""Counter-related text of the real cards in issue #76."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
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
