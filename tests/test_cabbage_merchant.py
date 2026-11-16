"""The Cabbage Merchant, from its real Oracle text: "Whenever a creature deals combat damage to you, sacrifice a Food token." Only combat
damage to its controller sets it off (not damage to an opponent, nor noncombat damage), and with no Food there is nothing to sacrifice."""

import unittest

from infernal_machine.effects.outcomes import FOOD
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, real, run_stack, table3

MERCHANT = real("The Cabbage Merchant", "{2}{G}", "Legendary Creature — Human Citizen", "Whenever an opponent casts a noncreature spell, "
                "create a Food token. (It's an artifact with \"{2}, {T}, Sacrifice this token: You gain 3 life.\")\nWhenever a creature "
                "deals combat damage to you, sacrifice a Food token.\nTap two untapped Foods you control: Add one mana of any color.",
                "2", "2", colors=("G",))


def table(foods=2):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(MERCHANT)] + [Permanent(FOOD) for _ in range(foods)]
    b.battlefield = [Permanent(BEAR), Permanent(FOOD)]
    return game, a, b


def foods(seat):
    return sum(p.card.name == "Food" for p in seat.battlefield)


class CabbageMerchantTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(MERCHANT), [])

    def test_combat_damage_to_you_sacrifices_a_food(self):
        game, a, b = table()
        game.damage(a, 2, source=b.battlefield[0], combat=True)  # CR 510.2
        run_stack(game)
        self.assertEqual((foods(a), foods(b)), (1, 1))

    def test_noncombat_damage_or_damage_to_an_opponent_sets_nothing_off(self):
        game, a, b = table()
        game.damage(a, 2, source=b.battlefield[0])
        game.damage(b, 2, source=a.battlefield[0], combat=True)
        run_stack(game)
        self.assertEqual((foods(a), foods(b)), (2, 1))

    def test_with_no_food_nothing_is_sacrificed(self):
        game, a, b = table(foods=0)
        game.damage(a, 2, source=b.battlefield[0], combat=True)
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield], foods(b)), (["The Cabbage Merchant"], 1))


if __name__ == "__main__":
    unittest.main()
