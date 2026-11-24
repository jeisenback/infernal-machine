"""Issue #850: Mayhem {cost}, "(You may cast this card from your graveyard for {cost} if you discarded it this turn. Timing rules still
apply.)", from the cards' real Oracle text. All seven cards whose only gap it was are fully playable, and three more. Electro's Bolt ({2}{R}, "deals 4
damage to target creature"; Mayhem {1}{R}) discarded this turn may be cast from its owner's graveyard for {1}{R}: it kills an Ogre and
goes back to the graveyard, from where it may not be cast again that turn; put there some other way (milled), or discarded on an earlier turn, it may not."""

import unittest

from infernal_machine.game import CAST_GRAVEYARD, Permanent
from tests.helpers import OGRE, choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Chameleon, Master of Disguise", "Ultimate Green Goblin", "Electro's Bolt", "Abomination, World Ravager", "Raging Goblinoids",
         "Spider-Islanders", "Sadistic Slash",
         "Green Goblin, Back for More", "Swarm, Being of Bees", "The Squadron Sinister"]  # (and three more with mayhem)
BOLT = REAL["Electro's Bolt"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_mayhem).
MUTATIONS = [
    ("infernal_machine/casting.py", "            if graveyard.mayhem and seat.discarded_on.get(id(card)) != self.game.turn:\n",
     "            if False:\n", "only if it was discarded this turn"),
    ("infernal_machine/game.py", "        seat.discarded_on[id(card)] = self.turn  # Mayhem", "        pass  # Mayhem", "a discard is recorded"),
    ("infernal_machine/game.py", "            seat.discarded_on.pop(id(card), None)  # CR 400.7", "            pass  # CR 400.7", "once a turn"),
    ("infernal_machine/effects/costs.py", "            found.append(GraveyardCast(\"Mayhem\", m[1], mayhem=True))",
     "            found.append(GraveyardCast(\"Mayhem\", m[1]))", "a Mayhem cast is marked as one"),
]


def board():
    """Seat 0 has two lands and Electro's Bolt in hand; seat 1 has an Ogre (3/3)."""
    game, _ = table3()
    a, b, _ = game.seats
    ogre = Permanent(OGRE)
    a.hand, a.battlefield, b.battlefield = [BOLT], lands(2), [ogre]
    return game, a, b, ogre


def offered(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(CAST_GRAVEYARD)]


class MayhemTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_discarded_this_turn_it_is_cast_from_the_graveyard_for_its_mayhem_cost(self):
        game, a, b, ogre = board()
        game.discard(a, 1)
        self.assertEqual(offered(game, a), [CAST_GRAVEYARD + BOLT.name])  # (two lands: {1}{R}, not {2}{R})
        a.player.choose = choose(game, ogre)
        game._perform(a, CAST_GRAVEYARD + BOLT.name)
        run_stack(game)
        game._check_state()
        self.assertEqual((ogre in b.battlefield, a.graveyard), (False, [BOLT]))
        a.battlefield += lands(2)
        b.battlefield.append(Permanent(OGRE))  # (something to target again)
        self.assertEqual(offered(game, a), [])  # (back in the graveyard, a new object: it wasn't discarded, CR 400.7)

    def test_not_a_card_put_there_another_way(self):
        game, a, _, _ = board()
        a.hand, a.graveyard = [], [BOLT]  # (milled, say)
        self.assertEqual(offered(game, a), [])

    def test_not_a_card_discarded_on_an_earlier_turn(self):
        game, a, _, _ = board()
        game.discard(a, 1)
        game.turn += 1
        self.assertEqual(offered(game, a), [])


if __name__ == "__main__":
    unittest.main()
