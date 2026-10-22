"""The storage-counter lands of issue #91, each played from its real Oracle text: Hollow Trees (and Bottomless Vault, Dwarven
Hold, Icatian Store, Sand Silos), which may be left tapped to collect a counter each upkeep, and Fountain of Cho (and
Mercadian Bazaar, Rushwood Grove, Saprazzan Cove, Subterranean Hangar), which taps for a counter. Either kind gives one
mana for each storage counter removed."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, UNTAP_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import pick, real, run_stack, Table, table3

HOLLOW_TREES = Card(
    name="Hollow Trees", type_line="Land", produced_mana=("G",),
    oracle_text="This land enters tapped.\nYou may choose not to untap this land during your untap step.\n"
                "At the beginning of your upkeep, if this land is tapped, put a storage counter on it.\n"
                "{T}, Remove any number of storage counters from this land: Add {G} for each storage counter removed this way.")
FOUNTAIN = Card(
    name="Fountain of Cho", type_line="Land", produced_mana=("W",),
    oracle_text="This land enters tapped.\n{T}: Put a storage counter on this land.\n"
                "{T}, Remove any number of storage counters from this land: Add {W} for each storage counter removed this way.")
GREEN = real("Green Draw", "{G}", "Instant", "Draw a card.", colors=("G",))
GREEN_GREEN = real("Double Green", "{G}{G}", "Instant", "Draw a card.", colors=("G",))
GREEN3 = real("Triple Green", "{G}{G}{G}", "Instant", "Draw a card.", colors=("G",))
TWO = real("Two", "{2}", "Instant", "Draw a card.")
WHITE = real("White Draw", "{W}", "Instant", "Draw a card.", colors=("W",))


def land(card, counters=0, tapped=False):
    permanent = Permanent(card, tapped=tapped)
    if counters:
        permanent.counters["storage"] = counters
    return permanent


def castable(spell, permanent):
    t = Table(spell, n=0, mine=[permanent])
    return any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a))


def cast(spell, permanent):
    return Table(spell, n=0, mine=[permanent]).cast()


def step(game, seat, name):
    game.active = seat.index
    game.step = name
    game._turn_based_actions(seat)
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_both_kinds_are_fully_understood(self):
        for card in (HOLLOW_TREES, FOUNTAIN):
            with self.subTest(card=card.name):
                self.assertEqual(unsupported_lines(card), [])


class StorageManaTests(unittest.TestCase):
    def test_it_makes_one_mana_for_each_counter(self):
        for card, spell in ((HOLLOW_TREES, GREEN3), (FOUNTAIN, real("Triple White", "{W}{W}{W}", "Instant", "Draw a card.", colors=("W",)))):
            with self.subTest(card=card.name):
                self.assertTrue(castable(spell, land(card, 3)))
                self.assertFalse(castable(spell, land(card, 2)), "two counters are two mana")

    def test_with_no_counters_it_makes_no_mana(self):
        self.assertFalse(castable(GREEN, land(HOLLOW_TREES, 0)))
        self.assertFalse(castable(WHITE, land(FOUNTAIN, 0)))

    def test_it_makes_only_its_own_color(self):
        self.assertFalse(castable(WHITE, land(HOLLOW_TREES, 3)))
        self.assertFalse(castable(GREEN, land(FOUNTAIN, 3)))

    def test_as_many_counters_come_off_as_mana_is_used(self):
        for spell, left in ((GREEN, 3), (GREEN_GREEN, 2), (TWO, 2), (GREEN3, 1)):
            with self.subTest(spell=spell.name):
                permanent = land(HOLLOW_TREES, 4)
                cast(spell, permanent)
                self.assertEqual((permanent.counters.get("storage", 0), permanent.tapped), (left, True))

    def test_the_last_counter_leaves_the_land_in_play(self):
        permanent = land(HOLLOW_TREES, 1)
        t = cast(GREEN, permanent)
        self.assertIn(permanent, t.a.battlefield)
        self.assertEqual(permanent.counters, {})

    def test_a_tapped_land_makes_no_mana(self):
        self.assertFalse(castable(GREEN, land(HOLLOW_TREES, 3, tapped=True)))

    def test_it_is_tapped_once_however_much_mana_it_makes(self):
        permanent = land(HOLLOW_TREES, 3)
        cast(GREEN3, permanent)
        self.assertTrue(permanent.tapped)


class UpkeepCounterTests(unittest.TestCase):
    def table(self, permanent, who=0):
        game, _ = table3(pick())
        game.seats[who].battlefield = [permanent]
        return game

    def test_a_tapped_land_gets_a_counter_at_its_controllers_upkeep(self):
        permanent = land(HOLLOW_TREES, 1, tapped=True)
        game = self.table(permanent)
        step(game, game.seats[0], "upkeep")
        self.assertEqual(permanent.counters, {"storage": 2})

    def test_an_untapped_land_gets_none(self):
        permanent = land(HOLLOW_TREES, 1)
        game = self.table(permanent)
        step(game, game.seats[0], "upkeep")
        self.assertEqual(permanent.counters, {"storage": 1})

    def test_it_does_nothing_at_an_opponents_upkeep(self):
        permanent = land(HOLLOW_TREES, 0, tapped=True)
        game = self.table(permanent)
        step(game, game.seats[1], "upkeep")
        self.assertEqual(permanent.counters, {})


class UntapChoiceTests(unittest.TestCase):
    def untap(self, answer, tapped=True, card=HOLLOW_TREES, who=0):
        asked = []

        def policy(prompt, options):
            asked.append((prompt, options))
            return pick(answer)(prompt, options)

        game, _ = table3(policy)
        permanent = land(card, tapped=tapped)
        game.seats[0].battlefield = [permanent]
        step(game, game.seats[who], "untap")
        return permanent, asked

    def test_you_may_leave_it_tapped(self):
        permanent, asked = self.untap("Leave")
        self.assertTrue(permanent.tapped)
        self.assertEqual(asked, [(UNTAP_PROMPT + "Hollow Trees", ["Untap", "Leave tapped"])])

    def test_or_untap_it(self):
        permanent, _ = self.untap("Untap")
        self.assertFalse(permanent.tapped)

    def test_an_untapped_land_is_not_asked_about(self):
        permanent, asked = self.untap("Leave", tapped=False)
        self.assertEqual((permanent.tapped, asked), (False, []))

    def test_a_land_without_the_choice_just_untaps(self):
        permanent, asked = self.untap("Leave", card=FOUNTAIN)
        self.assertEqual((permanent.tapped, asked), (False, []))

    def test_an_opponents_untap_step_does_not_untap_it_or_ask(self):
        permanent, asked = self.untap("Untap", who=1)
        self.assertEqual((permanent.tapped, asked), (True, []))

    def test_leaving_it_tapped_for_turns_collects_counters_to_spend(self):
        game, _ = table3(pick("Leave"))
        a = game.seats[0]
        permanent = land(HOLLOW_TREES, tapped=True)
        a.battlefield = [permanent]
        for _ in range(3):
            step(game, a, "untap")
            step(game, a, "upkeep")
        self.assertEqual((permanent.tapped, permanent.counters), (True, {"storage": 3}))
        permanent.tapped = False
        t = cast(GREEN3, permanent)
        self.assertEqual((permanent.counters, t.a.battlefield), ({}, [permanent]))


class FountainOfChoTests(unittest.TestCase):
    def test_tapping_it_puts_a_counter_on_it(self):
        game, _ = table3(pick())
        a = game.seats[0]
        permanent = land(FOUNTAIN)
        a.battlefield = [permanent]
        action = next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Put a storage counter" in x)
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((permanent.counters, permanent.tapped), ({"storage": 1}, True))

    def test_it_cannot_do_it_while_tapped(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [land(FOUNTAIN, tapped=True)]
        self.assertFalse(any("Put a storage counter" in x for x in game.legal_actions(a)))


if __name__ == "__main__":
    unittest.main()
