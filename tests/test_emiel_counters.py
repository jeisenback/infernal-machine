"""Emiel the Blessed (Sisay's deck): "Whenever another creature you control enters, you may pay {G/W}. If you do, put a +1/+1 counter on
it. If it's a Unicorn, put two +1/+1 counters on it instead." The creature that entered is the one that gets the counters; the payment
is a choice made as the trigger resolves. Emiel from his real Oracle text; the creatures are probes."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, PLAINS, SWAMP, enter, pick, real, run_stack, table3

EMIEL = real("Emiel the Blessed", "{2}{W}{W}", "Legendary Creature — Unicorn",
             "{3}: Exile another target creature you control, then return it to the battlefield under its owner's control.\nWhenever "
             "another creature you control enters, you may pay {G/W}. If you do, put a +1/+1 counter on it. If it's a Unicorn, put two "
             "+1/+1 counters on it instead. ({G/W} can be paid with either {G} or {W}.)", "4", "4", colors=("W",))
BEAR = real("Bear Probe", "{1}{G}", "Creature — Bear", "", "2", "2")
UNICORN = real("Unicorn Probe", "{1}{W}", "Creature — Unicorn", "", "2", "2")


def table(*mana, policy=None):
    game, _ = table3(policy or pick("Pay"))
    a = game.seats[0]
    a.battlefield = [Permanent(EMIEL), *[Permanent(c) for c in mana]]
    return game, a


def counters(permanent):
    return permanent.counters.get("+1/+1", 0)


class ParseTests(unittest.TestCase):
    def test_every_line_is_read(self):
        self.assertEqual(unsupported_lines(EMIEL), [])


class EmielTests(unittest.TestCase):
    def test_a_creature_that_enters_gets_a_counter_when_you_pay(self):
        game, a = table(FOREST)
        bear = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual(counters(bear), 1)
        self.assertTrue(a.battlefield[1].tapped)  # the Forest paid

    def test_either_color_pays_the_hybrid_symbol(self):
        game, a = table(PLAINS)
        bear = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual(counters(bear), 1)

    def test_a_unicorn_gets_two_counters_instead(self):
        game, a = table(FOREST)
        unicorn = enter(game, a, UNICORN)
        run_stack(game)
        self.assertEqual(counters(unicorn), 2)

    def test_declining_to_pay_puts_no_counter(self):
        game, a = table(FOREST, policy=pick("Don't"))
        bear = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual(counters(bear), 0)
        self.assertFalse(a.battlefield[1].tapped)

    def test_without_mana_of_the_right_color_nothing_happens(self):
        game, a = table(SWAMP)
        bear = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual(counters(bear), 0)

    def test_emiel_does_not_count_himself(self):
        game, a = table(FOREST)
        a.battlefield = [Permanent(c) for c in (FOREST,)]
        emiel = enter(game, a, EMIEL)
        run_stack(game)
        self.assertEqual(counters(emiel), 0)

    def test_an_opponents_creature_does_not_trigger_it(self):
        game, a = table(FOREST)
        theirs = enter(game, game.seats[1], BEAR)
        run_stack(game)
        self.assertEqual(counters(theirs), 0)
        self.assertFalse(a.battlefield[1].tapped)

    def test_a_creature_that_left_before_the_trigger_resolved_gets_nothing(self):
        game, a = table(FOREST)
        bear = enter(game, a, BEAR)
        game._put_triggers_on_stack()
        a.battlefield.remove(bear)
        while game.stack:
            game._resolve(game.stack.pop())
        self.assertEqual(counters(bear), 0)
        self.assertFalse(a.battlefield[1].tapped)  # nothing was paid for

    def test_the_counters_are_on_the_creature_not_on_emiel(self):
        game, a = table(FOREST)
        enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual(counters(a.battlefield[0]), 0)


if __name__ == "__main__":
    unittest.main()
