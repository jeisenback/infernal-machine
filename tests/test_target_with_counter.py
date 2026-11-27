"""A target "with a +1/+1 counter on it" (or a -1/-1 or stun counter), from the cards' real Oracle text: the qualifier is part of the
target kind `_PERMANENT_KIND` reads, and `Game._target_options` offers only the creatures with such a counter. All 13 cards whose only
gap it was are fully playable. Helium Squirter ("{1}: Target creature with a +1/+1 counter on it gains flying until end of turn.")
offers the Bear with a counter, not the Bear without one; with neither it can't be activated. Crumbling Ashes destroys the Ogre with a
-1/-1 counter at the beginning of the upkeep and leaves the Bear without one. Hog-Monkey's "target creature you control with a +1/+1
counter on it" passes over the opponent's creature with one."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from tests.helpers import BEAR, OGRE, activate, fire, lands, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Aquastrand Spider", "Crumbling Ashes", "Cytoplast Manipulator", "Cytospawn Shambler", "Helium Squirter", "Hog-Monkey",
         "Liliana, Death Wielder", "Ollenbock Escort", "Plaxcaster Frogling", "Sporeback Troll", "Steppe Glider", "Tempered Veteran",
         "Vigean Graftmage"]
SQUIRTER, ASHES, HOG = REAL["Helium Squirter"], REAL["Crumbling Ashes"], REAL["Hog-Monkey"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_target_with_counter).
MUTATIONS = [
    ("infernal_machine/game.py", "                if counter_needed and not permanent.counters.get(counter_needed[1]):",
     "                if False:", "only a creature with the counter"),
    ("infernal_machine/effects/outcomes.py", 'r"| with an? (?:\\+1/\\+1|-1/-1|stun) counter on it)?)")', 'r")?)")', "the qualifier is read"),
]


def countered(card, kind, sick=False):
    permanent = Permanent(card, sick=sick)
    permanent.counters[kind] = 1
    return permanent


class TargetWithCounterTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_only_a_creature_with_the_counter_is_offered(self):
        game, _ = table3()
        a = game.seats[0]
        plain, marked = Permanent(BEAR, sick=False), countered(BEAR, "+1/+1")
        a.battlefield = [Permanent(SQUIRTER, sick=False), plain, marked] + lands(1)
        activate(game, a, "gains flying")
        self.assertEqual((game.has_keyword(marked, "flying"), game.has_keyword(plain, "flying")), (True, False))

    def test_with_none_it_cant_be_activated(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(SQUIRTER, sick=False), Permanent(BEAR, sick=False)] + lands(1)
        self.assertFalse(any(x.startswith(ACTIVATE) and "gains flying" in x for x in game.legal_actions(a)))

    def test_a_minus_counter_destroys_only_that_creature(self):
        game, _ = table3()
        a, b, _ = game.seats
        ashes, ogre, bear = Permanent(ASHES), countered(OGRE, "-1/-1"), Permanent(BEAR)
        a.battlefield, b.battlefield = [ashes], [ogre, bear]
        fire(game, a, ashes, "upkeep")
        self.assertEqual([p.card.name for p in b.battlefield], ["Bear"])

    def test_one_you_control(self):
        game, _ = table3()
        a, b, _ = game.seats
        hog, theirs = Permanent(HOG), countered(OGRE, "+1/+1")
        a.battlefield, b.battlefield = [hog], [theirs]
        fire(game, a, hog, "combat")
        self.assertFalse(game.has_keyword(theirs, "menace"))
        mine = countered(BEAR, "+1/+1")
        a.battlefield.append(mine)
        fire(game, a, hog, "combat")
        self.assertTrue(game.has_keyword(mine, "menace"))


if __name__ == "__main__":
    unittest.main()
