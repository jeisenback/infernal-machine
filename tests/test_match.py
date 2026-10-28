"""Best-of-three matches with sideboarding (#412)."""

import random
import unittest
from unittest import mock

from infernal_machine import match, matchup
from infernal_machine.cards import Card, Deck
from infernal_machine.matchup import GameResult, SeatLog
from tests.helpers import real

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
ALPHA = real("Alpha Bear", "{1}{G}", "Creature — Bear", "", "2", "2")
BETA = real("Beta Bear", "{1}{G}", "Creature — Bear", "", "2", "2")


def spell(name, cost, color="G"):
    return real(name, cost, "Creature — Bear", "", "1", "1")


BIG = spell("Big Drake", "{4}{G}{G}")
MID = spell("Mid Drake", "{2}{G}{G}")
SMALL = spell("Small Mouse", "{G}")
CHEAP_SIDE = spell("Cheap Side", "{G}")
PRICEY_SIDE = spell("Pricey Side", "{3}{G}")
OFF_COLOUR = spell("Off Colour", "{R}{R}")
FILLER = spell("Filler Mouse", "{G}")


def deck(main, side=()):
    return Deck([], list(main), list(side))


def standard(marker, extra=(), side=()):
    return deck([FOREST] * 20 + [marker] * 4 + list(extra) * 4, side)


class SideboardTests(unittest.TestCase):
    def test_cards_never_cast_come_out_most_expensive_first_and_cheap_ones_in(self):
        d = deck([FOREST] * 20 + [BIG] * 2 + [MID] * 2 + [SMALL] * 2, [CHEAP_SIDE, PRICEY_SIDE, OFF_COLOUR])
        new, swaps = match.sideboard(d, cast=["Small Mouse"], swaps=2)
        self.assertEqual(swaps, [("Big Drake", "Cheap Side"), ("Big Drake", "Pricey Side")])
        self.assertEqual(len(new.main), len(d.main))
        self.assertEqual(len(new.sideboard), len(d.sideboard))
        self.assertEqual([c.name for c in new.main].count("Big Drake"), 0)
        self.assertEqual([c.name for c in new.main].count("Cheap Side"), 1)
        self.assertEqual(sorted(c.name for c in new.sideboard), ["Big Drake", "Big Drake", "Off Colour"])

    def test_a_card_that_was_cast_stays(self):
        d = deck([FOREST] * 20 + [BIG, MID, SMALL] * 2, [CHEAP_SIDE])
        _, swaps = match.sideboard(d, cast=["Big Drake", "Mid Drake"], swaps=3)
        self.assertEqual(swaps, [("Small Mouse", "Cheap Side")])

    def test_only_sideboard_cards_in_the_colours_the_deck_plays_come_in(self):
        d = deck([FOREST] * 20 + [MID] * 4, [OFF_COLOUR])
        self.assertEqual(match.sideboard(d, cast=[])[1], [])

    def test_a_colour_with_too_few_symbols_is_not_played(self):
        splash = deck([FOREST] * 20 + [MID] * 2 + [spell("Red Splash", "{1}{R}"), spell("Red Splash Two", "{2}{R}")], [spell("Red Side", "{R}")])
        self.assertEqual(match.sideboard(splash, cast=[])[1], [], "two red symbols are a splash, not a color the deck plays")
        red = deck([FOREST] * 20 + [MID] * 2 + [spell("Red One", "{R}")] * 3, [spell("Red Side", "{R}")])
        self.assertEqual(len(match.sideboard(red, cast=["Mid Drake"])[1]), 1, "three red symbols are")

    def test_no_sideboard_or_nothing_to_take_out_is_no_change(self):
        d = deck([FOREST] * 20 + [BIG] * 4)
        self.assertIs(match.sideboard(d, cast=[])[0], d)
        d = deck([FOREST] * 20 + [BIG] * 4, [CHEAP_SIDE])
        self.assertIs(match.sideboard(d, cast=["Big Drake"])[0], d)

    def test_the_most_it_swaps_is_the_limit_and_the_registered_deck_is_left_alone(self):
        d = deck([FOREST] * 20 + [BIG] * 8, [CHEAP_SIDE] * 6)
        new, swaps = match.sideboard(d, cast=[])
        self.assertEqual(len(swaps), match.SWAPS)
        self.assertEqual(sum(c.name == "Big Drake" for c in d.main), 8)
        self.assertEqual(sum(c.name == "Big Drake" for c in new.main), 8 - match.SWAPS)

    def test_a_legal_deck_is_still_legal_after_sideboarding(self):
        """The swaps are one for one between the main deck and the sideboard, so the deck keeps its size and the copy limit, which counts
        the sideboard (#521)."""
        from infernal_machine.formats import STANDARD, deck_problems
        fillers = [spell(f"Filler {n}", "{G}") for n in "ABCDEF"]
        d = deck([FOREST] * 24 + [BIG] * 4 + [MID] * 4 + [SMALL] * 4 + fillers * 4, [CHEAP_SIDE] * 4 + [PRICEY_SIDE] * 4)
        self.assertEqual(deck_problems(d, STANDARD), [])
        new, swaps = match.sideboard(d, cast=[c.name for c in fillers])
        self.assertEqual(len(swaps), match.SWAPS)
        self.assertEqual((len(new.main), len(new.sideboard)), (60, 8))
        self.assertEqual(deck_problems(new, STANDARD), [])

    def test_ties_are_settled_by_name(self):
        a, b = spell("Aardvark", "{G}"), spell("Zebra", "{G}")
        d = deck([FOREST] * 20 + [a, b] + [MID] * 2, [spell("Yak Side", "{G}"), spell("Bat Side", "{G}")])
        self.assertEqual(match.sideboard(d, cast=["Mid Drake"], swaps=1)[1], [("Aardvark", "Bat Side")])


