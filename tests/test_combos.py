"""Commander Spellbook combos (#487, #488): the cached client, the Bracket floor the combos a deck holds set, and the combos part of
`analyze` and the HTML report. The tests never reach the network: the client takes the HTTP function, and the fixture
(tests/spellbook_find_my_combos.json) is Spellbook's answer for Thassa's Oracle with Demonic Consultation and Tainted Pact, trimmed to
the fields the client reads."""

import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock
from pathlib import Path

from infernal_machine.analyze import PARTS, analyze_deck, format_analysis
from infernal_machine.brackets import analyze as bracket_analyze, bracket_floor
from infernal_machine.cards import Card, Deck
from infernal_machine.combos import CACHE_FORMAT, Combo, ComboReport, SpellbookSource, deck_key, format_combos
from infernal_machine.htmlreport import render_html
from tests.helpers import ANALYZE_BOSS as BOSS, commander_deck

FIXTURE = json.loads(Path(__file__).with_name("spellbook_find_my_combos.json").read_text(encoding="utf-8"))
ORACLE = Card(name="Thassa's Oracle", mana_cost="{U}{U}", cmc=2, type_line="Creature — Merfolk Wizard", power="1", toughness="3",
              color_identity=("U",), game_changer=True)
CONSULTATION = Card(name="Demonic Consultation", mana_cost="{B}", cmc=1, type_line="Instant", color_identity=("B",),
                    oracle_text="Exchange the frobnicator of each player with the quuxes.")  # a line the engine does not read
PACT = Card(name="Tainted Pact", mana_cost="{1}{B}", cmc=2, type_line="Instant", color_identity=("B",))
FAST = dict(games=2, sim_games=30, turns=4, seed=1)
QUIET = ["manabase", "goldfish", "tuning", "matchups"]  # the parts that take time and are tested elsewhere


class FakeHttp:
    """Answers every request with the fixture, remembering what was asked; `fail` makes it unreachable."""

    def __init__(self, fail=False):
        self.requests = []
        self.fail = fail

    def __call__(self, request):
        self.requests.append(request)
        if self.fail:
            raise urllib.error.URLError("no route to host")
        return json.loads(json.dumps(FIXTURE))


def oracle_deck():
    return commander_deck(ORACLE, CONSULTATION, PACT)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "cache", "combos.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_post_per_deck_with_the_commanders_and_the_counted_main(self):
        http = FakeHttp()
        SpellbookSource(http=http, cache_path=self.path).find(oracle_deck())
        self.assertEqual(len(http.requests), 1)
        request = http.requests[0]
        self.assertEqual((request.full_url, request.get_method()), ("https://backend.commanderspellbook.com/find-my-combos/", "POST"))
        self.assertEqual(request.get_header("User-agent"), "infernal-machine/0.1")
        body = json.loads(request.data)
        self.assertEqual(body["commanders"], [{"card": BOSS.name, "quantity": 1}])
        by_name = {entry["card"]: entry["quantity"] for entry in body["main"]}
        self.assertEqual((by_name["Thassa's Oracle"], by_name["Forest"]), (1, 38))

    def test_a_reader_during_a_save_sees_the_old_file_whole(self):
        # Another process (a bot looking its deck up while the tests run) may read the cache as it is rewritten: the new file is
        # written beside it and renamed over it, so the old one stays complete until the new one is, and no partial file is left.
        SpellbookSource(http=FakeHttp(), cache_path=self.path).find(oracle_deck())
        seen = []
        dump = json.dump

        def dump_and_peek(data, f, *args, **kwargs):
            with open(self.path, encoding="utf-8") as current:
                seen.append(sorted(json.load(current)["decks"]))
            dump(data, f, *args, **kwargs)

        with mock.patch("infernal_machine.combos.json.dump", dump_and_peek):
            SpellbookSource(http=FakeHttp(), cache_path=self.path).find(commander_deck(ORACLE))
        self.assertEqual(seen, [[deck_key(oracle_deck())]])
        self.assertEqual(sorted(os.listdir(os.path.dirname(self.path))), ["combos.json"])
        self.assertEqual(len(SpellbookSource(http=FakeHttp(fail=True), cache_path=self.path)._load()), 2)

    def test_the_answer_is_read_into_combos(self):
        report = SpellbookSource(http=FakeHttp(), cache_path=self.path).find(oracle_deck())
        self.assertEqual(report.identity, "GWUB")
        self.assertEqual([c.cards for c in report.included], [("Demonic Consultation", "Thassa's Oracle"), ("Tainted Pact", "Thassa's Oracle")])
        first = report.included[0]
        self.assertEqual((first.id, first.produces, first.tag, first.tag_name, first.bracket, first.mana, first.popularity, first.requires),
                         ("742-1295", ("Exile your library", "Win the game"), "R", "Ruthless", 4, "{U}{U}{B}", 149578, ()))
        self.assertEqual([c.label() for c in report.almost][:2], ["Demonic Consultation + Laboratory Maniac", "Doomsday + Thassa's Oracle"])

    def test_the_second_ask_is_answered_from_the_cache_offline(self):
        SpellbookSource(http=FakeHttp(), cache_path=self.path).find(oracle_deck())
        self.assertTrue(os.path.exists(self.path))
        again = SpellbookSource(http=FakeHttp(fail=True), cache_path=self.path).find(oracle_deck())
        self.assertEqual(len(again.included), 2)
        self.assertEqual(again.included[0].produces, ("Exile your library", "Win the game"))  # tuples again, not the cache's lists

    def test_a_different_deck_is_asked_again(self):
        http = FakeHttp()
        source = SpellbookSource(http=http, cache_path=self.path)
        source.find(oracle_deck())
        source.find(commander_deck(ORACLE, PACT))
        self.assertEqual(len(http.requests), 2)
        self.assertNotEqual(deck_key(oracle_deck()), deck_key(commander_deck(ORACLE, PACT)))

    def test_an_unreachable_spellbook_with_no_cache_raises_an_os_error(self):
        with self.assertRaises(OSError):
            SpellbookSource(http=FakeHttp(fail=True), cache_path=self.path).find(oracle_deck())

    def test_an_older_cache_format_is_fetched_again(self):
        os.makedirs(os.path.dirname(self.path))
        Path(self.path).write_text(json.dumps({"format": CACHE_FORMAT - 1, "decks": {deck_key(oracle_deck()): {"identity": "", "included": [], "almost": []}}}))
        http = FakeHttp()
        report = SpellbookSource(http=http, cache_path=self.path).find(oracle_deck())
        self.assertEqual((len(http.requests), len(report.included)), (1, 2))

    def test_without_a_cache_path_nothing_is_written(self):
        report = SpellbookSource(http=FakeHttp(), cache_path=None).find(oracle_deck())
        self.assertEqual(len(report.included), 2)
        self.assertEqual(os.listdir(self.tmp.name), [])


