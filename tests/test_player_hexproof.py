"""A player with hexproof or shroud (CR 702.11c, 702.18c), from the cards' real Oracle text: "You have hexproof." (Leyline of
Sanctity) and "You have shroud." (Ivory Mask) are rules statics read by `Game._player_untargetable`. All eight cards whose only gap
it was are fully playable. Under Leyline of Sanctity an opponent's Lightning Bolt is not offered its controller as a target (only the
other players), while the controller's own spells still can target them; under Ivory Mask not even their own can. A player without
either is offered as usual."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import choose, lands, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Aegis of the Gods", "Crystal Barricade", "Ivory Mask", "Leyline of Sanctity", "Metropolis Reformer", "Spirit of the Hearth",
         "Teyo, the Shieldmage", "True Believer"]
LEYLINE, MASK = REAL["Leyline of Sanctity"], REAL["Ivory Mask"]
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")

# The guards these tests are there to catch (python tools/mutate.py tests.test_player_hexproof).
MUTATIONS = [
    ("infernal_machine/game.py", '(key == "you_hexproof" and caster is not seat)', '(key == "you_hexproof")', "only an opponent's"),
    ("infernal_machine/game.py", 'any(owner is seat and (key == "you_shroud"', 'any(owner is not None and (key == "you_shroud"',
     "only its controller"),
    ("infernal_machine/game.py", '(key == "you_shroud" or (key == "you_hexproof"', '((key == "you_hexproof"', "shroud too"),
]


def players(game, kind, caster):
    return [t for _, t in game.target_options(kind, caster) if t in game.seats]


class PlayerHexproofTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_an_opponent_cant_target_them_but_they_can(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(LEYLINE)]
        self.assertEqual((players(game, "player", b), players(game, "player", a)), ([b, c], [a, b, c]))

    def test_shroud_stops_their_own_too(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(MASK)]
        self.assertEqual((players(game, "any", b), players(game, "player", a)), ([b, c], [b, c]))

    def test_an_opponents_bolt_goes_elsewhere(self):
        game, players_ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(LEYLINE)]
        b.battlefield, b.hand = lands(1), [BOLT]
        players_[1].policy = choose(game, a, c)
        game._perform(b, CAST + "Lightning Bolt")
        run_stack(game)
        self.assertEqual((a.life, c.life), (40, 37))


if __name__ == "__main__":
    unittest.main()
