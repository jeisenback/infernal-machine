""""Whenever this creature deals combat damage to a player or planeswalker, ..." (Psychic Frog)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, real, run_stack, table3

FROG = real("Psychic Frog", "{U}{B}", "Creature — Frog", "Whenever this creature deals combat damage to a player or planeswalker, draw a "
            "card.\nDiscard a card: Put a +1/+1 counter on this creature.\nExile three cards from your graveyard: This creature gains flying "
            "until end of turn.", "1", "2")
WALKER = Card(name="Walker", mana_cost="{3}", type_line="Legendary Planeswalker — Test", loyalty="5")


def table():
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.hand, a.library = [], [OGRE, OGRE, OGRE]
    frog = Permanent(FROG)
    a.battlefield = [frog]
    return game, a, b, frog


class PsychicFrogTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(FROG), [])

    def test_combat_damage_to_a_player_draws(self):
        game, a, b, frog = table()
        game.damage(b, 1, frog, combat=True)
        run_stack(game)
        self.assertEqual(a.hand, [OGRE])

    def test_combat_damage_to_a_planeswalker_draws(self):
        game, a, b, frog = table()
        walker = Permanent(WALKER)
        walker.loyalty = 5
        b.battlefield = [walker]
        game.damage(walker, 1, frog, combat=True)
        run_stack(game)
        self.assertEqual(a.hand, [OGRE])

    def test_combat_damage_to_a_creature_does_not(self):
        game, a, b, frog = table()
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        game.damage(bear, 1, frog, combat=True)
        run_stack(game)
        self.assertEqual(a.hand, [])

    def test_noncombat_damage_does_not(self):
        game, a, b, frog = table()
        walker = Permanent(WALKER)
        walker.loyalty = 5
        b.battlefield = [walker]
        game.damage(b, 1, frog)
        game.damage(walker, 1, frog)
        run_stack(game)
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
