"""Stopping early in matchup and impact: the rule, the rounds, the budget, and how often a null result looks clear (#410)."""

import unittest
import zlib
from unittest import mock

from infernal_machine import impact, matchup
from infernal_machine.cards import Card, Deck
from infernal_machine.matchup import GameResult, SeatLog, win_stop
from infernal_machine.sequential import MAX_LOOKS, MIN_LOOK_PAIRS, Z, confidence, look_z, schedule

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def named(name):
    return Card(name=name, mana_cost="{1}", cmc=1, type_line="Creature — Bear", power="1", toughness="1")


STARS = [named(f"Star{i}") for i in (1, 2, 3)]
DUD = named("Dud")
NOISE = named("Noise")
DECK = Deck([], [FOREST] * 20 + STARS + [DUD, NOISE], [])


def result(seat, won):
    """A finished game: the focus deck's seat won, or the next seat did (a table is up to four seats)."""
    return GameResult(focus_seat=seat, winner=seat if won else (seat + 1) % 4, turns=10, starting_seat=0, logs={i: SeatLog() for i in range(4)})


def fake_play(plans, workers=1):
    """Games without an engine: the focus deck wins when a number made from the game's seed falls under its chance. Each Star card in
    the focus deck adds 20 points to that chance (base 40%), a Dud adds nothing, and Noise has no effect but flips the outcome of its own
    games at random (so blanking it changes results with a true impact of zero)."""
    out = []
    for _, tasks in plans:
        results = []
        for decks, seat, seed, *_ in tasks:
            focus = decks[seat].main
            stars = sum(c.name.startswith("Star") for c in focus)
            chance = min(1.0, 0.4 + 0.2 * stars)
            u = (seed % 1000) / 1000
            if any(c.name == "Noise" for c in focus):
                u = ((zlib.crc32(f"noise-{seed}".encode()) % 1000) / 1000)
            results.append(result(seat, u < chance))
        out.append(results)
    return out


def duel_fake(chance):
    """A play_plans for matchups where the focus deck wins `chance` of the games, from the game's seed."""
    def play(plans, workers=1):
        return [[result(seat, (seed % 1000) / 1000 < chance) for _, seat, seed, *_ in tasks] for _, tasks in plans]
    return play


class ScheduleTests(unittest.TestCase):
    def test_the_looks_and_the_games_between_them(self):
        self.assertEqual(schedule(40), (10, 4))
        self.assertEqual(schedule(25), (9, 3))
        self.assertEqual(schedule(5), (5, 1))
        self.assertEqual(schedule(1), (1, 1))
        self.assertLessEqual(schedule(1000)[0], MAX_LOOKS)

    def test_the_interval_is_widened_for_the_looks(self):
        self.assertEqual(look_z(1), Z)
        self.assertAlmostEqual(look_z(10), 2.807, places=3)
        self.assertEqual(confidence(Z), "95%")
        self.assertEqual(confidence(look_z(10)), "99.5%")


class WinStopTests(unittest.TestCase):
    def test_a_win_rate_clearly_above_or_below_the_fair_share_stops(self):
        z = look_z(10)
        self.assertEqual(win_stop(45, 50, 0.5, z, final=False), "better")
        self.assertEqual(win_stop(5, 50, 0.5, z, final=False), "worse")
        self.assertIsNone(win_stop(27, 50, 0.5, z, final=False))

    def test_not_before_the_minimum_games_and_not_on_the_last_look(self):
        self.assertIsNone(win_stop(MIN_LOOK_PAIRS - 1, MIN_LOOK_PAIRS - 1, 0.5, look_z(10), final=False))
        self.assertEqual(win_stop(MIN_LOOK_PAIRS, MIN_LOOK_PAIRS, 0.5, look_z(10), final=False), "better")
        self.assertIsNone(win_stop(50, 50, 0.5, look_z(10), final=True))

    def test_a_pod_is_judged_against_a_quarter(self):
        self.assertEqual(win_stop(28, 50, 0.25, look_z(10), final=False), "better")
        self.assertIsNone(win_stop(28, 50, 0.5, look_z(10), final=False), "56% is not clearly away from half")


class MatchupRoundsTests(unittest.TestCase):
    OPPONENTS = {"easy": DECK, "even": DECK}

    def run_matchups(self, chance, games=40, pod=2, early=True):
        with mock.patch("infernal_machine.matchup.play_plans", duel_fake(chance)):
            return matchup.matchups(DECK, self.OPPONENTS, games=games, pod=pod, seed=0, early_stop=early)

    def test_a_lopsided_matchup_stops_before_every_game_is_played(self):
        records = self.run_matchups(0.9)
        for record in records:
            self.assertEqual(record.stopped, "better")
            self.assertLess(record.games, record.planned)
            self.assertGreaterEqual(record.games, MIN_LOOK_PAIRS)
            self.assertEqual((record.planned, record.looks), (40, 10))
            self.assertAlmostEqual(record.z, look_z(10))

    def test_a_losing_matchup_stops_as_worse(self):
        self.assertEqual({r.stopped for r in self.run_matchups(0.1)}, {"worse"})

    def test_an_even_matchup_plays_every_game_and_matches_the_plain_run(self):
        early, plain = self.run_matchups(0.5), self.run_matchups(0.5, early=False)
        self.assertEqual([r.stopped for r in early], [None, None])
        self.assertEqual([(r.wins, r.games) for r in early], [(r.wins, r.games) for r in plain])
        self.assertEqual({r.planned for r in plain}, {0}, "the plain run says nothing about stopping")
        self.assertEqual({r.z for r in plain}, {1.96})

    def test_the_report_says_the_rule_and_who_stopped(self):
        text = matchup.format_matchups(self.run_matchups(0.9), "mine")
        self.assertIn("99.5% interval", text)
        self.assertIn("Stopping rule: 10 looks", text)
        self.assertIn("easy: stopped after", text)
        self.assertIn("clearly better than the fair share", text)
        self.assertNotIn("Stopping rule", matchup.format_matchups(self.run_matchups(0.9, early=False), "mine"))

    def test_a_pod_uses_a_quarter_as_the_fair_share(self):
        with mock.patch("infernal_machine.matchup.play_plans", duel_fake(0.25)):
            records = matchup.matchups(DECK, self.OPPONENTS, games=40, pod=4, seed=0, early_stop=True)
        self.assertEqual([r.stopped for r in records], [None], "a quarter is the fair share in a pod of four")
        self.assertEqual(records[0].fair_share, 0.25)

    def test_equal_decks_are_called_clearly_better_or_worse_no_more_than_the_rule_allows(self):
        stopped = total = 0
        for seed in range(250):
            with mock.patch("infernal_machine.matchup.play_plans", duel_fake(0.5)):
                records = matchup.matchups(DECK, {"x": DECK}, games=40, pod=2, seed=seed, early_stop=True)
            stopped += records[0].stopped is not None
            total += 1
        self.assertLessEqual(stopped / total, 0.05)


