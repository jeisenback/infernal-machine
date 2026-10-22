"""Mana that changes when a permanent is tapped for it (#214, second slice): "Whenever you tap a nonland permanent for mana, add one mana
of any type that permanent produced." (Kinnan, CR 106.12a, a triggered mana ability adding its own mana) and "If you tap a permanent
for mana, it produces three times as much of that mana instead." (Nyxbloom Ancient, CR 106.12b, a replacement), with the rest of the
family (Mana Reflection, Mana Flare, Crypt Ghast). Each card from its real Oracle text; the spells are probes of what can be paid."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, SOL_RING, SWAMP, activate, names, real, table3

KINNAN = real("Kinnan, Bonder Prodigy", "{G}{U}", "Legendary Creature — Human Druid",
              "Whenever you tap a nonland permanent for mana, add one mana of any type that permanent produced.\n{5}{G}{U}: Look at the top "
              "five cards of your library. You may put a non-Human creature card from among them onto the battlefield. Put the rest on "
              "the bottom of your library in a random order.", "2", "2", colors=("G", "U"))
NYXBLOOM = real("Nyxbloom Ancient", "{4}{G}{G}{G}", "Enchantment Creature — Elemental",
                "Trample\nIf you tap a permanent for mana, it produces three times as much of that mana instead.", "5", "5", colors=("G",))
REFLECTION = real("Mana Reflection", "{4}{G}{G}", "Enchantment",
                  "If you tap a permanent for mana, it produces twice as much of that mana instead.", colors=("G",))
FLARE = real("Mana Flare", "{2}{R}", "Enchantment",
             "Whenever a player taps a land for mana, that player adds one mana of any type that land produced.", colors=("R",))
GHAST = real("Crypt Ghast", "{3}{B}", "Creature — Spirit",
             "Extort (Whenever you cast a spell, you may pay {W/B}. If you do, each opponent loses 1 life and you gain that much life.)\n"
             "Whenever you tap a Swamp for mana, add an additional {B}.", "2", "2", colors=("B",))
OVERABUNDANCE = real("Overabundance", "{1}{R}{G}", "Enchantment",
                     "Whenever a player taps a land for mana, that player adds one mana of any type that land produced, and this "
                     "enchantment deals 1 damage to the player.", colors=("G", "R"))
SIGNET = real("Dimir Signet", "{2}", "Artifact", "{1}, {T}: Add {U}{B}.")
ELVES = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))

HUMAN = real("Human Probe", "{1}", "Creature — Human", "", "1", "1")
BEAST = real("Beast Probe", "{1}", "Creature — Beast", "", "3", "3")


def seat_with(*cards):
    game, _ = table3(None)
    a = game.seats[0]
    a.battlefield = [Permanent(c) for c in cards]
    return game, a


def made(game, seat):
    """The mana `seat` can make now, one entry per mana, as sorted strings of the types each may be."""
    return sorted("".join(sorted(s.types)) for s in game._mana_sources(seat))


def payable(game, seat, cost):
    return game._payment(seat, Card(name="Probe", mana_cost=cost, type_line="Sorcery")) is not None


class ParseTests(unittest.TestCase):
    def test_the_family_is_read(self):
        for card in (KINNAN, NYXBLOOM, REFLECTION, FLARE, GHAST):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_line_with_more_after_it_is_not(self):
        self.assertEqual(len(unsupported_lines(OVERABUNDANCE)), 1)


class KinnanTests(unittest.TestCase):
    def test_a_nonland_permanent_makes_one_more_of_a_type_it_made(self):
        game, a = seat_with(KINNAN, SOL_RING)
        self.assertEqual(made(game, a), ["C", "C", "C"])
        self.assertTrue(payable(game, a, "{3}"))

    def test_without_kinnan_sol_ring_makes_two(self):
        game, a = seat_with(SOL_RING)
        self.assertFalse(payable(game, a, "{3}"))

    def test_a_land_is_not_a_nonland_permanent(self):
        game, a = seat_with(KINNAN, FOREST)
        self.assertEqual(made(game, a), ["G"])

    def test_once_per_tap_however_much_was_made_and_a_summoning_sick_elf_makes_nothing(self):
        game, a = seat_with(KINNAN, ELVES)
        self.assertEqual(made(game, a), ["G", "G"])
        a.battlefield[1].sick = True
        self.assertEqual(made(game, a), [])

    def test_a_signet_tapped_for_mana_counts_too(self):
        game, a = seat_with(KINNAN, SIGNET, FOREST)
        self.assertTrue(payable(game, a, "{U}{U}{B}"))  # the Forest pays the Signet's {1}; Kinnan adds a {U} or {B}
        game, a = seat_with(SIGNET, FOREST)
        self.assertFalse(payable(game, a, "{U}{U}{B}"))

    def test_an_opponents_kinnan_does_nothing_for_you(self):
        game, a = seat_with(SOL_RING)
        game.seats[1].battlefield = [Permanent(KINNAN)]
        self.assertEqual(made(game, a), ["C", "C"])

    def test_the_activated_ability_puts_a_non_human_creature_onto_the_battlefield(self):
        game, players = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Beast")), 0))
        a = game.seats[0]
        a.battlefield = [Permanent(KINNAN), *[Permanent(Card(name="City of Brass", type_line="Land", produced_mana=tuple("WUBRG")))
                                               for _ in range(7)]]
        a.library = [HUMAN, BEAST, FOREST, FOREST, FOREST, SWAMP]
        activate(game, a, "Look at the top five cards")
        self.assertIn("Beast Probe", names(a))
        self.assertNotIn("Human Probe", names(a))
        self.assertEqual(a.library[0].name, "Swamp")  # the sixth card stays on top; the rest go under it


class MultiplierTests(unittest.TestCase):
    def test_nyxbloom_triples_a_land(self):
        game, a = seat_with(NYXBLOOM, FOREST)
        self.assertEqual(made(game, a), ["G", "G", "G"])

    def test_two_nyxblooms_make_nine_and_mana_reflection_doubles(self):
        game, a = seat_with(NYXBLOOM, NYXBLOOM, FOREST)
        self.assertEqual(len(made(game, a)), 9)
        game, a = seat_with(REFLECTION, SOL_RING)
        self.assertEqual(made(game, a), ["C"] * 4)

    def test_kinnans_mana_is_its_own_and_is_not_tripled(self):
        game, a = seat_with(NYXBLOOM, KINNAN, SOL_RING)
        self.assertEqual(made(game, a), ["C"] * 7)  # Sol Ring's two, tripled, and Kinnan's one

    def test_an_opponents_nyxbloom_does_not_triple_your_land(self):
        game, a = seat_with(FOREST)
        game.seats[1].battlefield = [Permanent(NYXBLOOM)]
        self.assertEqual(made(game, a), ["G"])


class LandTriggerTests(unittest.TestCase):
    def test_an_opponents_mana_flare_helps_every_player(self):
        game, a = seat_with(FOREST)
        game.seats[1].battlefield = [Permanent(FLARE)]
        self.assertEqual(made(game, a), ["G", "G"])

    def test_crypt_ghast_adds_black_to_a_swamp_only(self):
        game, a = seat_with(GHAST, SWAMP, FOREST)
        self.assertEqual(made(game, a), ["B", "B", "G"])

    def test_a_permanent_that_lost_its_abilities_adds_nothing(self):
        game, a = seat_with(GHAST, SWAMP)
        game.loses_abilities = lambda permanent: permanent.card is GHAST
        self.assertEqual(made(game, a), ["B"])


if __name__ == "__main__":
    unittest.main()
