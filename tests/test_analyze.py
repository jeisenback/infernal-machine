"""The combined report for a deck: which parts it runs, in what order, and that nothing is said twice (#387). The numbers in each
part are tested where the part is; these check the assembly."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from infernal_machine.analyze import PARTS, analyze_deck, format_analysis, main
from infernal_machine.cards import Card, CardNotFound, Deck

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))
ODD = Card(name="Odd Spell", mana_cost="{1}{G}", cmc=2, type_line="Sorcery", oracle_text="Exchange the frobnicator of each player with the quuxes.",
           color_identity=("G",))
FAST = dict(games=2, sim_games=30, turns=4, seed=1)  # small, so the whole run is quick


def commander_deck(*extras):
    return Deck([BOSS], [*extras, *[FOREST] * 38, *[BEAR] * (61 - len(extras))], [])


def standard_deck(*extras):
    return Deck([], [*extras, *[FOREST] * 24, *[BEAR] * (36 - len(extras))], [])


def titles(analysis):
    return [s.title for s in analysis.sections]


class SectionTests(unittest.TestCase):
    def test_a_commander_deck_with_opponents_gets_every_part_in_order(self):
        analysis = analyze_deck(commander_deck(), {"mirror": commander_deck()}, name="mine", **FAST)
        self.assertEqual(titles(analysis), ["Commander Bracket", "Mana base", "Goldfish", "Tuning", "Matchups"])
        self.assertEqual(analysis.kind, "Commander")
        self.assertEqual(analysis.skipped, [])

    def test_a_standard_deck_has_no_bracket(self):
        analysis = analyze_deck(standard_deck(), {"mirror": standard_deck()}, **FAST)
        self.assertEqual(titles(analysis), ["Mana base", "Goldfish", "Tuning", "Matchups"])
        self.assertEqual(analysis.kind, "Standard")
        self.assertIn("Commander Bracket (a deck with no commander has none)", analysis.skipped)

    def test_without_opponents_there_are_no_matchups(self):
        analysis = analyze_deck(commander_deck(), **FAST)
        self.assertNotIn("Matchups", titles(analysis))
        self.assertIn("Matchups (no opponents given)", analysis.skipped)

    def test_a_part_can_be_skipped(self):
        analysis = analyze_deck(commander_deck(), {"mirror": commander_deck()}, skip=["tuning", "matchups"], **FAST)
        self.assertEqual(titles(analysis), ["Commander Bracket", "Mana base", "Goldfish"])
        self.assertEqual(analysis.skipped, ["Tuning (skipped on request)", "Matchups (skipped on request)"])

    def test_an_unknown_part_is_an_error(self):
        with self.assertRaises(ValueError) as error:
            analyze_deck(commander_deck(), skip=["tunning"], **FAST)
        for part in PARTS:
            self.assertIn(part, str(error.exception))

    def test_decks_with_and_without_a_commander_cannot_be_mixed(self):
        with self.assertRaises(ValueError):
            analyze_deck(commander_deck(), {"standard": standard_deck()}, **FAST)

    def test_every_part_is_timed(self):
        analysis = analyze_deck(commander_deck(), {"mirror": commander_deck()}, **FAST)
        self.assertTrue(all(s.seconds >= 0 for s in analysis.sections))
        self.assertGreater(analysis.seconds, 0)

    def test_progress_is_reported_once_for_each_part_that_runs(self):
        messages = []
        analyze_deck(commander_deck(), {"mirror": commander_deck()}, skip=["goldfish"], progress=messages.append, **FAST)
        self.assertEqual(messages, ["Commander Bracket...", "Mana base...", "Tuning...", "Matchups..."])


class WarningTests(unittest.TestCase):
    def test_cards_the_engine_cannot_play_come_first(self):
        analysis = analyze_deck(commander_deck(ODD), **FAST)
        self.assertEqual(titles(analysis)[0], "Cards the engine can't play")
        self.assertIn("Odd Spell", analysis.sections[0].body)
        self.assertFalse(analysis.sections[0].code)

    def test_a_clean_deck_has_no_warning(self):
        self.assertNotIn("Cards the engine can't play", titles(analyze_deck(commander_deck(), **FAST)))

    def test_nothing_is_said_twice(self):
        report = format_analysis(analyze_deck(commander_deck(ODD), {"mirror": commander_deck()}, **FAST))
        self.assertEqual(report.count("Mana base: sources of each color"), 1)  # (the tuning report has its own copy, left out)
        self.assertEqual(report.count("Bracket: no hard limit"), 0)  # (the tuning report's own Bracket line, left out; the matchups' line compares brackets)
        self.assertEqual(report.count("can't fully play: Odd Spell"), 1)  # (the matchup report's own sentence about the focus deck is left out)
        self.assertIn("The matchup win rates below are unreliable for the same reason.", report)
        tuning = next(s for s in analyze_deck(commander_deck(ODD), **FAST).sections if s.title == "Tuning")
        self.assertNotIn("Mana base:", tuning.body)
        self.assertNotIn("Bracket:", tuning.body)
        self.assertNotIn("can't fully play", tuning.body)

    def test_candidates_reach_the_tuning_part(self):
        dud = Card(name="Aaa Dud", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1", color_identity=("G",))
        fresh = Card(name="Fresh Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))
        analysis = analyze_deck(commander_deck(*[dud] * 8), candidates=[fresh], skip=["goldfish"], **FAST)
        tuning = next(s for s in analysis.sections if s.title == "Tuning")
        self.assertIn("Fresh Bear for", tuning.body)


class FormatTests(unittest.TestCase):
    def test_markdown_structure(self):
        analysis = analyze_deck(commander_deck(ODD), {"mirror": commander_deck()}, name="mine", **FAST)
        report = format_analysis(analysis, "A settings line.")
        lines = report.splitlines()
        self.assertEqual(lines[0], "# Analysis of mine")
        self.assertIn("Commander deck. A settings line.", report)
        for section in analysis.sections:
            self.assertIn(f"## {section.title}", report)
        self.assertEqual(report.count("```"), 2 * sum(s.code for s in analysis.sections))  # tables are fenced, prose is not
        self.assertRegex(report, r"Took \d+ seconds \(")

    def test_what_was_left_out_is_said(self):
        report = format_analysis(analyze_deck(standard_deck(), skip=["goldfish"], **FAST))
        self.assertIn("Left out: Commander Bracket (a deck with no commander has none); Goldfish (skipped on request); Matchups (no opponents given).", report)


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
    def run_main(self, files, *options):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name, text in files.items():
                path = os.path.join(directory, name)
                Path(path).write_text(text, encoding="utf-8")
                paths.append(path)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main([*paths, "--sim-games", "20", "--turns", "3", "--games", "2", "--workers", "1", *options], source=FakeSource(FOREST, BEAR, BOSS))
            return code, out.getvalue(), err.getvalue(), directory

    DECK = "24 Forest\n36 Grizzly Bears\n"

    def test_a_deck_and_an_opponent(self):
        code, out, err, _ = self.run_main({"mine.txt": self.DECK, "theirs.txt": self.DECK})
        self.assertEqual(code, 0)
        self.assertIn("# Analysis of mine", out)
        self.assertIn("## Matchups", out)
        self.assertIn("theirs", out)  # the opponent is named by its file
        self.assertIn("Matchups...", err)  # progress goes to stderr

    def test_a_deck_alone_and_the_output_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "report.md")
            code, out, _, _ = self.run_main({"mine.txt": self.DECK}, "--skip", "tuning", "--output", target)
            self.assertEqual(code, 0)
            self.assertNotIn("## Tuning", out)
            self.assertEqual(Path(target).read_text(encoding="utf-8"), out)  # the same report, plus the newline print adds

    def test_an_unknown_card_is_an_error_not_a_traceback(self):
        code, out, err, _ = self.run_main({"mine.txt": "24 Forest\n36 Nonexistent Card\n"})
        self.assertEqual((code, out), (2, ""))
        self.assertIn("Error: Nonexistent Card", err)

    def test_an_unknown_part_is_an_error(self):
        code, _, err, _ = self.run_main({"mine.txt": self.DECK}, "--skip", "tunning")
        self.assertEqual(code, 2)
        self.assertIn("unknown part", err)


if __name__ == "__main__":
    unittest.main()
