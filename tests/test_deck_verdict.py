"""The verdict on a deck (issue #477): "Plays fully" / "Plays except N cards", the lines to build to unlock it, in the markdown report, the
saved run and the HTML report."""

import unittest

from infernal_machine import coverage
from infernal_machine.analyze import Analysis, Section, analyze_deck, format_analysis
from infernal_machine.cards import Card, Deck
from infernal_machine.htmlreport import render_html
from tests.helpers import real

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = real("Cub", "{1}{G}", "Creature — Bear", "", "2", "2")
MOON = "Whenever the moon is full, frobnicate the widget."
MOON_A = real("Moon Cat", "{1}{G}", "Creature — Cat", MOON, "1", "1")
MOON_B = real("Moon Elk", "{1}{G}", "Creature — Elk", MOON, "1", "1")
SKIP = ["bracket", "manabase", "goldfish", "tuning", "matchups"]  # only the verdict, which needs no games


def odd(i):
    return real(f"Odd Beast {i}", "{G}", "Creature — Frog", f"Gather the quuxes number {chr(97 + i)} from the nearest bog.", "1", "1")


def deck(*cards):
    return Deck([], [c for card, n in cards for c in [card] * n], [])


def verdict_of(d, **more):
    return analyze_deck(d, skip=SKIP, **more).sections[0]


class WordingTests(unittest.TestCase):
    def test_the_headline_for_each_number_of_blocked_cards(self):
        self.assertEqual([coverage.verdict(n) for n in (0, 1, 2, 10, 11, 40)],
                         ["Plays fully", "Plays except 1 card", "Plays except 2 cards", "Plays except 10 cards",
                          "11 cards can't be played yet", "40 cards can't be played yet"])

    def test_a_negative_count_is_not_a_failure(self):
        self.assertEqual(coverage.verdict(-1), "Plays fully")


class PlayabilityDataTests(unittest.TestCase):
    def test_a_deck_the_engine_plays_has_nothing_blocked_and_nothing_to_fix(self):
        data = coverage.playability(deck((FOREST, 30), (BEAR, 3)))
        self.assertEqual((data["cards"], data["playable"], data["unplayable"], data["fixes"]), (33, 33, [], []))

    def test_blocked_cards_are_listed_most_copies_first_with_their_first_line(self):
        data = coverage.playability(deck((FOREST, 20), (MOON_A, 1), (MOON_B, 3), (BEAR, 1)))
        self.assertEqual((data["cards"], data["playable"]), (25, 21))
        self.assertEqual([(c["name"], c["copies"]) for c in data["unplayable"]], [("Moon Elk", 3), ("Moon Cat", 1)])
        self.assertEqual(data["unplayable"][0]["line"], MOON)
        self.assertEqual(data["unplayable"][0]["more"], 0)

    def test_the_fixes_are_ranked_by_the_cards_they_unlock_for_this_deck(self):
        data = coverage.playability(deck((FOREST, 20), (MOON_A, 1), (MOON_B, 1), (odd(0), 1)))
        self.assertEqual([f["unlocks"] for f in data["fixes"]], [2, 1])
        self.assertEqual(sorted(data["fixes"][0]["cards"]), ["Moon Cat", "Moon Elk"])
        self.assertAlmostEqual(data["fixes"][-1]["playable_after"], 1.0)
        self.assertLess(data["fixes"][0]["playable_after"], 1.0)

    def test_a_deck_with_no_cards_does_not_divide_by_zero(self):
        data = coverage.playability(Deck([], [], []))
        self.assertEqual((data["cards"], data["playable"]), (0, 0))

    def test_the_numbers_are_the_same_whatever_the_deck_is_called(self):
        d = deck((FOREST, 20), (MOON_A, 1))
        self.assertEqual(coverage.playability(d, "a"), coverage.playability(d, "b"))


