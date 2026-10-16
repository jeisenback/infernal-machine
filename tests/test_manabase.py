"""Mana base advice: sources of each color a deck needs, from the hypergeometric distribution, and the sources it has (#375)."""

import unittest
from fractions import Fraction
from itertools import combinations
from math import comb

from infernal_machine.cards import Card, Deck
from infernal_machine.manabase import (analyze_mana_base, cards_seen, format_mana_base, land_sources, p_at_least, pips,
                                       sources_needed)
from infernal_machine.tune import format_tuning, tune
from tests.helpers import real

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
DUAL = Card(name="Hinterland Harbor", type_line="Land", produced_mana=("G", "U"), oracle_text="{T}: Add {G} or {U}.")
TOWER = Card(name="Command Tower", type_line="Land", produced_mana=("W", "U", "B", "R", "G"),
             oracle_text="{T}: Add one mana of any color in your commander's color identity.")
WILDS = real("Evolving Wilds", "", "Land", "{T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.")
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G", "U"))
SIGNET = Card(name="Signet", mana_cost="{2}", cmc=2, type_line="Artifact", oracle_text="{T}: Add one mana of any color.", produced_mana=("G", "U"))


def spell(name, cost, cmc):
    return Card(name=name, mana_cost=cost, cmc=cmc, type_line="Creature — Elf", power="1", toughness="1")


def deck(*main, commanders=()):
    return Deck(list(commanders), list(main), [])


class HypergeometricTests(unittest.TestCase):
    def test_it_matches_counting_every_hand(self):
        # 10 cards, 4 of them sources, 3 drawn: count the hands with at least 2 sources directly
        cards = [True] * 4 + [False] * 6
        hands = list(combinations(range(10), 3))
        good = sum(1 for hand in hands if sum(cards[i] for i in hand) >= 2)
        self.assertEqual(Fraction(good, len(hands)), Fraction(sum(comb(4, k) * comb(6, 3 - k) for k in (2, 3)), comb(10, 3)))
        self.assertAlmostEqual(p_at_least(10, 4, 3, 2), good / len(hands))

    def test_a_single_source_among_seven_of_sixty(self):
        self.assertAlmostEqual(p_at_least(60, 14, 7, 1), 1 - comb(46, 7) / comb(60, 7))

    def test_the_edges(self):
        self.assertEqual(p_at_least(60, 0, 7, 1), 0.0)
        self.assertEqual(p_at_least(60, 20, 7, 0), 1.0)
        self.assertAlmostEqual(p_at_least(60, 60, 7, 7), 1.0)
        self.assertEqual(p_at_least(60, 3, 7, 4), 0.0)  # more sources asked for than there are

    def test_more_sources_never_lowers_the_odds(self):
        odds = [p_at_least(99, s, 10, 2) for s in range(0, 60)]
        self.assertEqual(odds, sorted(odds))

    def test_sources_needed_is_the_smallest_that_reaches_the_target(self):
        for library, seen, need in ((60, 7, 1), (60, 9, 2), (99, 11, 2), (99, 12, 3)):
            s = sources_needed(library, seen, need, 0.9)
            assert s is not None
            self.assertGreaterEqual(p_at_least(library, s, seen, need), 0.9)
            self.assertLess(p_at_least(library, s - 1, seen, need), 0.9)

    def test_a_higher_target_needs_more_and_more_pips_need_more(self):
        self.assertGreater(sources_needed(99, 10, 1, 0.95), sources_needed(99, 10, 1, 0.90))
        self.assertGreater(sources_needed(99, 10, 2), sources_needed(99, 10, 1))

    def test_more_pips_than_cards_seen_cannot_be_met(self):
        self.assertIsNone(sources_needed(99, 2, 3))

    def test_cards_seen(self):
        self.assertEqual([cards_seen(t, True) for t in (1, 2, 4)], [7, 8, 10])  # no draw on turn one
        self.assertEqual([cards_seen(t, False) for t in (1, 2, 4)], [8, 9, 11])


class CostTests(unittest.TestCase):
    def test_pips_count_single_color_symbols(self):
        self.assertEqual(pips(spell("A", "{1}{W}{W}", 3)), {"W": 2})
        self.assertEqual(pips(spell("B", "{G}{U}", 2)), {"G": 1, "U": 1})
        self.assertEqual(pips(spell("C", "{3}", 3)), {})

    def test_hybrid_and_phyrexian_symbols_are_not_counted(self):
        self.assertEqual(pips(spell("D", "{R/W}{R/W}{1}", 3)), {})
        self.assertEqual(pips(spell("E", "{1}{W/P}{G}", 2)), {"G": 1})


