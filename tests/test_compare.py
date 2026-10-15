"""Comparing two builds of a deck head to head on paired games (#374)."""

import math
import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.compare import compare_builds, deck_diff, format_comparison, pair_up, score, summarize
from infernal_machine.matchup import GameResult, plan_games

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
DUD = Card(name="Dud", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1")  # never castable with Forests
ODD = Card(name="Odd Spell", mana_cost="{1}{G}", cmc=2, type_line="Sorcery", oracle_text="Exchange the frobnicator of each player with the quuxes.")
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))
CHANGER = Card(name="Changer", mana_cost="{1}{G}", cmc=2, type_line="Creature — Elf", power="1", toughness="1", color_identity=("G",), game_changer=True)


def standard(spell, extra=()):
    return Deck([], [FOREST] * 24 + list(extra) + [spell] * (36 - len(extra)), [])


def result(winner, seat=0, error=None):
    return GameResult(focus_seat=seat, winner=winner, error=error)


class ScoreTests(unittest.TestCase):
    def test_a_win_is_one_a_draw_a_half_a_loss_nothing(self):
        self.assertEqual([score(result(0)), score(result(None)), score(result(1))], [1.0, 0.5, 0.0])
        self.assertEqual(score(result(1, seat=1)), 1.0)  # (the focus deck's seat, not seat zero)

    def test_the_diff_of_two_decks(self):
        a = Deck([BOSS], [BEAR] * 3 + [DUD] * 2, [])
        b = Deck([BOSS], [BEAR] * 1 + [DUD] * 2 + [FOREST] * 2, [])
        self.assertEqual(deck_diff(a, b), ({"Grizzly Bears": 2}, {"Forest": 2}))
        self.assertEqual(deck_diff(a, a), ({}, {}))


class StatisticsTests(unittest.TestCase):
    def test_the_mean_the_spread_and_the_interval(self):
        # ten pairs: the changed build scored 1 higher in six, 1 lower in one, the same in three
        differences = [1.0] * 6 + [-1.0] + [0.0] * 3
        c = summarize(differences, [], 0)
        self.assertAlmostEqual(c.difference, 0.5)
        sd = math.sqrt(sum((d - 0.5) ** 2 for d in differences) / 9)
        self.assertAlmostEqual(c.spread, sd)
        self.assertAlmostEqual(c.error, sd / math.sqrt(10))
        low, high = c.interval
        self.assertAlmostEqual(high - low, 2 * 1.96 * c.error)
        self.assertEqual((c.changed_better, c.baseline_better, c.same), (6, 1, 3))
        self.assertTrue(c.clear)

    def test_a_small_difference_in_few_pairs_is_within_noise(self):
        c = summarize([1.0, -1.0, 0.0, 1.0], [], 0)
        self.assertFalse(c.clear)
        self.assertLess(c.interval[0], 0)

    def test_pairs_needed_grows_as_the_difference_shrinks(self):
        c = summarize([1.0, -1.0, 0.0, 0.0, 1.0, 0.0, 0.0, -1.0], [], 0)
        self.assertEqual(c.pairs_needed(0.10), math.ceil((1.96 * c.spread / 0.10) ** 2))
        self.assertEqual(c.pairs_needed(0.05), math.ceil((1.96 * c.spread / 0.05) ** 2))
        self.assertGreater(c.pairs_needed(0.05), c.pairs_needed(0.10))

    def test_no_differences_means_no_estimate(self):
        c = summarize([0.0] * 5, [], 0)
        self.assertEqual((c.difference, c.spread, c.pairs_needed(0.05), c.clear), (0.0, 0.0, None, False))

    def test_a_pair_is_dropped_when_either_game_failed(self):
        before = [[result(0), result(1), result(0, error="timeout")]]
        after = [[result(0), result(0, error="boom"), result(0)]]
        differences, lines, dropped = pair_up(before, after, ["opp"])
        self.assertEqual((differences, dropped, lines[0].pairs), ([0.0], 2, 1))

    def test_per_opponent_lines_are_averaged_into_the_total(self):
        before = [[result(1), result(1)], [result(0)]]
        after = [[result(0), result(1)], [result(0)]]
        c = summarize(*pair_up(before, after, ["a", "b"]))
        self.assertEqual([(o.opponent, o.pairs, o.baseline, o.changed) for o in c.opponents], [("a", 2, 0.0, 0.5), ("b", 1, 1.0, 1.0)])
        self.assertAlmostEqual(c.baseline_score, 1 / 3)
        self.assertAlmostEqual(c.changed_score, 2 / 3)
        self.assertAlmostEqual(c.difference, 1 / 3)


class PlanTests(unittest.TestCase):
    def test_both_builds_play_the_same_games(self):
        opponents = {"a": standard(BEAR), "b": standard(BEAR, [DUD])}
        for pod in (2, 3):
            one = plan_games(standard(BEAR), opponents, 6, pod, 7, 30, 60.0)
            two = plan_games(standard(DUD), opponents, 6, pod, 7, 30, 60.0)
            for (name_a, tasks_a), (name_b, tasks_b) in zip(one, two):
                self.assertEqual(name_a, name_b)
                for a, b in zip(tasks_a, tasks_b):
                    self.assertEqual((a[1], a[2], a[3]), (b[1], b[2], b[3]))  # seat, seed, turn limit
                    self.assertEqual([d for i, d in enumerate(a[0]) if i != a[1]], [d for i, d in enumerate(b[0]) if i != b[1]])  # the opponents


