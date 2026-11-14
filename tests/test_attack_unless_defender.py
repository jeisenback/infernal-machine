""""This creature can't attack unless defending player controls ..." (CR 508.1c), from the cards' real Oracle text: the creature may
attack only the opponents who control such a permanent (an Island for Serpent of the Endless Sea, a blue permanent for Whimwader, a
creature with flying for Lurking Green Dragon); with none of them it doesn't attack at all."""

import unittest

from infernal_machine.combat import ATTACK_PROMPT
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIRD, real, table3

SERPENT = real("Serpent of the Endless Sea", "{4}{U}", "Creature — Serpent", "Serpent of the Endless Sea's power and toughness are each equal "
               "to the number of Islands you control.\nThis creature can't attack unless defending player controls an Island.", "*", "*",
               colors=("U",))
WHIMWADER = real("Whimwader", "{4}{U}", "Creature — Elemental", "This creature can't attack unless defending player controls a blue permanent.",
                 "6", "4", colors=("U",))
DRAGON = real("Lurking Green Dragon", "{3}{G}", "Creature — Dragon", "Flying\nThis creature can't attack unless defending player controls a "
              "creature with flying.", "4", "4", colors=("G",))
ISLAND = real("Island", "", "Basic Land — Island", "")
BLUE = real("Merfolk Looter", "{1}{U}", "Creature — Merfolk Rogue", "{T}: Draw a card, then discard a card.", "1", "1", colors=("U",))
OCTOPUS = real("Godhunter Octopus", "{5}{U}", "Creature — Octopus", "This creature can't attack unless defending player controls an enchantment "
               "or an enchanted permanent.", "5", "5", colors=("U",))


def attackable(attacker, seat1=(), seat2=(), own=()):
    """The options the attack prompt offers `attacker` (None when it isn't asked at all)."""
    seen = []

    def policy(prompt, options):
        if ATTACK_PROMPT.matches(prompt):
            seen.append(options)
        return 0
    game, _ = table3(policy)
    a, b, c = game.seats
    a.battlefield = [Permanent(attacker), *[Permanent(x) for x in own]]
    b.battlefield, c.battlefield = [Permanent(x) for x in seat1], [Permanent(x) for x in seat2]
    game.combat.declare_attackers(a)
    return [o for o in seen[0][1:]] if seen else None


class AttackUnlessDefenderTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SERPENT, WHIMWADER, DRAGON):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_kind_it_cant_match_leaves_the_line_unread(self):
        self.assertEqual(len(unsupported_lines(OCTOPUS)), 1)

    def test_only_an_opponent_with_an_island_can_be_attacked(self):
        options = attackable(SERPENT, seat1=[ISLAND], own=[ISLAND])
        self.assertEqual(len(options), 1)
        self.assertIn("seat 1", options[0])

    def test_with_no_such_opponent_it_does_not_attack(self):
        self.assertIsNone(attackable(SERPENT, seat1=[BEAR], seat2=[BEAR], own=[ISLAND]))
        self.assertIsNone(attackable(WHIMWADER, seat1=[BEAR]))
        self.assertIsNone(attackable(DRAGON, seat1=[BEAR]))

    def test_a_blue_permanent_and_a_flier(self):
        self.assertEqual(len(attackable(WHIMWADER, seat2=[BLUE])), 1)
        self.assertEqual(len(attackable(DRAGON, seat1=[BIRD], seat2=[BIRD])), 2)


if __name__ == "__main__":
    unittest.main()
