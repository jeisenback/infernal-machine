""""When this artifact enters, mill a card. You may play that card this turn." (Tablet of Discovery)."""

import unittest

from infernal_machine.report import unsupported_lines
from infernal_machine.zones import CAST_MILLED, PLAY_MILLED
from tests.helpers import BEAR, FOREST, enter, lands, real, run_stack, table3

TABLET = real("Tablet of Discovery", "{2}{R}", "Artifact", "When this artifact enters, mill a card. You may play that card this turn. (To mill "
              "a card, put the top card of your library into your graveyard.)\n{T}: Add {R}.\n{T}: Add {R}{R}. Spend this mana only to cast "
              "instant and sorcery spells.", colors=("R",))


def mill(top, graveyard=()):
    game, _ = table3()
    a = game.seats[0]
    a.library, a.graveyard, a.battlefield = [top, BEAR], list(graveyard), lands(2)
    game.active, game.step = 0, "main1"
    enter(game, a, TABLET)
    run_stack(game)
    return game, a


class TabletOfDiscoveryTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(TABLET), [])

    def test_the_milled_land_can_be_played_this_turn(self):
        game, a = mill(FOREST)
        self.assertIn(PLAY_MILLED + "Forest", game.legal_actions(a))
        game._perform(a, PLAY_MILLED + "Forest")
        self.assertIn(FOREST, [p.card for p in a.battlefield])
        self.assertEqual(a.graveyard, [])

    def test_the_milled_spell_can_be_cast_this_turn(self):
        game, a = mill(BEAR)
        game._perform(a, CAST_MILLED + "Bear")
        run_stack(game)
        bear = next(p for p in a.battlefield if p.card is BEAR)
        game.destroy(bear)  # back in the graveyard the same turn, the card is a new object: the permission is used up
        self.assertIn(BEAR, a.graveyard)
        self.assertNotIn(CAST_MILLED + "Bear", game.legal_actions(a))

    def test_not_next_turn_nor_a_card_already_there(self):
        game, a = mill(FOREST, graveyard=[BEAR])
        self.assertNotIn(CAST_MILLED + "Bear", game.legal_actions(a))
        game.turn += 1
        self.assertFalse(any(action.startswith(PLAY_MILLED) for action in game.legal_actions(a)))

    def test_not_once_the_card_has_left_the_graveyard(self):
        game, a = mill(FOREST)
        a.graveyard.remove(FOREST)
        self.assertNotIn(PLAY_MILLED + "Forest", game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
