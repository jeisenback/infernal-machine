"""Confluence: "Choose three. You may choose the same mode more than once." (CR 700.2d). Righteous, Fiery and Wretched Confluence, and
Moment of Reckoning ("Choose up to four")."""

import unittest

from infernal_machine.game import CAST, DONE_MODES, MODE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, pick, real, script

HEADER = "Choose three. You may choose the same mode more than once.\n"
RIGHTEOUS = real("Righteous Confluence", "{3}{W}{W}", "Sorcery", HEADER + "• Create a 2/2 white Knight creature token with vigilance.\n"
                 "• Exile target enchantment.\n• You gain 5 life.")
FIERY = real("Fiery Confluence", "{2}{R}{R}", "Sorcery", HEADER + "• Fiery Confluence deals 1 damage to each creature.\n"
             "• Fiery Confluence deals 2 damage to each opponent.\n• Destroy target artifact.")
WRETCHED = real("Wretched Confluence", "{3}{B}{B}", "Instant", HEADER + "• Target player draws a card and loses 1 life.\n"
                "• Target creature gets -2/-2 until end of turn.\n• Return target creature card from your graveyard to your hand.")
RECKONING = real("Moment of Reckoning", "{3}{W}{W}{B}{B}", "Sorcery", "Choose up to four. You may choose the same mode more than once.\n"
                 "• Destroy target nonland permanent.\n• Return target nonland permanent card from your graveyard to the battlefield.")
GLOOM = real("Pacifism", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature can't attack or block.")


def watching(policy):
    """Wrap `policy` and record the options of every mode question."""
    asked = []

    def wrapped(prompt, options):
        if prompt.startswith(MODE_PROMPT):
            asked.append(list(options))
        return policy(prompt, options)
    return wrapped, asked


class ConfluenceTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (RIGHTEOUS, FIERY, WRETCHED, RECKONING):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_same_mode_three_times(self):
        t = Table(RIGHTEOUS, n=5, policy=pick("You gain")).cast()
        self.assertEqual(t.a.life, 40 + 15)

    def test_a_mode_twice_and_another_once(self):
        t = Table(RIGHTEOUS, n=5, policy=script("Create", "Create", "You gain")).cast()
        self.assertEqual((len([p for p in t.a.battlefield if "Knight" in p.card.type_line]), t.a.life), (2, 45))

    def test_each_instance_of_the_mode_happens(self):
        t = Table(FIERY, n=5, policy=pick("Fiery Confluence deals 2")).cast()
        self.assertEqual((t.b.life, t.c.life, t.a.life), (34, 34, 40))

    def test_modes_without_a_legal_target_are_not_offered(self):
        policy, asked = watching(pick("You gain"))
        Table(RIGHTEOUS, n=5, policy=policy).cast()
        self.assertTrue(all(not any("Exile target enchantment" in o for o in options) for options in asked))
        policy, asked = watching(pick("You gain"))
        Table(RIGHTEOUS, n=5, policy=policy, theirs=[Permanent(GLOOM)]).cast()
        self.assertTrue(all(any("Exile target enchantment" in o for o in options) for options in asked))

    def test_three_modes_are_chosen_even_when_only_one_is_possible(self):
        policy, asked = watching(pick("Target player draws"))
        t = Table(WRETCHED, n=5, policy=policy)  # no creature to shrink, none in the graveyard to return
        self.assertIn(CAST + "Wretched Confluence", t.game.legal_actions(t.a))
        t.cast()
        self.assertEqual([len(options) for options in asked], [1, 1, 1])
        self.assertEqual((len(t.a.hand), t.a.life), (3, 37))

    def test_done_is_only_offered_for_up_to(self):
        policy, asked = watching(pick("Destroy"))
        Table(FIERY, n=5, policy=policy).cast()
        self.assertTrue(all(DONE_MODES not in options for options in asked))
        policy, asked = watching(pick(DONE_MODES))
        Table(RECKONING, n=7, policy=policy, theirs=[Permanent(BEAR)]).cast()
        self.assertEqual(len(asked), 1)  # chose nothing, then done

    def test_each_instance_of_a_mode_picks_its_own_target(self):
        t = Table(RECKONING, n=7, policy=script("Destroy", "Destroy", "Done", "Bear", "Ogre"), theirs=[Permanent(BEAR), Permanent(OGRE)]).cast()
        self.assertEqual((t.b.battlefield, sorted(c.name for c in t.b.graveyard)), ([], ["Bear", "Ogre"]))


if __name__ == "__main__":
    unittest.main()
