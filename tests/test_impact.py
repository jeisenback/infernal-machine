"""Measuring a card's impact in real games, with the same games played with the card and with a blank in its place (#389)."""

import contextlib
import io
import unittest
from dataclasses import replace

from infernal_machine.cards import Card, CardNotFound, Deck
from infernal_machine.impact import MIN_DIFFERING, CardGameImpact, blanked, format_impacts, main, measure_impacts, weakest_cards
from infernal_machine.tune import BLANK

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))
OGRE = Card(name="Hill Giant", mana_cost="{3}{G}", cmc=4, type_line="Creature — Giant", power="3", toughness="3", color_identity=("G",))
DUD = Card(name="Dud", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1", color_identity=("G",))
ODD = Card(name="Odd Spell", mana_cost="{1}{G}", cmc=2, type_line="Sorcery", oracle_text="Exchange the frobnicator of each player with the quuxes.",
           color_identity=("G",))
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))
FAST = dict(games=5, max_turns=25, goldfish_games=40, goldfish_turns=4, seed=1)


def deck(bears=36, extras=()):
    return Deck([], [FOREST] * 24 + list(extras) + [BEAR] * (bears - len(extras)), [])


class BlankedTests(unittest.TestCase):
    def test_every_copy_is_replaced_and_the_size_stays(self):
        d = deck(extras=[OGRE] * 3)
        b = blanked(d, "Hill Giant")
        self.assertEqual(len(b.main), len(d.main))
        self.assertEqual([c.name for c in b.main].count("Hill Giant"), 0)
        self.assertEqual([c.name for c in b.main].count("(blank)"), 3)
        self.assertEqual([c for c in b.main if c is not BLANK], [c for c in d.main if c.name != "Hill Giant"])  # nothing else moves

    def test_the_original_deck_is_untouched(self):
        d = deck(extras=[OGRE])
        blanked(d, "Hill Giant")
        self.assertIn(OGRE, d.main)


class SelectionTests(unittest.TestCase):
    def test_the_weakest_by_goldfish_leave_out_the_commander_and_lands(self):
        d = Deck([BOSS], [FOREST] * 38 + [DUD] * 8 + [BEAR] * 53, [])
        names = weakest_cards(d, 5, games=60, turns=4, seed=1)
        self.assertNotIn("Boss", names)
        self.assertNotIn("Forest", names)
        self.assertEqual(names[0], "Dud")  # a card that cannot be cast is the weakest the goldfish sees

    def test_cards_can_be_named(self):
        report = measure_impacts(deck(extras=[OGRE]), {"m": deck()}, ["Hill Giant"], **FAST)
        self.assertEqual([c.card for c in report.impacts], ["Hill Giant"])

    def test_a_card_not_in_the_deck_is_an_error(self):
        with self.assertRaises(ValueError) as error:
            measure_impacts(deck(), {"m": deck()}, ["Nonexistent"], **FAST)
        self.assertIn("not in the main deck", str(error.exception))

    def test_a_commander_is_not_measured(self):
        commander_deck = Deck([BOSS], [FOREST] * 40 + [BEAR] * 59, [])
        with self.assertRaises(ValueError) as error:
            measure_impacts(commander_deck, {"m": commander_deck}, ["Boss"], **FAST)
        self.assertIn("commander", str(error.exception))

    def test_the_default_is_the_top_weakest(self):
        report = measure_impacts(Deck([], [FOREST] * 24 + [DUD] * 4 + [OGRE] * 4 + [BEAR] * 28, []), {"m": deck()}, top=2, **FAST)
        self.assertEqual(len(report.impacts), 2)
        self.assertIn("Dud", [c.card for c in report.impacts])


