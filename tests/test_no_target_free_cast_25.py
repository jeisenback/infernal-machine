"""A spell cast without paying its mana cost still needs a legal target; with none it is not cast (found by bot games on
the real precon decks, #25: a cascade into Reality Shift with no creature in play crashed the cast).
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from tests.test_combat import BEAR, OGRE
from tests.test_effects import FOREST, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

SHIFT = Card(name="Reality Shift", mana_cost="{1}{U}", cmc=2.0, type_line="Instant", colors=("U",),
             oracle_text="Exile target creature. Its controller manifests the top card of their library.")
DRAW = Card(name="Brainwave", mana_cost="{1}", cmc=1.0, type_line="Sorcery", oracle_text="Draw a card.")


class CascadeWithoutATargetTests(unittest.TestCase):
    def cascade(self, board, answer="Yes"):
        game, _ = table3(pick(answer, "Ogre", "Bear"))
        a, b, c = game.seats
        a.library = [FOREST, SHIFT, BEAR, BEAR, BEAR]
        for seat, creatures in zip((a, b, c), board):
            seat.battlefield = [Permanent(card) for card in creatures]
        game.cascade(a, 4)  # Reality Shift (mana value 2) is the card found, behind a land
        run_stack(game)
        return game, a, b, c

    def test_with_no_creature_in_play_it_is_not_cast_and_goes_to_the_bottom(self):
        game, a, b, c = self.cascade([[], [], []])
        self.assertEqual((game.stack, a.exile, a.graveyard), ([], [], []))
        self.assertIn("Reality Shift", [card.name for card in a.library])

    def test_with_a_creature_in_play_it_is_cast_and_exiles_it(self):
        game, a, b, c = self.cascade([[], [OGRE], []])
        self.assertEqual([p.card.name for p in b.battlefield if p.card.name == "Ogre"], [])  # exiled
        self.assertEqual([c.name for c in a.graveyard], ["Reality Shift"])

    def test_declining_the_cast_still_puts_it_on_the_bottom(self):
        game, a, b, c = self.cascade([[], [OGRE], []], answer="No")
        self.assertEqual([p.card.name for p in b.battlefield], ["Ogre"])
        self.assertEqual(("Reality Shift" in [x.name for x in a.library], a.exile), (True, []))
