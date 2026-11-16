"""Teferi, Master of Time, from its real Oracle text: "You may activate loyalty abilities of Teferi on any player's turn any time you could
cast an instant." (still once each turn; another planeswalker's wait for its controller's main phase), "−3: Target creature you don't control
phases out." (not your own) and "−10: Take two extra turns after this one." """

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, pick, real, run_stack, table3

TEFERI = real("Teferi, Master of Time", "{2}{U}{U}", "Legendary Planeswalker — Teferi", "You may activate loyalty abilities of Teferi on "
              "any player's turn any time you could cast an instant.\n+1: Draw a card, then discard a card.\n−3: Target creature you "
              "don't control phases out. (Treat it and anything attached to it as though they don't exist until its controller's next turn.)"
              "\n−10: Take two extra turns after this one.", None, None, colors=("U",))
JACE = real("Jace Beleren", "{1}{U}{U}", "Legendary Planeswalker — Jace", "+2: Each player draws a card.\n−1: Target player draws a "
            "card.\n−10: Target player mills twenty cards.", None, None, colors=("U",))


def on_their_turn(policy=None, loyalty=3):
    """Seat 0 controls Teferi (and Jace); it is seat 1's turn, in its main phase, and seat 1 has a Bear."""
    game, _ = table3(policy)
    a, b, _ = game.seats
    a.battlefield = [Permanent(TEFERI, loyalty=loyalty), Permanent(JACE, loyalty=3), Permanent(BEAR)]
    b.battlefield = [Permanent(BEAR)]
    a.library = [BEAR] * 3
    game.step, game.active = "main1", b.index
    return game, a, b


def offered(game, seat, name):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE + name)]


class TeferiTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(TEFERI), [])

    def test_on_an_opponents_turn_teferi_but_not_jace_may_be_activated_once(self):
        game, a, _ = on_their_turn()
        self.assertEqual((len(offered(game, a, "Teferi")) > 0, offered(game, a, "Jace")), (True, []))
        (plus,) = [x for x in offered(game, a, "Teferi") if ": +1:" in x]
        game._perform(a, plus)
        run_stack(game)
        self.assertEqual(offered(game, a, "Teferi"), [])  # once each turn (CR 606.3)

    def test_minus_three_phases_out_a_creature_you_dont_control(self):
        seen = []
        def policy(prompt, options):
            seen.extend(options)
            return pick("Bear 2/2 (seat 1")(prompt, options)
        game, a, b = on_their_turn(policy)
        (minus,) = [x for x in offered(game, a, "Teferi") if ": −3:" in x]
        game._perform(a, minus)
        run_stack(game)
        self.assertEqual([o for o in seen if o.startswith("Bear") and "seat 0" in o], [])  # your own Bear is not offered
        self.assertEqual(([p.card.name for p in b.battlefield], [p.card.name for p in b.phased_out]), ([], ["Bear"]))

    def test_minus_ten_takes_two_extra_turns(self):
        game, a, _ = on_their_turn(loyalty=10)
        (minus,) = [x for x in offered(game, a, "Teferi") if ": −10:" in x]
        game._perform(a, minus)
        run_stack(game)
        self.assertEqual(game.extra_turns, [a.index, a.index])


if __name__ == "__main__":
    unittest.main()