def scripted(outcomes, calls):
    """A play_one that plays no game: `outcomes` are which deck (0 or 1, by the marker card in it) wins each game, None for a draw."""
    def play(decks, focus_seat, seed, max_turns=60, time_limit=120.0, bots=None):
        k = len(calls)
        calls.append({"names": [sorted({c.name for c in d.main if c.name in ("Alpha Bear", "Beta Bear")}) for d in decks], "decks": decks,
                      "focus_seat": focus_seat, "seed": seed})
        seat_of = {name: s for s, d in enumerate(decks) for name in ("Alpha Bear", "Beta Bear") if any(c.name == name for c in d.main)}
        winner = None if outcomes[k] is None else seat_of["Alpha Bear" if outcomes[k] == 0 else "Beta Bear"]
        first = random.Random(seed).randrange(2)
        logs = {0: SeatLog(cast_names=["Mid Drake", "Alpha Bear", "Beta Bear"]), 1: SeatLog(cast_names=["Mid Drake", "Alpha Bear", "Beta Bear"])}
        return GameResult(focus_seat, winner=winner, turns=10, starting_seat=first, logs=logs, reasons={1 - winner: "life"} if winner is not None else {})
    return play


def lineup():
    alpha = deck([FOREST] * 20 + [ALPHA, MID, BIG, FILLER, FILLER], [CHEAP_SIDE] * 3)
    beta = deck([FOREST] * 20 + [BETA, MID, BIG, FILLER, FILLER], [CHEAP_SIDE] * 3)
    return [alpha, beta]


