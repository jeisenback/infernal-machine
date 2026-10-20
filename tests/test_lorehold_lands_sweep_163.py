"""The thirteen Lorehold lands of the precon decks (issue #163), each played from its real Oracle text: how it comes in
(tapped or untapped, with a case on each side of the line), the mana it makes really pays for a spell, and the extra
abilities do what they say."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, CYCLE, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, lands, pick, PLAINS, real, run_stack, Table, table3

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
RED = real("Red Draw", "{R}", "Instant", "Draw a card.", colors=("R",))
WHITE = real("White Draw", "{W}", "Instant", "Draw a card.", colors=("W",))
RED_RED = real("Double Red", "{R}{R}", "Instant", "Draw a card.", colors=("R",))
WHITE_WHITE = real("Double White", "{W}{W}", "Instant", "Draw a card.", colors=("W",))
RED_WHITE = real("Red White", "{R}{W}", "Instant", "Draw a card.", colors=("R", "W"))
GREEN = real("Green Draw", "{G}", "Instant", "Draw a card.", colors=("G",))
ONE = real("One Draw", "{1}", "Instant", "Draw a card.")

def land(name, type_line, text, mana):
    """A land as Scryfall gives it: the Oracle text and the mana it can produce."""
    return Card(name=name, type_line=type_line, oracle_text=text, produced_mana=tuple(mana))


STEPPE = land("Turbulent Steppe", "Land — Mountain Plains", "({T}: Add {R} or {W}.)\nThis land enters tapped unless your opponents control eight or more lands.", "RW")
FORGE = land("Battlefield Forge", "Land", "{T}: Add {C}.\n{T}: Add {R} or {W}. This land deals 1 damage to you.", "CRW")
CLIFFTOP = land("Clifftop Retreat", "Land", "This land enters tapped unless you control a Mountain or a Plains.\n{T}: Add {R} or {W}.", "RW")
EMERIA = land("Emeria, the Sky Ruin", "Land", "This land enters tapped.\nAt the beginning of your upkeep, if you control seven or more Plains, you may return target creature card from your graveyard to the battlefield.\n{T}: Add {W}.", "W")
MASSIF = land("Glittering Massif", "Land — Mountain Plains", "({T}: Add {R} or {W}.)\nThis land enters tapped.\nCycling {2} ({2}, Discard this card: Draw a card.)", "RW")
SUMMIT = land("Radiant Summit", "Land — Mountain Plains", "({T}: Add {R} or {W}.)\nThis land enters tapped unless you control two or more basic lands.", "RW")
PRAIRIE = land("Rugged Prairie", "Land", "{T}: Add {C}.\n{R/W}, {T}: Add {R}{R}, {R}{W}, or {W}{W}.", "CRW")
DIVIDE = land("Sunscorched Divide", "Land", "{1}, {T}: Add {R}{W}.", "RW")
TEMPLE = land("Temple of Triumph", "Land", "This land enters tapped.\nWhen this land enters, scry 1. (Look at the top card of your library. You may put that card on the bottom.)\n{T}: Add {R} or {W}.", "RW")
FIELDS = land("Fields of Strife", "Land", "This land enters tapped.\n{T}: Add {R} or {W}.\n{2}{R}{W}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)", "RW")
EXPANSE = land("Terramorphic Expanse", "Land", "{T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.", "")
CAMPUS = land("Lorehold Campus", "Land", "This land enters tapped.\n{T}: Add {R} or {W}.\n{4}, {T}: Scry 1. (Look at the top card of your library. You may put that card on the bottom.)", "RW")
PEAKS = land("Sacred Peaks", "Land — Mountain Plains", "({T}: Add {R} or {W}.)\nThis land enters tapped.", "RW")

ALL = [STEPPE, FORGE, CLIFFTOP, EMERIA, MASSIF, SUMMIT, PRAIRIE, DIVIDE, TEMPLE, FIELDS, EXPANSE, CAMPUS, PEAKS]
RED_OR_WHITE = [STEPPE, FORGE, CLIFFTOP, MASSIF, SUMMIT, TEMPLE, FIELDS, CAMPUS, PEAKS]
ALWAYS_TAPPED = [EMERIA, MASSIF, TEMPLE, FIELDS, CAMPUS, PEAKS]


def play(policy, card, mine=(), theirs=()):
    """Seat 0 plays `card` from its hand; returns (game, seat, permanent)."""
    game, _ = table3(policy)
    a = game.seats[0]
    a.battlefield = list(mine)
    game.seats[1].battlefield = list(theirs)
    a.hand = [card]
    a.library = [PLAINS, FOREST, FOREST, FOREST]
    game._perform(a, PLAY_LAND + card.name)
    run_stack(game)
    return game, a, next(p for p in a.battlefield if p.card.name == card.name)


def entered_tapped(card, mine=(), theirs=()):
    return play(pick(), card, mine, theirs)[2].tapped


def castable(spell, *permanents):
    t = Table(spell, n=0, mine=list(permanents))
    return any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a))


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


def can_activate(game, seat, fragment):
    return any(a.startswith(ACTIVATE) and fragment in a for a in game.legal_actions(seat))


class EveryLandTests(unittest.TestCase):
    def test_parse(self):
        for card in ALL:
            with self.subTest(card=card.name):
                self.assertEqual(unsupported_lines(card), [])

    def test_the_lands_that_always_enter_tapped_do(self):
        for card in ALWAYS_TAPPED:
            with self.subTest(card=card.name):
                self.assertTrue(entered_tapped(card, mine=[Permanent(PLAINS), Permanent(MOUNTAIN)]))

    def test_the_lands_that_can_come_in_untapped_do_so_on_their_stated_condition_only(self):
        for card in (FORGE, DIVIDE, PRAIRIE, EXPANSE):
            with self.subTest(card=card.name):
                self.assertFalse(entered_tapped(card))

    def test_a_land_that_makes_red_or_white_pays_for_either_but_not_for_another_color(self):
        for card in RED_OR_WHITE:
            with self.subTest(card=card.name):
                self.assertTrue(castable(RED, Permanent(card)), "red")
                self.assertTrue(castable(WHITE, Permanent(card)), "white")
                self.assertFalse(castable(GREEN, Permanent(card)), "green")
                self.assertFalse(castable(RED_WHITE, Permanent(card)), "it makes one mana")


class TurbulentSteppeTests(unittest.TestCase):
    def test_it_enters_tapped_unless_the_opponents_control_eight_or_more_lands(self):
        self.assertTrue(entered_tapped(STEPPE, theirs=lands(7)), "seven")
        self.assertFalse(entered_tapped(STEPPE, theirs=lands(8)), "eight")
        self.assertFalse(entered_tapped(STEPPE, theirs=lands(12)), "twelve")

    def test_your_own_lands_do_not_count(self):
        self.assertTrue(entered_tapped(STEPPE, mine=lands(9), theirs=lands(2)))

    def test_nonland_permanents_of_the_opponents_do_not_count(self):
        self.assertTrue(entered_tapped(STEPPE, theirs=lands(5) + [Permanent(BEAR)] * 5))

    def test_the_lands_of_the_opponents_together_count(self):
        game, _ = table3(pick())
        game.seats[1].battlefield = lands(4)
        game.seats[2].battlefield = lands(4)
        a = game.seats[0]
        a.hand = [STEPPE]
        game._perform(a, PLAY_LAND + STEPPE.name)
        self.assertFalse(a.battlefield[-1].tapped)


class BattlefieldForgeTests(unittest.TestCase):
    def pay(self, spell):
        t = Table(spell, n=0, mine=[Permanent(FORGE)])
        before = t.a.life
        t.cast()
        return before - t.a.life

    def test_colored_mana_costs_one_life(self):
        self.assertEqual(self.pay(RED), 1)
        self.assertEqual(self.pay(WHITE), 1)

    def test_colorless_mana_costs_nothing(self):
        self.assertEqual(self.pay(ONE), 0)


class ClifftopRetreatTests(unittest.TestCase):
    def test_a_mountain_or_a_plains_makes_it_untapped(self):
        for enabler in (MOUNTAIN, PLAINS, STEPPE, PEAKS):
            with self.subTest(enabler=enabler.name):
                self.assertFalse(entered_tapped(CLIFFTOP, mine=[Permanent(enabler)]))

    def test_other_lands_and_permanents_do_not(self):
        self.assertTrue(entered_tapped(CLIFFTOP))
        self.assertTrue(entered_tapped(CLIFFTOP, mine=[Permanent(FOREST), Permanent(WASTES), Permanent(BEAR)]))

    def test_an_opponents_mountain_does_not(self):
        self.assertTrue(entered_tapped(CLIFFTOP, theirs=[Permanent(MOUNTAIN), Permanent(PLAINS)]))


class RadiantSummitTests(unittest.TestCase):
    def test_two_or_more_basic_lands_make_it_untapped(self):
        self.assertFalse(entered_tapped(SUMMIT, mine=[Permanent(FOREST), Permanent(FOREST)]))
        self.assertFalse(entered_tapped(SUMMIT, mine=[Permanent(MOUNTAIN), Permanent(PLAINS), Permanent(WASTES)]))

    def test_one_basic_land_is_not_enough(self):
        self.assertTrue(entered_tapped(SUMMIT))
        self.assertTrue(entered_tapped(SUMMIT, mine=[Permanent(FOREST)]))

    def test_nonbasic_lands_do_not_count(self):
        self.assertTrue(entered_tapped(SUMMIT, mine=[Permanent(FORGE), Permanent(CLIFFTOP), Permanent(STEPPE)]))

    def test_an_opponents_basic_lands_do_not_count(self):
        self.assertTrue(entered_tapped(SUMMIT, theirs=lands(4)))


class EmeriaTests(unittest.TestCase):
    FALLEN = real("Fallen Hero", "{2}", "Creature — Human", "", "2", "2")

    def upkeep(self, plains, answers=(), seat=0, graveyard=None, extra=()):
        game, _ = table3(pick(*answers))
        a = game.seats[0]
        a.battlefield = [Permanent(EMERIA)] + [Permanent(PLAINS) for _ in range(plains)] + list(extra)
        a.graveyard = list(graveyard if graveyard is not None else [self.FALLEN])
        game.active = seat
        game.step = "upkeep"
        game._turn_based_actions(game.seats[seat])
        run_stack(game)
        return a

    def test_it_makes_white(self):
        self.assertTrue(castable(WHITE, Permanent(EMERIA)))
        self.assertFalse(castable(RED, Permanent(EMERIA)))

    def test_seven_plains_return_a_creature_card_from_the_graveyard_at_upkeep(self):
        a = self.upkeep(7, ["Yes", "Fallen Hero"])
        self.assertIn("Fallen Hero", [p.card.name for p in a.battlefield])
        self.assertEqual(a.graveyard, [])

    def test_six_plains_do_not(self):
        a = self.upkeep(6, ["Yes", "Fallen Hero"])
        self.assertNotIn("Fallen Hero", [p.card.name for p in a.battlefield])

    def test_a_land_with_the_plains_type_counts_but_Emeria_itself_does_not(self):
        a = self.upkeep(5, ["Yes", "Fallen Hero"], extra=[Permanent(STEPPE)])
        self.assertNotIn("Fallen Hero", [p.card.name for p in a.battlefield], "five Plains and a Mountain Plains is six")
        a = self.upkeep(6, ["Yes", "Fallen Hero"], extra=[Permanent(STEPPE)])
        self.assertIn("Fallen Hero", [p.card.name for p in a.battlefield], "six Plains and a Mountain Plains is seven")

    def test_it_is_a_may_and_can_be_declined(self):
        a = self.upkeep(7, ["No"])
        self.assertNotIn("Fallen Hero", [p.card.name for p in a.battlefield])
        self.assertEqual([c.name for c in a.graveyard], ["Fallen Hero"])

    def test_only_a_creature_card_can_come_back(self):
        a = self.upkeep(7, ["Yes"], graveyard=[FOREST])
        self.assertEqual([c.name for c in a.graveyard], ["Forest"])

    def test_it_does_nothing_at_an_opponents_upkeep(self):
        a = self.upkeep(7, ["Yes", "Fallen Hero"], seat=1)
        self.assertNotIn("Fallen Hero", [p.card.name for p in a.battlefield])


class GlitteringMassifTests(unittest.TestCase):
    def test_cycling_costs_two_and_draws_a_card(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(2)
        a.hand = [MASSIF]
        a.library = [PLAINS, FOREST]
        game._perform(a, CYCLE + MASSIF.name)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Plains"], ["Glittering Massif"]))
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_cycling_needs_two_mana(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(1)
        a.hand = [MASSIF]
        self.assertFalse(any(x.startswith(CYCLE) for x in game.legal_actions(a)))


class RuggedPrairieTests(unittest.TestCase):
    def test_on_its_own_it_makes_only_colorless(self):
        self.assertTrue(castable(ONE, Permanent(PRAIRIE)))
        self.assertFalse(castable(RED, Permanent(PRAIRIE)))
        self.assertFalse(castable(WHITE, Permanent(PRAIRIE)))

    def test_with_red_or_white_mana_to_pay_it_makes_two_mana_of_either_color_pair(self):
        for spell in (RED_RED, RED_WHITE, WHITE_WHITE):
            for payer in (MOUNTAIN, PLAINS):
                with self.subTest(spell=spell.name, payer=payer.name):
                    self.assertTrue(castable(spell, Permanent(PRAIRIE), Permanent(payer)))

    def test_it_cannot_make_green_or_pay_for_itself_with_other_colors(self):
        self.assertFalse(castable(GREEN, Permanent(PRAIRIE), Permanent(MOUNTAIN)))
        self.assertFalse(castable(RED_RED, Permanent(PRAIRIE), Permanent(FOREST)))

    def test_it_makes_exactly_two_mana_for_the_one_it_took(self):
        three = real("Triple", "{R}{R}{R}", "Instant", "Draw a card.", colors=("R",))
        self.assertFalse(castable(three, Permanent(PRAIRIE), Permanent(MOUNTAIN)))
        self.assertTrue(castable(three, Permanent(PRAIRIE), Permanent(MOUNTAIN), Permanent(MOUNTAIN)))


class SunscorchedDivideTests(unittest.TestCase):
    def test_one_mana_of_any_kind_turns_into_red_and_white(self):
        for payer in (MOUNTAIN, FOREST, WASTES):
            with self.subTest(payer=payer.name):
                self.assertTrue(castable(RED_WHITE, Permanent(DIVIDE), Permanent(payer)))

    def test_it_cannot_pay_for_itself(self):
        self.assertFalse(castable(RED_WHITE, Permanent(DIVIDE)))
        self.assertFalse(castable(RED, Permanent(DIVIDE)))

    def test_it_makes_exactly_red_and_white(self):
        self.assertFalse(castable(RED_RED, Permanent(DIVIDE), Permanent(MOUNTAIN)))
        self.assertFalse(castable(GREEN, Permanent(DIVIDE), Permanent(WASTES)))


class TempleOfTriumphTests(unittest.TestCase):
    def test_it_scries_one_when_it_enters_and_the_card_may_go_to_the_bottom(self):
        game, a, _ = play(pick("Put on the bottom"), TEMPLE)
        self.assertEqual((a.library[0].name, a.library[-1].name), ("Forest", "Plains"))

    def test_the_card_may_stay_on_top(self):
        game, a, _ = play(pick("Keep", "Top"), TEMPLE)
        self.assertEqual(a.library[0].name, "Plains")

    def test_it_scries_only_when_it_enters(self):
        game, a, _ = play(pick("Keep", "Top"), TEMPLE)
        self.assertEqual(len(a.library), 4)


class FieldsOfStrifeTests(unittest.TestCase):
    def table(self, policy, mine):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(FIELDS)] + [Permanent(c) for c in mine]
        a.library = [PLAINS, FOREST, FOREST, FOREST]
        return game, a

    def test_two_red_white_and_two_more_pay_to_surveil_one(self):
        game, a = self.table(pick("Put into"), [MOUNTAIN, PLAINS, FOREST, FOREST])
        activate(game, a, "Surveil")
        self.assertEqual([c.name for c in a.graveyard], ["Plains"])
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_the_card_may_stay_on_top(self):
        game, a = self.table(pick("Keep on top"), [MOUNTAIN, PLAINS, FOREST, FOREST])
        activate(game, a, "Surveil")
        self.assertEqual((a.library[0].name, a.graveyard), ("Plains", []))

    def test_without_the_mana_it_cannot_be_activated(self):
        game, a = self.table(pick(), [MOUNTAIN, PLAINS, FOREST])
        self.assertFalse(can_activate(game, a, "Surveil"))

    def test_the_red_and_the_white_are_required(self):
        game, a = self.table(pick(), [FOREST, FOREST, FOREST, FOREST])
        self.assertFalse(can_activate(game, a, "Surveil"))


class TerramorphicExpanseTests(unittest.TestCase):
    def table(self, library, policy):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(EXPANSE)]
        a.library = list(library)
        return game, a

    def test_it_sacrifices_itself_and_fetches_a_basic_land_tapped(self):
        game, a = self.table([FOREST, MOUNTAIN, PLAINS], pick("Mountain"))
        activate(game, a, "Sacrifice")
        self.assertEqual([p.card.name for p in a.battlefield], ["Mountain"])
        self.assertTrue(a.battlefield[0].tapped)
        self.assertEqual([c.name for c in a.graveyard], ["Terramorphic Expanse"])
        self.assertEqual(sorted(c.name for c in a.library), ["Forest", "Plains"])

    def test_a_nonbasic_land_cannot_be_fetched(self):
        game, a = self.table([FORGE, STEPPE], pick())
        activate(game, a, "Sacrifice")
        self.assertEqual(a.battlefield, [])
        self.assertEqual([c.name for c in a.graveyard], ["Terramorphic Expanse"])
        self.assertEqual(sorted(c.name for c in a.library), ["Battlefield Forge", "Turbulent Steppe"])

    def test_the_cost_is_paid_even_with_no_basic_land_to_find(self):
        game, a = self.table([], pick())
        activate(game, a, "Sacrifice")
        self.assertEqual(a.battlefield, [])

    def test_it_must_be_untapped_to_use(self):
        game, a = self.table([FOREST], pick())
        a.battlefield[0].tapped = True
        self.assertFalse(can_activate(game, a, "Sacrifice"))


class LoreholdCampusTests(unittest.TestCase):
    def table(self, policy, others):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(CAMPUS)] + others
        a.library = [PLAINS, FOREST, FOREST, FOREST]
        return game, a

    def test_four_mana_and_a_tap_scry_one_and_the_card_may_go_to_the_bottom(self):
        game, a = self.table(pick("Put on the bottom"), lands(4))
        activate(game, a, "Scry")
        self.assertEqual((a.library[0].name, a.library[-1].name), ("Forest", "Plains"))
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_the_card_may_stay_on_top(self):
        game, a = self.table(pick("Keep", "Top"), lands(4))
        activate(game, a, "Scry")
        self.assertEqual(a.library[0].name, "Plains")

    def test_three_other_lands_are_not_enough(self):
        game, a = self.table(pick(), lands(3))
        self.assertFalse(can_activate(game, a, "Scry"))


if __name__ == "__main__":
    unittest.main()
