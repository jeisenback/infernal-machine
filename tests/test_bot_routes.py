"""The bot's "routes" judgment: the other ways to play a card. A fused split card and a face-down spell are weighed with the other casts
(the fused card for both halves' mana, the face-down one for {3}); ninjutsu is taken when offered; and encore, suspend and the rest go in
a main phase once nothing is left to cast."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import CAST, CAST_FACE_DOWN, CAST_FUSED, ENCORE, NINJUTSU, PASS
from infernal_machine.prompts import PRIORITY_PROMPT

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
TEAR = Card(name="Tear", mana_cost="{W}", cmc=1, type_line="Instant", oracle_text="Destroy target enchantment.\nFuse")
WEAR_TEAR = Card(name="Wear // Tear", mana_cost="{1}{R}", cmc=3, type_line="Instant", oracle_text="Destroy target artifact.\nFuse",
                 alternate=TEAR)
BIG = Card(name="Big Morph", mana_cost="{4}{G}{G}", cmc=6, type_line="Creature — Beast", power="6", toughness="6",
           oracle_text="Morph {4}{G}")
THREE = Card(name="Three Drop", mana_cost="{2}{R}", cmc=3, type_line="Creature — Imp", power="2", toughness="2")
DECK = Deck([], [MOUNTAIN, WEAR_TEAR, BIG, THREE], [])


def choice(step, options, lands=3, features=FEATURES):
    b = BotPlayer("Bot", DECK, features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 20})
    b.notify({"event": "state", "active": 0, "hand": [], "seats": [
        {"seat": 0, "lost": False, "life": 20, "mana_pool": [],
         "battlefield": [{"name": "Mountain", "type": "Basic Land", "tapped": False} for _ in range(lands)]},
        {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": []}]})
    return ([PASS, *options])[b.choose(PRIORITY_PROMPT(step), [PASS, *options])]


class RoutesTests(unittest.TestCase):
    def test_both_halves_fused_over_either_half(self):
        options = [CAST + "Wear", CAST + "Tear", CAST_FUSED + "Wear // Tear"]
        self.assertEqual(choice("main1", options), CAST_FUSED + "Wear // Tear")
        self.assertNotEqual(choice("main1", options, features=FEATURES - {"routes"}), CAST_FUSED + "Wear // Tear")

    def test_a_face_down_spell_is_counted_as_three_mana(self):
        options = [CAST + "Three Drop", CAST_FACE_DOWN + "Big Morph"]  # both spend all three lands: the first listed is kept
        self.assertEqual(choice("main1", options), CAST + "Three Drop")

    def test_encore_in_a_main_phase_once_nothing_is_cast(self):
        self.assertEqual(choice("main2", [ENCORE + "Big Morph"]), ENCORE + "Big Morph")
        self.assertEqual(choice("upkeep", [ENCORE + "Big Morph"]), PASS)
        self.assertEqual(choice("main1", [ENCORE + "Big Morph", CAST + "Three Drop"]), CAST + "Three Drop")
        self.assertEqual(choice("main2", [ENCORE + "Big Morph"], features=FEATURES - {"routes"}), PASS)

    def test_ninjutsu_when_offered(self):
        self.assertEqual(choice("declare_blockers", [NINJUTSU + "Ninja"]), NINJUTSU + "Ninja")
        self.assertEqual(choice("declare_blockers", [NINJUTSU + "Ninja"], features=FEATURES - {"routes"}), PASS)


if __name__ == "__main__":
    unittest.main()
