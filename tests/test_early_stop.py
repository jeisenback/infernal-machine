"""Comparing builds in rounds and stopping when the answer is clear or hopeless (#393)."""

import random
import unittest

from infernal_machine.compare import HOPELESS_FACTOR, MAX_LOOKS, MIN_LOOK_PAIRS, Z, compare_builds, format_comparison, look_z, stop_reason, summarize
from tests.test_compare import BEAR, DUD, standard


def sequence(rng, mean, pairs):
    """Per-pair differences in score, each -1, 0 or 1 (40% of pairs come out the same), with the given mean."""
    up = 0.3 + mean / 2
    down = 0.3 - mean / 2
    return [1.0 if (x := rng.random()) < up else -1.0 if x < up + down else 0.0 for _ in range(pairs)]


def looked_at(differences, looks, z):
    """What a comparison of these differences says at each of `looks` equal looks: (why it stops, if it does, whether it says clear then,
    and the pairs by then). The plan is taken as too big for "hopeless" to come into it: these are about the "clear" rule."""
    planned, step = 10_000, len(differences) // looks
    for look in range(1, looks + 1):
        c = summarize(differences[:look * step], [], 0)
        c.z = z
        reason = stop_reason(c, planned, look == looks)
        if reason or look == looks:
            return reason, c.clear, look * step


class RuleTests(unittest.TestCase):
    def test_the_interval_widens_with_the_number_of_looks(self):
        self.assertEqual(look_z(1), Z)
        self.assertAlmostEqual(look_z(10), 2.807, places=3)
        self.assertGreater(look_z(10), look_z(5))
        self.assertGreater(look_z(5), look_z(2))

    def test_equal_builds_are_called_clear_no_more_than_the_rule_allows(self):
        rng = random.Random(393)
        runs = 1500
        falsely = sum(looked_at(sequence(rng, 0.0, 200), 10, look_z(10))[1] for _ in range(runs))
        self.assertLessEqual(falsely / runs, 0.05)

    def test_looking_ten_times_at_the_plain_interval_would_break_it(self):
        rng = random.Random(393)
        runs = 1500
        falsely = sum(looked_at(sequence(rng, 0.0, 200), 10, Z)[1] for _ in range(runs))
        self.assertGreater(falsely / runs, 0.10)  # (which is why each look is widened)

    def test_a_real_difference_stops_early(self):
        rng = random.Random(7)
        runs = 200
        stops = [looked_at(sequence(rng, 0.5, 200), 10, look_z(10)) for _ in range(runs)]
        early = [s for s in stops if s[0] == "clear"]
        self.assertGreater(len(early) / runs, 0.9)
        self.assertLess(sum(s[2] for s in early) / len(early), 100)

    def test_nothing_stops_on_too_few_pairs(self):
        c = summarize([1.0] * (MIN_LOOK_PAIRS - 1), [], 0)  # (every pair alike: an interval of no width)
        self.assertTrue(c.clear)
        self.assertIsNone(stop_reason(c, 200, final=False))
        self.assertEqual(stop_reason(summarize([1.0] * MIN_LOOK_PAIRS, [], 0), 200, final=False), "clear")

    def test_the_last_look_never_stops_early(self):
        self.assertIsNone(stop_reason(summarize([1.0] * 60, [], 0), 60, final=True))

    def test_a_noisy_nothing_is_hopeless_but_only_with_enough_differing_pairs(self):
        noisy = [1.0, -1.0] * 20 + [0.0] * 20
        c = summarize(noisy, [], 0)
        self.assertGreater(c.pairs_needed(0.05), HOPELESS_FACTOR * 60)
        self.assertEqual(stop_reason(c, 60, final=False), "hopeless")
        self.assertIsNone(stop_reason(c, 10_000, final=False))  # (a plan big enough to settle it is not hopeless)
        few = summarize([1.0, -1.0] * 3 + [0.0] * 40, [], 0)
        self.assertIsNone(stop_reason(few, 60, final=False))  # (six differing pairs: the spread is a guess)


class PlayedTests(unittest.TestCase):
    OPPONENTS = {"one": standard(BEAR), "two": standard(BEAR)}

    def test_a_clearly_better_build_stops_before_every_pair_is_played(self):
        c = compare_builds(standard(DUD), standard(BEAR), self.OPPONENTS, games=20, max_turns=25, early_stop=True)
        self.assertEqual(c.stopped, "clear")
        self.assertLess(c.pairs, c.planned)
        self.assertEqual((c.planned, c.looks), (40, MAX_LOOKS))
        self.assertGreaterEqual(c.pairs, MIN_LOOK_PAIRS)
        text = format_comparison(c)
        self.assertIn(f"Stopped early: clearly better after {c.pairs} of 40 planned pairs", text)
        self.assertIn("99.5% interval", text)
        self.assertIn("Stopping rule: 10 looks, one per 2 games per opponent", text)

    def test_equal_builds_play_every_pair_and_match_the_plain_run(self):
        early = compare_builds(standard(BEAR), standard(BEAR), self.OPPONENTS, games=6, max_turns=8, early_stop=True)
        plain = compare_builds(standard(BEAR), standard(BEAR), self.OPPONENTS, games=6, max_turns=8)
        self.assertIsNone(early.stopped)
        self.assertEqual((early.pairs, early.difference, early.same), (plain.pairs, plain.difference, plain.same))
        self.assertIn("Played all 12 planned pairs; neither stop applied.", format_comparison(early))
        self.assertIsNone(plain.stopped)
        self.assertNotIn("Stopping rule", format_comparison(plain))

    def test_the_rounds_play_the_same_games_as_one_run(self):
        a = compare_builds(standard(DUD), standard(BEAR), {"one": standard(BEAR)}, games=4, max_turns=8)
        b = compare_builds(standard(DUD), standard(BEAR), {"one": standard(BEAR)}, games=4, max_turns=8, early_stop=True)
        self.assertEqual((a.pairs, a.changed_score, a.baseline_score), (b.pairs, b.changed_score, b.baseline_score))


if __name__ == "__main__":
    unittest.main()
