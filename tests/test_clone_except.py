import dataclasses
import unittest

from infernal_machine.game import CAST, CLONE_PROMPT, NOT_A_COPY, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, PASS, lands, real, run_stack, table

SPARK_DOUBLE = real("Spark Double", "{3}{U}", "Creature — Illusion",
                    "You may have this creature enter as a copy of a creature or planeswalker you control, except it enters with an "
                    "additional +1/+1 counter on it if it's a creature, it enters with an additional loyalty counter on it if it's a "
                    "planeswalker, and it isn't legendary.", "0", "0")
VESUVA = real("Vesuva", "", "Land", "You may have this land enter tapped as a copy of any land on the battlefield.")
GLASSPOOL = real("Glasspool Mimic", "{2}{U}", "Creature — Shapeshifter Rogue",
                 "You may have this creature enter as a copy of a creature you control, except it's a Shapeshifter Rogue in addition to its other types.",
                 "0", "0")
IMPOSTOR = real("Malleable Impostor", "{3}{U}", "Creature — Faerie Shapeshifter",
                "Flash\nFlying\nYou may have this creature enter as a copy of a creature an opponent controls, except it's a Faerie Shapeshifter in "
                "addition to its other types and it has flying.", "0", "0")
FROSTKITE = real("Deceptive Frostkite", "{U}{U}", "Creature — Dragon",
                 "Flying\nYou may have this creature enter as a copy of a creature you control with power 4 or greater, except it's a Dragon in "
                 "addition to its other types and it has flying.", "1", "1")
IMAGE = real("Phantasmal Image", "{1}{U}", "Creature — Illusion",
             'You may have this creature enter as a copy of any creature on the battlefield, except it\'s an Illusion in addition to its other '
             'types and it has "When this creature becomes the target of a spell or ability, sacrifice it."', "0", "0")
JACE = real("Walker Jace", "{3}{U}", "Legendary Planeswalker — Jace", "+1: Draw a card.")
JACE = dataclasses.replace(JACE, loyalty="3")
KING = dataclasses.replace(BEAR, name="Old King", type_line="Legendary Creature — Human Noble", power="5", toughness="5")
FOREST_COPYABLE = real("Test Cave", "", "Land", "{T}: Add {G}.")


def choosing(wanted):
    """Policy: cast the card, copy the permanent whose label starts with `wanted` (or nothing, for None), else pass."""
    def policy(prompt, options):
        if CLONE_PROMPT.matches(prompt):
            if wanted is None:
                return options.index(NOT_A_COPY)
            return next(i for i, option in enumerate(options) if option.startswith(wanted))
        return next((i for i, option in enumerate(options) if option.startswith(CAST)), options.index(PASS) if PASS in options else 0)
    return policy


def enter(card, mine=(), theirs=(), wanted=None):
    game, _, _ = table(choosing(wanted))
    a, b = game.seats
    a.hand = [card]
    a.battlefield = lands(5) + [Permanent(c) for c in mine]
    b.battlefield = [Permanent(c) for c in theirs]
    game._priority_round(a)
    run_stack(game)
    return game, a, b


