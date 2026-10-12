"""A card cast from another player's library or exile is its owner's: it goes to the owner's zones when it leaves the stack or the
battlefield, not to the caster's (CR 108.3, 400.3; issue #318)."""

import unittest

from infernal_machine.game import CAST, CAST_EXILE, Permanent
from tests.helpers import lands, real, run_stack, table3

BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")
BEARS = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", "2", "2")


def plargg(card):
    """Seat A's Plargg and Nassari trigger finds only seat B's `card`, and A casts it free."""
    game, _ = table3()
    a, b, c = game.seats
    a.library, b.library, c.library = [], [card], []
    game.exile_until_nonland_and_cast(a, 1)
    return game, a, b, c


class PlarggTests(unittest.TestCase):
    def test_an_instant_goes_to_its_owners_graveyard(self):
        game, a, b, c = plargg(BOLT)
        run_stack(game)
        self.assertEqual((b.graveyard, a.graveyard), ([BOLT], []))

    def test_a_countered_spell_goes_to_its_owners_graveyard(self):
        game, a, b, c = plargg(BOLT)
        game.counter(game.stack[-1])
        self.assertEqual((b.graveyard, a.graveyard), ([BOLT], []))

    def test_a_creature_is_its_owners_card_on_the_caster_battlefield(self):
        game, a, b, c = plargg(BEARS)
        run_stack(game)
        [bears] = a.battlefield
        self.assertEqual(game.owner_of(bears).index, b.index)
        game.destroy(bears)
        run_stack(game)
        self.assertEqual((b.graveyard, a.graveyard), ([BEARS], []))

    def test_a_creature_returned_to_hand_is_in_its_owners_hand(self):
        game, a, b, c = plargg(BEARS)
        run_stack(game)
        game.return_to_hand(a.battlefield[0])
        self.assertEqual((b.hand, a.hand), ([BEARS], []))


class RagavanTests(unittest.TestCase):
    def test_a_spell_cast_from_the_exiled_top_card_goes_to_its_owners_graveyard(self):
        game, _ = table3()
        a, b, c = game.seats
        b.library = [BOLT]
        a.battlefield = lands(1)
        game.exile_top_of_other(a, b)
        game._perform(a, CAST_EXILE + BOLT.name)
        run_stack(game)
        self.assertEqual((b.graveyard, a.graveyard), ([BOLT], []))


class OwnCardsTests(unittest.TestCase):
    def test_a_spell_cast_from_your_own_hand_goes_to_your_graveyard(self):
        game, _ = table3()
        a, b, c = game.seats
        a.hand, a.battlefield = [BOLT], lands(1)
        game._perform(a, CAST + BOLT.name)
        run_stack(game)
        self.assertEqual((a.graveyard, b.graveyard), ([BOLT], []))

    def test_a_stolen_creature_still_goes_to_its_owner(self):
        game, _ = table3()
        a, b, c = game.seats
        stolen = Permanent(BEARS, owner=b)
        a.battlefield = [stolen]
        game.destroy(stolen)
        run_stack(game)
        self.assertEqual((b.graveyard, a.graveyard), ([BEARS], []))


if __name__ == "__main__":
    unittest.main()
