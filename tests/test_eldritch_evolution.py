"""Eldritch Evolution, from its real Oracle text: the creature card it finds may have mana value up to 2 plus the sacrificed creature's, and
the spell is exiled."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, run_stack, table3

EVOLUTION = real("Eldritch Evolution", "{1}{G}{G}", "Sorcery", "As an additional cost to cast this spell, sacrifice a creature.\nSearch your "
                 "library for a creature card with mana value X or less, where X is 2 plus the sacrificed creature's mana value. Put that card "
                 "onto the battlefield, then shuffle. Exile Eldritch Evolution.", colors=("G",))
FOUR = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "3", "3", colors=("R",))
FIVE = real("Thorn Elemental", "{5}{G}{G}", "Creature — Elemental", "", "7", "7", colors=("G",))  # mana value 7: too big for a Bear
SACRIFICED = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))


class EldritchEvolutionTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(EVOLUTION), [])

    def test_it_finds_a_creature_of_up_to_2_more_mana_value_and_is_exiled(self):
        game, _ = table3(pick("Grizzly Bears", "Thorn Elemental", "Hill Giant"))  # it would take the 7 if it were offered
        a = game.seats[0]
        a.battlefield = [Permanent(SACRIFICED)] + lands(3)
        a.library, a.hand = [FIVE, FOUR, BEAR], [EVOLUTION]
        game._perform(a, CAST + EVOLUTION.name)
        run_stack(game)
        self.assertEqual((sorted(p.card.name for p in a.battlefield if "Creature" in p.card.type_line), [c.name for c in a.graveyard],
                          [c.name for c in a.exile]), (["Hill Giant"], ["Grizzly Bears"], ["Eldritch Evolution"]))


if __name__ == "__main__":
    unittest.main()
