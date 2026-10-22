"""Activating abilities as though creatures had haste (Sisay's and Kinnan's combos): "You may activate abilities of creatures you control
as though those creatures had haste." (Tyvar, Jubilant Brawler, Thousand-Year Elixir, Shang-Chi, CR 302.6) and Tyvar's "-2: Mill three
cards, then you may return a creature card with mana value 2 or less from your graveyard to the battlefield." Each card from its real
Oracle text; the creatures are real mana and damage creatures or probes."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, activate, lands, names, pick, real, run_stack, table3

TYVAR = real("Tyvar, Jubilant Brawler", "{1}{B}{G}", "Legendary Planeswalker — Tyvar",
             "You may activate abilities of creatures you control as though those creatures had haste.\n+1: Untap up to one target creature."
             "\n−2: Mill three cards, then you may return a creature card with mana value 2 or less from your graveyard to the battlefield.",
             colors=("B", "G"))
ELIXIR = real("Thousand-Year Elixir", "{3}", "Artifact",
              "You may activate abilities of creatures you control as though those creatures had haste.\n{1}, {T}: Untap target creature.")
ELVES = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))
PYROMANCER = real("Prodigal Pyromancer", "{2}{R}", "Creature — Human Wizard", "{T}: This creature deals 1 damage to any target.", "1", "1",
                  colors=("R",))
TWO_DROP = real("Two Drop", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
THREE_DROP = real("Three Drop", "{2}{G}", "Creature — Bear", "", "3", "3", colors=("G",))
SPELL = real("Probe Spell", "{G}", "Sorcery", "")


def seat_with(*permanents):
    game, _ = table3(pick("Two Drop"))
    a = game.seats[0]
    a.battlefield = list(permanents)
    return game, a


def sick(card):
    return Permanent(card, sick=True)


def payable(game, seat):
    return game._payment(seat, SPELL) is not None


def offered(game, seat, fragment):
    return [a for a in game.legal_actions(seat) if fragment in a]


class ParseTests(unittest.TestCase):
    def test_every_line_is_read(self):
        for card in (TYVAR, ELIXIR):
            self.assertEqual(unsupported_lines(card), [], card.name)


class HasteForAbilitiesTests(unittest.TestCase):
    def test_a_summoning_sick_mana_creature_taps_for_mana_with_tyvar_or_the_elixir(self):
        for helper in (Permanent(TYVAR, loyalty=3), Permanent(ELIXIR)):
            game, a = seat_with(sick(ELVES), helper)
            self.assertTrue(payable(game, a), helper.card.name)

    def test_without_it_a_summoning_sick_mana_creature_cannot(self):
        game, a = seat_with(sick(ELVES))
        self.assertFalse(payable(game, a))
        a.battlefield[0].sick = False
        self.assertTrue(payable(game, a))

    def test_a_summoning_sick_creature_gets_its_tap_ability_offered(self):
        game, a = seat_with(sick(PYROMANCER))
        self.assertEqual(offered(game, a, "deals 1 damage"), [])
        a.battlefield.append(Permanent(ELIXIR))
        self.assertEqual(len(offered(game, a, "deals 1 damage")), 1)

    def test_only_its_controllers_creatures_benefit(self):
        game, a = seat_with(sick(ELVES))
        game.seats[1].battlefield = [Permanent(TYVAR, loyalty=3)]
        self.assertFalse(payable(game, a))

    def test_it_does_not_give_haste_for_attacking(self):
        game, a = seat_with(sick(ELVES), Permanent(ELIXIR))
        self.assertFalse(game.combat._can_attack(a.battlefield[0]))

    def test_it_stops_when_the_card_leaves(self):
        game, a = seat_with(sick(ELVES), Permanent(ELIXIR))
        self.assertTrue(payable(game, a))
        a.battlefield.pop()
        self.assertFalse(payable(game, a))

    def test_a_filter_ability_of_a_sick_creature_works_too(self):
        selvala = real("Selvala, Heart of the Wilds", "{1}{G}{G}", "Legendary Creature — Elf Scout",
                       "{G}, {T}: Add X mana in any combination of colors, where X is the greatest power among creatures you control.",
                       "2", "3", colors=("G",))
        game, a = seat_with(sick(selvala), *lands(0), Permanent(FOREST))
        cost_two = real("Two Mana", "{W}{U}", "Sorcery", "")
        self.assertIsNone(game._payment(a, cost_two))
        a.battlefield.append(Permanent(ELIXIR))
        self.assertIsNotNone(game._payment(a, cost_two))


class TyvarAbilityTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3(pick("Two Drop"))
        self.a = self.game.seats[0]
        self.tyvar = Permanent(TYVAR, loyalty=3)
        self.a.battlefield = [self.tyvar]

    def test_plus_one_untaps_a_creature(self):
        elves = Permanent(ELVES)
        elves.tapped = True
        self.a.battlefield.append(elves)
        activate(self.game, self.a, "Untap up to one target creature")
        self.assertFalse(elves.tapped)
        self.assertEqual(self.tyvar.loyalty, 4)

    def test_minus_two_mills_three_and_returns_the_chosen_cheap_creature(self):
        self.a.library = [TWO_DROP, THREE_DROP, FOREST, FOREST, FOREST]
        self.a.graveyard = []
        activate(self.game, self.a, "Mill three cards")
        self.assertEqual(names(self.a), ["Two Drop", "Tyvar, Jubilant Brawler"])
        self.assertEqual(sorted(c.name for c in self.a.graveyard), ["Forest", "Three Drop"])
        self.assertEqual(self.tyvar.loyalty, 1)

    def test_only_mana_value_two_or_less_is_offered_and_it_may_be_declined(self):
        seen = []

        def decline(prompt, options):
            seen.append(list(options))
            return len(options) - 1  # the last option: take none
        game, _ = table3(decline)
        a = game.seats[0]
        a.battlefield = [Permanent(TYVAR, loyalty=3)]
        a.library = [TWO_DROP, THREE_DROP, FOREST, FOREST]
        a.graveyard = [real("Old Cheap", "{G}", "Creature — Elf", "", "1", "1")]
        activate(game, a, "Mill three cards")
        self.assertEqual(seen[-1][:-1].count("Three Drop"), 0)
        self.assertEqual(sorted(seen[-1][:-1]), ["Old Cheap", "Two Drop"])
        self.assertEqual(names(a), ["Tyvar, Jubilant Brawler"])  # declined

    def test_with_no_creature_that_cheap_nothing_comes_back(self):
        self.a.library = [THREE_DROP, FOREST, FOREST]
        activate(self.game, self.a, "Mill three cards")
        self.assertEqual(names(self.a), ["Tyvar, Jubilant Brawler"])
        self.assertEqual(len(self.a.graveyard), 3)


if __name__ == "__main__":
    unittest.main()
