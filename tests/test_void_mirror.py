""""Whenever a player casts a spell, if no colored mana was spent to cast it, counter that spell." (Void Mirror)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, real, run_stack, table3

MIRROR = real("Void Mirror", "{2}", "Artifact", "Whenever a player casts a spell, if no colored mana was spent to cast it, counter that spell.")
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
PAINLAND = Card(name="Adarkar Wastes", type_line="Land", produced_mana=("C", "W"))
THING = Card(name="Thing", mana_cost="{2}", cmc=2.0, type_line="Artifact")


def cast_by_opponent(land):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(MIRROR)]
    b.hand, b.battlefield, b.graveyard = [THING], lands(2, land), []
    game.active = 1
    game._perform(b, CAST + THING.name)
    run_stack(game)
    return b


class VoidMirrorTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(MIRROR), [])

    def test_a_spell_paid_with_colorless_mana_is_countered(self):
        b = cast_by_opponent(WASTES)
        self.assertEqual(b.graveyard, [THING])

    def test_a_spell_paid_with_colored_mana_resolves(self):
        b = cast_by_opponent(FOREST)
        self.assertEqual(b.graveyard, [])
        self.assertTrue(any(p.card is THING for p in b.battlefield))

    def test_mana_that_could_have_been_colored_counts_as_colored(self):
        b = cast_by_opponent(PAINLAND)
        self.assertEqual(b.graveyard, [])


if __name__ == "__main__":
    unittest.main()
