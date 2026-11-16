"""Vraska, Betrayal's Sting, from its real Oracle text: "−2: Target creature becomes a Treasure artifact with "{T}, Sacrifice this artifact:
Add one mana of any color" and loses all other card types and abilities." (for good; a legendary one stays legendary; it leaves as its real
card) and "−9: If target player has fewer than nine poison counters, they get a number of poison counters equal to the difference." (one
with nine already gets none)."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, pick, real, run_stack, table3

VRASKA = real("Vraska, Betrayal's Sting", "{4}{B}{B/P}", "Legendary Planeswalker — Vraska", "Compleated ({B/P} can be paid with {B} or "
              "2 life. If life was paid, this planeswalker enters with two fewer loyalty counters.)\n0: You draw a card and lose 1 life. "
              "Proliferate.\n−2: Target creature becomes a Treasure artifact with \"{T}, Sacrifice this artifact: Add one mana of any "
              "color\" and loses all other card types and abilities.\n−9: If target player has fewer than nine poison counters, they get "
              "a number of poison counters equal to the difference.", None, None, colors=("B",))
ISAMARU = real("Isamaru, Hound of Konda", "{W}", "Legendary Creature — Dog", "", "2", "2", colors=("W",))


def activate(ability, target, victim=BEAR):
    """Seat 0 activates Vraska's `ability` ("−2" or "−9"), choosing the option that starts with `target`; seat 1 has `victim`."""
    game, _ = table3(pick(target))
    a, b, c = game.seats
    a.battlefield = [Permanent(VRASKA, loyalty=9)]
    b.battlefield = [Permanent(victim)]
    game.step, game.active = "main1", a.index
    (action,) = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and f": {ability}:" in x]
    game._perform(a, action)
    run_stack(game)
    return game, a, b


class VraskaTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(VRASKA), [])

    def test_minus_two_makes_a_creature_a_treasure_for_good_and_it_leaves_as_itself(self):
        game, a, b = activate("−2", "Bear")
        treasure = b.battlefield[0]
        self.assertEqual((treasure.card.name, treasure.card.type_line, treasure.card.power, treasure.card.oracle_text),
                         ("Bear", "Artifact — Treasure", None, "{T}, Sacrifice this artifact: Add one mana of any color."))
        game.destroy(treasure)
        self.assertEqual(b.graveyard, [BEAR])

    def test_a_legendary_creature_stays_legendary(self):
        _, _, b = activate("−2", "Isamaru", ISAMARU)
        self.assertEqual(b.battlefield[0].card.type_line, "Legendary Artifact — Treasure")

    def test_minus_nine_brings_a_player_to_nine_poison_counters(self):
        for had, has in ((3, 9), (9, 9)):
            game, _ = table3(pick("Player: B"))
            a, b, _ = game.seats
            a.battlefield = [Permanent(VRASKA, loyalty=9)]
            b.player_counters["poison"] = had
            game.step, game.active = "main1", a.index
            (action,) = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and ": −9:" in x]
            game._perform(a, action)
            run_stack(game)
            self.assertEqual(b.player_counters["poison"], has, had)


if __name__ == "__main__":
    unittest.main()
