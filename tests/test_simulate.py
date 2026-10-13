import unittest

from infernal_machine.bot import goldfish
from infernal_machine.cards import Card, Deck
from infernal_machine.simulate import Fetch, _landing, _Source, enters_tapped, fetch_land, format_simulation, mana_sources, simulate

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
TAPLAND = Card(name="Tapland", type_line="Land", produced_mana=("G",), oracle_text="This land enters tapped.\n{T}: Add {G}.")
SOL_RING = Card(name="Sol Ring", mana_cost="{1}", cmc=1, type_line="Artifact", oracle_text="{T}: Add {C}{C}.", produced_mana=("C",))
ELF = Card(name="Llanowar Elves", mana_cost="{G}", cmc=1, type_line="Creature — Elf Druid", power="1", toughness="1",
           oracle_text="{T}: Add {G}.", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
HASTY = Card(name="Goblin Guide", mana_cost="{G}", cmc=1, type_line="Creature — Goblin", power="2", toughness="2", oracle_text="Haste")
BLUE = Card(name="Counterspell", mana_cost="{U}{U}", cmc=2, type_line="Instant")
TITAN = Card(name="Titan", mana_cost="{9}{G}", cmc=10, type_line="Creature — Giant", power="9", toughness="9")


PASSAGE = Card(name="Fabled Passage", type_line="Land", oracle_text="{T}, Sacrifice this land: Search your library for a basic land card, "
               "put it onto the battlefield tapped, then shuffle. Then if you control four or more lands, untap that land.")
WILDS = Card(name="Evolving Wilds", type_line="Land", oracle_text="{T}, Sacrifice this land: Search your library for a basic land card, "
             "put it onto the battlefield tapped, then shuffle.")
STRAND = Card(name="Flooded Strand", type_line="Land", oracle_text="{T}, Pay 1 life, Sacrifice Flooded Strand: Search your library for a "
              "Plains or Island card, put it onto the battlefield, then shuffle.")
ICE_TUNNEL = Card(name="Ice Tunnel", type_line="Land \u2014 Island Swamp", produced_mana=("U", "B"),
                  oracle_text="({T}: Add {U} or {B}.)\nThis land enters tapped.")
SWAMP = Card(name="Swamp", type_line="Basic Land \u2014 Swamp", produced_mana=("B",))
ISLAND_SOURCE = _Source(frozenset("U"), 1)


def deck(*cards, commanders=()):
    return Deck(commanders=list(commanders), main=list(cards), sideboard=[])


class CardModelTests(unittest.TestCase):
    def test_mana_makers(self):
        self.assertEqual(mana_sources(SOL_RING), [frozenset("C")] * 2)
        self.assertEqual(mana_sources(ELF), [frozenset("G")])
        self.assertEqual(mana_sources(BEAR), [])
        self.assertEqual(mana_sources(FOREST), [])  # lands are handled apart

    def test_enters_tapped_only_when_unconditional(self):
        self.assertTrue(enters_tapped(TAPLAND))
        self.assertFalse(enters_tapped(FOREST))
        self.assertFalse(enters_tapped(Card(name="Glacial Fortress", type_line="Land", oracle_text="Glacial Fortress enters tapped unless you control a Plains or an Island.")))


class SimulateTests(unittest.TestCase):
    def test_reproducible(self):
        d = deck(*[FOREST] * 24, *[BEAR] * 36)
        self.assertEqual(simulate(d, games=100, seed=3), simulate(d, games=100, seed=3))

    def test_openings_match_goldfish(self):
        d = deck(*[FOREST] * 37, *[BEAR] * 62, commanders=[BEAR])
        g, s = goldfish(d, games=300, turns=4, seed=2), simulate(d, games=300, turns=4, seed=2)
        self.assertEqual((g.mulligan_rate, g.average_opening_lands, g.land_drop_rate), (s.mulligan_rate, s.average_opening_lands, s.land_drop_rate))

    def test_all_lands_spend_nothing(self):
        stats = simulate(deck(*[FOREST] * 60), games=20, turns=4)
        self.assertEqual(stats.mana_spent, {1: 0, 2: 0, 3: 0, 4: 0})
        self.assertEqual(stats.mana_available[3], 3.0)
        self.assertEqual(stats.cards, [])

    def test_casts_what_it_can_pay_for_and_attacks_a_turn_later(self):
        stats = simulate(deck(*[FOREST] * 30, *[BEAR] * 30), games=300, turns=4, seed=1)
        self.assertEqual(stats.damage[1], 0)  # nothing has been on the battlefield for a turn yet
        self.assertGreater(stats.damage[4], stats.damage[3])
        bear = stats.cards[0]
        self.assertEqual((bear.name, bear.copies), ("Grizzly Bears", 30))
        self.assertGreater(bear.cast_when_seen, 0.9)

    def test_haste_attacks_the_turn_it_enters(self):
        stats = simulate(deck(*[FOREST] * 30, *[HASTY] * 30), games=300, turns=2, seed=1, on_the_play=True)
        self.assertGreater(stats.damage[1], 0)

    def test_ramp_gets_ahead_of_the_land_count(self):
        ramp = simulate(deck(*[FOREST] * 24, *[SOL_RING] * 12, *[TITAN] * 24), games=400, turns=6, seed=4)
        plain = simulate(deck(*[FOREST] * 24, *[BEAR] * 12, *[TITAN] * 24), games=400, turns=6, seed=4)
        self.assertGreater(ramp.mana_available[4], plain.mana_available[4])

    def test_wrong_colors_are_stuck_not_cast(self):
        stats = simulate(deck(*[FOREST] * 30, *[BLUE] * 30), games=200, turns=5, seed=1)
        self.assertEqual(stats.cards[0].cast_rate, 0.0)
        self.assertGreater(stats.stuck_on_colors[5], 0.9)
        self.assertIsNone(stats.cards[0].average_cast_turn)

    def test_a_tapland_is_played_when_it_costs_nothing(self):
        # Turn 1 with a one-drop in hand wants the untapped land; with nothing to cast the tapped one is free.
        stats = simulate(deck(*[TAPLAND] * 30, *[HASTY] * 30), games=200, turns=1, seed=1, on_the_play=True)
        self.assertEqual(stats.damage[1], 0.0)

    def test_the_commander_is_cast_from_the_command_zone(self):
        stats = simulate(deck(*[FOREST] * 99, commanders=[BEAR]), games=50, turns=3, seed=1)
        bear = stats.cards[0]
        self.assertEqual((bear.seen_rate, bear.cast_rate), (1.0, 1.0))

    def test_report_text(self):
        text = format_simulation(simulate(deck(*[FOREST] * 30, *[BEAR] * 30), games=50, turns=3))
        self.assertIn("Grizzly Bears", text)
        self.assertIn("land drop", text)


class FetchLandTests(unittest.TestCase):
    def test_basic_land_fetches_are_read(self):
        self.assertEqual(fetch_land(WILDS), Fetch(tapped=True, untap_at_four=False))
        self.assertEqual(fetch_land(PASSAGE), Fetch(tapped=True, untap_at_four=True))

    def test_other_lands_are_not_fetches(self):
        self.assertIsNone(fetch_land(STRAND))  # it finds a land by type, which is not modeled
        self.assertIsNone(fetch_land(ICE_TUNNEL))
        self.assertIsNone(fetch_land(FOREST))

    def test_it_takes_the_basic_that_adds_a_wanted_color(self):
        colors, tapped, found = _landing(WILDS, [ISLAND, SWAMP], {"U", "B"}, [ISLAND_SOURCE], 1)
        self.assertEqual((colors, tapped, found), (frozenset("B"), True, SWAMP))

    def test_it_takes_what_the_library_has(self):
        colors, _, found = _landing(WILDS, [ISLAND, FOREST], {"B"}, [], 0)
        self.assertIn(found, (ISLAND, FOREST))  # no Swamp left, so something that still makes mana
        self.assertEqual(colors, frozenset(found.produced_mana))

    def test_with_no_basic_left_it_fetches_nothing(self):
        self.assertEqual(_landing(WILDS, [BEAR, ICE_TUNNEL], {"B"}, [], 0), (frozenset(), True, None))

    def test_fabled_passage_untaps_with_four_lands_only(self):
        self.assertTrue(_landing(PASSAGE, [SWAMP], {"B"}, [], 2)[1])  # it would be the third land
        self.assertFalse(_landing(PASSAGE, [SWAMP], {"B"}, [], 3)[1])  # the fourth
        self.assertTrue(_landing(WILDS, [SWAMP], {"B"}, [], 3)[1])

    def test_a_plain_land_is_played_as_it_is(self):
        self.assertEqual(_landing(ICE_TUNNEL, [SWAMP], {"B"}, [], 0), (frozenset("UB"), True, None))
        self.assertEqual(_landing(FOREST, [SWAMP], {"B"}, [], 0), (frozenset("G"), False, None))

    def test_the_fetch_finds_the_color_the_deck_needs(self):
        # Only Evolving Wilds and Islands: the fetched Island pays for {U}{U}. Without an Island in the library it cannot.
        with_islands = simulate(deck(*[WILDS] * 20, *[ISLAND] * 20, *[BLUE] * 20), games=200, turns=6, seed=1)
        without = simulate(deck(*[WILDS] * 20, *[SWAMP] * 20, *[BLUE] * 20), games=200, turns=6, seed=1)
        self.assertGreater(with_islands.cards[0].cast_rate, 0.5)
        self.assertEqual(without.cards[0].cast_rate, 0.0)

    def test_a_fetched_basic_leaves_the_library(self):
        # One Swamp in the deck: it can be drawn or fetched once, so there is never more than one source of mana.
        stats = simulate(deck(*[WILDS] * 59, SWAMP), games=200, turns=6, seed=1)
        self.assertLessEqual(max(stats.mana_available.values()), 1.0)

    def test_a_fetch_with_nothing_to_fetch_makes_no_mana(self):
        stats = simulate(deck(*[WILDS] * 60), games=20, turns=4)
        self.assertEqual(stats.mana_available[4], 0.0)


class OnCurveTests(unittest.TestCase):
    def test_cheap_spells_in_a_land_heavy_deck_are_on_curve(self):
        stats = simulate(deck(*[FOREST] * 30, *[HASTY] * 30), games=300, turns=6, seed=1)
        self.assertGreater(stats.cards[0].on_curve, 0.8)
        self.assertEqual(stats.on_curve, stats.cards[0].on_curve)

    def test_a_card_that_can_never_be_cast_is_never_on_curve(self):
        stats = simulate(deck(*[FOREST] * 30, *[BLUE] * 30), games=200, turns=5, seed=1)
        self.assertEqual(stats.cards[0].on_curve, 0.0)

    def test_a_card_too_expensive_for_the_game_length_is_not_rated(self):
        stats = simulate(deck(*[FOREST] * 30, *[TITAN] * 30), games=100, turns=8, seed=1)
        self.assertIsNone(stats.cards[0].on_curve)
        self.assertIsNone(stats.on_curve)

    def test_report_text_shows_it(self):
        text = format_simulation(simulate(deck(*[FOREST] * 30, *[BEAR] * 30), games=100, turns=4, seed=1))
        self.assertIn("On curve:", text)
        self.assertIn("on curve", text)


if __name__ == "__main__":
    unittest.main()
