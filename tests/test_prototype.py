"""Issue #842: Prototype {cost} — P/T, "(You may cast this spell with different mana cost, color, and size. It keeps its abilities and
types.)" (CR 702.160, 718), from the cards' real Oracle text. All twelve cards whose only gap it was are fully playable. Blitz Automaton
({7}, a colorless 6/4 with haste; Prototype {2}{R} — 3/2): cast prototyped for three mana it is a red 3/2 with mana value 3 and haste,
and when it dies the card in the graveyard is the 6/4 again; cast for {7} it is the colorless 6/4; with three lands only the prototype
is offered, and with two lands and Ruby Medallion the prototype is (a red spell then)."""

import unittest

from infernal_machine.game import CAST, COST_PROMPT, Permanent
from tests.helpers import lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Blitz Automaton", "Boulderbranch Golem", "Combat Thresher", "Cradle Clearcutter", "Depth Charge Colossus", "Fallaji Dragon Engine",
         "Frogmyr Enforcer", "Goring Warplow", "Iron-Craw Crusher", "Rust Goliath", "Skitterbeam Battalion", "Spotter Thopter"]
AUTOMATON = REAL["Blitz Automaton"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_prototype).
MUTATIONS = [
    ("infernal_machine/casting.py", "power=power, toughness=toughness)", "power=power, toughness=card.toughness)", "the prototype's toughness"),
    ("infernal_machine/casting.py", "colors=tuple(c for c in \"WUBRG\" if c in cost.colors()), power=",
     "colors=card.colors, power=", "the prototype's colors"),
    ("infernal_machine/game.py", "real_card=whole if door or item.prototyped else None", "real_card=whole if door else None",
     "the card itself leaves the battlefield"),
    ("infernal_machine/casting.py", "seat, prototyped(card, way) if way and way.prototype else card, from_command_zone", "seat, card, from_command_zone",
     "a prototype is offered by what it costs prototyped"),
    ("infernal_machine/effects/costs.py", "_IMPENDING, _DASH, _PROTOTYPE, _SPECTACLE,", "_IMPENDING, _DASH, _SPECTACLE,", "the line is read"),
]


def cast(way, mana=7):
    """Seat 0, with `mana` lands, casts Blitz Automaton the way whose option starts with `way`."""
    game, players = table3(lambda prompt, options: next(i for i, o in enumerate(options) if o.startswith(way))
                           if COST_PROMPT.matches(prompt) else 0)
    a = game.seats[0]
    a.hand, a.battlefield = [AUTOMATON], lands(mana)
    game._perform(a, CAST + AUTOMATON.name)
    run_stack(game)
    (automaton,) = [p for p in a.battlefield if p.card.name == AUTOMATON.name]
    return game, players, a, automaton


class PrototypeTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_prototyped_it_is_a_red_three_two_and_the_card_goes_back_whole(self):
        game, _, a, automaton = cast("Prototype")
        card = automaton.card
        self.assertEqual((card.power, card.toughness, card.colors, card.cmc, game.has_keyword(automaton, "haste")), ("3", "2", ("R",), 3.0, True))
        self.assertEqual(sum(not p.tapped for p in a.battlefield if "Land" in p.card.type_line), 4)
        game.destroy(automaton)
        self.assertEqual([(c.power, c.toughness, c.colors) for c in a.graveyard], [("6", "4", ())])

    def test_countered_prototyped_the_card_goes_to_the_graveyard_whole(self):
        game, _ = table3(lambda prompt, options: next(i for i, o in enumerate(options) if o.startswith("Prototype"))
                         if COST_PROMPT.matches(prompt) else 0)
        a = game.seats[0]
        a.hand, a.battlefield = [AUTOMATON], lands(7)
        game._perform(a, CAST + AUTOMATON.name)
        game.counter(game.stack[-1])
        self.assertEqual([(c.power, c.colors) for c in a.graveyard], [("6", ())])

    def test_cast_normally_it_is_the_six_four(self):
        _, _, _, automaton = cast("Pay")
        self.assertEqual((automaton.card.power, automaton.card.toughness, automaton.card.colors), ("6", "4", ()))

    def test_a_red_cost_reducer_counts_for_the_prototype(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield = [AUTOMATON], lands(2) + [Permanent(REAL["Ruby Medallion"])]  # (red spells cost {1} less: {1}{R} is enough)
        self.assertIn(CAST + AUTOMATON.name, game.legal_actions(a))
        game._perform(a, CAST + AUTOMATON.name)
        run_stack(game)
        self.assertEqual([p.card.power for p in a.battlefield if p.card.name == AUTOMATON.name], ["3"])

    def test_with_three_lands_only_the_prototype(self):
        _, players, _, automaton = cast("Prototype", mana=3)
        self.assertEqual(automaton.card.power, "3")
        self.assertEqual([p for p, _ in players[0].prompts if COST_PROMPT.matches(p)], [])  # (one way only: not asked)


if __name__ == "__main__":
    unittest.main()
