"""Issue #840: Ravenous, "(This creature enters with X +1/+1 counters on it. If X is 5 or more, draw a card when it enters.)"
(CR 702.156a), read as those two abilities, from the cards' real Oracle text. All eight cards whose only gap it was are fully playable.
Hormagaunt Horde ({X}{G}, 1/1): cast with X = 5 it enters with five +1/+1 counters and its controller draws a card; with X = 4, four
counters and no card."""

import unittest

from infernal_machine.game import CAST, X_PROMPT
from tests.helpers import BEAR, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Aberrant", "Broodlord", "Hormagaunt Horde", "Jacked Rabbit", "Mawloc", "Termagant Swarm", "Tervigon", "Zoanthrope"]
HORDE = REAL["Hormagaunt Horde"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_ravenous).
MUTATIONS = [
    ("infernal_machine/effects/common.py", '"When this creature enters, if X is 5 or more, draw a card."),',
     '"When this creature enters, draw a card."),', "a card only if X is 5 or more"),
    ("infernal_machine/effects/common.py", 'lambda m: "This creature enters with X +1/+1 counters on it.\\n"',
     'lambda m: "This creature enters with a +1/+1 counter on it.\\n"', "X counters"),
    ("infernal_machine/game.py", "            return (x or self.x_value) >= condition.count", "            return self.x_value >= condition.count",
     "the X the creature was cast with"),
]


def cast(x):
    """Seat 0 casts Hormagaunt Horde with X = `x` (its library holds a Bear to draw)."""
    game, _ = table3(lambda prompt, options: options.index(str(x)) if X_PROMPT.matches(prompt) else 0)
    a = game.seats[0]
    a.hand, a.battlefield, a.library = [HORDE], lands(6), [BEAR]
    game._perform(a, CAST + HORDE.name)
    run_stack(game)
    (horde,) = [p for p in a.battlefield if p.card is HORDE]
    return horde, a


class RavenousTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_x_counters_and_a_card_when_x_is_five_or_more(self):
        horde, a = cast(5)
        self.assertEqual((horde.counters, [c.name for c in a.hand]), ({"+1/+1": 5}, ["Bear"]))

    def test_no_card_when_x_is_less(self):
        horde, a = cast(4)
        self.assertEqual((horde.counters, a.hand, a.library), ({"+1/+1": 4}, [], [BEAR]))


if __name__ == "__main__":
    unittest.main()
