"""Disturb: the back face of a transforming card can be cast from the graveyard, and is exiled if it would go back."""

import dataclasses
import unittest

from infernal_machine.effects import disturb_of, replacement_effects
from infernal_machine.game import CAST, CAST_DISTURB, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, OGRE, real, run_stack, script, table3

EXILE_LINE = "If CARDNAME would be put into a graveyard from anywhere, exile it instead."
PHANTOM = real("Luminous Phantom", "", "Creature — Spirit", f"Flying\n{EXILE_LINE}", "2", "2")
VETERAN = dataclasses.replace(
    real("Lunarch Veteran // Luminous Phantom", "{W}", "Creature — Human Cleric", "Whenever another creature enters under your control, you gain 1 "
         "life.\nDisturb {1}{W} (You may cast this card transformed from your graveyard for its disturb cost.)", "1", "1"),
    flip=dataclasses.replace(PHANTOM, cmc=1.0))
EMBRACE = real("Ancestor's Embrace", "", "Enchantment — Aura", f"Enchant creature\nEnchanted creature gets +2/+2.\n{EXILE_LINE}")
ANCESTOR = dataclasses.replace(
    real("Kindly Ancestor // Ancestor's Embrace", "{1}{W}", "Creature — Spirit Cleric", "Disturb {1}{W}", "2", "2"),
    flip=dataclasses.replace(EMBRACE, cmc=2.0))
COUNTER = real("Counter", "{U}", "Instant", "Counter target spell.")


def table(*graveyard, mana=2, hand=()):
    game, _ = table3(script("Pass"))
    a = game.seats[0]
    a.hand, a.graveyard, a.exile = list(hand), list(graveyard), []
    a.battlefield = lands(mana)
    game.turn, game.step = 2, "main1"
    return game, a


def disturb(game, seat, card):
    game._perform(seat, CAST_DISTURB + card.name)
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (VETERAN, ANCESTOR):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_cost_is_read(self):
        self.assertEqual(disturb_of(VETERAN), "{1}{W}")
        self.assertIsNone(disturb_of(BEAR))

    def test_the_back_is_exiled_instead_of_going_to_a_graveyard(self):
        self.assertTrue(replacement_effects(PHANTOM).graveyard_self)
        self.assertFalse(replacement_effects(BEAR).graveyard_self)


class CastTests(unittest.TestCase):
    def test_it_is_offered_from_the_graveyard(self):
        game, a = table(VETERAN)
        self.assertIn(CAST_DISTURB + VETERAN.name, game.legal_actions(a))

    def test_not_from_the_hand(self):
        game, a = table(hand=[VETERAN])
        self.assertNotIn(CAST_DISTURB + VETERAN.name, game.legal_actions(a))

    def test_not_without_the_mana(self):
        game, a = table(VETERAN, mana=1)
        self.assertNotIn(CAST_DISTURB + VETERAN.name, game.legal_actions(a))

    def test_not_at_instant_speed_for_a_creature(self):
        game, a = table(VETERAN)
        game.step = "combat"
        self.assertNotIn(CAST_DISTURB + VETERAN.name, game.legal_actions(a))

    def test_a_card_without_disturb_has_no_such_action(self):
        game, a = table(BEAR)
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(CAST_DISTURB)])

    def test_it_enters_as_its_back_face(self):
        game, a = table(VETERAN)
        disturb(game, a, VETERAN)
        [phantom] = a.battlefield[2:]
        self.assertEqual((phantom.card.name, game.power(phantom)), ("Luminous Phantom", 2))
        self.assertIs(phantom.transformed_from, VETERAN)
        self.assertEqual(a.graveyard, [])
        self.assertEqual(game._mana_sources(a), [])

    def test_the_mana_value_is_the_front_faces(self):
        game, a = table(VETERAN)
        disturb(game, a, VETERAN)
        self.assertEqual(a.battlefield[-1].card.cmc, 1.0)

    def test_when_it_dies_it_is_exiled_not_buried(self):
        game, a = table(VETERAN)
        disturb(game, a, VETERAN)
        game.destroy(a.battlefield[-1])
        self.assertEqual(a.graveyard, [])
        self.assertEqual(a.exile, [VETERAN])

    def test_the_front_face_still_goes_to_the_graveyard(self):
        game, a = table(hand=[VETERAN])
        a.battlefield = lands(2) + [Permanent(VETERAN)]
        game.destroy(a.battlefield[-1])
        self.assertEqual(a.graveyard, [VETERAN])

    def test_once_exiled_it_cannot_be_cast_again(self):
        game, a = table(VETERAN, mana=4)
        disturb(game, a, VETERAN)
        game.destroy(a.battlefield[-1])
        self.assertNotIn(CAST_DISTURB + VETERAN.name, game.legal_actions(a))

    def test_it_is_not_cast_from_the_graveyard_the_normal_way(self):
        game, a = table(VETERAN)
        self.assertNotIn(CAST + VETERAN.name, game.legal_actions(a))


class AuraTests(unittest.TestCase):
    def test_an_aura_back_enchants_a_creature(self):
        game, a = table(ANCESTOR)
        a.battlefield.append(Permanent(BEAR))
        disturb(game, a, ANCESTOR)
        aura = next(p for p in a.battlefield if p.transformed_from is ANCESTOR)
        self.assertIs(aura.attached_to, a.battlefield[2])
        self.assertEqual(game.power(a.battlefield[2]), 4)

    def test_it_needs_a_creature_to_enchant(self):
        game, a = table(ANCESTOR)
        self.assertNotIn(CAST_DISTURB + ANCESTOR.name, game.legal_actions(a))

    def test_a_fizzled_aura_is_exiled(self):
        game, a = table(ANCESTOR)
        a.battlefield.append(Permanent(BEAR))
        game._perform(a, CAST_DISTURB + ANCESTOR.name)
        a.battlefield.remove(a.battlefield[2])  # the creature is gone as it resolves
        run_stack(game)
        self.assertEqual(a.graveyard, [])
        self.assertEqual(a.exile, [ANCESTOR])

    def test_a_countered_spell_is_exiled(self):
        game, a = table(VETERAN)
        game._perform(a, CAST_DISTURB + VETERAN.name)
        game.counter(game.stack[-1])
        self.assertEqual(a.graveyard, [])
        self.assertEqual(a.exile, [VETERAN])


if __name__ == "__main__":
    unittest.main()
