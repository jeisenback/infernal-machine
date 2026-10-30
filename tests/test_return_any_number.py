"""Paradoxical Outcome: "Return any number of target nonland, nontoken permanents you control to their owners' hands. Draw a card for
each card returned to your hand this way." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, SPIRIT, lands, real, run_stack, table3

OUTCOME = real("Paradoxical Outcome", "{3}{U}", "Instant", "Return any number of target nonland, nontoken permanents you control to their "
               "owners' hands. Draw a card for each card returned to your hand this way.")
STOLEN = Card(name="Stolen", type_line="Creature — Test", power="1", toughness="1")


def cast(take, mine=(BEAR, RELIC, FOREST, SPIRIT), stolen=False):
    """Cast Paradoxical Outcome, choosing the first `take` targets offered. Returns the game, the caster and the options offered."""
    offered: list[list[str]] = []

    def policy(prompt, options):
        offered.append(list(options))
        return 0 if len(offered) <= take else options.index("No target")
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    a.hand, a.library = [OUTCOME], [OGRE] * 5
    a.battlefield = lands(4) + [Permanent(card) for card in mine]
    b.battlefield = [Permanent(OGRE)]  # not theirs to return
    if stolen:
        theirs = Permanent(STOLEN)
        theirs.owner = b
        a.battlefield.append(theirs)
    game._perform(a, CAST + OUTCOME.name)
    run_stack(game)
    return game, a, offered


class ParadoxicalOutcomeTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(OUTCOME), [])

    def test_two_returned_draw_two(self):
        game, a, _ = cast(2)
        self.assertEqual(sorted(c.name for c in a.hand), ["Bear", "Ogre", "Ogre", "Relic"])

    def test_lands_and_tokens_are_not_offered(self):
        _, _, offered = cast(0)
        self.assertEqual(sorted(o.split(" ")[0] for o in offered[0] if o != "No target"), ["Bear", "Relic"])

    def test_none_returned_draws_none(self):
        game, a, _ = cast(0)
        self.assertEqual(a.hand, [])

    def test_a_card_that_goes_to_another_players_hand_is_not_counted(self):
        game, a, _ = cast(1, mine=(), stolen=True)
        self.assertEqual(game.seats[1].hand, [STOLEN])
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
