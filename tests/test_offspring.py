"""Offspring: "You may pay an additional {M} as you cast this spell. If you do, when this creature enters, create a 1/1 token copy of it."
(CR 702.175a). Rust-Shield Rampager, Intrepid Rabbit and Agate Instigator."""

import unittest

from infernal_machine.game import KICKER_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import Table, creature, pick, real

TEXT = "Offspring {}(You may pay an additional {} as you cast this spell. If you do, when this creature enters, create a 1/1 token copy of it.)"
RAMPAGER = real("Rust-Shield Rampager", "{3}{G}", "Creature — Raccoon Warrior", TEXT.format("{2} ", "{2}") +
                "\nThis creature can't be blocked by creatures with power 2 or less.", "4", "4")
RABBIT = real("Intrepid Rabbit", "{2}{W}", "Creature — Rabbit Soldier", TEXT.format("{1} ", "{1}") +
              "\nWhen this creature enters, target creature you control gets +1/+1 until end of turn.", "3", "2")
INSTIGATOR = real("Agate Instigator", "{1}{R}", "Creature — Lizard Rogue", TEXT.format("{1}{R} ", "{1}{R}") +
                  "\nWhenever another creature you control enters, this creature deals 1 damage to each opponent.", "1", "3")
YES = pick("Yes")
NO = pick("No")


def creatures(seat):
    return [p for p in seat.battlefield if "Creature" in p.card.type_line]


def untapped_lands(seat):
    return sum(not p.tapped for p in seat.battlefield if "Land" in p.card.type_line)


class OffspringTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (RAMPAGER, RABBIT, INSTIGATOR):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_paid_makes_a_one_one_token_copy(self):
        t = Table(RAMPAGER, policy=YES, n=6).cast()
        original, token = creatures(t.a)
        self.assertEqual((original.card.power, original.card.toughness), ("4", "4"))
        self.assertTrue(token.card.type_line.startswith("Token"))
        self.assertEqual((token.card.name, token.card.power, token.card.toughness), ("Rust-Shield Rampager", "1", "1"))
        self.assertIn("can't be blocked by creatures with power 2 or less", token.card.oracle_text)
        self.assertEqual(untapped_lands(t.a), 0)  # {3}{G} and the offspring {2}

    def test_not_paid_makes_no_token(self):
        t = Table(RAMPAGER, policy=NO, n=6).cast()
        self.assertEqual(len(creatures(t.a)), 1)
        self.assertEqual(untapped_lands(t.a), 2)

    def test_the_token_is_not_offspring_too(self):
        t = Table(RAMPAGER, policy=YES, n=10).cast()
        self.assertEqual(len(creatures(t.a)), 2)  # not a chain of tokens

    def test_not_offered_when_the_extra_cost_cannot_be_paid(self):
        t = Table(RAMPAGER, policy=YES, n=5).cast()
        self.assertFalse(any(prompt.startswith(KICKER_PROMPT) for prompt, _ in t.game.seats[0].player.prompts))
        self.assertEqual(len(creatures(t.a)), 1)

    def test_the_cost_is_added_to_the_mana_cost(self):
        t = Table(INSTIGATOR, policy=YES, n=4).cast()
        self.assertEqual(len(creatures(t.a)), 2)
        self.assertEqual(untapped_lands(t.a), 0)

    def test_the_token_copy_enters_with_its_own_enters_trigger(self):
        t = Table(RABBIT, policy=YES, n=4, mine=[Permanent(creature("Bear", 2, 2))]).cast()
        self.assertEqual(len(creatures(t.a)), 3)
        self.assertEqual(sorted(p.card.name for p in creatures(t.a)), ["Bear", "Intrepid Rabbit", "Intrepid Rabbit"])

    def test_the_original_triggers_for_its_token(self):
        t = Table(INSTIGATOR, policy=YES, n=4).cast()
        self.assertEqual(t.b.life, t.c.life)
        self.assertEqual(t.b.life, 40 - 1)  # the token entered after the Instigator: "another creature you control enters"


if __name__ == "__main__":
    unittest.main()
