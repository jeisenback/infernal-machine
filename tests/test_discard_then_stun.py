"""Seasoned Cryomancer: loot, then tap and stun up to as many creatures as nonland cards were discarded (#564 row 7)."""

import unittest

from infernal_machine.effects import triggered_abilities
from infernal_machine.effects.families.library_and_hand import DiscardThenStun, Draw
from infernal_machine.game import TARGET_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, Permanent, Table, real

CRYOMANCER = real("Seasoned Cryomancer", "{1}{U}{U}", "Creature — Human Wizard",
                  "When this creature enters, draw two cards, then discard two cards. When you discard one or more nonland cards "
                  "this way, tap up to that many target creatures and put a stun counter on each of them.\n"
                  "{3}{U}{U}, Exile this card from your graveyard: Draw two cards.", "2", "2")
SPELL_1 = real("Spell 1", "{U}", "Sorcery", "")
SPELL_2 = real("Spell 2", "{U}", "Sorcery", "")


def cast(*answers, top):
    """Seat A casts the Cryomancer against B's Bear and Ogre, drawing `top`; `answers` are the discards and the targets."""
    bear, ogre = Permanent(BEAR), Permanent(OGRE)
    t = Table(CRYOMANCER, *answers, n=3, theirs=[bear, ogre], library=list(top) + [FOREST] * 5).cast()
    return t, bear, ogre


def target_prompts(t):
    return [prompt for prompt, _ in t.a.player.prompts if TARGET_PROMPT.matches(prompt)]


class ParseTests(unittest.TestCase):
    def test_the_card_is_read(self):
        self.assertEqual(unsupported_lines(CRYOMANCER), [])
        self.assertEqual(list(triggered_abilities(CRYOMANCER)[0].effects), [Draw(2), DiscardThenStun(2, "creature")])

    def test_an_opponents_discard_does_not_take_the_stun_sentence(self):
        other = real("Other", "{U}", "Sorcery", "Each opponent discards two cards. When you discard one or more nonland cards this "
                                                "way, tap up to that many target creatures and put a stun counter on each of them.")
        self.assertTrue(unsupported_lines(other))


class ResolveTests(unittest.TestCase):
    def test_two_nonland_discards_tap_and_stun_two_creatures(self):
        t, bear, ogre = cast("Spell 1", "Spell 2", "Bear", "Ogre", top=[SPELL_1, SPELL_2])
        self.assertEqual([c.name for c in t.a.graveyard], ["Spell 1", "Spell 2"])
        self.assertTrue(bear.tapped and ogre.tapped)
        self.assertEqual((bear.counters.get("stun"), ogre.counters.get("stun")), (1, 1))

    def test_a_discarded_land_does_not_count(self):
        t, bear, ogre = cast("Forest", "Spell 1", "Bear", "Ogre", top=[FOREST, SPELL_1])
        self.assertEqual(len(target_prompts(t)), 1)
        self.assertTrue(bear.tapped)
        self.assertEqual(bear.counters.get("stun"), 1)
        self.assertFalse(ogre.tapped)
        self.assertIsNone(ogre.counters.get("stun"))

    def test_two_lands_ask_for_no_targets(self):
        t, bear, ogre = cast("Forest", "Forest", top=[FOREST, FOREST])
        self.assertEqual(target_prompts(t), [])
        self.assertFalse(bear.tapped or ogre.tapped)

    def test_the_player_may_stop_early_and_cannot_pick_the_same_creature_twice(self):
        t, bear, ogre = cast("Spell 1", "Spell 2", "Bear", "No more", top=[SPELL_1, SPELL_2])
        prompts = [(p, options) for p, options in t.a.player.prompts if TARGET_PROMPT.matches(p)]
        self.assertEqual(len(prompts), 2)
        self.assertFalse(any(option.startswith("Bear") for option in prompts[1][1]))
        self.assertTrue(any(option.startswith("Ogre") for option in prompts[1][1]))
        self.assertTrue(bear.tapped)
        self.assertFalse(ogre.tapped)
        self.assertIsNone(ogre.counters.get("stun"))


if __name__ == "__main__":
    unittest.main()
