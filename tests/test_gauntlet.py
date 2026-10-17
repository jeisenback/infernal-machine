"""The saved gauntlet: opponents by default, picked by Bracket (#395)."""

import contextlib
import io
import json
import os
import tempfile
import unittest

from unittest import mock

from infernal_machine import analyze, compare, gauntlet, impact, matchup
from infernal_machine.cards import BulkSource, Card, parse_decklist

BOSS = Card(name="Boss", type_line="Legendary Creature — Elf", color_identity=("G",))
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
CHANGER = Card(name="Changer", type_line="Creature — Elf", color_identity=("G",), game_changer=True)
TEXT = "Commander\n1 Boss\n\nDeck\n3 Forest\n"
STRONG = "Commander\n1 Boss\n\nDeck\n2 Forest\n1 Changer\n"


class Files:
    """A directory with a card file and a manifest of two decks."""

    def __init__(self, directory):
        self.dir = directory
        self.bulk = os.path.join(directory, "bulk.json")
        with open(self.bulk, "w", encoding="utf-8") as f:
            json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (BOSS, FOREST, CHANGER)}}, f)
        os.makedirs(os.path.join(directory, "decks"))
        for name, text in (("calm", TEXT), ("strong", STRONG)):
            with open(os.path.join(directory, "decks", f"{name}.txt"), "w", encoding="utf-8") as f:
                f.write(text)
        self.manifest = os.path.join(directory, "gauntlet.json")
        self.write([{"name": "calm", "file": "decks/calm.txt", "bracket": 1, "commander": "Boss"},
                    {"name": "strong", "file": "decks/strong.txt", "bracket": 3, "commander": "Boss"}])

    def write(self, decks):
        with open(self.manifest, "w", encoding="utf-8") as f:
            json.dump({"decks": decks}, f)


