"""Issue #801: Sunburst, "(This enters with a +1/+1 counter on it for each color of mana spent to cast it if it's a creature, and with a
charge counter on it for each color otherwise.)" (CR 702.44a), from the cards' real Oracle text. All ten cards whose only gap it was are
fully playable. Pentad Prism cast with white and green mana gets two charge counters, with colorless mana none; Etched Oracle, a
creature, gets +1/+1 counters instead; and one put onto the battlefield without being cast gets none."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from tests.helpers import FOREST, PLAINS, enter, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Pentad Prism", "Etched Oracle", "Suntouched Myr", "Clearwater Goblet", "Solarion", "Suncrusher", "Skyreach Manta", "Heliophial",
         "Sawtooth Thresher", "Baton of Courage"]
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))

# The guards these tests are there to catch (python tools/mutate.py tests.test_sunburst).
MUTATIONS = [
    ("infernal_machine/game.py", 'kind = "+1/+1" if "Creature" in permanent.card.type_line else "charge"', 'kind = "charge"',
     "a creature gets +1/+1 counters"),
    ("infernal_machine/game.py", "if has_sunburst(permanent.card) and (colors := colors_spent(permanent.mana_types_spent)):",
     "if has_sunburst(permanent.card) and (colors := 2):", "a counter for each color spent"),
    ("infernal_machine/effects/statics.py", " or SUNBURST.fullmatch(line) is not None", "", "the line is read"),
]


def cast(name, lands):
    """Seat 0 casts `name` with `lands`; the permanent it becomes."""
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.battlefield = [REAL[name]], [Permanent(land) for land in lands]
    game._perform(a, CAST + name)
    run_stack(game)
    game._check_state()
    return next((p for p in a.battlefield if p.card.name == name), None), a


class SunburstTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_a_charge_counter_for_each_color_spent(self):
        prism, _ = cast("Pentad Prism", [PLAINS, FOREST])
        self.assertEqual(prism.counters, {"charge": 2})
        prism, _ = cast("Pentad Prism", [WASTES, WASTES])
        self.assertEqual(prism.counters, {})

    def test_a_creature_gets_plus_one_counters_and_with_none_dies(self):
        oracle, _ = cast("Etched Oracle", [PLAINS, FOREST, WASTES, WASTES])
        self.assertEqual(oracle.counters, {"+1/+1": 2})
        oracle, a = cast("Etched Oracle", [WASTES] * 4)
        self.assertEqual((oracle, [c.name for c in a.graveyard]), (None, ["Etched Oracle"]))  # a 0/0 with no counters

    def test_none_if_it_was_not_cast(self):
        game, _ = table3()
        self.assertEqual(enter(game, game.seats[0], REAL["Pentad Prism"]).counters, {})


if __name__ == "__main__":
    unittest.main()
