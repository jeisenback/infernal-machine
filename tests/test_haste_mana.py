"""A summoning-sick creature taps for mana when it has haste (CR 302.6), from its own text or from another permanent, as well as under
Tyvar and Thousand-Year Elixir (tests/test_haste_abilities.py). The payer once looked only at the "as though haste" rule, while the
activation check (`_can_activate`) honored the creature's haste. Each card from its real Oracle text, and probes."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import FOREST, pick, real, table3

SPELL = real("Probe Spell", "{G}", "Sorcery", "")
ELVES = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))
HASTY_ELVES = real("Hasty Elves", "{G}", "Creature — Elf Druid", "Haste\n{T}: Add {G}.", "1", "1", colors=("G",))
ARCHDRUID = real("Elvish Archdruid", "{1}{G}{G}", "Creature — Elf Druid",
                 "Other Elf creatures you control get +1/+1.\n{T}: Add {G} for each Elf you control.", "2", "2", colors=("G",))
HASTY_ARCHDRUID = real("Hasty Archdruid", "{1}{G}{G}", "Creature — Elf Druid", "Haste\n{T}: Add {G} for each Elf you control.", "2", "2",
                       colors=("G",))
FERVOR = real("Fervor", "{2}{R}", "Enchantment", "Creatures you control have haste.", colors=("R",))
FILTER = real("Filter Beast", "{2}", "Creature \u2014 Beast", "{1}, {T}: Add {G}{G}.", "1", "1", colors=("G",))
HASTY_FILTER = real("Hasty Filter Beast", "{2}", "Creature \u2014 Beast", "Haste\n{1}, {T}: Add {G}{G}.", "1", "1", colors=("G",))
BIG_SPELL = real("Probe Spell Two", "{G}{G}", "Sorcery", "")


def seat_with(*permanents):
    game, _ = table3(pick("Probe Spell"))
    a = game.seats[0]
    a.battlefield = list(permanents)
    return game, a


def sick(card):
    return Permanent(card, sick=True)


def payable(game, seat):
    return game._payment(seat, SPELL) is not None


class HasteMakesManaTests(unittest.TestCase):
    def test_a_creature_with_haste_taps_for_mana_the_turn_it_came_in(self):
        game, a = seat_with(sick(HASTY_ELVES))
        self.assertTrue(payable(game, a))

    def test_the_same_creature_without_haste_cannot(self):
        game, a = seat_with(sick(ELVES))
        self.assertFalse(payable(game, a))

    def test_haste_from_another_permanent_counts(self):
        game, a = seat_with(sick(ELVES), Permanent(FERVOR))
        self.assertTrue(payable(game, a))

    def test_an_opponents_haste_grant_does_not(self):
        game, a = seat_with(sick(ELVES))
        game.seats[1].battlefield = [Permanent(FERVOR)]
        self.assertFalse(payable(game, a))

    def test_mana_by_count_follows_the_same_rule(self):
        game, a = seat_with(sick(HASTY_ARCHDRUID))
        self.assertTrue(payable(game, a))
        game, a = seat_with(sick(ARCHDRUID))
        self.assertFalse(payable(game, a))

    def test_a_creature_that_filters_mana_follows_the_same_rule(self):
        for card, expected in ((HASTY_FILTER, True), (FILTER, False)):
            game, a = seat_with(sick(card), Permanent(FOREST))
            self.assertEqual(game._payment(a, BIG_SPELL) is not None, expected, card.name)

    def test_a_sick_artifact_is_not_held_back(self):
        game, a = seat_with(sick(real("Sol Probe", "{1}", "Artifact", "{T}: Add {G}.")))
        self.assertTrue(payable(game, a))


if __name__ == "__main__":
    unittest.main()
