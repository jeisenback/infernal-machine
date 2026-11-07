"""Exile the top cards of your library and play them: until the end of your next turn (said after the exile), until your next end step,
and "Choose one of them" (Clockwork Percussionist, Haste Magic, Heroes' Hangout, Riverwheel Sweep, Fireglass Mentor, Snowslope Hunter);
what was exiled decides a rider (Bonehoard Dracosaur), only spells may be cast (Apex of Power), and played free (Urza, Lord High Artificer)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.zones import CAST_EXILE
from tests.helpers import BEAR, FOREST, OGRE, activate, fire, lands, pick, real, run_stack, table

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
DRACOSAUR = real("Bonehoard Dracosaur", "{3}{R}{R}", "Creature — Dinosaur Dragon",
                 "Flying, first strike\nAt the beginning of your upkeep, exile the top two cards of your library. You may play them this turn. "
                 "If you exiled a land card this way, create a 3/1 red Dinosaur creature token. If you exiled a nonland card this way, "
                 "create a Treasure token.", "5", "5")
WILDS = real("Escape to the Wilds", "{3}{R}{G}", "Sorcery",
             "Exile the top five cards of your library. You may play cards exiled this way until the end of your next turn.\n"
             "You may play an additional land this turn.")
APEX = real("Apex of Power", "{7}{R}{R}{R}", "Sorcery",
            "Exile the top seven cards of your library. Until end of turn, you may cast spells from among them.\n"
            "If this spell was cast from your hand, add ten mana of any one color.")
URZA = real("Urza, Lord High Artificer", "{2}{U}{U}", "Legendary Creature — Human Artificer",
            "When Urza enters, create a 0/0 colorless Construct artifact creature token with \"This token gets +1/+1 for each artifact you control.\"\n"
            "Tap an untapped artifact you control: Add {U}.\n"
            "{5}: Shuffle your library, then exile the top card. Until end of turn, you may play that card without paying its mana cost.", "1", "4")
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


class BonehoardDracosaurTests(unittest.TestCase):
    def upkeep(self, library):
        game, mine, theirs = board(None, Permanent(DRACOSAUR, sick=False))
        mine.library = list(library)
        fire(game, mine, mine.battlefield[0], "upkeep")
        return game, mine

    def test_a_land_and_a_nonland_make_both_tokens(self):
        game, mine = self.upkeep([TOP, FOREST, NEXT])
        self.assertEqual(playable(mine), [("Top Card", game.turn), ("Forest", game.turn)])
        self.assertEqual(sorted(p.card.name for p in mine.battlefield[1:]), ["Dinosaur", "Treasure"])
        dinosaur = next(p for p in mine.battlefield if p.card.name == "Dinosaur")
        self.assertEqual((dinosaur.card.power, dinosaur.card.toughness), ("3", "1"))

    def test_two_nonland_cards_make_only_a_treasure(self):
        game, mine = self.upkeep([TOP, NEXT, FOREST])
        self.assertEqual([p.card.name for p in mine.battlefield[1:]], ["Treasure"])

    def test_two_lands_make_only_a_dinosaur(self):
        game, mine = self.upkeep([FOREST, FOREST, TOP])
        self.assertEqual([p.card.name for p in mine.battlefield[1:]], ["Dinosaur"])

    def test_an_empty_library_makes_nothing(self):
        game, mine = self.upkeep([])
        self.assertEqual(mine.battlefield[1:], [])


class EscapeToTheWildsTests(unittest.TestCase):
    def test_the_five_cards_may_be_played_through_the_next_turn(self):
        game, mine, theirs = board()
        mine.library = [TOP, NEXT, FOREST, FOREST, FOREST, FOREST]
        mine.hand = [WILDS]
        mine.battlefield = lands(5)
        game.step = "main1"
        game._perform(mine, "Cast: Escape to the Wilds")
        run_stack(game)
        self.assertEqual(len(playable(mine)), 5)
        self.assertTrue(all(until == game.turn + 2 for _, until in playable(mine)))
        self.assertEqual(len(mine.library), 1)


class ApexOfPowerTests(unittest.TestCase):
    def cast(self, from_hand):
        game, mine, theirs = board()
        mine.library = [TOP, FOREST, NEXT, FOREST]
        mine.battlefield = lands(10)
        game.step = "main1"
        if from_hand:
            mine.hand = [APEX]
            game._perform(mine, "Cast: Apex of Power")
        else:
            mine.exile, mine.exile_play = [APEX], [(APEX, game.turn)]
            game._perform(mine, CAST_EXILE + "Apex of Power")
        run_stack(game)
        return game, mine

    def test_spells_among_them_may_be_cast_but_not_the_lands(self):
        game, mine = self.cast(True)
        self.assertEqual(sorted(name for name, _ in playable(mine)), ["Next Card", "Top Card"])
        self.assertEqual(sum(c.name == "Forest" for c in mine.exile), 2)

    def test_cast_from_the_hand_it_adds_ten_mana(self):
        game, mine = self.cast(True)
        self.assertEqual(len(mine.mana_pool), 10)

    def test_cast_from_elsewhere_it_adds_none(self):
        game, mine = self.cast(False)
        self.assertEqual(mine.mana_pool, [])
        self.assertEqual(sorted(name for name, _ in playable(mine)), ["Next Card", "Top Card"])


class UrzaTests(unittest.TestCase):
    def test_the_exiled_card_may_be_played_free_this_turn(self):
        game, mine, theirs = board(None, *lands(5), Permanent(URZA, sick=False))
        mine.library = [TOP]
        game.step = "main1"
        activate(game, mine, "Shuffle your library")
        self.assertEqual(playable(mine), [("Top Card", game.turn)])
        self.assertEqual(mine.exile_free, [TOP])


if __name__ == "__main__":
    unittest.main()