RUTHLESS = Combo("1", ("Demonic Consultation", "Thassa's Oracle"), (), ("Win the game",), "R", "{U}{U}{B}", 5)
CORE = Combo("2", ("A", "B"), ("A creature",), ("Infinite life",), "C", "", 1)
BANNED = Combo("3", ("A", "B"), (), ("Win the game",), "B", "", 1)


class BracketTests(unittest.TestCase):
    def test_a_ruthless_combo_puts_the_deck_at_bracket_four(self):
        self.assertEqual(bracket_floor(0, 0, [RUTHLESS]), 4)
        self.assertEqual(bracket_floor(1, 0, [RUTHLESS]), 4)

    def test_a_core_combo_does_not_lower_what_the_cards_say(self):
        self.assertEqual(bracket_floor(0, 0, [CORE]), 2)
        self.assertEqual(bracket_floor(1, 0, [CORE]), 3)
        self.assertEqual(bracket_floor(0, 0, [BANNED]), 1)  # a banned combo carries no bracket

    def test_the_report_names_the_combos_and_reads_as_before_without_them(self):
        report = bracket_analyze(oracle_deck(), [RUTHLESS, CORE])
        self.assertEqual((report.floor, report.combos), (4, [RUTHLESS, CORE]))
        self.assertEqual(report.summary(), "plays at Bracket 4 or higher; 1 Game Changer: Thassa's Oracle; "
                                           "2 combos: Demonic Consultation + Thassa's Oracle (Ruthless), A + B (Core)")
        plain = bracket_analyze(oracle_deck())
        self.assertEqual((plain.floor, plain.combos, plain.summary()), (3, [], "plays at Bracket 3 or higher; 1 Game Changer: Thassa's Oracle"))


