"""Casting without paying the mana cost, batch 8 (#655), from the cards' real Oracle text: Submerge and the Legates ("If an opponent controls a
Forest and you control an Island, you may cast this spell without paying its mana cost."), "Put target creature on top of its owner's
library.", Sunbird's Invocation, Cosmic Cube and Rashmi, Eternities Crafter."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, attack_all, lands, pick, real, run_stack, table, table3, take_turn_attacking

SUBMERGE = real("Submerge", "{4}{U}", "Instant", "If an opponent controls a Forest and you control an Island, you may cast this spell "
                "without paying its mana cost.\nPut target creature on top of its owner's library.", colors=("U",))
LEGATE = real("Saprazzan Legate", "{3}{U}", "Creature — Merfolk Soldier", "If an opponent controls a Mountain and you control an Island, "
              "you may cast this spell without paying its mana cost.\nFlying", "1", "3", colors=("U",))
SUNBIRD = real("Sunbird's Invocation", "{5}{R}", "Enchantment", "Whenever you cast a spell from your hand, reveal the top X cards of your "
               "library, where X is that spell's mana value. You may cast a spell with mana value X or less from among cards revealed "
               "this way without paying its mana cost. Put the rest on the bottom of your library in a random order.", colors=("R",))
RASHMI = real("Rashmi, Eternities Crafter", "{2}{G}{U}", "Legendary Creature — Elf Druid", "Whenever you cast your first spell each turn, "
              "reveal the top card of your library. You may cast it without paying its mana cost if it's a spell with lesser mana value. "
              "If you don't cast it, put it into your hand.", "2", "3", colors=("G", "U"))
CUBE = real("Cosmic Cube", "{5}", "Artifact", "Ward {2}\nWhenever you attack, look at the top six cards of your library. You may cast a "
            "spell from among them with mana value less than or equal to the greatest power among attacking creatures you control without "
            "paying its mana cost. Put the rest on the bottom of your library in a random order.")
CARDS = (SUBMERGE, LEGATE, SUNBIRD, RASHMI, CUBE)

ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
OGRE = real("Gray Ogre", "{2}{R}", "Creature — Ogre", "", "2", "2", colors=("R",))  # mana value 3
GIANT = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "3", "3", colors=("R",))  # mana value 4
DRAKE = real("Wind Drake", "{2}{U}", "Creature — Drake", "Flying", "2", "2", colors=("U",))  # mana value 3
DRAGON = real("Shivan Dragon", "{4}{R}{R}", "Creature — Dragon", "Flying\n{R}: Shivan Dragon gets +1/+0 until end of turn.", "5", "5",
              colors=("R",))  # mana value 6
SPHINX = real("Wind Sphinx", "{2}{U}", "Creature — Sphinx", "Flying", "3", "3", colors=("U",))  # a 3/3 attacker


def names(cards):
    return [c.name for c in cards]


def on_battlefield(seat, name):
    return any(p.card.name == name for p in seat.battlefield)


class CastFree8Tests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_submerge_puts_the_creature_on_top_for_free(self):
        game, _ = table3(pick("Ogre"))
        a, b, _ = game.seats
        a.hand, a.battlefield = [SUBMERGE], [Permanent(ISLAND)]
        b.battlefield, b.library = [Permanent(FOREST), Permanent(OGRE)], [FOREST]
        game._perform(a, CAST + "Submerge")
        run_stack(game)
        self.assertEqual((b.library[0].name, on_battlefield(b, "Gray Ogre")), ("Gray Ogre", False))
        self.assertFalse(a.battlefield[0].tapped)  # nothing was paid

    def test_submerge_is_offered_free_only_when_both_lands_are_there(self):
        for theirs, mine, offered in ((FOREST, ISLAND, True), (MOUNTAIN, ISLAND, False), (FOREST, MOUNTAIN, False)):
            game, _ = table3()
            a, b, _ = game.seats
            a.hand, a.battlefield, b.battlefield = [SUBMERGE], [Permanent(mine)], [Permanent(theirs), Permanent(BEAR)]
            self.assertEqual(any(x.startswith(CAST + "Submerge") for x in game.legal_actions(a)), offered, (theirs.name, mine.name))

    def test_a_legate_is_free_against_a_mountain(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.hand, a.battlefield, b.battlefield = [LEGATE], [Permanent(ISLAND)], [Permanent(MOUNTAIN)]
        game._perform(a, CAST + "Saprazzan Legate")
        run_stack(game)
        self.assertTrue(on_battlefield(a, "Saprazzan Legate"))

    def test_sunbirds_invocation_casts_one_spell_no_bigger_than_the_spell_cast(self):
        game, _ = table3(pick("Shivan Dragon", "Wind Drake"))
        a = game.seats[0]
        a.battlefield = [Permanent(SUNBIRD)] + lands(3)
        a.hand, a.library = [OGRE], [DRAGON, DRAKE, FOREST, FOREST]
        game._perform(a, CAST + "Gray Ogre")
        run_stack(game)
        self.assertTrue(on_battlefield(a, "Wind Drake"))  # mana value 3: the Dragon's 6 is too big to be offered
        self.assertEqual(sorted(names(a.library)), ["Forest", "Forest", "Shivan Dragon"])

    def test_rashmi_casts_a_cheaper_spell_or_takes_the_card(self):
        for top in (DRAKE, GIANT):  # under a Hill Giant: the Drake (3) is cheaper; under a Gray Ogre: the Giant (4) is not
            game, _ = table3(pick("Yes"))
            a = game.seats[0]
            a.battlefield = [Permanent(RASHMI)] + lands(4)
            a.hand, a.library = [GIANT if top is not GIANT else OGRE], [top, FOREST]
            spell = a.hand[0]
            game._perform(a, CAST + spell.name)
            run_stack(game)
            lesser = top.cmc < spell.cmc
            self.assertEqual(on_battlefield(a, top.name), lesser, top.name)
            self.assertEqual(top.name in names(a.hand), not lesser, top.name)

    def test_cosmic_cube_caps_the_free_spell_at_the_greatest_attacking_power(self):
        def policy(prompt, options):
            return attack_all(prompt, options) if any("ttack" in o for o in options) else pick("Shivan Dragon", "Wind Drake")(prompt, options)
        game, _, _ = table(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(CUBE), Permanent(SPHINX)]
        a.library = [FOREST, DRAGON, DRAKE] + [FOREST] * 6  # (the draw step takes the first Forest)
        take_turn_attacking(game, a)
        self.assertEqual((on_battlefield(a, "Wind Drake"), on_battlefield(a, "Shivan Dragon")), (True, False))


if __name__ == "__main__":
    unittest.main()
