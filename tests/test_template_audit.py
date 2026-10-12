"""The template audit tool (tools/template_audit.py): unused templates and sentences two templates read, on a toy template list."""

import importlib.util
import os
import re
import unittest
from unittest import mock

from infernal_machine.cards import Card
from infernal_machine.effects import Draw, outcomes

_spec = importlib.util.spec_from_file_location("template_audit", os.path.join(os.path.dirname(__file__), "..", "tools", "template_audit.py"))
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)


def spell(name, text):
    return Card(name=name, type_line="Sorcery", oracle_text=text)


def audit(templates, *cards):
    with mock.patch.object(outcomes, "_TEMPLATES", templates):
        return tool.audit(cards)


NARROW = (re.compile(r"draw a card\.", re.I), lambda m: Draw(1))
BROAD_SAME = (re.compile(r"draw (.+)\.", re.I), lambda m: Draw(1))
BROAD_OTHER = (re.compile(r"draw (.+)\.", re.I), lambda m: Draw(2))
NEVER = (re.compile(r"frobnicate the widget\.", re.I), lambda m: Draw(3))


class AuditTests(unittest.TestCase):
    def test_a_template_that_wins_nothing_is_unused(self):
        result = audit([NARROW, NEVER], spell("One", "Draw a card."))
        self.assertEqual([u["index"] for u in result["unused"]], [1])
        self.assertEqual(result["unused"][0]["pattern"], NEVER[0].pattern)

    def test_the_second_of_two_templates_that_read_a_sentence_wins_nothing(self):
        result = audit([NARROW, BROAD_SAME], spell("One", "Draw a card."))
        self.assertEqual([u["index"] for u in result["unused"]], [1])

    def test_a_sentence_two_templates_read_differently_is_reported_with_the_winner_first(self):
        [found] = audit([NARROW, BROAD_OTHER], spell("One", "Draw a card."))["ambiguous"]
        self.assertEqual((found["sentence"], found["wins"], found["also"], found["differs"]), ("Draw a card.", 0, [1], True))

    def test_two_templates_that_build_the_same_effect_do_not_differ(self):
        [found] = audit([NARROW, BROAD_SAME], spell("One", "Draw a card."))["ambiguous"]
        self.assertFalse(found["differs"])

    def test_a_sentence_one_template_reads_is_not_ambiguous(self):
        self.assertEqual(audit([NARROW, BROAD_OTHER], spell("One", "Draw two cards."))["ambiguous"], [])

    def test_it_counts_the_cards_that_have_the_sentence_not_the_lookups(self):
        result = audit([NARROW, BROAD_OTHER], spell("One", "Draw a card."), spell("Two", "Draw a card.\nDraw a card."))
        self.assertEqual([a["cards"] for a in result["ambiguous"]], [2])

    def test_the_real_lookup_is_put_back(self):
        original = outcomes._template
        audit([NARROW], spell("One", "Draw a card."))
        self.assertIs(outcomes._template, original)


class RenderTests(unittest.TestCase):
    def test_it_lists_the_unused_templates_and_the_sentences_that_differ(self):
        text = tool.render(audit([NARROW, BROAD_OTHER, NEVER], spell("One", "Draw a card.")))
        self.assertIn("Templates no sentence reached (2)", text)
        self.assertIn("#1", text)
        self.assertIn("frobnicate", text)
        self.assertIn("| 1 | Draw a card. | #0 | #1 |", text)

    def test_nothing_to_report(self):
        text = tool.render(audit([NARROW], spell("One", "Draw a card.")))
        self.assertIn("None.", text)
        self.assertIn("None read differently.", text)


if __name__ == "__main__":
    unittest.main()
