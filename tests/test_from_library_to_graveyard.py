""""When this card is put into your graveyard from your library, you may put it onto the battlefield." (Narcomoeba), "... you may exile it.
If you do, Creeping Chill deals 3 damage to each opponent and you gain 3 life." (Creeping Chill)."""

import unittest

from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, real, run_stack, table3

NARCOMOEBA = real("Narcomoeba", "{1}{U}", "Creature — Illusion", "Flying\nWhen this card is put into your graveyard from your library, you "
                  "may put it onto the battlefield.", "1", "1")
CHILL = real("Creeping Chill", "{3}{B}", "Sorcery", "Creeping Chill deals 3 damage to each opponent and you gain 3 life.\nWhen Creeping "
             "Chill is put into your graveyard from your library, you may exile it. If you do, Creeping Chill deals 3 damage to each "
             "opponent and you gain 3 life.")


def milled(*library):
    game, _ = table3()
    a = game.seats[0]
    a.library, a.graveyard, a.battlefield = list(library), [], []
    game.mill(a, len(library))
    run_stack(game)
    return game, a


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (NARCOMOEBA, CHILL):
            self.assertEqual(unsupported_lines(card), [], card.name)


class NarcomoebaTests(unittest.TestCase):
    def test_milled_it_comes_onto_the_battlefield(self):
        game, a = milled(FOREST, NARCOMOEBA)
        self.assertEqual([p.card for p in a.battlefield], [NARCOMOEBA])
        self.assertEqual(a.graveyard, [FOREST])

    def test_surveilled_into_the_graveyard_too(self):
        game, _ = table3(lambda prompt, options: options.index("Put into your graveyard") if "Put into your graveyard" in options else 0)
        a = game.seats[0]
        a.library, a.graveyard, a.battlefield = [NARCOMOEBA], [], []
        game.surveil(a, 1)
        run_stack(game)
        self.assertEqual([p.card for p in a.battlefield], [NARCOMOEBA])

    def test_drawn_or_discarded_it_stays(self):
        game, _ = table3()
        a = game.seats[0]
        a.library, a.hand, a.graveyard = [NARCOMOEBA], [], []
        game.draw(a, 1)
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual(a.graveyard, [NARCOMOEBA])


class CreepingChillTests(unittest.TestCase):
    def test_milled_it_drains_from_exile(self):
        game, a = milled(CHILL)
        self.assertEqual(a.exile, [CHILL])
        self.assertEqual([s.life for s in game.seats], [43, 37, 37])

    def test_cast_it_drains_too(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield = [CHILL], lands(4)
        game._perform(a, CAST + CHILL.name)
        run_stack(game)
        self.assertEqual([s.life for s in game.seats], [43, 37, 37])


if __name__ == "__main__":
    unittest.main()
