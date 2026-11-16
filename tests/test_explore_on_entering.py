"""Issue #795: "When this creature enters, it explores." (CR 701.44), from the cards' real Oracle text. All fifteen cards whose only gap it
was are fully playable; on Cenote Scout, the most played: a land on top goes to the hand, anything else puts a +1/+1 counter on it and
may go to the graveyard, and a creature that is gone by the time the trigger resolves still explores, without the counter (CR 701.44)."""

import unittest

from tests.helpers import BEAR, FOREST, enter, pick, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Cenote Scout", "Pathfinding Axejaw", "Merfolk Branchwalker", "River Herald Scout", "River Herald Guide", "Siren Lookout",
         "Tishana's Wayfinder", "Ixalli's Diviner", "Kinjalli's Dawnrunner", "Brazen Buccaneers", "Dire Fleet Interloper", "Seekers' Squire",
         "Queen's Agent", "Emissary of Sunrise", "Sunrise Seeker"]
SCOUT = REAL["Cenote Scout"]


def scout_enters(top, policy=None, leaves_first=False):
    """Cenote Scout enters for seat 0 with `top` on top of its library; its trigger resolves (after it left, with `leaves_first`)."""
    game, _ = table3(policy)
    a = game.seats[0]
    a.library = [top, BEAR]
    scout = enter(game, a, SCOUT)
    if leaves_first:
        game.destroy(scout)
    run_stack(game)
    return game, a, scout


class ExploreOnEnteringTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_a_land_on_top_goes_to_the_hand(self):
        _, a, scout = scout_enters(FOREST)
        self.assertEqual((a.hand, a.library, scout.counters), ([FOREST], [BEAR], {}))

    def test_anything_else_gives_a_counter_and_may_go_to_the_graveyard(self):
        for answer, library, graveyard in (("Keep", [BEAR, BEAR], []), ("Put", [BEAR], [BEAR])):
            game, a, scout = scout_enters(BEAR, pick(answer))
            self.assertEqual((scout.counters, a.hand, a.library, a.graveyard), ({"+1/+1": 1}, [], library, graveyard), answer)

    def test_a_creature_gone_before_it_resolves_still_explores_without_the_counter(self):
        _, a, scout = scout_enters(FOREST, leaves_first=True)
        self.assertEqual((a.hand, a.library), ([FOREST], [BEAR]))
        game, a, scout = scout_enters(BEAR, pick("Put"), leaves_first=True)
        self.assertEqual((scout.counters, sorted(c.name for c in a.graveyard)), ({}, ["Bear", "Cenote Scout"]))


if __name__ == "__main__":
    unittest.main()
