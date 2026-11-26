""""Whenever one or more +1/+1 counters are put on this creature, ..." (CR 122.6: put on it, moved onto it, or as it enters with them),
from the cards' real Oracle text. All ten cards whose only gap it was are fully playable. Knighted Myr adapts and gains double
strike; Herd Baloth given two counters at once makes one Beast; Dusk Legion Duelist given counters twice in a turn draws once ("This
ability triggers only once each turn."); Scurry Oak's evolve makes a Squirrel. Counters moved onto Herd Baloth make a Beast, and a
creature that enters with +1/+1 counters triggers too (a test creature with two real lines: Herd Baloth's trigger and "This creature
enters with two +1/+1 counters on it."). A -1/-1 counter or another creature's counters do not."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, activate, lands, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Basking Broodscale", "Benthic Biomancer", "Dreamdrinker Vampire", "Dusk Legion Duelist", "Evolution Witness", "Generous Pup",
         "Herd Baloth", "Knighted Myr", "Scurry Oak", "Sharktocrab"]
BALOTH, MYR, DUELIST, OAK = REAL["Herd Baloth"], REAL["Knighted Myr"], REAL["Dusk Legion Duelist"], REAL["Scurry Oak"]
ARRIVES = real("Grown Baloth", "{3}{G}{G}", "Creature — Beast", "This creature enters with two +1/+1 counters on it.\n"
               + BALOTH.oracle_text, "4", "4")
OGRE4 = real("Big Ogre", "{3}{R}", "Creature — Ogre", "", "4", "4")

# The guards these tests are there to catch (python tools/mutate.py tests.test_counters_put_trigger).
MUTATIONS = [
    ("infernal_machine/game.py", '        if counter == "+1/+1" and count > 0 and (holder := self.controller_of(permanent)) is not None:',
     '        if count > 0 and (holder := self.controller_of(permanent)) is not None:', "only +1/+1 counters"),
    ("infernal_machine/game.py", "        self._plus_counters_put(destination, counter, moved)\n", "", "counters moved onto it"),
    ("infernal_machine/game.py", '        self._plus_counters_put(permanent, "+1/+1", permanent.counters.get("+1/+1", 0))  # CR 122.6: entering with them\n',
     "", "entering with them"),
]


def beasts(seat):
    return [p for p in seat.battlefield if p.card.name == "Beast"]


def table(*cards):
    game, _ = table3()
    a = game.seats[0]
    permanents = [Permanent(c, sick=False) for c in cards]
    for p in permanents:
        game._enter(a, p)
    run_stack(game)
    return game, a, permanents


class CountersPutTriggerTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_adapt_gives_double_strike(self):
        game, a, (myr,) = table(MYR)
        a.battlefield += lands(3)
        activate(game, a, "Adapt")
        self.assertTrue(game.has_keyword(myr, "double strike"))

    def test_two_counters_at_once_trigger_once(self):
        game, a, (baloth, bear) = table(BALOTH, BEAR)
        game.put_counters(baloth, "+1/+1", 2)
        run_stack(game)
        self.assertEqual(len(beasts(a)), 1)
        game.put_counters(baloth, "-1/-1", 1)
        game.put_counters(bear, "+1/+1", 1)
        run_stack(game)
        self.assertEqual(len(beasts(a)), 1)

    def test_only_once_each_turn(self):
        game, a, (duelist,) = table(DUELIST)
        a.library = [BEAR] * 5
        for _ in range(2):
            game.put_counters(duelist, "+1/+1", 1)
            run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_evolve_makes_a_squirrel(self):
        game, a, (oak,) = table(OAK)
        game._enter(a, Permanent(OGRE4))
        run_stack(game)
        self.assertEqual((oak.counters.get("+1/+1"), [p.card.name for p in a.battlefield if p.card.name == "Squirrel"]), (1, ["Squirrel"]))

    def test_moved_onto_it_or_entering_with_them(self):
        game, a, (baloth, bear) = table(BALOTH, BEAR)
        bear.counters["+1/+1"] = 2
        game.move_counters(bear, baloth, "+1/+1", None)
        run_stack(game)
        self.assertEqual(len(beasts(a)), 1)
        game, a, _ = table(ARRIVES)
        self.assertEqual(len(beasts(a)), 1)


if __name__ == "__main__":
    unittest.main()
