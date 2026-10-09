"""A token that dies is put into a graveyard from the battlefield, and abilities that watch for that trigger, before
the token ceases to exist (CR 111.7, 704.5d). Watchers that say "nontoken" still ignore it.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

GRAVE_TEXT = "put a +1/+1 counter on this creature."


def watcher(who, name="Watcher"):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Wizard", power="1", toughness="1",
                oracle_text=f"Whenever {who} you control is put into a graveyard from the battlefield, {GRAVE_TEXT}")


def token(name="Soldier", text=""):
    return Card(name=name, type_line="Token Creature — Soldier", power="1", toughness="1", oracle_text=text)


def kill(game, *permanents, destination="graveyard", reason="destroyed"):
    game._leave_together([(p, reason) for p in permanents], destination)
    run_stack(game)


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3()
        self.a, self.b, _ = self.game.seats

    def counters(self, card):
        watcher_permanent = Permanent(card)
        self.a.battlefield = [watcher_permanent]
        return watcher_permanent

    def test_the_lines_are_supported(self):
        for who in ("a creature", "a nontoken creature", "a creature token"):
            self.assertEqual(unsupported_lines(watcher(who)), [], who)

    def test_a_creature_watcher_sees_a_token_go(self):
        watching = self.counters(watcher("a creature"))
        dying = Permanent(token())
        self.a.battlefield.append(dying)
        kill(self.game, dying)
        self.assertEqual(watching.counters, {"+1/+1": 1})

    def test_a_creature_token_watcher_sees_it_too(self):
        watching = self.counters(watcher("a creature token"))
        dying = Permanent(token())
        self.a.battlefield.append(dying)
        kill(self.game, dying)
        self.assertEqual(watching.counters, {"+1/+1": 1})

    def test_a_nontoken_watcher_ignores_a_token(self):
        watching = self.counters(watcher("a nontoken creature"))
        dying = Permanent(token())
        self.a.battlefield.append(dying)
        kill(self.game, dying)
        self.assertEqual(watching.counters, {})

    def test_a_nontoken_watcher_still_sees_a_card(self):
        watching = self.counters(watcher("a nontoken creature"))
        dying = Permanent(BEAR)
        self.a.battlefield.append(dying)
        kill(self.game, dying)
        self.assertEqual(watching.counters, {"+1/+1": 1})

    def test_a_creature_token_watcher_ignores_a_card(self):
        watching = self.counters(watcher("a creature token"))
        dying = Permanent(BEAR)
        self.a.battlefield.append(dying)
        kill(self.game, dying)
        self.assertEqual(watching.counters, {})

    def test_an_opponents_token_does_not_count_for_you_control(self):
        watching = self.counters(watcher("a creature"))
        dying = Permanent(token())
        self.b.battlefield = [dying]
        kill(self.game, dying)
        self.assertEqual(watching.counters, {})

    def test_a_token_that_is_exiled_is_not_put_into_a_graveyard(self):
        watching = self.counters(watcher("a creature"))
        leaving = Permanent(token())
        self.a.battlefield.append(leaving)
        kill(self.game, leaving, destination="exile", reason="exiled")
        self.assertEqual(watching.counters, {})

    def test_the_token_is_still_gone_afterwards(self):
        self.counters(watcher("a creature"))
        dying = Permanent(token())
        self.a.battlefield.append(dying)
        kill(self.game, dying)
        self.assertEqual((self.a.graveyard, [p.card.name for p in self.a.battlefield]), ([], ["Watcher"]))


class OwnTriggerTests(unittest.TestCase):
    def test_a_token_with_its_own_graveyard_trigger_fires_it(self):
        game, _ = table3()
        a = game.seats[0]
        a.life = 20
        dying = Permanent(token("Martyr", "When this creature is put into a graveyard from the battlefield, you gain 3 life."))
        a.battlefield = [dying]
        kill(game, dying)
        self.assertEqual((a.life, a.graveyard), (23, []))


if __name__ == "__main__":
    unittest.main()
