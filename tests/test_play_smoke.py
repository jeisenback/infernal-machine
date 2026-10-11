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
