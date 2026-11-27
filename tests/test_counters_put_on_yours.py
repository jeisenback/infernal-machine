""""Whenever one or more +1/+1 counters are put on (another|a) <creature> you control, ..." (the watch `plus_counters_put_on`, x: how
many), from the cards' real Oracle text. All four cards are fully playable. Enduring Scalelord gets a counter when one is put on a
Bear, not when one is put on itself or on an opponent's creature; Shalai and Hallar deals 2 damage to an opponent when two counters
are put on a Bear at once; Wildwood Scourge (a Hydra) grows for the Bear, not for another Hydra. Spider-Man, New Champion's
"deals that much damage to any target" is read by Shalai and Hallar's sentence."""

import unittest

from infernal_machine.game import OPTIONAL_PROMPT, Permanent
from tests.helpers import BEAR, choose, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Enduring Scalelord", "Shalai and Hallar", "Wildwood Scourge", "Spider-Man, New Champion"]
SCALELORD, SHALAI, SCOURGE = REAL["Enduring Scalelord"], REAL["Shalai and Hallar"], REAL["Wildwood Scourge"]
HYDRA = real("Little Hydra", "{G}", "Creature — Hydra", "", "1", "1")

# The guards these tests are there to catch (python tools/mutate.py tests.test_counters_put_on_yours).
MUTATIONS = [
    ("infernal_machine/game.py", '            self._observe("plus_counters_put_on", permanent.card, holder, subject=permanent, x=count)', "            pass",
     "the watch hears it"),
    ("infernal_machine/effects/triggers.py", 'Watch(m[2].lower(), other=m[1].lower() == "another", yours=True)',
     'Watch(m[2].lower(), yours=True)', "\"another\""),
    ("infernal_machine/effects/triggers.py", 'Watch(m[2].lower(), other=m[1].lower() == "another", yours=True)',
     'Watch(m[2].lower(), other=m[1].lower() == "another")', "\"you control\""),
]


def table(mine, theirs=()):
    game, players = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(c, sick=False) for c in mine]
    b.battlefield = [Permanent(c, sick=False) for c in theirs]
    players[0].policy = choose(game, b)
    return game, a, b


class CountersPutOnYoursTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_another_creature_you_control(self):
        game, a, b = table([SCALELORD, BEAR], theirs=[BEAR])
        scalelord, bear = a.battlefield
        uses = iter((0,))  # (once: a second "may" would be the Scalelord seeing its own counter)
        game.seats[0].player.policy = lambda prompt, options: next(uses, 1) if OPTIONAL_PROMPT.matches(prompt) else 0
        game.put_counters(bear, "+1/+1", 1)
        run_stack(game)
        self.assertEqual(scalelord.counters.get("+1/+1"), 1)

    def test_not_its_own_counters_nor_an_opponents_creature(self):
        game, a, b = table([SCALELORD], theirs=[BEAR])
        asked = []
        game.seats[0].player.policy = lambda prompt, options: asked.append(prompt) or (1 if OPTIONAL_PROMPT.matches(prompt) else 0)
        game.put_counters(a.battlefield[0], "+1/+1", 1)  # (were it to trigger, it is declined: no loop)
        game.put_counters(b.battlefield[0], "+1/+1", 1)
        run_stack(game)
        self.assertEqual([p for p in asked if OPTIONAL_PROMPT.matches(p)], [])

    def test_that_much_damage(self):
        game, a, b = table([SHALAI, BEAR])
        game.put_counters(a.battlefield[1], "+1/+1", 2)
        run_stack(game)
        self.assertEqual(b.life, 38)

    def test_not_for_another_hydra(self):
        game, a, _ = table([SCOURGE, HYDRA, BEAR])
        scourge, hydra, bear = a.battlefield
        scourge.counters["+1/+1"] = 1
        game.put_counters(hydra, "+1/+1", 1)
        run_stack(game)
        self.assertEqual(scourge.counters.get("+1/+1"), 1)
        game.put_counters(bear, "+1/+1", 1)
        run_stack(game)
        self.assertEqual(scourge.counters.get("+1/+1"), 2)


if __name__ == "__main__":
    unittest.main()