class FormatTests(unittest.TestCase):
    def test_the_table_says_what_each_combo_needs_and_whether_the_engine_plays_it(self):
        text = format_combos(ComboReport("UB", [RUTHLESS, CORE], []), {"Demonic Consultation": False, "Thassa's Oracle": True, "A": True, "B": True})
        lines = text.splitlines()
        self.assertEqual(lines[0], "Combos the deck holds (2, from Commander Spellbook):")
        self.assertIn("Demonic Consultation + Thassa's Oracle", lines[2])
        self.assertIn("can't play Demonic Consultation", lines[2])
        self.assertIn("A + B (needs A creature)", lines[3])
        self.assertTrue(lines[3].rstrip().endswith("plays"))

    def test_no_combos_is_one_line(self):
        self.assertEqual(format_combos(ComboReport("UB", [], [])), "Commander Spellbook knows no combo among these cards.")


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "combos.json")

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, fail=False):
        return SpellbookSource(http=FakeHttp(fail=fail), cache_path=self.path)

    def test_the_combos_part_follows_the_bracket_and_raises_its_floor(self):
        analysis = analyze_deck(oracle_deck(), skip=QUIET, spellbook=self.source(), **FAST)
        self.assertEqual([s.title for s in analysis.sections], ["Playability", "Commander Bracket", "Combos"])
        bracket, combos = analysis.sections[1], analysis.sections[2]
        self.assertTrue(bracket.body.startswith("Plays at Bracket 4 or higher; 1 Game Changer: Thassa's Oracle; 2 combos:"), bracket.body)
        self.assertEqual(bracket.data["combos"], ["Demonic Consultation + Thassa's Oracle", "Tainted Pact + Thassa's Oracle"])
        self.assertEqual(combos.part, "combos")
        self.assertIn("can't play Demonic Consultation", combos.body)
        self.assertEqual(combos.data["combos"][1], {"cards": ["Tainted Pact", "Thassa's Oracle"], "requires": [], "produces": ["Win the game"],
                                                   "mana": "{1}{U}{U}{B}", "tag": "Ruthless", "bracket": 4, "popularity": 131683, "blocked": []})
        self.assertIn("## Combos", format_analysis(analysis))

    def test_without_a_client_there_is_no_combos_part_and_nothing_is_said(self):
        analysis = analyze_deck(oracle_deck(), skip=QUIET, **FAST)
        self.assertEqual([s.title for s in analysis.sections], ["Playability", "Commander Bracket"])
        self.assertEqual([note for note in analysis.skipped if note.startswith("Combos")], [])
        self.assertTrue(analysis.sections[1].body.startswith("Plays at Bracket 3 or higher"))

    def test_the_part_can_be_skipped(self):
        analysis = analyze_deck(oracle_deck(), skip=QUIET + ["combos"], spellbook=self.source(), **FAST)
        self.assertEqual([s.title for s in analysis.sections], ["Playability", "Commander Bracket"])
        self.assertIn("Combos (skipped on request)", analysis.skipped)
        self.assertIn("combos", PARTS)

    def test_an_unreachable_spellbook_leaves_the_part_out_and_says_so(self):
        analysis = analyze_deck(oracle_deck(), skip=QUIET, spellbook=self.source(fail=True), **FAST)
        self.assertEqual([s.title for s in analysis.sections], ["Playability", "Commander Bracket"])
        self.assertTrue(any(note.startswith("Combos (Commander Spellbook could not be reached") for note in analysis.skipped), analysis.skipped)

    def test_a_deck_with_no_combos_says_so_in_one_line(self):
        plain = SpellbookSource(http=lambda request: {"results": {"identity": "G", "included": [], "almostIncluded": []}}, cache_path=None)
        analysis = analyze_deck(commander_deck(), skip=QUIET, spellbook=plain, **FAST)
        self.assertEqual(analysis.sections[2].body, "Commander Spellbook knows no combo among these cards.")
        self.assertEqual(analysis.sections[2].data, {"identity": "G", "combos": []})

    def test_a_standard_deck_has_no_combos_part(self):
        standard = Deck([], [*[CONSULTATION] * 4, *[PACT] * 56], [])
        analysis = analyze_deck(standard, skip=QUIET, spellbook=self.source(), **FAST)
        self.assertEqual([s.title for s in analysis.sections], ["Playability"])
        self.assertIn("Combos (Commander Spellbook knows Commander decks)", analysis.skipped)


class HtmlTests(unittest.TestCase):
    def test_the_page_has_the_combos_table_and_tile(self):
        analysis = analyze_deck(oracle_deck(), skip=QUIET, spellbook=SpellbookSource(http=FakeHttp(), cache_path=None), **FAST)
        page = render_html(analysis)
        self.assertIn("<h2>Combos</h2>", page)
        self.assertIn("Demonic Consultation + Thassa&#x27;s Oracle", page)
        self.assertIn("can&#x27;t play Demonic Consultation", page)
        self.assertIn('<td class="good">plays</td>', page)
        self.assertIn("combos it holds", page)
        self.assertIn("Bracket 4+", page)
        self.assertIn("and combos", page)

    def test_no_combos_is_a_sentence_not_a_table(self):
        plain = SpellbookSource(http=lambda request: {"results": {"identity": "G", "included": [], "almostIncluded": []}}, cache_path=None)
        page = render_html(analyze_deck(commander_deck(), skip=QUIET, spellbook=plain, **FAST))
        self.assertIn("<p>Commander Spellbook knows no combo among these cards.</p>", page)
        self.assertIn("<b>0</b><span>combos it holds</span>", page)


if __name__ == "__main__":
    unittest.main()
