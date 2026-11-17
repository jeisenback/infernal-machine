"""Issue #800: Unleash, "(You may have this creature enter with a +1/+1 counter on it. It can't block as long as it has a +1/+1 counter on
it.)" (CR 702.98a), from the cards' real Oracle text. All eleven cards whose only gap it was are fully playable. On Rakdos Cackler: the
controller chooses as it enters; with the counter it can't block, without it it can, and it can block again once the counter is gone. A
creature without unleash blocks with a +1/+1 counter on it."""

import unittest

from infernal_machine.game import NOT_UNLEASHED, UNLEASH_PROMPT, UNLEASHED, Permanent
from tests.helpers import BEAR, COURSEWORK, OGRE, enter, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Bloodfray Giant", "Carnival Hellsteed", "Dead Reveler", "Gore-House Chainwalker", "Grim Roustabout", "Hellhole Flailer",
         "Rakdos Cackler", "Rakdos Drake", "Spawn of Rix Maadi", "Splatter Thug", "Thrill-Kill Assassin"]
CACKLER = REAL["Rakdos Cackler"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_unleash).
MUTATIONS = [
    ("infernal_machine/game.py", "seat.player.choose(UNLEASH_PROMPT(permanent.card.name), [UNLEASHED, NOT_UNLEASHED]) == 0:",
     "True:", "the counter is the controller's choice"),
    ("infernal_machine/combat.py", '        if blocker.counters.get("+1/+1", 0) > 0 and any(r.kind == "unleashed"',
     '        if any(r.kind == "unleashed"', "it can't block only while it has a counter"),
    ("infernal_machine/combat.py", 'any(r.kind == "unleashed" for r in combat_restrictions(blocker.card)) \\',
     "True \\", "only a creature with unleash"),
    ("infernal_machine/combat.py", "                and not self.game.loses_abilities(blocker):\n            return False  # Unleash",
     "                and True:\n            return False  # Unleash", "not once it has lost its abilities"),
]


def answer(choice):
    return lambda prompt, options: options.index(choice) if UNLEASH_PROMPT.matches(prompt) else 0


def cackler_enters(choice):
    game, _ = table3(answer(choice))
    a, b, _ = game.seats
    cackler = enter(game, a, CACKLER)
    attacker = Permanent(OGRE, sick=False)
    b.battlefield = [attacker]
    return game, cackler, attacker


class UnleashTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_with_the_counter_it_cant_block_and_without_it_it_can(self):
        game, cackler, attacker = cackler_enters(UNLEASHED)
        self.assertEqual((cackler.counters, game.combat._can_block(cackler, attacker)), ({"+1/+1": 1}, False))
        game, cackler, attacker = cackler_enters(NOT_UNLEASHED)
        self.assertEqual((cackler.counters, game.combat._can_block(cackler, attacker)), ({}, True))

    def test_it_blocks_again_once_the_counter_is_gone(self):
        game, cackler, attacker = cackler_enters(UNLEASHED)
        game.remove_counters(cackler, "+1/+1", 1)
        self.assertTrue(game.combat._can_block(cackler, attacker))

    def test_a_creature_without_unleash_blocks_with_a_counter(self):
        game, _, attacker = cackler_enters(UNLEASHED)
        bear = enter(game, game.seats[0], BEAR)
        bear.counters["+1/+1"] = 1
        self.assertTrue(game.combat._can_block(bear, attacker))

    def test_a_creature_that_lost_its_abilities_blocks_with_the_counter(self):
        game, cackler, attacker = cackler_enters(UNLEASHED)
        game.seats[1].battlefield.append(Permanent(COURSEWORK, attached_to=cackler))  # (enchanted creature loses all abilities)
        self.assertTrue(game.loses_abilities(cackler))
        self.assertTrue(game.combat._can_block(cackler, attacker))


if __name__ == "__main__":
    unittest.main()