class MarkdownTests(unittest.TestCase):
    def test_the_section_is_first_never_code_and_always_there(self):
        for d in (deck((FOREST, 20)), deck((FOREST, 20), (MOON_A, 1))):
            analysis = analyze_deck(d, skip=SKIP)
            self.assertEqual((analysis.sections[0].title, analysis.sections[0].part, analysis.sections[0].code), ("Playability", "playability", False))

    def test_a_deck_that_plays_fully_says_so(self):
        section = verdict_of(deck((FOREST, 20), (BEAR, 2)))
        self.assertEqual(section.body, "Plays fully: 22 of 22 cards fully playable (100%). Every card is one the engine understands.")

    def test_a_deck_with_blocked_cards_gets_the_verdict_the_note_and_the_fix_list(self):
        body = verdict_of(deck((FOREST, 20), (MOON_A, 1), (MOON_B, 1), (BEAR, 1))).body
        self.assertTrue(body.startswith("Plays except 2 cards: 21 of 23 cards fully playable (91%)."), body)
        self.assertIn("can't fully play: Moon Cat, Moon Elk", body)
        self.assertIn("Fix these lines to unlock this deck:\n1. " + MOON + " (unlocks 2: ", body)
        self.assertIn("-> 100% playable", body)

    def test_only_five_fixes_are_listed_and_the_rest_counted(self):
        body = verdict_of(deck((FOREST, 20), *[(odd(i), 1) for i in range(8)])).body
        numbered = [line for line in body.splitlines() if line[:1].isdigit()]
        self.assertEqual(len(numbered), 5)
        self.assertIn("... and 3 more pieces of work that each unlock at least one card.", body)

    def test_a_very_long_rules_line_is_cut_in_the_printed_report_but_kept_whole_in_the_numbers(self):
        long_text = "Whenever the moon is full, " + "frobnicate the widget and " * 12 + "stop."
        section = verdict_of(deck((FOREST, 20), (real("Moon Owl", "{1}{G}", "Creature — Bird", long_text, "1", "1"), 1)))
        row = next(line for line in section.body.splitlines() if line.startswith("1. "))
        self.assertIn("... (unlocks 1: Moon Owl)", row)
        self.assertLess(len(row), 260)
        self.assertEqual(section.data["fixes"][0]["line"], long_text)

    def test_more_than_ten_blocked_cards_are_said_bluntly(self):
        body = verdict_of(deck((FOREST, 20), *[(odd(i), 1) for i in range(12)])).body
        self.assertTrue(body.startswith("12 cards can't be played yet: "), body)

    def test_the_matchup_warning_is_kept_when_there_are_opponents(self):
        analysis = analyze_deck(deck((FOREST, 20), (MOON_A, 1)), {"them": deck((FOREST, 20))}, skip=["bracket", "manabase", "goldfish", "tuning"],
                                games=2, sim_games=2, turns=2, workers=1)
        self.assertIn("The matchup win rates below are unreliable for the same reason.", analysis.sections[0].body)

    def test_a_deck_with_no_cards_says_so(self):
        self.assertEqual(verdict_of(Deck([], [], [])).body, "The deck has no cards.")

    def test_it_can_be_skipped(self):
        analysis = analyze_deck(deck((FOREST, 20), (MOON_A, 1)), skip=SKIP + ["playability"])
        self.assertEqual(analysis.sections, [])
        self.assertIn("Playability (skipped on request)", analysis.skipped)
        self.assertNotIn("playability", analysis.record["parts"])

    def test_it_is_in_the_printed_report(self):
        text = format_analysis(analyze_deck(deck((FOREST, 20), (MOON_A, 1)), skip=SKIP))
        self.assertIn("## Playability", text)
        self.assertIn("Plays except 1 card", text)


