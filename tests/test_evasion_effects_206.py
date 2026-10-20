"""More of #206: Flanking, "All creatures able to block this creature do so", and the "can't be blocked / can't block this turn"
effects, each from the card's own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import CANT_BE_BLOCKED, CANT_BLOCK, overloaded_effects
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import attack_all, lands, pick, run_stack, table


def creature(name, text="", power=2, toughness=2, colors=()):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Bear", oracle_text=text, power=str(power),
                toughness=str(toughness), colors=colors)


FLANKING = "Flanking (Whenever a creature without flanking blocks this creature, the blocking creature gets -1/-1 until end of turn.)"
LAST = lambda prompt, options: len(options) - 1  # noqa: E731
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))


def blocks(attackers, blockers):
    """Declare attackers and blockers (each blocker takes the last block it is offered); returns the game, the blockers
    of each attack by name, and the defender's seat."""
    game, _, _ = table(attack_all, LAST)
    a, b = game.seats
    a.battlefield = [Permanent(c) for c in attackers]
    b.battlefield = [Permanent(c) for c in blockers]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    return game, [[p.card.name for p in attack.blockers] for attack in game.combat.attacks], b


class FlankingTests(unittest.TestCase):
    def test_a_blocker_without_flanking_gets_minus_one_minus_one(self):
        game, blockers, b = blocks([creature("Cavalry", FLANKING, 2, 2)], [creature("Bear", "", 2, 2)])
        self.assertEqual(blockers, [["Bear"]])
        bear = b.battlefield[0]
        self.assertEqual((game.power(bear), game.toughness(bear)), (1, 1))

    def test_a_blocker_with_flanking_is_not_affected(self):
        game, blockers, b = blocks([creature("Cavalry", FLANKING, 2, 2)], [creature("Rival", FLANKING, 2, 2)])
        rival = b.battlefield[0]
        self.assertEqual((game.power(rival), game.toughness(rival)), (2, 2))

    def test_every_blocker_gets_it(self):
        game, blockers, b = blocks([creature("Cavalry", FLANKING, 2, 2)], [creature("A"), creature("B")])
        self.assertEqual([game.toughness(p) for p in b.battlefield], [1, 1])

    def test_a_creature_without_flanking_does_nothing(self):
        game, blockers, b = blocks([creature("Plain")], [creature("Bear")])
        self.assertEqual(game.toughness(b.battlefield[0]), 2)

    def test_an_unblocked_flanker_changes_nothing(self):
        game, blockers, b = blocks([creature("Cavalry", FLANKING)], [])
        self.assertEqual(blockers, [[]])


class AllMustBlockTests(unittest.TestCase):
    BREAKER = creature("Breaker of Armies", "All creatures able to block this creature do so.", 10, 10)

    def test_every_creature_able_to_block_it_does(self):
        game, blockers, b = blocks([self.BREAKER, creature("Plain")], [creature("A"), creature("B")])
        self.assertEqual(blockers[0], ["A", "B"])
        self.assertEqual(blockers[1], [])  # they were not free to block the other attacker

    def test_a_creature_that_cannot_block_it_is_not_forced(self):
        flyer = creature("Flying Breaker", "Flying\nAll creatures able to block this creature do so.", 5, 5)
        game, blockers, b = blocks([flyer], [creature("A"), creature("Bird", "Flying")])
        self.assertEqual(blockers, [["Bird"]])

    def test_a_tapped_creature_is_not_forced(self):
        a_tapped = Permanent(creature("Tapped"))
        game, _, _ = table(attack_all, LAST)
        a, b = game.seats
        a.battlefield = [Permanent(self.BREAKER)]
        a_tapped.tapped = True
        b.battlefield = [a_tapped, Permanent(creature("Free"))]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        self.assertEqual([p.card.name for p in game.combat.attacks[0].blockers], ["Free"])


class CantBeBlockedThisTurnTests(unittest.TestCase):
    SABOTEUR = creature("Daring Saboteur", "{2}{U}: This creature can't be blocked this turn.")
    SOWER = creature("Sower of Chaos", "{2}{R}: Target creature can't block this turn.")
    MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))

    def test_it_makes_itself_unblockable(self):
        game, _, _ = table(pick(ACTIVATE))
        a, b = game.seats
        a.battlefield = [Permanent(self.SABOTEUR)] + [Permanent(ISLAND) for _ in range(3)]
        game._priority_round(a)
        saboteur = a.battlefield[0]
        self.assertTrue(game.has_keyword(saboteur, CANT_BE_BLOCKED))
        b.battlefield = [Permanent(creature("Bear"))]
        game.combat.attacks = []
        self.assertFalse(game.combat._can_block(b.battlefield[0], saboteur))

    def test_it_stops_a_target_creature_blocking(self):
        game, _, _ = table(pick(ACTIVATE, "Bear"))
        a, b = game.seats
        a.battlefield = [Permanent(self.SOWER)] + [Permanent(self.MOUNTAIN) for _ in range(3)]
        b.battlefield = [Permanent(creature("Bear"))]
        game._priority_round(a)
        self.assertTrue(game.has_keyword(b.battlefield[0], CANT_BLOCK))

    def test_it_wears_off_at_end_of_turn(self):
        game, _, _ = table(pick(ACTIVATE, "Bear"))
        a, b = game.seats
        a.battlefield = [Permanent(self.SOWER)] + [Permanent(self.MOUNTAIN) for _ in range(3)]
        b.battlefield = [Permanent(creature("Bear"))]
        game._priority_round(a)
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertFalse(game.has_keyword(b.battlefield[0], CANT_BLOCK))


class OverloadTests(unittest.TestCase):
    def test_a_capitalized_target_becomes_each_for_overload(self):
        card = Card(name="Round", mana_cost="{1}{U}", type_line="Sorcery",
                    oracle_text="Target player draws a card.\nOverload {2}{U}")
        effects = overloaded_effects(card)
        self.assertEqual(type(effects[0]).__name__, "EachDraw")  # every player, not one target


class ReportTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for text in (FLANKING, "Flanking", "All creatures able to block this creature do so.",
                     "{2}{U}: This creature can't be blocked this turn.", "{2}{R}: Target creature can't block this turn.",
                     "When this creature enters, target creature can't block this turn."):
            with self.subTest(text):
                self.assertEqual(unsupported_lines(creature("Test", text)), [])


if __name__ == "__main__":
    unittest.main()
