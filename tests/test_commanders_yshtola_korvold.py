"""Two tracked decks' commanders, from their real Oracle text. Y'shtola, Night's Blessed: "At the beginning of each end step, if a player
lost 4 or more life this turn, you draw a card." (Knight of the Ebon Legion has the same condition). Korvold, Fae-Cursed King: "Whenever
Korvold enters or attacks, sacrifice another permanent." and its sacrifice trigger."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, fire, real, table3

YSHTOLA = real("Y'shtola, Night's Blessed", "{1}{W}{U}{B}", "Legendary Creature — Cat Warlock", "Vigilance\nAt the beginning of each end step, "
               "if a player lost 4 or more life this turn, you draw a card.\nWhenever you cast a noncreature spell with mana value 3 or greater, "
               "Y'shtola deals 2 damage to each opponent and you gain 2 life.", "2", "4", colors=("W", "U", "B"))
KNIGHT = real("Knight of the Ebon Legion", "{B}", "Creature — Vampire Knight", "{2}{B}: This creature gets +3/+3 and gains deathtouch until end "
              "of turn.\nAt the beginning of your end step, if a player lost 4 or more life this turn, put a +1/+1 counter on this creature. "
              "(Damage causes loss of life.)", "1", "2", colors=("B",))
KORVOLD = real("Korvold, Fae-Cursed King", "{2}{B}{R}{G}", "Legendary Creature — Dragon Noble", "Flying\nWhenever Korvold enters or attacks, "
               "sacrifice another permanent.\nWhenever you sacrifice a permanent, put a +1/+1 counter on Korvold and draw a card.", "4", "4",
               colors=("B", "R", "G"))


class YshtolaTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (YSHTOLA, KNIGHT, KORVOLD):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_it_draws_only_after_a_player_lost_four_life(self):
        for lost, drawn in ((4, 1), (3, 0)):
            game, _ = table3()
            a, b = game.seats[0], game.seats[1]
            yshtola = Permanent(YSHTOLA)
            a.battlefield, a.library = [yshtola], [FOREST] * 3
            game.change_life(b, -1)
            game.change_life(b, -(lost - 1))  # two losses in one turn add up
            fire(game, a, yshtola, "each_end_step")
            self.assertEqual(len(a.hand), drawn, lost)

    def test_a_loss_on_an_earlier_turn_does_not_count(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        yshtola = Permanent(YSHTOLA)
        a.battlefield, a.library = [yshtola], [FOREST] * 3
        game.change_life(b, -5)
        game.turn += 1
        fire(game, a, yshtola, "each_end_step")
        self.assertEqual(a.hand, [])

    def test_its_own_controllers_loss_counts_too(self):
        game, _ = table3()
        a = game.seats[0]
        knight = Permanent(KNIGHT)
        a.battlefield = [knight]
        game.change_life(a, -5)
        fire(game, a, knight, "end_step")
        self.assertEqual(knight.counters.get("+1/+1"), 1)


class KorvoldTests(unittest.TestCase):
    def test_entering_sacrifices_another_permanent_and_draws(self):
        game, _ = table3()
        a = game.seats[0]
        korvold, land = Permanent(KORVOLD), Permanent(FOREST)
        a.battlefield, a.library = [korvold, land], [FOREST] * 3
        fire(game, a, korvold, "enters")
        self.assertEqual((a.battlefield, len(a.hand), korvold.counters.get("+1/+1")), ([korvold], 1, 1))

    def test_alone_it_sacrifices_nothing(self):
        game, _ = table3()
        a = game.seats[0]
        korvold = Permanent(KORVOLD)
        a.battlefield = [korvold]
        fire(game, a, korvold, "attacks")
        self.assertEqual((a.battlefield, a.graveyard), ([korvold], []))


if __name__ == "__main__":
    unittest.main()
