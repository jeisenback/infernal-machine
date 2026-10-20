"""The tracked decks against their baseline (#475): a card that played and no longer does fails the weekly coverage job."""

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from infernal_machine.cards import BulkSource, Card, Deck
from tests.helpers import real

_spec = importlib.util.spec_from_file_location("coverage_audit", Path(__file__).parent.parent / "tools" / "coverage_audit.py")
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

ROOT = Path(__file__).parent.parent
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = real("Cub", "{1}{G}", "Creature — Bear", "", "2", "2")
MOON = "Whenever the moon is full, frobnicate the widget."
MOON_A = real("Moon Cat", "{1}{G}", "Creature — Cat", MOON, "1", "1")
MOON_B = real("Moon Elk", "{1}{G}", "Creature — Elk", MOON, "1", "1")


def deck(*cards):
    return Deck([], [c for card, n in cards for c in [card] * n], [])


def analyzed(**decks):
    return audit.analyze_decks(decks)


class BaselineTests(unittest.TestCase):
    def test_the_baseline_names_the_cards_that_cannot_be_played_sorted(self):
        result = analyzed(mine=deck((FOREST, 20), (MOON_B, 1), (MOON_A, 2), (BEAR, 1)))
        self.assertEqual(audit.baseline_of(result), {"decks": {"mine": {"cards": 24, "unplayable": ["Moon Cat", "Moon Elk"]}}})

    def test_a_deck_with_nothing_wrong_has_an_empty_list(self):
        self.assertEqual(audit.baseline_of(analyzed(mine=deck((FOREST, 5))))["decks"]["mine"]["unplayable"], [])

    def test_the_same_decks_against_their_own_baseline_change_nothing(self):
        result = analyzed(mine=deck((FOREST, 20), (MOON_A, 1)))
        comparison = audit.compare_baseline(audit.baseline_of(result), result)
        self.assertEqual(comparison, {"regressed": {}, "fixed": {}, "new_decks": [], "missing_decks": []})

    def test_a_card_that_played_and_no_longer_does_is_named(self):
        before = audit.baseline_of(analyzed(mine=deck((FOREST, 20), (MOON_A, 1))))
        after = analyzed(mine=deck((FOREST, 20), (MOON_A, 1), (MOON_B, 1)))  # Moon Elk was not in the baseline's list: it played then
        comparison = audit.compare_baseline(before, after)
        self.assertEqual(comparison["regressed"], {"mine": ["Moon Elk"]})
        self.assertEqual(comparison["fixed"], {})

    def test_a_card_that_now_plays_is_a_reminder_and_not_a_regression(self):
        before = audit.baseline_of(analyzed(mine=deck((FOREST, 20), (MOON_A, 1))))
        after = analyzed(mine=deck((FOREST, 20), (BEAR, 1)))
        comparison = audit.compare_baseline(before, after)
        self.assertEqual((comparison["regressed"], comparison["fixed"]), ({}, {"mine": ["Moon Cat"]}))

    def test_one_card_fixed_and_another_broken_in_the_same_week_still_regresses(self):
        before = audit.baseline_of(analyzed(mine=deck((FOREST, 20), (MOON_A, 1))))
        after = analyzed(mine=deck((FOREST, 20), (MOON_B, 1)))  # a different card is the unplayable one now
        comparison = audit.compare_baseline(before, after)
        self.assertEqual(comparison["regressed"], {"mine": ["Moon Elk"]}, "counts alone (1 and 1) would have hidden it")
        self.assertEqual(comparison["fixed"], {"mine": ["Moon Cat"]})

    def test_a_deck_the_baseline_has_not_seen_is_recorded_and_does_not_fail(self):
        before = audit.baseline_of(analyzed(old=deck((FOREST, 5))))
        after = analyzed(old=deck((FOREST, 5)), brand_new=deck((FOREST, 5), (MOON_A, 1)))
        comparison = audit.compare_baseline(before, after)
        self.assertEqual((comparison["new_decks"], comparison["regressed"]), (["brand_new"], {}))

    def test_a_baseline_deck_that_was_not_checked_is_reported(self):
        before = audit.baseline_of(analyzed(a=deck((FOREST, 5)), b=deck((FOREST, 5))))
        comparison = audit.compare_baseline(before, analyzed(a=deck((FOREST, 5))))
        self.assertEqual(comparison["missing_decks"], ["b"])

    def test_the_report_names_what_regressed_and_what_now_plays(self):
        before = audit.baseline_of(analyzed(mine=deck((FOREST, 20), (MOON_A, 1))))
        after = analyzed(mine=deck((FOREST, 20), (MOON_B, 1)))
        text = audit.render_baseline(audit.compare_baseline(before, after), after)
        self.assertIn("Regressed", text)
        self.assertIn("mine: Moon Elk", text)
        self.assertIn("Now playable", text)
        self.assertIn("mine: Moon Cat", text)
        self.assertIn("**mine**: 20 of 21 cards fully playable (95%)", text)


