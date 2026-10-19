"""What an effect acts on is one value, `binds` (issue #436): every effect names a known one, the wrappers pass the right ones on, the
trigger checks and the resolver agree on them, and the old flags are gone."""

import dataclasses
import inspect
import re
import unittest
from pathlib import Path

from infernal_machine.effects import (BINDINGS, CONTEXT_BINDINGS, DEAD_SOURCE, DEAD_SUBJECT, PLAYER, PREVIOUS_TARGET, SOURCE, SOURCE_AND_SUBJECT,
                                      SUBJECT, binding, outcomes, triggered_abilities)
from infernal_machine.effects.outcomes import (Conditional, CreateDelayedTrigger, DoubleStats, Draw, ExileOwnGraveyard, GrantProtection,
                                               MayPay, PreventNext, PutCounters, ReturnTransformed)
from infernal_machine.game import PASS, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table

ROOT = Path(__file__).parent.parent / "infernal_machine"


def effect_classes():
    """Every effect class, wherever it is defined (the families package, and outcomes.py for what stayed)."""
    return [c for _, c in inspect.getmembers(outcomes, inspect.isclass)
            if c.__module__.startswith(("infernal_machine.effects.families", outcomes.__name__)) and hasattr(c, "resolve")]


class EveryEffectTests(unittest.TestCase):
    def test_a_class_level_binding_is_a_known_one(self):
        seen = 0
        for cls in effect_classes():
            value = cls.__dict__.get("binds")
            if value is not None and not isinstance(value, property):
                self.assertIn(value, BINDINGS, cls.__name__)
                seen += 1
        self.assertGreater(seen, 60)  # the 83 that were flags

    def test_no_effect_still_has_a_flag_instead(self):
        for cls in effect_classes():
            for old in ("uses_source", "uses_subject", "uses_player", "uses_dead_both", "uses_dead_subject", "uses_dead_source", "follows_target"):
                self.assertFalse(hasattr(cls, old), f"{cls.__name__}.{old}")

    def test_the_old_names_are_not_in_the_code_at_all(self):
        pattern = re.compile(r"\b(uses_source|uses_subject|uses_player|uses_dead_\w+|follows_target)\b")
        for path in ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if pattern.search(line) and not line.lstrip().startswith("#"):
                    self.fail(f"{path.name}: {line.strip()}")

    def test_the_context_bindings_are_exactly_those_a_plain_trigger_lacks(self):
        self.assertEqual(CONTEXT_BINDINGS, {SOURCE, SUBJECT, PLAYER, PREVIOUS_TARGET})
        self.assertEqual(set(BINDINGS), CONTEXT_BINDINGS | {DEAD_SUBJECT, SOURCE_AND_SUBJECT, DEAD_SOURCE})


class WrapperTests(unittest.TestCase):
    ON_SOURCE = PreventNext(1, on_source=True)

    def test_a_field_makes_it_about_the_source(self):
        self.assertEqual(binding(GrantProtection(on_source=True)), SOURCE)
        self.assertIsNone(binding(GrantProtection()))
        self.assertEqual(binding(DoubleStats(True, True, on_source=True)), SOURCE)
        self.assertIsNone(binding(PreventNext(1)))

    def test_a_conditional_passes_on_source_subject_and_player_and_nothing_else(self):
        self.assertEqual(binding(Conditional(None, self.ON_SOURCE)), SOURCE)
        self.assertEqual(binding(Conditional(None, outcomes.OnSubject(Draw(1)))), SUBJECT)
        self.assertEqual(binding(Conditional(None, outcomes.PlayerLosesLife(1))), PLAYER)
        self.assertIsNone(binding(Conditional(None, outcomes.TapThat())), "a follow-up on the previous target is not passed on, as before")
        self.assertIsNone(binding(Conditional(None, Draw(1))))

    def test_may_pay_passes_on_only_the_source(self):
        self.assertEqual(binding(MayPay("{1}", self.ON_SOURCE)), SOURCE)
        self.assertIsNone(binding(MayPay("{1}", Draw(1))))
        self.assertIsNone(binding(MayPay("{1}", outcomes.OnSubject(Draw(1)))), "a subject is not passed on, as before")

    def test_a_graveyard_exile_with_a_then_passes_on_its_source(self):
        self.assertEqual(binding(ExileOwnGraveyard(8, self.ON_SOURCE)), SOURCE)
        self.assertIsNone(binding(ExileOwnGraveyard(8)))
        self.assertIsNone(binding(ExileOwnGraveyard(8, Draw(1))))

    def test_a_dying_return_is_about_the_dead_source_and_otherwise_the_source(self):
        self.assertEqual(binding(ReturnTransformed(dies=True)), DEAD_SOURCE)
        self.assertEqual(binding(ReturnTransformed(dies=False)), SOURCE)

    def test_a_delayed_trigger_follows_a_target_only_when_it_waits_for_one(self):
        self.assertEqual(binding(CreateDelayedTrigger((), when=frozenset({"x"}))), PREVIOUS_TARGET)
        self.assertIsNone(binding(CreateDelayedTrigger(())))

    def test_an_effect_with_its_own_target_binds_nothing(self):
        self.assertIsNone(binding(PutCounters(1, "+1/+1", "creature")))


