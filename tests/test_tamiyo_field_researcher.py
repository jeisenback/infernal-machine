"""Tamiyo, Field Researcher, from its real Oracle text: "+1: Choose up to two target creatures. Until your next turn, whenever either of
those creatures deals combat damage, you draw a card." (not another creature; still through an opponent's turn; over once your next turn
begins) and "−2: Tap up to two target nonland permanents. They don't untap during their controller's next untap step." (only that one)."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, SOL_RING, choose, combat_damage, next_turn, real, run_stack, table3, untap_step

TAMIYO = real("Tamiyo, Field Researcher", "{1}{G}{W}{U}", "Legendary Planeswalker — Tamiyo", "+1: Choose up to two target creatures. "
              "Until your next turn, whenever either of those creatures deals combat damage, you draw a card.\n−2: Tap up to two target "
              "nonland permanents. They don't untap during their controller's next untap step.\n−7: Draw three cards. You get an emblem "
              "with \"You may cast spells from your hand without paying their mana costs.\"", None, None, colors=("G", "U", "W"))


# The guards these tests are there to catch (python tools/mutate.py tests.test_tamiyo_field_researcher).
MUTATIONS = [
    ("infernal_machine/game.py", "d.until_your_turn and d.controller is seat", "False", "the +1 ends as your next turn begins"),
    ("infernal_machine/game.py", "                if permanent.skips_next_untap:  # Sleep of the Dead: this untap step only\n"
     "                    permanent.skips_next_untap = False\n", "                if False:\n                    pass\n",
     "the -2 skips the next untap step"),
]

def first_two(prompt, options):
    """Choose the first target offered each time (the targets are distinct), and pass on anything else."""
    return 0


def activate(text, mine=(), theirs=(), targets=()):
    """Seat 0 activates the Tamiyo ability whose text contains `text`, choosing `targets` (else the first offered each time); `mine` and
    `theirs` are the permanents of seats 0 and 1."""
    game, players = table3(first_two)
    a, b, _ = game.seats
    if targets:
        players[0].policy = choose(game, *targets)
    a.battlefield = [*mine, Permanent(TAMIYO, loyalty=4)]
    b.battlefield = list(theirs)
    a.library = [BEAR] * 10
    game.step, game.active = "main1", a.index
    (action,) = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Tamiyo") and text in x]
    game._perform(a, action)
    run_stack(game)
    return game, a, b


class PlusOneTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(TAMIYO), [])

    def test_a_chosen_creature_dealing_combat_damage_draws_a_card_and_another_does_not(self):
        first, second, other = Permanent(BEAR, sick=False), Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)
        game, a, b = activate("+1:", mine=[first, second, other])
        hand = len(a.hand)
        combat_damage(game, other, b)
        self.assertEqual(len(a.hand), hand)
        combat_damage(game, first, b)
        self.assertEqual(len(a.hand), hand + 1)

    def test_it_lasts_through_an_opponents_turn_and_ends_as_your_next_turn_begins(self):
        first = Permanent(BEAR, sick=False)
        game, a, b = activate("+1:", mine=[first, Permanent(BEAR, sick=False)])
        next_turn(game, b)
        hand = len(a.hand)
        combat_damage(game, first, b)  # (as a blocker would, on their turn)
        self.assertEqual(len(a.hand), hand + 1)
        next_turn(game, a)
        combat_damage(game, first, b)
        self.assertEqual(len(a.hand), hand + 1)


class MinusTwoTests(unittest.TestCase):
    def test_the_tapped_permanents_skip_their_controllers_next_untap_only(self):
        ogre, ring = Permanent(OGRE), Permanent(SOL_RING)
        game, a, b = activate("−2:", theirs=[ogre, ring], targets=[ogre, ring])
        self.assertEqual((ogre.tapped, ring.tapped), (True, True))
        untap_step(game, b)
        self.assertEqual((ogre.tapped, ring.tapped), (True, True))
        untap_step(game, b)
        self.assertEqual((ogre.tapped, ring.tapped), (False, False))


if __name__ == "__main__":
    unittest.main()
