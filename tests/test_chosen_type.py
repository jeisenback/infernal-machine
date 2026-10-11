"""Cards that name a creature type as they enter (Cavern of Souls and the others), each from its own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands, pick
from tests.test_lands import spell
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

ALL = ("C", "W", "U", "B", "R", "G")
CAVERN = Card(name="Cavern of Souls", type_line="Land", produced_mana=ALL,
              oracle_text="As this land enters, choose a creature type.\n{T}: Add {C}.\n{T}: Add one mana of any color. Spend this mana only to "
                          "cast a creature spell of the chosen type, and that spell can't be countered.")
TERRITORY = Card(name="Unclaimed Territory", type_line="Land", produced_mana=ALL,
                 oracle_text="As this land enters, choose a creature type.\n{T}: Add {C}.\n{T}: Add one mana of any color. Spend this mana only "
                             "to cast a creature spell of the chosen type.")
PILLAR = Card(name="Pillar of Origins", type_line="Artifact", mana_cost="{3}", cmc=3.0,
              oracle_text="As this artifact enters, choose a creature type.\n{T}: Add one mana of any color. Spend this mana only to cast a "
                          "creature spell of the chosen type.")
HALFLING = Card(name="Delighted Halfling", type_line="Creature — Halfling Citizen", mana_cost="{G}", cmc=1.0, power="1", toughness="2",
                oracle_text="{T}: Add {C}.\n{T}: Add one mana of any color. Spend this mana only to cast a legendary spell, and that spell "
                            "can't be countered.")
ELF = real("Elf Warrior", "{R}", "Creature — Elf Warrior", "", "1", "1")
GOBLIN = real("Goblin", "{R}", "Creature — Goblin", "", "1", "1")
ELF_SPELL = real("Elf Charm", "{R}", "Instant", "Draw a card.")
LEGEND = real("Legend", "{R}", "Legendary Creature — Human", "", "1", "1")
BEAR = real("Bear", "{R}", "Creature — Bear", "", "2", "2")
CHANGELING = Card(name="Changeling", type_line="Creature — Shapeshifter", mana_cost="{R}", cmc=1.0, power="1", toughness="1",
                  oracle_text="Changeling")


def seat_with(*permanents):
    game, _ = table3(None)
    a = game.seats[0]
    a.battlefield = list(permanents)
    return game, a


def on_table(a, name):
    return next(p for p in a.battlefield if p.card.name == name)


def payable(game, a, card):
    return game._payment(a, card) is not None


class CavernTests(unittest.TestCase):
    def test_it_pays_for_a_creature_of_the_chosen_type(self):
        game, a = seat_with(Permanent(CAVERN, chosen_type="Elf"))
        self.assertTrue(payable(game, a, ELF))

    def test_not_for_another_type(self):
        game, a = seat_with(Permanent(CAVERN, chosen_type="Elf"))
        self.assertFalse(payable(game, a, GOBLIN))

    def test_not_for_a_spell_that_is_not_a_creature(self):
        game, a = seat_with(Permanent(CAVERN, chosen_type="Elf"))
        self.assertFalse(payable(game, a, ELF_SPELL))

    def test_its_colorless_mana_pays_for_anything_generic(self):
        game, a = seat_with(Permanent(CAVERN, chosen_type="Elf"))
        self.assertTrue(payable(game, a, real("Rock", "{1}", "Artifact", "")))

    def test_a_changeling_is_of_every_type(self):
        game, a = seat_with(Permanent(CAVERN, chosen_type="Elf"))
        self.assertTrue(payable(game, a, CHANGELING))

    def test_without_a_chosen_type_it_only_makes_colorless(self):
        game, a = seat_with(Permanent(CAVERN))
        self.assertFalse(payable(game, a, ELF))

    def test_the_land_names_a_type_as_it_enters(self):
        game, _ = table3(pick("Elf"))
        a = game.seats[0]
        a.hand, a.library = [CAVERN], [ELF, GOBLIN, GOBLIN]
        game._perform(a, PLAY_LAND + "Cavern of Souls")
        self.assertEqual(a.battlefield[0].chosen_type, "Elf")

    def test_the_spell_cannot_be_countered(self):
        game, a = seat_with(Permanent(CAVERN, chosen_type="Elf"))
        a.hand = [ELF]
        game._perform(a, CAST + "Elf Warrior")
        self.assertTrue(game.uncounterable(game.stack[-1]))

    def test_a_spell_paid_by_other_lands_can_be_countered(self):
        game, a = seat_with(Permanent(CAVERN, chosen_type="Elf"), *lands(1))
        a.battlefield[0].tapped = True
        a.hand = [ELF]
        game._perform(a, CAST + "Elf Warrior")
        self.assertFalse(game.uncounterable(game.stack[-1]))

    def test_a_spell_it_could_not_help_cast_can_be_countered(self):
        game, a = seat_with(Permanent(CAVERN, chosen_type="Elf"), *lands(1))
        a.hand = [real("Goblin Two", "{1}{R}", "Creature \u2014 Goblin", "", "1", "1")]
        game._perform(a, CAST + "Goblin Two")
        self.assertEqual([p.tapped for p in a.battlefield], [True, True])  # the Cavern's mana was spent on it
        self.assertFalse(game.uncounterable(game.stack[-1]))

    def test_it_is_fully_playable(self):
        self.assertEqual(unsupported_lines(CAVERN), [])


class RelativesTests(unittest.TestCase):
    def test_unclaimed_territory_pays_for_the_type_but_leaves_the_spell_counterable(self):
        game, a = seat_with(Permanent(TERRITORY, chosen_type="Elf"))
        self.assertTrue(payable(game, a, ELF))
        self.assertFalse(payable(game, a, GOBLIN))
        a.hand = [ELF]
        game._perform(a, CAST + "Elf Warrior")
        self.assertFalse(game.uncounterable(game.stack[-1]))

    def test_pillar_of_origins_has_only_the_restricted_mana(self):
        game, a = seat_with(Permanent(PILLAR, chosen_type="Elf"))
        self.assertTrue(payable(game, a, ELF))
        self.assertFalse(payable(game, a, GOBLIN))
        self.assertFalse(payable(game, a, real("Rock", "{1}", "Artifact", "")))

    def test_delighted_halfling_pays_for_a_legendary_spell_and_protects_it(self):
        game, a = seat_with(Permanent(HALFLING, sick=False))
        self.assertTrue(payable(game, a, LEGEND))
        self.assertFalse(payable(game, a, BEAR))
        a.hand = [LEGEND]
        game._perform(a, CAST + "Legend")
        self.assertTrue(game.uncounterable(game.stack[-1]))

    def test_its_colorless_mana_still_pays_a_colorless_cost(self):
        game, a = seat_with(Permanent(HALFLING, sick=False))
        self.assertTrue(payable(game, a, real("Eldrazi", "{C}", "Legendary Creature \u2014 Eldrazi", "", "1", "1")))

    def test_the_halfling_is_a_creature_that_needs_to_be_free_of_summoning_sickness(self):
        game, a = seat_with(Permanent(HALFLING, sick=True))
        self.assertFalse(payable(game, a, LEGEND))

    def test_the_cards_are_fully_playable(self):
        self.assertEqual([unsupported_lines(c) for c in (TERRITORY, PILLAR, HALFLING)], [[], [], []])


AUTOMATON = real("Adaptive Automaton", "{3}", "Artifact Creature \u2014 Construct",
                 "As this creature enters, choose a creature type.\nThis creature is the chosen type in addition to its other types.\n"
                 "Other creatures you control of the chosen type get +1/+1.", "2", "2")
MIMIC = real("Metallic Mimic", "{2}", "Artifact Creature \u2014 Shapeshifter",
             "As this creature enters, choose a creature type.\nThis creature is the chosen type in addition to its other types.\n"
             "Each other creature you control of the chosen type enters with an additional +1/+1 counter on it.", "2", "1")
THRONE = real("Roaming Throne", "{4}", "Artifact Creature \u2014 Golem",
              "Ward {2}\nAs this creature enters, choose a creature type.\nThis creature is the chosen type in addition to its other types.\n"
              "If a triggered ability of another creature you control of the chosen type triggers, it triggers an additional time.", "4", "4")
BANNER = real("Heraldic Banner", "{3}", "Artifact",
              "As this artifact enters, choose a color.\nCreatures you control of the chosen color get +1/+0.\n{T}: Add one mana of the chosen color.")
TRIUMPH = real("Hall of Triumph", "{4}", "Legendary Artifact",
               "As Hall of Triumph enters, choose a color.\nCreatures you control of the chosen color get +1/+1.")
GAINER = real("Elf Gainer", "{1}", "Creature \u2014 Elf Druid", "When this creature enters, you gain 1 life.", "1", "1")
GOBLIN_GAINER = real("Goblin Gainer", "{1}", "Creature \u2014 Goblin", "When this creature enters, you gain 1 life.", "1", "1")
RED_BEAR = real("Red Bear", "{1}{R}", "Creature \u2014 Bear", "", "2", "2", colors=("R",))
GREEN_BEAR = real("Green Bear", "{1}{G}", "Creature \u2014 Bear", "", "2", "2", colors=("G",))
ELF_BEAR = real("Elf Bear", "{1}{G}", "Creature \u2014 Elf", "", "1", "1")


class ChosenTypeSelfTests(unittest.TestCase):
    def test_the_creature_is_the_type_it_named(self):
        game, _ = table3(pick("Elf"))
        a = game.seats[0]
        a.library = [ELF_BEAR, GOBLIN, GOBLIN]
        a.battlefield = lands(3)
        a.hand = [AUTOMATON]
        game._perform(a, CAST + "Adaptive Automaton")
        run_stack(game)
        automaton = on_table(a, "Adaptive Automaton")
        self.assertEqual((automaton.chosen_type, game.subtypes(automaton)), ("Elf", ["Construct", "Elf"]))

    def test_it_goes_to_the_graveyard_as_the_card_it_was(self):
        game, _ = table3(pick("Elf"))
        a = game.seats[0]
        a.library = [ELF_BEAR]
        a.battlefield = lands(3)
        a.hand = [AUTOMATON]
        game._perform(a, CAST + "Adaptive Automaton")
        run_stack(game)
        game.destroy(on_table(a, "Adaptive Automaton"))
        self.assertEqual([c.type_line for c in a.graveyard], ["Artifact Creature \u2014 Construct"])


class BuffTests(unittest.TestCase):
    def test_other_creatures_of_the_chosen_type_get_the_bonus(self):
        game, _ = table3(None)
        a, b, _ = game.seats
        automaton = Permanent(AUTOMATON, chosen_type="Elf")
        elf, goblin, enemy = Permanent(ELF_BEAR), Permanent(GOBLIN), Permanent(ELF_BEAR)
        a.battlefield = [automaton, elf, goblin]
        b.battlefield = [enemy]
        self.assertEqual((game.power(elf), game.power(goblin), game.power(enemy), game.power(automaton)), (2, 1, 1, 2))

    def test_it_does_not_buff_itself(self):
        game, _ = table3(None)
        a = game.seats[0]
        own = real("Adaptive Automaton", "{3}", "Artifact Creature \u2014 Construct Elf", AUTOMATON.oracle_text, "2", "2")
        automaton = Permanent(own, chosen_type="Elf")
        a.battlefield = [automaton]
        self.assertEqual(game.power(automaton), 2)

    def test_without_a_chosen_type_it_does_nothing(self):
        game, _ = table3(None)
        a = game.seats[0]
        elf = Permanent(ELF_BEAR)
        a.battlefield = [Permanent(AUTOMATON), elf]
        self.assertEqual(game.power(elf), 1)

    def test_the_chosen_color_gets_the_bonus(self):
        for card, wanted in ((BANNER, (3, 2)), (TRIUMPH, (3, 3))):
            game, _ = table3(None)
            a = game.seats[0]
            red, green = Permanent(RED_BEAR), Permanent(GREEN_BEAR)
            a.battlefield = [Permanent(card, chosen_color="R"), red, green]
            self.assertEqual((game.power(red), game.toughness(red)), wanted, card.name)
            self.assertEqual((game.power(green), game.toughness(green)), (2, 2), card.name)

    def test_a_banner_that_has_not_chosen_a_color_gives_nothing(self):
        game, _ = table3(None)
        a = game.seats[0]
        red = Permanent(RED_BEAR)
        a.battlefield = [Permanent(BANNER), red]
        self.assertEqual(game.power(red), 2)

    def test_the_color_is_named_as_it_enters(self):
        game, _ = table3(pick("Red"))
        a = game.seats[0]
        a.battlefield = lands(4)
        a.hand = [TRIUMPH]
        game._perform(a, CAST + "Hall of Triumph")
        run_stack(game)
        self.assertEqual(on_table(a, "Hall of Triumph").chosen_color, "R")

    def test_the_cards_are_fully_playable(self):
        self.assertEqual([unsupported_lines(c) for c in (AUTOMATON, MIMIC, THRONE, BANNER, TRIUMPH)], [[]] * 5)


class MimicTests(unittest.TestCase):
    def enter(self, card, *mimics):
        game, _ = table3(None)
        a = game.seats[0]
        a.battlefield = [Permanent(MIMIC, chosen_type="Elf") for _ in range(mimics[0])] if mimics else []
        entering = Permanent(card)
        game._enter(a, entering)
        return entering, a

    def test_another_creature_of_the_type_enters_with_a_counter(self):
        entering, _ = self.enter(ELF_BEAR, 1)
        self.assertEqual(entering.counters.get("+1/+1"), 1)

    def test_each_mimic_adds_one(self):
        entering, _ = self.enter(ELF_BEAR, 2)
        self.assertEqual(entering.counters.get("+1/+1"), 2)

    def test_another_type_gets_nothing(self):
        entering, _ = self.enter(GOBLIN, 1)
        self.assertEqual(entering.counters, {})

    def test_the_mimic_itself_gets_nothing(self):
        game, _ = table3(pick("Elf"))
        a = game.seats[0]
        a.library = [ELF_BEAR]
        mimic = Permanent(MIMIC)
        game._enter(a, mimic)
        self.assertEqual((mimic.chosen_type, mimic.counters), ("Elf", {}))


class ThroneTests(unittest.TestCase):
    def life_after_entering(self, card, with_throne=True):
        game, _ = table3(None)
        a = game.seats[0]
        a.battlefield = [Permanent(THRONE, chosen_type="Elf")] if with_throne else []
        game._enter(a, Permanent(card))
        run_stack(game)
        return a.life

    def test_a_creature_of_the_type_triggers_twice(self):
        self.assertEqual(self.life_after_entering(GAINER), 42)

    def test_other_creatures_trigger_once(self):
        self.assertEqual(self.life_after_entering(GOBLIN_GAINER), 41)

    def test_without_the_throne_it_triggers_once(self):
        self.assertEqual(self.life_after_entering(GAINER, with_throne=False), 41)

    def test_the_throne_does_not_double_its_own_abilities(self):
        game, _ = table3(pick("Elf"))
        a = game.seats[0]
        a.library = [ELF_BEAR]
        own = real("Throne Gainer", "{4}", "Artifact Creature \u2014 Golem",
                   THRONE.oracle_text + "\nWhen this creature enters, you gain 1 life.", "4", "4")
        throne = Permanent(own)
        game._enter(a, throne)
        run_stack(game)
        self.assertEqual((game.subtypes(throne), a.life), (["Golem", "Elf"], 41))


if __name__ == "__main__":
    unittest.main()
