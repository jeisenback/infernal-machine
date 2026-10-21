"""The HTML report (htmlreport.py, issue #447): it shows each number the analysis has, escapes what a card or file name could break the
page with, falls back to the text where the numbers were not kept, and loads nothing from the network."""

import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path

from infernal_machine.analyze import Analysis, Section, analyze_deck, main
from infernal_machine.htmlreport import render_html
from infernal_machine.matchup import wilson
from tests.helpers import ANALYZE_BEAR as BEAR, ANALYZE_BOSS as BOSS, ANALYZE_FOREST as FOREST, FakeSource, commander_deck

CARDS = [{"name": "Strong <b>Card</b>", "copies": 1, "delta": 1.25, "error": 0.2, "seen": 0.4, "cast_when_seen": 0.9, "note": ""},
         {"name": "Weak Card", "copies": 2, "delta": -0.5, "error": 0.1, "seen": 0.3, "cast_when_seen": 0.25, "note": "rarely cast when drawn"},
         {"name": "Noise Card", "copies": 1, "delta": 0.02, "error": 0.5, "seen": 0.1, "cast_when_seen": 1.0, "note": ""}]


def analysis(**more):
    sections = [
        Section("Playability", "Plays except 1 card: Odd Spell can't be played.", part="playability", code=False),
        Section("Commander Bracket", "No hard limit above Bracket 2.", part="bracket", code=False, data={"floor": 2, "game_changers": []}),
        Section("Mana base", "text", part="manabase", data={"lands": 37, "colors": {"W": {"have": 30, "needed": 24, "short": 0},
                                                                              "R": {"have": 12, "needed": 18, "short": 6}}}),
        Section("Goldfish", "text", part="goldfish", seconds=1.0,
                data={"games": 30, "turns": 4, "mulligan_rate": 0.1, "on_curve": 0.36, "land_drops": {"1": 1.0, "2": 0.9},
                      "damage": {"1": 0.0, "2": 1.5, "3": 4.0, "4": 9.5}}),
        Section("Tuning", "tuning text", part="tuning",
                data={"games": 30, "turns": 4, "baseline": 21.5, "cards": CARDS, "lands": {"-1": {"delta": 0.4, "error": 0.2}},
                      "swaps": [{"card": "Sol Ring", "replaces": "Weak Card", "delta": 1.5, "error": 0.3, "note": "no Bracket change"}]}),
        Section("Matchups", "text", part="matchups", data={"pod": 2, "opponents": {"Strong Deck": {"wins": 9, "games": 10, "draws": 0},
                                                                              "Even Deck": {"wins": 5, "games": 10, "draws": 0}}}),
    ]
    return Analysis("my <deck>", "Commander", sections, **more)


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.page = render_html(analysis(skipped=["Other thing (skipped on request)"]), "30 games.")

    def test_it_is_a_document_with_the_deck_named_and_the_settings(self):
        self.assertTrue(self.page.startswith("<!doctype html>"))
        self.assertIn("<title>Analysis of my &lt;deck&gt;</title>", self.page)
        self.assertIn("Commander deck. 30 games.", self.page)

    def test_a_name_that_could_break_the_page_is_escaped(self):
        self.assertIn("Strong &lt;b&gt;Card&lt;/b&gt;", self.page)
        self.assertNotIn("<b>Card</b>", self.page)

    def test_the_playability_section_comes_before_everything(self):
        self.assertLess(self.page.index("Odd Spell can&#x27;t be played."), self.page.index("<h2>Commander Bracket</h2>"))
        self.assertLess(self.page.index("Playability"), self.page.index('<div class="tiles">'))

    def test_the_summary_tiles(self):
        for text in ("Commander", "Bracket 2+", "37", "lands, 6 sources short", "10%", "36%", "of 20 matchup games"):
            self.assertIn(text, self.page)
        self.assertIn("70%", self.page)  # 14 of 20 won

    def test_the_mana_base_says_what_is_short(self):
        self.assertIn("short by 6", self.page)
        self.assertIn("enough", self.page)

    def test_the_mana_bars_share_one_scale_and_the_tick_is_what_is_needed(self):
        self.assertIn('style="width:100.0%"', self.page)  # W: 30 of the most, 30
        self.assertIn('style="width:40.0%"', self.page)  # R: 12 of 30
        self.assertIn('class="tick" style="left:80.0%"', self.page)  # W needs 24 of 30
        self.assertIn('class="tick" style="left:60.0%"', self.page)  # R needs 18 of 30

    def test_a_section_title_is_escaped(self):
        page = render_html(Analysis("x", "Commander", [Section("Odd & <title>", "body", part="other")]))
        self.assertIn("<h2>Odd &amp; &lt;title&gt;</h2>", page)

    def test_the_opponents_come_weakest_first(self):
        self.assertLess(self.page.index("Even Deck"), self.page.index("Strong Deck"))

    def test_the_goldfish_charts_damage_by_turn(self):
        self.assertIn("<svg", self.page)
        for value in ("9.5", "T4", "90%"):
            self.assertIn(value, self.page)

    def test_every_card_has_its_value_with_the_error_and_only_clear_ones_are_coloured(self):
        self.assertIn("+1.25 &plusmn; 0.40", self.page)
        self.assertIn("-0.50 &plusmn; 0.20", self.page)
        self.assertIn("rarely cast when drawn", self.page)
        self.assertRegex(self.page, r'class="n good" data-v="1.25"')
        self.assertRegex(self.page, r'class="n bad" data-v="-0.5"')
        self.assertRegex(self.page, r'class="n " data-v="0.02"')  # +0.02 +- 1.0 is nothing

    def test_land_count_and_swaps(self):
        self.assertIn("-1 lands", self.page)
        self.assertIn("Sol Ring", self.page)
        self.assertIn("no Bracket change", self.page)

    def test_each_opponent_has_its_rate_and_interval_and_a_verdict(self):
        low, high = wilson(9, 10)
        self.assertIn(f"{low:.0%}&ndash;{high:.0%}", self.page)
        self.assertIn("9 of 10", self.page)
        self.assertIn("ahead", self.page)  # 90%: the interval is above one half
        self.assertIn("too close to say", self.page)  # 5 of 10

    def test_the_footer_says_what_was_left_out_and_the_time(self):
        self.assertIn("Left out: Other thing (skipped on request).", self.page)
        self.assertIn("Took 1 seconds (goldfish 1.0s).", self.page)

    def test_what_changed_is_shown_when_there_is_something(self):
        self.assertNotIn("What changed", self.page)
        self.assertIn("<h2>What changed</h2><pre>mana base: +1</pre>", render_html(analysis(changes="mana base: +1")))


