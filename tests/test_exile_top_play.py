"""Exile the top cards of your library and play them: until the end of your next turn (said after the exile), until your next end step,
and "Choose one of them" (Clockwork Percussionist, Haste Magic, Heroes' Hangout, Riverwheel Sweep, Fireglass Mentor, Snowslope Hunter)."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, FOREST, OGRE, lands, pick, real, run_stack, table

PERCUSSIONIST = real("Clockwork Percussionist", "{R}", "Artifact Creature — Monkey Toy",
                     "Haste\nWhen this creature dies, exile the top card of your library. You may play it until the end of your next turn.", "1", "1")
HASTE_MAGIC = real("Haste Magic", "{1}{R}", "Instant",
                   "Target creature gets +3/+1 and gains haste until end of turn. Exile the top card of your library. You may play it until your next end step.")
SWEEP = real("Riverwheel Sweep", "{2/U}{2/R}{2/W}", "Sorcery",
             "Tap target creature. Put three stun counters on it. (If a permanent with a stun counter would become untapped, remove one from it instead.)\n"
             "Exile the top two cards of your library. Choose one of them. Until the end of your next turn, you may play that card.")
MENTOR = real("Fireglass Mentor", "{B}{R}", "Creature — Lizard Warlock",
              "At the beginning of your second main phase, if an opponent lost life this turn, exile the top two cards of your library. "
              "Choose one of them. Until end of turn, you may play that card.", "2", "1")
HUNTER = real("Snowslope Hunter", "{2}{R}", "Creature — Goblin Ranger",
              "Sacrifice another creature or artifact: Exile the top card of your library. You may play it until the end of your next turn. "
              "Activate only during your turn and only once each turn.", "2", "3")
TOP = real("Top Card", "{1}", "Sorcery", "")
NEXT = real("Next Card", "{1}", "Sorcery", "")


def board(policy=None, *permanents):
    game, _, _ = table(policy)
    mine, theirs = game.seats
    mine.battlefield = list(permanents)
    mine.library = [TOP, NEXT, FOREST, FOREST]
    return game, mine, theirs


def playable(seat):
    return [(c.name, until) for c, until in seat.exile_play]


class UntilTheEndOfYourNextTurnTests(unittest.TestCase):
    def test_a_card_exiled_when_the_creature_dies_may_be_played_through_the_next_turn(self):
        game, mine, theirs = board(None, Permanent(PERCUSSIONIST, sick=False))
        game.destroy(mine.battlefield[0])
        run_stack(game)
        self.assertEqual(playable(mine), [("Top Card", game.turn + 2)])  # the opponent's turn, then this one's next turn
        self.assertEqual([c.name for c in mine.exile], ["Top Card"])

    def test_the_opponent_gets_no_permission(self):
        game, mine, theirs = board(None, Permanent(PERCUSSIONIST, sick=False))
        game.destroy(mine.battlefield[0])
        run_stack(game)
        self.assertEqual(playable(theirs), [])


class UntilYourNextEndStepTests(unittest.TestCase):
    def test_on_your_own_turn_it_lasts_until_the_turn_ends(self):
        game, mine, theirs = board(pick("Creature", "Bear", "Ogre"))
        mine.hand = [HASTE_MAGIC]
        mine.battlefield = lands(2) + [Permanent(BEAR, sick=False)]
        game.step = "main1"
        game._perform(mine, "Cast: Haste Magic")
        run_stack(game)
        self.assertEqual(playable(mine), [("Top Card", game.turn)])

    def test_on_another_players_turn_it_lasts_through_your_next_turn(self):
        game, mine, theirs = board(pick("Bear"))
        mine.hand = [HASTE_MAGIC]
        mine.battlefield = lands(2) + [Permanent(BEAR, sick=False)]
        game.active, game.step = 1, "main1"
        game._perform(mine, "Cast: Haste Magic")
        run_stack(game)
        self.assertEqual(playable(mine), [("Top Card", game.turn + 1)])  # (the opponent's turn, then it is mine)


class ChooseOneOfThemTests(unittest.TestCase):
    def test_only_the_chosen_card_may_be_played_and_the_other_stays_exiled(self):
        game, mine, theirs = board(pick("Next Card", "Ogre", "Player: B"))
        theirs.battlefield = [Permanent(OGRE, sick=False)]
        mine.hand = [SWEEP]
        mine.battlefield = lands(6)
        game.step = "main1"
        game._perform(mine, "Cast: Riverwheel Sweep")
        run_stack(game)
        self.assertEqual(sorted(c.name for c in mine.exile), ["Next Card", "Top Card"])
        self.assertEqual([name for name, _ in playable(mine)], ["Next Card"])

    def test_the_default_choice_is_the_first_card(self):
        game, mine, theirs = board(pick("Ogre"))
        theirs.battlefield = [Permanent(OGRE, sick=False)]
        mine.hand = [SWEEP]
        mine.battlefield = lands(6)
        game.step = "main1"
        game._perform(mine, "Cast: Riverwheel Sweep")
        run_stack(game)
        self.assertEqual([name for name, _ in playable(mine)], ["Top Card"])


class FireglassMentorTests(unittest.TestCase):
    def test_it_exiles_only_if_an_opponent_lost_life_this_turn(self):
        game, mine, theirs = board(pick("Next Card"), Permanent(MENTOR, sick=False))
        game.step = "main2"
        game.trigger("second_main", mine.battlefield[0], mine)
        run_stack(game)
        self.assertEqual(mine.exile, [])
        game.change_life(theirs, -1)
        game.trigger("second_main", mine.battlefield[0], mine)
        run_stack(game)
        self.assertEqual(sorted(c.name for c in mine.exile), ["Next Card", "Top Card"])
        self.assertEqual(playable(mine), [("Next Card", game.turn)])

    def test_your_own_life_loss_does_not_count(self):
        game, mine, theirs = board(None, Permanent(MENTOR, sick=False))
        game.change_life(mine, -3)
        game.trigger("second_main", mine.battlefield[0], mine)
        run_stack(game)
        self.assertEqual(mine.exile, [])


class SnowslopeHunterTests(unittest.TestCase):
    def test_once_each_turn_and_only_on_your_turn(self):
        game, mine, theirs = board(pick("Bear"), Permanent(HUNTER, sick=False), Permanent(BEAR, sick=False), Permanent(OGRE, sick=False))
        offered = lambda: [o for o in game.legal_actions(mine) if "Exile the top card" in o]
        self.assertEqual(len(offered()), 1)
        game._perform(mine, offered()[0])
        run_stack(game)
        self.assertEqual(offered(), [], "only once each turn")
        game.turn += 1
        self.assertEqual(len(offered()), 1, "again on the next turn")
        game.active = 1
        self.assertEqual(offered(), [], "not on the opponent's turn")


if __name__ == "__main__":
    unittest.main()
