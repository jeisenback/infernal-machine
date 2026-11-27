"""Training (CR 702.149): "Whenever this creature attacks with another creature with greater power, put a +1/+1 counter on this
creature.", from the cards' real Oracle text. All four cards whose only gap it was are fully playable. Gryff Rider (2/1) attacking with
an Ogre (3/3) gets a counter; with a Bear (2/2, the same power) or alone it doesn't. Torens, Fist of the Angels' Human Soldier token
"with training" (1/1) attacking with a Bear gets one too, and the Bear (the greater power) does not."""

import unittest

from infernal_machine.combat import ATTACK_PROMPT
from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, OGRE, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Apprentice Sharpshooter", "Gryff Rider", "Rural Recruit", "Torens, Fist of the Angels"]
RIDER, TORENS = REAL["Gryff Rider"], REAL["Torens, Fist of the Angels"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_training).
MUTATIONS = [
    ("infernal_machine/combat.py", "if any(power > powers[i] for j, power in enumerate(powers) if j != i):",
     "if any(power >= powers[i] for j, power in enumerate(powers) if j != i):", "greater, not equal"),
    ("infernal_machine/combat.py", "if any(power > powers[i] for j, power in enumerate(powers) if j != i):",
     "if True:", "only with a greater one"),
]


def attack(game, seat, attackers):
    """`seat` attacks seat 1 with every creature in `attackers` (sick=False)."""
    seat.battlefield += attackers
    game.combat.declare_attackers(seat)
    run_stack(game)


def attack_seat_1(prompt, options):
    return 1 if ATTACK_PROMPT.matches(prompt) else 0


class TrainingTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def counters(self, *others):
        game, _ = table3(attack_seat_1)
        rider = Permanent(RIDER, sick=False)
        attack(game, game.seats[0], [rider] + [Permanent(c, sick=False) for c in others])
        return rider.counters.get("+1/+1", 0)

    def test_attacking_with_a_greater_power_puts_a_counter_on_it(self):
        self.assertEqual(self.counters(OGRE), 1)

    def test_not_with_the_same_power_or_alone(self):
        self.assertEqual((self.counters(BEAR), self.counters()), (0, 0))

    def test_a_token_with_training_trains(self):
        game, _ = table3(attack_seat_1)
        a = game.seats[0]
        torens = Permanent(TORENS, sick=False)
        a.battlefield, a.hand = [torens] + lands(2), [BEAR]
        game._perform(a, CAST + "Bear")
        run_stack(game)
        (token,) = [p for p in a.battlefield if "Soldier" in p.card.type_line]
        bear = next(p for p in a.battlefield if p.card is BEAR)
        a.battlefield = [token, bear]
        token.sick = bear.sick = False
        attack(game, a, [])
        self.assertEqual((token.counters.get("+1/+1", 0), bear.counters.get("+1/+1", 0)), (1, 0))


if __name__ == "__main__":
    unittest.main()
