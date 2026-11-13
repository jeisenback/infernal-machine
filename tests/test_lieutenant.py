"""Lieutenant, from the cards' real Oracle text: Loyal Apprentice and Siege-Gang Lieutenant (tokens at the beginning of combat that "gain
haste until end of turn"), and Thunderfoot Baloth and Angelic Field Marshal ("this creature gets +2/+2 and other creatures you control
get ..." while you control your commander: two buffs in one sentence)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, COMMANDER, fire, real, table3

APPRENTICE = real("Loyal Apprentice", "{1}{R}", "Creature — Human Artificer", "Haste\nLieutenant — At the beginning of combat on your turn, "
                  "if you control your commander, create a 1/1 colorless Thopter artifact creature token with flying. That token gains haste "
                  "until end of turn.", "2", "1", colors=("R",))
SIEGE_GANG = real("Siege-Gang Lieutenant", "{3}{R}", "Creature — Goblin", "Lieutenant — At the beginning of combat on your turn, if you "
                  "control your commander, create two 1/1 red Goblin creature tokens. Those tokens gain haste until end of turn.\n{2}, Sacrifice "
                  "a Goblin: This creature deals 1 damage to any target.", "2", "2", colors=("R",))
BALOTH = real("Thunderfoot Baloth", "{4}{G}{G}", "Creature — Beast", "Trample\nLieutenant — As long as you control your commander, this "
              "creature gets +2/+2 and other creatures you control get +2/+2 and have trample.", "5", "5", colors=("G",))
MARSHAL = real("Angelic Field Marshal", "{2}{W}{W}", "Creature — Angel", "Flying\nLieutenant — As long as you control your commander, this "
               "creature gets +2/+2 and creatures you control have vigilance.", "3", "3", colors=("W",))
CARDS = (APPRENTICE, SIEGE_GANG, BALOTH, MARSHAL)
HALF_READ = real("Half Read", "{3}", "Creature — Beast", "Lieutenant — As long as you control your commander, this creature gets +2/+2 and "
                 "other creatures you control can't be countered.", "2", "2")


def tokens(seat):
    return [p for p in seat.battlefield if p.card.type_line.startswith("Token")]


class LieutenantTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_line_read_only_in_half_is_not_read(self):
        self.assertNotEqual(unsupported_lines(HALF_READ), [])

    def test_the_tokens_come_with_haste_only_with_your_commander(self):
        for card, count in ((APPRENTICE, 1), (SIEGE_GANG, 2)):
            for commander in (True, False):
                game, _ = table3()
                a = game.seats[0]
                lieutenant = Permanent(card)
                a.battlefield = [lieutenant] + ([Permanent(COMMANDER)] if commander else [])
                fire(game, a, lieutenant, "combat")
                made = tokens(a)
                self.assertEqual((len(made), all(game.has_keyword(t, "haste") for t in made)), (count if commander else 0, True),
                                 (card.name, commander))

    def test_thunderfoot_baloth_grows_itself_and_the_others(self):
        for commander, sizes in ((True, ((7, 7), (4, 4), True)), (False, ((5, 5), (2, 2), False))):
            game, _ = table3()
            a = game.seats[0]
            baloth, bear = Permanent(BALOTH), Permanent(BEAR)
            a.battlefield = [baloth, bear] + ([Permanent(COMMANDER)] if commander else [])
            self.assertEqual(((game.power(baloth), game.toughness(baloth)), (game.power(bear), game.toughness(bear)),
                              game.has_keyword(bear, "trample")), sizes, commander)

    def test_angelic_field_marshal_gives_vigilance_to_all_your_creatures(self):
        game, _ = table3()
        a = game.seats[0]
        marshal, bear = Permanent(MARSHAL), Permanent(BEAR)
        a.battlefield = [marshal, bear, Permanent(COMMANDER)]
        self.assertEqual((game.power(marshal), game.has_keyword(bear, "vigilance"), game.has_keyword(marshal, "vigilance")), (5, True, True))


if __name__ == "__main__":
    unittest.main()
