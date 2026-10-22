"""explain_card and the misparse audit (issue #478): how the engine read a card, and the rule that catches an effect bound to the wrong
permanent (Skyclave Squid, Fearless Fledgling, Kappa Cannoneer)."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from importlib import util
from pathlib import Path
from unittest import mock

from infernal_machine.cards import BulkSource, Card
from infernal_machine.effects import triggered_abilities
from infernal_machine.effects.families.combat_and_pump import PumpSource
from infernal_machine.effects.families.spells_and_misc import OnSubject
from infernal_machine.effects.outcomes import Modifier
from infernal_machine.effects.targets import SOURCE, SUBJECT, binding
from infernal_machine.effects.triggers import TriggeredAbility
from infernal_machine.explain import Finding, audit, explain
from infernal_machine.game import PLAY_LAND, Permanent
from tests.helpers import FOREST, lands, real, run_stack, table3
from tests.real import REAL

_spec = util.spec_from_file_location("explain_card", Path(__file__).parent.parent / "tools" / "explain_card.py")
assert _spec is not None and _spec.loader is not None
tool = util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

FLEDGLING = real("Fearless Fledgling", "{1}{W}", "Creature — Griffin",
                 "Landfall — Whenever a land you control enters, put a +1/+1 counter on this creature. It gains flying until end of turn.", "1", "1")
CANNONEER = real("Kappa Cannoneer", "{5}{U}", "Artifact Creature — Turtle Warrior",
                 "Improvise (Your artifacts can help cast this spell. Each artifact you tap after you're done activating mana abilities pays for {1}.)\n"
                 "Ward {4}\nWhenever this creature or another artifact you control enters, put a +1/+1 counter on this creature. It can't be blocked this turn.",
                 "4", "4")
SQUID = real("Skyclave Squid", "{1}{U}", "Creature — Squid",
             "Defender\nLandfall — Whenever a land you control enters, this creature can attack this turn as though it didn't have defender.", "3", "2")
CAVALCADE = real("Cavalcade of Calamity", "{1}{R}", "Enchantment",
                 "Whenever a creature you control with power 1 or less attacks, this enchantment deals 1 damage to the player or planeswalker that creature is attacking.")
ODD = real("Odd Toad", "{G}", "Creature — Frog", "Gather the quuxes from the nearest bog.", "1", "1")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


class ExplainTests(unittest.TestCase):
    def test_it_shows_the_text_the_ability_its_effects_and_what_they_are_bound_to(self):
        text = explain(FLEDGLING)
        self.assertIn("Fearless Fledgling  {1}{W}  Creature — Griffin  1/1", text)
        self.assertIn("put a +1/+1 counter on this creature. It gains flying until end of turn.", text)
        self.assertIn("triggered:", text)
        self.assertIn("event permanent_enters; watches land you control", text)
        self.assertIn("PutCountersOnSource(", text)
        self.assertIn("(binds source)", text)

    def test_a_wrapped_effect_is_shown_with_what_it_wraps(self):
        ability = TriggeredAbility("permanent_enters", (OnSubject(PumpSource(Modifier(1, 1))),), False, "Whenever a land enters, it gets +1/+1.")
        with mock.patch("infernal_machine.explain.triggered_abilities", return_value=(ability,)):
            text = explain(FLEDGLING)
        self.assertIn("OnSubject(inner=PumpSource(", text)
        self.assertIn("(binds subject)", text)
        self.assertIn("        PumpSource(", text, "the inner effect on a line of its own, indented under the wrapper")

    def test_a_card_that_is_fully_read_says_so(self):
        self.assertIn("not understood: nothing: every line is read", explain(FLEDGLING))

    def test_a_line_that_is_not_understood_is_named(self):
        self.assertIn("not understood: Gather the quuxes from the nearest bog.", explain(ODD))

    def test_a_spell_shows_what_it_resolves_with(self):
        text = explain(BOLT)
        self.assertIn("spell: resolves with", text)
        self.assertIn("Damage(", text)

    def test_a_card_with_no_rules_text(self):
        self.assertIn("(no rules text)", explain(real("Plain Bear", "{1}{G}", "Creature — Bear", "", "2", "2")))

    def test_an_activated_ability_shows_its_cost(self):
        card = real("Pump Toad", "{G}", "Creature — Frog", "{1}{G}, {T}: Draw a card.", "1", "1")
        text = explain(card)
        self.assertIn("activated: {1}{G}, {T}: Draw a card.", text)
        self.assertIn("cost {1}{G} {T}", text)


class RegressionTests(unittest.TestCase):
    """The three cards the audit first found: the effect is on the card itself, not on the permanent that set the trigger off."""

    def test_the_effects_are_not_wrapped_to_act_on_the_subject(self):
        for card in (FLEDGLING, CANNONEER, SQUID):
            for ability in triggered_abilities(card):
                self.assertFalse(any(isinstance(e, OnSubject) for e in ability.effects), card.name)
                self.assertTrue(all(binding(e) == SOURCE for e in ability.effects), card.name)

    def test_a_land_entering_puts_the_counter_on_the_fledgling_and_not_on_the_land(self):
        game, _ = table3()
        a = game.seats[0]
        bird = Permanent(FLEDGLING)
        a.battlefield = [bird]
        a.hand = [FOREST]
        game._perform(a, PLAY_LAND + "Forest")
        run_stack(game)
        land = next(p for p in a.battlefield if p.card.name == "Forest")
        self.assertEqual(bird.counters.get("+1/+1", 0), 1)
        self.assertEqual(land.counters.get("+1/+1", 0), 0)
        self.assertTrue(game.has_keyword(bird, "flying"))
        self.assertFalse(game.has_keyword(land, "flying"))

    def test_another_artifact_entering_puts_the_counter_on_the_cannoneer(self):
        relic = real("Little Relic", "{1}", "Artifact", "")
        game, _ = table3()
        a = game.seats[0]
        turtle = Permanent(CANNONEER)
        a.battlefield = [turtle]
        newcomer = Permanent(relic)
        game._enter(a, newcomer)
        run_stack(game)
        self.assertEqual(turtle.counters.get("+1/+1", 0), 1)
        self.assertEqual(newcomer.counters.get("+1/+1", 0), 0)

    def test_what_a_creature_is_attacking_is_hit_by_the_enchantment_and_the_effect_is_bound_to_the_attacker(self):
        (ability,) = triggered_abilities(CAVALCADE)
        (effect,) = ability.effects
        self.assertEqual(binding(effect), SUBJECT, "it acts on the attacker, which the trigger carries")
        self.assertFalse(isinstance(effect, OnSubject), "and needs no wrapper to say so")

    def test_an_it_that_really_is_the_permanent_that_set_the_trigger_off_is_still_bound_to_it(self):
        card = real("Watcher", "{1}", "Enchantment", "Whenever a creature enters under your control, it gets +1/+1 until end of turn.")
        (ability,) = triggered_abilities(card)
        self.assertTrue(any(isinstance(e, OnSubject) for e in ability.effects) or all(binding(e) == SUBJECT for e in ability.effects), ability.effects)


class AuditTests(unittest.TestCase):
    def audit_with(self, text, effect, name="Test Card"):
        ability = TriggeredAbility("permanent_enters", (effect,), False, text)
        with mock.patch("infernal_machine.explain.triggered_abilities", return_value=(ability,)):
            return audit(real(name, "{1}", "Creature — Test", "", "1", "1"))

    def test_an_effect_bound_to_the_subject_when_the_sentence_says_this_creature_is_flagged(self):
        findings = self.audit_with("Whenever a land you control enters, this creature gets +1/+1 until end of turn.", OnSubject(PumpSource(Modifier(1, 1))))
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0].rule, findings[0].card), ("subject-binding", "Test Card"))
        self.assertIn("bound to the permanent that set the trigger off", findings[0].why)
        self.assertIn("PumpSource", findings[0].effect)

    def test_the_cards_own_name_counts_as_saying_this_creature(self):
        findings = self.audit_with("Whenever a land enters, Test gets +1/+1 until end of turn.", OnSubject(PumpSource(Modifier(1, 1))), name="Test, the Brave")
        self.assertEqual(len(findings), 1)

    def test_an_ability_word_before_the_event_is_not_part_of_the_sentence(self):
        findings = self.audit_with("Landfall — Whenever a land you control enters, it gets +1/+1.", OnSubject(PumpSource(Modifier(1, 1))))
        self.assertEqual(findings, [], "the sentence after the event never says this creature")

    def test_a_wrapped_effect_that_is_not_about_the_source_is_not_flagged_even_if_the_sentence_names_the_card(self):
        class OnTheAttacker:  # (an effect that is by nature about the permanent that set the trigger off)
            binds = SUBJECT

        text = "Whenever a creature you control attacks, this enchantment deals 1 damage to what it is attacking."
        self.assertEqual(self.audit_with(text, OnSubject(OnTheAttacker())), [])

    def test_an_effect_on_it_when_the_sentence_says_it_is_fine(self):
        self.assertEqual(self.audit_with("Whenever a creature enters, it gets +1/+1 until end of turn.", OnSubject(PumpSource(Modifier(1, 1)))), [])

    def test_an_effect_not_wrapped_is_fine(self):
        self.assertEqual(self.audit_with("Whenever a land enters, this creature gets +1/+1 until end of turn.", PumpSource(Modifier(1, 1))), [])

    def test_a_card_with_no_triggers_has_no_findings(self):
        self.assertEqual(audit(ODD), [])

    def test_a_finding_prints_its_rule_card_text_and_effect(self):
        text = str(Finding("subject-binding", "Card", "the text", "the effect", "the reason"))
        self.assertEqual(text, "[subject-binding] Card: the reason\n    the text\n    -> the effect")

    def test_the_cards_the_audit_first_found_pass_now(self):
        for card in (FLEDGLING, CANNONEER, SQUID, CAVALCADE, REAL["Raid Bombardment"]):
            self.assertEqual(audit(card), [], card.name)

    def test_every_real_card_in_the_fixtures_passes(self):
        found = [f for card in REAL.values() for f in audit(card)]
        self.assertEqual(found, [], "\n".join(str(f) for f in found))


class CommandLineTests(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = tool.main(list(args))
            except SystemExit as stop:
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    def bulk(self, directory, *cards):
        path = os.path.join(directory, "bulk.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in cards}}, f)
        return path

    def test_it_explains_the_named_cards_one_after_another(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self.run_main("Fearless Fledgling", "Skyclave Squid", "--bulk", self.bulk(d, FLEDGLING, SQUID))
        self.assertEqual(code, 0)
        self.assertLess(out.index("Fearless Fledgling"), out.index("Skyclave Squid"))
        self.assertIn("-" * 72, out)

    def test_a_name_the_card_file_does_not_know_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            code, _, err = self.run_main("No Such Card", "--bulk", self.bulk(d, FLEDGLING))
        self.assertEqual(code, 2)
        self.assertIn("No Such Card", err)

    def test_it_needs_card_names_or_audit_but_not_both(self):
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.run_main("Some Card", "--audit")[0], 2)

    def test_the_audit_of_clean_cards_exits_zero_and_counts_them(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self.run_main("--audit", "--bulk", self.bulk(d, FLEDGLING, SQUID, ODD))
        self.assertEqual(code, 0)
        self.assertIn("0 findings in 3 cards.", out)

    def test_a_finding_is_printed_and_makes_the_exit_status_one(self):
        finding = Finding("subject-binding", "Bad Card", "text", "effect", "why")
        with tempfile.TemporaryDirectory() as d, mock.patch.object(tool, "audit", return_value=[finding]):
            code, out, _ = self.run_main("--audit", "--bulk", self.bulk(d, ODD))
        self.assertEqual(code, 1)
        self.assertIn("[subject-binding] Bad Card: why", out)
        self.assertIn("1 finding in 1 cards.", out)

    def test_limit_stops_the_listing_but_not_the_count(self):
        findings = [Finding("r", f"Card {i}", "t", "e", "w") for i in range(3)]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(tool, "audit", return_value=findings):
            _, out, _ = self.run_main("--audit", "--limit", "1", "--bulk", self.bulk(d, ODD))
        self.assertEqual(out.count("[r] Card"), 1)
        self.assertIn("3 findings in 1 cards.", out)


if __name__ == "__main__":
    unittest.main()
