"""Glaring Fleshraker: "Whenever you cast a colorless spell, create a 0/1 colorless Eldrazi Spawn creature token with "Sacrifice this
token: Add {C}."" and "Whenever another colorless creature you control enters, this creature deals 1 damage to each opponent." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, real, run_stack, table3

FLESHRAKER = real("Glaring Fleshraker", "{2}{C}", "Creature — Eldrazi Drone", "Whenever you cast a colorless spell, create a 0/1 "
                  "colorless Eldrazi Spawn creature token with \"Sacrifice this token: Add {C}.\"\nWhenever another colorless creature you "
                  "control enters, this creature deals 1 damage to each opponent.", "2", "2")
GOLEM = Card(name="Golem", mana_cost="{2}", cmc=2.0, type_line="Artifact Creature — Golem", power="2", toughness="2")
GOBLIN = Card(name="Goblin", mana_cost="{R}", cmc=1.0, type_line="Creature — Goblin", colors=("R",), power="1", toughness="1")


def cast(card):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.battlefield = [card], [Permanent(FLESHRAKER)] + lands(2)
    game._perform(a, CAST + card.name)
    run_stack(game)
    return game, a


def spawns(seat):
    return sum(p.card.name == "Eldrazi Spawn" for p in seat.battlefield)


class GlaringFleshrakerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(FLESHRAKER), [])

    def test_a_colorless_creature_makes_a_spawn_and_both_ping(self):
        game, a = cast(GOLEM)
        self.assertEqual(spawns(a), 1)
        self.assertEqual([s.life for s in game.seats[1:]], [38, 38])  # the Golem and the Spawn are colorless creatures entering

    def test_a_colored_creature_does_nothing(self):
        game, a = cast(GOBLIN)
        self.assertEqual(spawns(a), 0)
        self.assertEqual([s.life for s in game.seats[1:]], [40, 40])


if __name__ == "__main__":
    unittest.main()
