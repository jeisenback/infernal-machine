"""Fuse (CR 702.102), from the card's real Oracle text: Wear // Tear may be cast as one spell from the hand, both costs paid ({1}{R}{W})
and both halves done, the left one first; with mana for only one half, only that half is offered."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, CAST_FUSED, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import RELIC, lands, real, run_stack, scryfall, table3

WEAR_TEAR = Card.from_scryfall(scryfall(
    "split",
    {"name": "Wear", "mana_cost": "{1}{R}", "type_line": "Instant",
     "oracle_text": "Destroy target artifact.\nFuse (You may cast one or both halves of this card from your hand.)"},
    {"name": "Tear", "mana_cost": "{W}", "type_line": "Instant",
     "oracle_text": "Destroy target enchantment.\nFuse (You may cast one or both halves of this card from your hand.)"},
    cmc=3.0, colors=["R", "W"]))
ANTHEM = real("Glorious Anthem", "{1}{W}{W}", "Enchantment", "Creatures you control get +1/+1.", colors=("W",))


class FuseTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(WEAR_TEAR), [])

    def test_both_halves_cast_together_destroy_an_artifact_and_an_enchantment(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield, a.hand = lands(3), [WEAR_TEAR]
        b.battlefield = [Permanent(RELIC), Permanent(ANTHEM)]
        game._perform(a, CAST_FUSED + WEAR_TEAR.name)
        run_stack(game)
        self.assertEqual((b.battlefield, sorted(c.name for c in b.graveyard), [c.name for c in a.graveyard]),
                         ([], ["Glorious Anthem", "Relic"], ["Wear // Tear"]))

    def test_with_mana_for_one_half_only_the_halves_are_offered(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield, a.hand = lands(2), [WEAR_TEAR]
        b.battlefield = [Permanent(RELIC), Permanent(ANTHEM)]
        actions = game.legal_actions(a)
        self.assertEqual((CAST_FUSED + WEAR_TEAR.name in actions, CAST + WEAR_TEAR.name in actions, CAST + "Tear" in actions),
                         (False, True, True))


if __name__ == "__main__":
    unittest.main()
