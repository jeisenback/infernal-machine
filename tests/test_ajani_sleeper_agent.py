"""Ajani, Sleeper Agent, from its real Oracle text: "+1: Reveal the top card of your library. If it's a creature or planeswalker card, put
it into your hand. Otherwise, you may put it on the bottom of your library." "−3: Distribute three +1/+1 counters among up to three target
creatures. They gain vigilance until end of turn." (only those given a counter) and "−6: You get an emblem with "Whenever you cast a creature
or planeswalker spell, target opponent gets two poison counters."" (not for an instant)."""

import unittest

from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BOLT, FOREST, lands, pick, real, run_stack, table3

AJANI = real("Ajani, Sleeper Agent", "{1}{G}{G/W/P}{W}", "Legendary Planeswalker — Ajani", "Compleated ({G/W/P} can be paid with {G}, "
             "{W}, or 2 life. If life was paid, this planeswalker enters with two fewer loyalty counters.)\n+1: Reveal the top card of your "
             "library. If it's a creature or planeswalker card, put it into your hand. Otherwise, you may put it on the bottom of your library."
             "\n−3: Distribute three +1/+1 counters among up to three target creatures. They gain vigilance until end of turn.\n−6: "
             "You get an emblem with \"Whenever you cast a creature or planeswalker spell, target opponent gets two poison counters.\"",
             None, None, colors=("G", "W"))


def activate(ability, policy=None, others=()):
    """Seat 0 activates Ajani's `ability` ("+1", "−3" or "−6"), with `others` on its battlefield."""
    game, _ = table3(policy)
    a = game.seats[0]
    a.battlefield = [Permanent(AJANI, loyalty=6), *others] + lands(2)
    game.step, game.active = "main1", a.index
    (action,) = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Ajani") and f": {ability}:" in x]
    game._perform(a, action)
    run_stack(game)
    return game, a


class PlusOneTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(AJANI), [])

    def test_a_creature_on_top_goes_to_the_hand(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR, FOREST]
        a.battlefield = [Permanent(AJANI, loyalty=6)]
        game.step, game.active = "main1", a.index
        (action,) = [x for x in game.legal_actions(a) if ": +1:" in x]
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((a.hand, a.library), ([BEAR], [FOREST]))

    def test_anything_else_may_go_to_the_bottom(self):
        for answer, library in (("Yes", [BEAR, FOREST]), ("No", [FOREST, BEAR])):
            game, _ = table3(pick(answer))
            a = game.seats[0]
            a.library = [FOREST, BEAR]
            a.battlefield = [Permanent(AJANI, loyalty=6)]
            game.step, game.active = "main1", a.index
            (action,) = [x for x in game.legal_actions(a) if ": +1:" in x]
            game._perform(a, action)
            run_stack(game)
            self.assertEqual((a.hand, a.library), ([], library), answer)


class MinusThreeTests(unittest.TestCase):
    def test_the_creatures_given_counters_gain_vigilance(self):
        first, second = Permanent(BEAR), Permanent(BEAR)
        game, _ = activate("−3", lambda prompt, options: len(options) - 1, (first, second))  # the last offered: the second
        self.assertEqual((first.counters.get("+1/+1", 0), second.counters.get("+1/+1", 0)), (0, 3))
        self.assertEqual((game.has_keyword(first, "vigilance"), game.has_keyword(second, "vigilance")), (False, True))


class EmblemTests(unittest.TestCase):
    def test_casting_a_creature_poisons_an_opponent_and_an_instant_does_not(self):
        game, a = activate("−6")
        b, c = game.seats[1], game.seats[2]
        poison = lambda: b.player_counters.get("poison", 0) + c.player_counters.get("poison", 0)  # noqa: E731
        a.hand = [BOLT, BEAR]
        a.library = [FOREST] * 3
        game._perform(a, CAST + "Bolt")
        run_stack(game)
        self.assertEqual(poison(), 0)
        game._perform(a, CAST + "Bear")
        run_stack(game)
        self.assertEqual(poison(), 2)


if __name__ == "__main__":
    unittest.main()
