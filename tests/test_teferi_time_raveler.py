"""Teferi, Time Raveler: "Each opponent can cast spells only any time they could cast a sorcery.", "+1: Until your next turn, you may cast
sorcery spells as though they had flash." and "−3: Return up to one target artifact, creature, or enchantment to its owner's hand. Draw a
card." """

import unittest

from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BOLT, DIVINATION, FOREST, lands, pick, real, run_stack, table3

TEFERI = real("Teferi, Time Raveler", "{1}{W}{U}", "Legendary Planeswalker — Teferi", "Each opponent can cast spells only any time they "
              "could cast a sorcery.\n+1: Until your next turn, you may cast sorcery spells as though they had flash.\n−3: Return up to one "
              "target artifact, creature, or enchantment to its owner's hand. Draw a card.", colors=("W", "U"))


def table(active, step="main1", teferi=True, policy=None):
    game, _ = table3(policy) if policy else table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = ([Permanent(TEFERI, loyalty=4)] if teferi else []) + lands(4)
    a.hand, b.hand, b.battlefield, a.library = [BOLT, DIVINATION], [BOLT], lands(2), [FOREST] * 3
    game.active, game.step = active, step
    return game, a, b


class TeferiTimeRavelerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(TEFERI), [])

    def test_an_opponent_casts_an_instant_only_when_they_could_cast_a_sorcery(self):
        game, _, b = table(active=0)
        self.assertNotIn(CAST + "Bolt", game.legal_actions(b))  # on Teferi's controller's turn
        game, _, b = table(active=1, step="upkeep")
        self.assertNotIn(CAST + "Bolt", game.legal_actions(b))  # on their own turn, outside a main phase
        game, _, b = table(active=1)
        self.assertIn(CAST + "Bolt", game.legal_actions(b))  # their own main phase, the stack empty

    def test_not_in_their_main_phase_while_the_stack_holds_a_spell(self):
        game, a, b = table(active=1)
        game._perform(a, CAST + "Bolt")  # Teferi's controller is not held to sorcery speed
        self.assertEqual(len(game.stack), 1)
        self.assertNotIn(CAST + "Bolt", game.legal_actions(b))

    def test_without_teferi_or_for_his_controller_instants_stay_instants(self):
        game, _, b = table(active=0, teferi=False)
        self.assertIn(CAST + "Bolt", game.legal_actions(b))
        game, a, _ = table(active=1)
        self.assertIn(CAST + "Bolt", game.legal_actions(a))

    def test_plus_one_lets_sorceries_be_cast_at_instant_speed_until_your_next_turn(self):
        game, a, _ = table(active=0, policy=pick("Activate: Teferi"))
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "+1" in x))
        run_stack(game)
        game.active, game.step = 1, "main1"
        a.hand.append(BEAR)
        self.assertIn(CAST + "Divination", game.legal_actions(a))
        self.assertNotIn(CAST + "Bear", game.legal_actions(a))  # sorceries only
        game.active, game.step = 0, "untap"
        game._turn_based_actions(a)
        game.active, game.step = 1, "main1"
        self.assertNotIn(CAST + "Divination", game.legal_actions(a))

    def test_minus_three_returns_a_creature_and_draws(self):
        game, a, b = table(active=0, policy=pick("Bear"))
        b.battlefield.append(Permanent(BEAR))
        a.hand = []
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "−3" in x))
        run_stack(game)
        self.assertEqual((b.hand[-1], [c.name for c in a.hand]), (BEAR, ["Forest"]))


if __name__ == "__main__":
    unittest.main()
