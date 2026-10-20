"""rules_lines(card): the cached lines come back as a fresh list, so a caller that mutates or slices the result cannot change the next one."""

import unittest

from infernal_machine.effects.common import _rules_lines, rules_lines
from tests.helpers import real

CARD = real("Two Lines", "{1}", "Creature — Bear", "Flying\nWhen this creature enters, draw a card.", "1", "1")


class RulesLinesTests(unittest.TestCase):
    def test_each_ability_is_a_line(self):
        self.assertEqual(rules_lines(CARD), ["Flying", "When this creature enters, draw a card."])

    def test_the_result_is_a_fresh_list_each_time(self):
        first = rules_lines(CARD)
        first.append("junk")
        first.pop(0)
        self.assertEqual(rules_lines(CARD), ["Flying", "When this creature enters, draw a card."])
        self.assertIsNot(rules_lines(CARD), rules_lines(CARD))

    def test_a_card_is_parsed_once(self):
        rules_lines(CARD)
        before = _rules_lines.cache_info().hits
        rules_lines(CARD)
        self.assertEqual(_rules_lines.cache_info().hits, before + 1)


if __name__ == "__main__":
    unittest.main()
