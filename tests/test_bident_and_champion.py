"""Two combat staples, from the cards' real Oracle text. Bident of Thassa (#448 by EDHREC rank): "{1}{U}, {T}: Creatures your opponents
control attack this turn if able." An opponent's Bear then attacks even when its player would rather not, and the Bident's controller's
own creatures are not made to. Champion of Lambholt (#594): "Creatures with power less than this creature's power can't block creatures
you control." With the Champion at power 3, a Bear (power 2) can't block its controller's Bear and an Ogre (power 3) can; without the
Champion the Bear can."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, OGRE, activate, lands, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Bident of Thassa", "Champion of Lambholt"]
BIDENT, CHAMPION = REAL["Bident of Thassa"], REAL["Champion of Lambholt"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_bident_and_champion).
MUTATIONS = [
    ("infernal_machine/effects/families/combat_and_pump.py", "        for seat in game.opponents(controller):\n            for permanent in seat.battlefield:\n                if \"Creature\" in permanent.card.type_line:",
     "        for seat in game.live_seats():\n            for permanent in seat.battlefield:\n                if \"Creature\" in permanent.card.type_line:", "only the opponents' creatures"),
    ("infernal_machine/combat.py", 'r.kind == "weaker_cant_block_yours" and self.game.power(blocker) < self.game.power(source)',
     'r.kind == "weaker_cant_block_yours" and self.game.power(blocker) <= self.game.power(source)', "less, not equal"),
    ("infernal_machine/combat.py", "        if owner is not None and any(r.kind == \"weaker_cant_block_yours\"",
     "        if False and any(r.kind == \"weaker_cant_block_yours\"", "the Champion's restriction"),
]


def stay_home(prompt, options):
    return 0


class BidentAndChampionTests(unittest.TestCase):
    def test_both_are_playable(self):
        wording_unlocked(self, CARDS)

    def test_bident_makes_the_opponents_creatures_attack(self):
        game, _ = table3(None, stay_home)
        a, b, _ = game.seats
        mine, theirs = Permanent(BEAR, sick=False), Permanent(BEAR, sick=False)
        a.battlefield = [Permanent(BIDENT), mine] + lands(2)
        b.battlefield = [theirs]
        activate(game, a, "attack this turn")
        self.assertEqual((theirs.must_attack_turn, mine.must_attack_turn), (game.turn, 0))
        game.active = 1
        game.combat.declare_attackers(b)
        self.assertEqual([x.attacker for x in game.combat.attacks], [theirs])

    def test_champion_stops_weaker_blockers(self):
        game, _ = table3()
        a, b, _ = game.seats
        champion, attacker = Permanent(CHAMPION, sick=False), Permanent(BEAR, sick=False)
        champion.counters["+1/+1"] = 2
        a.battlefield = [champion, attacker]
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        b.battlefield = [bear, ogre]
        self.assertEqual((game.combat._can_block(bear, attacker), game.combat._can_block(ogre, attacker)), (False, True))
        a.battlefield.remove(champion)
        self.assertTrue(game.combat._can_block(bear, attacker))


if __name__ == "__main__":
    unittest.main()