class SavedRunTests(unittest.TestCase):
    def test_the_numbers_are_kept_in_the_record(self):
        analysis = analyze_deck(deck((FOREST, 20), (MOON_A, 1)), skip=SKIP)
        part = analysis.record["parts"]["playability"]
        self.assertEqual((part["data"]["cards"], part["data"]["playable"]), (21, 20))
        self.assertEqual(part["settings"], {})

    def test_it_is_worked_out_again_not_taken_from_the_earlier_run(self):
        d = deck((FOREST, 20), (MOON_A, 1))
        first = analyze_deck(d, skip=SKIP)
        stale = first.record
        stale["parts"]["playability"]["data"] = {"cards": 21, "playable": 21, "unplayable": [], "fixes": []}  # as if the engine could play it then
        second = analyze_deck(d, skip=SKIP, since=stale)
        self.assertEqual(second.sections[0].data["playable"], 20)
        self.assertNotIn("playability", second.record["reused"])
        self.assertIn("Playable cards: 21 of 21 -> 20 of 21 (no longer: Moon Cat).", second.changes)

    def test_what_changed_names_cards_that_started_playing_and_not_cards_taken_out(self):
        first = analyze_deck(deck((FOREST, 20), (MOON_A, 1), (MOON_B, 1)), skip=SKIP)
        second = analyze_deck(deck((FOREST, 20), (BEAR, 1), (MOON_B, 1)), skip=SKIP, since=first.record)
        self.assertIn("Playable cards: 20 of 22 -> 21 of 22.", second.changes, "Moon Cat left the deck: it did not start playing")

    def test_what_changed_names_a_card_that_broke_and_one_that_was_added(self):
        first = analyze_deck(deck((FOREST, 20), (MOON_A, 1)), skip=SKIP)
        second = analyze_deck(deck((FOREST, 20), (MOON_A, 1), (MOON_B, 1)), skip=SKIP, since=first.record)
        self.assertIn("Playable cards: 20 of 21 -> 20 of 22.", second.changes)
        self.assertNotIn("no longer", second.changes, "a card added to the deck did not break")


def html_of(data, body="text"):
    return render_html(Analysis("deck", "Commander", [Section("Playability", body, 0.0, False, "playability", data)]))


def blocked(i, copies=1, more=0, line=None):
    return {"name": f"Card {i}", "copies": copies, "line": line or f"Line number {i}.", "more": more}


def fix(i, unlocks=1, after=0.97):
    return {"family": f"Family {i}", "line": f"Fix line {i}.", "unlocks": unlocks, "cards": [f"Card {i}"], "playable_after": after}


