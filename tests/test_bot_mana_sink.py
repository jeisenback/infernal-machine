"""The bot spends spare mana on an ability that costs only mana (#553)."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import ACTIVATE, CAST, PASS
from tests.helpers import real

KINNAN = real("Kinnan, Bonder Prodigy", "{G}{U}", "Legendary Creature — Human Druid",
              "Whenever you tap a nonland permanent for mana, add one mana of any type that permanent produced.\n"
              "{5}{G}{U}: Look at the top five cards of your library. You may put a non-Human creature card from among them onto the battlefield. "
              "Put the rest on the bottom of your library in a random order.", 2, 2)
BEAR = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", 2, 2)
DECK = Deck([KINNAN], [Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",)), BEAR], [])
SINK = f"{ACTIVATE}Kinnan, Bonder Prodigy 2/2 (seat 0, #6): {{5}}{{G}}{{U}}: Look at the top five cards of your library."
PAID_WITH_CARDS = f"{ACTIVATE}Altar of Dementia (seat 0, #7): Sacrifice a creature: Target player mills cards equal to its power."
MANA_AND_CARDS = f"{ACTIVATE}Fling Engine (seat 0, #8): {{2}}, Discard a card: Draw a card."


def bot(turn=3, features=FEATURES):
    b = BotPlayer("Bot", DECK, features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 40})
    b.notify({"event": "state", "turn": turn, "hand": [], "seats": [{"seat": 0, "lost": False, "life": 40, "mana_pool": [], "battlefield": []}]})
    return b


def act(b, step, *options):
    options = [PASS, *options]
    return options[b.choose(f"Priority: {step}", options)]


class ManaSinkTests(unittest.TestCase):
    def test_it_activates_an_ability_that_costs_only_mana_when_nothing_else_is_left(self):
        self.assertEqual(act(bot(), "main2", SINK), SINK)

    def test_not_while_a_spell_can_be_cast(self):
        self.assertEqual(act(bot(), "main2", f"{CAST}Grizzly Bears", SINK), f"{CAST}Grizzly Bears")

    def test_not_in_the_first_main_phase(self):
        self.assertEqual(act(bot(), "main1", SINK), PASS)

    def test_once_a_turn_for_each_source_and_again_the_next_turn(self):
        b = bot()
        self.assertEqual(act(b, "main2", SINK), SINK)
        self.assertEqual(act(b, "main2", SINK), PASS, "it cannot loop")
        b.notify({"event": "state", "turn": 7, "hand": [], "seats": [{"seat": 0, "lost": False, "life": 40, "mana_pool": [], "battlefield": []}]})
        self.assertEqual(act(b, "main2", SINK), SINK)

    def test_an_ability_with_another_cost_is_not_a_mana_sink(self):
        self.assertEqual(act(bot(), "main2", PAID_WITH_CARDS, MANA_AND_CARDS), PASS)

    def test_the_plain_judgments_do_not_include_it(self):
        self.assertEqual(act(bot(features=FEATURES - {"sink"}), "main2", SINK), PASS)


if __name__ == "__main__":
    unittest.main()
