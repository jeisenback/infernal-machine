"""Jace, Multiverse Architect, a tracked deck's commander, from its real Oracle text: its combat tax ("they may pay {2}. If they don't,
creatures they control can't attack Jaces you control this turn."), its +1 (draw two, put a card from your hand on the bottom) and its -3
(exile another planeswalker or creature you control, then reveal until a creature or planeswalker card and put it onto the battlefield)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, activate, lands, real, run_stack, table3

JACE = real("Jace, Multiverse Architect", "{1}{W}{U}{B}{R}", "Legendary Planeswalker — Jace", "At the beginning of combat on each opponent's "
            "turn, they may pay {2}. If they don't, creatures they control can't attack Jaces you control this turn.\n+1: Draw two cards, then "
            "put a card from your hand on the bottom of your library.\n−3: Exile another target planeswalker or creature you control. "
            "Reveal cards from the top of your library until you reveal a creature or planeswalker card. Put that card onto the battlefield "
            "and the rest on the bottom of your library in a random order.\nJace, Multiverse Architect can be your commander.",
            colors=tuple("WUBR"))


def with_jace(opponent=None):
    game, _ = table3(None, opponent)  # the opponent (seat 1) answers whether to pay
    a = game.seats[0]
    jace = Permanent(JACE, loyalty=4)
    a.battlefield = [jace]
    return game, a, jace


class JaceTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(JACE), [])

    def test_plus_one_draws_two_and_puts_one_on_the_bottom(self):
        game, a, _ = with_jace()
        a.library = [OGRE, BEAR, FOREST, FOREST]
        activate(game, a, "+1")
        self.assertEqual((len(a.hand), a.library[-1].name, len(a.library)), (1, "Ogre", 3))  # the first card offered went to the bottom

    def test_minus_three_exiles_another_and_puts_the_first_creature_revealed_onto_the_battlefield(self):
        game, a, jace = with_jace()
        bear = Permanent(BEAR)
        a.battlefield.append(bear)
        a.library = [FOREST, FOREST, OGRE, FOREST]
        activate(game, a, "−3")
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in a.exile], [c.name for c in a.library]),
                         (["Jace, Multiverse Architect", "Ogre"], ["Bear"], ["Forest", "Forest", "Forest"]))

    def test_an_opponent_who_doesnt_pay_cant_attack_jace_this_turn(self):
        for pays, walker_offered in ((False, False), (True, True)):
            def answer(prompt, options):
                return 0 if pays else len(options) - 1
            game, a, jace = with_jace(answer)
            b = game.seats[1]
            bear = Permanent(BEAR)
            b.battlefield = [*lands(2), bear]
            game.trigger("opponent_combat", jace, a, player=b)
            run_stack(game)
            _, walkers = game.combat._attackable(b, bear, game.opponents(b), [jace])
            self.assertEqual((walkers == [jace], sum(p.tapped for p in b.battlefield)), (walker_offered, 2 if pays else 0), pays)

    def test_the_bar_is_for_this_turn_only(self):
        game, a, jace = with_jace(lambda prompt, options: len(options) - 1)
        b = game.seats[1]
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        game.trigger("opponent_combat", jace, a, player=b)
        run_stack(game)
        game.turn += 1
        self.assertEqual(game.combat._attackable(b, bear, game.opponents(b), [jace])[1], [jace])


if __name__ == "__main__":
    unittest.main()
