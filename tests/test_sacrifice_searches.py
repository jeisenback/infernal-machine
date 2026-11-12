"""Searches keyed to a creature sacrificed to cast the spell, from the cards' real Oracle text: Eldritch Evolution (mana value up to 2 plus
the sacrificed creature's, and the spell is exiled) and Neoform (exactly 1 plus, entering with an additional +1/+1 counter)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, run_stack, table3

EVOLUTION = real("Eldritch Evolution", "{1}{G}{G}", "Sorcery", "As an additional cost to cast this spell, sacrifice a creature.\nSearch your "
                 "library for a creature card with mana value X or less, where X is 2 plus the sacrificed creature's mana value. Put that card "
                 "onto the battlefield, then shuffle. Exile Eldritch Evolution.", colors=("G",))
FOUR = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "3", "3", colors=("R",))
FIVE = real("Thorn Elemental", "{5}{G}{G}", "Creature — Elemental", "", "7", "7", colors=("G",))  # mana value 7: too big for a Bear
NEOFORM = real("Neoform", "{G}{U}", "Sorcery", "As an additional cost to cast this spell, sacrifice a creature.\nSearch your library for a "
               "creature card with mana value equal to 1 plus the sacrificed creature's mana value, put that card onto the battlefield with an "
               "additional +1/+1 counter on it, then shuffle.", colors=("G", "U"))
THREE = real("Centaur Courser", "{2}{G}", "Creature — Centaur Warrior", "", "3", "3", colors=("G",))
SACRIFICED = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))


class SacrificeSearchTests(unittest.TestCase):
    def test_they_are_understood(self):
        for card in (EVOLUTION, NEOFORM):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_it_finds_a_creature_of_up_to_2_more_mana_value_and_is_exiled(self):
        game, _ = table3(pick("Grizzly Bears", "Thorn Elemental", "Hill Giant"))  # it would take the 7 if it were offered
        a = game.seats[0]
        a.battlefield = [Permanent(SACRIFICED)] + lands(3)
        a.library, a.hand = [FIVE, FOUR, BEAR], [EVOLUTION]
        game._perform(a, CAST + EVOLUTION.name)
        run_stack(game)
        self.assertEqual((sorted(p.card.name for p in a.battlefield if "Creature" in p.card.type_line), [c.name for c in a.graveyard],
                          [c.name for c in a.exile]), (["Hill Giant"], ["Grizzly Bears"], ["Eldritch Evolution"]))

    def test_neoform_finds_exactly_1_more_mana_value_with_a_counter(self):
        game, _ = table3(pick("Grizzly Bears", "Hill Giant", "Centaur Courser"))  # it would take the 4 if it were offered
        a = game.seats[0]
        a.battlefield = [Permanent(SACRIFICED)] + lands(2)
        a.library, a.hand = [FOUR, THREE, BEAR], [NEOFORM]
        game._perform(a, CAST + NEOFORM.name)
        run_stack(game)
        found = [p for p in a.battlefield if "Creature" in p.card.type_line]
        self.assertEqual([(p.card.name, p.counters.get("+1/+1")) for p in found], [("Centaur Courser", 1)])


if __name__ == "__main__":
    unittest.main()