class ImpactRoundsTests(unittest.TestCase):
    OPPONENTS = {"one": DECK, "two": DECK}

    def measure(self, cards, games=40, early=True, seed=0):
        with mock.patch("infernal_machine.impact.play_plans", fake_play):
            return impact.measure_impacts(DECK, self.OPPONENTS, cards, games=games, seed=seed, early_stop=early)

    def test_a_card_that_matters_stops_clear_and_one_that_does_not_plays_on(self):
        report = self.measure(["Star1", "Dud"])
        by = {c.card: c for c in report.impacts}
        self.assertEqual(by["Star1"].stopped, "clear")
        self.assertGreater(by["Star1"].impact, 0.1)
        self.assertGreater(by["Dud"].pairs, by["Star1"].pairs, "the card with nothing to show keeps being played")
        self.assertIsNone(by["Dud"].stopped)
        low, high = by["Star1"].interval
        self.assertAlmostEqual(high - low, 2 * look_z(10) * by["Star1"].error, msg="the interval is the widened one")
        self.assertEqual(by["Star1"].z, look_z(10))

    def test_the_games_played_never_pass_what_a_fixed_run_plays(self):
        report = self.measure(["Star1", "Star2", "Star3", "Dud", "Noise"])
        self.assertGreater(report.budget, 0)
        self.assertLessEqual(report.spent, report.budget)
        self.assertEqual(report.budget, (1 + 5) * 40 * 2)

    def test_the_games_played_are_counted_exactly(self):
        for cards in (["Star1", "Dud"], ["Star1", "Star2", "Star3"], ["Dud", "Noise"]):
            report = self.measure(cards)
            baseline = max(c.pairs for c in report.impacts)
            self.assertEqual(report.spent, baseline + sum(c.pairs for c in report.impacts), cards)

    def test_when_every_card_is_settled_nothing_more_is_played(self):
        report = self.measure(["Star1", "Star2", "Star3"])
        self.assertEqual({c.stopped for c in report.impacts}, {"clear"})
        self.assertLess(report.spent, report.budget)
        self.assertLess(max(c.pairs for c in report.impacts), 40 * 2, "stopped well before the fixed run's pairs")

    def test_the_games_the_settled_cards_leave_go_to_the_others(self):
        report = self.measure(["Star1", "Star2", "Star3", "Dud", "Noise"], games=40)
        dud = next(c for c in report.impacts if c.card == "Dud")
        self.assertGreater(dud.pairs, 40 * 2, "more pairs than the 40 games per opponent a fixed run plays")
        self.assertLessEqual(dud.pairs, 40 * impact.EXTEND * 2)

    def test_without_early_stopping_it_is_the_fixed_run(self):
        fixed = self.measure(["Star1", "Dud"], early=False)
        self.assertEqual((fixed.spent, fixed.budget), (0, 0))
        self.assertEqual({c.pairs for c in fixed.impacts}, {80})
        self.assertEqual({c.z for c in fixed.impacts}, {Z})
        self.assertEqual({c.stopped for c in fixed.impacts}, {None})

    def test_the_report_only_says_the_leftover_games_were_used_when_they_were(self):
        used = impact.format_impacts(self.measure(["Star1", "Star2", "Star3", "Dud", "Noise"]))
        self.assertIn("used what the others left", used)
        none_left = impact.format_impacts(self.measure(["Dud", "Noise"]))
        self.assertNotIn("used what the others left", none_left)

    def test_the_report_gives_the_rule_and_marks_the_settled_cards(self):
        text = impact.format_impacts(self.measure(["Star1", "Dud"]))
        self.assertIn("stopped early: clear", text)
        self.assertIn("Stopping rule: 10 looks", text)
        self.assertIn("99.5%", text)
        self.assertNotIn("Stopping rule", impact.format_impacts(self.measure(["Star1", "Dud"], early=False)))

    def test_a_card_with_no_true_effect_is_called_clear_no_more_than_the_rule_allows(self):
        clear = 0
        runs = 200
        for seed in range(runs):
            report = self.measure(["Noise"], games=40, seed=seed)
            clear += report.impacts[0].clear and report.impacts[0].pairs >= MIN_LOOK_PAIRS
        self.assertLessEqual(clear / runs, 0.07)


if __name__ == "__main__":
    unittest.main()
