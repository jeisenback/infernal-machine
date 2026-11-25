"""Ascend on an instant or sorcery (CR 702.131b): its controller gets the city's blessing as it resolves if they control ten or more
permanents, from the cards' real Oracle text. Pride of Conquerors cast with ten permanents (two of them lands that pay for it) gives the
Bears +2/+2 and the blessing for good; with nine, +1/+1 and no blessing. Secrets of the Golden City draws three with ten, two with nine.
The Ascend line used to leave the spell unread, so it resolved doing nothing. Fiery Impulse ("Spell mastery — ... deals 3 damage
instead.") is read by the same "deals N damage instead" sentence as Akoum Hellkite."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, OGRE, choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Pride of Conquerors", "Fiery Impulse"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_ascend_spells).
MUTATIONS = [
    ("infernal_machine/game.py", "        if (item.ability is None and not seat.citys_blessing and len(seat.battlefield) >= 10",
     "        if (False and not seat.citys_blessing and len(seat.battlefield) >= 10", "the blessing as the spell resolves"),
    ("infernal_machine/game.py", "        if (item.ability is None and not seat.citys_blessing and len(seat.battlefield) >= 10",
     "        if (item.ability is None and not seat.citys_blessing and len(seat.battlefield) >= 9", "only with ten permanents"),
    ("infernal_machine/effects/spells.py", "             and not _ASCEND.fullmatch(line)]", "             ]", "the keyword line is not a step of the spell"),
]


def cast(name, bears, mana=2, graveyard=(), theirs=()):
    """Seat 0, with `mana` lands and `bears` Bears, casts `name`, aimed at seat 1's first permanent."""
    game, players = table3()
    a, b, _ = game.seats
    a.battlefield = lands(mana) + [Permanent(BEAR, sick=False) for _ in range(bears)]
    a.hand, a.graveyard, a.library = [REAL[name]], list(graveyard), [BEAR] * 5
    b.battlefield = [Permanent(c) for c in theirs]
    players[0].policy = choose(game, *b.battlefield)
    game._perform(a, CAST + name)
    run_stack(game)
    return game, a, b


class AscendSpellTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_ten_permanents_give_the_blessing_as_it_resolves(self):
        game, a, _ = cast("Pride of Conquerors", 8)
        self.assertEqual((game.power(a.battlefield[-1]), a.citys_blessing), (4, True))

    def test_nine_do_not(self):
        game, a, _ = cast("Pride of Conquerors", 7)
        self.assertEqual((game.power(a.battlefield[-1]), a.citys_blessing), (3, False))

    def test_a_sorcery_draws_three_with_the_blessing(self):
        _, a, _ = cast("Secrets of the Golden City", 7, mana=3)
        self.assertEqual((len(a.hand), a.citys_blessing), (3, True))
        _, a, _ = cast("Secrets of the Golden City", 6, mana=3)
        self.assertEqual(len(a.hand), 2)

    def test_spell_mastery_deals_three(self):
        spells = [REAL["Pride of Conquerors"], REAL["Secrets of the Golden City"]]
        _, _, b = cast("Fiery Impulse", 0, mana=1, graveyard=spells, theirs=[OGRE])
        self.assertEqual([p.damage for p in b.battlefield], [3])
        _, _, b = cast("Fiery Impulse", 0, mana=1, graveyard=spells[:1], theirs=[OGRE])
        self.assertEqual([p.damage for p in b.battlefield], [2])


if __name__ == "__main__":
    unittest.main()
