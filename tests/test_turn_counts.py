import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Condition, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, run_stack, table3

SPELL = Card(name="Quick Study", mana_cost="{1}{U}", type_line="Instant", oracle_text="Draw two cards.", cmc=2.0)
SORCERY = Card(name="Bolt", mana_cost="{R}", type_line="Instant", oracle_text="Draw a card.", cmc=1.0)


def watcher(text, name="Watcher"):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Wizard", oracle_text=text)


GAIN = watcher("Whenever you gain life for the first time each turn, draw a card.")
SECOND_DRAW = watcher("Whenever an opponent draws their second card each turn, you draw a card.")
THIRD_SPELL = watcher("Whenever you cast your third spell each turn, draw a card.")
OPPONENT_SECOND = watcher("Whenever an opponent casts their second spell each turn, you create a Treasure token.")
FIRST_MAIN = watcher("At the beginning of your first main phase, draw a card.")
SECOND_MAIN = watcher("At the beginning of your second main phase, draw a card.")
DEATHS = watcher("At the beginning of your end step, if two or more creatures died this turn, draw a card.")
LIFE = watcher("At the beginning of your second main phase, if you gained 2 or more life this turn, draw a card.")


def hand_after(game, seat):
    run_stack(game)
    return len(seat.hand)


class ParseTests(unittest.TestCase):
    def test_conditions(self):
        self.assertEqual(triggered_abilities(DEATHS)[0].condition, Condition("creatures_died", 2))
        self.assertEqual(triggered_abilities(LIFE)[0].condition, Condition("gained_life_at_least", 2))

    def test_events(self):
        events = {c.oracle_text.split(",")[0]: triggered_abilities(c)[0].event
                  for c in (GAIN, SECOND_DRAW, FIRST_MAIN, SECOND_MAIN)}
        self.assertEqual(sorted(events.values()), ["first_life_gain", "first_main", "opponent_second_draw", "second_main"])
        self.assertEqual(triggered_abilities(THIRD_SPELL)[0].watch.nth_each_turn, 3)
        self.assertEqual(triggered_abilities(OPPONENT_SECOND)[0].watch.caster, "opponent")

    def test_the_report_understands_them_all(self):
        for card in (GAIN, SECOND_DRAW, THIRD_SPELL, OPPONENT_SECOND, FIRST_MAIN, SECOND_MAIN, DEATHS, LIFE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class EventTests(unittest.TestCase):
    def test_first_life_gain_once_per_turn(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(GAIN)]
        game.change_life(a, 2)
        game.change_life(a, 3)
        self.assertEqual(hand_after(game, a), 1)
        game.turn += 1
        game.change_life(a, 1)
        self.assertEqual(hand_after(game, a), 2)

    def test_losing_life_is_not_gaining_it(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(GAIN)]
        game.change_life(a, -2)
        self.assertEqual(hand_after(game, a), 0)

    def test_an_opponent_draws_their_second_card(self):
        game, _ = table3()
        a, b, c = game.seats
        a.library, b.library, c.library = [BEAR] * 5, [BEAR] * 5, [BEAR] * 5
        a.battlefield = [Permanent(SECOND_DRAW)]
        game.draw(b, 1)
        self.assertEqual(hand_after(game, a), 0)
        game.draw(b, 1)
        game.draw(b, 1)
        self.assertEqual(hand_after(game, a), 1)  # only the second card counts
        game.draw(a, 2)  # you drawing is not an opponent drawing
        self.assertEqual(hand_after(game, a), 3)

    def cast(self, game, seat, card=SPELL):
        seat.cast_log.append((game.turn, card))
        game._observe("cast", card, seat)

    def test_your_third_spell_each_turn(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(THIRD_SPELL)]
        for expected in (0, 0, 1, 1):
            self.cast(game, a)
            self.assertEqual(hand_after(game, a), expected)

    def test_an_opponent_casts_their_second_spell(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(OPPONENT_SECOND)]
        self.cast(game, b)
        self.cast(game, a)
        self.cast(game, a)
        run_stack(game)
        self.assertEqual(len(a.battlefield), 1)  # nobody else's second spell, or your own, counts
        self.cast(game, b)
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Treasure", "Watcher"])


class PhaseAndConditionTests(unittest.TestCase):
    def test_main_phase_triggers(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(FIRST_MAIN), Permanent(SECOND_MAIN)]
        game.step = "main1"
        game._turn_based_actions(a)
        self.assertEqual(hand_after(game, a), 1)
        game.step = "main2"
        game._turn_based_actions(a)
        self.assertEqual(hand_after(game, a), 2)

    def end_step(self, game, seat):
        game.step = "end"
        game._turn_based_actions(seat)
        return hand_after(game, seat)

    def test_creatures_that_died_this_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.library = [BEAR] * 5
        bears = [Permanent(BEAR) for _ in range(3)]
        a.battlefield = [Permanent(DEATHS), bears[0]]
        b.battlefield = bears[1:]
        game._leave_battlefield(bears[0], "dies")
        self.assertEqual(self.end_step(game, a), 0)  # one creature died
        game._leave_battlefield(bears[1], "dies")  # an opponent's creature counts too
        self.assertEqual(self.end_step(game, a), 1)

    def test_deaths_are_counted_per_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.library = [BEAR] * 5
        bears = [Permanent(BEAR) for _ in range(2)]
        a.battlefield = [Permanent(DEATHS), *bears]
        game._leave_battlefield(bears[0], "dies")
        game.turn += 1
        game._leave_battlefield(bears[1], "dies")
        self.assertEqual(self.end_step(game, a), 0)

    def test_gaining_two_or_more_life(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(LIFE)]
        game.change_life(a, 1)
        game.step = "main2"
        game._turn_based_actions(a)
        self.assertEqual(hand_after(game, a), 0)
        game.change_life(a, 1)  # 2 in total this turn
        game._turn_based_actions(a)
        self.assertEqual(hand_after(game, a), 1)


if __name__ == "__main__":
    unittest.main()
