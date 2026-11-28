"""Two staples, from the cards' real Oracle text. Drannith Magistrate (#781 by EDHREC rank): "Your opponents can't cast spells from
anywhere other than their hands." An opponent can't cast their commander from the command zone but can cast a Bear from their hand,
and the Magistrate's controller still casts their own commander. Mindcrank (#992): "Whenever an opponent loses life, that player mills
that many cards." An opponent losing 3 life mills 3; its controller losing life mills nothing."""

import unittest

from infernal_machine.game import CAST, CAST_COMMANDER, Permanent
from tests.helpers import BEAR, COMMANDER, FOREST, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Drannith Magistrate", "Mindcrank"]
MAGISTRATE, CRANK = REAL["Drannith Magistrate"], REAL["Mindcrank"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_drannith_and_mindcrank).
MUTATIONS = [
    ("infernal_machine/game.py", 'key == "opp_hand_only" and owner is not seat for owner, _, key in self._static_rules()):',
     'key == "opp_hand_only" for owner, _, key in self._static_rules()):', "only its controller's opponents"),
    ("infernal_machine/game.py", "        if (not from_hand or from_command_zone or graveyard is not None) and any(",
     "        if any(", "their hand is still allowed"),
]


def casts(game, seat, name, prefix=CAST):
    return any(x == prefix + name for x in game.legal_actions(seat))


class DrannithAndMindcrankTests(unittest.TestCase):
    def test_both_are_playable(self):
        wording_unlocked(self, CARDS)

    def test_opponents_cast_only_from_their_hands(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(MAGISTRATE)] + lands(2)
        b.battlefield, b.hand = lands(2), [BEAR]
        for seat in (a, b):
            seat.command_zone = [COMMANDER]
        game.active = 1  # (b's turn, so b may cast at sorcery speed)
        self.assertEqual((casts(game, b, COMMANDER.name, CAST_COMMANDER), casts(game, b, BEAR.name)), (False, True))
        game.active = 0
        self.assertTrue(casts(game, a, COMMANDER.name, CAST_COMMANDER))

    def test_an_opponent_losing_life_mills_that_many(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(CRANK)]
        a.library = b.library = [FOREST] * 10
        game.change_life(b, -3)
        run_stack(game)
        game.change_life(a, -2)
        run_stack(game)
        self.assertEqual((len(b.graveyard), len(a.graveyard)), (3, 0))


if __name__ == "__main__":
    unittest.main()
