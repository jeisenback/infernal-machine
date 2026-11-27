""""If one or more +1/+1 counters would be put on <whom>, that many plus one +1/+1 counters are put on it instead." for the kinds the
exact Hardened Scales sentences don't name, from the cards' real Oracle text. All four cards are fully playable. Solid Ground: on any
permanent you control (an artifact too); Mowu, Loyal Companion: only on itself, not on a Bear; Caradora, Heart of Alacria: on a creature
or a Vehicle, not on another artifact; Mauhur, Uruk-hai Captain: on an Army, Goblin or Orc, not on a Bear. None of them on an opponent's
permanent; with two of them, each adds one."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, real, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Solid Ground", "Mowu, Loyal Companion", "Caradora, Heart of Alacria", "Mauhúr, Uruk-hai Captain"]
GROUND, MOWU, CARADORA, MAUHUR = (REAL[n] for n in CARDS)
VEHICLE = real("Cart", "{2}", "Artifact — Vehicle", "Crew 1", "3", "3")
RELIC = real("Relic", "{1}", "Artifact", "")
ORC = real("Orc Grunt", "{1}{B}", "Creature — Orc Warrior", "", "2", "2")

# The guards these tests are there to catch (python tools/mutate.py tests.test_plus_one_counters).
MUTATIONS = [
    ("infernal_machine/game.py", 'count += sum(p is receiver if kind == "self" else _permanent_matches(kind, card)', 'count += sum(True if kind == "self" else _permanent_matches(kind, card)',
     "\"on CARDNAME\": only itself"),
    ("infernal_machine/game.py", 'count += sum(p is receiver if kind == "self" else _permanent_matches(kind, card)', 'count += sum(p is receiver if kind == "self" else True',
     "only the kinds it names"),
]


def counters_on(source_cards, receiver_card, theirs=False):
    """Seat 0 has `source_cards`; three +1/+1 counters are put on a `receiver_card` of seat 0's (seat 1's if `theirs`)."""
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(c) for c in source_cards]
    receiver = Permanent(receiver_card)
    (b if theirs else a).battlefield.append(receiver)
    game.put_counters(receiver, "+1/+1", 3)
    return receiver.counters.get("+1/+1")


class PlusOneCountersTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_on_any_permanent_you_control(self):
        self.assertEqual((counters_on([GROUND], RELIC), counters_on([GROUND], BEAR), counters_on([GROUND], BEAR, theirs=True)), (4, 4, 3))

    def test_only_on_itself(self):
        game, _ = table3()
        a = game.seats[0]
        mowu, bear = Permanent(MOWU), Permanent(BEAR)
        a.battlefield = [mowu, bear]
        game.put_counters(mowu, "+1/+1", 3)
        game.put_counters(bear, "+1/+1", 3)
        self.assertEqual((mowu.counters.get("+1/+1"), bear.counters.get("+1/+1")), (4, 3))

    def test_a_creature_or_vehicle(self):
        self.assertEqual((counters_on([CARADORA], VEHICLE), counters_on([CARADORA], BEAR), counters_on([CARADORA], RELIC)), (4, 4, 3))

    def test_an_army_goblin_or_orc(self):
        self.assertEqual((counters_on([MAUHUR], ORC), counters_on([MAUHUR], BEAR)), (4, 3))

    def test_each_one_adds_one(self):
        self.assertEqual(counters_on([GROUND, CARADORA], BEAR), 5)


if __name__ == "__main__":
    unittest.main()
