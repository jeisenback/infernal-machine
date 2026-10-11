"""Mana artifacts among the most played cards (Chromatic Lantern, Chrome Mox, Mox Diamond, Phyrexian Altar, Lion's Eye Diamond ...),
each from its own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import RAINBOW, FOREST as EFFECTS_FOREST, lands, pick
from tests.test_lands import spell
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_triggers_80 import FOREST
from tests.test_x_targets import script

LANTERN = real("Chromatic Lantern", "{3}", "Artifact",
               "Lands you control have \"{T}: Add one mana of any color.\"\n{T}: Add one mana of any color.")
CHROME = real("Chrome Mox", "{0}", "Artifact",
              "Imprint — When this artifact enters, you may exile a nonartifact, nonland card from your hand.\n"
              "{T}: Add one mana of any of the exiled card's colors.")
AMBER = real("Mox Amber", "{0}", "Legendary Artifact",
             "{T}: Add one mana of any color among legendary creatures and planeswalkers you control.")
DIAMOND = real("Mox Diamond", "{0}", "Artifact",
               "If this artifact would enter, you may discard a land card instead. If you do, put this artifact onto the battlefield. "
               "If you don't, put it into its owner's graveyard.\n{T}: Add one mana of any color.")
ALTAR = real("Phyrexian Altar", "{3}", "Artifact", "Sacrifice a creature: Add one mana of any color.")
DRUM = real("Springleaf Drum", "{1}", "Artifact", "{T}, Tap an untapped creature you control: Add one mana of any color.")
RELIC = real("Relic of Legends", "{3}", "Artifact",
             "Tap an untapped legendary creature you control: Add one mana of any color.\n"
             "{T}: Add one mana of any color.")
LED = real("Lion's Eye Diamond", "{0}", "Artifact",
           "Discard your hand, Sacrifice this artifact: Add three mana of any one color. Activate only as an instant.")
SAURON = real("Relic of Sauron", "{3}", "Artifact", "{T}: Add two mana in any combination of {U}, {B}, and/or {R}.")
LOTUS = real("Nyx Lotus", "{5}", "Artifact", "{T}: Choose a color. Add an amount of mana of that color equal to your devotion to that color.")
HENGE = real("The Great Henge", "{7}{G}{G}", "Legendary Artifact",
             "This spell costs {X} less to cast, where X is the greatest power among creatures you control.\n"
             "{T}: Add {G}{G}. You gain 2 life.\nWhenever a nontoken creature you control enters, put a +1/+1 counter on it and draw a card.")

RED_CREATURE = real("Red Creature", "{1}{R}", "Creature — Goblin", "", "2", "2", colors=("R",))
GOLD_CREATURE = real("Gold Creature", "{R}{G}", "Creature — Elf", "", "2", "2", colors=("R", "G"))
GREEN_LEGEND = real("Green Legend", "{G}", "Legendary Creature — Elf", "", "1", "1", colors=("G",))
BLUE_WALKER = real("Blue Walker", "{3}{U}", "Legendary Planeswalker — Test", "", colors=("U",))
WHITE_BEAR = real("White Bear", "{1}{W}", "Creature — Bear", "", "2", "2", colors=("W",))
BLACK_PIPS = real("Black Pips", "{B}{B}{B}", "Creature — Wizard", "", "1", "1", colors=("B",))
BEAR = real("Bear", "{1}", "Creature — Bear", "", "2", "2")


def table_for(*answers):
    game, _ = table3(script(*answers))
    return game, game.seats[0]


def payable(game, a, cost):
    return game._payment(a, spell(cost)) is not None


class LanternTests(unittest.TestCase):
    def test_lands_make_any_color(self):
        game, a = table_for()
        a.battlefield = [Permanent(LANTERN), Permanent(FOREST)]
        self.assertTrue(payable(game, a, "{R}{U}"))

    def test_without_it_a_forest_makes_green(self):
        game, a = table_for()
        a.battlefield = [Permanent(FOREST), Permanent(FOREST)]
        self.assertTrue(payable(game, a, "{G}{G}"))
        self.assertFalse(payable(game, a, "{R}{G}"))

    def test_opponents_lands_are_not_changed(self):
        game, a = table_for()
        b = game.seats[1]
        a.battlefield = [Permanent(LANTERN)]
        b.battlefield = [Permanent(FOREST)]
        self.assertFalse(payable(game, b, "{R}"))

    def test_the_lantern_itself_makes_any_color(self):
        game, a = table_for()
        a.battlefield = [Permanent(LANTERN)]
        self.assertTrue(payable(game, a, "{W}"))

    def test_the_card_is_fully_playable(self):
        self.assertEqual(unsupported_lines(LANTERN), [])


class ChromeMoxTests(unittest.TestCase):
    def cast(self, hand, *answers):
        game, a = table_for(*answers)
        a.hand = [CHROME, *hand]
        game._perform(a, CAST + "Chrome Mox")
        run_stack(game)
        return game, a

    def test_it_exiles_a_card_and_makes_its_colors(self):
        game, a = self.cast([RED_CREATURE, WHITE_BEAR], "Yes", "Red Creature")
        mox = next(p for p in a.battlefield if p.card.name == "Chrome Mox")
        self.assertEqual(([c.name for c in a.exile], [c.name for c in a.hand]), (["Red Creature"], ["White Bear"]))
        self.assertTrue(payable(game, a, "{R}"))
        self.assertFalse(payable(game, a, "{W}"))
        self.assertEqual([c.name for _, c in mox.exiled_with], ["Red Creature"])

    def test_a_two_color_card_gives_either(self):
        game, a = self.cast([GOLD_CREATURE], "Yes", "Gold Creature")
        self.assertTrue(payable(game, a, "{R}"))
        game2, a2 = self.cast([GOLD_CREATURE], "Yes", "Gold Creature")
        self.assertTrue(payable(game2, a2, "{G}"))

    def test_declining_leaves_it_without_mana(self):
        game, a = self.cast([RED_CREATURE], "No")
        self.assertEqual(([c.name for c in a.exile], len(a.hand)), ([], 1))
        self.assertFalse(payable(game, a, "{R}"))

    def test_lands_and_artifacts_cannot_be_exiled(self):
        game, a = self.cast([FOREST, ALTAR], "Yes")
        self.assertEqual(([c.name for c in a.exile], len(a.hand)), ([], 2))

    def test_a_colorless_card_makes_no_mana(self):
        game, a = self.cast([BEAR], "Yes", "Bear")
        self.assertEqual([c.name for c in a.exile], ["Bear"])
        self.assertFalse(payable(game, a, "{1}"))

    def test_the_card_is_fully_playable(self):
        self.assertEqual(unsupported_lines(CHROME), [])


class MoxAmberTests(unittest.TestCase):
    def test_it_makes_the_colors_of_legendary_creatures_and_planeswalkers(self):
        game, a = table_for()
        a.battlefield = [Permanent(AMBER), Permanent(GREEN_LEGEND), Permanent(BLUE_WALKER), Permanent(RED_CREATURE)]
        self.assertTrue(payable(game, a, "{G}"))
        a.battlefield[0].tapped = False
        self.assertFalse(payable(game, a, "{R}"))

    def test_a_planeswalker_counts(self):
        game, a = table_for()
        a.battlefield = [Permanent(AMBER), Permanent(BLUE_WALKER)]
        self.assertTrue(payable(game, a, "{U}"))

    def test_without_a_legendary_creature_it_makes_nothing(self):
        game, a = table_for()
        a.battlefield = [Permanent(AMBER), Permanent(RED_CREATURE)]
        self.assertFalse(payable(game, a, "{R}"))

    def test_a_legendary_permanent_that_is_neither_does_not_count(self):
        game, a = table_for()
        a.battlefield = [Permanent(AMBER), Permanent(real("Green Shrine", "{G}", "Legendary Enchantment", "", colors=("G",)))]
        self.assertFalse(payable(game, a, "{G}"))

    def test_an_opponents_legend_does_not_count(self):
        game, a = table_for()
        game.seats[1].battlefield = [Permanent(GREEN_LEGEND)]
        a.battlefield = [Permanent(AMBER)]
        self.assertFalse(payable(game, a, "{G}"))

    def test_the_card_is_fully_playable(self):
        self.assertEqual(unsupported_lines(AMBER), [])


class MoxDiamondTests(unittest.TestCase):
    def cast(self, hand, *answers):
        game, a = table_for(*answers)
        a.hand = [DIAMOND, *hand]
        game._perform(a, CAST + "Mox Diamond")
        run_stack(game)
        return game, a

    def test_discarding_a_land_puts_it_onto_the_battlefield(self):
        game, a = self.cast([FOREST], "Forest")
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in a.graveyard], a.hand), (["Mox Diamond"], ["Forest"], []))
        self.assertTrue(payable(game, a, "{R}"))

    def test_not_discarding_puts_it_into_the_graveyard(self):
        game, a = self.cast([FOREST], "Don't")
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in a.graveyard], len(a.hand)),
                         ([], ["Mox Diamond"], 1))

    def test_without_a_land_it_goes_to_the_graveyard(self):
        game, a = self.cast([RED_CREATURE])
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in a.graveyard]), ([], ["Mox Diamond"]))

    def test_the_card_is_fully_playable(self):
        self.assertEqual(unsupported_lines(DIAMOND), [])


def activate(game, a, name):
    actions = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and name in x]
    return actions


def use(game, a, name):
    [action] = activate(game, a, name)
    game._perform(a, action)
    run_stack(game)


class ActivatedManaTests(unittest.TestCase):
    def test_the_altar_turns_a_creature_into_mana(self):
        game, a = table_for("Red Creature")
        creature = Permanent(RED_CREATURE)
        a.battlefield = [Permanent(ALTAR), creature]
        use(game, a, "Phyrexian Altar")
        self.assertEqual((a.battlefield[0].card.name, [c.name for c in a.graveyard], len(a.mana_pool)), ("Phyrexian Altar", ["Red Creature"], 1))
        self.assertEqual(a.mana_pool[0], frozenset("WUBRG"))

    def test_the_altar_needs_a_creature(self):
        game, a = table_for()
        a.battlefield = [Permanent(ALTAR)]
        self.assertEqual(activate(game, a, "Phyrexian Altar"), [])

    def test_the_drum_taps_a_creature_and_itself(self):
        game, a = table_for("Red Creature")
        creature = Permanent(RED_CREATURE, sick=True)
        drum = Permanent(DRUM)
        a.battlefield = [drum, creature]
        use(game, a, "Springleaf Drum")
        self.assertEqual((drum.tapped, creature.tapped, len(a.mana_pool)), (True, True, 1))

    def test_the_drum_needs_an_untapped_creature(self):
        game, a = table_for()
        a.battlefield = [Permanent(DRUM), Permanent(RED_CREATURE, tapped=True)]
        self.assertEqual(activate(game, a, "Springleaf Drum"), [])

    def test_the_relic_taps_only_a_legendary_creature(self):
        game, a = table_for("Green Legend")
        legend, other = Permanent(GREEN_LEGEND), Permanent(RED_CREATURE)
        a.battlefield = [Permanent(RELIC), legend, other]
        use(game, a, "Relic of Legends")
        self.assertEqual((legend.tapped, other.tapped, len(a.mana_pool)), (True, False, 1))

    def test_the_relic_without_a_legendary_creature_cannot_use_that_ability(self):
        game, a = table_for()
        a.battlefield = [Permanent(RELIC), Permanent(RED_CREATURE)]
        self.assertEqual(activate(game, a, "Relic of Legends"), [])
        self.assertTrue(payable(game, a, "{R}"))  # (it still taps for mana itself)

    def test_lions_eye_diamond_discards_the_hand_for_three_mana(self):
        game, a = table_for()
        a.battlefield = [Permanent(LED)]
        a.hand = [RED_CREATURE, WHITE_BEAR]
        use(game, a, "Lion's Eye Diamond")
        self.assertEqual((a.battlefield, a.hand, sorted(c.name for c in a.graveyard), len(a.mana_pool)),
                         ([], [], ["Lion's Eye Diamond", "Red Creature", "White Bear"], 3))

    def test_the_cards_are_fully_playable(self):
        self.assertEqual([unsupported_lines(c) for c in (ALTAR, DRUM, RELIC, LED)], [[]] * 4)


class OtherManaTests(unittest.TestCase):
    def test_relic_of_sauron_makes_two_mana_of_its_colors(self):
        game, a = table_for()
        a.battlefield = [Permanent(SAURON)]
        self.assertTrue(payable(game, a, "{U}{R}"))
        a.battlefield[0].tapped = False
        self.assertTrue(payable(game, a, "{B}{B}"))
        a.battlefield[0].tapped = False
        self.assertFalse(payable(game, a, "{G}"))
        self.assertFalse(payable(game, a, "{W}{1}"))

    def test_relic_of_sauron_makes_exactly_two(self):
        game, a = table_for()
        a.battlefield = [Permanent(SAURON)]
        self.assertFalse(payable(game, a, "{U}{R}{B}"))

    def test_nyx_lotus_makes_mana_equal_to_devotion(self):
        game, a = table_for("Black")
        a.battlefield = [Permanent(LOTUS), Permanent(BLACK_PIPS)]
        use(game, a, "Nyx Lotus")
        self.assertEqual(sorted(len(u) for u in a.mana_pool), [1, 1, 1])
        self.assertTrue(all(u == frozenset("B") for u in a.mana_pool))

    def test_nyx_lotus_counts_only_the_chosen_color(self):
        game, a = table_for("White")
        a.battlefield = [Permanent(LOTUS), Permanent(BLACK_PIPS), Permanent(WHITE_BEAR)]
        use(game, a, "Nyx Lotus")
        self.assertEqual(a.mana_pool, [frozenset("W")])

    def test_the_great_henge_costs_less_by_the_greatest_power(self):
        game, a = table_for()
        a.battlefield = [Permanent(real("Big", "{4}", "Creature \u2014 Giant", "", "5", "5")), Permanent(BEAR)]
        self.assertEqual(game.cost_reduction(a, HENGE), 5)
        a.battlefield = []
        self.assertEqual(game.cost_reduction(a, HENGE), 0)

    def test_the_great_henge_grows_and_draws_for_a_nontoken_creature(self):
        game, a = table_for()
        a.library = [FOREST] * 3
        a.battlefield = [Permanent(HENGE)]
        entering = Permanent(BEAR)
        game._enter(a, entering)
        run_stack(game)
        self.assertEqual((entering.counters.get("+1/+1"), len(a.hand)), (1, 1))

    def test_the_great_henge_ignores_tokens_and_opponents_creatures(self):
        game, a = table_for()
        a.library = [FOREST] * 3
        a.battlefield = [Permanent(HENGE)]
        token = Permanent(Card(name="Spirit", type_line="Token Creature \u2014 Spirit", power="1", toughness="1"))
        game._enter(a, token)
        game._enter(game.seats[1], Permanent(BEAR))
        run_stack(game)
        self.assertEqual((token.counters, a.hand), ({}, []))

    def test_the_cards_are_fully_playable(self):
        self.assertEqual([unsupported_lines(c) for c in (SAURON, LOTUS, HENGE)], [[], [], []])


if __name__ == "__main__":
    unittest.main()
