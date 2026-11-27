"""Jump-start (CR 702.133): "You may cast this card from your graveyard by discarding a card in addition to paying its other costs.
Then exile this card.", from the cards' real Oracle text. All six cards are fully playable. Radical Idea ({1}{U}, "Draw a card.") in
the graveyard, with two lands and a Bear in hand: it is cast, the Bear is discarded, a card is drawn and Radical Idea is exiled, not
put back in the graveyard. With an empty hand there is nothing to discard, so it isn't offered; nor with one land."""

import unittest

from infernal_machine.zones import CAST_GRAVEYARD
from tests.helpers import BEAR, FOREST, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Chemister's Insight", "Direct Current", "Maximize Altitude", "Maximize Velocity", "Quasiduplicate", "Radical Idea"]
IDEA = REAL["Radical Idea"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_jump_start).
MUTATIONS = [
    ("infernal_machine/effects/costs.py", 'GraveyardCast("Jump-start", card.mana_cost, exile_after=True, discard=True)',
     'GraveyardCast("Jump-start", card.mana_cost, discard=True)', "then exiled"),
    ("infernal_machine/effects/costs.py", 'GraveyardCast("Jump-start", card.mana_cost, exile_after=True, discard=True)',
     'GraveyardCast("Jump-start", card.mana_cost, exile_after=True)', "a card is discarded"),
]


def seat(hand, mana=2):
    game, _ = table3()
    a = game.seats[0]
    a.graveyard, a.hand, a.battlefield, a.library = [IDEA], list(hand), lands(mana), [FOREST] * 5
    return game, a


def offered(game, a):
    return CAST_GRAVEYARD + IDEA.name in game.legal_actions(a)


class JumpStartTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_cast_from_the_graveyard_discarding_a_card_then_exiled(self):
        game, a = seat([BEAR])
        self.assertTrue(offered(game, a))
        game._perform(a, CAST_GRAVEYARD + IDEA.name)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard], [c.name for c in a.exile]),
                         (["Forest"], ["Bear"], ["Radical Idea"]))

    def test_not_without_a_card_to_discard_or_the_mana(self):
        self.assertFalse(offered(*seat([])))
        self.assertFalse(offered(*seat([BEAR], mana=1)))


if __name__ == "__main__":
    unittest.main()
