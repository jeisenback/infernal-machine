"""Two more Aura restrictions, from the cards' real Oracle text. Brainwash ("Enchanted creature can't attack unless its controller pays
{3}.") is a cost to attack (CR 508.1d) that `Combat._attack_tax` adds: its Bear attacks with three lands to pay it, not with two, and
another Bear beside it attacks for free. Serra Bestiary ("... its activated abilities with {T} in their costs can't be activated.")
stops the Druid's "{T}: Draw a card." and its {T} mana ability, but not its "{1}: ... gains vigilance"."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from tests.helpers import BEAR, lands, real, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Brainwash", "Serra Bestiary"]
BRAINWASH, BESTIARY = REAL["Brainwash"], REAL["Serra Bestiary"]
DRUID = real("Druid", "{G}", "Creature — Elf Druid", "{T}: Add {G}.\n{T}: Draw a card.\n{1}: This creature gains vigilance until end of turn.",
             "1", "1")

# The guards these tests are there to catch (python tools/mutate.py tests.test_aura_attack_tax).
MUTATIONS = [
    ("infernal_machine/combat.py", "                if buff.attack_tax:\n                    tax += cost_of(buff.attack_tax)", "                pass",
     "the Aura's cost to attack"),
    ("infernal_machine/game.py", "        if ability.tap and self._tap_abilities_barred(permanent):  # Serra Bestiary",
     "        if False:  # Serra Bestiary", "its {T} abilities"),
    ("infernal_machine/game.py", "        if ability.tap and self._tap_abilities_barred(permanent):  # Serra Bestiary",
     "        if self._tap_abilities_barred(permanent):  # Serra Bestiary", "only those with {T}"),
    ("infernal_machine/game.py", "        locks = {NO_ACTIVATING, NO_ACTIVATING_TAP} if mana else",
     "        locks = {NO_ACTIVATING} if mana else", "its {T} mana ability too"),
]


def attackers(game, seat):
    b = game.seats[1]
    return [p for p in seat.battlefield if "Creature" in p.card.type_line
            and b in game.combat._attackable(seat, p, [b], [])[0]]


class AuraRestrictionTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_brainwash_costs_three_to_attack(self):
        game, _ = table3()
        a = game.seats[0]
        washed, free = Permanent(BEAR, sick=False), Permanent(BEAR, sick=False)
        a.battlefield = [washed, Permanent(BRAINWASH, attached_to=washed), free] + lands(2)
        self.assertEqual(attackers(game, a), [free])
        a.battlefield += lands(1)
        self.assertEqual(attackers(game, a), [washed, free])

    def test_serra_bestiary_stops_only_its_tap_abilities(self):
        game, _ = table3()
        a = game.seats[0]
        druid = Permanent(DRUID, sick=False)
        a.battlefield = [druid, Permanent(BESTIARY, attached_to=druid)] + lands(1)
        offered = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Druid" in x]
        self.assertEqual((any("Draw a card" in x for x in offered), any("vigilance" in x for x in offered)), (False, True))
        self.assertEqual([s.permanent for s in game._mana_sources(a) if s.permanent is druid], [])


if __name__ == "__main__":
    unittest.main()
