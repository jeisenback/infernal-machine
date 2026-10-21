"""Library search, reveal and look-at-the-top as one family (#495): searching for several cards (to the hand, the battlefield or
the top of the library), revealing the top cards and putting all of a kind onto the battlefield, looking at the top cards and
putting one onto the battlefield, and a search bounded by the source's power. Played from the cards' real Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, DONE, NONE_TAKEN, SEARCH_CARD_PROMPT, Permanent
from infernal_machine.prompts import PRIORITY_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, activate, enter, lands, pick, real, run_stack, script, settle, table3

GOBLIN_RECRUITER = real("Goblin Recruiter", "{1}{R}", "Creature — Goblin",
                        "When this creature enters, search your library for any number of Goblin cards, reveal them, then shuffle and "
                        "put those cards on top in any order.", "1", "1")
MUXUS = real("Muxus, Goblin Grandee", "{4}{R}{R}", "Legendary Creature — Goblin Noble",
             "When Muxus enters, reveal the top six cards of your library. Put all Goblin creature cards with mana value 5 or less from "
             "among them onto the battlefield and the rest on the bottom of your library in a random order.\n"
             "Whenever Muxus attacks, it gets +1/+1 until end of turn for each other Goblin you control.", "4", "4")
TIAMAT = real("Tiamat", "{2}{W}{U}{B}{R}{G}", "Legendary Creature — Dragon God",
              "Flying\nWhen Tiamat enters, if you cast it, search your library for up to five Dragon cards not named Tiamat that each "
              "have different names, reveal them, put them into your hand, then shuffle.", "7", "7", colors=tuple("WUBRG"))
URENI = real("Ureni of the Unwritten", "{4}{G}{U}{R}", "Legendary Creature — Spirit Dragon",
             "Flying, trample\nWhenever Ureni enters or attacks, look at the top eight cards of your library. You may put a Dragon "
             "creature card from among them onto the battlefield. Put the rest on the bottom of your library in a random order.",
             "7", "7", colors=("G", "U", "R"))
SISAY = real("Sisay, Weatherlight Captain", "{2}{W}", "Legendary Creature — Human Soldier",
             "Sisay gets +1/+1 for each color among other legendary permanents you control.\n"
             "{W}{U}{B}{R}{G}: Search your library for a legendary permanent card with mana value less than Sisay's power, put that "
             "card onto the battlefield, then shuffle.", "2", "2", colors=("W",))


def goblin(name, cmc):
    return Card(name=name, mana_cost=f"{{{cmc}}}", cmc=cmc, type_line="Creature — Goblin", power="1", toughness="1")


def dragon(name, type_line="Creature — Dragon"):
    return Card(name=name, mana_cost="{4}{R}", cmc=5, type_line=type_line, power="4", toughness="4")


GOBLIN_A, GOBLIN_B, GOBLIN_SIX = goblin("Goblin A", 1), goblin("Goblin B", 3), goblin("Goblin Six", 6)
DRAGON_A, DRAGON_B, DRAGON_C = dragon("Dragon A"), dragon("Dragon B"), dragon("Dragon C")
DRAGON_SHRINE = dragon("Dragon Shrine", "Enchantment — Dragon")  # a Dragon card that is not a creature
MARKER = Card(name="Marker", type_line="Land")
LEGEND_ONE = Card(name="Legend One", mana_cost="{1}", cmc=1, type_line="Legendary Artifact")
LEGEND_TWO = Card(name="Legend Two", mana_cost="{2}", cmc=2, type_line="Legendary Creature — Human", power="1", toughness="1")
LEGEND_SPELL = Card(name="Legend Spell", mana_cost="{0}", cmc=0, type_line="Legendary Sorcery")  # not a permanent card


def names(cards):
    return [c.name for c in cards]


class ParseTests(unittest.TestCase):
    def test_the_library_lines_are_read(self):
        self.assertEqual(unsupported_lines(GOBLIN_RECRUITER), [])
        self.assertEqual(unsupported_lines(TIAMAT), [])
        self.assertEqual(unsupported_lines(URENI), [])
        # Muxus's attack pump and Sisay's static are other work; their library lines are read
        self.assertEqual([line[:30] for line in unsupported_lines(MUXUS)], ["Whenever CARDNAME attacks, it "])
        self.assertEqual([line[:30] for line in unsupported_lines(SISAY)], ["CARDNAME gets +1/+1 for each c"])


class SearchManyTests(unittest.TestCase):
    def test_goblin_recruiter_stacks_the_chosen_goblins_on_top_in_the_chosen_order(self):
        game, _ = table3(script("Goblin A", "Goblin B", "Goblin B"))  # find A, then B (no Goblin is left, so no third ask); B goes on top
        a = game.seats[0]
        a.library = [BEAR, GOBLIN_A, FOREST, GOBLIN_B, OGRE]
        enter(game, a, GOBLIN_RECRUITER)
        run_stack(game)
        self.assertEqual(names(a.library[:2]), ["Goblin B", "Goblin A"])
        self.assertEqual(sorted(names(a.library[2:])), ["Bear", "Forest", "Ogre"])
        self.assertEqual(a.hand, [])

    def test_goblin_recruiter_with_no_goblins_finds_nothing(self):
        game, _ = table3(script(DONE))
        a = game.seats[0]
        a.library = [BEAR, FOREST, OGRE]
        enter(game, a, GOBLIN_RECRUITER)
        run_stack(game)
        self.assertEqual(sorted(names(a.library)), ["Bear", "Forest", "Ogre"])
        self.assertEqual(a.hand, [])

    def test_tiamat_cast_finds_dragons_with_different_names_and_never_itself(self):
        offered = []
        answers = script("Dragon A", "Dragon B", DONE)

        def policy(prompt, options):
            if PRIORITY_PROMPT.matches(prompt):
                return pick(CAST)(prompt, options)
            if SEARCH_CARD_PROMPT.matches(prompt):
                offered.append(list(options))
            return answers(prompt, options)

        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = lands(7)
        a.hand = [TIAMAT]
        a.library = [DRAGON_A, DRAGON_A, DRAGON_B, BEAR, TIAMAT, DRAGON_SHRINE]
        settle(game)
        self.assertEqual(sorted(names(a.hand)), ["Dragon A", "Dragon B"])
        self.assertNotIn("Tiamat", offered[0])  # "not named Tiamat"
        self.assertIn("Dragon Shrine", offered[0])  # any Dragon card, not only creatures
        self.assertNotIn("Dragon A", offered[1])  # "that each have different names"
        self.assertEqual(sorted(names(a.library)), ["Bear", "Dragon A", "Dragon Shrine", "Tiamat"])

    def test_tiamat_put_onto_the_battlefield_without_being_cast_does_not_search(self):
        game, _ = table3(script("Dragon A", DONE))
        a = game.seats[0]
        a.library = [DRAGON_A, BEAR]
        enter(game, a, TIAMAT)
        run_stack(game)
        self.assertEqual(a.hand, [])
        self.assertEqual(names(a.library), ["Dragon A", "Bear"])


class RevealTopPutAllTests(unittest.TestCase):
    def test_muxus_puts_the_cheap_goblins_onto_the_battlefield_and_the_rest_on_the_bottom(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [GOBLIN_A, BEAR, GOBLIN_SIX, GOBLIN_B, FOREST, DRAGON_A, MARKER, FOREST]
        enter(game, a, MUXUS)
        run_stack(game)
        self.assertEqual(sorted(names(p.card for p in a.battlefield)), ["Goblin A", "Goblin B", "Muxus, Goblin Grandee"])
        self.assertEqual(names(a.library[:2]), ["Marker", "Forest"])  # the seventh and eighth cards were not revealed
        self.assertEqual(sorted(names(a.library[2:])), ["Bear", "Dragon A", "Forest", "Goblin Six"])  # mana value 6 stays
        self.assertEqual(a.hand, [])

    def test_muxus_with_fewer_than_six_cards_reveals_what_there_is(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR, GOBLIN_B]
        enter(game, a, MUXUS)
        run_stack(game)
        self.assertEqual(sorted(names(p.card for p in a.battlefield)), ["Goblin B", "Muxus, Goblin Grandee"])
        self.assertEqual(names(a.library), ["Bear"])


class LookPutOneTests(unittest.TestCase):
    def setUp(self):
        self.top = [BEAR, FOREST, DRAGON_SHRINE, DRAGON_A, OGRE, FOREST, DRAGON_B, FOREST]

    def test_ureni_may_put_a_dragon_creature_from_the_top_eight_onto_the_battlefield(self):
        game, _ = table3(script("Dragon B"))
        a = game.seats[0]
        a.library = self.top + [MARKER]
        enter(game, a, URENI)
        run_stack(game)
        self.assertEqual(sorted(names(p.card for p in a.battlefield)), ["Dragon B", "Ureni of the Unwritten"])
        self.assertEqual(names(a.library[:1]), ["Marker"])
        self.assertEqual(len(a.library), 8)
        self.assertNotIn("Dragon B", names(a.library))
        self.assertEqual(a.hand, [])

    def test_ureni_may_take_none_and_the_enchantment_dragon_is_never_offered(self):
        offered = []

        def policy(prompt, options):
            offered.append(list(options))
            return pick(NONE_TAKEN)(prompt, options)

        game, _ = table3(policy)
        a = game.seats[0]
        a.library = self.top + [MARKER]
        enter(game, a, URENI)
        run_stack(game)
        self.assertEqual(names(p.card for p in a.battlefield), ["Ureni of the Unwritten"])
        self.assertEqual(sorted(offered[0]), ["Dragon A", "Dragon B", NONE_TAKEN])
        self.assertEqual(names(a.library[:1]), ["Marker"])
        self.assertEqual(len(a.library), 9)


class SearchBelowPowerTests(unittest.TestCase):
    def test_sisay_finds_a_legendary_permanent_card_cheaper_than_her_power(self):
        offered = []

        def policy(prompt, options):
            if SEARCH_CARD_PROMPT.matches(prompt):
                offered.append(list(options))
            return pick("Legend One")(prompt, options)

        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(SISAY)] + lands(5)
        a.library = [LEGEND_TWO, LEGEND_ONE, LEGEND_SPELL, BEAR]
        activate(game, a, "Search your library for a legendary permanent card")
        self.assertEqual(offered, [["Legend One"]])  # mana value 2 is not less than power 2; a sorcery is not a permanent card
        self.assertIn("Legend One", names(p.card for p in a.battlefield))
        self.assertEqual(sorted(names(a.library)), ["Bear", "Legend Spell", "Legend Two"])


if __name__ == "__main__":
    unittest.main()
