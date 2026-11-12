"""Land searches, batch 2, from the cards' real Oracle text: Kodama of the West Tree ("Whenever a modified creature you control deals combat
damage to a player"), Scapeshift (sacrifice any number of lands, then find that many) and Entish Restoration (two basic lands, or three
if you control a creature with power 4 or greater)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, PLAINS, RAINBOW, SWAMP, lands, pick, real, run_stack, table3

KODAMA = real("Kodama of the West Tree", "{2}{G}", "Legendary Creature — Spirit", "Reach\nModified creatures you control have trample. "
              "(Equipment, Auras you control, and counters are modifications.)\nWhenever a modified creature you control deals combat damage "
              "to a player, search your library for a basic land card, put it onto the battlefield tapped, then shuffle.", "3", "3", colors=("G",))
SCAPESHIFT = real("Scapeshift", "{2}{G}{G}", "Sorcery", "Sacrifice any number of lands. Search your library for up to that many land cards, put "
                  "them onto the battlefield tapped, then shuffle.", colors=("G",))
ENTISH = real("Entish Restoration", "{2}{G}", "Instant", "Sacrifice a land. Search your library for up to two basic land cards, put them onto "
              "the battlefield tapped, then shuffle. If you control a creature with power 4 or greater, instead search your library for up to "
              "three basic land cards, put them onto the battlefield tapped, then shuffle.", colors=("G",))
CARDS = (KODAMA, SCAPESHIFT, ENTISH)

VALAKUT = Card(name="Valakut", type_line="Land")  # a nonbasic land: "land cards", not only basic ones
GIANT = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "4", "4", colors=("R",))


def cast(game, seat, card, mana):
    seat.battlefield += mana
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


def found(seat):
    return sorted(p.card.name for p in seat.battlefield if p.card.name in ("Forest", "Plains", "Swamp", "Valakut"))


class LandSearches2Tests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_kodama_finds_a_land_when_a_modified_creature_deals_combat_damage(self):
        for modified, lands_found in ((True, ["Forest"]), (False, [])):
            game, _ = table3()
            a, b = game.seats[0], game.seats[1]
            bear = Permanent(BEAR)
            if modified:
                bear.counters["+1/+1"] = 1
            a.battlefield, a.library = [Permanent(KODAMA), bear], [FOREST]
            game.damage(b, 2, bear, combat=True)
            run_stack(game)
            self.assertEqual(found(a), lands_found, modified)

    def test_scapeshift_finds_as_many_lands_as_were_sacrificed(self):
        game, _ = table3(pick("2"))
        a = game.seats[0]
        a.library = [VALAKUT, FOREST, SWAMP, PLAINS]
        cast(game, a, SCAPESHIFT, lands(4))  # (tapped for the spell, then sacrificed)
        self.assertEqual((len(found(a)), sum(p.card is RAINBOW for p in a.battlefield)), (2, 2))
        self.assertTrue(all(p.tapped for p in a.battlefield if p.card is not RAINBOW))

    def test_scapeshift_sacrificing_nothing_finds_nothing(self):
        game, _ = table3(pick("0"))
        a = game.seats[0]
        a.library = [VALAKUT, FOREST]
        cast(game, a, SCAPESHIFT, lands(4))
        self.assertEqual((found(a), len(a.battlefield)), ([], 4))

    def test_entish_restoration_finds_three_with_a_big_creature(self):
        for creature, count in ((GIANT, 3), (OGRE, 2)):
            game, _ = table3()
            a = game.seats[0]
            a.library = [FOREST, SWAMP, PLAINS, FOREST]
            a.battlefield = [Permanent(creature)]
            cast(game, a, ENTISH, lands(3))
            self.assertEqual((len(found(a)), sum(p.card is RAINBOW for p in a.battlefield)), (count, 2), creature.name)


if __name__ == "__main__":
    unittest.main()
