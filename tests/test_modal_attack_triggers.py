"""Modal triggers that exile the top cards to play them (#658): Breeches, Eager Pillager ("choose one that hasn't been chosen this
turn", each mode once a turn for the source; Lita, Little Orphan Amphibian says it with a period) and Tectonic Giant ("attacks or
becomes the target of a spell an opponent controls")."""

import unittest

from infernal_machine.game import MODE_PROMPT, Permanent
from tests.helpers import BEAR, FOREST, enter, lands, pick, real, run_stack, table

BREECHES = real("Breeches, Eager Pillager", "{2}{R}", "Legendary Creature — Goblin Pirate",
                "First strike\nWhenever a Pirate you control attacks, choose one that hasn't been chosen this turn —\n• Create a Treasure token.\n"
                "• Target creature can't block this turn.\n• Exile the top card of your library. You may play it this turn.", "3", "3", colors=("R",))
GIANT = real("Tectonic Giant", "{2}{R}{R}", "Creature — Elemental Giant",
             "Whenever this creature attacks or becomes the target of a spell an opponent controls, choose one —\n• This creature deals 3 damage "
             "to each opponent.\n• Exile the top two cards of your library. Choose one of them. Until the end of your next turn, you may play "
             "that card.", "3", "4", colors=("R",))
LITA = real("Lita, Little Orphan Amphibian", "{1}{W}", "Legendary Creature — Mutant Ninja Turtle",
            "Alliance — Whenever another creature you control enters, choose one that hasn't been chosen this turn.\n• Put a +1/+1 counter "
            "on Lita.\n• Create a Food token. (It's an artifact with \"{2}, {T}, Sacrifice this token: You gain 3 life.\")\n• Scry 1.",
            "2", "1", colors=("W",))
PIRATE = real("Deckhand", "{1}{R}", "Creature — Human Pirate", "", "2", "2", colors=("R",))
SHOCK = real("Shock", "{R}", "Instant", "Shock deals 2 damage to any target.", colors=("R",))
TOP = real("Top Card", "{1}", "Sorcery", "")
NEXT = real("Next Card", "{1}", "Sorcery", "")


def attacks(game, seat, permanent):
    game._observe("creature_attacks", permanent.card, seat, subject=permanent)
    run_stack(game)


def asking(answer, asked):
    """A policy that answers the mode question with `answer` and writes down the modes it was offered."""
    def policy(prompt, options):
        if MODE_PROMPT.matches(prompt):
            asked.append(list(options))
        return pick(answer, "Bear")(prompt, options)
    return policy


class BreechesTests(unittest.TestCase):
    def board(self, answer, asked=None):
        game, _, _ = table(asking(answer, asked if asked is not None else []))
        mine, theirs = game.seats
        breeches, deckhand = Permanent(BREECHES, sick=False), Permanent(PIRATE, sick=False)
        mine.battlefield, mine.library = [breeches, deckhand], [TOP, NEXT, FOREST]
        theirs.battlefield = [Permanent(BEAR, sick=False)]
        return game, mine, breeches, deckhand

    def test_a_pirate_attacking_makes_a_treasure(self):
        game, mine, breeches, deckhand = self.board("Create a Treasure")
        attacks(game, mine, deckhand)
        self.assertIn("Treasure", [p.card.name for p in mine.battlefield])

    def test_a_mode_chosen_this_turn_is_not_offered_again(self):
        asked: list = []
        game, mine, breeches, deckhand = self.board("Create a Treasure", asked)
        attacks(game, mine, deckhand)
        attacks(game, mine, breeches)
        self.assertEqual(len(asked[0]), 3)
        self.assertNotIn("Create a Treasure token.", asked[1])
        self.assertEqual(len(asked[1]), 2)

    def test_next_turn_every_mode_is_offered_again(self):
        asked: list = []
        game, mine, breeches, deckhand = self.board("Create a Treasure", asked)
        attacks(game, mine, deckhand)
        game.turn += 2
        attacks(game, mine, deckhand)
        self.assertEqual(len(asked[1]), 3)

    def test_the_exiled_card_may_be_played_this_turn(self):
        game, mine, breeches, deckhand = self.board("Exile the top card")
        attacks(game, mine, deckhand)
        self.assertEqual([(c.name, until) for c, until in mine.exile_play], [("Top Card", game.turn)])

    def test_a_creature_that_is_not_a_pirate_sets_nothing_off(self):
        asked: list = []
        game, mine, breeches, deckhand = self.board("Create a Treasure", asked)
        bear = Permanent(BEAR, sick=False)
        mine.battlefield.append(bear)
        game._observe("creature_attacks", bear.card, mine, subject=bear)
        run_stack(game)
        self.assertEqual(asked, [])


class LitaTests(unittest.TestCase):
    def test_each_mode_once_a_turn_as_creatures_enter(self):
        asked: list = []
        game, _, _ = table(asking("Put a +1/+1 counter", asked))
        mine = game.seats[0]
        lita = Permanent(LITA, sick=False)
        mine.battlefield, mine.library = [lita], [FOREST] * 5
        enter(game, mine, BEAR)
        run_stack(game)
        enter(game, mine, BEAR)
        run_stack(game)
        self.assertEqual(lita.counters.get("+1/+1"), 1)
        self.assertEqual((len(asked[0]), len(asked[1])), (3, 2))
        self.assertIn("Food", [p.card.name for p in mine.battlefield])  # the second time: the first mode left (pick's default)


class TectonicGiantTests(unittest.TestCase):
    def board(self, answer, theirs_policy=None):
        game, _, _ = table(pick(answer), theirs_policy)
        mine, theirs = game.seats
        giant = Permanent(GIANT, sick=False)
        mine.battlefield, mine.library = [giant], [TOP, NEXT, FOREST]
        return game, mine, theirs, giant

    def test_attacking_deals_3_to_each_opponent(self):
        game, mine, theirs, giant = self.board("This creature deals 3")
        game.trigger("attacks", giant, mine)
        run_stack(game)
        self.assertEqual(theirs.life, 37)

    def test_the_exile_mode_lets_one_card_be_played_through_the_next_turn(self):
        game, mine, theirs, giant = self.board("Exile the top two")
        game.trigger("attacks", giant, mine)
        run_stack(game)
        self.assertEqual(len(mine.exile_play), 1)
        self.assertEqual(mine.exile_play[0][1], game.turn + 2)

    def test_an_opponents_spell_targeting_it_sets_it_off(self):
        game, mine, theirs, giant = self.board("This creature deals 3", pick("Tectonic Giant"))
        theirs.hand, theirs.battlefield = [SHOCK], lands(1)
        game.active = 1
        game._perform(theirs, "Cast: Shock")
        run_stack(game)
        self.assertEqual(theirs.life, 37)

    def test_its_controllers_own_spell_does_not(self):
        game, mine, theirs, giant = self.board("Tectonic Giant")
        mine.hand, mine.battlefield = [SHOCK], [giant, *lands(1)]
        game._perform(mine, "Cast: Shock")
        run_stack(game)
        self.assertEqual(theirs.life, 40)


if __name__ == "__main__":
    unittest.main()
