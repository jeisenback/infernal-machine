"""Emblems (#424): "You get an emblem with "..."" puts an emblem in its controller's command zone (CR 114). It is not a permanent,
so no spell or ability can touch it, and its text works like a permanent's static or triggered abilities. Played from the cards'
real Oracle text; an emblem whose text the engine cannot read leaves the loyalty ability unread."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, activate, enter, pick, real, run_stack, table


def walker(name, cost, text, loyalty, colors):
    return Card(**{**real(name, cost, "Legendary Planeswalker — " + name.split(",")[0], text, colors=colors).__dict__, "loyalty": loyalty})


ELSPETH = walker("Elspeth, Sun's Champion", "{4}{W}{W}",
                 "+1: Create three 1/1 white Soldier creature tokens.\n"
                 "−3: Destroy all creatures with power 4 or greater.\n"
                 "−7: You get an emblem with \"Creatures you control get +2/+2 and have flying.\"", "4", ("W",))
AJANI = walker("Ajani, Adversary of Tyrants", "{2}{W}{W}",
               "+1: Put a +1/+1 counter on each of up to two target creatures.\n"
               "−2: Return target creature card with mana value 2 or less from your graveyard to the battlefield.\n"
               "−7: You get an emblem with \"At the beginning of your end step, create three 1/1 white Cat creature tokens with "
               "lifelink.\"", "4", ("W",))
RAL = walker("Ral, Crackling Wit", "{2}{U}{R}",
             "Whenever you cast a noncreature spell, put a loyalty counter on Ral.\n"
             "+1: Create a 1/1 blue and red Otter creature token with prowess.\n"
             "−3: Draw three cards, then discard two cards.\n"
             "−10: Draw three cards. You get an emblem with \"Instant and sorcery spells you cast have storm.\" (Whenever you cast an "
             "instant or sorcery spell, copy it for each spell cast before it this turn.)", "4", ("U", "R"))
TEFERI = walker("Teferi, Hero of Dominaria", "{3}{W}{U}",
                "+1: Draw a card. At the beginning of the next end step, untap up to two lands.\n"
                "−3: Put target nonland permanent into its owner's library third from the top.\n"
                "−8: You get an emblem with \"Whenever you draw a card, exile target permanent an opponent controls.\"", "4", ("W", "U"))
NISSA = walker("Nissa, Vital Force", "{3}{G}{G}",
               "+1: Untap target land you control. Until your next turn, it becomes a 5/5 Elemental creature with haste. It's still a land.\n"
               "−3: Return target permanent card from your graveyard to your hand.\n"
               "−6: You get an emblem with \"Whenever a land you control enters, you may draw a card.\"", "5", ("G",))
WRATH = Card(name="Wrath", mana_cost="{2}{W}{W}", type_line="Sorcery", oracle_text="Destroy all creatures.")


def names(cards):
    return [c.name for c in cards]


class ParseTests(unittest.TestCase):
    def test_an_emblem_whose_text_the_engine_reads_makes_the_walker_playable(self):
        self.assertEqual(unsupported_lines(ELSPETH), [])
        self.assertEqual(unsupported_lines(AJANI), [])

    def test_an_emblem_whose_text_is_not_read_leaves_the_ability_unread(self):
        self.assertEqual([line[:30] for line in unsupported_lines(RAL)], ["−10: Draw three cards. You get"])


class StaticEmblemTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats
        self.elspeth = Permanent(ELSPETH, loyalty=7)
        self.mine, self.theirs = Permanent(BEAR), Permanent(BEAR)
        self.a.battlefield = [self.elspeth, self.mine]
        self.b.battlefield = [self.theirs]

    def test_the_emblem_buffs_its_owners_creatures_only(self):
        activate(self.game, self.a, "You get an emblem")
        self.assertEqual(names(e.card for e in self.a.emblems), ["Elspeth, Sun's Champion Emblem"])
        self.assertEqual(self.b.emblems, [])
        self.assertEqual((self.game.power(self.mine), self.game.toughness(self.mine), self.game.has_keyword(self.mine, "flying")),
                         (4, 4, True))
        self.assertEqual((self.game.power(self.theirs), self.game.has_keyword(self.theirs, "flying")), (2, False))
        self.assertEqual(self.elspeth.loyalty, 0)

    def test_the_emblem_is_not_a_permanent_and_outlives_a_board_wipe(self):
        activate(self.game, self.a, "You get an emblem")
        self.a.hand = [WRATH]
        self.game._cast(self.a, WRATH, self.a.hand, free=True)
        run_stack(self.game)
        creatures = [p for seat in (self.a, self.b) for p in seat.battlefield if "Creature" in p.card.type_line]
        self.assertEqual(creatures, [])
        self.assertEqual(len(self.a.emblems), 1)
        later = enter(self.game, self.a, BEAR)
        self.assertEqual((self.game.power(later), self.game.has_keyword(later, "flying")), (4, True))

    def test_without_the_loyalty_the_ability_is_not_offered(self):
        self.elspeth.loyalty = 6
        with self.assertRaises(StopIteration):
            activate(self.game, self.a, "You get an emblem")
        self.assertEqual(self.a.emblems, [])

    def test_the_state_shows_the_emblems(self):
        activate(self.game, self.a, "You get an emblem")
        state = self.game.snapshot(self.a)
        self.assertEqual(state["seats"][0]["emblems"], ["Elspeth, Sun's Champion Emblem"])
        self.assertEqual(state["seats"][1]["emblems"], [])


class TriggeredEmblemTests(unittest.TestCase):
    def test_the_emblem_triggers_at_its_owners_end_step_only(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(AJANI, loyalty=7)]
        activate(game, a, "You get an emblem")
        self.assertEqual(len(a.emblems), 1)
        game.step = "end"
        game._turn_based_actions(b)  # the opponent's end step: nothing
        run_stack(game)
        self.assertEqual(a.battlefield, [])
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(names(p.card for p in a.battlefield), ["Cat"] * 3)
        self.assertTrue(all(game.has_keyword(p, "lifelink") for p in a.battlefield))
        self.assertEqual(b.battlefield, [])

    def test_a_watching_emblem_hears_what_its_owner_does_and_not_what_an_opponent_does(self):
        game, _, _ = table(pick("Bear"))
        a, b = game.seats
        a.battlefield = [Permanent(TEFERI, loyalty=8)]
        a.library = b.library = [BEAR, BEAR, BEAR]
        theirs = Permanent(BEAR)
        b.battlefield = [theirs]
        activate(game, a, "You get an emblem")
        game.draw(b, 1)  # the opponent draws: not "you"
        run_stack(game)
        self.assertEqual(b.battlefield, [theirs])
        game.draw(a, 1)
        run_stack(game)
        self.assertEqual((b.battlefield, names(b.exile)), ([], ["Bear"]))

    def test_an_emblem_watching_permanents_sees_its_owners_lands_only(self):
        game, _, _ = table(pick("Draw", "Yes"))
        a, b = game.seats
        a.battlefield = [Permanent(NISSA, loyalty=6)]
        a.library = b.library = [BEAR, BEAR, BEAR]
        activate(game, a, "You get an emblem")
        enter(game, b, FOREST)  # an opponent's land: not "you control"
        run_stack(game)
        self.assertEqual((len(a.hand), len(b.hand)), (0, 0))
        enter(game, a, FOREST)
        run_stack(game)
        self.assertEqual((len(a.hand), len(b.hand)), (1, 0))


if __name__ == "__main__":
    unittest.main()
