"""Mass reanimation staples, from the cards' real Oracle text. Living Death (#447 by EDHREC rank): each player exiles the creature cards
in their graveyard, sacrifices their creatures, then puts the exiled cards onto the battlefield, so the creatures sacrificed stay in
the graveyard and each player's cards come back under that player's control; a land card in a graveyard stays. Rise of the Dark Realms
(#479): every graveyard's creature cards come back under its caster's control (still their owners' cards)."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, FOREST, OGRE, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Living Death", "Rise of the Dark Realms"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_mass_reanimation).
MUTATIONS = [
    ("infernal_machine/game.py", "            self.sacrifice(seat, \"creature\", None)\n        for seat, cards in exiled:",
     "            pass\n        for seat, cards in exiled:", "its creatures are sacrificed"),
    ("infernal_machine/game.py", '            cards = [c for c in seat.graveyard if "Creature" in c.type_line]',
     "            cards = list(seat.graveyard)", "only creature cards"),
    ("infernal_machine/game.py", "                    self._enter(seat, Permanent(card, sick=True, loyalty=_starting_loyalty(card), owner=seat))",
     "                    self._enter(self.seats[0], Permanent(card, sick=True, loyalty=_starting_loyalty(card), owner=seat))",
     "each under its own player's control"),
]


def names(cards):
    return sorted(getattr(c, "card", c).name for c in cards)


def cast(name, mana):
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield, a.graveyard, a.hand = lands(mana) + [Permanent(OGRE)], [BEAR, FOREST], [REAL[name]]
    b.battlefield, b.graveyard = [Permanent(BEAR)], [OGRE]
    game._perform(a, CAST + name)
    run_stack(game)
    return game, a, b


class MassReanimationTests(unittest.TestCase):
    def test_both_are_playable(self):
        wording_unlocked(self, CARDS)

    def test_living_death_swaps_graveyards_and_battlefields(self):
        game, a, b = cast("Living Death", 5)
        creatures = lambda seat: names(p for p in seat.battlefield if "Creature" in p.card.type_line)
        self.assertEqual((creatures(a), creatures(b)), (["Bear"], ["Ogre"]))
        self.assertEqual((names(a.graveyard), names(b.graveyard)), (["Forest", "Living Death", "Ogre"], ["Bear"]))

    def test_rise_of_the_dark_realms_takes_every_graveyard(self):
        game, a, b = cast("Rise of the Dark Realms", 9)
        mine = [p for p in a.battlefield if "Creature" in p.card.type_line]
        self.assertEqual((names(mine), names(b.graveyard), names(a.graveyard)), (["Bear", "Ogre", "Ogre"], [], ["Forest", "Rise of the Dark Realms"]))
        self.assertTrue(any(p.owner is b for p in mine))


if __name__ == "__main__":
    unittest.main()
