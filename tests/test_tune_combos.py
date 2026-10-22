"""`tune --suggest-combos` (#489): the cards Commander Spellbook says are one card from completing a combo the deck is close to, tried through
the same swap table as `--try`, each with the combos it would complete and what they produce. Spellbook is a fake that answers from a
list; the pieces and candidates are probes."""

import contextlib
import io
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path

from infernal_machine.cards import Card, Deck
from infernal_machine.combos import Combo, SpellbookSource
from infernal_machine.tune import COMBOS_SHOWN, combo_suggestions, format_tuning, main, tune
from tests.helpers import ANALYZE_BEAR as BEAR, ANALYZE_BOSS as BOSS, ANALYZE_FOREST as FOREST, FakeSource


def probe(name, text="", identity=("G",)):
    return Card(name=name, mana_cost="{1}{G}", cmc=2, type_line="Artifact", oracle_text=text, color_identity=identity)


PIECE_A = probe("Piece A")
PIECE_B = probe("Piece B")
STUCK_PIECE = probe("Stuck Piece", "Frobnicate the widget whenever the moon is full.")  # a line the engine does not read
X, Y, W, Q = probe("Card X"), probe("Card Y"), probe("Card W"), probe("Card Q", "Frobnicate the widget whenever the moon is full.")
OUTSIDE = probe("Blue Card", identity=("U",))
CARDS = [FOREST, BEAR, BOSS, PIECE_A, PIECE_B, STUCK_PIECE, X, Y, W, Q, OUTSIDE]


def combo(cards, popularity, produces=("Infinite mana",), requires=(), tag="S"):
    return Combo("1", tuple(cards), tuple(requires), tuple(produces), tag, "", popularity)


def deck():
    return Deck([BOSS], [*[FOREST] * 30, *[BEAR] * 25, PIECE_A, PIECE_B, STUCK_PIECE], [])


ALMOST = [
    combo(["Piece A", "Card X"], 100),
    combo(["Piece B", "Card X"], 300),
    combo(["Piece A", "Card Y"], 900),
    combo(["Boss", "Card W"], 500),          # the commander is one of the deck's cards
    combo(["Piece A", "Card X", "Card Y"], 999),  # two cards missing: not one away
    combo(["Piece A", "Piece B"], 999),      # none missing: the deck already holds it
]


class SuggestionTests(unittest.TestCase):
    def test_a_card_that_completes_more_combos_comes_first_then_the_more_played_one(self):
        names = [s.card for s in combo_suggestions(deck(), ALMOST)]
        self.assertEqual(names, ["Card X", "Card Y", "Card W"])  # X completes two; Y (900 decks) before W (500)

    def test_each_cards_combos_are_listed_most_played_first(self):
        x = combo_suggestions(deck(), ALMOST)[0]
        self.assertEqual([c.popularity for c in x.combos], [300, 100])

    def test_combos_missing_two_cards_or_none_are_left_out(self):
        listed = [c.cards for s in combo_suggestions(deck(), ALMOST) for c in s.combos]
        self.assertNotIn(("Piece A", "Card X", "Card Y"), listed)
        self.assertNotIn(("Piece A", "Piece B"), listed)

    def test_the_limit_keeps_the_best(self):
        self.assertEqual([s.card for s in combo_suggestions(deck(), ALMOST, limit=2)], ["Card X", "Card Y"])

    def test_ties_break_by_name(self):
        tied = [combo(["Piece A", "Card Y"], 5), combo(["Piece A", "Card X"], 5)]
        self.assertEqual([s.card for s in combo_suggestions(deck(), tied)], ["Card X", "Card Y"])

    def test_no_almost_combos_no_suggestions(self):
        self.assertEqual(combo_suggestions(deck(), []), [])


