"""Stun counters: a tapped permanent with one loses a stun counter instead of untapping."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import UntapAll, spell_effects
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, OGRE, real, run_stack, script, table3

FREEZE = real("Freeze", "{1}{U}", "Sorcery", "Tap target creature. Put three stun counters on it.")
JAM = real("Jam", "{1}{U}", "Instant", "Tap target creature an opponent controls and put a stun counter on it.")
PAIR = real("Pair", "{2}{U}", "Sorcery", "Tap up to two target creatures. Put a stun counter on each of them.")
OUT_COLD = real("Out Cold", "{2}{U}", "Instant", "Tap up to two target creatures and put a stun counter on each of them. Investigate.")
ONE_OR_TWO = real("Succumb", "{1}{U}", "Instant", "Tap one or two target creatures an opponent controls. Put a stun counter on each of them.")
SIDEKICK = real("Frost Sidekick", "{3}{U}", "Creature — Wizard", "When this creature enters, tap target creature an opponent controls and put a stun counter on it.", "2", "2")
KRAKEN = real("Grappling Kraken", "{4}{U}", "Creature — Kraken", "Landfall — Whenever a land you control enters, tap target creature an opponent controls and put a stun counter on it.", "4", "4")
DONATELLO = real("Donatello", "{3}{U}", "Legendary Creature — Turtle", "When CARDNAME enters, tap up to three target creatures your opponents control. Put a stun counter on each of them.", "3", "3")
UP_TO_ONE = real("Maybe", "{1}{U}", "Instant", "Tap up to one target creature and put two stun counters on it.")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def untap_step(game, seat):
    game.step = "untap"
    game._turn_based_actions(seat)


def cast(card, *answers, theirs=(BEAR,)):
    game, _ = table3(script(*answers))
    a, b, c = game.seats
    a.hand, a.battlefield, a.library = [card], lands(6), [FOREST] * 5
    b.battlefield = [Permanent(x) for x in theirs]
    game._perform(a, CAST + card.name)
    run_stack(game)
    game._check_state()
    return game, a, b


class RuleTests(unittest.TestCase):
    def test_a_stunned_permanent_stays_tapped_and_loses_the_counter(self):
        game, _ = table3()
        a = game.seats[0]
        stunned = Permanent(BEAR, tapped=True, counters={"stun": 1})
        a.battlefield = [stunned]
        untap_step(game, a)
        self.assertEqual((stunned.tapped, stunned.counters.get("stun")), (True, None))
        untap_step(game, a)
        self.assertFalse(stunned.tapped)

    def test_each_counter_costs_one_untap(self):
        game, _ = table3()
        a = game.seats[0]
        stunned = Permanent(BEAR, tapped=True, counters={"stun": 3})
        a.battlefield = [stunned]
        for expected in (2, 1):
            untap_step(game, a)
            self.assertEqual((stunned.tapped, stunned.counters["stun"]), (True, expected))
        untap_step(game, a)
        untap_step(game, a)
        self.assertFalse(stunned.tapped)

    def test_an_untapped_permanent_keeps_its_counter(self):
        game, _ = table3()
        a = game.seats[0]
        waiting = Permanent(BEAR, counters={"stun": 1})
        a.battlefield = [waiting]
        untap_step(game, a)
        self.assertEqual(waiting.counters["stun"], 1)  # nothing became untapped
        game.tap(waiting)
        untap_step(game, a)
        self.assertEqual((waiting.tapped, waiting.counters.get("stun")), (True, None))  # tapped now, so the untap was replaced

    def test_other_permanents_untap_as_usual(self):
        game, _ = table3()
        a = game.seats[0]
        stunned, free = Permanent(BEAR, tapped=True, counters={"stun": 1}), Permanent(OGRE, tapped=True)
        a.battlefield = [stunned, free]
        untap_step(game, a)
        self.assertEqual((stunned.tapped, free.tapped), (True, False))

    def test_untapping_by_an_effect_is_replaced_too(self):
        game, _ = table3()
        a = game.seats[0]
        stunned = Permanent(Card(name="Plains", type_line="Basic Land — Plains"), tapped=True, counters={"stun": 1})
        a.battlefield = [stunned]
        UntapAll("land").resolve(game, a, None)
        self.assertEqual((stunned.tapped, stunned.counters.get("stun")), (True, None))
        UntapAll("land").resolve(game, a, None)
        self.assertFalse(stunned.tapped)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (FREEZE, JAM, UP_TO_ONE, PAIR, OUT_COLD, ONE_OR_TWO, SIDEKICK, KRAKEN, DONATELLO):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_lone_each_of_them_is_not_understood(self):
        card = real("Odd", "{U}", "Instant", "Put a stun counter on each of them.")
        self.assertEqual(unsupported_lines(card), ["Put a stun counter on each of them."])

    def test_other_cards_that_name_creatures_your_opponents_control(self):
        taps = real("Fogger", "{2}{U}", "Sorcery", "Tap up to two target creatures your opponents control.")
        returns = real("Wave", "{3}{U}", "Sorcery", "Return up to two target creatures your opponents control to their owners' hands.")
        self.assertEqual([unsupported_lines(c) for c in (taps, returns)], [[], []])


class CastingTests(unittest.TestCase):
    def test_tap_and_stun_the_target(self):
        game, a, b = cast(JAM, "Bear")
        [bear] = b.battlefield
        self.assertEqual((bear.tapped, bear.counters.get("stun")), (True, 1))

    def test_up_to_one_target_may_be_left_out_and_otherwise_gets_the_counters(self):
        game, a, b = cast(UP_TO_ONE, "No target")
        self.assertEqual((b.battlefield[0].tapped, b.battlefield[0].counters), (False, {}))
        game, a, b = cast(UP_TO_ONE, "Bear")
        self.assertEqual((b.battlefield[0].tapped, b.battlefield[0].counters["stun"]), (True, 2))

    def test_several_counters(self):
        game, a, b = cast(FREEZE, "Bear")
        self.assertEqual(b.battlefield[0].counters["stun"], 3)

    def test_a_stunned_creature_stays_down_through_its_next_untap_step(self):
        game, a, b = cast(JAM, "Bear")
        untap_step(game, b)
        self.assertTrue(b.battlefield[0].tapped)
        untap_step(game, b)
        self.assertFalse(b.battlefield[0].tapped)

    def test_up_to_two_targets_each_get_a_counter(self):
        game, a, b = cast(PAIR, "Bear", "Ogre", theirs=(BEAR, OGRE, BEAR))
        stunned = [p.card.name for p in b.battlefield if p.counters.get("stun")]
        self.assertEqual(sorted(stunned), ["Bear", "Ogre"])
        self.assertEqual(len([p for p in b.battlefield if p.tapped]), 2)

    def test_fewer_targets_than_the_maximum(self):
        game, a, b = cast(PAIR, "Ogre", "No target", theirs=(BEAR, OGRE))
        self.assertEqual([p.card.name for p in b.battlefield if p.counters.get("stun")], ["Ogre"])

    def test_the_rest_of_the_spell_still_happens(self):
        game, a, b = cast(OUT_COLD, "Bear")
        self.assertEqual(b.battlefield[0].counters.get("stun"), 1)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Clue"]), 1)

    def test_one_or_two_targets_need_at_least_one(self):
        game, a, b = cast(ONE_OR_TWO, "Bear", theirs=(BEAR,))
        self.assertEqual(b.battlefield[0].counters.get("stun"), 1)

    def test_when_this_creature_enters(self):
        game, a, b = cast(SIDEKICK, "Bear")
        self.assertEqual((b.battlefield[0].tapped, b.battlefield[0].counters.get("stun")), (True, 1))

    def test_a_trigger_on_another_permanent_entering(self):
        game, _ = table3(script("Bear"))
        a, b, _ = game.seats
        a.battlefield = [Permanent(KRAKEN)]
        b.battlefield = [Permanent(BEAR)]
        game._enter(a, Permanent(FOREST))
        run_stack(game)
        self.assertEqual((b.battlefield[0].tapped, b.battlefield[0].counters.get("stun")), (True, 1))

    def test_up_to_three_targets_your_opponents_control(self):
        game, a, b = cast(DONATELLO, "Bear", "Ogre", "Bear", theirs=(BEAR, OGRE, BEAR))
        self.assertEqual([p.counters.get("stun") for p in b.battlefield], [1, 1, 1])


if __name__ == "__main__":
    unittest.main()