class SourceTests(unittest.TestCase):
    def test_basics_and_duals(self):
        counts = land_sources(deck(*[FOREST] * 8, *[ISLAND] * 6, *[DUAL] * 3, WASTES))
        self.assertEqual((counts["G"], counts["U"], counts["W"]), (11, 9, 0))

    def test_a_commander_limits_what_an_any_color_land_makes(self):
        counts = land_sources(deck(FOREST, ISLAND, TOWER, commanders=[BOSS]))  # the commander is green and blue
        self.assertEqual({c: counts[c] for c in "WUBRG"}, {"W": 0, "U": 2, "B": 0, "R": 0, "G": 2})

    def test_a_land_that_fetches_a_basic_counts_for_the_colors_of_the_basics_in_the_deck(self):
        counts = land_sources(deck(FOREST, FOREST, ISLAND, WILDS))
        self.assertEqual((counts["G"], counts["U"], counts["R"]), (3, 2, 0))
        self.assertEqual(land_sources(deck(WILDS))["G"], 0)  # no basics to find

    def test_only_lands_count_and_the_rocks_are_reported_apart(self):
        base = analyze_mana_base(deck(*[FOREST] * 10, SIGNET, BEAR, BEAR))
        assert base is not None
        green = base.colors[0]
        self.assertEqual((green.have, green.rocks), (10, 1))


class AnalysisTests(unittest.TestCase):
    CHEAP = [spell(f"One {i}", "{G}", 1) for i in range(8)]  # eight cheap green spells
    HARD = spell("Hard", "{1}{G}{G}{G}", 4)  # one spell that wants a great deal

    def test_a_colorless_deck_has_no_mana_base(self):
        self.assertIsNone(analyze_mana_base(deck(WASTES, spell("Rock", "{2}", 2))))

    def test_defaults_follow_the_format(self):
        standard = analyze_mana_base(deck(*[FOREST] * 24, *[BEAR] * 36))
        commander = analyze_mana_base(deck(*[FOREST] * 38, *[BEAR] * 61, commanders=[BOSS]))
        assert standard is not None and commander is not None
        self.assertEqual((standard.on_the_play, standard.slack, standard.library), (True, 0, 60))
        self.assertEqual((commander.on_the_play, commander.slack, commander.library), (False, 2, 99))

    def test_a_spell_is_cast_by_its_mana_value_plus_the_slack_and_needs_the_odds_for_that_turn(self):
        base = analyze_mana_base(deck(*[FOREST] * 24, *[BEAR] * 36), slack=1, on_the_play=True)
        assert base is not None
        driver = base.colors[0].driver
        assert driver is not None
        self.assertEqual((driver.turn, driver.pips), (3, 1))  # mana value 2 plus one turn of slack
        self.assertEqual(driver.sources, sources_needed(60, cards_seen(3, True), 1))
        self.assertEqual(base.colors[0].needed, driver.sources)  # one spell, so it sets the number

    def test_the_number_covers_most_spells_while_the_hardest_is_named(self):
        main = [*[FOREST] * 24, *self.CHEAP, self.HARD, *[BEAR] * 27]
        base = analyze_mana_base(deck(*main), on_the_play=True, slack=0)
        assert base is not None
        green = base.colors[0]
        assert green.driver is not None
        self.assertEqual(green.driver.card, "Hard")
        self.assertGreater(green.driver.sources, green.needed)  # the hardest spell does not set the number
        self.assertEqual(green.spells, 8 + 1 + 27)
        wide = analyze_mana_base(deck(*main), on_the_play=True, slack=0, coverage=1.0)
        assert wide is not None
        self.assertEqual(wide.colors[0].needed, green.driver.sources)  # covering every spell takes the hardest

    def test_x_spells_do_not_set_the_number(self):
        x_spell = spell("Hydra", "{X}{G}{G}{G}", 3)
        base = analyze_mana_base(deck(*[FOREST] * 24, x_spell, *[BEAR] * 35), on_the_play=True, slack=0)
        assert base is not None
        self.assertEqual(base.colors[0].driver.card, "Grizzly Bears")  # type: ignore[union-attr]
        self.assertEqual(base.colors[0].pips, 3 + 35)  # (its pips are still counted)

    def test_a_color_of_only_x_spells_asks_for_nothing(self):
        only_x = analyze_mana_base(deck(*[FOREST] * 24, *[spell("Hydra", "{X}{G}{G}", 2)] * 36))
        assert only_x is not None
        self.assertEqual((only_x.colors[0].needed, only_x.colors[0].driver), (0, None))

    def test_the_commander_counts_like_a_spell(self):
        base = analyze_mana_base(deck(*[FOREST] * 38, *[BEAR] * 61, commanders=[BOSS]))
        assert base is not None
        self.assertEqual(base.colors[0].spells, 62)

    def test_short_and_hardest_short(self):
        main = [*[FOREST] * 12, *[BEAR] * 48]
        green = analyze_mana_base(deck(*main), slack=0, on_the_play=True).colors[0]  # type: ignore[union-attr]
        self.assertEqual((green.have, green.short), (12, 3))  # a two-drop wants 15 sources in 60 cards on the play
        self.assertEqual(green.hardest_short, green.short)
        rich = analyze_mana_base(deck(*[FOREST] * 30, *[BEAR] * 30), slack=0, on_the_play=True).colors[0]  # type: ignore[union-attr]
        self.assertEqual((rich.short, rich.hardest_short), (0, 0))

    def test_two_colors_are_two_lines(self):
        blue = spell("Blue One", "{U}", 1)
        base = analyze_mana_base(deck(*[FOREST] * 12, *[ISLAND] * 12, BEAR, blue, *[BEAR] * 34))
        assert base is not None
        self.assertEqual([line.color for line in base.colors], ["U", "G"])  # in WUBRG order
        self.assertEqual([line.have for line in base.colors], [12, 12])


