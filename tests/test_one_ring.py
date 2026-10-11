"""The One Ring, from its Oracle text: protection from everything until your next turn if you cast it, burden counters, cards."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

RING = real("The One Ring", "{4}", "Legendary Artifact", "Indestructible\n"
            "When The One Ring enters, if you cast it, you gain protection from everything until your next turn.\n"
            "At the beginning of your upkeep, you lose 1 life for each burden counter on The One Ring.\n"
            "{T}: Put a burden counter on The One Ring, then draw a card for each burden counter on The One Ring.")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def cast_ring(*answers):
    game, _ = table3(script(), script(*answers))
    a, b, c = game.seats
    a.hand, a.battlefield, a.library = [RING], lands(4), [FOREST] * 10
    game._perform(a, CAST + "The One Ring")
    run_stack(game)
    return game, a, b, c


class RingTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(RING), [])

    def test_cast_it_and_you_are_protected(self):
        game, a, b, c = cast_ring()
        self.assertTrue(a.protected)
        self.assertFalse(b.protected or c.protected)

    def test_put_onto_the_battlefield_without_casting_it_gives_nothing(self):
        game, _ = table3()
        a = game.seats[0]
        game._enter(a, Permanent(RING))
        run_stack(game)
        self.assertFalse(a.protected)

    def test_a_copy_of_the_spell_is_not_a_cast_ring(self):
        game, _ = table3()
        a = game.seats[0]
        game._resolve(StackItem(RING, a, [], [], is_copy=True))  # a copy of the permanent spell becomes a token
        run_stack(game)
        self.assertFalse(a.protected)

    def test_nothing_can_target_you(self):
        game, a, b, c = cast_ring()
        names = [label for label, _ in game.target_options("any", b)]
        self.assertFalse(any(label.startswith("Player: A") for label in names))
        self.assertTrue(any(label.startswith("Player: B") for label in names))
        self.assertEqual([label for label, _ in game.target_options("opponent", b)], ["Player: C (seat 2)"])
        self.assertEqual([label for label, _ in game.target_options("player", a)], ["Player: B (seat 1)", "Player: C (seat 2)"])  # not even you

    def test_a_spell_aimed_at_you_before_it_fizzles(self):
        game, a, b, c = cast_ring()
        a.protected = False
        spell = real("Drain", "{1}", "Instant", "Target player loses 3 life.")
        b.hand, b.battlefield = [spell], lands(1)
        game.seats[1].player.policy = script("Player: A")  # B aims at A
        game._perform(b, CAST + "Drain")
        a.protected = True  # and then A gets protection before it resolves
        run_stack(game)
        self.assertEqual(a.life, 40)

    def test_damage_to_you_is_prevented(self):
        game, a, b, c = cast_ring()
        game.damage(a, 5)
        game.damage(a, 5, combat=True)
        self.assertEqual(a.life, 40)

    def test_damage_to_others_is_not(self):
        game, a, b, c = cast_ring()
        game.damage(b, 5)
        self.assertEqual(b.life, 35)

    def test_losing_life_is_not_damage(self):
        game, a, b, c = cast_ring()
        game.change_life(a, -2)
        self.assertEqual(a.life, 38)

    def test_it_lasts_until_your_next_turn_begins_not_anyone_elses(self):
        game, a, b, c = cast_ring()
        game.step = "untap"
        game._turn_based_actions(b)
        game._turn_based_actions(c)
        self.assertTrue(a.protected)
        game._turn_based_actions(a)
        self.assertFalse(a.protected)

    def test_the_ring_taps_for_a_burden_counter_and_that_many_cards(self):
        game, a, b, c = cast_ring()
        ring = next(p for p in a.battlefield if p.card.name == "The One Ring")
        for expected_counters, expected_hand in ((1, 1), (2, 3)):
            ring.tapped = False
            game._perform(a, next(x for x in game.legal_actions(a) if x.startswith("Activate")))
            run_stack(game)
            self.assertEqual((ring.counters.get("burden", 0), len(a.hand)), (expected_counters, expected_hand))

    def test_each_upkeep_costs_a_life_per_burden_counter(self):
        game, a, b, c = cast_ring()
        ring = next(p for p in a.battlefield if p.card.name == "The One Ring")
        ring.counters["burden"] = 3
        game.trigger("upkeep", ring, a)
        run_stack(game)
        self.assertEqual(a.life, 37)


if __name__ == "__main__":
    unittest.main()