class FormatTests(unittest.TestCase):
    def report(self, suggestions, candidates):
        report = tune(deck(), games=30, turns=3, seed=1, candidates=candidates)
        report.suggestions = suggestions
        return report

    def text(self, almost=ALMOST, candidates=(X, Y, W)):
        return format_tuning(self.report(combo_suggestions(deck(), almost), list(candidates)))

    def test_each_card_says_what_it_completes_and_what_that_produces(self):
        text = self.text()
        self.assertIn("Combos one card away (Commander Spellbook).", text)
        self.assertIn("  Card X: completes 2 combos; swap ", text)
        self.assertIn("    with Piece B: Infinite mana (Spicy, 300 decks)", text)
        self.assertIn("  Card Y: completes 1 combo; swap ", text)

    def test_the_pieces_are_the_decks_cards_and_not_the_candidate(self):
        self.assertNotIn("with Piece A + Card X", self.text())
        self.assertIn("with Boss: ", self.text())

    def test_what_a_combo_needs_and_makes_is_shown_and_long_lists_are_cut(self):
        almost = [combo(["Piece A", "Card X"], 5, produces=("One", "Two", "Three", "Four"), requires=("A creature with power 3",))]
        self.assertIn("with Piece A (needs A creature with power 3): One, Two, Three, ...", self.text(almost, [X]))

    def test_a_card_with_many_combos_shows_the_first_few_and_counts_the_rest(self):
        almost = [combo(["Piece A", "Card X"], 100 + n) for n in range(COMBOS_SHOWN + 2)]
        text = self.text(almost, [X])
        self.assertEqual(text.count("    with Piece A"), COMBOS_SHOWN)
        self.assertIn(f"    and 2 more", text)

    def test_a_piece_or_candidate_the_engine_cannot_play_is_said(self):
        text = self.text([combo(["Stuck Piece", "Card X"], 5), combo(["Piece A", "Card Q"], 4)], [X, Q])
        self.assertIn("with Stuck Piece: Infinite mana (Spicy, 5 decks)  [the engine can't play Stuck Piece]", text)
        self.assertIn("with Piece A: Infinite mana (Spicy, 4 decks)  [the engine can't play Card Q]", text)

    def test_a_card_that_could_not_be_tried_says_why_once(self):
        report = self.report(combo_suggestions(deck(), [combo(["Piece A", "Blue Card"], 5)]), [OUTSIDE])
        text = format_tuning(report)
        self.assertIn("  Blue Card: completes 1 combo; not tried: outside the commander's color identity (U)", text)
        self.assertNotIn("Not tried:", text)  # said in the suggestions, not again

    def test_a_card_tried_by_hand_that_was_skipped_is_still_listed_under_not_tried(self):
        report = self.report([], [OUTSIDE])
        self.assertIn("Not tried: Blue Card (outside the commander's color identity (U))", format_tuning(report))

    def test_without_suggestions_the_report_is_as_before(self):
        self.assertNotIn("Combos one card away", format_tuning(self.report([], [X])))


class CommandLineTests(unittest.TestCase):
    DECKLIST = "Commander\n1 Boss\n\nDeck\n30 Forest\n25 Grizzly Bears\n1 Piece A\n1 Piece B\n1 Stuck Piece\n"

    def spellbook(self, almost=ALMOST, fail=False):
        def answer(request):
            if fail:
                raise urllib.error.URLError("no route to host")
            variants = [{"id": str(i), "uses": [{"card": {"name": n}} for n in c.cards],
                         "produces": [{"feature": {"name": p}} for p in c.produces], "requires": [], "bracketTag": c.tag,
                         "popularity": c.popularity} for i, c in enumerate(almost)]
            return {"results": {"identity": "G", "included": [], "almostIncluded": variants}}
        return SpellbookSource(http=answer, cache_path=None)

    def run_main(self, *options, decklist=None, spellbook=None, cards=CARDS):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "deck.txt")
            Path(path).write_text(decklist or self.DECKLIST, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(["tune", path, "--games", "30", "--turns", "3", *options], source=FakeSource(*cards),
                            spellbook=spellbook or self.spellbook())
            return code, out.getvalue(), err.getvalue()

    def test_the_flag_tries_the_suggested_cards_and_lists_what_they_complete(self):
        code, out, _ = self.run_main("--suggest-combos")
        self.assertEqual(code, 0)
        self.assertIn("Combos one card away (Commander Spellbook).", out)
        self.assertIn("  Card X: completes 2 combos; swap ", out)
        self.assertRegex(out, r"  Card X for [^:]+: [+-]\d")  # the usual swap table has it too
        self.assertIn("  Card W: completes 1 combo", out)  # with no number, the ten best: all three here

    def test_a_number_limits_how_many(self):
        _, out, _ = self.run_main("--suggest-combos", "1")
        self.assertIn("  Card X: completes", out)
        self.assertNotIn("  Card Y: completes", out)

    def test_without_the_flag_nothing_is_asked_or_said(self):
        _, out, _ = self.run_main(spellbook=self.spellbook(fail=True))
        self.assertNotIn("Combos one card away", out)

    def test_a_card_named_by_hand_and_suggested_is_tried_once(self):
        _, out, _ = self.run_main("--try", "Card X", "--suggest-combos")
        self.assertEqual(out.count("  Card X for "), 1)

    def test_a_card_missing_from_the_card_data_is_said(self):
        _, out, _ = self.run_main("--suggest-combos", cards=[c for c in CARDS if c.name != "Card Y"])
        self.assertIn("  Card Y: completes 1 combo; not tried: not in the card data", out)

    def test_a_deck_with_no_commander_is_refused(self):
        code, out, err = self.run_main("--suggest-combos", decklist="30 Forest\n30 Grizzly Bears\n")
        self.assertEqual(code, 2)
        self.assertIn("needs a Commander deck", err)
        self.assertEqual(out, "")

    def test_an_unreachable_spellbook_with_no_cache_is_an_error(self):
        code, out, err = self.run_main("--suggest-combos", spellbook=self.spellbook(fail=True))
        self.assertEqual(code, 2)
        self.assertIn("Commander Spellbook could not be reached", err)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
