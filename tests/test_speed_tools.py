"""The speed-ups of issue #441: the parallel and cached audit read the same cards, and the test runner splits the work evenly."""

import importlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))  # (so the audit's worker processes can import it too)
run_tests = importlib.import_module("run_tests")

from infernal_machine import coverage
from infernal_machine.effects import outcomes  # noqa: E402


def card(name, text, rank):
    return {"name": name, "type_line": "Creature — Bear", "oracle_text": text, "mana_cost": "{1}{G}", "cmc": 2,
            "edhrec_rank": rank, "power": "2", "toughness": "2"}


class AuditTests(unittest.TestCase):
    POOL = [card("A", "Trample", 1), card("B", "Whenever the moon is full, frobnicate the widget.", 2), card("C", "Draw a card.", 3)] * 700

    def test_processes_read_the_same_cards_in_the_same_order(self):
        self.assertEqual(coverage.read_pool(self.POOL, 2), coverage.read_pool(self.POOL, 1))

    def test_a_small_pool_is_read_in_this_process(self):
        import concurrent.futures

        real, concurrent.futures.ProcessPoolExecutor = concurrent.futures.ProcessPoolExecutor, None  # (using it would raise)
        try:
            self.assertEqual(coverage.read_pool(self.POOL[:5], 8), coverage._read_cards(self.POOL[:5]))
        finally:
            concurrent.futures.ProcessPoolExecutor = real

    def test_a_card_the_report_cannot_read_is_listed_by_its_error(self):
        [(error, lines)] = coverage._read_cards([{"name": "Broken", "type_line": 5, "oracle_text": 5}])
        self.assertTrue(error and not lines)

    def test_the_line_classification_is_the_same_cached_or_not(self):
        line = "Enchant player"
        for keywords in ((), ["Enchant player"], ("Enchant player",)):
            self.assertEqual(coverage.mechanism_of(line, keywords), coverage._mechanism_of.__wrapped__(line, tuple(keywords)))
            self.assertEqual(coverage.families_of(line, keywords), coverage._families_of.__wrapped__(line, tuple(keywords)))

    def test_the_inclusion_scale_still_makes_the_probabilities_fill_the_deck(self):
        ranks = list(range(1, 3001))
        scale = coverage.inclusion_scale(ranks)
        self.assertAlmostEqual(sum(coverage.inclusion(r, scale) for r in ranks), coverage.DECK_CARDS - coverage.DECK_BASICS, delta=0.01)


class TemplateCacheTests(unittest.TestCase):
    def test_a_sentence_is_read_once(self):
        outcomes._template.cache_clear()
        first = outcomes._template("Draw a card.")
        self.assertIs(outcomes._template("Draw a card."), first)
        self.assertIsNone(outcomes._template("Frobnicate the widget."))
        self.assertEqual(outcomes._template.cache_info().hits, 1)


class RunnerTests(unittest.TestCase):
    def test_every_module_goes_to_exactly_one_shard_and_the_loads_are_close(self):
        names = [f"test_{n}" for n in "abcdefghij"]
        times = dict(zip(names, [100, 60, 50, 40, 30, 20, 10, 5, 5, 5]))
        shards = run_tests.balance(names, 3, times)
        self.assertEqual(len(shards), 3)
        self.assertEqual(sorted(n for s in shards for n in s), sorted(names))
        loads = [sum(times[n] for n in s) for s in shards]
        self.assertLessEqual(max(loads) - min(loads), 30)

    def test_fewer_modules_than_jobs_makes_fewer_shards(self):
        os.chdir(os.path.join(os.path.dirname(__file__), ".."))
        self.assertEqual(len(run_tests.balance(["test_speed_tools"], 8, {})), 1)


if __name__ == "__main__":
    unittest.main()
