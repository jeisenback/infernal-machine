"""Event.accepts (issue #439): which hearers an occurrence concerns, beyond who they are, as one callable instead of a string that
`Game.happened` had a branch for."""

import re
import unittest

from infernal_machine.effects import EVENTS, TriggeredAbility, triggered_abilities
from infernal_machine.effects import events as registry
from infernal_machine.effects.events import about_artifact, fact, on_the_subject
from infernal_machine.effects.outcomes import GainLife
from infernal_machine.game import Permanent, StackItem
from tests.helpers import BEAR, real, run_stack, table


def declared(name, pattern, **options):
    event = registry.declare(name, re.compile(pattern, re.I), **options)

    def forget():
        EVENTS.pop(name, None)
        for occurrence in event.happens:
            registry._HEARD[occurrence] = [e for e in registry._HEARD.get(occurrence, []) if e.name != name]

    return event, forget


RELIC = real("Test Relic", "{2}", "Artifact", "{T}: Add {C}.")
ARM = real("Test Arm", "{1}", "Artifact — Equipment", "Equip {1}")


class HelperTests(unittest.TestCase):
    def test_a_fact_is_asked_for_by_name(self):
        self.assertTrue(fact("second")(None, None, ("first", "second")))
        self.assertFalse(fact("second")(None, None, ("first",)))
        self.assertFalse(fact("second")(None, None, ()))

    def test_about_an_artifact(self):
        self.assertTrue(about_artifact(None, Permanent(RELIC), ()))
        self.assertFalse(about_artifact(None, Permanent(BEAR), ()))
        self.assertFalse(about_artifact(None, None, ()))

    def test_only_what_is_attached_to_the_subject_hears_it(self):
        creature, other = Permanent(BEAR), Permanent(BEAR)
        arm = Permanent(ARM, attached_to=creature)
        self.assertTrue(on_the_subject(arm, creature, ()))
        self.assertFalse(on_the_subject(arm, other, ()))
        self.assertFalse(on_the_subject(arm, None, ()))
        self.assertFalse(on_the_subject(Permanent(ARM), creature, ()))

    def test_no_event_still_has_a_needs_string(self):
        for event in EVENTS.values():
            self.assertFalse(hasattr(event, "needs"), event.name)
            self.assertTrue(event.accepts is None or callable(event.accepts), event.name)

    def test_the_declared_filters_are_the_ones_the_cards_need(self):
        self.assertIs(EVENTS["activate_artifact"].accepts, about_artifact)
        self.assertIs(EVENTS["activate_host"].accepts, on_the_subject)
        self.assertIsNone(EVENTS["activate_any"].accepts)


class HappenedTests(unittest.TestCase):
    def watchers(self):
        card = real("Test Watcher", "{2}", "Artifact", "Whenever a test thing happens, you gain 1 life.")
        game, _, _ = table(None)
        a, b = game.seats
        return game, a, b, card

    def test_each_hearer_is_asked_and_only_those_accepted_trigger(self):
        event, forget = declared("a_test_thing", r"Whenever a test thing happens, (.+)", to="you", happens="test_occurrence",
                                 accepts=lambda hearer, subject, facts: hearer.card.name == "Chosen")
        self.addCleanup(forget)
        text = "Whenever a test thing happens, you gain 1 life."
        chosen, other = real("Chosen", "{2}", "Artifact", text), real("Other", "{2}", "Artifact", text)
        self.assertEqual(triggered_abilities(chosen)[0].event, "a_test_thing")
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(chosen), Permanent(other)]
        game.happened("test_occurrence", a)
        run_stack(game)
        self.assertEqual(a.life, 41, "one of the two watchers, not both")

    def test_an_event_for_opponents_asks_too(self):
        event, forget = declared("an_opponents_test_thing", r"Whenever an opponent does a test thing, (.+)", to="opponents", happens="test_occurrence",
                                 accepts=lambda hearer, subject, facts: "wanted" in facts)
        self.addCleanup(forget)
        card = real("Opp Watcher", "{2}", "Artifact", "Whenever an opponent does a test thing, you gain 2 life.")
        game, _, _ = table(None)
        a, b = game.seats
        a.battlefield = [Permanent(card)]
        game.happened("test_occurrence", b)
        run_stack(game)
        self.assertEqual(a.life, 40)
        game.happened("test_occurrence", b, "wanted")
        run_stack(game)
        self.assertEqual(a.life, 42)

    def test_a_delayed_ability_is_asked_as_well(self):
        event, forget = declared("a_delayed_test_thing", r"Whenever a delayed test thing happens, (.+)", to="you", happens="test_occurrence",
                                 accepts=lambda hearer, subject, facts: "wanted" in facts)
        self.addCleanup(forget)
        game, _, _ = table(None)
        a = game.seats[0]
        ability = TriggeredAbility("a_delayed_test_thing", (GainLife(3),), False, "Whenever a delayed test thing happens, you gain 3 life.")
        game.add_delayed(ability, StackItem(BEAR, a, [], []), a)
        game.happened("test_occurrence", a)
        run_stack(game)
        self.assertEqual(a.life, 40)
        game.happened("test_occurrence", a, "wanted")
        run_stack(game)
        self.assertEqual(a.life, 43)

    def test_an_event_with_no_filter_concerns_everyone(self):
        event, forget = declared("an_open_test_thing", r"Whenever an open test thing happens, (.+)", to="you", happens="test_occurrence")
        self.addCleanup(forget)
        card = real("Open Watcher", "{2}", "Artifact", "Whenever an open test thing happens, you gain 1 life.")
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(card), Permanent(card)]
        game.happened("test_occurrence", a)
        run_stack(game)
        self.assertEqual(a.life, 42)


if __name__ == "__main__":
    unittest.main()
