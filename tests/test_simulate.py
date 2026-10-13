import unittest

from infernal_machine.bot import goldfish
from infernal_machine.cards import Card, Deck
from infernal_machine.simulate import enters_tapped, format_simulation, mana_sources, simulate

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


if __name__ == "__main__":
    unittest.main()
