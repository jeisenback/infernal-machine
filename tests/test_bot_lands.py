"""Which land the bot plays and which it fetches: tempo and colours (#408)."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import NONE_TAKEN, PASS, PLAY_LAND, SEARCH_CARD_PROMPT, SEARCH_LAND_HAND_PROMPT, SEARCH_LAND_PROMPT, SEARCH_PROMPT
from tests.helpers import real

PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
GAIN = Card(name="Blossom Gate", type_line="Land", produced_mana=("R",), oracle_text="This land enters tapped.\n{T}: Add {R}.")
BEAR = real("Red Bear", "{1}{R}", "Creature — Bear", "", "2", "2")
ONE = real("Red Spark", "{R}", "Instant", "Red Spark deals 1 damage to any target.")
THREE = real("Red Three", "{2}{R}", "Creature — Imp", "", "3", "3")
BLUE = real("Blue Clerk", "{1}{U}", "Creature — Wizard", "", "1", "1")
DECK = Deck([], [PLAINS, MOUNTAIN, ISLAND, GAIN, BEAR, ONE, THREE, BLUE], [])
NO_TEMPO = FEATURES - {"tempo"}
NO_FETCH = FEATURES - {"fetch"}


def permanent(name, kind="Basic Land", tapped=False, power=None, toughness=None):
    return {"name": name, "type": kind, "tapped": tapped, "sick": False, "power": power, "toughness": toughness}


def bot(mine, hand, features=FEATURES):
    b = BotPlayer("Bot", DECK, features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 20})
    b.notify({"event": "state", "hand": list(hand), "seats": [
        {"seat": 0, "lost": False, "life": 20, "mana_pool": [], "battlefield": list(mine)},
        {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": []}]})
    return b


def play(b, *lands):
    options = [PASS] + [f"{PLAY_LAND}{name}" for name in lands]
    return options[b.choose("Priority: main1", options)]


class TempoTests(unittest.TestCase):
    TWO_LANDS = [permanent("Mountain")] * 2

    def test_the_tapped_land_is_played_when_no_spell_needs_the_mana(self):
        # three lands in play next turn would cast Red Three; with a one-drop and a six-drop in hand nothing needs it
        hand = ["Red Spark", "Blossom Gate", "Mountain"]
        self.assertEqual(play(bot(self.TWO_LANDS, hand), "Blossom Gate", "Mountain"), f"{PLAY_LAND}Blossom Gate")

    def test_the_untapped_land_is_played_when_a_spell_needs_its_mana(self):
        hand = ["Red Three", "Blossom Gate", "Mountain"]  # two untapped lands now: a third untapped one casts Red Three
        self.assertEqual(play(bot(self.TWO_LANDS, hand), "Blossom Gate", "Mountain"), f"{PLAY_LAND}Mountain")

    def test_the_plain_bot_always_prefers_the_untapped_land(self):
        hand = ["Red Spark", "Blossom Gate", "Mountain"]
        self.assertEqual(play(bot(self.TWO_LANDS, hand, NO_TEMPO), "Blossom Gate", "Mountain"), f"{PLAY_LAND}Mountain")

    def test_a_spell_that_costs_more_than_one_extra_mana_does_not_count(self):
        hand = ["Red Three", "Blossom Gate", "Mountain"]
        self.assertEqual(play(bot([permanent("Mountain")], hand), "Blossom Gate", "Mountain"), f"{PLAY_LAND}Blossom Gate",
                         "one land in play: a third land's mana is not this turn's")

    def test_a_spell_it_could_already_cast_does_not_count(self):
        hand = ["Red Bear", "Blossom Gate", "Mountain"]  # two untapped lands pay for it already
        self.assertEqual(play(bot(self.TWO_LANDS, hand), "Blossom Gate", "Mountain"), f"{PLAY_LAND}Blossom Gate")

    def test_a_tapped_land_in_play_is_not_mana_it_has_now(self):
        hand = ["Red Bear", "Blossom Gate", "Mountain"]  # two lands in play, one tapped: the Bear needs the new land untapped
        mine = [permanent("Mountain"), permanent("Mountain", tapped=True)]
        self.assertEqual(play(bot(mine, hand), "Blossom Gate", "Mountain"), f"{PLAY_LAND}Mountain")

    def test_colours_still_come_first(self):
        hand = ["Blue Clerk", "Blossom Gate", "Island"]  # only the Island adds a colour the hand needs
        self.assertEqual(play(bot(self.TWO_LANDS, hand), "Blossom Gate", "Island"), f"{PLAY_LAND}Island")


class FetchTests(unittest.TestCase):
    def search(self, b, *names):
        options = list(names) + [NONE_TAKEN]
        return options[b.choose(SEARCH_CARD_PROMPT, options)]

    def test_it_fetches_the_land_that_adds_a_colour_the_hand_needs(self):
        b = bot([permanent("Mountain")] * 2, ["Blue Clerk"])
        self.assertEqual(self.search(b, "Plains", "Mountain", "Island"), "Island")

    def test_the_plain_bot_takes_the_first_land_listed(self):
        b = bot([permanent("Mountain")] * 2, ["Blue Clerk"], NO_FETCH)
        self.assertEqual(self.search(b, "Plains", "Mountain", "Island"), "Plains")

    def test_a_needed_colour_it_already_has_still_beats_one_nothing_needs(self):
        b = bot([permanent("Mountain")] * 2, ["Red Three"])
        self.assertEqual(self.search(b, "Plains", "Island", "Mountain"), "Mountain")

    def test_a_colour_the_lands_lack_beats_one_they_have_when_both_are_needed(self):
        b = bot([permanent("Mountain")] * 2, ["Red Three", "Blue Clerk"])
        self.assertEqual(self.search(b, "Mountain", "Island"), "Island")

    def test_an_untapped_land_beats_a_tapped_one_that_adds_the_same(self):
        b = bot([permanent("Plains")], ["Red Three"])
        self.assertEqual(self.search(b, "Blossom Gate", "Mountain"), "Mountain")

    def test_the_prompts_of_land_fetches_get_the_same_answer(self):
        for prompt in (SEARCH_PROMPT, SEARCH_LAND_PROMPT, SEARCH_LAND_HAND_PROMPT):
            with self.subTest(prompt=prompt):
                options = ["Plains", "Mountain", "Island"]
                b = bot([permanent("Mountain")] * 2, ["Blue Clerk"])
                self.assertEqual(options[b.choose(prompt, options)], "Island")
                plain = bot([permanent("Mountain")] * 2, ["Blue Clerk"], NO_FETCH)
                self.assertEqual(options[plain.choose(prompt, options)], "Plains")

    def test_a_search_for_something_else_is_left_alone(self):
        b = bot([permanent("Mountain")] * 2, ["Blue Clerk"])
        self.assertEqual(self.search(b, "Red Bear", "Red Three"), "Red Three", "the most expensive card, as before")


if __name__ == "__main__":
    unittest.main()
