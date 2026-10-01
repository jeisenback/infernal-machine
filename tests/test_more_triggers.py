import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Draw, GainLife, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, creature
from tests.test_effects import table

DRYAD = Card(name="Dryad", mana_cost="{G}", type_line="Enchantment",
             oracle_text="At the beginning of each upkeep, you gain 1 life.")
WATCHMAN = Card(name="Watchman", mana_cost="{W}", type_line="Enchantment",
                oracle_text="At the beginning of each end step, you gain 1 life.")
DRUMMER = Card(name="Drummer", mana_cost="{R}", type_line="Enchantment",
               oracle_text="At the beginning of combat on your turn, you gain 1 life.")
DINA = Card(name="Dina, Soul Steeper", mana_cost="{B}{G}", type_line="Legendary Creature — Dryad Druid",
            power="1", toughness="3", oracle_text="Whenever you gain life, each opponent loses 1 life.")
MOURNER = Card(name="Mourner", mana_cost="{B}", type_line="Enchantment",
               oracle_text="Whenever you lose life, draw a card.")
ABOMINATION = creature("Abomination", 4, 3, "Whenever you sacrifice a creature, draw a card.")
HARNESS = Card(name="Harness", mana_cost="{1}", type_line="Artifact — Equipment",
               oracle_text="When this Equipment enters, draw a card.\nEquip {1}")
TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure",
                oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")


def resolve_triggers(game, seat):
    game._priority_round(seat)


class ParseTests(unittest.TestCase):
    def test_new_events(self):
        cases = {DRYAD: "each_upkeep", WATCHMAN: "each_end_step", DRUMMER: "combat", DINA: "gain_life",
                 MOURNER: "lose_life", ABOMINATION: "sacrifice_creature"}
        for card, event in cases.items():
            [ability] = triggered_abilities(card)
            self.assertEqual(ability.event, event, card.name)
        self.assertEqual(triggered_abilities(DRYAD)[0].effects, (GainLife(1),))

    def test_aura_equipment_and_class_call_themselves_this(self):
        [ability] = triggered_abilities(HARNESS)
        self.assertEqual((ability.event, ability.effects), ("enters", (Draw(1),)))
        for kind in ("Aura", "Class", "Vehicle", "Saga"):
            card = Card(name="x", oracle_text=f"When this {kind} enters, draw a card.")
            self.assertEqual(triggered_abilities(card)[0].event, "enters", kind)

    def test_report_accepts_them(self):
        for card in (DRYAD, WATCHMAN, DRUMMER, DINA, MOURNER, ABOMINATION):
            self.assertEqual(unsupported_lines(card), [], card.name)


class TimingTests(unittest.TestCase):
    def test_each_upkeep_triggers_on_every_players_turn(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DRYAD)]
        game.turn = 3
        game._take_turn(b)
        self.assertEqual(a.life, 41)
        game._take_turn(a)
        self.assertEqual(a.life, 42)

    def test_each_end_step_triggers_on_every_players_turn(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(WATCHMAN)]
        game.turn = 3
        game._take_turn(b)
        self.assertEqual(a.life, 41)

    def test_beginning_of_combat_only_on_your_turn(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DRUMMER)]
        game.turn = 3
        game._take_turn(b)
        self.assertEqual(a.life, 40)
        game._take_turn(a)
        self.assertEqual(a.life, 41)


class PlayerEventTests(unittest.TestCase):
    def test_gaining_life_triggers(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DINA)]
        game.change_life(a, 3)
        resolve_triggers(game, a)
        self.assertEqual(b.life, 39)  # once per life-gain event, not per point

    def test_losing_life_or_an_opponent_gaining_doesnt_trigger_gain(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DINA)]
        game.change_life(a, -3)
        game.change_life(b, 3)
        resolve_triggers(game, a)
        self.assertEqual(b.life, 43)

    def test_losing_life_triggers(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(MOURNER)]
        a.library = [BEAR, BEAR]
        game.change_life(a, -2)
        game.change_life(a, 0)
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [BEAR])

    def test_sacrificing_a_creature_triggers(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(ABOMINATION), Permanent(BEAR)]
        a.library = [BEAR, BEAR]
        game.sacrifice(a)
        resolve_triggers(game, a)
        self.assertEqual(len(a.hand), 1)

    def test_sacrificing_the_watcher_itself_triggers(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(ABOMINATION)]
        a.library = [BEAR]
        game.sacrifice(a)
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [BEAR])  # it looks back in time (CR 603.10a)

    def test_destroying_or_sacrificing_a_noncreature_doesnt_trigger(self):
        game, _, _ = table()
        a = game.seats[0]
        bear, treasure = Permanent(BEAR), Permanent(TREASURE)
        a.battlefield = [Permanent(ABOMINATION), bear, treasure]
        a.library = [BEAR]
        game.destroy(bear)
        game._leave_battlefield(treasure, "sacrificed")
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [])

    def test_opponents_sacrifice_doesnt_trigger(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(ABOMINATION)]
        b.battlefield = [Permanent(BEAR)]
        a.library = [BEAR]
        game.sacrifice(b)
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
