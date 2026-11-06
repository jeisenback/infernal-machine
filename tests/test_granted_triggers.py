"""Auras and Equipment that grant a triggered ability (#645): 'Enchanted creature has "Whenever this creature deals combat damage to a
player, you may draw a card."' (Sixth Sense) and Black Mage's Rod, whose Job select makes a 1/1 Hero to carry it. The creature hears the
quoted ability as its own, for as long as the Aura or Equipment is attached to it. Played from the cards' real Oracle text."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, enter, fire, lands, pick, real, run_stack, table3

ROD = real("Black Mage's Rod", "{1}{B}", "Artifact — Equipment", "Job select (When this Equipment enters, create a 1/1 colorless Hero "
           "creature token, then attach this to it.)\nEquipped creature gets +1/+0, has \"Whenever you cast a noncreature spell, this creature "
           "deals 1 damage to each opponent,\" and is a Wizard in addition to its other types.\nEquip {3}", colors=("B",))
SIXTH_SENSE = real("Sixth Sense", "{G}", "Enchantment — Aura", "Enchant creature\nEnchanted creature has \"Whenever this creature deals "
                   "combat damage to a player, you may draw a card.\"", colors=("G",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))


class GrantedTriggerTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (ROD, SIXTH_SENSE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_job_select_makes_a_hero_wizard_that_pings_each_opponent_for_each_noncreature_spell(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield, a.hand, a.library = lands(2), [OPT, BEAR], [BEAR] * 3
        rod = enter(game, a, ROD)
        run_stack(game)
        hero = rod.attached_to
        self.assertEqual((hero.card.name, game.power(hero), game.toughness(hero)), ("Hero", 2, 1))
        self.assertIn("Wizard", game.subtypes(hero))
        lives = (b.life, c.life)
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual((b.life, c.life), (lives[0] - 1, lives[1] - 1))
        game._perform(a, CAST + "Bear")  # a creature spell: nothing
        run_stack(game)
        self.assertEqual((b.life, c.life), (lives[0] - 1, lives[1] - 1))

    def test_an_opponents_spell_and_an_unattached_rod_do_nothing(self):
        game, _ = table3()
        a, b, c = game.seats
        rod = enter(game, a, ROD)
        run_stack(game)
        b.battlefield, b.hand = lands(1), [OPT]
        lives = (a.life, b.life, c.life)
        game._perform(b, CAST + "Opt")
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), lives)
        game.detach(rod)
        a.battlefield += lands(1)
        a.hand = [OPT]
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), lives)

    def test_an_aura_grants_a_combat_damage_trigger(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        bear, other = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [bear, other, Permanent(SIXTH_SENSE, attached_to=bear)]
        a.library = [BEAR] * 3
        fire(game, a, other, "combat_damage_to_player")
        self.assertEqual(len(a.hand), 0)
        fire(game, a, bear, "combat_damage_to_player")
        self.assertEqual(len(a.hand), 1)


if __name__ == "__main__":
    unittest.main()
