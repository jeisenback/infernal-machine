"""The bot's block decisions: kill what it can safely, trade up, double-block, chump when what is coming is lethal (#394)."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.combat import BLOCK_PROMPT
from tests.helpers import real

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
BEAR = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", 2, 2)
STING = real("Sting Imp", "{B}", "Creature — Imp", "Deathtouch", 1, 1)
KNIGHT = real("White Knight", "{W}{W}", "Creature — Knight", "First strike", 2, 2)
GOLEM = real("Iron Golem", "{4}", "Artifact Creature — Golem", "Indestructible", 3, 3)
DECK = Deck([], [MOUNTAIN, BEAR, STING, KNIGHT, GOLEM], [])
NO_BLOCK = "Don't block"
NO_BLOCK_FEATURES = FEATURES - {"block"}


def permanent(name, power, toughness, tapped=False):
    return {"name": name, "type": "Creature", "tapped": tapped, "sick": False, "power": power, "toughness": toughness}


def bot(mine, life=20, features=FEATURES):
    b = BotPlayer("Bot", DECK, features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": life})
    b.notify({"event": "state", "turn": 4, "hand": [], "seats": [
        {"seat": 0, "lost": False, "life": life, "mana_pool": [], "battlefield": list(mine)},
        {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": []}]})
    return b


def block(b, blocker, *attackers):
    options = [NO_BLOCK] + [f"Block {a} (seat 1, #{i + 9})" for i, a in enumerate(attackers)]
    return b.choose(BLOCK_PROMPT(blocker), options)


class SingleBlockTests(unittest.TestCase):
    def test_it_kills_the_attacker_that_is_worth_most_among_those_it_can_kill_and_survive(self):
        me = "Iron Ogre 3/3 (seat 0, #1)"
        self.assertEqual(block(bot([]), me, "Spark 2/1", "Wall 1/3"), 2)  # the wall: it kills both, the wall is worth more
        self.assertEqual(block(bot([], features=NO_BLOCK_FEATURES), me, "Spark 2/1", "Wall 1/3"), 1, "the plain bot takes the harder hitter")

    def test_it_trades_with_a_creature_that_is_worth_more(self):
        me = "Grizzly Bears 2/2 (seat 0, #1)"
        self.assertEqual(block(bot([]), me, "Raider 4/2"), 1)
        self.assertEqual(block(bot([], features=NO_BLOCK_FEATURES), me, "Raider 4/2"), 0)

    def test_it_does_not_trade_down(self):
        self.assertEqual(block(bot([]), "Big Bear 4/4 (seat 0, #1)", "Pest 4/1"), 0)

    def test_a_deathtouch_creature_trades_with_anything(self):
        self.assertEqual(block(bot([]), "Sting Imp 1/1 (seat 0, #1)", "Dragon 5/5"), 1)
        self.assertEqual(block(bot([]), "Sting Imp 1/1 (seat 0, #1)", "Pest 1/1"), 0, "but not with a creature worth no more")

    def test_a_first_striker_kills_an_equal_creature_and_lives(self):
        self.assertEqual(block(bot([]), "White Knight 2/2 (seat 0, #1)", "Bear 2/2"), 1)
        self.assertEqual(block(bot([], features=NO_BLOCK_FEATURES), "White Knight 2/2 (seat 0, #1)", "Bear 2/2"), 0)

    def test_an_indestructible_creature_blocks_what_it_cannot_kill(self):
        # it survives a 5/5 but does not kill it: the plain rules (survive, so block) apply, and it still blocks
        self.assertEqual(block(bot([]), "Iron Golem 3/3 (seat 0, #1)", "Titan 5/5"), 1)


class DoubleBlockTests(unittest.TestCase):
    MINE = [permanent("Mountain", None, None)] * 4 + [permanent("Grizzly Bears", 2, 2), permanent("Grizzly Bears", 2, 2)]
    FIRST, SECOND = "Grizzly Bears 2/2 (seat 0, #5)", "Grizzly Bears 2/2 (seat 0, #6)"

    def test_two_creatures_that_together_kill_a_bigger_one_both_block_it(self):
        b = bot(self.MINE)
        self.assertEqual(block(b, self.FIRST, "Ogre 3/4"), 1)
        self.assertEqual(block(b, self.SECOND, "Ogre 3/4"), 1, "the second joins the plan")

    def test_the_plain_bot_does_not_block_it(self):
        self.assertEqual(block(bot(self.MINE, features=NO_BLOCK_FEATURES), self.FIRST, "Ogre 3/4"), 0)

    def test_not_when_the_attacker_would_kill_both(self):
        self.assertEqual(block(bot(self.MINE), self.FIRST, "Ogre 4/4"), 0)

    def test_not_when_the_two_together_cannot_kill_it(self):
        self.assertEqual(block(bot(self.MINE), self.FIRST, "Ogre 3/5"), 0)

    def test_not_when_it_would_lose_a_creature_worth_as_much_as_the_attacker(self):
        self.assertEqual(block(bot(self.MINE), self.FIRST, "Raider 3/1"), 0, "one bear kills it but dies: an even trade is not worth a block")
        self.assertEqual(block(bot(self.MINE), self.FIRST, "Wall 1/4"), 1, "the attacker cannot kill either bear: a free kill for two")

    def test_a_tapped_creature_is_not_a_partner(self):
        tapped = self.MINE[:5] + [permanent("Grizzly Bears", 2, 2, tapped=True)]
        self.assertEqual(block(bot(tapped), self.FIRST, "Ogre 3/4"), 0)

    def test_a_new_turn_forgets_the_plan(self):
        b = bot(self.MINE)
        block(b, self.FIRST, "Ogre 3/4")
        b.notify({"event": "state", "turn": 6, "hand": [], "seats": [
            {"seat": 0, "lost": False, "life": 20, "mana_pool": [], "battlefield": self.MINE[:5]},
            {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": []}]})
        self.assertEqual(block(b, self.FIRST, "Ogre 3/4"), 0, "a plan from the last turn does not pull this bear in; it has no partner now")


class ChumpTests(unittest.TestCase):
    def test_it_chumps_the_biggest_when_what_is_coming_would_be_lethal(self):
        me = "Grizzly Bears 2/2 (seat 0, #1)"
        self.assertEqual(block(bot([]), me, "Giant 10/10", "Titan 15/15"), 2)
        self.assertEqual(block(bot([], features=NO_BLOCK_FEATURES), me, "Giant 10/10", "Titan 15/15"), 0, "the plain bot waits until it is at 10 life")

    def test_it_does_not_chump_when_it_is_not_lethal(self):
        self.assertEqual(block(bot([]), "Grizzly Bears 2/2 (seat 0, #1)", "Giant 10/10", "Imp 3/3"), 0)


if __name__ == "__main__":
    unittest.main()