class FallbackTests(unittest.TestCase):
    def test_a_part_whose_numbers_were_not_kept_shows_its_text(self):
        old = Analysis("old", "Commander", [Section("Tuning", "text <of> the table", part="tuning", data={"games": 5, "baseline": 3.0}),
                                             Section("Matchups", "matchup text", part="matchups", data={}),
                                             Section("Mana base", "mana text", part="manabase", data={}),
                                             Section("Goldfish", "goldfish text", part="goldfish", data={})])
        page = render_html(old)
        for text in ("text &lt;of&gt; the table", "matchup text", "mana text", "goldfish text"):
            self.assertIn(text, page)

    def test_a_standard_deck_has_no_bracket_tile(self):
        page = render_html(Analysis("std", "Standard", [Section("Mana base", "t", part="manabase", data={"lands": 24, "colors": {}})]))
        self.assertNotIn("Bracket", page)


class SelfContainedTests(unittest.TestCase):
    def test_nothing_is_loaded_from_anywhere(self):
        page = render_html(analysis())
        self.assertNotRegex(page, r"https?://")
        self.assertNotRegex(page, r"<script[^>]+src=|<link |@import|url\(")

    def test_the_page_follows_the_readers_color_scheme_and_fits_a_phone(self):
        page = render_html(analysis())
        self.assertIn("prefers-color-scheme: dark", page)
        self.assertIn('name="viewport"', page)
        self.assertIn("max-width:600px", page)


class EndToEndTests(unittest.TestCase):
    def test_a_real_analysis_renders_every_part(self):
        result = analyze_deck(commander_deck(), {"opp": commander_deck()}, games=2, sim_games=30, turns=4, seed=1, workers=1)
        page = render_html(result)
        for heading in ("Commander Bracket", "Mana base", "Goldfish", "Tuning", "Matchups"):
            self.assertIn(f"<h2>{heading}</h2>", page)
        self.assertIn("Grizzly Bears", page)  # the tuning table names the cards
        self.assertTrue(re.search(r"\d+ of 2", page))  # the matchup record

    def test_the_tuning_data_names_the_card_tried_and_the_card_it_replaces(self):
        from infernal_machine.cards import Card

        dud = Card(name="Aaa Dud", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1", color_identity=("G",))
        fresh = Card(name="Fresh Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))
        result = analyze_deck(commander_deck(*[dud] * 8), candidates=[fresh], skip=["goldfish"], games=2, sim_games=30, turns=4, seed=1)
        swaps = next(s for s in result.sections if s.part == "tuning").data["swaps"]
        self.assertEqual((swaps[0]["card"], swaps[0]["replaces"]), ("Fresh Bear", "Aaa Dud"))
        self.assertIn("Fresh Bear", render_html(result))

    def test_the_option_writes_the_page(self):
        deck = "24 Forest\n36 Grizzly Bears\n"
        with tempfile.TemporaryDirectory() as directory:
            for name in ("mine.txt", "theirs.txt"):
                Path(directory, name).write_text(deck, encoding="utf-8")
            target = os.path.join(directory, "report.html")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                code = main([os.path.join(directory, "mine.txt"), os.path.join(directory, "theirs.txt"), "--sim-games", "20", "--turns", "3",
                             "--games", "2", "--workers", "1", "--html", target], source=FakeSource(FOREST, BEAR, BOSS))
            self.assertEqual(code, 0)
            page = Path(target).read_text(encoding="utf-8")
            self.assertIn("<title>Analysis of mine</title>", page)
            self.assertIn("theirs", page)
            self.assertIn(f"Wrote the HTML report to {target}.", err.getvalue())

    def test_no_option_writes_no_page(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "mine.txt").write_text("24 Forest\n36 Grizzly Bears\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                main([os.path.join(directory, "mine.txt"), "--sim-games", "20", "--turns", "3", "--skip", "matchups", "--workers", "1"],
                     source=FakeSource(FOREST, BEAR, BOSS))
            self.assertEqual([p for p in os.listdir(directory) if p.endswith(".html")], [])


if __name__ == "__main__":
    unittest.main()
