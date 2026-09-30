import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Damage, Draw, GainLife, triggered_abilities
from infernal_machine.game import CAST, Permanent
from tests.test_combat import BEAR, attack_all, creature
from tests.test_effects import BOLT, COUNTERSPELL, RAINBOW, lands, pick, table

MULLDRIFTER = Card(name="Mulldrifter", mana_cost="{4}{U}", type_line="Creature — Elemental", power="2",
                   toughness="2", oracle_text="Flying\nWhen Mulldrifter enters, draw two cards.")
MAYBE = Card(name="Maybe Elf", mana_cost="{G}", type_line="Creature — Elf", power="1", toughness="1",
             oracle_text="When this creature enters, you may draw a card.")
PINGER = Card(name="Flametongue", mana_cost="{R}", type_line="Creature — Kavu", power="4", toughness="2",
              oracle_text="When this creature enters, it deals 4 damage to target creature.")
MARTYR = Card(name="Martyr", mana_cost="{W}", type_line="Creature — Human", power="1", toughness="1",
              oracle_text="When Martyr dies, you gain 3 life.")
RAIDER = creature("Raider", 2, 2, "Whenever this creature attacks, each opponent loses 1 life.")
NINJA = creature("Ninja", 1, 1, "Whenever this creature deals combat damage to a player, draw a card.")
FARMER = Card(name="Farmer", mana_cost="{1}", type_line="Artifact",
              oracle_text="At the beginning of your upkeep, you gain 1 life.\nAt the beginning of your end step, draw a card.")
OMNATH = Card(name="Omnath, Locus of Rage", mana_cost="{G}", type_line="Legendary Creature — Elemental",
              power="5", toughness="5", oracle_text="When Omnath enters, draw a card.")


class ParseTests(unittest.TestCase):
    def test_events_and_effects(self):
        [etb] = triggered_abilities(MULLDRIFTER)
        self.assertEqual((etb.event, etb.effects, etb.optional), ("enters", (Draw(2),), False))
        self.assertTrue(triggered_abilities(MAYBE)[0].optional)
        self.assertEqual(triggered_abilities(PINGER)[0].effects, (Damage(4, "creature"),))
        self.assertEqual(triggered_abilities(MARTYR)[0].event, "dies")
        self.assertEqual([a.event for a in triggered_abilities(FARMER)], ["upkeep", "end_step"])
        self.assertEqual(triggered_abilities(OMNATH)[0].effects, (Draw(1),))  # short legendary name

    def test_unsupported_effects_are_left_out(self):
        card = Card(name="x", oracle_text="When this creature enters, scry 2.")
        self.assertEqual(triggered_abilities(card), ())


class TriggerTests(unittest.TestCase):
    def test_enters_trigger_uses_the_stack(self):
        game, a, _ = table(pick(CAST))
        game.seats[0].hand = [MULLDRIFTER]
        game.seats[0].battlefield = lands(5)
        game._priority_round(game.seats[0])
        self.assertEqual(len(game.seats[0].hand), 2)
        order = [e["event"] for e in a.events if e["event"] in ("cast", "resolve", "trigger")]
        self.assertEqual(order, ["cast", "resolve", "trigger", "resolve"])

    def test_opponents_can_respond_to_a_trigger(self):
        # B answers Flametongue's trigger by bolting its target first; the trigger then fizzles.
        game, a, b = table(pick(CAST, "Grizzly"))
        respond = pick(CAST, "Grizzly")
        b.policy = lambda prompt, options: (respond(prompt, options)
                                            if any(item.ability for item in game.stack) or prompt.startswith("Choose")
                                            else options.index("Pass"))
        game.seats[0].hand = [PINGER]
        game.seats[0].battlefield = lands(1)
        grizzly = Card(name="Grizzly", mana_cost="{1}", type_line="Creature — Bear", power="2", toughness="2")
        game.seats[1].battlefield = lands(1) + [Permanent(grizzly)]
        game.seats[1].hand = [BOLT]
        game._priority_round(game.seats[0])
        events = [e["event"] for e in a.events if e["event"] in ("trigger", "resolve", "fizzle")]
        self.assertEqual(events, ["resolve", "trigger", "resolve", "fizzle"])

    def test_trigger_with_no_legal_target_is_removed(self):
        game, a, _ = table(pick(CAST))
        game.seats[0].hand = [PINGER]
        game.seats[0].battlefield = lands(1)
        game._priority_round(game.seats[0])
        # Flametongue itself is the only creature, so it must target itself.
        self.assertEqual(game.seats[0].graveyard, [PINGER])

    def test_optional_trigger(self):
        game, a, _ = table(pick(CAST, "No"))
        game.seats[0].hand = [MAYBE]
        game.seats[0].battlefield = lands(1)
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].hand, [])
        self.assertTrue(any(e.get("declined") for e in a.events))

    def test_dies_trigger(self):
        game, _, _ = table(pick(CAST, "Martyr"))
        game.seats[0].hand = [BOLT]
        game.seats[0].battlefield = lands(1) + [Permanent(MARTYR)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].life, 43)

    def test_attack_and_combat_damage_triggers(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(RAIDER), Permanent(NINJA)]
        game.turn = 3
        game._take_turn(a)
        self.assertEqual(b.life, 40 - 1 - 2 - 1)
        self.assertEqual(len(a.hand), 1 + 1)  # draw step + Ninja trigger

    def test_upkeep_and_end_step_triggers(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(FARMER)]
        game.turn = 3
        game._take_turn(a)
        self.assertEqual(a.life, 41)
        self.assertEqual(len(a.hand), 2)  # draw step + end step trigger

    def test_active_players_triggers_resolve_last(self):
        game, a, _ = table()
        game.seats[0].battlefield = [Permanent(MARTYR)]
        game.seats[1].battlefield = [Permanent(MARTYR)]
        game.trigger("dies", Permanent(MARTYR), game.seats[0])
        game.trigger("dies", Permanent(MARTYR), game.seats[1])
        game._put_triggers_on_stack()
        self.assertEqual([item.controller.index for item in game.stack], [0, 1])

    def test_counterspell_cannot_target_abilities(self):
        game, _, _ = table()
        a, b = game.seats
        game.trigger("dies", Permanent(MARTYR), a)
        game._put_triggers_on_stack()
        b.hand = [COUNTERSPELL]
        b.battlefield = lands(2)
        self.assertEqual(game.target_options("spell", b), [])


if __name__ == "__main__":
    unittest.main()
