""""If an opponent cast three or more spells this turn, you may pay {0} rather than pay this spell's mana cost. Exile any number of target
spells." (Mindbreak Trap)."""

import unittest

from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, lands, real, table3

TRAP = real("Mindbreak Trap", "{2}{U}{U}", "Instant — Trap", "If an opponent cast three or more spells this turn, you may pay {0} rather "
            "than pay this spell's mana cost.\nExile any number of target spells.", colors=("U",))
UNCOUNTERABLE = real("Carnage Tyrant", "{4}{G}{G}", "Creature — Dinosaur", "This spell can't be countered.\nTrample, hexproof", "7", "6",
                     colors=("G",))


def table(spells_cast, mana=0):
    """Seat 1 has cast `spells_cast` spells this turn and has a Bear and a Carnage Tyrant on the stack; seat 0 holds the Trap."""
    game, _ = table3(lambda prompt, options: 0)  # every spell it may target, the first option each time
    a, b = game.seats[0], game.seats[1]
    b.hand, b.battlefield = [BEAR, UNCOUNTERABLE], lands(8)
    game.active, game.step = 1, "main1"
    game._perform(b, CAST + "Bear")
    game._perform(b, CAST + "Carnage Tyrant")
    b.cast_log = [(game.turn, OGRE)] * spells_cast
    a.hand, a.battlefield, a.exile = [TRAP], lands(mana), []
    return game, a, b


class MindbreakTrapTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(TRAP), [])

    def test_free_after_an_opponent_cast_three_spells(self):
        game, a, _ = table(3)
        self.assertIn(CAST + "Mindbreak Trap", game.legal_actions(a))

    def test_not_free_after_two(self):
        game, a, _ = table(2)
        self.assertNotIn(CAST + "Mindbreak Trap", game.legal_actions(a))

    def test_spells_cast_last_turn_do_not_count(self):
        game, a, b = table(0)
        b.cast_log = [(game.turn - 1, OGRE)] * 3
        self.assertNotIn(CAST + "Mindbreak Trap", game.legal_actions(a))

    def test_it_exiles_every_spell_it_targets_even_one_that_cant_be_countered(self):
        game, a, b = table(3)
        game._perform(a, CAST + "Mindbreak Trap")
        game._resolve(game.stack.pop())
        self.assertEqual(game.stack, [])
        self.assertEqual(sorted(c.name for c in b.exile), ["Bear", "Carnage Tyrant"])

    def test_a_spell_that_already_left_the_stack_stays_where_it_went(self):
        game, a, b = table(3)
        game._perform(a, CAST + "Mindbreak Trap")
        trap = game.stack.pop()
        game.counter(next(i for i in game.stack if i.card.name == "Bear"))
        game._resolve(trap)
        self.assertEqual(([c.name for c in b.graveyard], [c.name for c in b.exile]), (["Bear"], ["Carnage Tyrant"]))

    def test_a_copy_of_a_spell_just_stops_existing(self):
        game, a, b = table(3)
        bear = next(i for i in game.stack if i.card.name == "Bear")
        game.copy_spell(bear, b)
        game._perform(a, CAST + "Mindbreak Trap")
        game._resolve(game.stack.pop())
        self.assertEqual(game.stack, [])
        self.assertEqual(sorted(c.name for c in b.exile), ["Bear", "Carnage Tyrant"])  # one Bear: the copy is no card


if __name__ == "__main__":
    unittest.main()
