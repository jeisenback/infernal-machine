import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import triggered_abilities
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, creature, fight
from tests.test_effects import DIVINATION, FOREST, lands, pick, table


def watcher(name, text, kind="Enchantment"):
    return Card(name=name, mana_cost="{1}", type_line=kind, oracle_text=text)


def settle(game):
    """Let queued triggers go on the stack and resolve."""
    game._priority_round(game.seats[0])


def attack_with_everything(prompt, options):
    return 1 if options[0] == "Don't attack" else 0


class SeveralEventTests(unittest.TestCase):
    def test_enters_or_dies_is_two_abilities(self):
        card = creature("Hopper", 1, 1, "When this creature enters or dies, you gain 2 life.")
        self.assertEqual([a.event for a in triggered_abilities(card)], ["enters", "dies"])
        self.assertEqual(unsupported_lines(card), [])

    def test_enters_or_dies_both_fire(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        hopper = creature("Hopper", 1, 1, "When this creature enters or dies, you gain 2 life.")
        seat.hand = [hopper]
        seat.battlefield = lands(1, FOREST)
        settle(game)
        self.assertEqual(seat.life, 42)
        game._leave_battlefield(next(p for p in seat.battlefield if p.card is hopper), "dies")
        settle(game)
        self.assertEqual(seat.life, 44)

    def test_attacks_or_blocks(self):
        card = creature("Guard", 2, 2, "Whenever this creature attacks or blocks, you gain 1 life.")
        self.assertEqual([a.event for a in triggered_abilities(card)], ["attacks", "blocks"])

    def test_an_unlisted_event_in_the_list_is_unsupported(self):
        card = creature("Odd", 2, 2, "Whenever this creature attacks or becomes tapped, you gain 1 life.")
        self.assertEqual(len(unsupported_lines(card)), 1)


class CombatTests(unittest.TestCase):
    def test_blocks(self):
        guard = creature("Guard", 2, 3, "Whenever this creature blocks, you gain 2 life.")
        game, _, b = fight([BEAR], [guard])
        settle(game)
        self.assertEqual(b.life, 42)

    def test_a_creature_that_does_not_block_does_not_trigger(self):
        guard = creature("Guard", 2, 3, "Whenever this creature blocks, you gain 2 life.")
        game, _, b = fight([BEAR], [guard], blocker_policy=lambda prompt, options: 0)
        settle(game)
        self.assertEqual(b.life, 38)  # took the damage, gained nothing

    def test_a_creature_you_control_attacks(self):
        horn = watcher("Horn", "Whenever a creature you control attacks, you gain 1 life.")
        game, _, _ = table(attack_with_everything)
        a = game.seats[0]
        a.battlefield = [Permanent(horn), Permanent(BEAR), Permanent(BEAR)]
        game.combat.declare_attackers(a)
        settle(game)
        self.assertEqual(a.life, 42)

    def test_the_opponents_attackers_dont_count(self):
        horn = watcher("Horn", "Whenever a creature you control attacks, you gain 1 life.")
        game, _, _ = table(attack_with_everything)
        a, b = game.seats
        a.battlefield = [Permanent(BEAR)]
        b.battlefield = [Permanent(horn)]
        game.combat.declare_attackers(a)
        settle(game)
        self.assertEqual(b.life, 40)


class DrawAndLifeTests(unittest.TestCase):
    def test_you_draw_a_card(self):
        owl = watcher("Owl", "Whenever you draw a card, you gain 1 life.")
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.battlefield = [Permanent(owl)] + lands(3, Card(name="Island", type_line="Basic Land", produced_mana=("U",)))
        seat.hand = [DIVINATION]
        settle(game)
        self.assertEqual(seat.life, 42)  # one per card drawn

    def test_the_opening_hand_does_not_trigger(self):
        owl = watcher("Owl", "Whenever you draw a card, you gain 1 life.")
        game, _, _ = table()
        game.seats[0].battlefield = [Permanent(owl)]
        game.draw(game.seats[0], 3, announce=False)
        self.assertEqual(game.pending, [])

    def test_an_opponent_draws_a_card(self):
        owl = watcher("Owl", "Whenever an opponent draws a card, you gain 1 life.")
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(owl)]
        game.draw(b, 2)
        game.draw(a, 1)  # your own draws don't count
        settle(game)
        self.assertEqual(a.life, 42)

    def test_an_opponent_gains_life(self):
        taker = watcher("Taker", "Whenever an opponent gains life, you gain 1 life.")
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(taker)]
        game.change_life(b, 4)
        game.change_life(b, -2)  # losing life doesn't count
        game.change_life(a, 3)  # neither does your own gain
        settle(game)
        self.assertEqual(a.life, 44)


class ItTests(unittest.TestCase):
    def test_it_is_the_creature_that_entered(self):
        crusade = watcher("Crusade", "Whenever another creature you control enters, put a +1/+1 counter on it.")
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        source = Permanent(crusade)
        seat.battlefield = [source] + lands(1, FOREST)
        seat.hand = [BEAR]
        settle(game)
        bear = next(p for p in seat.battlefield if p.card is BEAR)
        self.assertEqual(bear.counters, {"+1/+1": 1})
        self.assertEqual(source.counters, {})

    def test_that_creature(self):
        card = watcher("Blessing", "Whenever another creature enters, put a +1/+1 counter on that creature.")
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.battlefield = [Permanent(card)] + lands(1, FOREST)
        seat.hand = [BEAR]
        settle(game)
        bear = next(p for p in seat.battlefield if p.card is BEAR)
        self.assertEqual(bear.counters, {"+1/+1": 1})

    def test_it_mixed_with_other_effects_is_unsupported(self):
        card = watcher("Odd", "Whenever another creature enters, draw a card. Put a +1/+1 counter on it.")
        self.assertEqual(len(unsupported_lines(card)), 1)


class ReportTests(unittest.TestCase):
    def test_supported(self):
        for text in ("Whenever you draw a card, you gain 1 life.",
                     "Whenever an opponent draws a card, you gain 1 life.",
                     "Whenever an opponent gains life, you gain 1 life.",
                     "Whenever a creature you control attacks, draw a card.",
                     "Whenever this creature blocks, draw a card."):
            self.assertEqual(unsupported_lines(watcher("W", text)), [], text)

    def test_still_unsupported(self):
        for text in ("Whenever you draw your third card each turn, draw a card.",
                     "Whenever a creature you control attacks, it and target creature gain flying."):
            self.assertEqual(unsupported_lines(watcher("W", text)), [text], text)


if __name__ == "__main__":
    unittest.main()
