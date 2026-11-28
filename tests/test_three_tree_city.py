"""Three Tree City (#180 by EDHREC rank), from its real Oracle text: "{2}, {T}: Choose a color. Add an amount of mana of that color equal
to the number of creatures you control of the chosen type." It chose Elf as it entered; with five Elves and two other lands it pays
for a {G}{G}{G}{G}{G} spell (the lands pay its {2}); with two Elves it can't (tapped for one mana each, the three lands make only three),
and creatures of another type don't count."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, ELF, lands, real, table3, wording_unlocked
from tests.real import REAL

CITY = REAL["Three Tree City"]
GIANT = real("Big Green", "{G}{G}{G}{G}{G}", "Creature — Giant", "", "5", "5")

# The guards these tests are there to catch (python tools/mutate.py tests.test_three_tree_city).
MUTATIONS = [
    ("infernal_machine/game.py", 'return sum("Creature" in p.card.type_line and wanted in self.subtypes(p) for p in controller.battlefield) if wanted else 0',
     'return sum("Creature" in p.card.type_line for p in controller.battlefield) if wanted else 0', "only the chosen type"),
]


def castable(*creatures):
    game, _ = table3()
    a = game.seats[0]
    city = Permanent(CITY, sick=False)
    city.chosen_type = "Elf"
    a.battlefield = [city] + lands(2) + [Permanent(c, sick=False) for c in creatures]
    a.hand = [GIANT]
    return any(x == CAST + GIANT.name for x in game.legal_actions(a))


class ThreeTreeCityTests(unittest.TestCase):
    def test_it_is_playable(self):
        wording_unlocked(self, ["Three Tree City"])

    def test_mana_for_each_creature_of_the_chosen_type(self):
        self.assertEqual((castable(*[ELF] * 5), castable(ELF, ELF), castable(ELF, ELF, BEAR, BEAR, BEAR)), (True, False, False))


if __name__ == "__main__":
    unittest.main()