class MeasureTests(unittest.TestCase):
    def test_a_card_identical_to_the_blank_adds_nothing_and_changes_no_game(self):
        # The deck holds blanks already; "blanking" them again is the same deck, so every pair is identical.
        with_blanks = Deck([], [FOREST] * 24 + [BLANK] * 6 + [BEAR] * 30, [])
        report = measure_impacts(with_blanks, {"m": deck()}, ["(blank)"], **FAST)
        c = report.impacts[0]
        self.assertEqual((c.impact, c.error, c.differing, c.needed), (0.0, 0.0, 0, None))
        self.assertFalse(c.clear)

    def test_a_card_the_deck_depends_on_is_found(self):
        # Every creature is a Grizzly Bears: without them the deck casts nothing. Against a deck of bears that is a clear loss.
        report = measure_impacts(deck(), {"bears": deck()}, ["Grizzly Bears"], games=20, max_turns=25, seed=1)
        c = report.impacts[0]
        self.assertGreater(c.impact, 0.1)
        self.assertTrue(c.clear)
        self.assertEqual((c.copies, c.pairs), (36, 20))
        self.assertGreaterEqual(c.differing, MIN_DIFFERING)
        self.assertGreater(c.needed or 0, 0)  # enough pairs differ to give a spread, and so a number of pairs to resolve 5 points

    def test_the_sign_is_what_the_card_adds_not_what_the_blank_does(self):
        # A deck of duds with one playable bear slot: the bears' impact is positive, and swapping duds for blanks changes nothing.
        useless = measure_impacts(Deck([], [FOREST] * 24 + [DUD] * 12 + [BEAR] * 24, []), {"bears": deck()}, ["Dud"], **FAST).impacts[0]
        useful = measure_impacts(Deck([], [FOREST] * 24 + [DUD] * 12 + [BEAR] * 24, []), {"bears": deck()}, ["Grizzly Bears"], **FAST).impacts[0]
        self.assertGreater(useful.impact, useless.impact)

    def test_too_few_differing_pairs_give_no_estimate(self):
        report = measure_impacts(deck(extras=[OGRE]), {"m": deck()}, ["Hill Giant"], games=4, max_turns=15, seed=1)
        c = report.impacts[0]
        self.assertLess(c.differing, MIN_DIFFERING)  # (four pairs cannot differ eight times)
        self.assertIsNone(c.needed)
        self.assertIn(f"a dash means fewer than {MIN_DIFFERING} pairs differed", " ".join(report.notes))

    def test_the_estimate_waits_for_enough_differing_pairs(self):
        # Pairs do differ here (the bears matter), so a spread exists; only the threshold decides whether it is trusted.
        from unittest import mock
        with mock.patch("infernal_machine.impact.MIN_DIFFERING", 10_000):
            c = measure_impacts(deck(), {"bears": deck()}, ["Grizzly Bears"], games=10, max_turns=25, seed=1).impacts[0]
        self.assertGreater(c.differing, 0)
        self.assertIsNone(c.needed)
        with mock.patch("infernal_machine.impact.MIN_DIFFERING", 1):
            c = measure_impacts(deck(), {"bears": deck()}, ["Grizzly Bears"], games=10, max_turns=25, seed=1).impacts[0]
        self.assertGreater(c.needed or 0, 0)

    def test_the_baseline_is_played_once_and_shared(self):
        report = measure_impacts(deck(extras=[OGRE] * 4), {"m": deck()}, ["Hill Giant", "Grizzly Bears"], **FAST)
        self.assertEqual(len(report.impacts), 2)
        self.assertEqual({c.pairs for c in report.impacts}, {5})
        self.assertTrue(0.0 <= report.baseline_score <= 1.0)

    def test_the_weakest_come_first(self):
        report = measure_impacts(deck(extras=[OGRE] * 4), {"m": deck()}, ["Hill Giant", "Grizzly Bears"], games=8, max_turns=25, seed=1)
        per_copy = [c.impact / c.copies for c in report.impacts]
        self.assertEqual(per_copy, sorted(per_copy))

    def test_a_pod_pairs_games_too(self):
        report = measure_impacts(deck(extras=[OGRE]), {"a": deck(), "b": deck()}, ["Hill Giant"], games=3, pod=3, max_turns=15, seed=1)
        self.assertEqual(report.opponents, ["a", "b"])
        self.assertEqual(report.impacts[0].pairs, 3)  # three pod games in all, each played with and without the card

    def test_progress_is_reported_for_each_step(self):
        messages = []
        measure_impacts(deck(extras=[OGRE]), {"m": deck()}, ["Hill Giant", "Grizzly Bears"], progress=messages.append, **FAST)
        self.assertEqual(messages, ["Baseline...", "Hill Giant (1/2)...", "Grizzly Bears (2/2)..."])

    def test_a_card_the_engine_cannot_read_is_marked(self):
        report = measure_impacts(deck(extras=[ODD]), {"m": deck()}, ["Odd Spell"], **FAST)
        self.assertIn("frobnicator", report.impacts[0].unreadable or "")
        self.assertTrue(any("Odd Spell" in note and "can't fully play" in note for note in report.notes))


