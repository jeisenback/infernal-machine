"""The twelve Silverquill lands of the precon decks (issue #166), each played from its real Oracle text: how it comes in
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
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
WHITE = real("White Draw", "{W}", "Instant", "Draw a card.", colors=("W",))
BLACK = real("Black Draw", "{B}", "Instant", "Draw a card.", colors=("B",))
WHITE_BLACK = real("White Black", "{W}{B}", "Instant", "Draw a card.", colors=("W", "B"))
GREEN = real("Green Draw", "{G}", "Instant", "Draw a card.", colors=("G",))
ONE = real("One Draw", "{1}", "Instant", "Draw a card.")


def land(name, type_line, text, mana):
    """A land as Scryfall gives it: the Oracle text and the mana it can produce."""
    return Card(name=name, type_line=type_line, oracle_text=text, produced_mana=tuple(mana))


ECLIPSED = land("Eclipsed Steppe", "Land — Plains Swamp", "({T}: Add {W} or {B}.)\nThis land enters tapped unless you control two or more basic lands.", "BW")
MOOR = land("Turbulent Moor", "Land — Plains Swamp", "({T}: Add {W} or {B}.)\nThis land enters tapped unless your opponents control eight or more lands.", "BW")
EXPANSE = land("Umbral Expanse", "Land — Plains Swamp", "({T}: Add {W} or {B}.)\nThis land enters tapped.\nCycling {2} ({2}, Discard this card: Draw a card.)", "BW")
CAVES = land("Caves of Koilos", "Land", "{T}: Add {C}.\n{T}: Add {W} or {B}. This land deals 1 damage to you.", "BCW")
MIRE = land("Desolate Mire", "Land", "{1}, {T}: Add {W}{B}.", "BW")
CHAPEL = land("Isolated Chapel", "Land", "This land enters tapped unless you control a Plains or a Swamp.\n{T}: Add {W} or {B}.", "BW")
SNARL = land("Shineshadow Snarl", "Land", "As this land enters, you may reveal a Plains or Swamp card from your hand. If you don't, this land enters tapped.\n{T}: Add {W} or {B}.", "BW")
TEMPLE = land("Temple of Silence", "Land", "This land enters tapped.\nWhen this land enters, scry 1. (Look at the top card of your library. You may put that card on the bottom.)\n{T}: Add {W} or {B}.", "BW")
FORUM = land("Forum of Amity", "Land", "This land enters tapped.\n{T}: Add {W} or {B}.\n{2}{W}{B}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)", "BW")
BOG = land("Bojuka Bog", "Land", "This land enters tapped.\nWhen this land enters, exile target player's graveyard.\n{T}: Add {B}.", "B")
CAMPUS = land("Silverquill Campus", "Land", "This land enters tapped.\n{T}: Add {W} or {B}.\n{4}, {T}: Scry 1. (Look at the top card of your library. You may put that card on the bottom.)", "BW")
MARSH = land("Sunlit Marsh", "Land — Plains Swamp", "({T}: Add {W} or {B}.)\nThis land enters tapped.", "BW")

ALL = [ECLIPSED, MOOR, EXPANSE, CAVES, MIRE, CHAPEL, SNARL, TEMPLE, FORUM, BOG, CAMPUS, MARSH]
WHITE_OR_BLACK = [ECLIPSED, MOOR, EXPANSE, CAVES, CHAPEL, SNARL, TEMPLE, FORUM, CAMPUS, MARSH]
ALWAYS_TAPPED = [EXPANSE, TEMPLE, FORUM, BOG, CAMPUS, MARSH]


def play(policy, card, mine=(), theirs=(), hand=(), graveyards=None):
    """Seat 0 plays `card` from its hand (which also holds `hand`); returns (game, seat, permanent)."""
    game, _ = table3(policy)
    a = game.seats[0]
    a.battlefield = list(mine)
    game.seats[1].battlefield = list(theirs)
    a.hand = [card, *hand]
    a.library = [PLAINS, FOREST, FOREST, FOREST]
    for seat, cards in (graveyards or {}).items():
        game.seats[seat].graveyard = list(cards)
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
                self.assertTrue(entered_tapped(card, mine=[Permanent(PLAINS), Permanent(SWAMP)], hand=[PLAINS, SWAMP]))

    def test_the_lands_that_enter_untapped_do(self):
        for card in (CAVES, MIRE):
            with self.subTest(card=card.name):
                self.assertFalse(entered_tapped(card))

    def test_a_land_that_makes_white_or_black_pays_for_either_but_not_for_another_color(self):
        for card in WHITE_OR_BLACK:
            with self.subTest(card=card.name):
                self.assertTrue(castable(WHITE, Permanent(card)), "white")
                self.assertTrue(castable(BLACK, Permanent(card)), "black")
                self.assertFalse(castable(GREEN, Permanent(card)), "green")
                self.assertFalse(castable(WHITE_BLACK, Permanent(card)), "it makes one mana")


class EclipsedSteppeTests(unittest.TestCase):
    def test_two_or_more_basic_lands_make_it_untapped(self):
        self.assertFalse(entered_tapped(ECLIPSED, mine=[Permanent(FOREST), Permanent(FOREST)]))
        self.assertFalse(entered_tapped(ECLIPSED, mine=[Permanent(PLAINS), Permanent(SWAMP), Permanent(WASTES)]))

    def test_one_basic_land_is_not_enough(self):
        self.assertTrue(entered_tapped(ECLIPSED))
        self.assertTrue(entered_tapped(ECLIPSED, mine=[Permanent(PLAINS)]))

    def test_nonbasic_lands_do_not_count(self):
        self.assertTrue(entered_tapped(ECLIPSED, mine=[Permanent(CHAPEL), Permanent(MOOR), Permanent(MARSH)]))

    def test_an_opponents_basic_lands_do_not_count(self):
        self.assertTrue(entered_tapped(ECLIPSED, theirs=lands(4)))


class TurbulentMoorTests(unittest.TestCase):
    def test_it_enters_tapped_unless_the_opponents_control_eight_or_more_lands(self):
        self.assertTrue(entered_tapped(MOOR, theirs=lands(7)), "seven")
        self.assertFalse(entered_tapped(MOOR, theirs=lands(8)), "eight")
        self.assertFalse(entered_tapped(MOOR, theirs=lands(12)), "twelve")

    def test_your_own_lands_do_not_count(self):
        self.assertTrue(entered_tapped(MOOR, mine=lands(9), theirs=lands(2)))

    def test_nonland_permanents_of_the_opponents_do_not_count(self):
        self.assertTrue(entered_tapped(MOOR, theirs=lands(5) + [Permanent(BEAR)] * 5))

    def test_the_lands_of_the_opponents_together_count(self):
        game, _ = table3(pick())
        game.seats[1].battlefield = lands(4)
        game.seats[2].battlefield = lands(4)
        a = game.seats[0]
        a.hand = [MOOR]
        game._perform(a, PLAY_LAND + MOOR.name)
        self.assertFalse(a.battlefield[-1].tapped)


class IsolatedChapelTests(unittest.TestCase):
    def test_a_plains_or_a_swamp_makes_it_untapped(self):
        for enabler in (PLAINS, SWAMP, EXPANSE, MARSH):
            with self.subTest(enabler=enabler.name):
                self.assertFalse(entered_tapped(CHAPEL, mine=[Permanent(enabler)]))

    def test_other_lands_and_permanents_do_not(self):
        self.assertTrue(entered_tapped(CHAPEL))
        self.assertTrue(entered_tapped(CHAPEL, mine=[Permanent(FOREST), Permanent(WASTES), Permanent(BEAR)]))

    def test_an_opponents_plains_or_swamp_does_not(self):
        self.assertTrue(entered_tapped(CHAPEL, theirs=[Permanent(PLAINS), Permanent(SWAMP)]))

    def test_a_plains_or_swamp_in_hand_does_not(self):
        self.assertTrue(entered_tapped(CHAPEL, hand=[PLAINS, SWAMP]))


class ShineshadowSnarlTests(unittest.TestCase):
    def test_revealing_a_plains_or_a_swamp_from_hand_lets_it_enter_untapped(self):
        for card in (PLAINS, SWAMP, MARSH):
            with self.subTest(card=card.name):
                game, a, snarl = play(pick("Reveal"), SNARL, hand=[BEAR, card])
                self.assertFalse(snarl.tapped)
                self.assertEqual([c.name for c in a.hand], ["Bear", card.name], "revealed, not discarded")

    def test_it_enters_tapped_when_nothing_in_hand_can_be_revealed(self):
        self.assertTrue(entered_tapped(SNARL, policy=pick("Reveal")), "empty hand")
        self.assertTrue(entered_tapped(SNARL, hand=[BEAR, FOREST, WASTES], policy=pick("Reveal")), "no Plains or Swamp")

    def test_a_land_on_the_battlefield_is_not_a_reveal(self):
        self.assertTrue(entered_tapped(SNARL, mine=[Permanent(PLAINS), Permanent(SWAMP)], policy=pick("Reveal")))

    def test_declining_to_reveal_enters_tapped(self):
        self.assertTrue(entered_tapped(SNARL, hand=[PLAINS], policy=pick("Enter tapped")))


class CavesOfKoilosTests(unittest.TestCase):
    def pay(self, spell):
        t = Table(spell, n=0, mine=[Permanent(CAVES)])
        before = t.a.life
        t.cast()
        return before - t.a.life

    def test_colored_mana_costs_one_life(self):
        self.assertEqual(self.pay(WHITE), 1)
        self.assertEqual(self.pay(BLACK), 1)

    def test_colorless_mana_costs_nothing(self):
        self.assertEqual(self.pay(ONE), 0)


class DesolateMireTests(unittest.TestCase):
    def test_one_mana_of_any_kind_turns_into_white_and_black(self):
        for payer in (PLAINS, FOREST, WASTES):
            with self.subTest(payer=payer.name):
                self.assertTrue(castable(WHITE_BLACK, Permanent(MIRE), Permanent(payer)))

    def test_it_cannot_pay_for_itself(self):
        self.assertFalse(castable(WHITE_BLACK, Permanent(MIRE)))
        self.assertFalse(castable(WHITE, Permanent(MIRE)))

    def test_it_makes_exactly_white_and_black(self):
        double_white = real("Double White", "{W}{W}", "Instant", "Draw a card.", colors=("W",))
        self.assertFalse(castable(double_white, Permanent(MIRE), Permanent(WASTES)))
        self.assertFalse(castable(GREEN, Permanent(MIRE), Permanent(WASTES)))


class UmbralExpanseTests(unittest.TestCase):
    def test_cycling_costs_two_and_draws_a_card(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(2)
        a.hand = [EXPANSE]
        a.library = [PLAINS, FOREST]
        game._perform(a, CYCLE + EXPANSE.name)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Plains"], ["Umbral Expanse"]))
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_cycling_needs_two_mana(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(1)
        a.hand = [EXPANSE]
        self.assertFalse(any(x.startswith(CYCLE) for x in game.legal_actions(a)))


class TempleOfSilenceTests(unittest.TestCase):
    def test_it_scries_one_when_it_enters_and_the_card_may_go_to_the_bottom(self):
        game, a, _ = play(pick("Put on the bottom"), TEMPLE)
        self.assertEqual((a.library[0].name, a.library[-1].name), ("Forest", "Plains"))

    def test_the_card_may_stay_on_top(self):
        game, a, _ = play(pick("Keep on top"), TEMPLE)
        self.assertEqual((a.library[0].name, len(a.library)), ("Plains", 4))


class ForumOfAmityTests(unittest.TestCase):
    def table(self, policy, mine):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(FORUM)] + [Permanent(c) for c in mine]
        a.library = [PLAINS, FOREST, FOREST, FOREST]
        return game, a

    def test_white_black_and_two_more_pay_to_surveil_one(self):
        game, a = self.table(pick("Put into"), [PLAINS, SWAMP, FOREST, FOREST])
        activate(game, a, "Surveil")
        self.assertEqual([c.name for c in a.graveyard], ["Plains"])
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_the_card_may_stay_on_top(self):
        game, a = self.table(pick("Keep on top"), [PLAINS, SWAMP, FOREST, FOREST])
        activate(game, a, "Surveil")
        self.assertEqual((a.library[0].name, a.graveyard), ("Plains", []))

    def test_without_the_mana_it_cannot_be_activated(self):
        game, a = self.table(pick(), [PLAINS, SWAMP, FOREST])
        self.assertFalse(can_activate(game, a, "Surveil"))

    def test_the_white_and_the_black_are_required(self):
        game, a = self.table(pick(), [FOREST, FOREST, FOREST, FOREST])
        self.assertFalse(can_activate(game, a, "Surveil"))


class BojukaBogTests(unittest.TestCase):
    MINE = [BEAR]
    THEIRS = [FOREST, PLAINS]

    def enter(self, target):
        game, a, bog = play(pick(target), BOG, graveyards={0: self.MINE, 1: self.THEIRS, 2: [SWAMP]})
        return game, a, bog

    def names(self, cards):
        return sorted(c.name for c in cards)

    def test_it_exiles_the_chosen_players_graveyard_and_no_other(self):
        game, a, bog = self.enter("Player: B")
        self.assertEqual(game.seats[1].graveyard, [])
        self.assertEqual(self.names(game.seats[1].exile), ["Forest", "Plains"])
        self.assertEqual(self.names(a.graveyard), ["Bear"], "mine is untouched")
        self.assertEqual(self.names(game.seats[2].graveyard), ["Swamp"], "the third player's is untouched")

    def test_it_may_target_your_own_graveyard(self):
        game, a, bog = self.enter("Player: A")
        self.assertEqual(a.graveyard, [])
        self.assertEqual(self.names(a.exile), ["Bear"])
        self.assertEqual(self.names(game.seats[1].graveyard), ["Forest", "Plains"])

    def test_it_enters_tapped_and_makes_black(self):
        game, a, bog = self.enter("Player: B")
        self.assertTrue(bog.tapped)
        self.assertTrue(castable(BLACK, Permanent(BOG)))
        self.assertFalse(castable(WHITE, Permanent(BOG)))

    def test_it_exiles_only_when_it_enters(self):
        game, a, bog = self.enter("Player: B")
        game.seats[1].graveyard.append(BEAR)
        run_stack(game)
        self.assertEqual(self.names(game.seats[1].graveyard), ["Bear"])


class SilverquillCampusTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
