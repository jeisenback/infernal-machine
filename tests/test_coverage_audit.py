"""The coverage audit tool (tools/coverage_audit.py): its numbers for a handful of cards, and the pool cache."""

import importlib.util
import json
import os
import tempfile
import unittest

_spec = importlib.util.spec_from_file_location("coverage_audit", os.path.join(os.path.dirname(__file__), "..", "tools", "coverage_audit.py"))
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def card(name, type_line, text, rank=None, **more):
    return {"name": name, "type_line": type_line, "oracle_text": text, "mana_cost": more.pop("mana_cost", ""), "cmc": 0,
            **({"edhrec_rank": rank} if rank else {}), **more}


POOL = [
    card("Plain Forest", "Basic Land — Forest", "({T}: Add {G}.)", rank=1, produced_mana=["G"]),
    card("Quick Bear", "Creature — Bear", "Trample", rank=2, mana_cost="{1}{G}", power="2", toughness="2"),
    card("Odd Bear", "Creature — Bear", "Whenever the moon is full, frobnicate the widget.", rank=3, mana_cost="{1}{G}", power="2", toughness="2"),
    card("Odd Cat", "Creature — Cat", "Whenever the moon is full, frobnicate the widget.", rank=4, mana_cost="{1}{G}", power="1", toughness="1"),
    card("Odd Elk", "Creature — Elk", "Whenever the moon is full, frobnicate the widget.\nShroud", rank=5, mana_cost="{G}", power="1", toughness="1"),
    card("Unranked Sorcery", "Sorcery", "Draw a card.", mana_cost="{1}"),
]


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.result = audit.analyze(POOL)

    def test_it_counts_the_playable_cards(self):
        self.assertEqual((self.result["total"], self.result["playable"]), (6, 3))

    def test_it_counts_by_card_type(self):
        self.assertEqual(self.result["by_type"]["Creature"], [4, 1])
        self.assertEqual(self.result["by_type"]["Land"], [1, 1])
        self.assertEqual(self.result["by_type"]["Sorcery"], [1, 1])

    def test_it_weights_by_popularity(self):
        self.assertEqual(self.result["popular"][100], (2, 5), "of the five ranked cards, the Forest and the Bear are playable")

    def test_the_same_unsupported_line_on_several_cards_is_one_group_most_played_first(self):
        group = self.result["shapes"]["Whenever the moon is full, frobnicate the widget."]
        self.assertEqual(group, ["Odd Bear", "Odd Cat", "Odd Elk"])

    def test_a_card_with_one_gap_counts_as_a_single_gap(self):
        self.assertEqual(self.result["one_gap"], 3)
        self.assertEqual(self.result["only_gap"]["Whenever the moon is full, frobnicate the widget."], ["Odd Bear", "Odd Cat", "Odd Elk"])

    def test_a_card_the_report_cannot_read_is_listed_not_fatal(self):
        broken = audit.analyze([{"name": "Broken", "cmc": "not a number"}])
        self.assertEqual((broken["total"], broken["crashes"]), (0, ["Broken: ValueError"]))


class ShapeTests(unittest.TestCase):
    def test_numbers_and_mana_symbols_are_blurred(self):
        self.assertEqual(audit.shape("Madness {1}{R}"), "Madness {M}{M}")
        self.assertEqual(audit.shape("Toxic 2"), "Toxic N")
        self.assertEqual(audit.shape("Bushido three"), "Bushido N")

    def test_long_lines_are_cut(self):
        self.assertEqual(len(audit.shape("x" * 300)), 100)


class RenderTests(unittest.TestCase):
    def test_the_summary_names_the_numbers_and_the_groups(self):
        text = audit.render(audit.analyze(POOL), top=5)
        self.assertIn("3 of 6 Commander-legal cards fully playable (50.0%)", text)
        self.assertIn("| Creature | 1 of 4 (25%) |", text)
        self.assertIn("| 3 | `Whenever the moon is full, frobnicate the widget.` | Odd Bear #3, Odd Cat #4 |", text)

    def test_a_pipe_in_a_line_does_not_break_the_table(self):
        pool = [card("Pipes", "Creature — Bear", "Choose one | or the other", power="1", toughness="1")]
        self.assertNotIn("one | or", audit.render(audit.analyze(pool)))


class PoolCacheTests(unittest.TestCase):
    def test_a_fresh_cache_is_used_without_the_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "pool.json")
            with open(path, "w") as f:
                json.dump(POOL, f)
            self.assertEqual(audit.fetch_pool(path), POOL)


if __name__ == "__main__":
    unittest.main()
