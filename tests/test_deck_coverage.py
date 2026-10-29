"""The coverage audit asked of real decklists: what blocks them, and what to build (#409)."""

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from infernal_machine import coverage
from infernal_machine.cards import BulkSource, Card, Deck
from tests.helpers import real

_spec = importlib.util.spec_from_file_location("coverage_audit", Path(__file__).parent.parent / "tools" / "coverage_audit.py")
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = real("Cub", "{1}{G}", "Creature — Bear", "", "2", "2")
MOON = "Whenever the moon is full, frobnicate the widget."
MOON_A = real("Moon Cat", "{1}{G}", "Creature — Cat", MOON, "1", "1")
MOON_B = real("Moon Elk", "{1}{G}", "Creature — Elk", MOON, "1", "1")
SHROUD_MOON = real("Moon Owl", "{1}{G}", "Creature — Bird", MOON + "\nShroud", "1", "1")
ODD = real("Odd Toad", "{G}", "Creature — Frog", "Gather the quuxes from the nearest bog.", "1", "1")
TWO_GAPS = real("Odd Moon Newt", "{G}", "Creature — Salamander", MOON + "\nGather the quuxes from the nearest bog.", "1", "1")
COPY = real("Copy Cat", "{1}{G}", "Creature — Cat", "Create a token that's a copy of target creature.", "1", "1")


def deck(*cards, commanders=()):
    return Deck(list(commanders), [c for card, n in cards for c in [card] * n], [])


class AnalyzeDecksTests(unittest.TestCase):
    def test_a_deck_with_every_card_playable_has_nothing_to_build(self):
        result = coverage.analyze_decks({"mine": deck((FOREST, 30), (BEAR, 10))})
        self.assertEqual((result["total"], result["playable"]), (40, 40))
        self.assertEqual(result["next"], [])
        self.assertIn("40 of 40 cards fully playable (100%); 1 of 1 play in full", audit.render_decks(result))

    def test_every_copy_counts(self):
        result = coverage.analyze_decks({"mine": deck((FOREST, 20), (MOON_A, 3), (BEAR, 1))})
        self.assertEqual((result["total"], result["playable"]), (24, 21))
        self.assertEqual(result["decks"]["mine"]["unplayable"][0][:2], ("Moon Cat", 3))
        self.assertEqual(result["next"][0]["unlocks"], 3, "one piece of work unlocks all three copies")
        self.assertAlmostEqual(result["next"][0]["playable_after"], 1.0, msg="and all three count toward the share")

    def test_the_same_wording_on_two_cards_is_one_piece_of_work_that_unlocks_both(self):
        result = coverage.analyze_decks({"mine": deck((FOREST, 20), (MOON_A, 1), (MOON_B, 1), (ODD, 1))})
        first, second = result["next"][0], result["next"][1]
        self.assertEqual((first["unlocks"], sorted(first["cards"])), (2, ["Moon Cat", "Moon Elk"]))
        self.assertEqual(second["unlocks"], 1)
        self.assertEqual(second["family"], "Other: Gather the quuxes from the nearest bog.", "a line no family covers is named by its wording")

    def test_a_card_with_two_gaps_is_unlocked_only_when_both_are_built(self):
        result = coverage.analyze_decks({"mine": deck((FOREST, 20), (TWO_GAPS, 1), (MOON_A, 1))})
        first, second = result["next"][0], result["next"][1]
        self.assertEqual((first["unlocks"], first["cards"]), (1, ["Moon Cat"]), "the plain moon card first")
        self.assertEqual(first["also_needs"], "Other: Gather the quuxes from the nearest bog.", "and what the other card is waiting for")
        self.assertEqual((second["unlocks"], second["cards"]), (1, ["Odd Moon Newt"]), "the second gap then completes the card with two")

    def test_the_share_playable_after_each_piece_adds_up_to_everything(self):
        result = coverage.analyze_decks({"mine": deck((FOREST, 20), (MOON_A, 1), (MOON_B, 1), (ODD, 1), (BEAR, 1))})
        shares = [p["playable_after"] for p in result["next"]]
        self.assertEqual(shares, sorted(shares))
        self.assertAlmostEqual(shares[0], (21 + 2) / 24)
        self.assertAlmostEqual(shares[-1], 1.0)

    def test_several_decks_are_ranked_together_and_named_apart(self):
        result = coverage.analyze_decks({"one": deck((FOREST, 10), (MOON_A, 1)), "two": deck((FOREST, 10), (MOON_B, 1), (ODD, 1))})
        self.assertEqual((result["total"], result["playable"]), (23, 20))
        self.assertEqual(result["next"][0]["unlocks"], 2, "the shared wording unlocks a card in each deck")
        text = audit.render_decks(result)
        self.assertIn("**one**", text)
        self.assertIn("**two**", text)
        self.assertIn("Coverage for 2 decks: 20 of 23 cards fully playable (87%); 0 of 2 play in full", text)

    def test_the_headline_counts_the_decks_that_play_in_full(self):
        result = coverage.analyze_decks({"one": deck((FOREST, 10), (BEAR, 1)), "two": deck((FOREST, 10), (ODD, 1)), "three": deck((BEAR, 3))})
        self.assertIn("Coverage for 3 decks: 24 of 25 cards fully playable (96%); 2 of 3 play in full", audit.render_decks(result))

    def test_a_commander_counts_as_a_card_of_the_deck(self):
        result = coverage.analyze_decks({"mine": deck((FOREST, 10), commanders=[MOON_A])})
        self.assertEqual((result["total"], result["playable"]), (11, 10))

    def test_the_cards_are_grouped_by_kind_of_text(self):
        result = coverage.analyze_decks({"mine": deck((FOREST, 10), (COPY, 2), (ODD, 1))})
        kinds = dict(result["by_kind"])
        self.assertEqual(kinds.get("Copy effects"), 2)

    def test_the_report_lists_the_cards_with_their_first_line_and_the_extra_lines(self):
        text = audit.render_decks(coverage.analyze_decks({"mine": deck((FOREST, 10), (TWO_GAPS, 2), (BEAR, 1))}))
        self.assertIn("- Odd Moon Newt (x2): Whenever the moon is full, frobnicate the widget. (+1 more)", text)
        self.assertIn("What to build, in order", text)

    def test_no_single_piece_unlocks_a_card_that_needs_two(self):
        result = coverage.analyze_decks({"mine": deck((FOREST, 5), (TWO_GAPS, 1))})
        self.assertEqual([p["unlocks"] for p in result["next"]], [0, 1])
        self.assertIn("Odd Moon Newt", audit.render_decks(result))


