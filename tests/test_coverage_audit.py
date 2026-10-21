"""The coverage audit tool (tools/coverage_audit.py): its numbers for a handful of cards, and the pool cache."""

import importlib.util
import json
import os
import tempfile
import unittest

from infernal_machine import coverage

_spec = importlib.util.spec_from_file_location("coverage_audit", os.path.join(os.path.dirname(__file__), "..", "tools", "coverage_audit.py"))
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def card(name, type_line, text, rank=None, **more):
    return {"name": name, "type_line": type_line, "oracle_text": text, "mana_cost": more.pop("mana_cost", ""), "cmc": 0,
            **({"edhrec_rank": rank} if rank else {}), **more}


POOL = [
    card("Plain Forest", "Basic Land — Forest", "({T}: Add {G}.)", rank=1, produced_mana=["G"]),
    card("Quick Bear", "Creature — Bear", "Trample", rank=2, mana_cost="{1}{G}", power="2", toughness="2"),
    card("Odd Bear", "Creature — Bear", "Whenever the moon is full, frobnicate the widget.", rank=3, mana_cost="{1}{G}", power="2", toughness="2"),
    card("Odd Cat", "Creature — Cat", "Whenever the moon is full, frobnicate the widget.", rank=4, mana_cost="{1}{G}", power="1", toughness="1"),
    card("Odd Elk", "Creature — Elk", "Whenever the moon is full, frobnicate the widget.\nShroud", rank=5, mana_cost="{G}", power="1", toughness="1"),
    card("Unranked Sorcery", "Sorcery", "Draw a card.", mana_cost="{1}"),
]


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.result = coverage.analyze(POOL)

    def test_it_counts_the_playable_cards(self):
        self.assertEqual((self.result["total"], self.result["playable"]), (6, 3))

    def test_it_counts_by_card_type(self):
        self.assertEqual(self.result["by_type"]["Creature"], [4, 1])
        self.assertEqual(self.result["by_type"]["Land"], [1, 1])
        self.assertEqual(self.result["by_type"]["Sorcery"], [1, 1])

    def test_it_weights_by_popularity(self):
        self.assertEqual(self.result["popular"][100], (2, 5), "of the five ranked cards, the Forest and the Bear are playable")

    def test_the_same_unsupported_line_on_several_cards_is_one_group_most_played_first(self):
        group = self.result["shapes"]["Whenever the moon is full, frobnicate the widget."]
        self.assertEqual(group, ["Odd Bear", "Odd Cat", "Odd Elk"])

    def test_a_card_with_one_gap_counts_as_a_single_gap(self):
        self.assertEqual(self.result["one_gap"], 3)
        self.assertEqual(self.result["only_gap"]["Whenever the moon is full, frobnicate the widget."], ["Odd Bear", "Odd Cat", "Odd Elk"])

    def test_a_card_the_report_cannot_read_is_listed_not_fatal(self):
        broken = coverage.analyze([{"name": "Broken", "cmc": "not a number"}])
        self.assertEqual((broken["total"], broken["crashes"]), (0, ["Broken: ValueError"]))


class ShapeTests(unittest.TestCase):
    def test_numbers_and_mana_symbols_are_blurred(self):
        self.assertEqual(coverage.shape("Madness {1}{R}"), "Madness {M}{M}")
        self.assertEqual(coverage.shape("Toxic 2"), "Toxic N")
        self.assertEqual(coverage.shape("Bushido three"), "Bushido N")

    def test_long_lines_are_cut(self):
        self.assertEqual(len(coverage.shape("x" * 300)), 100)


class MechanismTests(unittest.TestCase):
    def test_a_keyword_or_ability_word_names_its_own_mechanism(self):
        self.assertEqual(coverage.mechanism_of("Offspring {2}", ["Offspring"]), "Offspring")
        self.assertEqual(coverage.mechanism_of("Delirium \u2014 This creature gets +1/+1.", []), "Delirium")

    def test_a_longer_word_is_not_the_keyword(self):
        self.assertEqual(coverage.mechanism_of("Enchant player", ["Enchant"]), "Enchant")
        self.assertEqual(coverage.mechanism_of("Equip {2}", ["Equip"]), "Equip")
        self.assertEqual(coverage.mechanism_of("Enchanted creature has flash.", ["Enchant"]), "Auras and Equipment")
        self.assertEqual(coverage.mechanism_of("Equipped creature has first strike.", ["Equip"]), "Auras and Equipment")

    def test_other_lines_take_the_first_pattern_that_fits(self):
        self.assertEqual(coverage.mechanism_of("This creature can't attack unless you control a Swamp.", []), "Attack/block restrictions")
        self.assertEqual(coverage.mechanism_of("Create a token that's a copy of target creature.", []), "Copy effects")
        self.assertEqual(coverage.mechanism_of("Whenever the moon is full, frobnicate the widget.", []), "Other")