class PlayMatchTests(unittest.TestCase):
    def play(self, outcomes, focus=0, best_of=3, sideboarding=True, seed=5):
        calls: list[dict] = []
        with mock.patch.object(match, "play_one", scripted(outcomes, calls)):
            return match.play_match(lineup(), focus, seed, best_of=best_of, sideboarding=sideboarding), calls

    def test_two_wins_in_a_row_end_the_match(self):
        result, calls = self.play([0, 0, 1])
        self.assertEqual((result.winner, len(result.games), len(calls)), (0, 2, 2))
        self.assertEqual(match.game_record(result), (2, 0, 0))

    def test_a_split_goes_to_a_third_game(self):
        result, calls = self.play([0, 1, 1])
        self.assertEqual((result.winner, len(result.games)), (1, 3))
        self.assertEqual(match.game_record(result), (1, 2, 0))

    def test_the_winner_is_the_deck_whatever_seat_it_sat_in(self):
        for outcomes, expected in (([1, 1], 1), ([0, 0], 0)):
            result, calls = self.play(outcomes, seed=9)
            self.assertEqual(result.winner, expected)
            self.assertTrue(all(g.focus_seat == 0 for g in result.games), "every game is read with the tested deck as 0")

    def test_the_loser_of_a_game_plays_first_in_the_next(self):
        for seed in range(12):
            result, calls = self.play([0, 1, 0], seed=seed)
            for k in (1, 2):
                first_seat = random.Random(match.game_seed(seed, k)).randrange(2)
                loser_marker = "Beta Bear" if (0, 1, 0)[k - 1] == 0 else "Alpha Bear"
                self.assertEqual(calls[k]["names"][first_seat], [loser_marker], (seed, k))

    def test_after_a_draw_the_deck_that_started_it_starts_again(self):
        """CR 103.2: the player who chose in a drawn game chooses again, and the chooser plays first."""
        for seed in range(12):
            result, calls = self.play([None, None, 0], seed=seed)
            self.assertEqual(len(calls), 3)
            starters = [calls[k]["names"][random.Random(match.game_seed(seed, k) if k else seed).randrange(2)] for k in range(3)]
            self.assertEqual(starters[1], starters[0], (seed, "after the first draw"))
            self.assertEqual(starters[2], starters[1], (seed, "and after the second"))

    def test_the_first_game_seats_the_decks_as_given(self):
        result, calls = self.play([0, 0], focus=1)
        self.assertEqual(calls[0]["names"], [["Alpha Bear"], ["Beta Bear"]])
        self.assertEqual(calls[0]["focus_seat"], 1)
        self.assertEqual(result.focus_seat, 1)

    def test_a_drawn_game_gives_no_point(self):
        result, _ = self.play([None, 0, 0])
        self.assertEqual((result.winner, len(result.games)), (0, 3))
        self.assertEqual(match.game_record(result), (2, 0, 1))

    def test_all_draws_are_a_drawn_match_and_a_split_that_stays_split_is_too(self):
        self.assertIsNone(self.play([None, None, None])[0].winner)
        self.assertIsNone(self.play([0, None, 1])[0].winner)

    def test_the_games_before_a_crash_are_kept_and_the_match_is_an_error(self):
        calls: list[dict] = []
        base = scripted([0, 0, 0], calls)

        def crashing(decks, focus_seat, seed, *rest):
            game = base(decks, focus_seat, seed, *rest)
            if len(calls) == 2:
                game.error = "timeout"
            return game
        base = scripted([0, 1, 0], calls)
        with mock.patch.object(match, "play_one", crashing):
            result = match.play_match(lineup(), 0, 3)
        self.assertEqual(result.error, "timeout")
        self.assertEqual(len(result.games), 2)

    def test_sideboarding_changes_the_decks_of_the_next_game_and_off_does_not(self):
        _, calls = self.play([0, 1, 0], sideboarding=True)
        self.assertNotEqual(sorted(c.name for c in calls[1]["decks"][0].main), sorted(c.name for c in lineup()[0].main))
        self.assertIn("Cheap Side", [c.name for d in calls[1]["decks"] for c in d.main])
        _, calls = self.play([0, 1, 0], sideboarding=False)
        for d in calls[1]["decks"]:
            self.assertNotIn("Cheap Side", [c.name for c in d.main])

    def test_one_side_can_sideboard_and_the_other_keep_its_deck(self):
        for flags, side_a, side_b in (((True, False), True, False), ((False, True), False, True)):
            calls: list[dict] = []
            with mock.patch.object(match, "play_one", scripted([0, 1, 0], calls)):
                match.play_match(lineup(), 0, 5, best_of=3, sideboarding=flags)
            by_marker = {}
            for decks in (calls[1]["decks"],):
                for d in decks:
                    marker = "Alpha Bear" if any(c.name == "Alpha Bear" for c in d.main) else "Beta Bear"
                    by_marker[marker] = "Cheap Side" in [c.name for c in d.main]
            self.assertEqual((by_marker["Alpha Bear"], by_marker["Beta Bear"]), (side_a, side_b), flags)

    def test_the_first_game_is_played_with_the_decks_as_registered(self):
        _, calls = self.play([0, 0])
        self.assertEqual(sorted(c.name for c in calls[0]["decks"][0].main), sorted(c.name for c in lineup()[0].main))

    def test_the_next_game_uses_what_was_cast_in_the_last(self):
        _, calls = self.play([0, 0])
        for d in calls[1]["decks"]:
            names = [c.name for c in d.main]
            self.assertIn("Mid Drake", names, "cast in the last game: stays")
            self.assertNotIn("Big Drake", names, "never cast: out")
            self.assertEqual(names.count("Cheap Side"), 3, "Big Drake and the two fillers, none of them cast, were swapped for three")
            self.assertEqual(names.count("Filler Mouse"), 0)

    def test_a_match_is_between_two_decks(self):
        with self.assertRaises(ValueError):
            match.play_match([lineup()[0]] * 3, 0, 1)

    def test_one_game_is_the_same_game_as_a_single_game(self):
        calls: list[dict] = []
        with mock.patch.object(match, "play_one", scripted([0], calls)):
            match.play_match(lineup(), 0, 77, best_of=1)
        self.assertEqual(calls[0]["seed"], 77)
        self.assertEqual(match.game_seed(77, 0), 77)
        self.assertNotEqual(match.game_seed(77, 1), match.game_seed(77, 2))


