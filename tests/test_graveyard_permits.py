import dataclasses
import unittest

from infernal_machine.game import CAST_GRAVEYARD, CAST_PERMIT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, run_stack, table

GRAVECRAWLER = real("Gravecrawler", "{B}", "Creature — Zombie", "This creature can't block.\nYou may cast this card from your graveyard as long as you control a Zombie.", "2", "1")
GISA = real("Gisa and Geralf", "{2}{U}{B}", "Legendary Creature — Human Wizard",
            "When Gisa and Geralf enters, mill four cards.\nOnce during each of your turns, you may cast a Zombie creature spell from your graveyard.", "4", "4")
LURRUS = real("Lurrus of the Dream-Den", "{1}{W/B}{W/B}", "Legendary Creature — Cat Nightmare",
              "Companion — Each permanent card in your starting deck has mana value 2 or less. (If this card is your chosen companion, you may put it "
              "into your hand from outside the game for {3} as a sorcery.)\nLifelink\nOnce during each of your turns, you may cast a permanent spell "
              "with mana value 2 or less from your graveyard.", "3", "2")
DANITHA = real("Danitha, New Benalia's Light", "{1}{G}{W}", "Legendary Creature — Human Knight",
               "Vigilance, trample, lifelink\nOnce during each of your turns, you may cast an Aura or Equipment spell from your graveyard.", "2", "2")
ZOMBIE = real("Test Zombie", "{1}{B}", "Creature — Zombie", "", "2", "2")
SMALL_ARTIFACT = real("Test Relic", "{2}", "Artifact", "")
BIG_ARTIFACT = real("Big Relic", "{3}", "Artifact", "")
BOLT = real("Test Bolt", "{R}", "Instant", "Test Bolt deals 1 damage to any target.")
SWORD = real("Test Sword", "{1}", "Artifact — Equipment", "Equipped creature gets +1/+0.\nEquip {1}")


def actions(battlefield, graveyard, mana=6):
    game, _, _ = table(pick("Pass"))
    a = game.seats[0]
    a.battlefield = lands(mana) + [c if isinstance(c, Permanent) else Permanent(c) for c in battlefield]
    a.graveyard = list(graveyard)
    return game, a, [x for x in game.legal_actions(a) if x.startswith((CAST_GRAVEYARD, CAST_PERMIT))]


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (GRAVECRAWLER, GISA, LURRUS, DANITHA):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_companion_condition_the_game_does_not_check_is_not_understood(self):
        odd = real("Odd Pet", "{2}", "Creature — Cat", "Companion — Your starting deck contains only cards with a name that starts with Q.", "1", "1")
        self.assertNotEqual(unsupported_lines(odd), [])


class SelfPermissionTests(unittest.TestCase):
    def test_it_may_be_cast_from_the_graveyard_while_you_control_a_zombie(self):
        self.assertEqual(actions([ZOMBIE], [GRAVECRAWLER])[2], [CAST_GRAVEYARD + "Gravecrawler"])

    def test_not_without_a_zombie(self):
        self.assertEqual(actions([BEAR], [GRAVECRAWLER])[2], [])

    def test_it_is_cast_for_its_mana_cost_and_goes_back_to_the_graveyard_if_it_dies(self):
        game, _, _ = table(pick(CAST_GRAVEYARD))
        a = game.seats[0]
        a.battlefield = lands(2) + [Permanent(ZOMBIE)]
        a.graveyard = [GRAVECRAWLER]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], ["Test Zombie", "Gravecrawler"])
        self.assertEqual(a.graveyard, [])


class OncePerTurnTests(unittest.TestCase):
    def test_a_kind_of_spell_may_be_cast_from_the_graveyard(self):
        self.assertEqual(actions([GISA], [ZOMBIE, BEAR])[2], [CAST_PERMIT + "Test Zombie"])

    def test_a_card_that_is_not_that_kind_is_not_offered(self):
        self.assertEqual(actions([GISA], [BEAR, BOLT])[2], [])

    def test_a_mana_value_ceiling(self):
        self.assertEqual(actions([LURRUS], [SMALL_ARTIFACT, BIG_ARTIFACT, BOLT])[2], [CAST_PERMIT + "Test Relic"])

    def test_a_land_card_is_a_permanent_card_but_cannot_be_cast(self):
        land = real("Test Cave", "", "Land", "{T}: Add {G}.")
        self.assertEqual(actions([LURRUS], [land])[2], [])

    def test_a_permanent_that_has_lost_its_abilities_gives_no_permission(self):
        lurrus = Permanent(LURRUS)
        shackle = real("Test Shackle", "{1}{U}", "Enchantment — Aura",
                       "Enchant creature\nEnchanted creature loses all abilities and doesn't untap during its controller's untap step.")
        self.assertEqual(actions([LURRUS], [SMALL_ARTIFACT])[2], [CAST_PERMIT + "Test Relic"])
        game, a, found = actions([lurrus], [SMALL_ARTIFACT])
        a.battlefield.append(Permanent(shackle, attached_to=lurrus))
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST_PERMIT)], [])

    def test_aura_or_equipment(self):
        self.assertEqual(actions([DANITHA], [SWORD, SMALL_ARTIFACT])[2], [CAST_PERMIT + "Test Sword"])

    def test_only_once_each_turn_and_again_on_the_next(self):
        game, _, _ = table(pick(CAST_PERMIT))
        a = game.seats[0]
        a.battlefield = lands(8) + [Permanent(LURRUS)]
        a.graveyard = [SMALL_ARTIFACT, dataclasses.replace(SMALL_ARTIFACT, name="Second Relic")]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(sum(p.card.type_line == "Artifact" for p in a.battlefield), 1, "one cast this turn")
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST_PERMIT)], [], "the permission is used up")
        game.turn += 1
        self.assertEqual(len([x for x in game.legal_actions(a) if x.startswith(CAST_PERMIT)]), 1, "a new turn, a new use")

    def test_two_permanents_each_give_a_use(self):
        game, _, _ = table(pick(CAST_PERMIT))
        a = game.seats[0]
        a.battlefield = lands(8) + [Permanent(LURRUS), Permanent(dataclasses.replace(LURRUS, name="Second Lurrus"))]
        a.graveyard = [SMALL_ARTIFACT, dataclasses.replace(SMALL_ARTIFACT, name="Second Relic"), dataclasses.replace(SMALL_ARTIFACT, name="Third Relic")]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(sum(p.card.type_line == "Artifact" for p in a.battlefield), 2, "one use from each, and no third")


if __name__ == "__main__":
    unittest.main()
