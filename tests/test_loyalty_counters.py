import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, Permanent
from tests.helpers import BEAR, pick, table

# Ajani, Caller of the Pride's real +1 (the rest of the card is not yet understood, so the walker here carries only this line)
AJANI_PLUS = "+1: Put a +1/+1 counter on up to one target creature."
WALKER = Card(name="Ajani Stand-in", mana_cost="{1}{W}{W}", type_line="Legendary Planeswalker — Ajani", loyalty="4", oracle_text=AJANI_PLUS)


class UpToOneCounterTests(unittest.TestCase):
    def test_the_counter_goes_on_the_chosen_creature(self):
        game, _, _ = table(pick(ACTIVATE + "Ajani Stand-in", "Bear"))
        seat = game.seats[0]
        walker = Permanent(WALKER, loyalty=4)
        bear = Permanent(BEAR)
        seat.battlefield = [walker, bear]
        game._priority_round(seat)
        self.assertEqual((walker.loyalty, bear.counters), (5, {"+1/+1": 1}))

    def test_with_no_creature_to_choose_it_still_resolves(self):
        game, _, _ = table(pick(ACTIVATE + "Ajani Stand-in"))
        seat = game.seats[0]
        walker = Permanent(WALKER, loyalty=4)
        seat.battlefield = [walker]  # "up to one": no creature anywhere is a legal choice
        game._priority_round(seat)
        self.assertEqual(walker.loyalty, 5)


if __name__ == "__main__":
    unittest.main()
