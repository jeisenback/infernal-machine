"""The bot's "sink" judgment: mana it would leave unspent goes on an ability that costs only mana, in its own second main phase or at
an opponent's end step, and never on one that costs a card of its own or nothing at all."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import PASS
from infernal_machine.prompts import PRIORITY_PROMPT

SINK = "Activate: Scavenging Ooze (seat 0, #4): {G}: Exile target card from a graveyard."


FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def choice(step, option=SINK, active=0, features=FEATURES, stack=()):
    b = BotPlayer("Bot", Deck([], [FOREST], []), features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 20})
    b.notify({"event": "state", "active": active, "hand": [], "seats": [
        {"seat": 0, "lost": False, "life": 20, "mana_pool": [], "battlefield": [{"name": "Forest", "type": "Basic Land", "tapped": False}]},
        {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": []}]})
    b._stack = list(stack)
    return b.choose(PRIORITY_PROMPT(step), [PASS, option])


class SinkTests(unittest.TestCase):
    def test_its_own_second_main_phase_and_an_opponents_end_step(self):
        self.assertEqual((choice("main2"), choice("end", active=1)), (1, 1))

    def test_not_while_the_mana_may_still_be_wanted(self):
        self.assertEqual((choice("main1"), choice("end"), choice("main2", active=1), choice("upkeep", active=1),
                          choice("end", active=1, stack=[1])), (0, 0, 0, 0, 0))

    def test_only_a_cost_of_mana(self):
        for cost in ("Sacrifice another creature", "{1}, Sacrifice another creature", "{0}", "{2}, Exile this artifact"):
            self.assertEqual(choice("main2", f"Activate: Thing (seat 0, #4): {cost}: Scry 1."), 0, cost)
        self.assertEqual(choice("main2", "Activate: Thing (seat 0, #4): {2}{G/W}: Scry 1."), 1)

    def test_without_the_feature_it_passes(self):
        self.assertEqual(choice("main2", features=FEATURES - {"sink"}), 0)


if __name__ == "__main__":
    unittest.main()