class FamilyTests(unittest.TestCase):
    def test_a_keyword_is_its_own_family(self):
        self.assertEqual(coverage.families_of("Offspring {2}", ["Offspring"]), {"Offspring"})

    def test_a_line_belongs_to_every_family_it_matches(self):
        line = "Create a token that's a copy of target creature you control, except it isn't legendary."
        self.assertEqual(coverage.families_of(line), {"Token copy of a creature or permanent", "Copy with changes (an except clause)"})

    def test_a_line_no_family_covers_is_empty(self):
        self.assertEqual(coverage.families_of("Whenever the moon is full, frobnicate the widget."), frozenset())

    def test_a_graveyard_return_is_not_a_cast_from_the_graveyard(self):
        self.assertEqual(coverage.families_of("When this creature enters, return target creature card from your graveyard to your hand."), frozenset())
        self.assertEqual(coverage.families_of("When you cast this spell, return target creature card from your graveyard to your hand."), frozenset())
        self.assertEqual(coverage.families_of("You may cast creature spells from your graveyard."), {"Cast spells from a graveyard"})

    def test_exile_alone_is_not_exile_the_top_card_and_play_it(self):
        self.assertEqual(coverage.families_of("Exile target creature."), frozenset())
        self.assertEqual(coverage.families_of("Exile the top card of your library. You may play it this turn."),
                         {"Exile the top cards, you may play or cast them"})


class WeightTests(unittest.TestCase):
    def test_a_card_counts_for_half_at_the_knee_and_nothing_without_a_rank(self):
        self.assertAlmostEqual(coverage.weight(coverage.WEIGHT_KNEE), 0.5)
        self.assertEqual(coverage.weight(None), 0.0)
        self.assertGreater(coverage.weight(100), 4 * coverage.weight(4900), "rank 100 is worth far more than rank 4,900")


class NextTargetTests(unittest.TestCase):
    def test_the_family_that_unlocks_the_most_goes_first_and_is_assumed_built(self):
        picks = coverage.next_targets([("A", 100, frozenset({"X"})), ("B", 100, frozenset({"X", "Y"})), ("C", 50000, frozenset({"Y"})),
                                    ("D", None, frozenset({"Z"}))])
        self.assertEqual([p["family"] for p in picks], ["X", "Y"], "Z only has a card with no rank, so it is never suggested")
        self.assertEqual((picks[0]["unlocks"], picks[0]["cards"], picks[0]["also_needs"]), (1, ["A"], "Y"))
        self.assertEqual((picks[1]["unlocks"], picks[1]["cards"], picks[1]["also_needs"]), (2, ["B", "C"], ""))

    def test_a_pair_that_unlocks_nothing_alone_is_still_suggested(self):
        picks = coverage.next_targets([("P1", 10, frozenset({"A", "B"})), ("P2", 20, frozenset({"A", "B"})), ("Q", 5000, frozenset({"C"}))])
        self.assertEqual([(p["family"], p["unlocks"]) for p in picks[:2]], [("A", 0), ("B", 2)])
        self.assertEqual(picks[0]["also_needs"], "B")

    def test_a_card_that_needs_two_families_shares_its_weight(self):
        picks = coverage.next_targets([("P", 10, frozenset({"A", "B"})), ("Q", 300, frozenset({"C"}))])
        self.assertEqual(picks[0]["family"], "C", "half of rank 10 is worth less than all of rank 300")

    def test_the_limit_caps_the_list(self):
        cards = [(f"C{i}", 10 + i, frozenset({f"F{i}"})) for i in range(5)]
        self.assertEqual(len(coverage.next_targets(cards, limit=3)), 3)