class FormatTests(unittest.TestCase):
    def report(self):
        a = CardGameImpact("Weak Card", 1, 40, -0.05, 0.04, 6, needed=300)
        b = CardGameImpact("Strong Card", 2, 40, 0.20, 0.05, 14, "Exchange the frobnicator of each player with the quuxes.", needed=40)
        from infernal_machine.impact import ImpactReport
        return ImpactReport(20, ["one", "two"], 0.55, [a, b], ["a note"])

    def test_the_table(self):
        text = format_impacts(self.report())
        self.assertIn("20 paired games against one, two for each of 2 cards", text)
        self.assertIn("The unchanged deck scores 55.0%.", text)
        weak = next(line for line in text.splitlines() if line.startswith("Weak Card"))
        strong = next(line for line in text.splitlines() if line.startswith("Strong Card"))
        self.assertIn("-5.0 ± 4.0  (within noise)", weak)
        self.assertIn("+20.0 ± 5.0", strong)
        self.assertNotIn("within noise", strong)
        self.assertIn("can't read: Exchange the frobnicator", strong)
        self.assertRegex(weak.rstrip(), r"\s300$")  # the pairs it takes to resolve 5 points, in the last column
        self.assertTrue(text.rstrip().endswith("a note"))

    def test_many_opponents_are_counted_not_listed(self):
        report = replace(self.report(), opponents=["a", "b", "c", "d"])
        self.assertIn("against 4 opponents", format_impacts(report))

    def test_no_estimate_when_no_pair_differed(self):
        c = CardGameImpact("Idle", 1, 40, 0.0, 0.0, 0)
        from infernal_machine.impact import ImpactReport
        self.assertRegex(format_impacts(ImpactReport(40, ["x"], 0.5, [c])), r"Idle .*\s0\s+-\s*$")


class FakeSource:
    def __init__(self, *cards):
        self.cards = {c.name: c for c in cards}

    def get(self, name):
        if name not in self.cards:
            raise CardNotFound(name)
        return self.cards[name]

    def get_many(self, names):
        return {n: self.get(n) for n in dict.fromkeys(names)}


class CommandLineTests(unittest.TestCase):
    def run_main(self, *options, files=None):
        import os
        import tempfile
        files = files or {"mine.txt": "24 Forest\n30 Grizzly Bears\n6 Hill Giant\n", "theirs.txt": "24 Forest\n36 Grizzly Bears\n"}
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name, text in files.items():
                path = os.path.join(directory, name)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                paths.append(path)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main([*paths, "--games", "3", "--max-turns", "20", "--workers", "1", "--goldfish-games", "30", *options], source=FakeSource(FOREST, BEAR, OGRE))
            return code, out.getvalue(), err.getvalue()

    def test_named_cards(self):
        code, out, err = self.run_main("--cards", "Hill Giant")
        self.assertEqual(code, 0)
        self.assertIn("Card impact in real games: 3 paired games against theirs for each of 1 cards.", out)
        self.assertIn("Hill Giant", out)
        self.assertIn("Hill Giant (1/1)...", err)

    def test_the_default_picks_the_weakest(self):
        code, out, _ = self.run_main("--top", "1")
        self.assertEqual(code, 0)
        self.assertIn("for each of 1 cards", out)

    def test_an_unknown_card_is_a_message_not_a_traceback(self):
        code, out, err = self.run_main("--cards", "Nonexistent")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("Error: Nonexistent is not in the main deck", err)


if __name__ == "__main__":
    unittest.main()
