"""Aura grants and other static buffs from the real cards in issue #75."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import attached_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

RELIC = Card(name="Relic", type_line="Artifact")


class EldraziConscriptionTests(unittest.TestCase):
    def test_it_is_understood(self):
        card = REAL["Eldrazi Conscription"]
        self.assertEqual(unsupported_lines(card), [])
        [buff] = attached_abilities(card)
        self.assertEqual((buff.modifier.power, buff.modifier.keywords), (10, frozenset({"trample", "annihilator 2"})))

    def test_the_enchanted_creature_has_annihilator_2(self):
        game, _ = table3(pick("Attack Player: B"))
        a, b, _c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(REAL["Eldrazi Conscription"], attached_to=bear)]
        b.battlefield = [Permanent(RELIC) for _ in range(5)]
        self.assertEqual((game.power(bear), game.annihilator(bear)), (12, 2))
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(len(b.battlefield), 3)  # two sacrificed

    def test_no_annihilator_without_the_aura(self):
        game, _ = table3(pick("Attack Player: B"))
        a, b, _c = game.seats
        a.battlefield = [Permanent(BEAR)]
        b.battlefield = [Permanent(RELIC)]
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(len(b.battlefield), 1)
