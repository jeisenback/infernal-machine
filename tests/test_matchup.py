import unittest
from unittest import mock

from infernal_machine.cards import Card, Deck
from infernal_machine.matchup import SeatLog, format_matchups, matchups, play_one, wilson

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
WALL = Card(name="Wall", mana_cost="{1}{G}", cmc=2, type_line="Creature — Wall", power="0", toughness="4")
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3")


def deck(spell, commander=BOSS):
    return Deck(commanders=[commander], main=[FOREST] * 40 + [spell] * 59, sideboard=[])


BEARS, WALLS = deck(BEAR), deck(WALL)


class WilsonTests(unittest.TestCase):
    def test_interval(self):
        low, high = wilson(5, 10)
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)
        self.assertEqual(wilson(0, 0), (0.0, 1.0))
        self.assertEqual(wilson(10, 10)[1], 1.0)
        self.assertGreater(wilson(10, 10)[0], 0.65)  # ten wins is not proof of a perfect deck


class SeatLogTests(unittest.TestCase):
    def test_flags(self):
        self.assertTrue(SeatLog(lands_early=2, casts_early=0).stumbled)
        self.assertFalse(SeatLog(lands_early=4, casts_early=0).stumbled)
        self.assertTrue(SeatLog(lands_early=4, casts_early=1).idle)
        self.assertFalse(SeatLog(lands_early=2, casts_early=0).idle)
        self.assertFalse(SeatLog().stumbled or SeatLog().idle)  # the game ended before the fifth turn


class PlayOneTests(unittest.TestCase):
    def test_a_game_finishes_and_is_logged(self):
        result = play_one([BEARS, WALLS], focus_seat=0, seed=1, max_turns=30)
        self.assertIsNone(result.error)
        self.assertGreater(result.turns, 4)
        self.assertGreater(result.logs[0].lands, 2)
        self.assertGreater(result.logs[0].casts, 0)
        self.assertEqual(result.winner is None, not result.reasons)  # a loser is recorded exactly when someone won

    def test_reproducible(self):
        a = play_one([BEARS, WALLS], 0, seed=5, max_turns=15)
        b = play_one([BEARS, WALLS], 0, seed=5, max_turns=15)
        self.assertEqual((a.winner, a.turns, a.starting_seat), (b.winner, b.turns, b.starting_seat))

    def test_a_slow_game_is_a_timeout_not_a_result(self):
        self.assertEqual(play_one([BEARS, WALLS], 0, seed=1, time_limit=0.0).error, "timeout")

    def test_a_crash_is_caught_with_its_message(self):
        with mock.patch("infernal_machine.matchup.Game.play", side_effect=ValueError("boom")):
            self.assertEqual(play_one([BEARS, WALLS], 0, seed=1).error, "ValueError: boom")


class MatchupTests(unittest.TestCase):
    def test_duels_against_each_opponent(self):
        records = matchups(BEARS, {"walls": WALLS, "mirror": BEARS}, games=4, max_turns=12)
        self.assertEqual([r.opponent for r in records], ["walls", "mirror"])
        for r in records:
            self.assertEqual(r.wins + r.losses + r.draws + r.errors, 4)
            self.assertEqual(r.fair_share, 0.5)
            self.assertEqual(r.on_play[1] + r.on_draw[1], r.games)

    def test_the_focus_deck_is_seated_in_turn(self):
        seats = []
        real = play_one
        with mock.patch("infernal_machine.matchup.play_one", side_effect=lambda decks, seat, *a, **k: seats.append(seat) or real(decks, seat, *a, **k)):
            matchups(BEARS, {"walls": WALLS}, games=4, max_turns=3)
        self.assertEqual(seats, [0, 1, 0, 1])

    def test_a_pod_draws_opponents_and_reads_against_a_fair_share(self):
        records = matchups(BEARS, {"walls": WALLS, "mirror": BEARS}, games=3, pod=4, max_turns=8)
        self.assertEqual(len(records), 1)
        self.assertEqual((records[0].opponent, records[0].fair_share), ("pod of 4", 0.25))
        self.assertEqual(records[0].wins + records[0].losses + records[0].draws + records[0].errors, 3)

    def test_workers_give_the_same_results(self):
        one = matchups(BEARS, {"walls": WALLS}, games=4, max_turns=10, workers=1)
        two = matchups(BEARS, {"walls": WALLS}, games=4, max_turns=10, workers=2)
        self.assertEqual([(r.wins, r.losses, r.draws, r.turns) for r in one], [(r.wins, r.losses, r.draws, r.turns) for r in two])

    def test_errors_are_counted_apart(self):
        records = matchups(BEARS, {"walls": WALLS}, games=3, max_turns=10, time_limit=0.0)
        self.assertEqual((records[0].games, records[0].errors, records[0].first_error), (0, 3, "timeout"))

    def test_report_text(self):
        text = format_matchups(matchups(BEARS, {"walls": WALLS}, games=4, max_turns=10), "bears")
        self.assertIn("walls", text)
        self.assertIn("win rate", text)
        self.assertIn("Overall", text)


if __name__ == "__main__":
    unittest.main()
