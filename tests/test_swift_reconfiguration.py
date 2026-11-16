"""Swift Reconfiguration, from its real Oracle text: "Enchanted permanent is a Vehicle artifact with crew 5 and it loses all other card
types. (It's not a creature unless it's crewed.)" While the Aura is attached the permanent is a noncreature Vehicle (legendary still, if it
was) that 5 power crews; once the Aura is gone it is its own card again, and it goes to the graveyard as itself."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, pick, real, table

SWIFT = real("Swift Reconfiguration", "{W}", "Enchantment — Aura", "Flash\nEnchant creature or Vehicle\nEnchanted permanent is a Vehicle "
             "artifact with crew 5 and it loses all other card types. (It's not a creature unless it's crewed.)", None, None, colors=("W",))
ISAMARU = real("Isamaru, Hound of Konda", "{W}", "Legendary Creature — Dog", "", "2", "2", colors=("W",))


def enchanted(host_card, *others, policy=None):
    """Seat 0 controls `host_card` (and `others`), enchanted by Swift Reconfiguration; state-based actions are checked."""
    game, _, _ = table(policy)
    a = game.seats[0]
    host = Permanent(host_card, sick=False)
    aura = Permanent(SWIFT, attached_to=host)
    a.battlefield = [host, aura] + [Permanent(card, sick=False) for card in others]
    game._check_state()
    return game, a, host, aura


def crew_actions(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE) and x.endswith("Crew 5")]


class SwiftReconfigurationTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(SWIFT), [])

    def test_the_creature_is_a_noncreature_vehicle_artifact_and_the_aura_stays(self):
        game, a, bear, aura = enchanted(BEAR)
        self.assertEqual((bear.card.type_line, bear.vehicled, aura.attached_to), ("Artifact — Vehicle", BEAR, bear))
        self.assertIn(aura, a.battlefield)
        game.combat.declare_attackers(a)
        self.assertEqual(game.combat.attacks, [])

    def test_a_legendary_permanent_stays_legendary(self):
        _, _, isamaru, _ = enchanted(ISAMARU)
        self.assertEqual(isamaru.card.type_line, "Legendary Artifact — Vehicle")

    def test_five_power_crews_it_and_less_does_not(self):
        game, a, _, _ = enchanted(BEAR, BEAR, BEAR)
        self.assertEqual(crew_actions(game, a), [])  # 2 + 2 is not 5
        game, a, bear, _ = enchanted(BEAR, BIG, policy=pick("Crew 5"))
        (action,) = crew_actions(game, a)
        game._perform(a, action)
        game._priority_round(a)
        self.assertEqual(("Artifact Creature" in bear.card.type_line, game.power(bear), game.toughness(bear)), (True, 2, 2))
        game.destroy(bear)  # crewed, it still goes to the graveyard as itself
        self.assertIn(BEAR, a.graveyard)

    def test_once_the_aura_is_gone_it_is_its_own_card_again(self):
        game, a, bear, aura = enchanted(BEAR)
        game.destroy(aura)
        game._check_state()
        self.assertEqual((bear.card, bear.vehicled, bear.original), (BEAR, None, None))

    def test_it_goes_to_the_graveyard_as_itself(self):
        game, a, bear, _ = enchanted(BEAR)
        game.destroy(bear)
        game._check_state()
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Swift Reconfiguration"])
        self.assertIn(BEAR, a.graveyard)


if __name__ == "__main__":
    unittest.main()
