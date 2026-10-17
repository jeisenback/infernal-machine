"""The Standard half of the saved gauntlet, and the recipe that builds its baseline decks (#412)."""

import contextlib
import dataclasses
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from infernal_machine import analyze, compare, gauntlet, impact, matchup
from infernal_machine.cards import BulkSource, Card, Deck, parse_decklist
from tests.helpers import real

_spec = importlib.util.spec_from_file_location("build_standard_decks", Path(__file__).parent.parent / "tools" / "build_standard_decks.py")
assert _spec is not None and _spec.loader is not None
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))


def creature(name, cost, power, toughness, text="", **more):
    return dataclasses.replace(real(name, cost, "Creature — Bear", text, str(power), str(toughness)), **{"colors": ("G",), **more})


def bulk(directory, cards):
    path = os.path.join(directory, "bulk.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in cards}}, f)
    return path


class SavedStandardTests(unittest.TestCase):
    def test_the_saved_decks_of_both_formats_exist_and_read(self):
        entries = gauntlet.load()
        standard = [e for e in entries if e.format == "standard"]
        commander = [e for e in entries if e.format == "commander"]
        self.assertGreaterEqual(len(standard), 5)
        self.assertGreaterEqual(len(commander), 5)
        for entry in standard:
            self.assertIsNone(entry.bracket, entry.name)
            with open(entry.path, encoding="utf-8") as f:
                decklist = parse_decklist(f.read())
            self.assertEqual(decklist.commanders, {}, entry.name)
            self.assertGreaterEqual(sum(decklist.main.values()), 60, entry.name)
            self.assertLessEqual(sum(decklist.sideboard.values()), 15, entry.name)
            self.assertTrue(decklist.sideboard, f"{entry.name} has a sideboard to play best-of-three with")

    def test_an_entry_without_a_format_is_a_commander_deck(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "gauntlet.json")
            Path(path).write_text(json.dumps({"decks": [{"name": "old", "file": "old.txt", "bracket": 2, "commander": "Boss"}]}), encoding="utf-8")
            self.assertEqual(gauntlet.load(path)[0].format, "commander")


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.manifest = os.path.join(self._dir.name, "gauntlet.json")
        decks = [{"name": "calm", "file": "c.txt", "bracket": 1, "commander": "Boss"},
                 {"name": "strong", "file": "s.txt", "bracket": 3, "commander": "Boss", "format": "commander"},
                 {"name": "std_a", "file": "a.txt", "bracket": None, "commander": "", "format": "standard"},
                 {"name": "std_b", "file": "b.txt", "bracket": None, "commander": "", "format": "standard"}]
        Path(self.manifest).write_text(json.dumps({"decks": decks}), encoding="utf-8")

    def names(self, **more):
        return [e.name for e in gauntlet.opponents(manifest=self.manifest, **more)]

    def test_each_format_has_its_own_decks(self):
        self.assertEqual(self.names(), ["calm", "strong"], "Commander is the default")
        self.assertEqual(self.names(format="commander"), ["calm", "strong"])
        self.assertEqual(self.names(format="standard"), ["std_a", "std_b"])

    def test_a_bracket_limit_never_leaves_a_standard_deck_out(self):
        self.assertEqual(self.names(max_bracket=1, format="standard"), ["std_a", "std_b"])
        self.assertEqual(self.names(max_bracket=1), ["calm"])

    def test_the_default_for_a_standard_deck_says_so_and_names_no_bracket(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            paths = gauntlet.opponent_paths([], 2, self.manifest, format="standard")
        self.assertEqual([os.path.basename(p) for p in paths], ["a.txt", "b.txt"])
        self.assertIn("using the saved standard gauntlet (2 decks)", err.getvalue())
        self.assertNotIn("Bracket", err.getvalue())

    def test_no_saved_deck_of_the_format_is_an_error_naming_the_format(self):
        Path(self.manifest).write_text(json.dumps({"decks": [{"name": "calm", "file": "c.txt", "bracket": 1, "commander": "Boss"}]}), encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            gauntlet.opponent_paths([], None, self.manifest, format="standard")
        self.assertIn("No saved standard gauntlet deck", str(caught.exception))

    def test_deck_format_reads_the_commander(self):
        self.assertEqual(gauntlet.deck_format(Deck([BOSS], [], [])), "commander")
        self.assertEqual(gauntlet.deck_format(Deck([], [FOREST], [])), "standard")


class CheckAndAddTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.dir = self._dir.name
        self.good = creature("Good Bear", "{1}{G}", 2, 2)
        self.odd = creature("Odd Bear", "{G}", 1, 1, "Frobnicate the quuxes.")
        self.old = creature("Old Bear", "{G}", 1, 1, standard_legal=False)
        self.bulk = bulk(self.dir, [FOREST, BOSS, self.good, self.odd, self.old])
        self.manifest = os.path.join(self.dir, "gauntlet.json")
        os.makedirs(os.path.join(self.dir, "gauntlet"))

    def deck_file(self, name, text):
        path = os.path.join(self.dir, f"{name}.txt")
        Path(path).write_text(text, encoding="utf-8")
        return path

    def save(self, *entries):
        Path(self.manifest).write_text(json.dumps({"decks": [{"bracket": None, "commander": "", "format": "standard", **e} for e in entries]}), encoding="utf-8")

    def check(self, text, **entry):
        Path(os.path.join(self.dir, "gauntlet", "d.txt")).write_text(text, encoding="utf-8")
        self.save({"name": "d", "file": "gauntlet/d.txt", **entry})
        return gauntlet.check(self.manifest, self.bulk)

    LEGAL = "Deck\n24 Forest\n4 Good Bear\n"

    def test_a_legal_playable_standard_deck_has_no_problems(self):
        self.assertEqual(self.check("Deck\n56 Forest\n4 Good Bear\n\nSideboard\n3 Forest\n"), [])

    def test_a_deck_with_too_few_cards_too_many_copies_or_a_big_sideboard_is_found(self):
        self.assertTrue(any("needs at least 60" in p for p in self.check(self.LEGAL)))
        self.assertTrue(any("copies, limit is 4" in p for p in self.check("Deck\n55 Forest\n5 Good Bear\n")))
        self.assertTrue(any("Sideboard has 16" in p for p in self.check("Deck\n56 Forest\n4 Good Bear\n\nSideboard\n16 Forest\n")))

    def test_a_card_that_is_not_standard_legal_is_found(self):
        self.assertTrue(any("Old Bear is not legal" in p for p in self.check("Deck\n56 Forest\n4 Old Bear\n")))

    def test_a_card_the_engine_cannot_play_is_found_in_the_main_deck_and_the_sideboard(self):
        main = self.check("Deck\n56 Forest\n4 Odd Bear\n")
        self.assertTrue(any("can't fully play Odd Bear" in p for p in main), main)
        side = self.check("Deck\n60 Forest\n\nSideboard\n2 Odd Bear\n")
        self.assertTrue(any("can't fully play Odd Bear" in p for p in side), side)

    def test_a_standard_entry_with_a_commander_is_found(self):
        problems = self.check("Commander\n1 Boss\n\nDeck\n59 Forest\n")
        self.assertTrue(any("saved as a Standard deck but it has a commander" in p for p in problems), problems)

    def test_add_saves_a_deck_with_no_commander_as_standard(self):
        path = self.deck_file("mine", "Deck\n56 Forest\n4 Good Bear\n\nSideboard\n3 Forest\n")
        Path(self.manifest).write_text(json.dumps({"decks": []}), encoding="utf-8")
        entry = gauntlet.add(path, self.manifest, self.bulk)
        self.assertEqual((entry.format, entry.bracket, entry.commander), ("standard", None, ""))
        saved = json.loads(Path(self.manifest).read_text(encoding="utf-8"))["decks"][0]
        self.assertEqual((saved["format"], saved["bracket"]), ("standard", None))
        self.assertTrue(os.path.exists(os.path.join(self.dir, "gauntlet", "mine.txt")))
        self.assertEqual(gauntlet.check(self.manifest, self.bulk), [])

    def test_add_refuses_a_deck_that_breaks_the_standard_rules(self):
        path = self.deck_file("short", self.LEGAL)
        Path(self.manifest).write_text(json.dumps({"decks": []}), encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            gauntlet.add(path, self.manifest, self.bulk)
        self.assertIn("Not a Standard deck", str(caught.exception))
        self.assertIn("needs at least 60", str(caught.exception))

    def test_add_does_not_copy_a_file_onto_itself(self):
        Path(self.manifest).write_text(json.dumps({"decks": []}), encoding="utf-8")
        path = os.path.join(self.dir, "gauntlet", "inplace.txt")
        Path(path).write_text("Deck\n56 Forest\n4 Good Bear\n", encoding="utf-8")
        entry = gauntlet.add(path, self.manifest, self.bulk)
        self.assertEqual(entry.name, "inplace")
        self.assertEqual(Path(path).read_text(encoding="utf-8"), "Deck\n56 Forest\n4 Good Bear\n")

    def test_a_commander_deck_is_still_saved_as_one(self):
        path = self.deck_file("cmd", "Commander\n1 Boss\n\nDeck\n99 Forest\n")
        Path(self.manifest).write_text(json.dumps({"decks": []}), encoding="utf-8")
        entry = gauntlet.add(path, self.manifest, self.bulk)
        self.assertEqual((entry.format, entry.bracket, entry.commander), ("commander", 1, "Boss"))


class RecipeTests(unittest.TestCase):
    def pool(self):
        cards = []
        # nine good creatures, best first by (power + toughness) / (mana value + 1)
        for i, (power, toughness, cost) in enumerate([(5, 5, "{G}{G}{G}{G}{G}"), (4, 4, "{2}{G}{G}"), (3, 3, "{1}{G}"), (3, 2, "{1}{G}"), (2, 2, "{1}{G}"),
                                                       (2, 1, "{G}"), (3, 3, "{3}{G}"), (2, 3, "{2}{G}"), (1, 1, "{1}{G}")]):
            cards.append(creature(f"Bear {i}", cost, power, toughness))
        cards.append(creature("Flier", "{1}{G}", 2, 2, "Flying"))
        cards.append(dataclasses.replace(real("Removal A", "{1}{G}", "Instant", "Destroy target creature."), colors=("G",)))
        cards.append(dataclasses.replace(real("Removal B", "{G}", "Sorcery", "Removal B deals 3 damage to target creature."), colors=("G",)))
        cards.append(dataclasses.replace(real("Removal C", "{2}{G}", "Instant", "Destroy target creature."), colors=("G",)))
        return cards

    def test_the_candidates_are_scored_and_ordered(self):
        creatures, removal = builder.candidates(self.pool(), "G")
        names = [c.name for c in creatures]
        self.assertEqual(names[0], "Bear 2", "a 3/3 for two scores 6/3")
        self.assertLess(names.index("Flier"), names.index("Bear 3"), "2/2 flying for two scores 4/3 + 0.5, above a plain 3/2 (5/3)")
        self.assertLess(names.index("Bear 3"), names.index("Bear 4"))
        self.assertEqual([c.name for c in removal], ["Removal B", "Removal A", "Removal C"], "cheapest first")
        self.assertGreater(builder.creature_score(creatures[0]), builder.creature_score(creatures[-1]))

    def test_cards_that_do_not_fit_are_left_out(self):
        odd = [creature("Legend", "{1}{G}", 3, 3, type_line="Legendary Creature — Elf"),
               creature("Unreadable", "{G}", 1, 1, "Frobnicate the quuxes."),
               creature("Old", "{G}", 1, 1, standard_legal=False),
               creature("Pair // Twin", "{G}", 1, 1),
               creature("Wall", "{1}{G}", 0, 4),
               creature("Huge", "{6}{G}", 8, 8),
               creature("Wrong Colour", "{R}", 2, 2, colors=("R",)),
               creature("Two Colours", "{G}{R}", 2, 2, colors=("G", "R"))]
        creatures, _ = builder.candidates(odd, "G")
        self.assertEqual([c.name for c in creatures], [], [c.name for c in creatures])

    def test_the_main_deck_is_four_copies_of_seven_creatures_and_two_removal_spells(self):
        main, side = builder.build(self.pool(), "G")
        names = [c.name for c in main]
        self.assertEqual(len(main), 36)
        self.assertEqual(len(set(names)), 9)
        self.assertTrue(all(names.count(n) == 4 for n in set(names)))
        self.assertIn("Removal B", names)
        self.assertIn("Removal A", names)
        self.assertNotIn("Removal C", names)

    def test_the_sideboard_is_the_next_best_cards_at_most_four_of_each(self):
        main, side = builder.build(self.pool(), "G")
        names = [c.name for c in side]
        self.assertLessEqual(len(side), 15)
        self.assertFalse(set(names) & {c.name for c in main}, "no card is in both")
        self.assertTrue(all(names.count(n) <= 4 for n in set(names)))
        self.assertIn("Removal C", names)

    def test_fewer_than_two_removal_spells_are_made_up_with_creatures(self):
        pool = [c for c in self.pool() if not c.name.startswith("Removal")] + [self.pool()[-3]]
        main, _ = builder.build(pool, "G")
        self.assertEqual(len(main), 36)
        self.assertEqual(len({c.name for c in main}), 9)

    def test_the_same_cards_make_the_same_deck(self):
        a, b = builder.build(self.pool(), "G"), builder.build(list(reversed(self.pool())), "G")
        self.assertEqual([c.name for c in a[0]], [c.name for c in b[0]])
        self.assertEqual([c.name for c in a[1]], [c.name for c in b[1]])

    def test_the_file_reads_back_as_24_lands_36_spells_and_a_sideboard(self):
        main, side = builder.build(self.pool(), "G")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "standard_green.txt")
            builder.write(path, "G", main, side)
            text = Path(path).read_text(encoding="utf-8")
            decklist = parse_decklist(text)
        self.assertTrue(text.startswith("// Standard baseline: mono-green."))
        self.assertEqual(decklist.main["Forest"], 24)
        self.assertEqual(sum(decklist.main.values()), 60)
        self.assertEqual(sum(decklist.sideboard.values()), len(side))
        self.assertEqual(decklist.commanders, {})


class CommandLineTests(unittest.TestCase):
    """The tools ask the gauntlet of the focus deck's own format."""

    class Asked(Exception):
        pass

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        d = self._dir.name
        self.bulk = bulk(d, [FOREST, BOSS, creature("Good Bear", "{1}{G}", 2, 2)])
        self.standard = os.path.join(d, "std.txt")
        Path(self.standard).write_text("Deck\n56 Forest\n4 Good Bear\n", encoding="utf-8")
        self.commander = os.path.join(d, "cmd.txt")
        Path(self.commander).write_text("Commander\n1 Boss\n\nDeck\n99 Forest\n", encoding="utf-8")

    def argv(self, module, deck):
        bulk_args = ["--bulk", self.bulk]
        if module is matchup:
            return ["tool", deck, *bulk_args]
        if module is compare:
            return ["tool", deck, deck, *bulk_args]
        return [deck, *bulk_args]

    def test_each_tool_asks_for_its_decks_format(self):
        for module in (matchup, compare, impact, analyze):
            for deck, expected in ((self.standard, "standard"), (self.commander, "commander")):
                with self.subTest(module=module.__name__, format=expected), mock.patch.object(module, "opponent_paths", side_effect=self.Asked) as asked:
                    with self.assertRaises(self.Asked):
                        module.main(self.argv(module, deck))
                    self.assertEqual(asked.call_args.kwargs["format"], expected)


if __name__ == "__main__":
    unittest.main()
