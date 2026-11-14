"""Ashling, the Limitless, a tracked deck's commander, from its real Oracle text: "Elemental permanent spells you cast from your hand
gain evoke {4} as you cast them." (not a non-Elemental, not from the command zone, not without Ashling) and "Whenever you sacrifice a
nontoken Elemental, create a token that's a copy of it. The token gains haste until end of turn. At the beginning of your next end step,
sacrifice it unless you pay {W}{U}{B}{R}{G}." (a token or a non-Elemental sets nothing off; another player's end step passes it by)."""

import unittest

from infernal_machine.effects import copy_of
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, run_stack, table3

ASHLING = real("Ashling, the Limitless", "{2}{R}", "Legendary Creature — Elemental Sorcerer", "Elemental permanent spells you cast from "
               "your hand gain evoke {4} as you cast them. (If you cast a spell for its evoke cost, it's sacrificed when it enters.)\n"
               "Whenever you sacrifice a nontoken Elemental, create a token that's a copy of it. The token gains haste until end of turn. "
               "At the beginning of your next end step, sacrifice it unless you pay {W}{U}{B}{R}{G}.", "2", "3", colors=("R",))
AIR_ELEMENTAL = real("Air Elemental", "{3}{U}{U}", "Creature — Elemental", "Flying", "4", "4", colors=("U",))


def with_ashling(policy=None):
    game, _ = table3(policy)
    a = game.seats[0]
    a.battlefield = [Permanent(ASHLING)]
    return game, a


def evokes(game, seat, card, from_command_zone=False):
    return [way.text for way in game.caster._cast_ways(seat, card, from_command_zone) if way is not None]


def sacrifice(game, permanent):
    game._leave_together([(permanent, "sacrificed")])


def end_step(game, seat):
    """The end step of `seat`'s turn begins: what was set to happen then happens."""
    game.turn += 1
    game.active, game.step = seat.index, "end"
    due = [what for turn, what in game.at_end_step if turn <= game.turn]
    game.at_end_step = [(turn, what) for turn, what in game.at_end_step if turn > game.turn]
    for what in due:
        what()


class EvokeTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(ASHLING), [])

    def test_an_elemental_from_the_hand_gains_evoke_four(self):
        game, a = with_ashling()
        a.battlefield += lands(4)
        self.assertEqual(evokes(game, a, AIR_ELEMENTAL), ["Evoke {4}"])
        self.assertEqual((evokes(game, a, BEAR), evokes(game, a, AIR_ELEMENTAL, from_command_zone=True)), ([], []))

    def test_evoked_for_four_it_is_sacrificed_and_comes_back_as_a_token(self):
        game, a = with_ashling(pick("Evoke"))
        a.battlefield += lands(4)
        a.hand = [AIR_ELEMENTAL]
        game._perform(a, CAST + "Air Elemental")
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], [p.card.type_line for p in a.battlefield if p.card.name == "Air Elemental"]),
                         (["Air Elemental"], ["Token Creature — Elemental"]))

    def test_not_without_ashling_nor_from_an_opponents(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = lands(4)
        self.assertEqual(evokes(game, a, AIR_ELEMENTAL), [])
        game.seats[1].battlefield = [Permanent(ASHLING)]
        self.assertEqual(evokes(game, a, AIR_ELEMENTAL), [])


class SacrificeTests(unittest.TestCase):
    def test_a_sacrificed_elemental_comes_back_as_a_hasty_token(self):
        game, a = with_ashling()
        elemental = Permanent(AIR_ELEMENTAL)
        a.battlefield.append(elemental)
        sacrifice(game, elemental)
        run_stack(game)
        token = next(p for p in a.battlefield if p.card.name == "Air Elemental")
        self.assertTrue(game.has_keyword(token, "haste"))

    def test_a_token_or_a_non_elemental_sets_nothing_off(self):
        for card, token in ((BEAR, False), (AIR_ELEMENTAL, True)):
            game, a = with_ashling()
            permanent = Permanent(copy_of(card, None, as_token=True) if token else card)
            a.battlefield.append(permanent)
            sacrifice(game, permanent)
            run_stack(game)
            self.assertEqual([p.card.name for p in a.battlefield], ["Ashling, the Limitless"], card.name)

    def test_at_your_next_end_step_it_is_sacrificed_unless_you_pay(self):
        for pays, kept in ((True, 1), (False, 0)):
            game, a = with_ashling(lambda prompt, options: 0 if pays else len(options) - 1)
            a.battlefield += lands(5)
            elemental = Permanent(AIR_ELEMENTAL)
            a.battlefield.append(elemental)
            sacrifice(game, elemental)
            run_stack(game)
            end_step(game, game.seats[1])  # another player's end step passes it by
            self.assertEqual(sum(p.card.name == "Air Elemental" for p in a.battlefield), 1, pays)
            end_step(game, a)
            self.assertEqual(sum(p.card.name == "Air Elemental" for p in a.battlefield), kept, pays)


if __name__ == "__main__":
    unittest.main()
