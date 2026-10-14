import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.simulate import game_value, play_games
from infernal_machine.tune import BLANK, format_tuning, tune

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
OGRE = Card(name="Hill Giant", mana_cost="{3}{G}", cmc=4, type_line="Creature — Giant", power="3", toughness="3")
BLUE = Card(name="Counterspell", mana_cost="{U}{U}", cmc=2, type_line="Instant")
COMMANDER = Card(name="Boss", mana_cost="{2}{G}", cmc=3, type_line="Legendary Creature — Elf", power="3", toughness="3")


def deck(*cards, commanders=()):
    return Deck(commanders=list(commanders), main=list(cards), sideboard=[])


MIXED = deck(*[FOREST] * 24, *[BEAR] * 12, *[OGRE] * 12, *[BLUE] * 12)


class TuneTests(unittest.TestCase):
    def test_reproducible(self):
        a, b = tune(MIXED, games=60, turns=5, seed=1), tune(MIXED, games=60, turns=5, seed=1)
        self.assertEqual(a, b)

    def test_uncastable_cards_add_nothing_and_are_flagged(self):
        report = tune(MIXED, games=200, turns=6, seed=1)
        weakest = report.cards[0]
        self.assertEqual(weakest.name, "Counterspell")
        self.assertLess(abs(weakest.value.delta), 0.5)  # not exactly 0: a blank has no cost, so a mulligan bottoms different cards
        self.assertEqual(weakest.note, "rarely cast when drawn")
        good = {c.name: c for c in report.cards}
        self.assertGreater(good["Grizzly Bears"].value.delta, 0)
        self.assertTrue(good["Hill Giant"].value.clear)

    def test_baseline_matches_the_simulation(self):
        report = tune(MIXED, games=80, turns=5, seed=2)
        runs = play_games(MIXED, 80, 5, 2, False, False)
        self.assertAlmostEqual(report.baseline, sum(game_value(r) for r in runs) / 80, places=2)

    def test_replaying_without_a_card_matches_a_full_rerun(self):
        # The shortcut (replay only the games where it was drawn) must give the same answer as replaying every game.
        report = tune(MIXED, games=80, turns=5, seed=3)
        blanked = deck(*[BLANK if c.name == "Hill Giant" else c for c in MIXED.main])
        full = [game_value(a) - game_value(b) for a, b in zip(play_games(MIXED, 80, 5, 3, False, False), play_games(blanked, 80, 5, 3, False, False))]
        got = {c.name: c for c in report.cards}["Hill Giant"]
        self.assertAlmostEqual(got.value.delta, sum(full) / 80, places=2)

    def test_a_better_land_count_shows_up(self):
        starved = deck(*[FOREST] * 14, *[OGRE] * 46)
        report = tune(starved, games=150, turns=6, seed=1)
        self.assertGreater(report.lands[1].delta, 0)
        self.assertGreater(report.lands[2].delta, report.lands[1].delta)

    def test_candidates_replace_the_weakest_card(self):
        report = tune(MIXED, games=150, turns=6, seed=1, candidates=[OGRE, Card(name="Wall", mana_cost="{G}", cmc=1, type_line="Creature", power="0", toughness="4"),
                                                                    BEAR])
        names = [name for name, _, _ in report.swaps]
        self.assertEqual(names, ["Wall"])
        self.assertEqual(report.skipped, [("Hill Giant", "already at 4 copies"), ("Grizzly Bears", "already at 4 copies")])  # Grizzly Bears and Hill Giant are already in the deck
        self.assertEqual(report.swaps[0][1], "Counterspell")

    def test_a_commander_deck_only_tries_legal_candidates(self):
        green = Card(name="Green Boss", mana_cost="{G}", cmc=1, type_line="Legendary Creature — Elf", color_identity=("G",))
        off_color = Card(name="Blue Bear", mana_cost="{1}{U}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("U",))
        banned = Card(name="Banned Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",), commander_legal=False)
        fine = Card(name="Fine Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))
        report = tune(deck(*[FOREST] * 40, *[BEAR] * 59, commanders=[green]), games=30, turns=4, seed=1, candidates=[off_color, banned, fine, BEAR])
        self.assertEqual([n for n, _, _ in report.swaps], ["Fine Bear"])
        self.assertEqual(dict(report.skipped), {"Blue Bear": "outside the commander's color identity (U)", "Banned Bear": "not legal in Commander",
                                                "Grizzly Bears": "already in the deck"})

    def test_a_deck_without_a_commander_allows_up_to_four_copies(self):
        three = deck(*[FOREST] * 24, *[BEAR] * 33, *[OGRE] * 3)
        report = tune(three, games=30, turns=4, seed=1, candidates=[OGRE, FOREST])
        self.assertEqual({n for n, _, _ in report.swaps}, {"Hill Giant", "Forest"})  # a fourth copy is fine, and a basic land has no limit

    def test_the_commander_is_measured_too(self):
        report = tune(deck(*[FOREST] * 99, commanders=[COMMANDER]), games=40, turns=5, seed=1)
        boss = next(c for c in report.cards if c.name == "Boss")
        self.assertGreater(boss.value.delta, 0)

    def test_report_text(self):
        text = format_tuning(tune(MIXED, games=40, turns=4, seed=1, candidates=[BEAR]))
        self.assertIn("Counterspell", text)
        self.assertIn("Land count", text)


if __name__ == "__main__":
    unittest.main()