class ResolverAndTriggerTests(unittest.TestCase):
    def test_a_trigger_effect_bound_to_the_source_and_the_subject_is_accepted_and_resolves_with_both(self):
        # the bug that started #436: an effect bound to (source, subject) was refused by one of the trigger checks
        lord = real("Test Doubler", "{3}", "Artifact",
                    "Whenever a nontoken creature you control dies, create a token that's a copy of that creature, except it isn't legendary.")
        self.assertEqual(unsupported_lines(lord), [])
        [ability] = triggered_abilities(lord)
        self.assertEqual([binding(e) for e in ability.effects], [SOURCE_AND_SUBJECT])
        game, _, _ = table(lambda prompt, options: options.index(PASS) if PASS in options else 0)
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = lands(1) + [Permanent(lord), bear]
        game.destroy(bear)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield if p.card.type_line.startswith("Token")], ["Bear"])

    def test_an_effect_bound_to_a_player_gets_the_player_who_set_it_off(self):
        card = real("Test Tax", "{2}", "Artifact", "Whenever an opponent draws a card, that player loses 1 life.")
        game, _, _ = table(lambda prompt, options: options.index(PASS) if PASS in options else 0)
        a, b = game.seats
        a.battlefield = [Permanent(card)]
        game.draw(b, 1)
        run_stack(game)
        self.assertEqual((a.life, b.life), (40, 39))

    def test_a_subject_bound_effect_does_nothing_once_the_subject_has_left(self):
        card = real("Test Feeder", "{2}", "Artifact", "Whenever another creature enters, put a +1/+1 counter on it.")
        self.assertEqual(unsupported_lines(card), [])
        game, _, _ = table(lambda prompt, options: options.index(PASS) if PASS in options else 0)
        a = game.seats[0]
        a.battlefield = [Permanent(card)]
        newcomer = Permanent(BEAR)
        game._enter(a, newcomer)
        a.battlefield.remove(newcomer)  # gone before the trigger resolves
        run_stack(game)
        self.assertEqual(newcomer.counters.get("+1/+1", 0), 0)
        second = Permanent(BEAR)
        game._enter(a, second)
        run_stack(game)
        self.assertEqual(second.counters.get("+1/+1"), 1, "and it does work when the subject is still there")

    def test_a_source_bound_effect_does_nothing_once_the_source_has_left(self):
        card = real("Test Grower", "{1}", "Artifact", "Whenever you draw a card, put a +1/+1 counter on this artifact.")
        game, _, _ = table(lambda prompt, options: options.index(PASS) if PASS in options else 0)
        a = game.seats[0]
        grower = Permanent(card)
        a.battlefield = [grower]
        game.draw(a, 1)
        a.battlefield.remove(grower)  # gone before the trigger resolves
        run_stack(game)
        self.assertEqual(grower.counters.get("+1/+1", 0), 0)


if __name__ == "__main__":
    unittest.main()
