"""The mana a payment makes and does not use stays in the pool until the step ends (#540, CR 106.4): Sol Ring tapped for a {1}
spell made {C}{C}, and the other {C} pays for the next one. Mana with a restriction is left out."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import lands, pick, real, run_stack, table

SOL_RING = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")
SLIVER = real("Metallic Sliver", "{1}", "Artifact Creature — Sliver", "", "1", "1")
VANGUARD = real("Elite Vanguard", "{W}", "Creature — Human Soldier", "", "2", "1", colors=("W",))
JEGANTHA = real("Jegantha, the Wellspring", "{4}{R/G}", "Legendary Creature — Elemental Elk",
                "Companion — No card in your starting deck has more than one of the same mana symbol in its mana cost. (If this card is your chosen "
                "companion, you may put it into your hand from outside the game for {3} as a sorcery.)\n{T}: Add {W}{U}{B}{R}{G}. This mana can't be spent "
                "to pay generic mana costs.", "5", "5", colors=("R", "G"))


def seat_with(*permanents, hand=()):
    game, _, _ = table(pick("Yes"))
    mine = game.seats[0]
    mine.battlefield = list(permanents)
    mine.hand = list(hand)
    return game, mine


class SurplusManaTests(unittest.TestCase):
    def test_the_second_mana_of_sol_ring_pays_for_the_next_spell(self):
        game, mine = seat_with(Permanent(SOL_RING), hand=[SLIVER, SLIVER])
        game._perform(mine, "Cast: Metallic Sliver")
        run_stack(game)
        self.assertEqual(mine.mana_pool, [frozenset("C")])
        self.assertIn("Cast: Metallic Sliver", game.legal_actions(mine))  # no land: the pool pays
        game._perform(mine, "Cast: Metallic Sliver")
        run_stack(game)
        self.assertEqual(([p.card.name for p in mine.battlefield], mine.mana_pool), (["Sol Ring", "Metallic Sliver", "Metallic Sliver"], []))

    def test_a_cost_that_uses_all_of_it_leaves_nothing(self):
        game, mine = seat_with(Permanent(SOL_RING), hand=[real("Pair", "{2}", "Artifact", "")])
        game._perform(mine, "Cast: Pair")
        run_stack(game)
        self.assertEqual(mine.mana_pool, [])

    def test_what_is_left_is_gone_at_the_end_of_the_step(self):
        game, mine = seat_with(Permanent(SOL_RING), hand=[SLIVER])
        game._perform(mine, "Cast: Metallic Sliver")
        run_stack(game)
        game._empty_pools()
        self.assertEqual(mine.mana_pool, [])

    def test_mana_that_cannot_pay_generic_costs_is_not_kept(self):
        game, mine = seat_with(Permanent(JEGANTHA, sick=False), hand=[VANGUARD, SLIVER])
        game._perform(mine, "Cast: Elite Vanguard")  # {W} out of {W}{U}{B}{R}{G}
        run_stack(game)
        self.assertEqual(mine.mana_pool, [])
        self.assertNotIn("Cast: Metallic Sliver", game.legal_actions(mine))

    def test_lands_leave_nothing_over(self):
        game, mine = seat_with(*lands(3), hand=[SLIVER])
        game._perform(mine, "Cast: Metallic Sliver")
        run_stack(game)
        self.assertEqual(mine.mana_pool, [])


if __name__ == "__main__":
    unittest.main()
