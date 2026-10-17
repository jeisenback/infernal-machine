"""Keeping an analysis's numbers, and saying what changed after an edit (#411)."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from infernal_machine import analyze, history
from infernal_machine.cards import BulkSource, Card, Deck
from tests.helpers import real

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = real("Cub", "{1}{G}", "Creature — Bear", "", "2", "2")
OGRE = real("Ogre", "{2}{G}", "Creature — Ogre", "", "3", "3")
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))


def deck(*cards, commanders=()):
    return Deck(list(commanders), [c for card, n in cards for c in [card] * n], [])


SETTINGS = {"games": 12, "sim_games": 100, "turns": 6, "seed": 0, "pod": 2, "candidates": []}


def goldfish_data(**more):
    data = {"games": 100, "turns": 8, "mulligan_rate": 0.15, "opening_lands": 2.9, "mana_efficiency": 0.79, "on_curve": 0.42,
            "land_drops": {"4": 0.75, "8": 0.15}, "damage": {"8": 25.0}}
    data.update(more)
    return data


def run(cards, bracket=1, changers=(), colors=None, gold=None, opponents=None, settings=SETTINGS):
    parts = {"bracket": {"data": {"floor": bracket, "game_changers": sorted(changers)}, "settings": {}},
             "manabase": {"data": {"lands": 37, "colors": colors or {"G": {"have": 24, "needed": 20, "short": 0}}}, "settings": {}},
             "goldfish": {"data": gold or goldfish_data(), "settings": {}}}
    if opponents:
        parts["matchups"] = {"data": {"pod": 2, "opponents": opponents}, "settings": {}}
    return {"version": history.VERSION, "name": "mine", "deck": cards, "settings": settings, "parts": parts}


class FingerprintTests(unittest.TestCase):
    def test_copies_of_each_card_and_the_commander_marked(self):
        self.assertEqual(history.fingerprint(deck((FOREST, 3), (BEAR, 1), commanders=[BOSS])),
                         {"Cub": 1, "Forest": 3, "commander: Boss": 1})

    def test_the_order_of_the_cards_does_not_matter(self):
        a = deck((FOREST, 2), (BEAR, 1), (OGRE, 1))
        b = Deck([], [OGRE, FOREST, BEAR, FOREST], [])
        self.assertEqual(history.fingerprint(a), history.fingerprint(b))


class PartSettingsTests(unittest.TestCase):
    def test_what_each_part_depends_on(self):
        opponents = {"them": deck((FOREST, 2))}
        self.assertEqual(history.part_settings("bracket", SETTINGS), {})
        self.assertEqual(history.part_settings("manabase", SETTINGS), {})
        self.assertEqual(history.part_settings("goldfish", SETTINGS), {"sim_games": 100, "turns": 6, "seed": 0})
        self.assertEqual(history.part_settings("tuning", {**SETTINGS, "candidates": ["Zed", "Abe"]}),
                         {"sim_games": 100, "turns": 6, "seed": 0, "candidates": ["Abe", "Zed"]})
        self.assertEqual(history.part_settings("matchups", SETTINGS, opponents),
                         {"games": 12, "pod": 2, "seed": 0, "opponents": {"them": {"Forest": 2}}})


class FileTests(unittest.TestCase):
    def test_a_run_is_saved_and_loaded_unchanged(self):
        record = history.snapshot("mine", deck((FOREST, 2)), SETTINGS, {"goldfish": {"title": "Goldfish", "body": "x", "code": True, "data": {"a": 1}}})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "run.json")
            history.save(path, record)
            self.assertEqual(history.load(path), record)

    def test_a_run_of_another_version_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "run.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": 0}, f)
            with self.assertRaises(ValueError) as caught:
                history.load(path)
            self.assertIn("another version", str(caught.exception))

    def test_jsonable_gives_a_fresh_run_the_keys_a_loaded_one_has(self):
        self.assertEqual(history.jsonable({1: {2: 0.5}}), {"1": {"2": 0.5}})


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.deck = deck((FOREST, 10), (BEAR, 4))
        self.opponents = {"them": deck((FOREST, 5))}
        sections = {part: {"title": part, "body": part, "code": True, "data": {}} for part in ("bracket", "manabase", "goldfish", "tuning", "matchups")}
        self.old = history.snapshot("mine", self.deck, SETTINGS, sections, self.opponents)

    def test_the_same_deck_and_settings_are_reused(self):
        for part in ("bracket", "manabase", "goldfish", "tuning", "matchups"):
            self.assertIsNotNone(history.reusable(self.old, part, self.deck, SETTINGS, self.opponents), part)

    def test_a_changed_card_reuses_nothing(self):
        edited = deck((FOREST, 10), (OGRE, 4))
        for part in ("bracket", "goldfish", "matchups"):
            self.assertIsNone(history.reusable(self.old, part, edited, SETTINGS, self.opponents), part)

    def test_changed_settings_reuse_only_the_parts_they_do_not_touch(self):
        more_games = {**SETTINGS, "games": 40}
        self.assertIsNone(history.reusable(self.old, "matchups", self.deck, more_games, self.opponents))
        self.assertIsNotNone(history.reusable(self.old, "goldfish", self.deck, more_games, self.opponents))
        other_seed = {**SETTINGS, "seed": 1}
        self.assertIsNone(history.reusable(self.old, "goldfish", self.deck, other_seed, self.opponents))
        self.assertIsNotNone(history.reusable(self.old, "bracket", self.deck, other_seed, self.opponents))

    def test_other_opponents_replay_the_matchups_only(self):
        other = {"them": deck((FOREST, 4), (BEAR, 1))}
        self.assertIsNone(history.reusable(self.old, "matchups", self.deck, SETTINGS, other))
        self.assertIsNotNone(history.reusable(self.old, "goldfish", self.deck, SETTINGS, other))

    def test_other_candidates_replay_the_tuning_only(self):
        tried = {**SETTINGS, "candidates": ["Ogre"]}
        self.assertIsNone(history.reusable(self.old, "tuning", self.deck, tried, self.opponents))
        self.assertIsNotNone(history.reusable(self.old, "goldfish", self.deck, tried, self.opponents))

    def test_nothing_saved_reuses_nothing(self):
        self.assertIsNone(history.reusable(None, "goldfish", self.deck, SETTINGS))
        self.assertIsNone(history.reusable({"deck": history.fingerprint(self.deck), "parts": {}}, "goldfish", self.deck, SETTINGS))


class NoiseTests(unittest.TestCase):
    def test_a_big_change_over_many_games_is_outside_noise(self):
        change, outside = history.proportion_change(0.30, 400, 0.45, 400)
        self.assertAlmostEqual(change, 0.15)
        self.assertTrue(outside)

    def test_the_same_change_over_a_few_games_is_not(self):
        self.assertFalse(history.proportion_change(0.30, 12, 0.45, 12)[1])

    def test_no_games_say_nothing(self):
        self.assertFalse(history.proportion_change(0.5, 0, 0.9, 40)[1])

    def test_rates_of_zero_or_one_that_differ_are_a_change(self):
        self.assertTrue(history.proportion_change(0.0, 40, 1.0, 40)[1])
        self.assertFalse(history.proportion_change(1.0, 40, 1.0, 40)[1])


class CompareTests(unittest.TestCase):
    def test_the_cards_that_changed(self):
        text = history.compare(run({"Forest": 20, "Cub": 1, "commander: Boss": 1}), run({"Forest": 20, "Ogre": 1, "commander: Boss": 1}), "run1.json")
        self.assertIn("Compared with run1.json: -1 Cub, +1 Ogre.", text)
        self.assertIn("no card changed", history.compare(run({"Forest": 1}), run({"Forest": 1})))
        self.assertIn("(commander)", history.compare(run({"commander: Boss": 1}), run({"commander: Ogre": 1})))

    def test_differing_settings_are_said(self):
        text = history.compare(run({}), run({}, settings={**SETTINGS, "sim_games": 500}))
        self.assertIn("sim_games 100 -> 500", text)
        self.assertIn("not directly comparable", text)

    def test_the_bracket(self):
        text = history.compare(run({}, 1), run({}, 3, changers=["Sol Ring"]))
        self.assertIn("Bracket: 1 -> 3 (new Game Changers: Sol Ring).", text)
        self.assertIn("Bracket: still 2 or higher", history.compare(run({}, 2), run({}, 2)))

    def test_the_mana_base(self):
        old = run({}, colors={"G": {"have": 24, "needed": 20, "short": 0}})
        new = run({}, colors={"G": {"have": 18, "needed": 20, "short": 2}})
        self.assertIn("G: sources 24 -> 18, short by 0 -> 2", history.compare(old, new))
        self.assertIn("no color's sources or shortfall changed", history.compare(old, old))

    def test_the_goldfish_rows_and_their_noise(self):
        old = run({}, gold=goldfish_data(mulligan_rate=0.10, games=2000, damage={"8": 25.0}, land_drops={"4": 0.75, "8": 0.15}))
        new = run({}, gold=goldfish_data(mulligan_rate=0.16, games=2000, damage={"8": 22.0}, land_drops={"4": 0.76, "8": 0.15}))
        text = history.compare(old, new)
        mulligan = next(line for line in text.splitlines() if line.startswith("mulligan rate"))
        self.assertIn("+6.0", mulligan)
        self.assertTrue(mulligan.rstrip().endswith("outside noise"))
        drops = next(line for line in text.splitlines() if line.startswith("land drops through turn 4"))
        self.assertTrue(drops.rstrip().endswith("within noise"))
        damage = next(line for line in text.splitlines() if line.startswith("damage by turn 8"))
        self.assertIn("-3.0", damage)
        self.assertNotIn("noise", damage, "an average has no error bar here: no verdict")

    def test_the_matchups_present_in_both_runs(self):
        old = run({}, opponents={"easy": {"wins": 30, "games": 100, "draws": 0}, "gone": {"wins": 5, "games": 10, "draws": 0}})
        new = run({}, opponents={"easy": {"wins": 60, "games": 100, "draws": 0}, "fresh": {"wins": 5, "games": 10, "draws": 0}})
        text = history.compare(old, new)
        easy = next(line for line in text.splitlines() if line.startswith("easy"))
        self.assertIn("30.0%", easy)
        self.assertIn("60.0%", easy)
        self.assertTrue(easy.rstrip().endswith("outside noise"))
        self.assertIn("1 of 1 win rates moved outside noise.", text)
        self.assertIn("Not in the earlier run: fresh.", text)
        self.assertNotIn("gone", text)

    def test_an_opponent_with_no_finished_games_in_either_run_is_left_out(self):
        old = run({}, opponents={"easy": {"wins": 30, "games": 100, "draws": 0}, "broken": {"wins": 0, "games": 0, "draws": 0}})
        new = run({}, opponents={"easy": {"wins": 60, "games": 100, "draws": 0}, "broken": {"wins": 3, "games": 10, "draws": 0}})
        text = history.compare(old, new)
        self.assertIn("easy", text)
        self.assertNotIn("broken", text)
        self.assertIn("1 of 1 win rates", text)

    def test_a_part_taken_from_the_earlier_run_is_not_compared(self):
        old = run({}, gold=goldfish_data(mulligan_rate=0.10))
        new = {**run({}, gold=goldfish_data(mulligan_rate=0.10)), "reused": ["goldfish", "bracket"]}
        text = history.compare(old, new)
        self.assertNotIn("mulligan rate", text)
        self.assertNotIn("Bracket:", text)
        self.assertIn("Not compared (taken from the earlier run, so the same): Commander Bracket, goldfish.", text)

    def test_the_tuning_baseline(self):
        old, new = run({}), run({})
        old["parts"]["tuning"] = {"data": {"games": 100, "baseline": 12.0}}
        new["parts"]["tuning"] = {"data": {"games": 100, "baseline": 13.5}}
        self.assertIn("average game value 12.0 -> 13.5", history.compare(old, new))


class AnalyzeTests(unittest.TestCase):
    DECK = deck((FOREST, 24), (BEAR, 18), (OGRE, 6), commanders=[BOSS])
    OPPONENTS = {"them": deck((FOREST, 24), (BEAR, 18), commanders=[BOSS])}

    def analyze(self, d=None, **more):
        return analyze.analyze_deck(d or self.DECK, self.OPPONENTS, name="mine", games=4, sim_games=40, turns=4, workers=1, **more)

    def test_a_run_records_its_parts_and_their_numbers(self):
        first = self.analyze()
        self.assertEqual(sorted(first.record["parts"]), ["bracket", "goldfish", "manabase", "matchups", "tuning"])
        self.assertEqual(first.record["parts"]["bracket"]["data"]["floor"], 1)
        self.assertEqual(first.record["parts"]["goldfish"]["data"]["games"], 40)
        self.assertEqual(first.record["parts"]["matchups"]["data"]["opponents"]["them"]["games"], 4)
        self.assertEqual(first.record["deck"], history.fingerprint(self.DECK))
        json.dumps(first.record)

    def test_the_same_run_again_reuses_every_part_and_plays_nothing(self):
        first = self.analyze()
        with mock.patch.object(analyze, "simulate", side_effect=AssertionError), mock.patch.object(analyze, "matchups", side_effect=AssertionError), \
                mock.patch.object(analyze, "tune", side_effect=AssertionError):
            again = self.analyze(since=first.record)
        self.assertEqual(again.reused, ["commander bracket", "mana base", "goldfish", "tuning", "matchups"])
        self.assertEqual([s.body for s in again.sections], [s.body for s in first.sections])
        self.assertEqual(again.seconds, 0.0)
        self.assertIn("Reused from the earlier run", analyze.format_analysis(again))
        self.assertIn("Not compared (taken from the earlier run, so the same)", again.changes)
        self.assertNotIn("mulligan rate", again.changes, "a part taken from the earlier run is not set against itself")
        self.assertEqual(again.record["reused"], ["bracket", "manabase", "goldfish", "tuning", "matchups"])

    def test_an_edited_deck_replays_everything_and_says_what_moved(self):
        first = self.analyze()
        edited = deck((FOREST, 24), (BEAR, 24), commanders=[BOSS])
        again = self.analyze(edited, since=first.record, since_name="run1.json")
        self.assertEqual(again.reused, [])
        self.assertIn("-6 Ogre, +6 Cub", again.changes.replace("+6 Cub", "+6 Cub"))
        text = analyze.format_analysis(again)
        self.assertIn("## What changed", text)
        self.assertLess(text.index("## What changed"), text.index("## Commander Bracket"))

    def test_other_opponents_replay_only_the_matchups(self):
        first = self.analyze()
        with mock.patch.object(analyze, "simulate", side_effect=AssertionError):
            again = analyze.analyze_deck(self.DECK, {"other": deck((FOREST, 24), (OGRE, 18), commanders=[BOSS])}, name="mine", games=4, sim_games=40, turns=4,
                                         since=first.record)
        self.assertNotIn("matchups", again.reused)
        self.assertIn("goldfish", again.reused)
        self.assertIn("Not in the earlier run: other.", again.changes)

    def test_no_reuse_plays_everything_but_still_compares(self):
        first = self.analyze()
        again = self.analyze(since=first.record, reuse=False)
        self.assertEqual(again.reused, [])
        self.assertIn("no card changed", again.changes)
        self.assertGreater(again.seconds, 0.0)

    def test_without_an_earlier_run_there_is_nothing_to_compare(self):
        analysis = self.analyze()
        self.assertEqual((analysis.changes, analysis.reused), ("", []))
        self.assertNotIn("What changed", analyze.format_analysis(analysis))


class CommandLineTests(unittest.TestCase):
    def test_save_then_since(self):
        cards = [FOREST, BEAR, OGRE, BOSS]
        with tempfile.TemporaryDirectory() as d:
            bulk = os.path.join(d, "bulk.json")
            with open(bulk, "w", encoding="utf-8") as f:
                json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in cards}}, f)
            mine, edited, theirs = (os.path.join(d, name) for name in ("mine.txt", "edited.txt", "theirs.txt"))
            with open(mine, "w", encoding="utf-8") as f:
                f.write("Commander\n1 Boss\n\nDeck\n24 Forest\n18 Cub\n6 Ogre\n")
            with open(edited, "w", encoding="utf-8") as f:
                f.write("Commander\n1 Boss\n\nDeck\n24 Forest\n24 Cub\n")
            with open(theirs, "w", encoding="utf-8") as f:
                f.write("Commander\n1 Boss\n\nDeck\n24 Forest\n18 Cub\n")
            saved = os.path.join(d, "run.json")
            common = ["--games", "4", "--sim-games", "40", "--turns", "4", "--workers", "1", "--skip", "tuning", "--bulk", bulk]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(analyze.main([mine, theirs, *common, "--save", saved]), 0)
            self.assertTrue(os.path.exists(saved))
            self.assertIn("Saved this run's numbers", err.getvalue())
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(analyze.main([edited, theirs, *common, "--since", saved]), 0)
            self.assertIn("## What changed", out.getvalue())
            self.assertIn("-6 Ogre", out.getvalue())

    def test_a_missing_or_foreign_run_is_an_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()) as err:
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as f:
                json.dump({"version": 0}, f)
            deck_file = os.path.join(d, "deck.txt")
            with open(deck_file, "w", encoding="utf-8") as f:
                f.write("24 Forest\n36 Cub\n")
            bulk = os.path.join(d, "bulk.json")
            with open(bulk, "w", encoding="utf-8") as f:
                json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (FOREST, BEAR)}}, f)
            self.assertEqual(analyze.main([deck_file, "--skip", "matchups", "--since", bad, "--bulk", bulk]), 2)
            self.assertIn("another version", err.getvalue())
            self.assertEqual(analyze.main([deck_file, "--skip", "matchups", "--since", os.path.join(d, "nope.json"), "--bulk", bulk]), 2)


if __name__ == "__main__":
    unittest.main()
