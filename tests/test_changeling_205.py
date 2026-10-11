"""Changeling (#205): the card is every creature type, so a Goblin lord, a Goblin-watching trigger and a tribal attack
restriction all see it; played from the cards' own Oracle text."""

import unittest

from infernal_machine.cards import Card, shown_type_line
from infernal_machine.creature_types import CREATURE_TYPES
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import attack_all
from tests.test_effects import table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

REMINDER = "(This card is every creature type.)"
MAULER = Card(name="Taurean Mauler", mana_cost="{2}{R}", cmc=3, type_line="Creature — Shapeshifter", power="4", toughness="4",
              oracle_text="Changeling " + REMINDER + "\nWhenever an opponent casts a spell, you may put a +1/+1 counter on this creature.")
AUTOMATON = Card(name="Universal Automaton", mana_cost="{1}", cmc=1, type_line="Artifact Creature — Shapeshifter", power="1",
                 toughness="1", oracle_text="Changeling " + REMINDER)
MISTFORM = Card(name="Mistform Ultimus", mana_cost="{3}{U}", cmc=4, type_line="Legendary Creature — Illusion", power="3", toughness="3",
                oracle_text="Mistform Ultimus is every creature type (even if this card isn't on the battlefield).")
KINDRED = Card(name="Shapely Spell", mana_cost="{1}{U}", cmc=2, type_line="Kindred Instant — Wizard", oracle_text="Changeling " + REMINDER + "\nDraw a card.")
BEAR = Card(name="Bear", mana_cost="{1}", cmc=1, type_line="Creature — Bear", power="2", toughness="2")
LORD = Card(name="Goblin Chieftain", mana_cost="{1}{R}", cmc=2, type_line="Creature — Goblin", power="2", toughness="2",
            oracle_text="Other Goblin creatures you control get +1/+1.")
WATCHER = Card(name="Watcher", mana_cost="{1}", cmc=1, type_line="Enchantment",
               oracle_text="Whenever another Goblin enters under your control, you gain 1 life.")
GRAVE = Card(name="Grave Goblin", mana_cost="{1}", cmc=1, type_line="Enchantment",
             oracle_text="Whenever a Goblin you control dies, you gain 1 life.")
WARD = Card(name="Inkwell", mana_cost="{1}", cmc=1, type_line="Enchantment",
            oracle_text="Inklings can't attack you or planeswalkers you control.")


class TypeLineTests(unittest.TestCase):
    def test_a_changeling_is_every_creature_type(self):
        subtypes = MAULER.type_line.partition("—")[2].split()
        words = {word for name in CREATURE_TYPES for word in name.split()}  # "Time Lord" is two words on a type line, as printed
        self.assertEqual(set(subtypes), words | {"Shapeshifter"})
        self.assertEqual(MAULER.type_line.split()[0], "Creature")

    def test_each_type_is_listed_once_and_the_printed_one_is_kept(self):
        subtypes = AUTOMATON.type_line.partition("—")[2].split()
        self.assertEqual(len(subtypes), len(set(subtypes)))
        self.assertTrue(AUTOMATON.type_line.startswith("Artifact Creature — Shapeshifter"))

    def test_kindred_and_the_older_wording_get_them_too(self):
        self.assertIn("Goblin", KINDRED.type_line.split())
        self.assertIn("Goblin", MISTFORM.type_line.split())
        self.assertIn("Illusion", MISTFORM.type_line.split())

    def test_a_card_without_changeling_is_unchanged(self):
        self.assertEqual(BEAR.type_line, "Creature — Bear")

    def test_mentioning_changeling_does_not_make_a_card_one(self):
        card = Card(name="Lover", type_line="Creature — Elf", power="1", toughness="1",
                    oracle_text="Creature spells you cast with changeling cost {1} less to cast.")
        self.assertEqual(card.type_line, "Creature — Elf")

    def test_a_token_copy_does_not_double_the_list(self):
        import dataclasses
        copy = dataclasses.replace(MAULER, type_line="Token " + MAULER.type_line)
        self.assertEqual(len(copy.type_line.split()), len(MAULER.type_line.split()) + 1)

    def test_players_are_shown_a_short_type_line(self):
        self.assertEqual(shown_type_line(MAULER), "Creature — every creature type")
        self.assertEqual(shown_type_line(BEAR), "Creature — Bear")
        game, _ = table3()
        game.seats[0].battlefield = [Permanent(MAULER)]
        self.assertEqual(game.snapshot(None)["seats"][0]["battlefield"][0]["type"], "Creature — every creature type")


class InTheGameTests(unittest.TestCase):
    def test_a_lord_of_goblins_buffs_it(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(LORD), Permanent(AUTOMATON), Permanent(BEAR)]
        self.assertEqual((game.power(a.battlefield[1]), game.power(a.battlefield[2])), (2, 2))  # the Automaton, not the Bear

    def test_a_trigger_that_watches_goblins_sees_it_enter(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(WATCHER)]
        life = a.life
        game._enter(a, Permanent(AUTOMATON))
        run_stack(game)
        self.assertEqual(a.life, life + 1)
        game._enter(a, Permanent(BEAR))
        run_stack(game)
        self.assertEqual(a.life, life + 1)  # a Bear is not a Goblin

    def test_a_trigger_that_watches_goblins_sees_it_die(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(GRAVE), Permanent(AUTOMATON)]
        life = a.life
        game.destroy(a.battlefield[1])
        run_stack(game)
        self.assertEqual(a.life, life + 1)

    def test_a_tribal_attack_restriction_stops_it(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        b.battlefield = [Permanent(WARD)]
        a.battlefield = [Permanent(AUTOMATON), Permanent(BEAR)]
        a.battlefield[0].sick = a.battlefield[1].sick = False
        game.combat.declare_attackers(a)
        self.assertEqual([x.attacker.card.name for x in game.combat.attacks], ["Bear"])  # the Automaton is an Inkling


class ReportTests(unittest.TestCase):
    def test_the_keyword_and_the_older_wording_are_supported(self):
        for card in (MAULER, AUTOMATON, MISTFORM, KINDRED):
            with self.subTest(card.name):
                self.assertEqual(unsupported_lines(card), [])


if __name__ == "__main__":
    unittest.main()
