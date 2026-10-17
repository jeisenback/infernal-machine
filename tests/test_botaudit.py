"""The audit of cards the bot sees and does not cast (#407)."""

import unittest
from collections import Counter

from infernal_machine.botaudit import HARD, AuditRow, MIN_SEEN, NEEDS_TARGET, ON_PURPOSE, audit, audit_rows, format_audit
from infernal_machine.cards import Card, Deck
from infernal_machine.goldfish import play_runs
from infernal_machine.simulate import simulate
from tests.helpers import real

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
RITUAL = real("Seething Song Lite", "{R}", "Instant", "Add {R}{R}{R}.")
WIPE = real("Doom Day", "{2}{R}", "Sorcery", "Destroy all creatures.")
BOLT = real("Zap Creature", "{R}", "Instant", "Zap Creature deals 3 damage to target creature.")
REANIMATE = real("Raise Lite", "{1}{R}", "Sorcery", "Return target creature card from your graveyard to the battlefield.")
BEAR = real("Cub", "{1}{R}", "Creature — Bear", "", "2", "2")
TOLL = real("Pay Toll", "{R}", "Creature — Imp", "As an additional cost to cast this spell, sacrifice a creature.", "1", "1")
BIG = real("Big Thing", "{4}{R}", "Creature — Giant", "", "5", "5")


def deck(*spells, lands=22):
    return Deck([], [MOUNTAIN] * lands + [c for card, n in spells for c in [card] * n], [])


def rows_for(d, games=30, turns=8, seed=0, model_games=300):
    rows, dropped = audit(d, games=games, turns=turns, seed=seed, workers=1, model_games=model_games)
    return {r.name: r for r in rows}, dropped


class ClassificationTests(unittest.TestCase):
    def test_a_ritual_is_held_on_purpose(self):
        rows, _ = rows_for(deck((RITUAL, 14), (BEAR, 6)))
        self.assertEqual(rows["Seething Song Lite"].verdict, ON_PURPOSE)
        self.assertIn("ritual", rows["Seething Song Lite"].on_purpose)
        self.assertEqual(rows["Seething Song Lite"].cast_when_seen, 0.0)

    def test_a_wipe_and_removal_are_held_on_purpose_against_an_empty_board(self):
        rows, _ = rows_for(deck((WIPE, 8), (BOLT, 8), (BEAR, 4)))
        self.assertIn("wipe", rows["Doom Day"].on_purpose)
        self.assertEqual(rows["Doom Day"].verdict, ON_PURPOSE)
        self.assertIn("removal", rows["Zap Creature"].on_purpose)

    def test_a_card_that_needs_a_graveyard_is_flagged_as_needing_one(self):
        rows, _ = rows_for(deck((REANIMATE, 14), (BEAR, 6)))
        self.assertTrue(rows["Raise Lite"].needs_target)
        self.assertEqual(rows["Raise Lite"].verdict, NEEDS_TARGET)

    def test_a_card_the_game_never_offers_is_not_a_choice_the_bot_made(self):
        rows, _ = rows_for(deck((TOLL, 16)), games=40)
        row = rows["Pay Toll"]
        self.assertEqual(row.verdict, "never offered")
        self.assertEqual(row.offered_turns, 0)
        self.assertGreater(row.model_cast_when_seen, 0.9, "the model, which ignores the cost, casts it")
        self.assertGreater(row.held_turns, 0)

    def test_the_turns_a_card_is_offered_and_not_cast_are_counted_and_a_cast_one_is_not(self):
        ritual = [r for r in play_runs(deck((RITUAL, 14), (BEAR, 6)), 10, 8, 0) if r]
        self.assertGreater(sum(r["passed_turns"].get("Seething Song Lite", 0) for r in ritual), 0, "offered every turn, never cast")
        self.assertGreater(sum(len(r["offered"].get("Seething Song Lite", ())) for r in ritual), 0)
        cubs = [r for r in play_runs(deck((BEAR, 16)), 10, 8, 0) if r]
        self.assertGreater(sum(len(r["offered"].get("Cub", ())) for r in cubs), 0)
        self.assertEqual(sum(r["passed_turns"].get("Cub", 0) for r in cubs), 0, "a Cub offered on a turn it was cast is not passed over")

    def test_a_card_that_is_cast_when_seen_is_not_listed(self):
        rows, _ = rows_for(deck((BEAR, 16)))
        self.assertNotIn("Cub", rows)

    def test_a_card_seen_too_rarely_is_not_judged(self):
        rows, _ = rows_for(deck((RITUAL, 1), (BEAR, 20)), games=6)
        self.assertNotIn("Seething Song Lite", rows)
        self.assertGreater(MIN_SEEN, 6)


