"""Melee (CR 702.121): "Whenever this creature attacks, it gets +1/+1 until end of turn for each opponent you attacked with a creature
this combat.", from the cards' real Oracle text. All six cards whose only gap it was are fully playable. Wings of the Guard (1/1) and a
Bear attacking seat 1 and seat 2: 3/3; both at seat 1: 2/2; attacking only a planeswalker: no opponent attacked, 1/1 (CR 702.121b).
Adriana, Captain of the Guard gives other creatures melee: a Bear alone with her, both at seat 1, is a 3/3; Wings of the Guard with her
has melee twice and each triggers ("each triggers separately"): 1/1 + 2 = 3/3 against one opponent."""

import unittest

from infernal_machine.combat import ATTACK_PROMPT
from infernal_machine.game import Permanent
from tests.helpers import BEAR, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Adriana, Captain of the Guard", "Deputized Protester", "Ferocious Colonist", "Menagerie Liberator", "Titania, Proud Pummeler",
         "Wings of the Guard"]
WINGS, ADRIANA = REAL["Wings of the Guard"], REAL["Adriana, Captain of the Guard"]
WALKER = real("Test Walker", "{3}", "Legendary Planeswalker — Test", "+1: Draw a card.")

# The guards these tests are there to catch (python tools/mutate.py tests.test_melee).
MUTATIONS = [
    ("infernal_machine/effects/families/combat_and_pump.py", "if a.controller is controller and a.walker is None}",
     "if a.controller is controller}", "not by attacking a planeswalker"),
    ("infernal_machine/effects/families/combat_and_pump.py", "attacked = {id(a.defender) for a", "attacked = [id(a.defender) for a",
     "each opponent once"),
    ("infernal_machine/combat.py", '                for _ in range(sum("melee" in m.keywords for m in self.game.modifiers(permanent))):',
     "                for _ in range(0):", "granted melee triggers"),
]


def attack(cards, targets, walker=False):
    """Seat 0 attacks with `cards`, the n-th at the option `targets[n]` (1: seat 1, 2: seat 2, 3: seat 1's planeswalker)."""
    picks = iter(targets)

    def policy(prompt, options):
        return next(picks) if ATTACK_PROMPT.matches(prompt) else 0

    game, _ = table3(policy)
    a, b, _ = game.seats
    attackers = [Permanent(c, sick=False) for c in cards]
    a.battlefield = list(attackers)
    if walker:
        b.battlefield = [Permanent(WALKER, loyalty=3)]
    game.combat.declare_attackers(a)
    run_stack(game)
    return game, attackers


def size(game, permanent):
    return game.power(permanent), game.toughness(permanent)


class MeleeTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_one_for_each_opponent_attacked(self):
        game, (wings, _) = attack([WINGS, BEAR], [1, 2])
        self.assertEqual(size(game, wings), (3, 3))
        game, (wings, _) = attack([WINGS, BEAR], [1, 1])
        self.assertEqual(size(game, wings), (2, 2))

    def test_a_planeswalker_is_not_its_controller(self):
        game, (wings,) = attack([WINGS], [3], walker=True)
        self.assertEqual(size(game, wings), (1, 1))

    def test_granted_melee_and_each_instance_triggers(self):
        game, (_, bear) = attack([ADRIANA, BEAR], [1, 1])
        self.assertEqual(size(game, bear), (3, 3))
        game, (_, wings) = attack([ADRIANA, WINGS], [1, 1])
        self.assertEqual(size(game, wings), (3, 3))


if __name__ == "__main__":
    unittest.main()
