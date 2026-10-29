"""Earthbender Ascension: earthbend then fetch on entering, and a landfall quest counter with a reflexive "When you do, if ..." trigger
(#564 row 14)."""

import unittest

from infernal_machine.effects import Condition, Earthbend, FetchBasicLand, PutCounters, ReflexiveTrigger, triggered_abilities
from infernal_machine.effects.families.counters import PutCountersOnSource
from infernal_machine.game import PLAY_LAND, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, enter, pick, real, run_stack, table3

ASCENSION = real("Earthbender Ascension", "{2}{G}", "Enchantment",
                 "When this enchantment enters, earthbend 2. Then search your library for a basic land card, put it onto the battlefield "
                 "tapped, then shuffle.\nLandfall — Whenever a land you control enters, put a quest counter on this enchantment. When "
                 "you do, if it has four or more quest counters on it, put a +1/+1 counter on target creature you control. It gains "
                 "trample until end of turn.")


def landfall(quest, with_creature=True):
    """A plays a Forest with the Ascension carrying `quest` counters; the trigger's target is the Bear."""
    game, (a_player, _, _) = table3(pick("Bear", "Forest"))
    a = game.seats[0]
    ascension = Permanent(ASCENSION, counters={"quest": quest} if quest else {})
    bear = Permanent(BEAR)
    a.battlefield = [ascension] + ([bear] if with_creature else [])
    a.hand = [FOREST]
    game._perform(a, PLAY_LAND + "Forest")
    run_stack(game)
    return game, a, a_player, ascension, bear


class ParseTests(unittest.TestCase):
    def test_the_card_is_read(self):
        self.assertEqual(unsupported_lines(ASCENSION), [])
        enters, quest = triggered_abilities(ASCENSION)
        self.assertEqual(list(enters.effects), [Earthbend(2), FetchBasicLand(tapped=True)])
        self.assertEqual(list(quest.effects), [PutCountersOnSource(1, "quest"), ReflexiveTrigger(
            (PutCounters(1, "+1/+1", "creature you control", grant=frozenset({"trample"})),),
            Condition("source_counters_at_least", 4, "quest"),
            "When you do, if it has four or more quest counters on it, put a +1/+1 counter on target creature you control.")])

    def test_a_reflexive_condition_the_grammar_does_not_know_leaves_the_line_unread(self):
        odd = real("Odd Ascension", "{G}", "Enchantment", "Whenever a land you control enters, put a quest counter on this enchantment. "
                                                            "When you do, if the moon is full, put a +1/+1 counter on target creature you control.")
        self.assertEqual(len(unsupported_lines(odd)), 1)


class LandfallTests(unittest.TestCase):
    def test_the_fourth_counter_sets_off_the_reflexive_trigger(self):
        game, a, a_player, ascension, bear = landfall(quest=3)
        self.assertEqual(ascension.counters.get("quest"), 4)
        self.assertEqual(bear.counters.get("+1/+1"), 1)
        self.assertTrue(game.has_keyword(bear, "trample"))
        self.assertTrue(any(TARGET_PROMPT.matches(p) for p, _ in a_player.prompts))

    def test_fewer_counters_only_add_the_quest_counter(self):
        game, a, a_player, ascension, bear = landfall(quest=2)
        self.assertEqual(ascension.counters.get("quest"), 3)
        self.assertIsNone(bear.counters.get("+1/+1"))
        self.assertFalse(any(TARGET_PROMPT.matches(p) for p, _ in a_player.prompts))

    def test_with_no_creature_the_quest_counter_still_goes_on(self):
        game, a, a_player, ascension, _ = landfall(quest=3, with_creature=False)
        self.assertEqual(ascension.counters.get("quest"), 4)  # the reflexive trigger had no target and was removed (CR 603.3d)
        self.assertEqual(game.stack, [])


class EnterTests(unittest.TestCase):
    def test_entering_earthbends_a_land_then_fetches_a_basic_tapped(self):
        game, _ = table3(pick("Forest"))
        a = game.seats[0]
        forest = Permanent(FOREST)
        a.battlefield = [forest]
        a.library = [FOREST, BEAR]
        enter(game, a, ASCENSION)
        run_stack(game)
        self.assertIn("Creature", forest.card.type_line)
        self.assertEqual(forest.counters.get("+1/+1"), 2)
        fetched = [p for p in a.battlefield if p.card is FOREST and p is not forest]
        self.assertEqual((len(fetched), fetched[0].tapped), (1, True))


if __name__ == "__main__":
    unittest.main()
