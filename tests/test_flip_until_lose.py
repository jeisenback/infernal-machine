"""Flip a coin until you lose a flip (CR 705): the flips won count for "for each flip you won", and each win is a "Whenever a player wins
a coin flip". Lines are the cards' own Oracle text; the coin is scripted."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, enter, fire, real, run_stack, table3

MIRROR_MARCH = real("Mirror March", "{5}{R}", "Enchantment",
                    "Whenever a nontoken creature you control enters, flip a coin until you lose a flip. For each flip you won, create a "
                    "token that's a copy of that creature. Those tokens gain haste. Exile them at the beginning of the next end step.",
                    colors=("R",))
OKAUN = real("Okaun, Eye of Chaos", "{4}{R}", "Legendary Creature — Cyclops Berserker",
             "Partner with Zndrsplt, Eye of Wisdom (When this creature enters, target player may put Zndrsplt into their hand from their "
             "library, then shuffle.)\nAt the beginning of combat on your turn, flip a coin until you lose a flip.\nWhenever a player wins a "
             "coin flip, double Okaun's power and toughness until end of turn.", "3", "3", colors=("R",))
ZNDRSPLT = real("Zndrsplt, Eye of Wisdom", "{4}{U}", "Legendary Creature — Homunculus",
                "Partner with Okaun, Eye of Chaos (When this creature enters, target player may put Okaun into their hand from their "
                "library, then shuffle.)\nAt the beginning of combat on your turn, flip a coin until you lose a flip.\nWhenever a player wins "
                "a coin flip, draw a card.", "1", "4", colors=("U",))
CRAZED_FIRECAT = real("Crazed Firecat", "{5}{R}{R}", "Creature — Elemental Cat",
                      "When this creature enters, flip a coin until you lose a flip. Put a +1/+1 counter on this creature for each flip you "
                      "won.", "4", "4", colors=("R",))


class Coin:
    """The flips come out as listed: True wins."""

    def __init__(self, *flips: bool):
        self.flips = list(flips)

    def random(self) -> float:
        return 0.0 if self.flips.pop(0) else 0.9


def tokens(seat):
    return [p for p in seat.battlefield if p.card.type_line.startswith("Token")]


class FlipUntilLoseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (MIRROR_MARCH, OKAUN, ZNDRSPLT, CRAZED_FIRECAT):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_mirror_march_makes_a_hasty_copy_for_each_flip_won(self):
        for flips, copies in (((True, True, False), 2), ((False,), 0)):
            game, _ = table3()
            game.rng = Coin(*flips)
            a = game.seats[0]
            a.battlefield = [Permanent(MIRROR_MARCH)]
            enter(game, a, BEAR)
            run_stack(game)  # (the copies are tokens: they do not set it off again)
            made = tokens(a)
            self.assertEqual((len(made), all(game.has_keyword(p, "haste") for p in made)), (copies, True), flips)
            game.step = "end"
            game._turn_based_actions(a)
            run_stack(game)
            self.assertEqual(tokens(a), [])

    def test_crazed_firecat_gets_a_counter_for_each_flip_won(self):
        game, _ = table3()
        game.rng = Coin(True, True, True, False)
        a = game.seats[0]
        cat = enter(game, a, CRAZED_FIRECAT)
        run_stack(game)
        self.assertEqual(cat.counters.get("+1/+1"), 3)

    def test_each_win_is_heard_by_every_player(self):
        game, _ = table3()
        game.rng = Coin(True, True, False)
        a, b, _ = game.seats
        okaun, zndrsplt = Permanent(OKAUN), Permanent(ZNDRSPLT)
        a.battlefield, b.battlefield, b.library = [okaun], [zndrsplt], [FOREST] * 5
        fire(game, a, okaun, "combat")
        self.assertEqual((game.power(okaun), game.toughness(okaun), len(b.hand)), (12, 12, 2))  # doubled twice; the opponent draws twice
