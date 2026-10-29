"""Deceit: "When this creature enters, if {U}{U} was spent to cast it, ..." and the {B}{B} twin, with hybrid mana and evoke."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Condition, triggered_abilities
from infernal_machine.game import CAST, Permanent
from infernal_machine.mana import parse_cost
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, RAINBOW, lands, pick, real, run_stack, table3

DECEIT = real("Deceit", "{4}{U/B}{U/B}", "Creature — Elemental Incarnation",
              "When this creature enters, if {U}{U} was spent to cast it, return up to one other target nonland permanent to its owner's "
              "hand.\nWhen this creature enters, if {B}{B} was spent to cast it, target opponent reveals their hand. You choose a nonland "
              "card from it. That player discards that card.\nEvoke {U/B}{U/B}", "5", "5")
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
SPELL = real("Spell", "{1}", "Sorcery", "")


def cast(*land_cards, way="Pay"):
    """A casts Deceit with those lands; B has a Bear and a Spell in hand. Returns whether each trigger happened."""
    game, _ = table3(pick(way, "Bear", "Spell"), pick("Spell"))
    a, b, _ = game.seats
    a.hand, a.battlefield = [DECEIT], [Permanent(c) for c in land_cards]
    bear = Permanent(BEAR)
    b.battlefield, b.hand = [bear], [SPELL]
    game._perform(a, CAST + "Deceit")
    run_stack(game)
    return bear in b.hand or bear not in b.battlefield, SPELL in b.graveyard


class ParseTests(unittest.TestCase):
    def test_the_card_is_read(self):
        self.assertEqual(unsupported_lines(DECEIT), [])
        blue, black = triggered_abilities(DECEIT)
        self.assertEqual((blue.condition, black.condition), (Condition("mana_spent_colors", what="UU"), Condition("mana_spent_colors", what="BB")))
        self.assertTrue(blue.effects[0].another and blue.effects[0].optional_target)


class PaymentRecordTests(unittest.TestCase):
    def test_a_source_paying_a_hybrid_symbol_counts_only_as_that_symbols_colors(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(Card(name="Glade", type_line="Land", produced_mana=("U", "G")))]
        payment = game._pay_cost(a, parse_cost("{U/B}"))
        self.assertEqual(payment.spent, (frozenset("U"),))  # it made {U} for the {U/B}, never {G}
        payment = game._pay_cost(a, parse_cost("{1}"))
        self.assertEqual(payment.spent, (frozenset("UG"),))  # for generic mana it could have made either


class SpentTests(unittest.TestCase):
    def test_blue_mana_sets_off_only_the_blue_trigger(self):
        self.assertEqual(cast(*[ISLAND] * 6), (True, False))

    def test_black_mana_sets_off_only_the_black_trigger(self):
        self.assertEqual(cast(*[SWAMP] * 6), (False, True))

    def test_one_of_each_sets_off_neither(self):
        self.assertEqual(cast(ISLAND, SWAMP, FOREST, FOREST, FOREST, FOREST), (False, False))

    def test_lands_of_any_color_count_for_both(self):
        self.assertEqual(cast(*[RAINBOW] * 6), (True, True))

    def test_evoked_with_blue_mana(self):
        self.assertEqual(cast(ISLAND, ISLAND, way="Evoke"), (True, False))


if __name__ == "__main__":
    unittest.main()
