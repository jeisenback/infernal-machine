"""Syr Konrad, the Grim (#268 by EDHREC rank), from his real Oracle text: "Whenever another creature dies, or a creature card is put into
a graveyard from anywhere other than the battlefield, or a creature card leaves your graveyard, Syr Konrad deals 1 damage to each
opponent." is three watches. A Bear dying deals 1 to each opponent, once (its card going to the graveyard is "from the battlefield");
an opponent milling a creature card deals 1, a land card nothing; Raise Dead returning a creature card from his controller's graveyard
deals 1; his "{1}{B}: Each player mills a card." with two creature cards on top deals 2."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, FOREST, activate, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

KONRAD, RAISE = REAL["Syr Konrad, the Grim"], REAL["Raise Dead"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_syr_konrad).
MUTATIONS = [
    ("infernal_machine/game.py", "                self._move_card(permanent.owner or controller, permanent.card, where, from_battlefield=True)",
     "                self._move_card(permanent.owner or controller, permanent.card, where)", "a death is not also a card put there"),
    ("infernal_machine/game.py", '            self._observe("card_left_graveyard", card, seat)  # Syr Konrad', "            pass  # Syr Konrad",
     "a creature card leaving the graveyard"),
    ("infernal_machine/effects/triggers.py", '("card_to_graveyard", Watch("creature", from_zone="not_battlefield"), rest)',
     '("card_to_graveyard", Watch("land", from_zone="not_battlefield"), rest)', "only a creature card"),
]


def konrad():
    game, players = table3()
    a, b, c = game.seats
    a.battlefield = [Permanent(KONRAD, sick=False)]
    return game, players, a, b, c


class SyrKonradTests(unittest.TestCase):
    def test_it_is_playable(self):
        wording_unlocked(self, ["Syr Konrad, the Grim"])

    def test_another_creature_dying_deals_one_once(self):
        game, _, a, b, c = konrad()
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        game.destroy(bear)
        run_stack(game)
        self.assertEqual((b.life, c.life, a.life), (39, 39, 40))

    def test_a_creature_card_milled_deals_one_and_a_land_nothing(self):
        game, _, a, b, c = konrad()
        b.library = [BEAR, FOREST]
        game.mill(b, 1)
        run_stack(game)
        game.mill(b, 1)
        run_stack(game)
        self.assertEqual((b.life, c.life), (39, 39))

    def test_a_creature_card_leaving_his_graveyard(self):
        game, _, a, b, c = konrad()
        a.battlefield += lands(1)
        a.graveyard, a.hand = [BEAR], [RAISE]
        game._perform(a, CAST + RAISE.name)
        run_stack(game)
        self.assertEqual((BEAR in a.hand, b.life), (True, 39))

    def test_each_player_mills(self):
        game, _, a, b, c = konrad()
        a.battlefield += lands(2)
        for seat in game.seats:
            seat.library = [BEAR if seat is not c else FOREST]
        activate(game, a, "mills")
        self.assertEqual((b.life, c.life), (38, 38))


if __name__ == "__main__":
    unittest.main()
