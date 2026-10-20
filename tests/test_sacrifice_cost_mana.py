"""A sacrifice cost and a mana payment that would use up the same permanent: a Treasure or an Eldrazi Spawn can pay for the mana or be
the sacrifice, not both. The cast used to be offered and then crashed with nothing left to sacrifice (the bot games, seed 109)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from tests.helpers import BARGAIN, battlefield_names, BEAR, priority_cast, real, RELIC, script, SHRINE, Table, table3

PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure", oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")
SPAWN = Card(name="Eldrazi Spawn", type_line="Token Creature — Eldrazi Spawn", power="0", toughness="1",
             oracle_text="Sacrifice this token: Add {C}.")
DRAW = real("Costly Draw", "{W}", "Instant", "As an additional cost to cast this spell, sacrifice an artifact.\nDraw a card.")
OFFERING = real("Grim Offering", "{C}", "Instant", "As an additional cost to cast this spell, sacrifice a creature.\nDraw a card.")


def table(card, *battlefield):
    game, _ = table3(script("Pass"))
    a = game.seats[0]
    a.hand, a.library = [card], [PLAINS] * 5
    a.battlefield = [Permanent(c, sick=False) for c in battlefield]
    game.turn, game.step = 2, "main1"
    return game, a


def offered(game, a, card):
    return CAST + card.name in game.legal_actions(a)


class TreasureTests(unittest.TestCase):
    def test_the_only_treasure_cannot_pay_for_both(self):
        game, a = table(DRAW, TREASURE)
        self.assertFalse(offered(game, a, DRAW))

    def test_a_land_pays_the_mana_and_the_treasure_is_the_sacrifice(self):
        game, a = table(DRAW, PLAINS, TREASURE)
        self.assertTrue(offered(game, a, DRAW))
        game._perform(a, CAST + DRAW.name)
        self.assertEqual([(p.card.name, p.tapped) for p in a.battlefield], [("Plains", True)])

    def test_two_treasures_pay_one_for_mana_and_one_as_the_sacrifice(self):
        game, a = table(DRAW, TREASURE, TREASURE)
        self.assertTrue(offered(game, a, DRAW))
        game._perform(a, CAST + DRAW.name)
        self.assertEqual(a.battlefield, [])


class SpawnTests(unittest.TestCase):
    def test_the_only_spawn_cannot_pay_for_both(self):
        game, a = table(OFFERING, SPAWN)
        self.assertFalse(offered(game, a, OFFERING))

    def test_a_second_creature_is_the_sacrifice(self):
        game, a = table(OFFERING, SPAWN, BEAR)
        self.assertTrue(offered(game, a, OFFERING))
        game._perform(a, CAST + OFFERING.name)
        self.assertEqual(a.battlefield, [], "the Spawn paid for the mana and the Bear was the sacrifice")


class SacrificeXTests(unittest.TestCase):
    """Immoral Bargain: X creatures are sacrificed, and a Spawn that paid for the mana is not one of them (bot games, seed 109)."""

    def asked(self, mine, **more):
        t = priority_cast(Table(BARGAIN, CAST, mine=mine, theirs=[Permanent(RELIC), Permanent(SHRINE)], **more))
        return t, [options for prompt, options in t.a.player.prompts if prompt.startswith("Choose X")][0]

    def test_a_spawn_that_pays_for_the_mana_is_not_a_creature_to_sacrifice(self):
        t, options = self.asked([Permanent(SPAWN, sick=False), Permanent(BEAR)], n=2)
        self.assertEqual(options, ["0", "1"])

    def test_only_the_spawn_that_pays_is_lost_to_the_count(self):
        t, options = self.asked([Permanent(SPAWN, sick=False), Permanent(SPAWN, sick=False), Permanent(BEAR)], n=2)
        self.assertEqual(options, ["0", "1", "2"], "one Spawn pays the {1}; the other Spawn and the Bear can be sacrificed")


class UnaffectedTests(unittest.TestCase):
    def test_a_spell_with_no_sacrifice_cost_is_still_cast_with_a_treasure(self):
        plain = real("Plain Draw", "{W}", "Instant", "Draw a card.")
        game, a = table(plain, TREASURE)
        self.assertTrue(offered(game, a, plain))


if __name__ == "__main__":
    unittest.main()
