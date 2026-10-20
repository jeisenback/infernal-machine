"""Costs to attack are worked out for all the attackers together and paid once, after they are chosen and tapped
(CR 508.1f-i), not paid attacker by attacker. Ghostly Prison's text is from Scryfall.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from tests.helpers import BEAR, FOREST, lands, table

PRISON = Card(name="Prison", mana_cost="{2}{W}", type_line="Enchantment",
              oracle_text="Creatures can't attack you unless their controller pays {1} for each creature they control that's "
                          "attacking you.")
PRISON_TWO = Card(name="Prison Two", mana_cost="{2}{W}", type_line="Enchantment",
                  oracle_text="Creatures can't attack you unless their controller pays {2} for each creature they control that's "
                              "attacking you.")
DORK = Card(name="Dork", mana_cost="{G}", type_line="Creature — Elf", power="1", toughness="1", oracle_text="{T}: Add {G}.")
VIGILANT_DORK = Card(name="Vigilant Dork", mana_cost="{G}", type_line="Creature — Elf", power="1", toughness="1",
                     oracle_text="Vigilance\n{T}: Add {G}.")
ATTACK_ALL = lambda prompt, options: 1 if prompt.startswith("Attack") and len(options) > 1 else 0


def declare(prison, creatures, forests):
    game, _, _ = table(ATTACK_ALL)
    a, b = game.seats
    a.battlefield = [Permanent(c, sick=False) for c in creatures] + lands(forests, FOREST)
    b.battlefield = [Permanent(prison)]
    game.combat.declare_attackers(a)
    return game, a, [x.attacker.card.name for x in game.combat.attacks]


def tapped_lands(seat):
    return sum(p.tapped for p in seat.battlefield if "Land" in p.card.type_line)


class AllAttackersPayTogetherTests(unittest.TestCase):
    def test_a_mana_creature_can_attack_when_lands_pay_for_both(self):
        game, a, attackers = declare(PRISON, [BEAR, DORK], forests=2)
        self.assertEqual(attackers, ["Bear", "Dork"])  # the Dork attacks; the Forests pay, not its mana ability
        self.assertEqual(tapped_lands(a), 2)

    def test_a_vigilant_mana_creature_can_still_pay(self):
        game, a, attackers = declare(PRISON, [BEAR, VIGILANT_DORK], forests=1)
        self.assertEqual(attackers, ["Bear", "Vigilant Dork"])
        vigilant = next(p for p in a.battlefield if p.card.name == "Vigilant Dork")
        self.assertEqual((tapped_lands(a), vigilant.tapped), (1, True))  # it paid with its mana ability, since it did not tap to attack

    def test_a_creature_that_would_tap_to_attack_cannot_pay_for_itself(self):
        game, a, attackers = declare(PRISON, [DORK], forests=0)
        self.assertEqual(attackers, [])  # its own mana would have to pay, but attacking taps it

    def test_only_as_many_attackers_as_the_total_cost_allows(self):
        game, a, attackers = declare(PRISON_TWO, [BEAR, BEAR, BEAR], forests=5)
        self.assertEqual((len(attackers), tapped_lands(a)), (2, 4))  # {2} each: two attackers, not three

    def test_everyone_attacks_when_the_total_is_affordable(self):
        game, a, attackers = declare(PRISON_TWO, [BEAR, BEAR], forests=4)
        self.assertEqual((len(attackers), tapped_lands(a)), (2, 4))

    def test_nobody_attacks_when_not_even_one_is_affordable(self):
        game, a, attackers = declare(PRISON_TWO, [BEAR, BEAR], forests=1)
        self.assertEqual((attackers, tapped_lands(a)), ([], 0))

    def test_no_tax_means_nothing_is_paid(self):
        game, a, attackers = declare(Card(name="Plain", type_line="Enchantment"), [BEAR, BEAR], forests=2)
        self.assertEqual((len(attackers), tapped_lands(a)), (2, 0))


if __name__ == "__main__":
    unittest.main()