class DeckModelTests(unittest.TestCase):
    RANKS = list(range(1, 3001))

    def test_a_deck_holds_its_nonbasic_slots_and_the_most_played_cards_are_likelier(self):
        scale = coverage.inclusion_scale(self.RANKS)
        slots = coverage.DECK_CARDS - coverage.DECK_BASICS
        self.assertAlmostEqual(sum(coverage.inclusion(r, scale) for r in self.RANKS), slots, places=3)
        self.assertGreater(coverage.inclusion(10, scale), 3 * coverage.inclusion(1000, scale))
        self.assertEqual(coverage.inclusion(None, scale), 0.0)
        self.assertTrue(all(0 <= coverage.inclusion(r, scale) <= 1 for r in self.RANKS))

    def test_too_few_cards_to_fill_a_deck_are_all_certain(self):
        scale = coverage.inclusion_scale([1, 2, 3])
        self.assertEqual([coverage.inclusion(r, scale) for r in (1, 2, 3)], [1.0, 1.0, 1.0])
        self.assertEqual(coverage.inclusion(None, scale), 0.0, "a card with no rank is in no deck, even when the scale is infinite")

    def test_the_share_counts_the_basics_and_the_playable_cards_by_their_chance(self):
        scale = coverage.inclusion_scale(self.RANKS)
        everything = coverage.deck_coverage([(r, True) for r in self.RANKS], scale)
        self.assertAlmostEqual(everything["share"], 1.0)
        self.assertAlmostEqual(everything["clean"], 1.0)
        nothing = coverage.deck_coverage([(r, False) for r in self.RANKS], scale)
        self.assertAlmostEqual(nothing["share"], coverage.DECK_BASICS / coverage.DECK_CARDS)
        self.assertAlmostEqual(nothing["unplayable"], coverage.DECK_CARDS - coverage.DECK_BASICS, places=3)
        one = coverage.deck_coverage([(r, r != 1) for r in self.RANKS], scale)  # only the most played card is broken
        self.assertAlmostEqual(one["clean"], 1 - coverage.inclusion(1, scale))
        self.assertAlmostEqual(one["unplayable"], coverage.inclusion(1, scale))

    def test_a_deck_with_a_certain_broken_card_is_never_clean(self):
        self.assertEqual(coverage.deck_coverage([(1, False)], float("inf"))["clean"], 0.0)

    def test_the_ranking_counts_cards_per_deck_not_the_weight_of_the_rank(self):
        # Three cards at rank 2000 weigh a little more than one at rank 10 by rank weight (3 * 0.33 against 0.99); by the chance of being
        # in a deck, the one popular card is worth more than the three from the tail.
        cards = [("A1", 2000, frozenset({"A"})), ("A2", 2001, frozenset({"A"})), ("A3", 2002, frozenset({"A"})), ("B", 10, frozenset({"B"}))]
        ranks = [r for _, r, _ in cards] + list(range(100, 3000))
        scale = coverage.inclusion_scale(ranks)
        plain = [p["family"] for p in coverage.next_targets(cards)]
        decky = [p["family"] for p in coverage.next_targets(cards, weigh=lambda r: coverage.inclusion(r, scale))]
        self.assertEqual(plain, ["A", "B"])
        self.assertEqual(decky, ["B", "A"])

    def test_the_audit_reports_the_deck_and_what_each_pick_does_to_it(self):
        result = coverage.analyze(MECH_POOL)
        deck = result["deck"]
        self.assertGreater(deck["share"], coverage.DECK_BASICS / coverage.DECK_CARDS)
        self.assertLess(deck["share"], 1.0)
        shares = [p["deck_share"] for p in result["next"]]
        self.assertEqual(shares, sorted(shares))
        self.assertIn(f"{deck['share']:.1%} fully playable", audit.render(result))


class NextReportTests(unittest.TestCase):
    def setUp(self):
        cat = "Create a token that's a copy of target creature you control, except it isn't legendary."
        self.result = coverage.analyze([
            card("Copy Cat", "Creature — Cat", cat, rank=10, mana_cost="{1}", power="1", toughness="1"),
            card("Copy Dog", "Creature — Dog", cat, rank=20, mana_cost="{1}", power="1", toughness="1"),
            card("Moon Elk", "Creature — Elk", MOON, rank=30, mana_cost="{1}", power="1", toughness="1"),
            card("Mixed Elk", "Creature — Elk", MOON + "\n" + cat, rank=40, mana_cost="{1}", power="1", toughness="1"),
        ])

    def test_a_card_with_an_uncovered_line_is_blocked_not_unlocked(self):
        self.assertEqual(self.result["blocked"], 2)
        self.assertEqual({p["family"] for p in self.result["next"]}, {"Token copy of a creature or permanent", "Copy with changes (an except clause)"})

    def test_the_report_lists_the_order_and_the_blocked_count(self):
        text = audit.render_next(self.result)
        self.assertIn("| 1 | Copy with changes (an except clause) | 0 | 0 | 0 | 17.2% | Token copy of a creature or permanent | - |", text)
        self.assertIn("| 2 | Token copy of a creature or permanent | 2 | 2 | 2.0 | 19.2% | - | Copy Cat #10, Copy Dog #20 |", text)
        self.assertIn("2 unplayable cards have a line no family covers", text)

    def test_the_drill_down_finds_a_family_by_name(self):
        text = audit.render_mechanism(self.result, "token copy")
        self.assertIn("### Token copy of a creature or permanent: a family, 3 cards not playable", text)


