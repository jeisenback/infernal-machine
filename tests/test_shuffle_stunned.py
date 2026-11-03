"""Floodpits Drowner: "{1}{U}, {T}: Shuffle this creature and target creature with a stun counter on it into their owners' libraries." """

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, activate, lands, real, run_stack, table3

DROWNER = real("Floodpits Drowner", "{1}{U}", "Creature — Merfolk", "Flash\nVigilance\nWhen this creature enters, tap target creature "
               "an opponent controls and put a stun counter on it.\n{1}{U}, {T}: Shuffle this creature and target creature with a stun counter "
               "on it into their owners' libraries.", "2", "1")


def table(theirs):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.library, b.library = [], []
    drowner = Permanent(DROWNER)
    drowner.entered_turn = game.turn - 1
    a.battlefield = [drowner] + lands(2)
    b.battlefield = [Permanent(card) for card in theirs]
    return game, a, b


def offered(game, seat):
    return any(x.startswith(ACTIVATE) and "Shuffle" in x for x in game.legal_actions(seat))


class FloodpitsDrownerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(DROWNER), [])

    def test_it_shuffles_itself_and_a_stunned_creature_away(self):
        game, a, b = table([OGRE])
        b.battlefield[0].counters["stun"] = 1
        activate(game, a, "Shuffle")
        self.assertEqual((a.library, b.library), ([DROWNER], [OGRE]))
        self.assertEqual(b.battlefield, [])

    def test_with_the_target_no_longer_stunned_nothing_is_shuffled(self):
        game, a, b = table([OGRE])
        b.battlefield[0].counters["stun"] = 1
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Shuffle" in x))
        b.battlefield[0].counters.pop("stun")
        run_stack(game)
        self.assertEqual((a.library, b.library), ([], []))
        self.assertIn(DROWNER, [p.card for p in a.battlefield])

    def test_a_creature_without_a_stun_counter_is_not_a_target(self):
        game, a, _ = table([BEAR])
        self.assertFalse(offered(game, a))

    def test_its_enters_trigger_sets_up_the_shuffle(self):
        game, a, b = table([OGRE])
        a.battlefield = lands(2)
        game._enter(a, Permanent(DROWNER))
        run_stack(game)
        self.assertEqual(b.battlefield[0].counters.get("stun"), 1)


if __name__ == "__main__":
    unittest.main()
