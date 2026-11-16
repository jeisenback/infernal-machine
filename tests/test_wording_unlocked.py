"""Issue #809: `wording_unlocked`, the check for a wording that unlocks many cards, and `tools/add_real_cards.py`, which puts their real
Oracle text in the fixture."""

import os
import sys
import unittest

from tests.helpers import wording_unlocked

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import add_real_cards  # noqa: E402


def result_of(names):
    """The failures and errors of a test that calls `wording_unlocked` with `names` (subTests count one each)."""
    class Probe(unittest.TestCase):
        def runTest(self):
            wording_unlocked(self, names)
    result = unittest.TestResult()
    Probe().run(result)
    return result.failures + result.errors


class WordingUnlockedTests(unittest.TestCase):
    def test_fully_playable_real_cards_pass(self):
        self.assertEqual(result_of(["Clone", "Treetop Village"]), [])

    def test_a_card_missing_from_the_fixture_fails_and_says_how_to_add_it(self):
        (failure,) = result_of(["Not A Real Card Name"])
        self.assertIn("add_real_cards", failure[1])

    def test_a_card_that_cannot_be_cast_or_played_fails(self):
        import play_smoke
        original = play_smoke.play
        play_smoke.play = lambda card: False
        try:
            (failure,) = result_of(["Clone"])
        finally:
            play_smoke.play = original
        self.assertIn("no way to cast or play it", failure[1])

    def test_a_card_with_an_unsupported_line_fails(self):
        from tests.real import DATA
        unsupported = DATA["unsupported_cards"][0]["name"]
        self.assertEqual(len(result_of([unsupported])), 1)


class AddRealCardsTests(unittest.TestCase):
    POOL = [{"name": "Cenote Scout", "mana_cost": "{G}", "type_line": "Creature — Merfolk Scout", "oracle_text": "When this creature "
             "enters, it explores.", "power": "1", "toughness": "1", "colors": ["G"]},
            {"name": "Said // Done", "card_faces": [{}, {}]}]

    def fixture(self):
        return {"source": "test", "cards": [{"name": "Clone"}]}

    def test_a_card_is_copied_with_the_fixtures_fields(self):
        fixture = self.fixture()
        added, problems = add_real_cards.add(["Cenote Scout"], self.POOL, fixture)
        self.assertEqual((added, problems, fixture["cards"][-1]),
                         (["Cenote Scout"], [], {"name": "Cenote Scout", "mana_cost": "{G}", "type_line": "Creature — Merfolk Scout",
                                                 "oracle_text": "When this creature enters, it explores.", "power": "1", "toughness": "1",
                                                 "colors": ["G"]}))

    def test_a_card_already_there_is_left_alone(self):
        fixture = self.fixture()
        self.assertEqual(add_real_cards.add(["Clone"], self.POOL + [{"name": "Clone"}], fixture), ([], []))
        self.assertEqual(fixture["cards"], [{"name": "Clone"}])

    def test_an_unknown_or_two_faced_card_is_refused_and_nothing_is_added(self):
        fixture = self.fixture()
        added, problems = add_real_cards.add(["Cenote Scout", "Nobody", "Said // Done"], self.POOL, fixture)
        self.assertEqual((added, len(problems), fixture["cards"]), ([], 2, [{"name": "Clone"}]))


if __name__ == "__main__":
    unittest.main()
