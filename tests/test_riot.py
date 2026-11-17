"""Issue #805: Riot, "(This creature enters with your choice of a +1/+1 counter or haste.)" (CR 702.136a), from the cards' real Oracle
text. All eight cards whose only gap it was are fully playable. Zhur-Taa Goblin: its controller chooses as it enters; with the counter it
has no haste, with haste no counter, and the haste is the riot effect's, so it stays when the creature loses its abilities. A creature
without riot is not asked."""

import unittest

from infernal_machine.game import RIOT_COUNTER, RIOT_HASTE, RIOT_PROMPT, Permanent
from tests.helpers import BEAR, COURSEWORK, enter, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Arcbound Slasher", "Burning-Tree Vandal", "Clamor Shaman", "Frenzied Arynx", "Ghor-Clan Wrecker", "Rampaging Rendhorn",
         "Wrecking Beast", "Zhur-Taa Goblin"]
GOBLIN = REAL["Zhur-Taa Goblin"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_riot).
MUTATIONS = [
    ("infernal_machine/game.py", "            if seat.player.choose(RIOT_PROMPT(permanent.card.name), [RIOT_COUNTER, RIOT_HASTE]) == 0:",
     "            if True:", "the controller's choice"),
    ("infernal_machine/game.py", "            else:\n                permanent.rioted = True", "            else:\n                pass", "haste when chosen"),
    ("infernal_machine/game.py", '(keyword == "haste" and (permanent.blitzed or permanent.rioted))', '(keyword == "haste" and permanent.blitzed)',
     "the riot haste counts"),
]


def answer(choice):
    return lambda prompt, options: options.index(choice) if RIOT_PROMPT.matches(prompt) else 0


def goblin_enters(choice):
    game, players = table3(answer(choice))
    return game, players[0], enter(game, game.seats[0], GOBLIN)


class RiotTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_a_counter_or_haste_as_its_controller_chooses(self):
        game, _, goblin = goblin_enters(RIOT_COUNTER)
        self.assertEqual((goblin.counters, game.has_keyword(goblin, "haste")), ({"+1/+1": 1}, False))
        game, _, goblin = goblin_enters(RIOT_HASTE)
        self.assertEqual((goblin.counters, game.has_keyword(goblin, "haste")), ({}, True))

    def test_the_haste_stays_when_it_loses_its_abilities(self):
        game, _, goblin = goblin_enters(RIOT_HASTE)
        game.seats[1].battlefield.append(Permanent(COURSEWORK, attached_to=goblin))
        self.assertEqual((game.loses_abilities(goblin), game.has_keyword(goblin, "haste")), (True, True))

    def test_a_creature_without_riot_is_not_asked(self):
        game, player, _ = goblin_enters(RIOT_COUNTER)
        player.prompts.clear()
        bear = enter(game, game.seats[0], BEAR)
        self.assertEqual(([p for p, _ in player.prompts if RIOT_PROMPT.matches(p)], bear.counters), ([], {}))


if __name__ == "__main__":
    unittest.main()
