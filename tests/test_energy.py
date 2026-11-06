"""Energy (#471, #645): "you get {E}{E}" puts energy counters on the player, and "Pay {E}{E}" is a cost paid from them (CR 107.14).
Played from Inventor's Axe's real Oracle text: it gives two energy as it enters, and its equip cost is two energy."""

import unittest

from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, lands, real, run_stack, script, table3

AXE = real("Inventor's Axe", "{R}", "Artifact — Equipment", "Flash\nWhen this Equipment enters, you get {E}{E} (two energy counters).\nWhen "
           "this Equipment enters, attach it to target creature you control.\nEquipped creature gets +2/+0.\nEquip—Pay {E}{E}.", colors=("R",))


def offered(game, seat, prefix):
    return [x for x in game.legal_actions(seat) if x.startswith(prefix)]


class EnergyTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(AXE), [])

    def test_the_axe_gives_two_energy_and_its_equip_spends_them_once(self):
        game, _ = table3(script("Bear", "Ogre"))
        a, b, _ = game.seats
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        a.battlefield, a.hand = [*lands(1), bear, ogre], [AXE]
        game._perform(a, CAST + "Inventor's Axe")
        run_stack(game)
        axe = next(p for p in a.battlefield if p.card is AXE)
        self.assertEqual((a.player_counters.get("energy"), axe.attached_to, game.power(bear)), (2, bear, 4))
        self.assertEqual(b.player_counters.get("energy", 0), 0)
        game._perform(a, offered(game, a, ACTIVATE + "Inventor's Axe")[0])
        run_stack(game)
        self.assertEqual((a.player_counters["energy"], axe.attached_to, game.power(bear), game.power(ogre)), (0, ogre, 2, 5))
        self.assertEqual(offered(game, a, ACTIVATE + "Inventor's Axe"), [])  # no energy left to pay


if __name__ == "__main__":
    unittest.main()
