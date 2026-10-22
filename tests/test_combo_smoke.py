"""tools/combo_smoke.py: the pieces of Commander Spellbook combos put on a table and played with the first action the game offers.
The cards are the real Blightsteel Colossus and Chandra's Ignition (one cast ends the game), Storm-Kiln Artist and Haze of Rage (a loop
that only ends at the board limit), and probes."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import combo_smoke  # noqa: E402

from tests.helpers import real  # noqa: E402

BLIGHTSTEEL = real("Blightsteel Colossus", "{12}", "Artifact Creature — Phyrexian Golem",
                   "Trample, infect, indestructible\nIf Blightsteel Colossus would be put into a graveyard from anywhere, reveal Blightsteel "
                   "Colossus and shuffle it into its owner's library instead.", "11", "11")
IGNITION = real("Chandra's Ignition", "{3}{R}{R}", "Sorcery",
                "Target creature you control deals damage equal to its power to each other creature and each opponent.")
ARTIST = real("Storm-Kiln Artist", "{3}{R}", "Creature — Dwarf Shaman",
              "This creature gets +1/+0 for each artifact you control.\nMagecraft — Whenever you cast or copy an instant or sorcery spell, "
              "create a Treasure token. (It's an artifact with \"{T}, Sacrifice this token: Add one mana of any color.\")", "2", "2")
HAZE = real("Haze of Rage", "{1}{R}", "Sorcery", "Buyback {2} (You may pay an additional {2} as you cast this spell. If you do, put this card "
            "into your hand as it resolves.)\nCreatures you control get +1/+0 until end of turn.\nStorm (When you cast this spell, copy it "
            "for each spell cast before it this turn.)")
STUCK = real("Stuck Probe", "{2}", "Creature — Frog", "Frobnicate the widget whenever the moon is full.", "1", "1")
CARDS = {c.name: c for c in (BLIGHTSTEEL, IGNITION, ARTIST, HAZE, STUCK)}


def combo(*names, id="1"):
    return {"id": id, "cards": list(names), "produces": ["Probe result"]}


class CheckTests(unittest.TestCase):
    def run_check(self, *combos, only=None):
        return combo_smoke.check(list(combos), CARDS, steps=40, only=only)

    def test_a_combo_that_ends_the_game_says_so(self):
        tried, results, errors = self.run_check(combo("Blightsteel Colossus", "Chandra's Ignition"))
        self.assertEqual((tried, dict(errors)), (1, {}))
        self.assertTrue(results[0][1].endswith("game over"))

    def test_a_loop_that_runs_away_ends_at_the_board_limit_and_is_not_an_error(self):
        original = combo_smoke.table

        def small(pieces):
            game, mine = original(pieces)
            game.board_limit = 40
            return game, mine
        combo_smoke.table = small
        self.addCleanup(setattr, combo_smoke, "table", original)
        tried, results, errors = self.run_check(combo("Storm-Kiln Artist", "Haze of Rage"))
        self.assertEqual((tried, dict(errors)), (1, {}))
        self.assertTrue(results[0][1].endswith("ran to the board limit"))

    def test_a_combo_with_a_piece_the_engine_cannot_play_is_left_out(self):
        self.assertEqual(self.run_check(combo("Blightsteel Colossus", "Stuck Probe"))[0], 0)

    def test_a_combo_with_a_piece_not_in_the_card_data_is_left_out(self):
        self.assertEqual(self.run_check(combo("Blightsteel Colossus", "Nameless Card"))[0], 0)

    def test_a_combo_that_raises_is_listed_by_its_error(self):
        original = combo_smoke.play
        combo_smoke.play = lambda pieces, steps: (_ for _ in ()).throw(KeyError("boom"))
        self.addCleanup(setattr, combo_smoke, "play", original)
        tried, results, errors = self.run_check(combo("Blightsteel Colossus", "Chandra's Ignition"))
        self.assertEqual((tried, results, dict(errors)), (1, [], {"KeyError: 'boom'": ["Blightsteel Colossus + Chandra's Ignition"]}))

    def test_a_combo_that_takes_too_long_is_listed(self):
        original, limit = combo_smoke.play, combo_smoke.TIMEOUT_SECONDS
        combo_smoke.TIMEOUT_SECONDS = 1
        combo_smoke.play = lambda pieces, steps: [None for _ in iter(int, 1)]  # never ends
        self.addCleanup(setattr, combo_smoke, "play", original)
        self.addCleanup(setattr, combo_smoke, "TIMEOUT_SECONDS", limit)
        errors = self.run_check(combo("Blightsteel Colossus", "Chandra's Ignition"))[2]
        self.assertEqual(dict(errors), {"took more than 1 seconds": ["Blightsteel Colossus + Chandra's Ignition"]})

    def test_only_the_combos_using_the_named_card_are_tried(self):
        both = [combo("Blightsteel Colossus", "Chandra's Ignition", id="1"), combo("Storm-Kiln Artist", "Haze of Rage", id="2")]
        self.assertEqual(self.run_check(*both[:1], only="Chandra's Ignition")[0], 1)
        self.assertEqual(self.run_check(*both[:1], only="Haze of Rage")[0], 0)

    def test_a_piece_that_is_not_a_permanent_goes_to_the_hand_and_is_cast(self):
        game, mine = combo_smoke.table([BLIGHTSTEEL, IGNITION])
        self.assertIn(BLIGHTSTEEL.name, [p.card.name for p in mine.battlefield])
        self.assertEqual([c.name for c in mine.hand], [IGNITION.name])


class CachedCombosTests(unittest.TestCase):
    def test_every_combo_is_listed_once_whichever_deck_and_list_it_came_from(self):
        decks = {"a": {"included": [combo("X", "Y", id="1")], "almost": [combo("X", "Z", id="2")]},
                 "b": {"included": [combo("X", "Y", id="1")], "almost": []}}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "combos.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"format": 1, "decks": decks}, f)
            self.assertEqual(sorted(c["id"] for c in combo_smoke.cached_combos(path)), ["1", "2"])


if __name__ == "__main__":
    unittest.main()
