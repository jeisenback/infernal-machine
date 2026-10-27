"""A shortcut (infernal_machine/shortcut.py): a player names the actions of a loop and how many times to go round it."""

import unittest

from infernal_machine.game import BoardLimitReached, Permanent
from infernal_machine.shortcut import Shortcut, pick, take
from tests.helpers import BEAR, OGRE, pick as pick_policy, real, table

BASALT = real("Basalt Monolith", "{3}", "Artifact", "This artifact doesn't untap during your untap step.\n{T}: Add {C}{C}{C}.\n{3}: Untap this artifact.")
SOULTRADER = real("Warren Soultrader", "{2}{B}", "Creature — Zombie Goblin Wizard", "Pay 1 life, Sacrifice another creature: Create a Treasure "
                  "token. (It's an artifact with \"{T}, Sacrifice this token: Add one mana of any color.\")", "3", "3", colors=("B",))
CUTTHROAT = real("Zulaport Cutthroat", "{1}{B}", "Creature — Human Rogue Ally", "Whenever this creature or another creature you control dies, "
                 "each opponent loses 1 life and you gain 1 life.", "1", "1", colors=("B",))
CHATTERFANG = real("Chatterfang, Squirrel General", "{2}{G}", "Legendary Creature — Squirrel Warrior", "Forestwalk (This creature can't be blocked as "
                   "long as defending player controls a Forest.)\nIf one or more tokens would be created under your control, those tokens plus that many "
                   "1/1 green Squirrel creature tokens are created instead.\n{B}, Sacrifice X Squirrels: Target creature gets +X/-X until end of turn.",
                   "3", "3", colors=("G",))
KINNAN = real("Kinnan, Bonder Prodigy", "{G}{U}", "Legendary Creature \u2014 Human Druid", "Whenever you tap a nonland permanent for mana, add one mana of any "
              "type that permanent produced.\n{5}{G}{U}: Look at the top five cards of your library. You may put a non-Human creature card from among them "
              "onto the battlefield. Put the rest on the bottom of your library in a random order.", "2", "2", colors=("G", "U"))
UNTAP = "{3}: Untap this artifact"


def basalt_table():
    game, _, _ = table()
    mine = game.seats[0]
    mine.battlefield = [Permanent(BASALT)]
    return game, mine


def drain_table(policy=None):
    """Soultrader and Cutthroat, with Chatterfang and a Bear to sacrifice: each sacrifice drains one and leaves a Squirrel."""
    game, _, _ = table(policy)
    mine = game.seats[0]
    mine.battlefield = [Permanent(SOULTRADER, sick=False), Permanent(CUTTHROAT, sick=False), Permanent(CHATTERFANG, sick=False), Permanent(BEAR, sick=False)]
    return game, mine


class ShortcutTests(unittest.TestCase):
    def test_it_goes_round_the_asked_number_of_times(self):
        game, mine = basalt_table()
        result = take(game, mine, Shortcut((UNTAP,)), 5)
        self.assertEqual((result.rounds, result.stopped, result.over), (5, None, False))

    def test_a_step_that_is_not_offered_stops_it_and_says_which(self):
        game, mine = basalt_table()
        result = take(game, mine, Shortcut((UNTAP, "Cast: Nothing")), 5)
        self.assertEqual((result.rounds, result.stopped), (0, 'round 1: "Cast: Nothing" is not offered'))

    def test_it_stops_when_the_game_is_over_and_names_the_round(self):
        game, mine = drain_table(pick_policy("Squirrel 1/1", "Bear"))
        result = take(game, mine, Shortcut(("Warren Soultrader",), ("Squirrel 1/1", "Bear", "Player: B")), 100)
        self.assertEqual((result.over, game.seats[1].lost, result.rounds), (True, True, 40))  # one life a round, from 40

    def test_its_answers_are_the_players_in_the_loop_and_the_players_own_after(self):
        game, mine = drain_table()
        original = mine.player
        take(game, mine, Shortcut(("Warren Soultrader",), ("Bear",)), 1)
        self.assertEqual([c.name for c in mine.graveyard], ["Bear"])  # the shortcut said the Bear
        self.assertIs(mine.player, original)

    def test_without_its_answer_the_player_chooses(self):
        game, mine = drain_table()
        take(game, mine, Shortcut(("Warren Soultrader",)), 1)
        self.assertEqual([c.name for c in mine.graveyard], ["Zulaport Cutthroat"])  # the scripted player takes the first option

    def test_the_player_is_put_back_when_the_board_limit_ends_it(self):
        game, mine = drain_table()
        game.board_limit = 5  # a Treasure and a Squirrel for each sacrifice
        original = mine.player
        with self.assertRaises(BoardLimitReached):
            take(game, mine, Shortcut(("Warren Soultrader",), ("Bear", "Squirrel 1/1")), 10)
        self.assertIs(mine.player, original)


class KeepPoolTests(unittest.TestCase):
    """Kinnan with Basalt Monolith: a tap makes four, the untap pays three. The game spends the pool first, which keeps the pool where it
    was; a shortcut that keeps the pool pays from the permanent first, so the extra mana builds up."""

    def table(self):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield = [Permanent(BASALT), Permanent(KINNAN, sick=False)]
        return game, mine

    def test_the_surplus_builds_up_one_a_round(self):
        game, mine = self.table()
        take(game, mine, Shortcut((UNTAP,)), 6, keep_pool=True)
        self.assertEqual(len(mine.mana_pool), 6)

    def test_by_default_the_pool_is_spent_first_and_stays_small(self):
        game, mine = self.table()
        take(game, mine, Shortcut((UNTAP,)), 6)
        self.assertLess(len(mine.mana_pool), 4)

    def test_the_order_is_put_back_afterwards(self):
        game, mine = self.table()
        take(game, mine, Shortcut((UNTAP,)), 2, keep_pool=True)
        self.assertFalse(game.pool_last)


class PickTests(unittest.TestCase):
    def test_an_answer_for_a_named_question_does_not_apply_to_another(self):
        self.assertEqual(pick(("Choose X~1", "Ogre"), "Choose X for Chatterfang", ["0", "1"]), 1)
        self.assertEqual(pick(("Choose X~1",), "Choose a target", ["0", "1"]), None)
        self.assertEqual(pick(("Ogre",), "Choose a target", [BEAR.name, OGRE.name]), 1)


if __name__ == "__main__":
    unittest.main()
