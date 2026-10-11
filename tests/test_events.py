"""The registry of events (effects/events.py): each event declared once, the game announcing what happened."""

import ast
import pathlib
import re
import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import EVENTS, heard_on, triggered_abilities
from infernal_machine.effects import events as registry
from infernal_machine.game import Permanent
from tests.test_combat import BEAR
from tests.test_mass_effects import table3
from tests.test_trigger_subjects import settle

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "infernal_machine"


def watcher(name, text):
    return Card(name=name, mana_cost="{1}", type_line="Enchantment", oracle_text=text)


def declared(name, text, **kwargs):
    """Declare an event for one test and take it out again afterwards."""
    event = registry.declare(name, re.compile(text, re.I), **kwargs)

    def forget():
        del EVENTS[name]
        for occurrence in event.happens:
            if event in registry._HEARD.get(occurrence, []):
                registry._HEARD[occurrence].remove(event)
    return event, forget


def names_in(arg):
    """The event or occurrence names an argument can be: "draw", "a" if x else "b", f"chapter_{n}" (its fixed start)."""
    if isinstance(arg, ast.Constant):
        return {arg.value}
    if isinstance(arg, ast.IfExp):
        return names_in(arg.body) | names_in(arg.orelse)
    if isinstance(arg, ast.JoinedStr) and isinstance(arg.values[0], ast.Constant):
        return {arg.values[0].value}
    return set()


def announced():
    """(event names passed to Game.trigger, occurrences passed to Game.happened) in the engine's own source."""
    triggered, happened = set(), set()
    for path in PACKAGE.glob("*.py"):
        for call in ast.walk(ast.parse(path.read_text())):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.args:
                if call.func.attr == "trigger":
                    triggered |= names_in(call.args[0])
                elif call.func.attr == "happened":
                    happened |= names_in(call.args[0])
    return triggered, happened


class RegistryTests(unittest.TestCase):
    def test_every_event_has_its_text_and_a_valid_audience(self):
        self.assertGreater(len(EVENTS), 70)
        for name, event in EVENTS.items():
            self.assertEqual(event.name, name)
            self.assertEqual(event.text.groups, 1, name)  # the body after the comma
            self.assertIn(event.to, ("you", "opponents", "direct"), name)
            self.assertTrue(event.happens, name)

    def test_the_game_announces_only_declared_events(self):
        triggered, happened = announced()
        self.assertEqual({t for t in triggered if not t.startswith("chapter_") and t not in EVENTS}, set())
        known = {occurrence for event in EVENTS.values() if event.to != "direct" for occurrence in event.happens}
        self.assertEqual(happened - known, set())

    def test_every_event_is_announced_by_the_game(self):
        triggered, happened = announced()
        silent = [name for name, event in EVENTS.items()
                  if (event.to == "direct" and name not in triggered and name != "cast_self")  # that one goes on the stack in Game._cast
                  or (event.to != "direct" and not set(event.happens) & happened)]
        self.assertEqual(silent, [])

    def test_occurrences_list_their_events_in_declaration_order(self):
        self.assertEqual([e.name for e in heard_on("drew")],
                         ["draw", "opponent_draw", "opponent_extra_draw", "second_draw", "opponent_second_draw"])
        self.assertEqual({e.name for e in heard_on("scried")}, {"scry", "scry_or_surveil"})
        self.assertEqual({e.name for e in heard_on("cycled")}, {"cycle", "cycle_or_discard"})
        self.assertEqual({e.name for e in heard_on("discarded")}, {"discard", "cycle_or_discard", "opponent_discard"})
        self.assertEqual(heard_on("nothing happened"), ())

    def test_what_the_text_is_about_comes_from_the_declaration(self):
        self.assertTrue(EVENTS["ally_attacks"].about_creature)
        self.assertTrue(EVENTS["opponent_draw"].about_player)
        self.assertTrue(EVENTS["host_dies"].host_gone)
        self.assertFalse(EVENTS["draw"].about_player)

    def test_an_unknown_event_is_an_error_not_silence(self):
        game, _ = table3()
        permanent = Permanent(BEAR)
        game.seats[0].battlefield = [permanent]
        with self.assertRaises(ValueError):
            game.trigger("drwa", permanent, game.seats[0])
        game.trigger("chapter_2", permanent, game.seats[0])  # a saga chapter is not declared one by one


