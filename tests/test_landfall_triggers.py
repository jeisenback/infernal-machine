"""Landfall triggers, from the cards' real Oracle text: Omnath, Locus of the Roil (a sentence "If <condition>, <effect>." checked as
it resolves), Tannuk, Memorial Ensign ("If this is the second time this ability has resolved this turn"), Roil Elemental (control for
as long as you control it), Ob Nixilis, the Fallen ("you may have target player lose 3 life. If you do, ...") and Geode Rager (goad
each creature target player controls)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, enter, lands, pick, real, run_stack, table3

OMNATH = real("Omnath, Locus of the Roil", "{1}{G}{U}{R}", "Legendary Creature — Elemental", "When Omnath enters, it deals damage to any "
              "target equal to the number of Elementals you control.\nLandfall — Whenever a land you control enters, put a +1/+1 counter "
              "on target Elemental you control. If you control eight or more lands, draw a card.", "3", "3", colors=("G", "R", "U"))
TANNUK = real("Tannuk, Memorial Ensign", "{1}{R}{G}", "Legendary Creature — Kavu Pilot", "Landfall — Whenever a land you control enters, "
              "Tannuk deals 1 damage to each opponent. If this is the second time this ability has resolved this turn, draw a card.",
              "2", "4", colors=("G", "R"))
ROIL = real("Roil Elemental", "{3}{U}{U}{U}", "Creature — Elemental", "Flying\nLandfall — Whenever a land you control enters, you may gain "
            "control of target creature for as long as you control this creature.", "3", "2", colors=("U",))
OB = real("Ob Nixilis, the Fallen", "{3}{B}{B}", "Legendary Creature — Demon", "Landfall — Whenever a land you control enters, you may "
          "have target player lose 3 life. If you do, put three +1/+1 counters on Ob Nixilis.", "3", "3", colors=("B",))
RAGER = real("Geode Rager", "{4}{R}{R}", "Creature — Elemental", "First strike\nLandfall — Whenever a land you control enters, goad each "
             "creature target player controls. (Until your next turn, those creatures attack each combat if able and attack a player "
             "other than you if able.)", "4", "3", colors=("R",))


def land_enters(game, seat):
    enter(game, seat, FOREST)
    run_stack(game)


class LandfallTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (OMNATH, TANNUK, ROIL, OB, RAGER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_an_if_sentence_about_what_an_earlier_one_chose_is_not_read(self):  # "on it" is the tapped creature, not the source
        wit = real("Rapier Wit", "{1}{U}", "Instant", "Tap target creature. If it's your turn, put a stun counter on it. (If a permanent "
                   "with a stun counter would become untapped, remove one from it instead.)\nDraw a card.", colors=("U",))
        self.assertTrue(unsupported_lines(wit))

    def test_omnath_draws_only_with_eight_or_more_lands(self):
        for others, drawn in ((7, 1), (6, 0)):
            game, _ = table3()
            a = game.seats[0]
            omnath = Permanent(OMNATH)
            a.battlefield, a.library = [omnath, *lands(others, FOREST)], [FOREST] * 3
            land_enters(game, a)
            self.assertEqual((omnath.counters.get("+1/+1"), len(a.hand)), (1, drawn), others)

    def test_tannuk_draws_on_the_second_resolution_each_turn_only(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield, a.library = [Permanent(TANNUK)], [FOREST] * 9
        for _ in range(3):
            land_enters(game, a)
        self.assertEqual((b.life, c.life, len(a.hand)), (37, 37, 1))  # three pings, one card: on the second
        game.turn += 1  # a new turn counts again from the first
        land_enters(game, a)
        self.assertEqual(len(a.hand), 1)
        land_enters(game, a)
        self.assertEqual(len(a.hand), 2)

    def test_roil_elemental_keeps_the_creature_only_while_you_control_it(self):
        game, _ = table3(pick("Yes", "Ogre"))
        a, b, _ = game.seats
        roil, ogre = Permanent(ROIL), Permanent(OGRE)
        a.battlefield, b.battlefield = [roil], [ogre]
        land_enters(game, a)
        self.assertIn(ogre, a.battlefield)
        game.gain_control(roil, b)  # its controller loses control of Roil Elemental: the effect ends
        game._check_state()
        self.assertIn(ogre, b.battlefield)

    def test_roil_elemental_gone_before_it_resolves_takes_nothing(self):
        game, _ = table3(pick("Yes", "Ogre"))
        a, b, _ = game.seats
        roil, ogre = Permanent(ROIL), Permanent(OGRE)
        a.battlefield, b.battlefield = [roil], [ogre]
        enter(game, a, FOREST)
        game._put_triggers_on_stack()
        a.battlefield.remove(roil)  # CR 611.2b: the duration has already ended
        run_stack(game)
        self.assertIn(ogre, b.battlefield)

    def test_ob_nixilis_drains_and_grows_only_if_you_do(self):
        for answer, life, counters in (("Yes", 37, 3), ("No", 40, None)):
            game, _ = table3(pick(answer, "Player: B"))
            a, b, _ = game.seats
            ob = Permanent(OB)
            a.battlefield = [ob]
            land_enters(game, a)
            self.assertEqual((b.life, ob.counters.get("+1/+1")), (life, counters), answer)

    def test_geode_rager_goads_the_creatures_of_the_target_player_only(self):
        game, _ = table3(pick("Player: B"))
        a, b, c = game.seats
        theirs, other = Permanent(BEAR), Permanent(OGRE)
        a.battlefield, b.battlefield, c.battlefield = [Permanent(RAGER)], [theirs], [other]
        land_enters(game, a)
        self.assertEqual((game.goader_of(theirs), game.goader_of(other)), (a, None))


if __name__ == "__main__":
    unittest.main()
