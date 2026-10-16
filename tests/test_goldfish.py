"""The deck alone against an idle seat, through the real engine (#390)."""

import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.game import Game
from infernal_machine.goldfish import (IDLE_LIFE, IdlePlayer, Pilot, format_gap, format_goldfish, goldfish, play_engine_game,
                                       unreadable_warning, _idle_deck)
from infernal_machine.simulate import play_games, simulate, summarize
from tests.helpers import real
from tests.test_compare import BEAR, BOSS, FOREST, ODD

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
LAVA_AXE = real("Lava Axe", "{4}{R}", "Sorcery", "Lava Axe deals 5 damage to target player or planeswalker.")


def forests(n=40):
    return Deck([], [FOREST] * n, [])


def bears():
    return Deck([], [FOREST] * 22 + [BEAR] * 18, [])


class IdleSeatTests(unittest.TestCase):
    def test_the_idle_seat_keeps_its_hand_and_never_acts(self):
        deck = bears()
        game = Game([(Pilot("deck", deck), deck), (IdlePlayer("idle", _idle_deck(deck)), _idle_deck(deck))], seed=1)
        game.seats[1].life = IDLE_LIFE
        game.play(max_turns=12)
        idle = game.seats[1]
        self.assertEqual(idle.battlefield, [], "it plays no land")
        self.assertGreater(len(idle.hand) + len(idle.graveyard), 7)
        self.assertLess(idle.life, IDLE_LIFE, "the deck's bears got through")

    def test_the_idle_deck_is_as_big_as_the_deck(self):
        self.assertEqual(len(_idle_deck(bears()).main), 40)
        self.assertEqual(_idle_deck(bears()).commanders, [])


class MeasurementTests(unittest.TestCase):
    def test_every_list_has_a_value_for_each_turn(self):
        run = play_engine_game(bears(), 0, 6, 0)
        for key in ("land_drops", "available", "spent", "stuck", "damage", "drawn", "permanents"):
            self.assertEqual(len(run[key]), 6, key)
        self.assertEqual(run["damage"], sorted(run["damage"]))
        self.assertGreater(run["damage"][-1], 0)
        self.assertIn("Grizzly Bears", run["cast"])

    def test_the_mana_is_counted_after_the_land_drop(self):
        for n in range(3):  # (the first player, the second, and either seed's shuffle: all lands, so a land every turn)
            run = play_engine_game(forests(), n, 5, 0)
            self.assertEqual(run["available"], [1, 2, 3, 4, 5])
            self.assertEqual(run["land_drops"], [True] * 5)

    def test_a_missed_land_drop_stays_missed(self):
        no_lands = Deck([], [BEAR] * 40, [])
        run = play_engine_game(no_lands, 0, 4, 0)
        self.assertEqual(run["land_drops"], [False] * 4)
        self.assertEqual(run["available"], [0] * 4)

    def test_a_missed_land_drop_is_not_made_up_for(self):
        few_lands = Deck([], [FOREST] * 8 + [BEAR] * 32, [])
        runs = [play_engine_game(few_lands, n, 8, 0)["land_drops"] for n in range(8)]
        self.assertTrue(any(False in drops for drops in runs), "some of these hands miss a drop")
        for drops in runs:
            self.assertEqual(drops, sorted(drops, reverse=True), "once False, always False")

    def test_the_opening_hand_is_the_one_that_was_kept(self):
        for n in range(4):
            run = play_engine_game(bears(), n, 2, 0)
            self.assertTrue(2 <= run["opening_lands"] <= 5 or run["mulligans"] > 0, (n, run["opening_lands"], run["mulligans"]))
            self.assertIn(run["mulligans"], range(0, 4))

    def test_the_damage_is_the_idle_seats_life_lost_not_its_life(self):
        self.assertLess(play_engine_game(bears(), 0, 8, 0)["damage"][-1], 100)

    def test_the_play_skips_the_first_draw(self):
        on_the_draw = play_engine_game(forests(), 0, 3, 0, on_the_play=False)["drawn"]
        on_the_play = play_engine_game(forests(), 0, 3, 0, on_the_play=True)["drawn"]
        self.assertEqual(on_the_draw, [1, 2, 3])
        self.assertEqual(on_the_play, [0, 1, 2])

    def test_what_a_spell_did_is_in_the_damage(self):
        deck = Deck([], [MOUNTAIN] * 30 + [LAVA_AXE] * 10, [])
        stats = goldfish(deck, games=6, turns=8, seed=0)
        model = simulate(deck, games=200, turns=8, seed=0)
        self.assertEqual(model.damage[8], 0, "the model does not read what Lava Axe says")
        self.assertGreaterEqual(stats.damage[8], 5)

    def test_a_commander_is_cast_from_the_command_zone(self):
        deck = Deck([BOSS], [FOREST] * 99, [])
        run = play_engine_game(deck, 0, 8, 0)
        self.assertIn("Boss", run["cast"])
        self.assertGreaterEqual(run["casts"]["Boss"], 1)
        self.assertEqual(run["seen"]["Boss"], 0)

    def test_the_same_game_plays_the_same_way(self):
        self.assertEqual(play_engine_game(bears(), 3, 6, 5), play_engine_game(bears(), 3, 6, 5))


class ReportTests(unittest.TestCase):
    def test_it_reports_in_the_shape_of_the_model(self):
        stats = goldfish(bears(), games=4, turns=5, seed=0)
        model = simulate(bears(), games=20, turns=5, seed=0)
        self.assertEqual((stats.games, stats.turns, stats.dropped), (4, 5, 0))
        self.assertEqual(set(stats.damage), set(model.damage))
        self.assertEqual({c.name for c in stats.cards}, {c.name for c in model.cards})
        self.assertEqual(sorted(stats.drawn), [1, 2, 3, 4, 5])
        self.assertEqual(model.drawn, {})
        text = format_goldfish(stats)
        self.assertIn("cards drawn  permanents", text)
        self.assertIn("against a seat that does nothing", text)
        self.assertNotIn("Card text is not played here", text)

    def test_a_game_that_cannot_finish_is_left_out_and_counted(self):
        stats = goldfish(bears(), games=3, turns=4, seed=0, time_limit=0)
        self.assertEqual((stats.games, stats.dropped), (0, 3))

    def test_the_gap_to_the_model_is_shown(self):
        engine = goldfish(bears(), games=3, turns=6, seed=0)
        model = simulate(bears(), games=50, turns=6, seed=0)
        text = format_gap(model, engine)
        self.assertIn("model", text)
        self.assertIn("damage by turn 6", text)
        self.assertIn("(50 games)", text)
        self.assertIn("(3 games)", text)

    def test_cards_the_engine_cannot_read_are_warned_about(self):
        self.assertIsNone(unreadable_warning(bears()))
        warning = unreadable_warning(Deck([], [FOREST] * 30 + [ODD] * 10, []))
        self.assertIn("Odd Spell", warning)
        self.assertIn("can't fully play", warning)

    def test_a_card_that_is_not_in_the_deck_is_left_out(self):
        runs = play_games(bears(), 5, 4, 0, False, False)
        runs[0]["seen"]["Stolen Card"] = 1
        self.assertNotIn("Stolen Card", [c.name for c in summarize(bears(), runs, 4).cards])

    def test_the_model_report_is_the_same_as_before_the_split(self):
        runs = play_games(bears(), 30, 6, 0, False, False)
        self.assertEqual(summarize(bears(), runs, 6), simulate(bears(), 30, 6, 0))


if __name__ == "__main__":
    unittest.main()
