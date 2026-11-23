"""Issue #848: "CARDNAME's power is equal to the number of creatures you control." (a characteristic-defining ability, CR 604.3), from
the cards' real Oracle text. All eight cards whose only gap it was are fully playable. Ironroot Warlord (*/5) with two Bears beside it
is 3/5: its toughness stays as printed; the creatures of another player do not count; Overbeing of Myth's "power and toughness are
each equal to ..." still sets both; once it has lost its abilities (Infinite Coursework) its power is its printed * (CR 613.1f). Eleven more cards whose power counts something else are playable too: Zendikar Incarnate (*/4) with
three lands is 3/4."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, COURSEWORK, lands, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Suki, Kyoshi Warrior", "Zurgo's Vanguard", "Snow Villiers", "Sumala Rumblers", "Freedom Fighter Recruit", "Ironroot Warlord",
         "Kolaghan Forerunners", "Soulsurge Elemental"]
OTHERS = ["Brotherhood Vertibird", "Cephalopod Sentry", "Coiling Woodworm", "Dakmor Sorceress", "Filigree Attendant", "Nightstalker Engine",
          "Sima Yi, Wei Field Marshal", "Swarm of Rats", "Sylvan Yeti", "Uurg, Spawn of Turg", "Zendikar Incarnate"]  # (counting other things)
WARLORD = REAL["Ironroot Warlord"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_power_equal_to_creatures).
MUTATIONS = [
    ("infernal_machine/game.py", "set_pt=(size, size if both else", "set_pt=(size, size if True else", "the toughness stays as printed"),
    ("infernal_machine/game.py", "                and not self.loses_abilities(permanent):  # CR 613.1f", "                and True:  # CR 613.1f",
     "not once it has lost its abilities"),
    ("infernal_machine/effects/statics.py", 'return amount, m[1] != "power is"', 'return amount, False', "both, for power and toughness"),
]


def board(*others):
    """Seat 0 controls Ironroot Warlord and `others`; seat 1 controls three Bears."""
    game, _ = table3()
    a, b, _ = game.seats
    warlord = Permanent(WARLORD)
    a.battlefield = [warlord, *others]
    b.battlefield = [Permanent(BEAR) for _ in range(3)]
    return game, warlord


class PowerEqualToCreaturesTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)
        wording_unlocked(self, OTHERS)

    def test_a_power_counting_lands(self):
        game, _ = table3()
        incarnate = Permanent(REAL["Zendikar Incarnate"])
        game.seats[0].battlefield = [incarnate, *lands(3)]
        self.assertEqual((game.power(incarnate), game.toughness(incarnate)), (3, 4))

    def test_its_power_counts_your_creatures_and_its_toughness_stays(self):
        game, warlord = board(Permanent(BEAR), Permanent(BEAR))
        self.assertEqual((game.power(warlord), game.toughness(warlord)), (3, 5))

    def test_alone_it_counts_itself_not_another_players_creatures(self):
        game, warlord = board()
        self.assertEqual((game.power(warlord), game.toughness(warlord)), (1, 5))

    def test_once_it_has_lost_its_abilities_its_power_is_its_printed_star(self):
        game, warlord = board(Permanent(BEAR), Permanent(BEAR))
        game.seats[1].battlefield.append(Permanent(COURSEWORK, attached_to=warlord))  # (enchanted creature loses all abilities)
        self.assertEqual((game.power(warlord), game.toughness(warlord)), (0, 5))

    def test_power_and_toughness_each_still_sets_both(self):
        game, _ = table3()
        a = game.seats[0]
        overbeing = Permanent(REAL["Overbeing of Myth"])  # (each equal to the number of cards in your hand)
        a.battlefield, a.hand = [overbeing], [BEAR, BEAR]
        self.assertEqual((game.power(overbeing), game.toughness(overbeing)), (2, 2))


if __name__ == "__main__":
    unittest.main()
