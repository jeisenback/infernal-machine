"""Real cards the Oracle text audit found unsupported (issue #97)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import mana_ability, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_lands import spell
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_real_oracle import REAL

LOTUS, EDGAR = REAL["Gilded Lotus"], REAL["Edgar Markov"]
VAMPIRE = Card(name="Bat", mana_cost="{B}", type_line="Creature — Vampire", power="1", toughness="1")


class GildedLotusTests(unittest.TestCase):
    def test_it_makes_three_mana_of_any_color(self):
        self.assertEqual(mana_ability(LOTUS, frozenset()), [frozenset("WUBRG")] * 3)
        self.assertEqual(unsupported_lines(LOTUS), [])

    def test_it_pays_for_a_three_mana_spell(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(LOTUS)]
        self.assertIsNotNone(game._payment(a, spell("{2}{R}")))
        self.assertIsNone(game._payment(a, spell("{3}{R}")))


class EminenceTests(unittest.TestCase):
    def test_edgar_is_understood(self):
        self.assertEqual(unsupported_lines(EDGAR), [])
        [eminence] = [t for t in triggered_abilities(EDGAR) if t.text.startswith("Eminence")]
        self.assertEqual((eminence.event, eminence.watch.kind, eminence.watch.other), ("cast", "vampire spell", True))

    def cast(self, game, seat, card):
        seat.cast_log.append((game.turn, card))
        game._observe("cast", card, seat)
        run_stack(game)

    def test_it_triggers_from_the_command_zone(self):
        game, _ = table3()
        a = game.seats[0]
        a.command_zone = [EDGAR]
        self.cast(game, a, VAMPIRE)
        self.assertEqual(len(a.battlefield), 1)
        self.assertEqual(a.battlefield[0].card.name, "Vampire")

    def test_it_triggers_from_the_battlefield(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(EDGAR)]
        self.cast(game, a, VAMPIRE)
        self.assertEqual(len(a.battlefield), 2)

    def test_it_ignores_other_spells_other_players_and_other_zones(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.command_zone = [EDGAR]
        self.cast(game, a, BEAR)  # not a Vampire
        self.cast(game, b, VAMPIRE)  # not your spell
        self.assertEqual(a.battlefield + b.battlefield, [])
        a.command_zone, a.hand = [], [EDGAR]
        self.cast(game, a, VAMPIRE)  # Edgar in hand does nothing
        self.assertEqual(a.battlefield, [])

    def test_casting_edgar_himself_does_not_trigger_it(self):
        game, _ = table3()
        a = game.seats[0]
        a.command_zone = [EDGAR]
        self.cast(game, a, EDGAR)
        self.assertEqual(a.battlefield, [])

    def test_other_cards_ignore_the_command_zone(self):
        game, _ = table3()
        a = game.seats[0]
        draw = Card(name="Watcher", type_line="Creature — Wizard",
                    oracle_text="Whenever you cast an instant or sorcery spell, draw a card.")
        a.command_zone, a.library = [draw], [BEAR] * 3
        self.cast(game, a, Card(name="Bolt", type_line="Instant", oracle_text="Draw a card."))
        self.assertEqual(a.hand, [])


class CountersOnEachTypeTests(unittest.TestCase):
    def test_edgar_puts_counters_on_each_vampire_only(self):
        game, _ = table3()
        a = game.seats[0]
        bat, bear = Permanent(VAMPIRE), Permanent(BEAR)
        a.battlefield = [Permanent(EDGAR), bat, bear]
        [attack] = [t for t in triggered_abilities(EDGAR) if t.event == "attacks"]
        attack.effects[0].resolve(game, a, None)
        self.assertEqual((bat.counters, bear.counters), ({"+1/+1": 1}, {}))
        self.assertEqual(a.battlefield[0].counters, {"+1/+1": 1})  # Edgar is a Vampire too