def copy_of(seat, name):
    return next(p for p in seat.battlefield if p.card.name == name and p.real_card is not None)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (SPARK_DOUBLE, VESUVA, GLASSPOOL, IMPOSTOR, FROSTKITE, IMAGE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_an_except_clause_the_engine_does_not_apply_leaves_the_line_unsupported(self):
        odd = real("Odd Twin", "{2}{U}", "Creature — Shapeshifter",
                   "You may have this creature enter as a copy of any creature on the battlefield, except it's green.", "0", "0")
        self.assertNotEqual(unsupported_lines(odd), [])

    def test_a_quoted_ability_the_engine_does_not_understand_leaves_the_line_unsupported(self):
        evil = real("Evil Twin", "{2}{U}{B}", "Creature — Shapeshifter",
                    'You may have this creature enter as a copy of any creature on the battlefield, except it has "{U}{B}, {T}: Destroy target '
                    'creature with the same name as this creature."', "0", "0")
        self.assertNotEqual(unsupported_lines(evil), [])


class SparkDoubleTests(unittest.TestCase):
    def test_a_creature_copy_has_an_extra_counter_and_is_not_legendary(self):
        game, a, _ = enter(SPARK_DOUBLE, mine=[KING], wanted="Old King")
        copy = copy_of(a, "Old King")
        self.assertEqual(copy.counters.get("+1/+1"), 1)
        self.assertEqual((game.power(copy), game.toughness(copy)), (6, 6))
        self.assertNotIn("Legendary", copy.card.type_line)
        self.assertIn("Legendary", next(p for p in a.battlefield if p.card.name == "Old King" and p.real_card is None).card.type_line)

    def test_a_planeswalker_copy_has_an_extra_loyalty_counter(self):
        game, a, _ = enter(SPARK_DOUBLE, mine=[JACE], wanted="Walker Jace")
        copy = copy_of(a, "Walker Jace")
        self.assertEqual(copy.loyalty, 4)
        self.assertEqual(copy.counters.get("+1/+1", 0), 0)
        self.assertNotIn("Legendary", copy.card.type_line)

    def test_it_only_copies_what_you_control(self):
        game, a, _ = enter(SPARK_DOUBLE, theirs=[OGRE], wanted="Ogre")
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], [], "no copy: a 0/0 that died")


class SourceTests(unittest.TestCase):
    def test_only_an_opponents_creature_may_be_copied(self):
        game, a, _ = enter(IMPOSTOR, mine=[BEAR], theirs=[OGRE], wanted="Ogre")
        copy = copy_of(a, "Ogre")
        self.assertEqual(copy.card.type_line, "Creature — Test Faerie Shapeshifter")
        self.assertIn("Flying", copy.card.oracle_text)

    def test_your_own_creature_is_no_choice_for_an_opponents_copier(self):
        game, a, _ = enter(IMPOSTOR, mine=[BEAR], wanted="Bear")
        self.assertEqual([p for p in a.battlefield if p.real_card is not None], [])

    def test_only_your_creature_may_be_copied(self):
        game, a, _ = enter(GLASSPOOL, mine=[BEAR], theirs=[OGRE], wanted="Bear")
        self.assertEqual(copy_of(a, "Bear").card.type_line, "Creature — Test Shapeshifter Rogue")
        game, a, _ = enter(GLASSPOOL, theirs=[OGRE], wanted="Ogre")
        self.assertEqual([p for p in a.battlefield if p.real_card is not None], [])

    def test_the_copied_creature_needs_the_power(self):
        small, big = BEAR, dataclasses.replace(OGRE, name="Giant", power="4", toughness="4")
        game, a, _ = enter(FROSTKITE, mine=[small, big], wanted="Giant")
        self.assertEqual(copy_of(a, "Giant").card.type_line, "Creature — Test Dragon")
        game, a, _ = enter(FROSTKITE, mine=[small], wanted="Bear")
        self.assertEqual([p for p in a.battlefield if p.real_card is not None], [], "power 2 is too small")

    def test_a_land_copy_enters_tapped(self):
        game, _, _ = table(choosing("Test Cave"))
        seat = game.seats[0]
        seat.battlefield = [Permanent(FOREST_COPYABLE)]
        game._enter(seat, Permanent(VESUVA))
        copy = next(p for p in seat.battlefield if p.real_card is not None)
        self.assertEqual((copy.card.name, copy.tapped), ("Test Cave", True))

    def test_choosing_not_to_copy_keeps_the_card_and_it_enters_untapped(self):
        game, _, _ = table(choosing(None))
        seat = game.seats[0]
        seat.battlefield = [Permanent(FOREST_COPYABLE)]
        vesuva = Permanent(VESUVA)
        game._enter(seat, vesuva)
        self.assertEqual((vesuva.card.name, vesuva.tapped, vesuva.real_card), ("Vesuva", False, None))


class QuotedAbilityTests(unittest.TestCase):
    def test_the_copy_is_sacrificed_when_it_becomes_a_target(self):
        game, a, _ = enter(IMAGE, theirs=[OGRE], wanted="Ogre")
        copy = copy_of(a, "Ogre")
        self.assertIn("sacrifice it", copy.card.oracle_text)
        game.trigger("targeted", copy, a)
        run_stack(game)
        self.assertNotIn(copy, a.battlefield)


if __name__ == "__main__":
    unittest.main()
