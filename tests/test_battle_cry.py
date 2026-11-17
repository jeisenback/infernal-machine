"""Issue #803: Battle cry, "(Whenever this creature attacks, each other attacking creature gets +1/+0 until end of turn.)" (CR 702.91a),
from the cards' real Oracle text. All nine cards whose only gap it was are fully playable. Accorder Paladin attacks with a Bear: the
Bear gets +1/+0, the Paladin itself does not, a creature of its controller's that isn't attacking does not, and the bonus ends with the
turn."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, OGRE, attack_all, end_turn, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Accorder Paladin", "Goblin Wardriver", "Hero of Bladehold", "Iraxxa, Empress of Mars", "Kuldotha Ringleader", "Loxodon Partisan",
         "Primaris Chaplain", "Rhox Veteran", "Sanguine Evangelist"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_battle_cry).
MUTATIONS = [
    ("infernal_machine/effects/outcomes.py", "     lambda m: PumpEach(_modifier(m, 1), attacking=True, other=True)),",
     "     lambda m: PumpEach(_modifier(m, 1), attacking=True)),", "not the creature itself"),
    ("infernal_machine/effects/outcomes.py", "     lambda m: PumpEach(_modifier(m, 1), attacking=True, other=True)),",
     "     lambda m: PumpEach(_modifier(m, 1), other=True)),", "only attacking creatures"),
    ("infernal_machine/effects/triggers.py", '        if line == "Battle cry":  # CR 702.91a', '        if False:  # CR 702.91a', "the trigger"),
]


def paladin_attacks():
    game, _ = table3(attack_all)
    a = game.seats[0]
    paladin, bear, ogre = Permanent(REAL["Accorder Paladin"], sick=False), Permanent(BEAR, sick=False), Permanent(OGRE, sick=True)  # (the Ogre can't attack yet)
    a.battlefield = [paladin, bear, ogre]
    game.step = "declare_attackers"
    game.combat.declare_attackers(a)
    run_stack(game)
    return game, a, paladin, bear, ogre


class BattleCryTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_each_other_attacking_creature_gets_plus_one_until_end_of_turn(self):
        game, a, paladin, bear, ogre = paladin_attacks()
        self.assertEqual([a_.attacker for a_ in game.combat.attacks], [paladin, bear])
        self.assertEqual((game.power(paladin), game.power(bear), game.power(ogre)), (3, 3, 3))  # (3/1, 2/2 + 1, 3/3 not attacking)
        end_turn(game, a)
        self.assertEqual(game.power(bear), 2)


if __name__ == "__main__":
    unittest.main()
