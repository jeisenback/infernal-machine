"""Removing a creature from combat (CR 506.4), from the cards' real Oracle text. Reconnaissance (#874 by EDHREC rank): "{0}: Remove
target attacking creature you control from combat and untap it." A Bear attacking is untapped and no longer attacking, so it deals no
combat damage; an opponent's attacker is not a legal target. Gustcloak Harrier: "Whenever this creature becomes blocked, you may untap it
and remove it from combat." Blocked by a Bird, it is untapped and out of combat, and the Bird is no longer blocking anything."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from tests.helpers import BEAR, attack_all, real, run_stack, table, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Reconnaissance", "Gustcloak Harrier", "Labyrinth of Skophos", "Hollowhenge Spirit"]
RECON, HARRIER = REAL["Reconnaissance"], REAL["Gustcloak Harrier"]
BIRD = real("Bird", "{1}{U}", "Creature — Bird", "Flying", "2", "2")

# The guards these tests are there to catch (python tools/mutate.py tests.test_remove_from_combat).
MUTATIONS = [
    ("infernal_machine/game.py", "        self.combat.attacks = [a for a in self.combat.attacks if a.attacker is not permanent]\n        for attack in self.combat.attacks:\n            attack.blockers = [b for b in attack.blockers if b is not permanent]\n        if untap:",
     "        if untap:", "it leaves combat"),
    ("infernal_machine/game.py", "        if untap:\n            self.untap(permanent)\n        self.broadcast({\"event\": \"removed_from_combat\"",
     "        self.broadcast({\"event\": \"removed_from_combat\"", "and is untapped"),
]


class RemoveFromCombatTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_reconnaissance_removes_its_own_attacker(self):
        game, _ = table3(attack_all)
        a, b, _ = game.seats
        bear = Permanent(BEAR, sick=False)
        a.battlefield = [Permanent(RECON), bear]
        game.combat.declare_attackers(a)
        self.assertTrue(bear.tapped)
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Remove target" in x))
        run_stack(game)
        self.assertEqual((bear.tapped, game.combat.attacks), (False, []))
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual(b.life, 40)

    def test_not_an_opponents_attacker(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(RECON)]
        b.battlefield = [Permanent(BEAR, sick=False)]
        game.active = 1
        game.combat.declare_attackers(b)
        self.assertFalse(any(x.startswith(ACTIVATE) and "Remove target" in x for x in game.legal_actions(a)))

    def test_gustcloak_harrier_leaves_combat_when_blocked(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        harrier, bird = Permanent(HARRIER, sick=False), Permanent(BIRD, sick=False)
        a.battlefield, b.battlefield = [harrier], [bird]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        run_stack(game)
        self.assertEqual((harrier.tapped, game.combat.attacks), (False, []))


if __name__ == "__main__":
    unittest.main()
