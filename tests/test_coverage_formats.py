"""The coverage audit for a format other than Commander (#521): Scryfall's search for the format, and the numbers without EDHREC's rank."""

import contextlib
import importlib.util
import io
import json
import os
import unittest
from unittest import mock

from infernal_machine import coverage

_spec = importlib.util.spec_from_file_location("coverage_audit", os.path.join(os.path.dirname(__file__), "..", "tools", "coverage_audit.py"))
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

COPY = "Create a token that's a copy of target creature."


def card(name, type_line, text, rank=None, **more):
    return {"name": name, "type_line": type_line, "oracle_text": text, "mana_cost": more.pop("mana_cost", ""), "cmc": 0,
            **({"edhrec_rank": rank} if rank else {}), **more}


POOL = [
    card("Plain Forest", "Basic Land — Forest", "({T}: Add {G}.)", rank=1, produced_mana=["G"]),
    card("Copy Cat", "Creature — Cat", COPY, mana_cost="{1}", power="1", toughness="1"),
    card("Copy Dog", "Creature — Dog", COPY, rank=9000, mana_cost="{1}", power="1", toughness="1"),
]


class WithoutPopularityTests(unittest.TestCase):
    def setUp(self):
        self.result = coverage.analyze(POOL, popularity=False)

    def test_there_is_no_rank_table_deck_or_ranked_card(self):
        self.assertEqual((self.result["popular"], self.result["deck"], self.result["best_rank"]), ({}, {}, {}))

    def test_every_card_counts_one_so_a_family_of_unranked_cards_is_a_pick(self):
        [pick] = self.result["next"]
        self.assertEqual((pick["unlocks"], pick["weight"], pick["deck_share"]), (2, 2.0, 1.0))  # the whole pool is playable after it

    def test_with_the_rank_the_cards_with_none_weigh_nothing(self):
        [pick] = coverage.analyze(POOL)["next"]
        self.assertEqual(pick["weight"], 1.0)  # the same pool: the card of rank 9000 counts and the one with no rank does not

    def test_the_report_names_the_format_and_says_there_is_no_play_data(self):
        text = audit.render(self.result, 40, "standard")
        self.assertIn("of 3 Standard-legal cards fully playable", text)
        self.assertIn("no play data for Standard", text)
        self.assertNotIn("EDHREC rank", text)
        self.assertNotIn("typical", text)

    def test_the_next_table_counts_cards_and_shares_the_pool(self):
        text = audit.render_next(self.result)
        self.assertIn("Pool playable after", text)
        self.assertIn("| 1 | Token copy of a creature or permanent | 2 | 100.0% | - | Copy Dog, Copy Cat |", text)

    def test_commander_keeps_its_report(self):
        text = audit.render(coverage.analyze(POOL), 40)
        self.assertIn("Commander-legal cards fully playable", text)
        self.assertIn("EDHREC rank", text)


class FetchPoolTests(unittest.TestCase):
    def test_the_search_is_for_the_cards_legal_in_the_format(self):
        urls = []

        def urlopen(request, timeout):
            urls.append(request.full_url)
            return io.StringIO(json.dumps({"data": [], "next_page": None}))
        with mock.patch.object(audit.urllib.request, "urlopen", urlopen), mock.patch.object(audit, "open", mock.mock_open(), create=True), \
                mock.patch.object(audit.os, "makedirs"):
            audit.fetch_pool("/nonexistent/standard_pool.json", format="standard")
        self.assertEqual(len(urls), 1)
        self.assertIn("legal%3Astandard", urls[0])
        self.assertNotIn("commander", urls[0])

    def test_a_format_scryfall_does_not_know_is_an_error_and_nothing_is_saved(self):
        # Scryfall's answer to `legal:nosuchformat`: the term ignored, with a warning, and every paper card returned.
        answer = {"data": POOL, "next_page": None, "total_cards": len(POOL),
                  "warnings": ["Invalid expression \u201clegal:nosuchformat\u201d was ignored. Unknown game format \u201cnosuchformat\u201d"]}
        saved = mock.mock_open()
        with mock.patch.object(audit.urllib.request, "urlopen", lambda request, timeout: io.StringIO(json.dumps(answer))), \
                mock.patch.object(audit, "open", saved, create=True), mock.patch.object(audit.os, "makedirs"):
            with self.assertRaises(ValueError) as caught:
                audit.fetch_pool("/nonexistent/nosuchformat_pool.json", format="nosuchformat")
            self.assertIn("Unknown game format", str(caught.exception))
            saved.assert_not_called()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(audit.main(["--format", "nosuchformat", "--pool", "/nonexistent/nosuchformat_pool.json"]), 2)
            self.assertIn("Scryfall did not search for the 'nosuchformat' format", err.getvalue())
            saved.assert_not_called()

    def test_a_known_format_with_no_warning_is_fetched(self):
        answer = {"data": POOL, "next_page": None, "total_cards": len(POOL)}
        with mock.patch.object(audit.urllib.request, "urlopen", lambda request, timeout: io.StringIO(json.dumps(answer))), \
                mock.patch.object(audit, "open", mock.mock_open(), create=True), mock.patch.object(audit.os, "makedirs"):
            self.assertEqual(audit.fetch_pool("/nonexistent/pauper_pool.json", format="pauper"), POOL)


if __name__ == "__main__":
    unittest.main()
