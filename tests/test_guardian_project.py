"""Guardian Project (#320 by EDHREC rank), from its real Oracle text: "Whenever a nontoken creature you control enters, if it doesn't have
the same name as another creature you control or a creature card in your graveyard, draw a card." A first Bear draws a card; a second
Bear (the same name as the first) doesn't; an Ogre with an Ogre card in the graveyard doesn't; an opponent's creature doesn't."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, OGRE, enter, run_stack, table3, wording_unlocked
from tests.real import REAL

PROJECT = REAL["Guardian Project"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_guardian_project).
MUTATIONS = [
    ("infernal_machine/game.py", 'p is not subject and "Creature" in p.card.type_line and p.card.name == subject.card.name for p in seat.battlefield',
     'False for p in seat.battlefield', "another creature you control"),
    ("infernal_machine/game.py", 'and not any("Creature" in c.type_line and c.name == subject.card.name for c in seat.graveyard)',
     'and True', "a creature card in your graveyard"),
    ("infernal_machine/game.py", 'p is not subject and "Creature" in p.card.type_line and p.card.name == subject.card.name for p in seat.battlefield',
     '"Creature" in p.card.type_line and p.card.name == subject.card.name for p in seat.battlefield', "not the creature itself"),
]


def project():
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield, a.hand, a.library = [Permanent(PROJECT)], [], [BEAR] * 5
    return game, a, b


def enters(game, seat, card):
    enter(game, seat, card)
    run_stack(game)


class GuardianProjectTests(unittest.TestCase):
    def test_it_is_playable(self):
        wording_unlocked(self, ["Guardian Project"])

    def test_a_new_name_draws_and_a_repeated_one_doesnt(self):
        game, a, _ = project()
        enters(game, a, BEAR)
        enters(game, a, BEAR)
        self.assertEqual(len(a.hand), 1)

    def test_not_with_that_name_in_the_graveyard(self):
        game, a, _ = project()
        a.graveyard = [OGRE]
        enters(game, a, OGRE)
        self.assertEqual(len(a.hand), 0)

    def test_not_an_opponents_creature(self):
        game, a, b = project()
        enters(game, b, BEAR)
        self.assertEqual(len(a.hand), 0)


if __name__ == "__main__":
    unittest.main()