class HtmlTests(unittest.TestCase):
    def test_a_deck_that_plays_fully(self):
        page = html_of({"cards": 100, "playable": 100, "unplayable": [], "fixes": []})
        self.assertIn('<h2 class="good">Plays fully</h2>', page)
        self.assertIn('class="pbar full"', page)
        self.assertIn("Every card is one the engine understands.", page)
        self.assertNotIn("Fix these lines", page)
        self.assertNotIn("<details>", page)

    def test_a_few_blocked_cards(self):
        page = html_of({"cards": 100, "playable": 96, "unplayable": [blocked(i) for i in range(4)], "fixes": [fix(i, 1, 0.97) for i in range(2)]})
        self.assertIn('<h2>Plays except <span class="bad">4</span> cards</h2>', page)
        self.assertIn("96 of 100 cards fully playable", page)
        self.assertIn('style="width:96.0%"', page)
        self.assertIn("Fix these lines to unlock this deck", page)
        self.assertIn("+1 card, 97% playable after", page)
        self.assertIn("<summary>All 4 blocked cards</summary>", page)

    def test_many_blocked_cards_are_said_bluntly(self):
        page = html_of({"cards": 100, "playable": 80, "unplayable": [blocked(i) for i in range(20)], "fixes": []})
        self.assertIn('<h2><span class="bad">20</span> cards can&#x27;t be played yet</h2>', page)

    def test_five_fixes_are_shown_and_the_rest_are_behind_a_disclosure(self):
        page = html_of({"cards": 100, "playable": 90, "unplayable": [blocked(i) for i in range(10)], "fixes": [fix(i) for i in range(8)]})
        shown, rest = page.split("<summary>Show 3 more</summary>")
        self.assertEqual(shown.count("<li><code>Fix line"), 5)
        self.assertEqual(rest.split("</details>")[0].count("<li><code>Fix line"), 3)
        self.assertIn('<ol class="fixes" start="6">', rest)

    def test_exactly_five_fixes_have_no_disclosure_for_more(self):
        page = html_of({"cards": 100, "playable": 95, "unplayable": [blocked(i) for i in range(5)], "fixes": [fix(i) for i in range(5)]})
        self.assertNotIn("Show ", page)

    def test_the_bar_does_not_depend_on_color_alone(self):
        page = html_of({"cards": 100, "playable": 96, "unplayable": [blocked(0)], "fixes": []})
        self.assertIn('role="img" aria-label="96% of cards fully playable"', page)

    def test_both_disclosures_are_native_details(self):
        page = html_of({"cards": 100, "playable": 90, "unplayable": [blocked(i) for i in range(10)], "fixes": [fix(i) for i in range(8)]})
        self.assertEqual(page.count("<details>"), 2)
        self.assertEqual(page.count("<summary>"), 2)

    def test_rules_text_and_names_are_escaped(self):
        evil = '<script>alert("x")</script> & more'
        data = {"cards": 10, "playable": 9, "unplayable": [{"name": evil, "copies": 1, "line": evil, "more": 0}],
                "fixes": [{"family": "F", "line": evil, "unlocks": 1, "cards": [evil], "playable_after": 1.0}]}
        page = html_of(data)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert", page)

    def test_copies_and_extra_lines_are_shown_in_the_full_list(self):
        page = html_of({"cards": 10, "playable": 6, "unplayable": [blocked(1, copies=3, more=2)], "fixes": []})
        self.assertIn("<b>Card 1</b> (x3)", page)
        self.assertIn("+2 more lines", page)

    def test_a_card_with_one_extra_line_says_line_not_lines(self):
        page = html_of({"cards": 10, "playable": 9, "unplayable": [blocked(1, more=1)], "fixes": []})
        self.assertIn("+1 more line<", page)

    def test_chips_show_three_cards_and_count_the_rest(self):
        f = {"family": "F", "line": "L", "unlocks": 6, "cards": ["A", "B", "C"], "playable_after": 1.0}
        page = html_of({"cards": 10, "playable": 4, "unplayable": [blocked(1)], "fixes": [f]})
        self.assertIn("<span>A</span><span>B</span><span>C</span><span>+3 more</span>", page)
        self.assertIn("+6 cards, 100% playable after", page)

    def test_a_deck_with_no_cards(self):
        page = html_of({"cards": 0, "playable": 0, "unplayable": [], "fixes": []})
        self.assertIn("<h2>No cards</h2>", page)

    def test_a_run_saved_before_the_verdict_falls_back_to_its_text(self):
        page = html_of({}, body="Old text about the deck.")
        self.assertIn("Old text about the deck.", page)
        self.assertNotIn('class="verdict"', page)

    def test_the_verdict_comes_before_the_tiles_and_the_other_parts(self):
        sections = [Section("Playability", "t", 0.0, False, "playability", {"cards": 1, "playable": 1, "unplayable": [], "fixes": []}),
                    Section("Mana base", "t", part="manabase", data={"lands": 1, "colors": {}})]
        page = render_html(Analysis("deck", "Commander", sections))
        self.assertLess(page.index('class="verdict"'), page.index('<div class="tiles">'))
        self.assertLess(page.index('<div class="tiles">'), page.index("<h2>Mana base</h2>"))
        self.assertEqual(page.count("Plays fully"), 1, "drawn once, not again in the loop over the parts")

    def test_a_real_analysis_renders_the_verdict(self):
        page = render_html(analyze_deck(deck((FOREST, 20), (MOON_A, 1)), skip=SKIP))
        self.assertIn("Plays except <span", page)
        self.assertIn(MOON, page)


if __name__ == "__main__":
    unittest.main()