HEADER = "// Standard: Dimir Midrange, 10.6% of MTGGoldfish's paper Standard metagame on 2026-10-28. MTGGoldfish deck 7996136.\n"


class ShareWeightedTests(unittest.TestCase):
    """The Standard lists' ranking weighted by each archetype's metagame share, read from the list's first line (#565)."""

    def decks(self):
        return {"big": deck((FOREST, 10), (MOON_A, 1)), "small": deck((FOREST, 10), (ODD, 3))}

    def test_the_share_is_read_from_the_first_line(self):
        self.assertEqual(coverage.deck_share(HEADER + "4 Cub\n"), 10.6)
        self.assertEqual(coverage.deck_share("// Standard: Boros Dwarves, 1% of the metagame.\n4 Cub\n"), 1.0)
        self.assertIsNone(coverage.deck_share("Commander\n1 Boss\n\nDeck\n4 Cub\n"))
        self.assertIsNone(coverage.deck_share("// a note with 50% in it on the second line? no:\n// 50% of nothing\n"))

    def test_the_weighted_order_puts_the_played_deck_first_and_the_count_order_stays(self):
        plain = coverage.analyze_decks(self.decks())
        result = coverage.analyze_decks(self.decks(), {"big": 10.0, "small": 1.0})
        self.assertEqual(result["next"][0]["cards"], ["Odd Toad"], "three copies outrank one by count")
        self.assertEqual([p["family"] for p in result["next"]], [p["family"] for p in plain["next"]])
        self.assertEqual((result["total"], result["playable"]), (plain["total"], plain["playable"]))
        self.assertEqual(result["weighted"][0]["cards"], ["Moon Cat"], "one copy in a 10% deck outranks three in a 1% deck")
        self.assertEqual([p["unlocks"] for p in result["weighted"]], [10.0, 3.0])
        self.assertNotIn("weighted", plain)

    def test_a_deck_without_a_share_weighs_one(self):
        result = coverage.analyze_decks(self.decks(), {"big": 2.0})
        self.assertEqual([(p["cards"], p["unlocks"]) for p in result["weighted"]], [(["Odd Toad"], 3.0), (["Moon Cat"], 2.0)])

    def test_the_report_names_the_weights_beside_the_second_table(self):
        text = audit.render_decks(coverage.analyze_decks(self.decks(), {"big": 10.6, "small": 1.0}))
        count_table, _, share_table = text.partition("### The same, weighted by metagame share")
        self.assertIn("| 1 | Other: Gather the quuxes from the nearest bog. | 3 |", count_table)
        self.assertIn("(a deck without one weighs 1): big 10.6, small 1.", share_table)
        self.assertIn("| 1 | Other: Whenever the moon is full, frobnicate the widget. | 10.6 | Moon Cat |", share_table)
        self.assertNotIn("weighted by metagame share", audit.render_decks(coverage.analyze_decks(self.decks())))

    def test_the_tool_weighs_the_lists_that_name_a_share_and_only_those(self):
        with tempfile.TemporaryDirectory() as d:
            bulk = os.path.join(d, "bulk.json")
            with open(bulk, "w", encoding="utf-8") as f:
                json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (FOREST, MOON_A, ODD)}}, f)
            big, small = os.path.join(d, "big.txt"), os.path.join(d, "small.txt")
            Path(big).write_text(HEADER + "10 Forest\n1 Moon Cat\n", encoding="utf-8")
            Path(small).write_text("10 Forest\n3 Odd Toad\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(audit.main(["--decks", big, small, "--bulk", bulk]), 0)
            self.assertIn("big 10.6, small 1.", out.getvalue())
            self.assertIn("| 1 | Other: Whenever the moon is full, frobnicate the widget. | 10.6 | Moon Cat |", out.getvalue())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(audit.main(["--decks", small, "--bulk", bulk]), 0)
            self.assertNotIn("weighted by metagame share", out.getvalue(), "a list without a share keeps the count order alone")


class GoldenReportTests(unittest.TestCase):
    """The whole `--decks` report for a fixed tiny deck, word for word (#474): moving the analysis into infernal_machine.coverage
    must not change a character of it."""

    def test_the_report_for_a_fixed_deck_is_exactly_this(self):
        mine = deck((FOREST, 20), (MOON_A, 1), (MOON_B, 1), (ODD, 1))
        self.assertEqual(
            audit.render_decks(coverage.analyze_decks({"mine": mine})),
            "## Coverage for 1 deck: 20 of 23 cards fully playable (87%); 0 of 1 play in full\n\n- **mine**: 20 of 23 cards fully playable (87%)\n\n"
            "### What to build, in order (each assuming those above it are built)\n\n"
            "| # | Piece of work | Cards unlocked | Playable after | Some of the cards | The wording |\n|---|---|---|---|---|---|\n"
            "| 1 | Other: Whenever the moon is full, frobnicate the widget. | 2 | 96% | Moon Cat, Moon Elk | Whenever the moon is full, frobnicate the widget. |\n"
            "| 2 | Other: Gather the quuxes from the nearest bog. | 1 | 100% | Odd Toad | Gather the quuxes from the nearest bog. |\n\n"
            "### By kind of text (a card counts under each kind it has)\n\n- Other: 3\n\n"
            "### The cards that can't be played yet\n\n**mine** (3):\n\n"
            "- Moon Cat: Whenever the moon is full, frobnicate the widget.\n- Moon Elk: Whenever the moon is full, frobnicate the widget.\n"
            "- Odd Toad: Gather the quuxes from the nearest bog.\n")

    def test_the_model_parameters_are_the_documented_ones(self):
        """The audit's own docstring describes these; changing one changes every ranking, so it is a decision, not a side effect."""
        self.assertEqual((coverage.WEIGHT_KNEE, coverage.DECK_CARDS, coverage.DECK_BASICS, coverage.DECK_TAIL, coverage.POPULAR),
                         (1000, 99, 17, 2, 5000))
        self.assertEqual(len(coverage.MECHANISMS), len(coverage._MECHANISMS))
        self.assertEqual(len(coverage.FAMILIES), len(coverage._FAMILIES))

    def test_the_tool_and_the_package_share_one_implementation(self):
        self.assertIs(audit.analyze_decks, coverage.analyze_decks)


class CommandLineTests(unittest.TestCase):
    def test_decks_are_read_from_files_offline(self):
        with tempfile.TemporaryDirectory() as d:
            bulk = os.path.join(d, "bulk.json")
            with open(bulk, "w", encoding="utf-8") as f:
                json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (FOREST, BEAR, MOON_A)}}, f)
            path = os.path.join(d, "my_deck.txt")
            Path(path).write_text("20 Forest\n3 Cub\n1 Moon Cat\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = audit.main(["--decks", path, "--bulk", bulk])
            self.assertEqual(code, 0)
            self.assertIn("**my_deck**: 23 of 24 cards fully playable", out.getvalue())
            self.assertIn("Moon Cat", out.getvalue())


if __name__ == "__main__":
    unittest.main()