class DeclaringTests(unittest.TestCase):
    def test_a_new_event_for_an_occurrence_the_game_already_announces(self):
        event, forget = declared("draw_a_pair", r"Whenever you draw a pair of cards, (.+)", to="you", happens="drew", needs="second")
        self.addCleanup(forget)
        card = watcher("Pair Watcher", "Whenever you draw a pair of cards, you gain 3 life.")
        self.assertEqual(triggered_abilities(card)[0].event, "draw_a_pair")
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(card)]
        game.draw(a, 1)
        settle(game)
        self.assertEqual(a.life, 40)
        game.draw(a, 1)  # the second card this turn
        settle(game)
        self.assertEqual(a.life, 43)

    def test_an_event_for_opponents_hears_the_other_players(self):
        event, forget = declared("rival_draws_pair", r"Whenever an opponent draws a pair, (.+)", to="opponents", happens="drew", needs="second")
        self.addCleanup(forget)
        card = watcher("Rival Watcher", "Whenever an opponent draws a pair, you gain 2 life.")
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(card)]
        game.draw(a, 2)  # their own draws do not count
        settle(game)
        self.assertEqual(a.life, 40)
        game.draw(b, 2)
        settle(game)
        self.assertEqual(a.life, 42)
        self.assertEqual(triggered_abilities(card)[0].event, "rival_draws_pair")

    def test_declaring_does_not_listen_for_a_direct_event(self):
        event, forget = declared("somewhere_else", r"Whenever somewhere else, (.+)")
        self.addCleanup(forget)
        self.assertEqual(event.to, "direct")
        self.assertEqual(event.happens, ("somewhere_else",))
        self.assertEqual(heard_on("somewhere_else"), ())


class OccurrenceTests(unittest.TestCase):
    def test_a_draw_in_the_draw_step_is_not_an_extra_draw(self):
        card = watcher("Bowmaster", "Whenever an opponent draws a card except the first one they draw in each of their draw steps, you gain 1 life.")
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(card)]
        game._draw_step_draw = True
        game.draw(b, 1)
        game._draw_step_draw = False
        settle(game)
        self.assertEqual(a.life, 40)
        game.draw(b, 1)
        settle(game)
        self.assertEqual(a.life, 41)

    def test_the_first_gain_of_the_turn_is_reported_once(self):
        first = watcher("First Watcher", "Whenever you gain life for the first time each turn, draw a card.")
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(first)]
        before = len(a.hand)
        game.change_life(a, 3)
        game.change_life(a, 2)
        settle(game)
        self.assertEqual(len(a.hand) - before, 1)  # only the first gain this turn
        game.turn += 1
        game.change_life(a, 1)
        settle(game)
        self.assertEqual(len(a.hand) - before, 2)

    def test_losing_life_sets_off_your_loss_events_and_the_opponents_not_each_others(self):
        own = watcher("Own Loss", "Whenever you lose life, you gain 5 life.")
        lose = watcher("Opponent Loss", "Whenever an opponent loses life, you gain 1 life.")
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(own), Permanent(lose)]
        game.change_life(a, -3)  # "an opponent loses life" is not about you
        settle(game)
        self.assertEqual(a.life, 42)
        game.change_life(b, -3)  # and "you lose life" is not about them
        settle(game)
        self.assertEqual(a.life, 43)

    def test_discarding_sets_off_discard_cycle_or_discard_and_the_opponents_events(self):
        mine = watcher("Mine", "Whenever you discard a card, you gain 1 life.")
        either = watcher("Either", "Whenever you cycle or discard a card, you gain 10 life.")
        theirs = watcher("Theirs", "Whenever an opponent discards a card, you gain 100 life.")
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(mine), Permanent(either)]
        b.battlefield = [Permanent(theirs)]
        game._discarded(a, BEAR)
        settle(game)
        self.assertEqual((a.life, b.life), (51, 140))

    def test_cycling_sets_off_cycle_and_cycle_or_discard_but_not_discard(self):
        mine = watcher("Mine", "Whenever you discard a card, you gain 1 life.")
        either = watcher("Either", "Whenever you cycle or discard a card, you gain 10 life.")
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(mine), Permanent(either)]
        game.happened("cycled", a)
        settle(game)
        self.assertEqual(a.life, 50)


if __name__ == "__main__":
    unittest.main()