class RealGamesTests(unittest.TestCase):
    def decks(self):
        a = standard(ALPHA, [MID], [CHEAP_SIDE] * 3)
        b = standard(BETA, [MID], [CHEAP_SIDE] * 3)
        return a, b

    def test_a_real_match_plays_two_or_three_games(self):
        a, b = self.decks()
        result = match.play_match([a, b], 0, 3, max_turns=25, time_limit=60.0)
        self.assertIsNone(result.error)
        self.assertIn(len(result.games), (2, 3))
        self.assertIn(result.winner, (0, 1, None))
        won, lost, drawn = match.game_record(result)
        self.assertEqual(won + lost + drawn, len(result.games))

    def test_matchups_with_best_of_report_matches_and_games(self):
        a, b = self.decks()
        records = matchup.matchups(a, {"them": b}, games=3, pod=2, seed=1, max_turns=25, best_of=3)
        record = records[0]
        self.assertEqual((record.best_of, record.games + record.errors), (3, 3))
        self.assertGreaterEqual(sum(record.game_record), 2 * record.games)
        self.assertEqual(record.wins + record.losses + record.draws, record.games)
        text = matchup.format_matchups(records, "mine")
        self.assertIn("Best of 3 with sideboarding", text)
        self.assertIn("games", text)

    def test_a_single_game_matchup_is_unchanged(self):
        a, b = self.decks()
        record = matchup.matchups(a, {"them": b}, games=2, pod=2, seed=1, max_turns=25)[0]
        self.assertEqual((record.best_of, record.game_record), (1, (0, 0, 0)))
        self.assertNotIn("Best of", matchup.format_matchups([record], "mine"))

    def test_best_of_is_for_duels(self):
        a, b = self.decks()
        with self.assertRaises(ValueError):
            matchup.plan_games(a, {"them": b}, 2, 4, 1, 25, 60.0, best_of=3)

    def test_tasks_carry_the_best_of_only_when_it_is_above_one(self):
        a, b = self.decks()
        self.assertEqual(len(matchup.plan_games(a, {"x": b}, 1, 2, 1, 25, 60.0)[0][1][0]), 6)
        self.assertEqual(matchup.plan_games(a, {"x": b}, 1, 2, 1, 25, 60.0, best_of=3)[0][1][0][6], 3)


class CastNamesTests(unittest.TestCase):
    def test_a_game_records_what_each_seat_cast(self):
        a, b = standard(ALPHA, [MID]), standard(BETA, [MID])
        game = matchup.play_one([a, b], 0, 11, max_turns=20, time_limit=60.0)
        self.assertEqual(game.logs[0].casts, len(game.logs[0].cast_names))
        self.assertTrue(set(game.logs[0].cast_names) <= {"Alpha Bear", "Mid Drake"})
        self.assertTrue(set(game.logs[1].cast_names) <= {"Beta Bear", "Mid Drake"})


if __name__ == "__main__":
    unittest.main()
