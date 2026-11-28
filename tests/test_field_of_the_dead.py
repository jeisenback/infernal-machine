"""Field of the Dead (#499 by EDHREC rank), from its real Oracle text: "Whenever this land or another land you control enters, if you
control seven or more lands with different names, create a 2/2 black Zombie creature token." With six differently named lands, a
seventh name entering makes a Zombie; seven lands of which two share a name don't; six land names and two creatures don't (only lands
count); an opponent's land entering doesn't."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from tests.helpers import BEAR, OGRE, enter, run_stack, table3, wording_unlocked
from tests.real import REAL

FIELD = REAL["Field of the Dead"]
NAMED = [Card(name=f"Land {n}", type_line="Land") for n in range(8)]

# The guards these tests are there to catch (python tools/mutate.py tests.test_field_of_the_dead).
MUTATIONS = [
    ("infernal_machine/game.py", "return len({p.card.name for p in seat.battlefield if is_land(p.card)}) >= condition.count",
     "return len([p.card.name for p in seat.battlefield if is_land(p.card)]) >= condition.count", "different names"),
    ("infernal_machine/game.py", "return len({p.card.name for p in seat.battlefield if is_land(p.card)}) >= condition.count",
     "return len({p.card.name for p in seat.battlefield}) >= condition.count", "lands only"),
]


def zombies(seat):
    return sum(p.card.name == "Zombie" for p in seat.battlefield)


def field(*others):
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(FIELD)] + [Permanent(c) for c in others]
    return game, a, b


class FieldOfTheDeadTests(unittest.TestCase):
    def test_it_is_playable(self):
        wording_unlocked(self, ["Field of the Dead"])

    def test_the_seventh_name_makes_a_zombie(self):
        game, a, _ = field(*NAMED[:5])  # six names with the Field
        enter(game, a, NAMED[5])
        run_stack(game)
        self.assertEqual(zombies(a), 1)

    def test_not_with_a_repeated_name(self):
        game, a, _ = field(*NAMED[:4], NAMED[0])  # five names, six lands
        enter(game, a, NAMED[0])
        run_stack(game)
        self.assertEqual(zombies(a), 0)

    def test_only_lands_count(self):
        game, a, _ = field(*NAMED[:4], BEAR, OGRE)  # five land names
        enter(game, a, NAMED[4])
        run_stack(game)
        self.assertEqual(zombies(a), 0)

    def test_not_an_opponents_land(self):
        game, a, b = field(*NAMED[:6])
        enter(game, b, NAMED[7])
        run_stack(game)
        self.assertEqual(zombies(a), 0)


if __name__ == "__main__":
    unittest.main()
