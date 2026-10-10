"""The thirteen Witherbloom lands of the precon decks (issue #167), each played from its real Oracle text: how it comes in
(tapped or untapped, with a case on each side of the line), the mana it makes really pays for a spell, and the extra
abilities do what they say."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, CYCLE, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, real
from tests.test_triggers_80 import FOREST, PLAINS

SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
BLACK = real("Black Draw", "{B}", "Instant", "Draw a card.", colors=("B",))
GREEN = real("Green Draw", "{G}", "Instant", "Draw a card.", colors=("G",))
BLACK_BLACK = real("Double Black", "{B}{B}", "Instant", "Draw a card.", colors=("B",))
GREEN_GREEN = real("Double Green", "{G}{G}", "Instant", "Draw a card.", colors=("G",))
BLACK_GREEN = real("Black Green", "{B}{G}", "Instant", "Draw a card.", colors=("B", "G"))
WHITE = real("White Draw", "{W}", "Instant", "Draw a card.", colors=("W",))
ONE = real("One Draw", "{1}", "Instant", "Draw a card.")


def land(name, type_line, text, mana):
    """A land as Scryfall gives it: the Oracle text and the mana it can produce."""
    return Card(name=name, type_line=type_line, oracle_text=text, produced_mana=tuple(mana))


THICKET = land("Festering Thicket", "Land — Swamp Forest", "({T}: Add {B} or {G}.)\nThis land enters tapped.\nCycling {2} ({2}, Discard this card: Draw a card.)", "BG")
BACKWOODS = land("Grim Backwoods", "Land", "{T}: Add {C}.\n{2}{B}{G}, {T}, Sacrifice a creature: Draw a card.", "C")
MARKET = land("High Market", "Land", "{T}: Add {C}.\n{T}, Sacrifice a creature: You gain 1 life.", "C")
WASTES_PAIN = land("Llanowar Wastes", "Land", "{T}: Add {C}.\n{T}: Add {B} or {G}. This land deals 1 damage to you.", "BCG")
SNARL = land("Necroblossom Snarl", "Land", "As this land enters, you may reveal a Swamp or Forest card from your hand. If you don't, this land enters tapped.\n{T}: Add {B} or {G}.", "BG")
TEMPLE = land("Temple of Malady", "Land", "This land enters tapped.\nWhen this land enters, scry 1. (Look at the top card of your library. You may put that card on the bottom.)\n{T}: Add {B} or {G}.", "BG")
MIRE = land("Twilight Mire", "Land", "{T}: Add {C}.\n{B/G}, {T}: Add {B}{B}, {B}{G}, or {G}{G}.", "BCG")
FEN = land("Vernal Fen", "Land — Swamp Forest", "({T}: Add {B} or {G}.)\nThis land enters tapped unless you control two or more basic lands.", "BG")
BOG = land("Viridescent Bog", "Land", "{1}, {T}: Add {B}{G}.", "BG")
CEMETERY = land("Woodland Cemetery", "Land", "This land enters tapped unless you control a Swamp or a Forest.\n{T}: Add {B} or {G}.", "BG")
GRAVE = land("Titan's Grave", "Land", "This land enters tapped.\n{T}: Add {B} or {G}.\n{2}{B}{G}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)", "BG")
CAMPUS = land("Witherbloom Campus", "Land", "This land enters tapped.\n{T}: Add {B} or {G}.\n{4}, {T}: Scry 1. (Look at the top card of your library. You may put that card on the bottom.)", "BG")
HAUNTED = land("Haunted Mire", "Land — Swamp Forest", "({T}: Add {B} or {G}.)\nThis land enters tapped.", "BG")

ALL = [THICKET, BACKWOODS, MARKET, WASTES_PAIN, SNARL, TEMPLE, MIRE, FEN, BOG, CEMETERY, GRAVE, HAUNTED, CAMPUS]
BLACK_OR_GREEN = [THICKET, WASTES_PAIN, SNARL, TEMPLE, FEN, CEMETERY, GRAVE, HAUNTED, CAMPUS]
ALWAYS_TAPPED = [THICKET, TEMPLE, GRAVE, HAUNTED, CAMPUS]


def play(policy, card, mine=(), theirs=(), hand=()):
    """Seat 0 plays `card` from its hand (which also holds `hand`); returns (game, seat, permanent)."""
    game, _ = table3(policy)
    a = game.seats[0]
    a.battlefield = list(mine)
    game.seats[1].battlefield = list(theirs)
    a.hand = [card, *hand]
    a.library = [PLAINS, FOREST, FOREST, FOREST]
    game._perform(a, PLAY_LAND + card.name)
    run_stack(game)
    return game, a, next(p for p in a.battlefield if p.card.name == card.name)


def entered_tapped(card, mine=(), theirs=(), hand=(), policy=None):
    return play(policy or pick(), card, mine, theirs, hand)[2].tapped


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
                self.assertTrue(entered_tapped(card, mine=[Permanent(SWAMP), Permanent(FOREST)], hand=[SWAMP, FOREST]))

    def test_the_lands_that_enter_untapped_do(self):
        for card in (BACKWOODS, MARKET, WASTES_PAIN, MIRE, BOG):
            with self.subTest(card=card.name):
                self.assertFalse(entered_tapped(card))

    def test_a_land_that_makes_black_or_green_pays_for_either_but_not_for_another_color(self):
        for card in BLACK_OR_GREEN:
            with self.subTest(card=card.name):
                self.assertTrue(castable(BLACK, Permanent(card)), "black")
                self.assertTrue(castable(GREEN, Permanent(card)), "green")
                self.assertFalse(castable(WHITE, Permanent(card)), "white")
                self.assertFalse(castable(BLACK_GREEN, Permanent(card)), "it makes one mana")


class VernalFenTests(unittest.TestCase):
    def test_two_or_more_basic_lands_make_it_untapped(self):
        self.assertFalse(entered_tapped(FEN, mine=[Permanent(MOUNTAIN), Permanent(MOUNTAIN)]))
        self.assertFalse(entered_tapped(FEN, mine=[Permanent(SWAMP), Permanent(FOREST), Permanent(WASTES)]))

    def test_one_basic_land_is_not_enough(self):
        self.assertTrue(entered_tapped(FEN))
        self.assertTrue(entered_tapped(FEN, mine=[Permanent(SWAMP)]))

    def test_nonbasic_lands_do_not_count(self):
        self.assertTrue(entered_tapped(FEN, mine=[Permanent(CEMETERY), Permanent(HAUNTED), Permanent(THICKET)]))

    def test_an_opponents_basic_lands_do_not_count(self):
        self.assertTrue(entered_tapped(FEN, theirs=lands(4)))


class WoodlandCemeteryTests(unittest.TestCase):
    def test_a_swamp_or_a_forest_makes_it_untapped(self):
        for enabler in (SWAMP, FOREST, THICKET, HAUNTED):
            with self.subTest(enabler=enabler.name):
                self.assertFalse(entered_tapped(CEMETERY, mine=[Permanent(enabler)]))

    def test_other_lands_and_permanents_do_not(self):
        self.assertTrue(entered_tapped(CEMETERY))
        self.assertTrue(entered_tapped(CEMETERY, mine=[Permanent(PLAINS), Permanent(MOUNTAIN), Permanent(WASTES), Permanent(BEAR)]))

    def test_an_opponents_swamp_or_forest_does_not(self):
        self.assertTrue(entered_tapped(CEMETERY, theirs=[Permanent(SWAMP), Permanent(FOREST)]))

    def test_a_swamp_or_forest_in_hand_does_not(self):
        self.assertTrue(entered_tapped(CEMETERY, hand=[SWAMP, FOREST]))


class NecroblossomSnarlTests(unittest.TestCase):
    def test_revealing_a_swamp_or_a_forest_from_hand_lets_it_enter_untapped(self):
        for card in (SWAMP, FOREST, HAUNTED):
            with self.subTest(card=card.name):
                game, a, snarl = play(pick("Reveal"), SNARL, hand=[BEAR, card])
                self.assertFalse(snarl.tapped)
                self.assertEqual([c.name for c in a.hand], ["Bear", card.name], "revealed, not discarded")

    def test_it_enters_tapped_when_nothing_in_hand_can_be_revealed(self):
        self.assertTrue(entered_tapped(SNARL, policy=pick("Reveal")), "empty hand")
        self.assertTrue(entered_tapped(SNARL, hand=[BEAR, PLAINS, WASTES], policy=pick("Reveal")), "no Swamp or Forest")

    def test_a_land_on_the_battlefield_is_not_a_reveal(self):
        self.assertTrue(entered_tapped(SNARL, mine=[Permanent(SWAMP), Permanent(FOREST)], policy=pick("Reveal")))

    def test_declining_to_reveal_enters_tapped(self):
        self.assertTrue(entered_tapped(SNARL, hand=[SWAMP], policy=pick("Enter tapped")))


class LlanowarWastesTests(unittest.TestCase):
    def pay(self, spell):
        t = Table(spell, n=0, mine=[Permanent(WASTES_PAIN)])
        before = t.a.life
        t.cast()
        return before - t.a.life

    def test_colored_mana_costs_one_life(self):
        self.assertEqual(self.pay(BLACK), 1)
        self.assertEqual(self.pay(GREEN), 1)

    def test_colorless_mana_costs_nothing(self):
        self.assertEqual(self.pay(ONE), 0)


class TwilightMireTests(unittest.TestCase):
    def test_on_its_own_it_makes_only_colorless(self):
        self.assertTrue(castable(ONE, Permanent(MIRE)))
        self.assertFalse(castable(BLACK, Permanent(MIRE)))
        self.assertFalse(castable(GREEN, Permanent(MIRE)))

    def test_with_black_or_green_mana_to_pay_it_makes_two_mana_of_either_color_pair(self):
        for spell in (BLACK_BLACK, BLACK_GREEN, GREEN_GREEN):
            for payer in (SWAMP, FOREST):
                with self.subTest(spell=spell.name, payer=payer.name):
                    self.assertTrue(castable(spell, Permanent(MIRE), Permanent(payer)))

    def test_it_cannot_make_white_or_be_paid_for_with_other_colors(self):
        self.assertFalse(castable(WHITE, Permanent(MIRE), Permanent(SWAMP)))
        self.assertFalse(castable(BLACK_BLACK, Permanent(MIRE), Permanent(MOUNTAIN)))

    def test_it_makes_exactly_two_mana_for_the_one_it_took(self):
        three = real("Triple", "{B}{B}{B}", "Instant", "Draw a card.", colors=("B",))
        self.assertFalse(castable(three, Permanent(MIRE), Permanent(SWAMP)))
        self.assertTrue(castable(three, Permanent(MIRE), Permanent(SWAMP), Permanent(SWAMP)))


class ViridescentBogTests(unittest.TestCase):
    def test_one_mana_of_any_kind_turns_into_black_and_green(self):
        for payer in (SWAMP, MOUNTAIN, WASTES):
            with self.subTest(payer=payer.name):
                self.assertTrue(castable(BLACK_GREEN, Permanent(BOG), Permanent(payer)))

    def test_it_cannot_pay_for_itself(self):
        self.assertFalse(castable(BLACK_GREEN, Permanent(BOG)))
        self.assertFalse(castable(BLACK, Permanent(BOG)))

    def test_it_makes_exactly_black_and_green(self):
        self.assertFalse(castable(BLACK_BLACK, Permanent(BOG), Permanent(WASTES)))
        self.assertFalse(castable(WHITE, Permanent(BOG), Permanent(WASTES)))


class FesteringThicketTests(unittest.TestCase):
    def test_cycling_costs_two_and_draws_a_card(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(2)
        a.hand = [THICKET]
        a.library = [PLAINS, FOREST]
        game._perform(a, CYCLE + THICKET.name)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Plains"], ["Festering Thicket"]))
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_cycling_needs_two_mana(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(1)
        a.hand = [THICKET]
        self.assertFalse(any(x.startswith(CYCLE) for x in game.legal_actions(a)))


class TempleOfMaladyTests(unittest.TestCase):
    def test_it_scries_one_when_it_enters_and_the_card_may_go_to_the_bottom(self):
        game, a, _ = play(pick("Put on the bottom"), TEMPLE)
        self.assertEqual((a.library[0].name, a.library[-1].name), ("Forest", "Plains"))

    def test_the_card_may_stay_on_top(self):
        game, a, _ = play(pick("Keep on top"), TEMPLE)
        self.assertEqual((a.library[0].name, len(a.library)), ("Plains", 4))


class TitansGraveTests(unittest.TestCase):
    def table(self, policy, mine):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(GRAVE)] + [Permanent(c) for c in mine]
        a.library = [PLAINS, FOREST, FOREST, FOREST]
        return game, a

    def test_black_green_and_two_more_pay_to_surveil_one(self):
        game, a = self.table(pick("Put into"), [SWAMP, FOREST, MOUNTAIN, MOUNTAIN])
        activate(game, a, "Surveil")
        self.assertEqual([c.name for c in a.graveyard], ["Plains"])
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_the_card_may_stay_on_top(self):
        game, a = self.table(pick("Keep on top"), [SWAMP, FOREST, MOUNTAIN, MOUNTAIN])
        activate(game, a, "Surveil")
        self.assertEqual((a.library[0].name, a.graveyard), ("Plains", []))

    def test_without_the_mana_it_cannot_be_activated(self):
        game, a = self.table(pick(), [SWAMP, FOREST, MOUNTAIN])
        self.assertFalse(can_activate(game, a, "Surveil"))

    def test_the_black_and_the_green_are_required(self):
        game, a = self.table(pick(), [MOUNTAIN, MOUNTAIN, MOUNTAIN, MOUNTAIN])
        self.assertFalse(can_activate(game, a, "Surveil"))


class WitherbloomCampusTests(unittest.TestCase):
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
        game, a = self.table(pick("Keep on top"), lands(4))
        activate(game, a, "Scry")
        self.assertEqual(a.library[0].name, "Plains")

    def test_three_other_lands_are_not_enough(self):
        game, a = self.table(pick(), lands(3))
        self.assertFalse(can_activate(game, a, "Scry"))


class HighMarketTests(unittest.TestCase):
    def table(self, policy=None, mine=(BEAR,), theirs=()):
        game, _ = table3(policy or pick())
        a = game.seats[0]
        a.battlefield = [Permanent(MARKET)] + [Permanent(c) for c in mine]
        game.seats[1].battlefield = [Permanent(c) for c in theirs]
        return game, a

    def test_it_makes_colorless_mana(self):
        self.assertTrue(castable(ONE, Permanent(MARKET)))
        self.assertFalse(castable(BLACK, Permanent(MARKET)))

    def test_sacrificing_a_creature_gains_one_life(self):
        game, a = self.table()
        life = a.life
        activate(game, a, "Sacrifice a creature")
        self.assertEqual(a.life, life + 1)
        self.assertEqual([c.name for c in a.graveyard], ["Bear"])
        self.assertTrue(a.battlefield[0].tapped)

    def test_it_cannot_be_activated_without_a_creature_to_sacrifice(self):
        game, a = self.table(mine=())
        self.assertFalse(can_activate(game, a, "Sacrifice a creature"))

    def test_an_opponents_creature_cannot_be_sacrificed(self):
        game, a = self.table(mine=(), theirs=(BEAR,))
        self.assertFalse(can_activate(game, a, "Sacrifice a creature"))

    def test_it_cannot_be_activated_while_tapped(self):
        game, a = self.table()
        a.battlefield[0].tapped = True
        self.assertFalse(can_activate(game, a, "Sacrifice a creature"))


class GrimBackwoodsTests(unittest.TestCase):
    def table(self, mine, creatures=(BEAR,)):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(BACKWOODS)] + [Permanent(c) for c in creatures] + [Permanent(c) for c in mine]
        a.library = [PLAINS, FOREST]
        return game, a

    def test_it_makes_colorless_mana(self):
        self.assertTrue(castable(ONE, Permanent(BACKWOODS)))
        self.assertFalse(castable(GREEN, Permanent(BACKWOODS)))

    def test_two_black_green_and_a_creature_draw_a_card(self):
        game, a = self.table([SWAMP, FOREST, MOUNTAIN, MOUNTAIN])
        activate(game, a, "Sacrifice a creature")
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Plains"], ["Bear"]))
        self.assertTrue(all(p.tapped for p in a.battlefield if p.card.name != "Bear"))

    def test_it_cannot_be_activated_without_a_creature_to_sacrifice(self):
        game, a = self.table([SWAMP, FOREST, MOUNTAIN, MOUNTAIN], creatures=())
        self.assertFalse(can_activate(game, a, "Sacrifice a creature"))

    def test_it_cannot_be_activated_without_the_mana(self):
        game, a = self.table([SWAMP, FOREST, MOUNTAIN])
        self.assertFalse(can_activate(game, a, "Sacrifice a creature"))

    def test_the_black_and_the_green_are_required(self):
        game, a = self.table([MOUNTAIN, MOUNTAIN, MOUNTAIN, MOUNTAIN])
        self.assertFalse(can_activate(game, a, "Sacrifice a creature"))
        game, a = self.table([SWAMP, SWAMP, MOUNTAIN, MOUNTAIN])
        self.assertFalse(can_activate(game, a, "Sacrifice a creature"), "no green")


if __name__ == "__main__":
    unittest.main()