class CommandLineTests(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = audit.main(list(args))
            except SystemExit as stop:
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    def files(self, directory, *decks):
        bulk = os.path.join(directory, "bulk.json")
        with open(bulk, "w", encoding="utf-8") as f:
            json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (FOREST, BEAR, MOON_A, MOON_B)}}, f)
        paths = []
        for name, text in decks:
            path = os.path.join(directory, name + ".txt")
            Path(path).write_text(text, encoding="utf-8")
            paths.append(path)
        return bulk, paths

    def test_write_then_check_passes_and_a_new_unplayable_card_fails(self):
        with tempfile.TemporaryDirectory() as d:
            bulk, (path,) = self.files(d, ("mine", "20 Forest\n1 Moon Cat\n"))
            base = os.path.join(d, "baseline.json")
            code, _, _ = self.run_main("--decks", path, "--bulk", bulk, "--write-baseline", base)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(Path(base).read_text(encoding="utf-8"))["decks"]["mine"]["unplayable"], ["Moon Cat"])
            code, out, _ = self.run_main("--decks", path, "--bulk", bulk, "--baseline", base)
            self.assertEqual(code, 0)
            self.assertIn("Tracked decks against their baseline", out)
            Path(path).write_text("20 Forest\n1 Moon Cat\n1 Moon Elk\n", encoding="utf-8")
            code, out, _ = self.run_main("--decks", path, "--bulk", bulk, "--baseline", base)
            self.assertEqual(code, 1)
            self.assertIn("mine: Moon Elk", out)

    def test_a_missing_deck_file_fails_loudly_instead_of_passing_on_zero_decks(self):
        with tempfile.TemporaryDirectory() as d:
            bulk, _ = self.files(d)
            code, _, err = self.run_main("--decks", os.path.join(d, "gone.txt"), "--bulk", bulk, "--baseline", os.path.join(d, "b.json"))
            self.assertEqual(code, 2)
            self.assertIn("cannot read the deck", err)

    def test_a_baseline_deck_that_is_not_among_the_checked_files_fails(self):
        with tempfile.TemporaryDirectory() as d:
            bulk, (a, b) = self.files(d, ("a", "20 Forest\n"), ("b", "20 Forest\n"))
            base = os.path.join(d, "baseline.json")
            self.run_main("--decks", a, b, "--bulk", bulk, "--write-baseline", base)
            code, out, _ = self.run_main("--decks", a, "--bulk", bulk, "--baseline", base)
            self.assertEqual(code, 1)
            self.assertIn("In the baseline but not checked:** b", out)

    def test_the_baseline_flags_need_decks(self):
        code, _, err = self.run_main("--baseline", "x.json")
        self.assertEqual(code, 2)
        self.assertIn("need --decks", err)


class TrackedDecksTests(unittest.TestCase):
    """The decks in examples/decks and their baseline.json agree: each deck has an entry, each entry has a deck."""

    def test_every_tracked_deck_has_a_baseline_entry_and_the_other_way_round(self):
        names = {p.stem for p in (ROOT / "examples" / "decks").glob("*.txt")}
        kept = json.loads((ROOT / "examples" / "decks" / "baseline.json").read_text(encoding="utf-8"))["decks"]
        self.assertEqual(names, set(kept))

    def test_each_baseline_entry_is_sorted_and_within_the_deck_size(self):
        kept = json.loads((ROOT / "examples" / "decks" / "baseline.json").read_text(encoding="utf-8"))["decks"]
        for name, entry in kept.items():
            self.assertEqual(entry["unplayable"], sorted(entry["unplayable"]), name)
            self.assertLessEqual(len(entry["unplayable"]), entry["cards"], name)


if __name__ == "__main__":
    unittest.main()
