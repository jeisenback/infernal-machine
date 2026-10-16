"""Every game the tests play checks each reuse of its board view against the full state (see Game._board_view): a change that did not
move the epoch counter fails the test instead of giving a stale answer."""

from infernal_machine.game import Game

Game.verify_views = True
