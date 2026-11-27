"""Graft N (CR 702.58): "This creature enters with N +1/+1 counters on it. Whenever another creature enters, you may move a +1/+1
counter from this creature onto it.", from the cards' real Oracle text. All three cards whose only gap it was are fully playable.
Vigean Hydropon enters with five counters; a Bear entering after it (anyone's: "another creature") takes one, leaving four; declined,
it takes none. Simic Initiate (graft 1) gives its only counter to the first Bear and has none for the second. Llanowar Reborn, a land,
enters with one too and gives it to a creature. A Hydropon destroyed with its trigger on the stack moves nothing."""

import unittest

from tests.helpers import BEAR, enter, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Llanowar Reborn", "Simic Initiate", "Vigean Hydropon"]
HYDROPON, INITIATE, REBORN = REAL["Vigean Hydropon"], REAL["Simic Initiate"], REAL["Llanowar Reborn"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_graft).
MUTATIONS = [
    ("infernal_machine/effects/families/counters.py", "any(source in s.battlefield for s in game.seats)", "True", "not once it has left"),
    ("infernal_machine/effects/common.py", "{_WORDS[int(m[1])]} +1/+1 {'counter' if m[1] == '1' else 'counters'} \"\n        \"on it.",
     "a +1/+1 counter \"\n        \"on it.", "it enters with N"),
]


def decline(prompt, options):
    return len(options) - 1


def graft(card, *policies):
    game, _ = table3(*policies)
    a, b, _ = game.seats
    source = enter(game, a, card)
    run_stack(game)
    return game, a, b, source


def plus(permanent):
    return permanent.counters.get("+1/+1", 0)


class GraftTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_it_enters_with_n_and_moves_one_onto_another_creature(self):
        game, _, b, hydropon = graft(HYDROPON)
        self.assertEqual(plus(hydropon), 5)
        bear = enter(game, b, BEAR)  # (an opponent's creature too)
        run_stack(game)
        self.assertEqual((plus(hydropon), plus(bear)), (4, 1))

    def test_declined_nothing_moves(self):
        game, a, _, hydropon = graft(HYDROPON, decline)
        bear = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual((plus(hydropon), plus(bear)), (5, 0))

    def test_with_none_left_nothing_moves(self):
        game, a, _, initiate = graft(INITIATE)
        first = enter(game, a, BEAR)
        run_stack(game)
        second = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual((plus(initiate), plus(first), plus(second)), (0, 1, 0))

    def test_not_once_it_has_left_the_battlefield(self):
        game, a, _, hydropon = graft(HYDROPON)
        bear = enter(game, a, BEAR)
        game.destroy(hydropon)
        run_stack(game)
        self.assertEqual(plus(bear), 0)

    def test_a_land_with_graft(self):
        game, a, _, reborn = graft(REBORN)
        bear = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual((plus(reborn), plus(bear), reborn.tapped), (0, 1, True))


if __name__ == "__main__":
    unittest.main()
