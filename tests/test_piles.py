"""Two piles, from the cards' real Oracle text: Fact or Fiction (an opponent separates the revealed cards, you choose the pile for your
hand) and Steam Augury (you separate them, an opponent chooses the pile for your hand); the other pile goes into the graveyard."""

import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Deck
from infernal_machine.game import CAST, PILE_GIVE_PROMPT, PILE_TAKE_PROMPT, SEPARATE_PROMPT
from infernal_machine.prompts import subject_of
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, SOL_RING, lands, real, run_stack, table3

FACT = real("Fact or Fiction", "{3}{U}", "Instant", "Reveal the top five cards of your library. An opponent separates those cards into two "
            "piles. Put one pile into your hand and the other into your graveyard.", colors=("U",))
AUGURY = real("Steam Augury", "{2}{U}{R}", "Instant", "Reveal the top five cards of your library and separate them into two piles. An "
              "opponent chooses one of those piles. Put that pile into your hand and the other into your graveyard.", colors=("U", "R"))
LIBRARY = [OGRE, BEAR, FOREST, RELIC, SOL_RING, FOREST]  # the sixth stays


def separate_ogre(prompt, options):
    """Ogre alone in pile 1, the rest in pile 2; take (or give) pile 1."""
    if SEPARATE_PROMPT.matches(prompt):
        return 0 if subject_of(prompt, SEPARATE_PROMPT) == "Ogre" else 1
    return 0


def names(cards):
    return sorted(c.name for c in cards)


class PileTests(unittest.TestCase):
    def test_they_are_understood(self):
        for card in (FACT, AUGURY):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_fact_or_fiction_the_opponent_separates_and_you_choose(self):
        asked = []
        def take_second(prompt, options):
            asked.append(prompt)
            return 1 if PILE_TAKE_PROMPT.matches(prompt) else 0
        game, _ = table3(take_second, separate_ogre)
        a = game.seats[0]
        a.library = list(LIBRARY)
        a.battlefield = lands(4)
        a.hand = [FACT]
        game._perform(a, CAST + FACT.name)
        run_stack(game)
        self.assertEqual((names(a.hand), names(a.graveyard), names(a.library)),
                         (["Bear", "Forest", "Relic", "Sol Ring"], ["Fact or Fiction", "Ogre"], ["Forest"]))
        self.assertTrue(any(PILE_TAKE_PROMPT.matches(p) for p in asked))
        self.assertFalse(any(SEPARATE_PROMPT.matches(p) for p in asked))  # the caster doesn't separate

    def test_steam_augury_you_separate_and_the_opponent_chooses(self):
        asked = []
        def give_first(prompt, options):
            asked.append(prompt)
            return 0
        game, _ = table3(separate_ogre, give_first)
        a = game.seats[0]
        a.library = list(LIBRARY)
        a.battlefield = lands(4)
        a.hand = [AUGURY]
        game._perform(a, CAST + AUGURY.name)
        run_stack(game)
        self.assertEqual((names(a.hand), names(a.graveyard)), (["Ogre"], ["Bear", "Forest", "Relic", "Sol Ring", "Steam Augury"]))
        self.assertTrue(any(PILE_GIVE_PROMPT.matches(p) for p in asked))

    def test_the_bot_takes_the_bigger_pile_and_gives_the_smaller(self):
        bot = BotPlayer("Bot", Deck(commanders=[], main=[], sideboard=[]))
        options = ["Pile 1: Ogre (mana value 3)", "Pile 2: Bear, Forest (mana value 2)"]
        self.assertEqual((bot.choose(PILE_TAKE_PROMPT, options), bot.choose(PILE_GIVE_PROMPT("A"), options),
                          bot.choose(SEPARATE_PROMPT("Relic"), options)), (0, 1, 1))


if __name__ == "__main__":
    unittest.main()