class SavedGauntletTests(unittest.TestCase):
    def test_the_saved_decks_exist_and_are_decklists(self):
        entries = gauntlet.load()
        commander = [e for e in entries if e.format == "commander"]
        self.assertGreaterEqual(len(commander), 5)
        self.assertEqual(len({e.name for e in entries}), len(entries), "names are unique")
        for entry in commander:  # (the Standard decks are read in test_standard_gauntlet.py)
            self.assertTrue(os.path.exists(entry.path), entry.path)
            with open(entry.path, encoding="utf-8") as f:
                decklist = parse_decklist(f.read())
            self.assertEqual(list(decklist.commanders), [entry.commander], entry.name)
            self.assertGreaterEqual(entry.bracket or 0, 1)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.files = Files(self._dir.name)

    def test_the_bracket_limit_picks_among_the_saved_decks(self):
        self.assertEqual([e.name for e in gauntlet.opponents(manifest=self.files.manifest)], ["calm", "strong"])
        self.assertEqual([e.name for e in gauntlet.opponents(2, self.files.manifest)], ["calm"])
        self.assertEqual([e.name for e in gauntlet.opponents(3, self.files.manifest)], ["calm", "strong"])

    def test_named_opponents_are_used_as_they_are(self):
        self.assertEqual(gauntlet.opponent_paths(["a.txt"], 1, self.files.manifest), ["a.txt"])

    def test_no_opponents_means_the_gauntlet_and_says_so(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            paths = gauntlet.opponent_paths([], 2, self.files.manifest)
        self.assertEqual([os.path.basename(p) for p in paths], ["calm.txt"])
        self.assertIn("using the saved commander gauntlet (1 deck at Bracket 2 or lower)", err.getvalue())

    def test_a_limit_nothing_meets_is_an_error(self):
        with self.assertRaises(SystemExit) as caught:
            gauntlet.opponent_paths([], 0, self.files.manifest)
        self.assertIn("Bracket 0", str(caught.exception))


class CheckAndAddTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.files = Files(self._dir.name)

    def test_a_manifest_that_matches_its_decks_has_no_problems(self):
        self.assertEqual(gauntlet.check(self.files.manifest, self.files.bulk), [])

    def test_a_wrong_bracket_a_wrong_commander_and_a_missing_file_are_found(self):
        self.files.write([{"name": "calm", "file": "decks/calm.txt", "bracket": 2, "commander": "Boss"},
                          {"name": "strong", "file": "decks/strong.txt", "bracket": 3, "commander": "Other"},
                          {"name": "gone", "file": "decks/gone.txt", "bracket": 1, "commander": "Boss"}])
        problems = gauntlet.check(self.files.manifest, self.files.bulk)
        self.assertEqual(len(problems), 3)
        self.assertIn("saved at Bracket 2, its cards say 1", problems[0])
        self.assertIn("saved commander 'Other'", problems[1])
        self.assertIn("does not exist", problems[2])

    def test_add_copies_the_deck_and_saves_its_floor(self):
        extra = os.path.join(self.files.dir, "tough.txt")
        with open(extra, "w", encoding="utf-8") as f:
            f.write(STRONG)
        entry = gauntlet.add(extra, self.files.manifest, self.files.bulk)
        self.assertEqual((entry.name, entry.bracket, entry.commander), ("tough", 3, "Boss"))
        self.assertTrue(os.path.exists(os.path.join(self.files.dir, "gauntlet", "tough.txt")))
        self.assertEqual([e.name for e in gauntlet.load(self.files.manifest)], ["calm", "strong", "tough"])
        self.assertEqual(gauntlet.check(self.files.manifest, self.files.bulk), [])

    def test_add_refuses_a_name_in_use_and_a_deck_with_no_commander(self):
        extra = os.path.join(self.files.dir, "calm.txt")
        with open(extra, "w", encoding="utf-8") as f:
            f.write(TEXT)
        with self.assertRaises(SystemExit):
            gauntlet.add(extra, self.files.manifest, self.files.bulk)
        plain = os.path.join(self.files.dir, "plain.txt")
        with open(plain, "w", encoding="utf-8") as f:
            f.write("Deck\n3 Forest\n")
        with self.assertRaises(SystemExit):
            gauntlet.add(plain, self.files.manifest, self.files.bulk)


class CommandLineTests(unittest.TestCase):
    """Each tool that takes opponents asks the gauntlet when it is given none (and not when it is)."""

    class Asked(Exception):
        pass

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.files = Files(self._dir.name)
        self.deck = os.path.join(self.files.dir, "decks", "calm.txt")

    def argv(self, module, *opponents):
        bulk = ["--bulk", self.files.bulk]
        if module is matchup or module is compare:
            return ["tool", self.deck, *([self.deck] if module is compare else []), *opponents, *bulk]
        return [self.deck, *opponents, *bulk]

    def test_no_opponents_asks_the_gauntlet(self):
        for module in (matchup, compare, impact, analyze):
            with self.subTest(module=module.__name__), mock.patch.object(module, "opponent_paths", side_effect=self.Asked) as asked:
                with self.assertRaises(self.Asked):
                    module.main(self.argv(module))
                asked.assert_called_once()
                self.assertEqual(asked.call_args.args[0], [])

    def test_named_opponents_are_passed_through(self):
        for module in (matchup, compare, impact):
            with self.subTest(module=module.__name__), mock.patch.object(module, "opponent_paths", side_effect=self.Asked) as asked:
                with self.assertRaises(self.Asked):
                    module.main(self.argv(module, "other.txt"))
                self.assertEqual(asked.call_args.args[0], ["other.txt"])

    def test_analyze_does_not_ask_when_it_is_given_opponents(self):
        with mock.patch.object(analyze, "opponent_paths", side_effect=self.Asked), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(analyze.main(self.argv(analyze, "other.txt")), 2)  # (it tries to read other.txt, which is not there)

    def test_the_bracket_limit_reaches_matchup_and_analyze(self):
        for module in (matchup, analyze):
            with self.subTest(module=module.__name__), mock.patch.object(module, "opponent_paths", side_effect=self.Asked) as asked:
                with self.assertRaises(self.Asked):
                    module.main(self.argv(module) + ["--max-bracket", "2"])
                self.assertEqual(asked.call_args.args[1], 2)

    def test_analyze_that_skips_the_matchups_needs_no_opponents(self):
        with mock.patch.object(analyze, "opponent_paths", side_effect=self.Asked), contextlib.redirect_stdout(io.StringIO()):
            code = analyze.main(self.argv(analyze) + ["--skip", "matchups,goldfish,tuning,manabase", "--sim-games", "5"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