class ReportTests(unittest.TestCase):
    def test_the_text_says_what_is_short(self):
        text = format_mana_base(analyze_mana_base(deck(*[FOREST] * 12, *[BEAR] * 48)))  # type: ignore[arg-type]
        self.assertIn("short by", text)
        self.assertIn("Green", text)
        self.assertIn("Grizzly Bears ({1}{G}", text)
        self.assertIn("(no mulligans)", text)
        self.assertIn("no mulligans", text)

    def test_enough_and_the_hardest_spell_being_short(self):
        base = analyze_mana_base(deck(*[FOREST] * 24, *AnalysisTests.CHEAP, AnalysisTests.HARD, *[BEAR] * 27), on_the_play=True, slack=0)
        assert base is not None
        green = base.colors[0]
        self.assertEqual((green.short, green.hardest_short > 0), (0, True))
        self.assertIn(f"enough (hardest short by {green.hardest_short})", format_mana_base(base))

    def test_rocks_are_mentioned(self):
        text = format_mana_base(analyze_mana_base(deck(*[FOREST] * 24, SIGNET, *[BEAR] * 35)))  # type: ignore[arg-type]
        self.assertIn("Not counted as sources: mana rocks and creatures that make Green 1", text)


class TuneTests(unittest.TestCase):
    def test_the_tuning_report_carries_the_mana_base_and_the_goldfish_stuck_rate(self):
        report = tune(deck(*[FOREST] * 14, *[BEAR] * 46), games=40, turns=6, seed=1)
        assert report.mana_base is not None
        self.assertEqual(sorted(report.mana_base.stuck), [3, 5])
        self.assertTrue(all(0 <= share <= 1 for share in report.mana_base.stuck.values()))
        text = format_tuning(report)
        self.assertIn("Mana base:", text)
        self.assertIn("In the goldfish a spell was stuck on colors", text)

    def test_only_the_turns_that_were_played_are_reported(self):
        report = tune(deck(*[FOREST] * 24, *[BEAR] * 36), games=20, turns=4, seed=1)
        assert report.mana_base is not None
        self.assertEqual(sorted(report.mana_base.stuck), [3])

    def test_a_colorless_deck_has_no_section(self):
        report = tune(deck(*[WASTES] * 24, *[spell("Rock", "{2}", 2)] * 36), games=20, turns=4, seed=1)
        self.assertIsNone(report.mana_base)
        self.assertNotIn("Mana base:", format_tuning(report))


if __name__ == "__main__":
    unittest.main()
