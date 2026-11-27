"""Support N (CR 701.34): "Put a +1/+1 counter on each of up to N other target creatures.", from the cards' real Oracle text. All 11
cards whose only gap it was are fully playable. Gladehart Cavalry enters with a Bear and an Ogre on the battlefield: support 6 puts one
counter on each of them (each once, not twice), none on the Cavalry itself (offered first, it isn't a legal target: "other"), and the
four targets left over are left out. Shoulder to Shoulder (a sorcery, "Support 2. Draw a card.") puts a counter on each of two
creatures and draws."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, OGRE, choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Aerie Auxiliary", "Captured by Lagacs", "Expedition Raptor", "Gladehart Cavalry", "Joraga Auxiliary", "Lead by Example",
         "Press into Service", "Relief Captain", "Saddleback Lagac", "Shoulder to Shoulder", "Soulblade Renewer"]
CAVALRY, SHOULDER = REAL["Gladehart Cavalry"], REAL["Shoulder to Shoulder"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_support).
MUTATIONS = [
    ("infernal_machine/effects/outcomes.py", 'PutCounters(1, "+1/+1", "creature", another=True, optional_target=True, distinct=n > 0) for n in range(count)]',
     'PutCounters(1, "+1/+1", "creature", optional_target=True, distinct=n > 0) for n in range(count)]', "other creatures"),
    ("infernal_machine/effects/outcomes.py", 'PutCounters(1, "+1/+1", "creature", another=True, optional_target=True, distinct=n > 0) for n in range(count)]',
     'PutCounters(1, "+1/+1", "creature", another=True, optional_target=True) for n in range(count)]', "each creature once"),
    ("infernal_machine/effects/outcomes.py", 'lambda m: _support(int(m[1]))', 'lambda m: _support(1)', "N counters' worth of targets"),
]


class SupportTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_other_creatures_each_once(self):
        game, _ = table3()
        a = game.seats[0]
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        a.battlefield = [bear, ogre]
        cavalry = Permanent(CAVALRY)
        game.seats[0].player.policy = choose(game, cavalry, bear, ogre)
        game._enter(a, cavalry)
        run_stack(game)
        self.assertEqual([p.counters.get("+1/+1") for p in (cavalry, bear, ogre)], [None, 1, 1])

    def test_a_sorcery(self):
        game, _ = table3()
        a = game.seats[0]
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        a.battlefield, a.hand, a.library = [bear, ogre] + lands(3), [SHOULDER], [BEAR]
        game.seats[0].player.policy = choose(game, bear, ogre)
        game._perform(a, CAST + SHOULDER.name)
        run_stack(game)
        self.assertEqual(([p.counters.get("+1/+1") for p in (bear, ogre)], len(a.hand)), ([1, 1], 1))


if __name__ == "__main__":
    unittest.main()