class VerdictTests(unittest.TestCase):
    def row(self, model, offered):
        return AuditRow("X", 1, 20, 0.1, model, held_turns=100, offered_turns=offered, passed_turns=offered)

    def test_a_card_the_game_rarely_offers_is_the_games_when_the_model_casts_it_and_just_hard_when_it_does_not(self):
        self.assertEqual(self.row(0.9, 5).verdict, "never offered")
        self.assertEqual(self.row(0.15, 5).verdict, HARD)
        self.assertEqual(self.row(None, 5).verdict, HARD)

    def test_a_card_that_is_offered_and_passed_is_the_bots_choice(self):
        self.assertEqual(self.row(0.9, 60).verdict, "offered, passed over")


class RowTests(unittest.TestCase):
    def runs(self):
        return [r for r in play_runs(deck((BIG, 12), (BEAR, 6)), 14, 6, 0) if r is not None]

    def stage(self, runs, name, held, offered, passed_turns, passed=None):
        for run in runs:
            run["seen"][name] = 1
            run["cast"].pop(name, None)
            run["held"][name] = held
            run["offered"][name] = set(offered)
            run["passed_turns"][name] = passed_turns
            run["passed"][name] = Counter(passed or {})

    def test_offered_and_passed_turns_are_added_up_across_games_and_tell_what_was_cast_instead(self):
        d = deck((BIG, 12), (BEAR, 6))
        runs = self.runs()
        self.stage(runs, "Big Thing", 4, {2, 3, 4}, 3, {"cast Cub": 2, "cast nothing": 1})
        rows = {r.name: r for r in audit_rows(d, runs, 6, simulate(d, 200, 6, 0))}
        row = rows["Big Thing"]
        self.assertEqual((row.held_turns, row.offered_turns, row.passed_turns), (4 * len(runs), 3 * len(runs), 3 * len(runs)))
        self.assertEqual(row.passed_for, [("cast Cub", 2 * len(runs)), ("cast nothing", len(runs))])
        self.assertEqual(row.verdict, "offered, passed over")
        self.assertAlmostEqual(row.offered_rate, 0.75)

    def test_offered_often_and_cast_the_same_turn_is_not_a_pass(self):
        d = deck((BIG, 12), (BEAR, 6))
        runs = self.runs()
        self.stage(runs, "Big Thing", 4, {2, 3, 4}, 0)
        rows = {r.name: r for r in audit_rows(d, runs, 6, simulate(d, 200, 6, 0))}
        self.assertEqual(rows["Big Thing"].verdict, HARD)

    def test_the_bots_own_choices_come_first_and_what_it_holds_on_purpose_last(self):
        d = deck((BIG, 12), (BEAR, 6), (RITUAL, 6))
        runs = self.runs()
        self.stage(runs, "Big Thing", 4, {2, 3}, 2)
        self.stage(runs, "Cub", 4, {2, 3}, 0)
        self.stage(runs, "Seething Song Lite", 4, {2, 3}, 2)
        names = [r.name for r in audit_rows(d, runs, 6, simulate(d, 200, 6, 0))]
        self.assertEqual(names[0], "Big Thing")
        self.assertLess(names.index("Big Thing"), names.index("Seething Song Lite"))


class FormatTests(unittest.TestCase):
    def test_the_report_names_each_group_and_what_the_bot_did(self):
        d = deck((RITUAL, 14), (TOLL, 6))
        rows, dropped = audit(d, games=30, turns=8, seed=0, workers=1, model_games=200)
        text = format_audit(rows, 30, dropped, everything=True)
        self.assertIn("30 engine games.", text)
        self.assertIn("held on purpose (the bot's own rule):", text)
        self.assertIn("a ritual: never cast on its own", text)
        shown = format_audit(rows, 30, dropped)
        self.assertNotIn("held on purpose", shown.split('"offered" is')[0], "without --all they are not listed")

    def test_nothing_to_report_is_said(self):
        self.assertIn("None: every card", format_audit([], 30))

    def test_dropped_games_are_said(self):
        self.assertIn("2 game(s) could not be finished", format_audit([], 28, dropped=2))


if __name__ == "__main__":
    unittest.main()
