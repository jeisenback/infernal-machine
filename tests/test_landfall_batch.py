"""Landfall, from the cards' real Oracle text: Scythecat Cub (a +1/+1 counter, or the second time, double the counters instead), Omnath,
Locus of Creation (life, then mana, then damage, by how many times the ability has resolved this turn) and Emeria Shepherd (a nonland
permanent card back to the hand, or to the battlefield if the land was a Plains)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, PLAINS, RELIC, enter, pick, real, run_stack, table3

CUB = real("Scythecat Cub", "{1}{G}", "Creature — Cat", "Trample\nLandfall — Whenever a land you control enters, put a +1/+1 counter on target "
           "creature you control. If this is the second time this ability has resolved this turn, double the number of +1/+1 counters on that "
           "creature instead.", "2", "2", colors=("G",))
OMNATH = real("Omnath, Locus of Creation", "{R}{G}{W}{U}", "Legendary Creature — Elemental", "When Omnath enters, draw a card.\nLandfall — "
              "Whenever a land you control enters, you gain 4 life if this is the first time this ability has resolved this turn. If it's the "
              "second time, add {R}{G}{W}{U}. If it's the third time, Omnath deals 4 damage to each opponent and each planeswalker you don't "
              "control.", "4", "4", colors=("G", "R", "U", "W"))
SHEPHERD = real("Emeria Shepherd", "{5}{W}{W}", "Creature — Angel", "Flying\nLandfall — Whenever a land you control enters, you may return "
                "target nonland permanent card from your graveyard to your hand. If that land is a Plains, you may return that nonland "
                "permanent card to the battlefield instead.", "4", "4", colors=("W",))
CARDS = (CUB, OMNATH, SHEPHERD)
WALKER = Card(name="Test Walker", mana_cost="{3}", cmc=3.0, type_line="Legendary Planeswalker — Test", oracle_text="+1: You gain 1 life.",
              loyalty="5")


def land_enters(game, seat, card=FOREST):
    enter(game, seat, card)
    run_stack(game)


class LandfallBatchTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_scythecat_cub_puts_a_counter_then_doubles_the_second_time(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(CUB), bear]
        land_enters(game, a)
        self.assertEqual(bear.counters.get("+1/+1"), 1)
        bear.counters["+1/+1"] = 3
        land_enters(game, a)  # the second time: 3 doubled to 6, and no counter put
        self.assertEqual(bear.counters.get("+1/+1"), 6)
        land_enters(game, a)  # the third time: a counter again
        self.assertEqual(bear.counters.get("+1/+1"), 7)

    def test_omnath_gains_life_then_adds_mana_then_deals_damage(self):
        game, _ = table3()
        a, b, c = game.seats
        walker = Permanent(WALKER, loyalty=5)
        b.battlefield = [walker]
        a.battlefield = [Permanent(OMNATH)]
        land_enters(game, a)
        self.assertEqual((a.life, b.life), (44, 40))
        land_enters(game, a)
        self.assertEqual((a.life, sorted(color for unit in a.mana_pool for color in unit)), (44, ["G", "R", "U", "W"]))
        land_enters(game, a)
        self.assertEqual((b.life, c.life, a.life, walker.loyalty), (36, 36, 44, 1))
        land_enters(game, a)  # a fourth time: nothing
        self.assertEqual((a.life, b.life), (44, 36))

    def test_emeria_shepherd_returns_to_the_battlefield_only_for_a_plains(self):
        for land, to_battlefield in ((PLAINS, True), (FOREST, False)):
            game, _ = table3(pick("Yes", "Relic"))
            a = game.seats[0]
            a.battlefield, a.graveyard = [Permanent(SHEPHERD)], [RELIC]
            land_enters(game, a, land)
            self.assertEqual((any(p.card is RELIC for p in a.battlefield), RELIC in a.hand), (to_battlefield, not to_battlefield), land.name)


if __name__ == "__main__":
    unittest.main()
