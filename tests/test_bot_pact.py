"""The bot does not cast a Pact it could not pay for at its next upkeep, which would lose it the game: Pact of the Titan's {4}{R} needs
five mana sources in play (they untap for that upkeep)."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import CAST, PASS
from tests.helpers import real

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
TITAN = real("Pact of the Titan", "{0}", "Instant", "Create a 4/4 red Giant creature token.\nAt the beginning of your next upkeep, pay {4}{R}. "
             "If you don't, you lose the game.", colors=("R",))
DECK = Deck([], [MOUNTAIN, TITAN], [])
PACT_OFF = FEATURES - {"pact"}


def bot(lands, features=FEATURES):
    b = BotPlayer("Bot", DECK, features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 20})
    mountain = {"name": "Mountain", "type": "Basic Land — Mountain", "tapped": True, "sick": False, "power": None, "toughness": None}
    b.notify({"event": "state", "hand": ["Pact of the Titan"], "seats": [
        {"seat": 0, "lost": False, "life": 20, "mana_pool": [], "battlefield": [mountain] * lands},
        {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": []}]})
    return b


def main_phase(b):
    options = [PASS, f"{CAST}Pact of the Titan"]
    return options[b.choose("Priority: main1", options)]


class PactTests(unittest.TestCase):
    def test_not_without_the_mana_for_the_upkeep(self):
        self.assertEqual(main_phase(bot(4)), PASS)
        self.assertEqual(main_phase(bot(4, features=PACT_OFF)), f"{CAST}Pact of the Titan", "the plain bot casts it anyway")

    def test_with_five_sources_it_is_cast_even_when_they_are_tapped_now(self):
        self.assertEqual(main_phase(bot(5)), f"{CAST}Pact of the Titan")


if __name__ == "__main__":
    unittest.main()
