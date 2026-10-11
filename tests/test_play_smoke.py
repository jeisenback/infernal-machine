import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import play_smoke  # noqa: E402

from tests.test_rules_text_81 import real  # noqa: E402


def data(name, cost, type_line, text, power=None, toughness=None):
    return {"name": name, "layout": "normal", "mana_cost": cost, "cmc": float(len(cost) // 3), "type_line": type_line, "oracle_text": text,
            "power": power, "toughness": toughness, "legalities": {"commander": "legal"}, "id": name, "color_identity": []}


class SmokeTests(unittest.TestCase):
    def test_cards_that_play_are_counted(self):
        pool = [data("Bear Two", "{1}", "Creature — Bear", "", "2", "2"), data("Bolt", "{1}", "Instant", "Bolt deals 3 damage to any target."),
                data("Sap", "{1}", "Creature — Sap", "{1}: Draw a card.", "1", "1")]
        tried, cast, errors = play_smoke.check(pool)
        self.assertEqual((tried, cast, dict(errors)), (3, 3, {}))

    def test_the_other_half_of_a_card_is_played_too(self):
        front = {"name": "Giant", "type_line": "Creature \u2014 Giant", "mana_cost": "{2}{R}", "oracle_text": "", "power": "3", "toughness": "3"}
        adventure = {"name": "Insight", "type_line": "Instant \u2014 Adventure", "mana_cost": "{U}", "oracle_text": "Draw a card."}
        pool = [{"name": "Giant // Insight", "layout": "adventure", "cmc": 3.0, "legalities": {"commander": "legal"}, "id": "g",
                 "color_identity": [], "card_faces": [front, adventure]}]
        played = []
        original = play_smoke.play_other_half
        play_smoke.play_other_half = lambda card: played.append(card.alternate.name) or original(card)
        try:
            self.assertEqual(play_smoke.check(pool)[:2], (1, 1))
        finally:
            play_smoke.play_other_half = original
        self.assertEqual(played, ["Insight"])

    def test_a_card_with_no_other_half_has_nothing_to_play(self):
        self.assertFalse(play_smoke.play_other_half(real("Bear", "{1}", "Creature \u2014 Bear", "", "2", "2")))

    def test_cards_the_engine_does_not_understand_are_not_tried(self):
        pool = [data("Weird", "{1}", "Instant", "Frobnicate the widgets.")]
        self.assertEqual(play_smoke.check(pool)[:2], (0, 0))

    def test_a_card_that_raises_is_listed(self):
        original = play_smoke.play

        def boom(card):
            raise KeyError("missing")
        play_smoke.play = boom
        try:
            tried, cast, errors = play_smoke.check([data("Bear Two", "{1}", "Creature — Bear", "", "2", "2")])
        finally:
            play_smoke.play = original
        self.assertEqual((tried, dict(errors)), (1, {"KeyError: 'missing'": ["Bear Two"]}))

    def test_the_limit_stops_early(self):
        pool = [data(f"Bear {n}", "{1}", "Creature — Bear", "", "2", "2") for n in range(5)]
        self.assertEqual(play_smoke.check(pool, limit=2)[0], 2)


if __name__ == "__main__":
    unittest.main()
