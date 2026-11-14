"""Waterbend, from the cards' real Oracle text: "While paying a waterbend cost, you can tap your artifacts and creatures to help. Each
one pays for {1}." Katara, Bending Prodigy's "Waterbend {6}: Draw a card." is paid with lands and creatures (Katara herself among them),
Giant Koi's {3} likewise; a plain cost (Jayemdae Tome's {4}) gets no such help; and The Unagi of Kyoshi Island's "Ward—Waterbend {4}" lets the payer
tap their creatures too."""

import unittest

from infernal_machine.effects.statics import ward_cost
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, RELIC, activate, lands, real, table3

REMINDER = "(While paying a waterbend cost, you can tap your artifacts and creatures to help. Each one pays for {1}.)"
KATARA = real("Katara, Bending Prodigy", "{2}{U}", "Legendary Creature — Human Warrior Ally", "At the beginning of your end step, if "
              "Katara is tapped, put a +1/+1 counter on her.\nWaterbend {6}: Draw a card. " + REMINDER, "2", "3", colors=("U",))
KOI = real("Giant Koi", "{4}{U}{U}", "Creature — Fish", "Waterbend {3}: This creature can't be blocked this turn. " + REMINDER + "\nIslandcycling "
           "{2} ({2}, Discard this card: Search your library for an Island card, reveal it, put it into your hand, then shuffle.)", "5", "7",
           colors=("U",))
UNAGI = real("The Unagi of Kyoshi Island", "{3}{U}{U}", "Legendary Creature — Serpent", "Flash\nWard—Waterbend {4}. (Whenever this "
             "creature becomes the target of a spell or ability an opponent controls, counter it unless that player pays {4}. They can tap "
             "their artifacts and creatures to help. Each one pays for {1}.)\nWhenever an opponent draws their second card each turn, you "
             "draw two cards.", "5", "5", colors=("U",))
TOME = real("Jayemdae Tome", "{4}", "Artifact — Book", "{4}, {T}: Draw a card.")


def offered(game, seat, name):
    return any(a.startswith(ACTIVATE) and name in a for a in game.legal_actions(seat))


class WaterbendTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (KATARA, KOI, UNAGI):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_artifacts_and_creatures_help_pay_and_are_tapped(self):
        game, _ = table3()
        a = game.seats[0]
        katara = Permanent(KATARA)
        a.battlefield, a.library = [*lands(2), katara, Permanent(BEAR), Permanent(BEAR), Permanent(RELIC)], [FOREST] * 3
        activate(game, a, "Katara")
        self.assertEqual((len(a.hand), all(p.tapped for p in a.battlefield), game.payer._waterbending), (1, True, False))  # no help after

    def test_not_offered_when_even_tapping_everything_falls_short(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [*lands(1), Permanent(KOI)]  # two of the {3}: the land and the Koi itself
        self.assertFalse(offered(game, a, "Giant Koi"))
        a.battlefield.append(Permanent(BEAR))
        self.assertTrue(offered(game, a, "Giant Koi"))

    def test_a_plain_cost_gets_no_help(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [*lands(1), Permanent(TOME), Permanent(BEAR), Permanent(BEAR), Permanent(RELIC)]
        self.assertFalse(offered(game, a, "Jayemdae Tome"))

    def test_ward_waterbend_lets_the_payer_tap_creatures(self):
        game, _ = table3()
        b = game.seats[1]
        cost = ward_cost(UNAGI)
        b.battlefield = [*lands(1), Permanent(BEAR), Permanent(BEAR), Permanent(RELIC)]
        self.assertEqual((cost, game.can_pay_ward(b, cost), game.can_pay_ward(b, "{4}")), ("Waterbend {4}", True, False))
        game.pay_ward(b, cost)
        self.assertTrue(all(p.tapped for p in b.battlefield))


if __name__ == "__main__":
    unittest.main()
