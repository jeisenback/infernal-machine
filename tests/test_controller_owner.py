"""`Game.controller` and `Game.owner_of`: the seat of a permanent the caller knows is there, and whose card it is (issue #309)."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import creature, table3

BEAR = creature("Grizzly Bears", 2, 2)


class ControllerTests(unittest.TestCase):
    def test_the_seat_whose_battlefield_it_is_on(self):
        game, _ = table3()
        a, b, c = game.seats
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        self.assertIs(game.controller(bear), b)

    def test_a_permanent_that_is_gone_has_no_controller(self):
        game, _ = table3()
        a, b, c = game.seats
        gone = Permanent(BEAR)
        self.assertIsNone(game.controller_of(gone))
        with self.assertRaises(AssertionError):
            game.controller(gone)


class OwnerTests(unittest.TestCase):
    def test_the_seat_it_entered_under_beats_the_one_that_controls_it(self):
        game, _ = table3()
        a, b, c = game.seats
        stolen = Permanent(BEAR, owner=a)
        b.battlefield = [stolen]
        self.assertIs(game.owner_of(stolen), a)

    def test_without_an_owner_it_is_the_controller(self):
        game, _ = table3()
        a, b, c = game.seats
        bear = Permanent(BEAR)
        c.battlefield = [bear]
        self.assertIs(game.owner_of(bear), c)

    def test_a_permanent_that_left_is_its_last_controllers(self):
        game, _ = table3()
        a, b, c = game.seats
        bear = Permanent(BEAR)
        bear.last_controller = b
        self.assertIs(game.owner_of(bear), b)

    def test_nobody_to_ask_is_an_error(self):
        game, _ = table3()
        a, b, c = game.seats
        with self.assertRaises(AssertionError):
            game.owner_of(Permanent(BEAR))


if __name__ == "__main__":
    unittest.main()
