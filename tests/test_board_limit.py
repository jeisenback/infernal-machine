"""A game whose board grows without limit is ended as a draw instead of never finishing (#377)."""

import unittest
from functools import partial
from unittest import mock

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import BOARD_LIMIT, BoardLimitReached, Game, Permanent
from infernal_machine.matchup import format_matchups, matchups, play_one

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
GOBLIN = Card(name="Goblin", type_line="Token Creature — Goblin", power="1", toughness="1", colors=("R",))
DECK = Deck([], [FOREST] * 30 + [BEAR] * 30, [])


def game(limit, seed=1):
    return Game([(BotPlayer("A", DECK), DECK), (BotPlayer("B", DECK), DECK)], seed=seed, board_limit=limit)


def permanents(g):
    return sum(len(s.battlefield) for s in g.seats)


class LimitTests(unittest.TestCase):
    def test_the_default_limit(self):
        self.assertEqual(BOARD_LIMIT, 300)
        self.assertEqual(game(BOARD_LIMIT).board_limit, 300)
        self.assertEqual(Game([(BotPlayer("A", DECK), DECK), (BotPlayer("B", DECK), DECK)]).board_limit, BOARD_LIMIT)

    def test_a_permanent_entering_past_the_limit_raises(self):
        g = game(5)
        for _ in range(5):
            g._enter(g.seats[0], Permanent(GOBLIN))
        self.assertEqual(permanents(g), 5)  # at the limit is allowed
        with self.assertRaises(BoardLimitReached):
            g._enter(g.seats[1], Permanent(GOBLIN))

    def test_every_players_permanents_count(self):
        g = game(6)
        for _ in range(3):
            g._enter(g.seats[0], Permanent(GOBLIN))
            g._enter(g.seats[1], Permanent(GOBLIN))
        with self.assertRaises(BoardLimitReached):
            g._enter(g.seats[0], Permanent(GOBLIN))

    def test_one_effect_that_makes_tokens_without_end_stops_at_the_limit(self):
        g = game(50)
        with self.assertRaises(BoardLimitReached):
            g.create_tokens(g.seats[0], GOBLIN, 10_000)
        self.assertEqual(permanents(g), 51)  # it did not make ten thousand

    def test_no_limit_means_no_stop(self):
        g = game(None)
        g.create_tokens(g.seats[0], GOBLIN, 500)
        self.assertEqual(permanents(g), 500)

    def test_moving_a_permanent_between_players_does_not_count_as_a_new_one(self):
        g = game(3)
        for _ in range(3):
            g._enter(g.seats[0], Permanent(GOBLIN))
        g.gain_control(g.seats[0].battlefield[0], g.seats[1])  # three permanents still
        self.assertEqual(permanents(g), 3)


class PlayTests(unittest.TestCase):
    def test_a_game_that_passes_the_limit_is_a_draw_with_a_reason(self):
        g = game(10)
        events = []
        forward = g.broadcast
        g.broadcast = lambda event, skip=None: (events.append(event), forward(event, skip))  # type: ignore[method-assign]
        winner = g.play(max_turns=60)
        self.assertIsNone(winner)
        self.assertEqual(g.ended, "board_limit")
        self.assertLess(g.turn, 60)
        over = [e for e in events if e["event"] == "game_over"]
        self.assertEqual(len(over), 1)
        self.assertEqual((over[0]["winner"], over[0]["reason"]), (None, "board_limit"))

    def test_a_game_under_the_limit_is_unchanged(self):
        under, none = game(10_000), game(None)
        a, b = under.play(max_turns=8), none.play(max_turns=8)
        self.assertEqual((a, under.ended, none.ended, under.turn), (b, None, None, none.turn))
        self.assertEqual([s.life for s in under.seats], [s.life for s in none.seats])


    def test_a_limit_hit_after_a_player_lost_is_still_a_draw(self):
        # The turn is cut off mid-way, so the game is not decided: a seat marked lost just before must not hand the other player a win.
        g = game(10)

        def cut_off(seat):
            g.seats[1].lost = True
            raise BoardLimitReached(10)

        with mock.patch.object(g, "_take_turn", cut_off):
            self.assertIsNone(g.play(max_turns=5))
        self.assertEqual(g.ended, "board_limit")


class MatchupTests(unittest.TestCase):
    def test_a_limited_game_is_a_draw_that_is_counted_and_reported(self):
        with mock.patch("infernal_machine.matchup.Game", partial(Game, board_limit=10)):
            result = play_one([DECK, DECK], 0, seed=1, max_turns=40)
            records = matchups(DECK, {"mirror": DECK}, games=3, max_turns=40)
        self.assertEqual((result.winner, result.ended, result.error), (None, "board_limit", None))
        record = records[0]
        self.assertEqual((record.board_limit, record.draws, record.wins, record.errors), (3, 3, 0, 0))
        text = format_matchups(records, "focus")
        self.assertIn(f"mirror: 3 game(s) ended as draws because the board passed {BOARD_LIMIT} permanents", text)

    def test_ordinary_games_have_nothing_to_report(self):
        record = matchups(DECK, {"mirror": DECK}, games=2, max_turns=6)[0]
        self.assertEqual(record.board_limit, 0)
        self.assertNotIn("board passed", format_matchups([record], "focus"))


if __name__ == "__main__":
    unittest.main()