class CompareTests(unittest.TestCase):
    def test_two_identical_builds_never_differ(self):
        deck = standard(BEAR)
        c = compare_builds(deck, deck, {"mirror": standard(BEAR)}, games=6, max_turns=10)
        self.assertEqual((c.pairs, c.dropped, c.difference, c.spread, c.same), (6, 0, 0.0, 0.0, 6))
        text = format_comparison(c, "old", "new")
        self.assertIn("no card differs", text)
        self.assertIn("within noise", text)
        self.assertIn("No pair came out differently", text)

    def test_a_clearly_better_build_is_found(self):
        c = compare_builds(standard(DUD), standard(BEAR), {"bears": standard(BEAR)}, games=10, max_turns=25)
        self.assertGreater(c.changed_score, c.baseline_score)
        self.assertGreater(c.changed_better, c.baseline_better)
        self.assertTrue(c.clear)
        self.assertEqual(c.removed, {"Dud": 36})
        self.assertEqual(c.added, {"Grizzly Bears": 36})
        text = format_comparison(c, "duds", "bears")
        self.assertIn("-36 Dud, +36 Grizzly Bears", text)
        self.assertIn("the changed build is better", text)
        self.assertRegex(text, r"Difference \+\d+\.\d points")
        self.assertIn("pairs separate a 10 point difference", text)

    def test_the_goldfish_is_shown_side_by_side(self):
        c = compare_builds(standard(DUD), standard(BEAR), {"bears": standard(BEAR)}, games=2, max_turns=6, goldfish_games=40, goldfish_turns=4)
        self.assertIsNotNone(c.goldfish)
        text = format_comparison(c, "old", "new")
        self.assertIn("Goldfish (40 games, 4 turns):", text)
        self.assertIn("mana spent / available", text)
        self.assertIsNone(compare_builds(standard(BEAR), standard(BEAR), {"m": standard(BEAR)}, games=2, max_turns=6).goldfish)

    def test_several_opponents_get_a_line_each(self):
        c = compare_builds(standard(DUD), standard(BEAR), {"one": standard(BEAR), "two": standard(BEAR)}, games=2, max_turns=6)
        self.assertEqual([o.opponent for o in c.opponents], ["one", "two"])
        self.assertIn("opponent                       pairs", format_comparison(c))

    def test_a_pod_pairs_games_too(self):
        c = compare_builds(standard(DUD), standard(BEAR), {"a": standard(BEAR), "b": standard(BEAR)}, games=3, pod=3, max_turns=6)
        self.assertEqual([o.opponent for o in c.opponents], ["pod of 3"])
        self.assertEqual(c.pairs + c.dropped, 3)

    def test_decks_with_and_without_a_commander_cannot_be_compared(self):
        with self.assertRaises(ValueError):
            compare_builds(standard(BEAR), Deck([BOSS], [FOREST] * 99, []), {"m": standard(BEAR)}, games=1)

    def test_no_pair_finishing_says_so(self):
        c = compare_builds(standard(BEAR), standard(BEAR), {"m": standard(BEAR)}, games=2, max_turns=6, time_limit=0.0)
        self.assertEqual((c.pairs, c.dropped), (0, 2))
        self.assertIn("No pair finished", format_comparison(c))


class NoteTests(unittest.TestCase):
    def test_builds_of_different_sizes(self):
        notes = compare_builds(standard(BEAR), Deck([], [FOREST] * 25 + [BEAR] * 36, []), {"m": standard(BEAR)}, games=1, max_turns=4).notes
        self.assertTrue(any("60 and 61 cards" in note for note in notes))

    def test_a_changed_card_the_engine_cannot_read_is_named(self):
        notes = compare_builds(standard(BEAR), standard(BEAR, [ODD]), {"m": standard(BEAR)}, games=1, max_turns=4).notes
        self.assertTrue(any("Odd Spell" in note and "can't fully play" in note for note in notes), notes)

    def test_an_unreadable_card_that_did_not_change_is_not(self):
        both = standard(BEAR, [ODD])
        self.assertEqual([n for n in compare_builds(both, both, {"m": standard(BEAR)}, games=1, max_turns=4).notes if "Odd Spell" in n], [])

    def test_a_change_of_bracket_is_pointed_out(self):
        plain = Deck([BOSS], [FOREST] * 40 + [BEAR] * 59, [])
        stronger = Deck([BOSS], [FOREST] * 40 + [CHANGER] + [BEAR] * 58, [])
        notes = compare_builds(plain, stronger, {"m": plain}, games=1, max_turns=4).notes
        self.assertTrue(any("baseline plays at Bracket 1 or higher, the changed build at 3 or higher" in note for note in notes), notes)


if __name__ == "__main__":
    unittest.main()
