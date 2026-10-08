import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (AdditionalCost, DestroyAll, MassFilter, PumpEachX, activated_abilities,
                                      additional_costs, spell_effects)
from infernal_machine.game import ACTIVATE, CAST, LIFE_X_PROMPT, Permanent, X_PROMPT
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.real import REAL

DELUGE = REAL["Toxic Deluge"]
DEED = REAL["Pernicious Deed"]


def body(name, power, toughness, mana_value=2):
    return Card(name=name, cmc=float(mana_value), type_line="Creature — Bear", power=str(power), toughness=str(toughness))


def resolve_everything(game):
    game._put_triggers_on_stack()
    while game.stack:
        game._resolve(game.stack.pop())
        game._put_triggers_on_stack()
    game._check_state()


def choosing(x):
    """A policy that picks X when asked for it (as life or as mana) and the first option otherwise."""
    def policy(prompt, options):
        if prompt.startswith((LIFE_X_PROMPT, X_PROMPT)):
            return options.index(str(x))
        return 0
    return policy


class ParseTests(unittest.TestCase):
    def test_toxic_deluge(self):
        self.assertEqual(additional_costs(DELUGE), [AdditionalCost(life_x=True)])
        self.assertEqual(spell_effects(DELUGE), [PumpEachX(-1, -1, everyone=True)])
        self.assertEqual(unsupported_lines(DELUGE), [])

    def test_pernicious_deed(self):
        [ability] = activated_abilities(DEED)
        self.assertEqual((ability.mana_cost, ability.sacrifice), ("{X}", True))
        self.assertEqual(ability.effects, (DestroyAll("artifact or creature or enchantment",
                                                      MassFilter(stat="mana_value", at_most="X")),))
        self.assertEqual(unsupported_lines(DEED), [])

    def test_other_mass_pumps_with_x(self):
        mine = Card(name="Boost", type_line="Sorcery", oracle_text="Creatures you control get +X/+0 until end of turn.")
        theirs = Card(name="Shrink", type_line="Sorcery", oracle_text="Creatures your opponents control get -X/-X until end of turn.")
        self.assertEqual(spell_effects(mine), [PumpEachX(1, 0)])
        self.assertEqual(spell_effects(theirs), [PumpEachX(-1, -1, opponents=True)])


class DelugeTests(unittest.TestCase):
    def cast(self, x, life=40):
        game, _ = table3(choosing(x))
        a, b, _ = game.seats
        a.life = life
        small, big = Permanent(body("Small", 2, 2)), Permanent(body("Big", 4, 4))
        a.hand = [DELUGE]
        a.battlefield = [*lands(3), small]
        b.battlefield = [big]
        game._perform(a, CAST + "Toxic Deluge")
        resolve_everything(game)
        return game, a, b, small, big

    def test_pay_x_life_and_every_creature_gets_minus_x(self):
        game, a, b, small, big = self.cast(2)
        self.assertEqual(a.life, 38)
        self.assertNotIn(small, a.battlefield)  # a 2/2 became 0/0
        self.assertEqual((game.power(big), game.toughness(big)), (2, 2))  # a 4/4 survives, for the turn

    def test_a_bigger_x_kills_the_big_one_too(self):
        game, a, b, small, big = self.cast(4)
        self.assertEqual(a.life, 36)
        self.assertEqual(b.battlefield, [])

    def test_x_zero_costs_no_life(self):
        game, a, b, small, big = self.cast(0)
        self.assertEqual(a.life, 40)
        self.assertIn(small, a.battlefield)

    def test_you_cannot_pay_all_your_life(self):
        seen = []

        def policy(prompt, options):
            if prompt.startswith(LIFE_X_PROMPT):
                seen.append(options)
            return 0

        game, _ = table3(policy)
        a = game.seats[0]
        a.life, a.hand, a.battlefield = 3, [DELUGE], lands(3)
        game._perform(a, CAST + "Toxic Deluge")
        self.assertEqual(seen, [["0", "1", "2"]])  # three life: pay up to two


class DeedTests(unittest.TestCase):
    def test_destroys_everything_with_mana_value_x_or_less(self):
        game, _ = table3(choosing(2))
        a, b, _ = game.seats
        deed = Permanent(DEED)
        cheap, edge, dear = Permanent(body("Cheap", 1, 1, 1)), Permanent(body("Edge", 2, 2, 2)), Permanent(body("Dear", 3, 3, 3))
        trinket = Permanent(Card(name="Trinket", cmc=1.0, type_line="Artifact"))
        land = Permanent(Card(name="Wastes", cmc=0.0, type_line="Basic Land", produced_mana=("C",)))
        a.battlefield = [deed, *lands(2), cheap, land]
        b.battlefield = [edge, dear, trinket]
        [action] = [x for x in game._activations(a, True) if "Destroy each" in x]
        game._perform(a, action)
        resolve_everything(game)
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], [])
        self.assertEqual([p.card.name for p in b.battlefield], ["Dear"])  # mana value 3 survives X = 2
        self.assertIn(land, a.battlefield)  # lands are not artifacts, creatures or enchantments
        self.assertNotIn(deed, a.battlefield)  # it was sacrificed as the cost


if __name__ == "__main__":
    unittest.main()
