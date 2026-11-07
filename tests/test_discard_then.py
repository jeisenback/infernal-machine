"""Discard a card to exile the top cards and play them (#658): Inti, Seneschal of the Sun ("you may discard a card. When you do, ..." and
"Whenever you discard one or more cards") and Party Thrasher ("you may discard a card. If you do, exile the top two cards ...", and
convoke for noncreature spells cast from exile)."""

import unittest

from infernal_machine.game import CAST, CAST_EXILE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, pick, real, run_stack, table

INTI = real("Inti, Seneschal of the Sun", "{1}{R}", "Legendary Creature — Human Knight",
            "Whenever you attack, you may discard a card. When you do, put a +1/+1 counter on target attacking creature. It gains trample "
            "until end of turn.\nWhenever you discard one or more cards, exile the top card of your library. You may play that card until "
            "your next end step.", "2", "2", colors=("R",))
THRASHER = real("Party Thrasher", "{1}{R}", "Creature — Lizard Wizard",
                "Noncreature spells you cast from exile have convoke. (Each creature you tap while casting a noncreature spell from exile "
                "pays for {1} or one mana of that creature's color.)\nAt the beginning of your first main phase, you may discard a card. If "
                "you do, exile the top two cards of your library, then choose one of them. You may play that card this turn.",
                "1", "4", colors=("R",))
TOP = real("Top Card", "{1}", "Sorcery", "")
NEXT = real("Next Card", "{1}", "Sorcery", "")
JUNK = real("Junk", "{1}", "Sorcery", "")
DIVINE = real("Divine Draw", "{2}", "Sorcery", "Draw a card.")
BIG_BEAR = real("Big Bear", "{2}", "Creature — Bear", "", "2", "2")


class IntiTests(unittest.TestCase):
    def attack(self, answer):
        game, _, _ = table(pick("Attack", answer, "Bear"))
        mine = game.seats[0]
        inti, bear = Permanent(INTI, sick=False), Permanent(BEAR, sick=False)
        mine.battlefield, mine.hand, mine.library = [inti, bear], [JUNK], [TOP, NEXT, FOREST]
        game.step = "declare_attackers"
        game.combat.declare_attackers(mine)
        run_stack(game)
        return game, mine, bear

    def test_discarding_puts_a_counter_and_trample_on_an_attacker_and_exiles_the_top_card(self):
        game, mine, bear = self.attack("Yes")
        self.assertEqual(mine.graveyard, [JUNK])
        self.assertEqual(bear.counters.get("+1/+1"), 1)
        self.assertTrue(game.has_keyword(bear, "trample"))
        self.assertEqual([(c.name, until) for c, until in mine.exile_play], [("Top Card", game.turn)])  # (its end step is still to come)

    def test_declining_does_nothing(self):
        game, mine, bear = self.attack("No")
        self.assertEqual((mine.hand, bear.counters.get("+1/+1"), mine.exile_play), ([JUNK], None, []))

    def test_cards_discarded_together_exile_one_card(self):
        game, _, _ = table(pick("Junk"))
        mine = game.seats[0]
        mine.battlefield, mine.hand, mine.library = [Permanent(INTI)], [JUNK, JUNK], [TOP, NEXT]
        game.discard(mine, 2)
        run_stack(game)
        self.assertEqual([c.name for c, _ in mine.exile_play], ["Top Card"])


class PartyThrasherTests(unittest.TestCase):
    def first_main(self, answers, hand=(JUNK,)):
        game, _, _ = table(pick(*answers))
        mine = game.seats[0]
        mine.battlefield, mine.hand, mine.library = [Permanent(THRASHER)], list(hand), [TOP, NEXT, FOREST]
        game._turn_based_actions(mine)  # (the game is in its first main phase)
        run_stack(game)
        return game, mine

    def test_discarding_exiles_two_and_the_chosen_one_may_be_played_this_turn(self):
        game, mine = self.first_main(("Yes", "Next Card"))
        self.assertEqual(mine.graveyard, [JUNK])
        self.assertEqual(sorted(c.name for c in mine.exile), ["Next Card", "Top Card"])
        self.assertEqual([(c.name, until) for c, until in mine.exile_play], [("Next Card", game.turn)])

    def test_with_no_card_to_discard_nothing_is_exiled(self):
        game, mine = self.first_main(("Yes",), hand=())
        self.assertEqual((mine.exile, mine.library[0]), ([], TOP))

    def convoke(self, card, thrasher=True):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield = [Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)] + ([Permanent(THRASHER)] if thrasher else [])
        mine.exile, mine.exile_play = [card], [(card, game.turn)]
        return CAST_EXILE + card.name in game.legal_actions(mine), game, mine

    def test_a_noncreature_spell_cast_from_exile_can_be_paid_by_tapping_creatures(self):
        castable, game, mine = self.convoke(DIVINE)
        self.assertTrue(castable)
        game._perform(mine, CAST_EXILE + DIVINE.name)
        self.assertEqual(sorted(p.card.name for p in mine.battlefield if p.tapped), ["Bear", "Ogre"])

    def test_a_creature_spell_from_exile_has_no_convoke(self):
        self.assertFalse(self.convoke(BIG_BEAR)[0])

    def test_without_party_thrasher_there_is_no_convoke(self):
        self.assertFalse(self.convoke(DIVINE, thrasher=False)[0])

    def test_a_spell_cast_from_the_hand_has_no_convoke(self):
        castable, game, mine = self.convoke(DIVINE)
        mine.exile, mine.exile_play, mine.hand = [], [], [DIVINE]
        self.assertNotIn(CAST + DIVINE.name, game.legal_actions(mine))


class ReadingTests(unittest.TestCase):
    def test_an_if_you_do_effect_that_targets_is_not_read(self):  # (its target would be chosen before the discard)
        card = real("Probe", "{1}", "Creature — Probe", "When this creature enters, you may discard a card. If you do, destroy target "
                    "creature.", "1", "1")
        self.assertTrue(unsupported_lines(card))


if __name__ == "__main__":
    unittest.main()
