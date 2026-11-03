"""Valiant: "Whenever this creature becomes the target of a spell or ability you control for the first time each turn, ..." (Emberheart
Challenger)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, FOREST, activate, lands, pick, real, run_stack, table3

CHALLENGER = real("Emberheart Challenger", "{1}{R}", "Creature — Mouse Warrior", "Haste\nProwess (Whenever you cast a noncreature spell, "
                  "this creature gets +1/+1 until end of turn.)\nValiant — Whenever this creature becomes the target of a spell or ability "
                  "you control for the first time each turn, exile the top card of your library. Until end of turn, you may play that card.",
                  "2", "2")
GROWTH = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.")
WARDEN = real("Ghost Warden", "{1}{W}", "Creature — Spirit", "{T}: Target creature gets +1/+1 until end of turn.", "1", "1")


def table():
    game, _ = table3(pick("Emberheart Challenger"), pick("Emberheart Challenger"))
    a, b = game.seats[0], game.seats[1]
    challenger = Permanent(CHALLENGER)
    a.battlefield = [challenger] + lands(2)
    a.library, a.exile = [OGRE, FOREST, FOREST], []
    return game, a, b, challenger


def cast(game, seat, card):
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


class EmberheartChallengerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(CHALLENGER), [])

    def test_your_spell_exiles_the_top_card_to_play_this_turn(self):
        game, a, b, challenger = table()
        cast(game, a, GROWTH)
        self.assertEqual(a.exile, [OGRE])
        self.assertEqual(a.exile_play, [(OGRE, game.turn)])

    def test_only_the_first_time_each_turn(self):
        game, a, b, challenger = table()
        cast(game, a, GROWTH)
        cast(game, a, GROWTH)
        self.assertEqual(a.exile, [OGRE])
        game.turn += 1
        for land in a.battlefield:
            land.tapped = False
        cast(game, a, GROWTH)
        self.assertEqual(a.exile, [OGRE, FOREST])

    def test_your_ability_counts(self):
        game, a, b, challenger = table()
        warden = Permanent(WARDEN)
        a.battlefield.append(warden)
        activate(game, a, "Ghost Warden")
        self.assertEqual(a.exile, [OGRE])

    def test_an_opponents_spell_does_not(self):
        game, a, b, challenger = table()
        b.battlefield = lands(1)
        game.active = 1
        b.exile = []
        cast(game, b, GROWTH)
        self.assertEqual((a.exile, b.exile), ([], []))


if __name__ == "__main__":
    unittest.main()
