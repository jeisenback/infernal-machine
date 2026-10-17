"""The bot holds creature removal until a creature is worth it (#394)."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import CAST, PASS
from tests.helpers import real

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
DOOM = real("Doom Blade", "{1}{B}", "Instant", "Destroy target nonblack creature.")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")
CRUSH = real("Crush Pest", "{R}", "Sorcery", "Crush Pest deals 2 damage to target creature.")
WIPE = real("Day of Doom", "{2}{W}{W}", "Sorcery", "Destroy all creatures.")
RAISE = real("Raise Lite", "{1}{B}", "Sorcery", "Return target creature card from your graveyard to the battlefield.")
BEAR = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", 2, 2)
DECK = Deck([], [MOUNTAIN, DOOM, BOLT, CRUSH, WIPE, BEAR, RAISE], [])
HOLD_OFF = FEATURES - {"hold"}


def creature(name, power, toughness):
    return {"name": name, "type": "Creature", "tapped": False, "sick": False, "power": power, "toughness": toughness}


def bot(theirs, hand=("Doom Blade",), life=20, features=FEATURES):
    b = BotPlayer("Bot", DECK, features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": life})
    b.notify({"event": "state", "hand": list(hand), "seats": [
        {"seat": 0, "lost": False, "life": life, "mana_pool": [], "battlefield": [creature("Mountain", None, None)] * 3},
        {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": list(theirs)}]})
    return b


def main_phase(b, *spells):
    options = [PASS] + [f"{CAST}{spell}" for spell in spells]
    return options[b.choose("Priority: main1", options)]


class HoldTests(unittest.TestCase):
    def test_removal_waits_while_the_opponents_creatures_are_small(self):
        small = [creature("Pest", 1, 1), creature("Bear", 2, 2)]
        self.assertEqual(main_phase(bot(small), "Doom Blade"), PASS)
        self.assertEqual(main_phase(bot(small, features=HOLD_OFF), "Doom Blade"), f"{CAST}Doom Blade", "the plain bot casts it at once")

    def test_it_is_cast_at_a_creature_worth_it(self):
        self.assertEqual(main_phase(bot([creature("Pest", 1, 1), creature("Ogre", 4, 4)]), "Doom Blade"), f"{CAST}Doom Blade")

    def test_not_while_it_is_in_trouble(self):
        small = [creature("Bear", 2, 2)]
        self.assertEqual(main_phase(bot(small, life=8), "Doom Blade"), f"{CAST}Doom Blade")
        self.assertEqual(main_phase(bot(small, life=11), "Doom Blade"), PASS)

    def test_not_with_a_full_hand(self):
        full = ["Doom Blade"] + ["Mountain"] * 6
        self.assertEqual(main_phase(bot([creature("Bear", 2, 2)], hand=full), "Doom Blade"), f"{CAST}Doom Blade")

    def test_burn_that_can_go_to_the_face_and_other_spells_are_not_held(self):
        small = [creature("Bear", 2, 2)]
        self.assertEqual(main_phase(bot(small, hand=("Lightning Bolt",)), "Lightning Bolt"), f"{CAST}Lightning Bolt")
        self.assertEqual(main_phase(bot(small, hand=("Grizzly Bears",)), "Grizzly Bears"), f"{CAST}Grizzly Bears")

    def test_a_sorcery_that_damages_a_creature_is_held_too(self):
        self.assertEqual(main_phase(bot([creature("Pest", 1, 1)], hand=("Crush Pest",)), "Crush Pest"), PASS)

    def test_what_else_it_can_cast_is_cast_instead(self):
        self.assertEqual(main_phase(bot([creature("Pest", 1, 1)], hand=("Doom Blade", "Grizzly Bears")), "Doom Blade", "Grizzly Bears"),
                         f"{CAST}Grizzly Bears")

    def test_with_no_creature_to_remove_it_holds_it_whatever_its_hand_or_life(self):
        # (it would go at one of its own creatures; the game offers it then)
        full = ["Doom Blade"] + ["Mountain"] * 6
        self.assertEqual(main_phase(bot([]), "Doom Blade"), PASS)
        self.assertEqual(main_phase(bot([], hand=full), "Doom Blade"), PASS)
        self.assertEqual(main_phase(bot([], life=5), "Doom Blade"), PASS)

    def test_a_spell_that_returns_a_creature_card_from_a_graveyard_is_not_removal(self):
        self.assertEqual(main_phase(bot([creature("Pest", 1, 1)], hand=("Raise Lite",)), "Raise Lite"), f"{CAST}Raise Lite")


if __name__ == "__main__":
    unittest.main()
