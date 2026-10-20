"""Buyback (#216), played from the cards' own Oracle text."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BIG, FOREST, PLAINS, real, run_stack, Table
from infernal_machine.cards import Card

SWAMP = Card(name="Swamp", type_line="Basic Land \u2014 Swamp", produced_mana=("B",))

REMINDER = "(You may pay an additional {cost} as you cast this spell. If you do, put this card into your hand as it resolves.)"
WHISPERS = real("Whispers of the Muse", "{U}", "Instant", "Buyback {5} " + REMINDER.format(cost="{5}") + "\nDraw a card.")
BRUSH = real("Brush with Death", "{2}{B}", "Sorcery", "Buyback {2}{B}{B} " + REMINDER.format(cost="{2}{B}{B}")
             + "\nTarget opponent loses 2 life. You gain 2 life.")
SLAUGHTER = real("Slaughter", "{2}{B}{B}", "Instant", "Buyback—Pay 4 life. (You may pay 4 life in addition to any other costs as "
                 "you cast this spell. If you do, put this card into your hand as it resolves.)\n"
                 "Destroy target nonblack creature. It can't be regenerated.")
REWARDS = real("Reaping the Rewards", "{W}", "Instant", "Buyback\u2014Sacrifice a land. (You may sacrifice a land in addition to any "
               "other costs as you cast this spell. If you do, put this card into your hand as it resolves.)\nYou gain 2 life.")
COLLUSION = real("Demonic Collusion", "{3}{B}{B}", "Sorcery", "Buyback—Discard two cards. (You may discard two cards in addition "
                 "to any other costs as you cast this spell. If you do, put this card into your hand as it resolves.)\n"
                 "Search your library for a card, put it into your hand, then shuffle.")


def yes(prompt, options):
    return options.index("Yes") if "Yes" in options else 0


def no(prompt, options):
    return options.index("No") if "No" in options else 0


class Asked:
    """A policy that answers the buyback question with `answer` and remembers whether it was asked."""

    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def __call__(self, prompt, options):
        if "buyback" in prompt:
            self.prompts.append(prompt)
            return self.answer(prompt, options)
        return 0


def tapped(seat):
    return sum(p.tapped for p in seat.battlefield)


class BuybackTests(unittest.TestCase):
    def test_the_lines_are_supported_except_the_costs_that_are_not_read(self):
        for card in (WHISPERS, BRUSH, SLAUGHTER, REWARDS):
            with self.subTest(card.name):
                self.assertEqual(unsupported_lines(card), [])
        self.assertEqual(unsupported_lines(COLLUSION), ["Buyback—Discard two cards."])

    def test_paid_it_returns_to_hand_as_it_resolves(self):
        asked = Asked(yes)
        t = Table(WHISPERS, n=6, library=[FOREST, BIG], policy=asked).cast()
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual(sorted(c.name for c in t.a.hand), ["Forest", "Whispers of the Muse"])  # drew one, bought back
        self.assertEqual(t.a.graveyard, [])
        self.assertEqual(tapped(t.a), 6)  # {U} and the additional {5}

    def test_declined_it_goes_to_the_graveyard(self):
        t = Table(WHISPERS, n=6, library=[FOREST, BIG], policy=Asked(no)).cast()
        self.assertEqual([c.name for c in t.a.hand], ["Forest"])
        self.assertEqual([c.name for c in t.a.graveyard], ["Whispers of the Muse"])
        self.assertEqual(tapped(t.a), 1)

    def test_it_is_not_offered_when_the_extra_cost_cannot_be_paid(self):
        asked = Asked(yes)
        t = Table(WHISPERS, n=5, policy=asked).cast()
        self.assertEqual(asked.prompts, [])
        self.assertEqual([c.name for c in t.a.graveyard], ["Whispers of the Muse"])

    def test_a_spell_without_buyback_never_asks(self):
        asked = Asked(yes)
        Table(real("Plain", "{U}", "Instant", "Draw a card."), n=6, policy=asked).cast()
        self.assertEqual(asked.prompts, [])

    def test_a_colored_buyback_cost_needs_that_color(self):
        asked = Asked(yes)
        Table(BRUSH, n=0, mine=[Permanent(SWAMP)] + [Permanent(FOREST) for _ in range(6)], policy=asked).cast()
        self.assertEqual(asked.prompts, [])  # {2}{B}{B} more, and only one black mana in all

    def test_buyback_with_a_mana_cost_and_a_second_target_free_effect(self):
        asked = Asked(yes)
        t = Table(BRUSH, n=7, policy=asked).cast()
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual([c.name for c in t.a.hand], ["Brush with Death"])
        self.assertEqual((t.a.life, t.b.life), (42, 38))

    def test_a_countered_spell_is_not_bought_back(self):
        t = Table(WHISPERS, n=6, library=[FOREST, BIG], policy=Asked(yes))
        t.game._perform(t.a, CAST + "Whispers of the Muse")
        t.game.counter(t.game.stack[-1])
        run_stack(t.game)
        self.assertEqual([c.name for c in t.a.graveyard], ["Whispers of the Muse"])
        self.assertEqual(t.a.hand, [])

    def test_a_fizzled_spell_is_not_bought_back_but_its_cost_stays_paid(self):
        t = Table(SLAUGHTER, n=4, theirs=[Permanent(BIG)], policy=Asked(yes))
        t.game._perform(t.a, CAST + "Slaughter")
        self.assertEqual(t.a.life, 36)  # 4 life paid to cast
        t.b.battlefield.clear()  # the target is gone as it resolves
        run_stack(t.game)
        self.assertEqual([c.name for c in t.a.graveyard], ["Slaughter"])
        self.assertEqual(t.a.hand, [])

    def test_pay_life_buyback_returns_it_when_it_resolves(self):
        t = Table(SLAUGHTER, n=4, theirs=[Permanent(BIG)], policy=Asked(yes)).cast()
        self.assertEqual(t.a.life, 36)
        self.assertEqual([c.name for c in t.a.hand], ["Slaughter"])
        self.assertEqual(t.b.battlefield, [])

    def test_pay_life_buyback_is_not_offered_without_the_life(self):
        asked = Asked(yes)
        t = Table(SLAUGHTER, n=4, theirs=[Permanent(BIG)], policy=asked)
        t.a.life = 3  # it cannot pay 4 life
        t.cast()
        self.assertEqual(asked.prompts, [])

    def test_sacrifice_a_land_buyback(self):
        asked = Asked(yes)
        t = Table(REWARDS, n=3, policy=asked).cast()
        self.assertEqual(len(t.a.battlefield), 2)  # one land sacrificed
        self.assertEqual([c.name for c in t.a.hand], ["Reaping the Rewards"])
        self.assertEqual(t.a.life, 42)

    def test_the_land_sacrificed_may_be_one_that_was_tapped_for_the_mana(self):
        asked = Asked(yes)
        t = Table(REWARDS, n=1, policy=asked).cast()
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual(t.a.battlefield, [])
        self.assertEqual([c.name for c in t.a.hand], ["Reaping the Rewards"])

    def test_sacrifice_a_land_buyback_is_not_offered_without_a_land_to_sacrifice(self):
        asked = Asked(yes)
        t = Table(REWARDS, n=0, policy=asked)
        t.a.mana_pool = [frozenset("W")]  # the spell is paid for from the pool: there is no land at all
        t.cast()
        self.assertEqual(asked.prompts, [])
        self.assertEqual([c.name for c in t.a.graveyard], ["Reaping the Rewards"])


if __name__ == "__main__":
    unittest.main()