MOON = "Whenever the moon is full, frobnicate the widget."
MECH_POOL = [
    card("Bear A", "Creature — Bear", "This creature can't attack unless you control a Swamp.", rank=10, mana_cost="{1}", power="1", toughness="1"),
    card("Bear B", "Creature — Bear", "This creature can't block unless you control a Swamp.\n" + MOON, rank=20, mana_cost="{1}", power="1", toughness="1"),
    card("Bear C", "Creature — Bear", "This creature can't attack unless you control a Swamp.", rank=9000, mana_cost="{1}", power="1", toughness="1"),
    card("Moon Elk", "Creature — Elk", MOON, rank=30, mana_cost="{1}", power="1", toughness="1"),
    card("Safe Bear", "Creature — Bear", "This creature can't attack or block.", rank=40, mana_cost="{1}", power="1", toughness="1"),
    card("Reminder Bear", "Creature — Bear", "Trample (This creature can't attack unless you control a Swamp.)", rank=50, mana_cost="{1}", power="1", toughness="1"),
    card("Copy Cat", "Creature — Cat", "Create a token that's a copy of target creature.", rank=1, mana_cost="{1}", power="1", toughness="1"),
    card("Copy Dog", "Creature — Dog", "Create a token that's a copy of target creature.", rank=2, mana_cost="{1}", power="1", toughness="1"),
]


class MechanismReportTests(unittest.TestCase):
    def setUp(self):
        self.result = coverage.analyze(MECH_POOL)
        self.group = self.result["mechanisms"]["Attack/block restrictions"]

    def test_cards_are_grouped_most_played_first(self):
        self.assertEqual(self.group["cards"], ["Bear A", "Bear B", "Bear C"])

    def test_a_card_whose_other_gap_is_elsewhere_is_not_an_only_gap(self):
        self.assertEqual(self.group["only"], ["Bear A", "Bear C"])
        self.assertEqual(self.result["mechanisms"]["Other"]["only"], ["Moon Elk"])

    def test_the_table_ranks_by_popular_only_gap_cards(self):
        text = audit.render_mechanisms(self.result)
        self.assertIn("| Attack/block restrictions | 4 | 3 | 2 | 2 | 1 | Bear A #10, Bear C #9000 |", text)
        self.assertLess(text.index("| Copy effects |"), text.index("| Attack/block restrictions |"), "two popular only-gap cards beat one")
        self.assertIn("2 cards have a line that fits no mechanism.", text)

    def test_the_drill_down_lists_the_wordings(self):
        text = audit.render_mechanism(self.result, "attack/block")
        self.assertIn("### Attack/block restrictions: 3 of 4 cards not playable, 2 with this as the only gap", text)
        self.assertIn("`This creature can't attack unless you control a Swamp.`", text)

    def test_all_cards_counts_playable_ones_and_never_fewer_than_the_gaps(self):
        group = self.group
        self.assertEqual((group["all"], len(group["cards"])), (4, 3), "Safe Bear is playable, and the reminder text on Reminder Bear is ignored")
        back_only = coverage.analyze([
            {"name": "Front // Back", "layout": "transform", "cmc": 1, "mana_cost": "{1}", "type_line": "Creature — Bear // Creature — Wolf", "edhrec_rank": 60,
             "card_faces": [{"name": "Front", "mana_cost": "{1}", "type_line": "Creature — Bear", "oracle_text": "Trample", "power": "1", "toughness": "1"},
                            {"name": "Back", "mana_cost": "", "type_line": "Creature — Wolf", "oracle_text": "This creature can't attack unless you control a Swamp.",
                             "power": "1", "toughness": "1"}]}])
        self.assertEqual(back_only["mechanisms"]["Attack/block restrictions"]["all"], 1, "a gap on the back face counts, though the front text has none")

    def test_an_unknown_mechanism_says_so(self):
        self.assertTrue(audit.render_mechanism(self.result, "nonsense").startswith("No mechanism or family matches `nonsense`"))


class RenderTests(unittest.TestCase):
    def test_the_summary_names_the_numbers_and_the_groups(self):
        text = audit.render(coverage.analyze(POOL), top=5)
        self.assertIn("3 of 6 Commander-legal cards fully playable (50.0%)", text)
        self.assertIn("| Creature | 1 of 4 (25%) |", text)
        self.assertIn("| 3 | `Whenever the moon is full, frobnicate the widget.` | Odd Bear #3, Odd Cat #4 |", text)

    def test_a_pipe_in_a_line_does_not_break_the_table(self):
        pool = [card("Pipes", "Creature — Bear", "Choose one | or the other", power="1", toughness="1")]
        self.assertNotIn("one | or", audit.render(coverage.analyze(pool)))


class PoolCacheTests(unittest.TestCase):
    def test_a_fresh_cache_is_used_without_the_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "pool.json")
            with open(path, "w") as f:
                json.dump(POOL, f)
            self.assertEqual(audit.fetch_pool(path), POOL)


if __name__ == "__main__":
    unittest.main()
