"""Lands that make mana of the color chosen as they enter (issue #91): Room of Refuge, the Thriving lands and the Gates,
each played from its real Oracle text. The mana is only the chosen color (and, for Thriving lands and Gates, their own
color), not the five colors Scryfall lists as the land's possible mana."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, CHOOSE_COLOR_PROMPT, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, pick, real, run_stack, Table, table3

ANY = ("B", "G", "R", "U", "W")


def land(name, text, type_line="Land"):
    """A land as Scryfall gives it: its Oracle text, and every color it could make."""
    return Card(name=name, type_line=type_line, oracle_text=text, produced_mana=ANY)


ROOM = land("Room of Refuge", "This land enters tapped. As it enters, choose a color.\n{T}: Add one mana of the chosen color.")
VILLAGE = land("Crossroads Village", "This land enters tapped. As it enters, choose a color.\n{T}: Add one mana of the chosen color.", "Land — Town")
MESA = land("Mirage Mesa", "This land enters tapped. As it enters, choose a color.\n{T}: Add one mana of the chosen color.", "Land — Desert")
HAVEN = land("Uncharted Haven", "This land enters tapped. As it enters, choose a color.\n{T}: Add one mana of the chosen color.")
MARKET = land("Night Market", "This land enters tapped. As it enters, choose a color.\n{T}: Add one mana of the chosen color.\nCycling {3} ({3}, Discard this card: Draw a card.)")
LAIR = land("Valgavoth's Lair", "Hexproof\nThis land enters tapped. As it enters, choose a color.\n{T}: Add one mana of the chosen color.", "Enchantment Land")
INN = land("Edgewall Inn", "This land enters tapped.\nAs this land enters, choose a color.\n{T}: Add one mana of the chosen color.\n"
                          "{3}, {T}, Sacrifice this land: Return target card that has an Adventure from your graveyard to your hand.")
BLUFF = land("Thriving Bluff", "This land enters tapped. As it enters, choose a color other than red.\n{T}: Add {R} or one mana of the chosen color.")
MOOR = land("Thriving Moor", "This land enters tapped. As it enters, choose a color other than black.\n{T}: Add {B} or one mana of the chosen color.")
CITADEL_GATE = land("Citadel Gate", "This land enters tapped.\nAs this land enters, choose a color other than white.\n{T}: Add {W} or one mana of the chosen color.", "Land — Gate")
CLIFFGATE = land("Cliffgate", "This land enters tapped.\nAs this land enters, choose a color other than red.\n{T}: Add {R} or one mana of the chosen color.", "Land — Gate")

SPELLS = {c: real(f"{c} Draw", f"{{{c}}}", "Instant", "Draw a card.", colors=(c,)) for c in "WUBRG"}
PLAIN = [ROOM, VILLAGE, MESA, HAVEN, MARKET, LAIR]
OWN_COLOR = [(BLUFF, "R"), (MOOR, "B"), (CITADEL_GATE, "W"), (CLIFFGATE, "R")]
NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}


def chosen(card, color):
    permanent = Permanent(card)
    permanent.chosen_color = color
    return permanent


def colors_it_pays(permanent):
    """The colors of spell the land can pay for."""
    found = ""
    for color, spell in SPELLS.items():
        t = Table(spell, n=0, mine=[permanent])
        if any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a)):
            found += color
    return "".join(sorted(found))


def enter(card, answer, mine=()):
    """Seat 0 plays `card`; returns (permanent, the options of the color choice)."""
    seen = []

    def policy(prompt, options):
        if CHOOSE_COLOR_PROMPT.matches(prompt):
            seen.append(options)
        return pick(answer)(prompt, options)

    game, _ = table3(policy)
    a = game.seats[0]
    a.battlefield = list(mine)
    a.hand = [card]
    game._perform(a, PLAY_LAND + card.name)
    run_stack(game)
    permanent = next(p for p in a.battlefield if p.card.name == card.name)
    return permanent, seen


class ParseTests(unittest.TestCase):
    def test_the_plain_lands_are_fully_understood(self):
        for card in PLAIN + [c for c, _ in OWN_COLOR]:
            with self.subTest(card=card.name):
                self.assertEqual(unsupported_lines(card), [])

    def test_a_land_with_another_ability_reports_only_that_ability(self):
        self.assertEqual(unsupported_lines(INN), ["{3}, {T}, Sacrifice this land: Return target card that has an Adventure from your graveyard to your hand."])


class ChosenColorTests(unittest.TestCase):
    def test_it_makes_only_the_color_chosen(self):
        for card in PLAIN:
            for color in "WUBRG":
                with self.subTest(card=card.name, color=color):
                    self.assertEqual(colors_it_pays(chosen(card, color)), color)

    def test_each_land_keeps_its_own_choice(self):
        red, blue = chosen(ROOM, "R"), chosen(VILLAGE, "U")
        self.assertEqual((colors_it_pays(red), colors_it_pays(blue)), ("R", "U"))

    def test_the_choice_is_asked_as_it_enters_and_the_land_comes_in_tapped(self):
        permanent, seen = enter(ROOM, "Blue")
        self.assertEqual(seen, [["White", "Blue", "Black", "Red", "Green"]])
        self.assertEqual((permanent.chosen_color, permanent.tapped), ("U", True))
        permanent.tapped = False
        self.assertEqual(colors_it_pays(permanent), "U")

    def test_without_a_choice_it_makes_no_mana(self):
        self.assertEqual(colors_it_pays(Permanent(ROOM)), "")

    def test_another_land_is_not_affected_by_the_choice(self):
        t = Table(SPELLS["G"], n=0, mine=[chosen(ROOM, "R"), Permanent(FOREST)])
        self.assertTrue(any(a.startswith(CAST) for a in t.game.legal_actions(t.a)), "the Forest still makes green")


class OwnColorAndChosenColorTests(unittest.TestCase):
    def test_it_makes_its_own_color_or_the_chosen_one(self):
        for card, own in OWN_COLOR:
            for color in "WUBRG":
                if color == own:
                    continue
                with self.subTest(card=card.name, color=color):
                    self.assertEqual(colors_it_pays(chosen(card, color)), "".join(sorted(own + color)))

    def test_nothing_else_is_made(self):
        paid = colors_it_pays(chosen(BLUFF, "U"))
        for color in "WBG":
            self.assertNotIn(color, paid)

    def test_without_a_choice_it_makes_only_its_own_color(self):
        self.assertEqual(colors_it_pays(Permanent(BLUFF)), "R")

    def test_the_choice_leaves_out_its_own_color(self):
        for card, own in OWN_COLOR:
            with self.subTest(card=card.name):
                permanent, seen = enter(card, NAMES["G" if own != "G" else "W"])
                self.assertEqual(len(seen), 1)
                self.assertNotIn(NAMES[own], seen[0])
                self.assertEqual(len(seen[0]), 4)
                self.assertTrue(permanent.tapped)

    def test_a_chosen_color_through_the_whole_flow(self):
        permanent, _ = enter(BLUFF, "Green")
        permanent.tapped = False
        self.assertEqual(colors_it_pays(permanent), "GR")


if __name__ == "__main__":
    unittest.main()
