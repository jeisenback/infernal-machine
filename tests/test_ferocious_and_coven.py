"""Ferocious and Coven, from the cards' real Oracle text: Coven ("if you control three or more creatures with different powers": Dawnhart
Wardens), Temur Battle Rage ("That creature also gains trample until end of turn if you control a creature with power 4 or greater.")
and Stubborn Denial ("If you control a creature with power 4 or greater, counter that spell instead.": no paying {1} then)."""

import unittest

from infernal_machine.effects import spell_effects
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, DIVINATION, OGRE, fire, lands, pick, real, run_stack, table3

WARDENS = real("Dawnhart Wardens", "{1}{G}{W}", "Creature — Human Warlock", "Vigilance\nCoven — At the beginning of combat on your turn, if "
               "you control three or more creatures with different powers, creatures you control get +1/+0 until end of turn.", "3", "3",
               colors=("G", "W"))
RAGE = real("Temur Battle Rage", "{1}{R}", "Instant", "Target creature gains double strike until end of turn.\nFerocious — That creature also "
            "gains trample until end of turn if you control a creature with power 4 or greater.", colors=("R",))
DENIAL = real("Stubborn Denial", "{U}", "Instant", "Counter target noncreature spell unless its controller pays {1}.\nFerocious — If you "
              "control a creature with power 4 or greater, counter that spell instead.", colors=("U",))
CARDS = (WARDENS, RAGE, DENIAL)
GIANT = real("Hill Giant", "{3}{R}{R}", "Creature — Giant", "", "4", "4", colors=("R",))
ELF = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))


class FerociousAndCovenTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_coven_needs_three_different_powers(self):
        for others, pumped in (([ELF, BEAR], True), ([BEAR, BEAR], False)):  # powers 3, 1, 2; or 3, 2, 2
            game, _ = table3()
            a = game.seats[0]
            wardens = Permanent(WARDENS)
            a.battlefield = [wardens] + [Permanent(c) for c in others]
            fire(game, a, wardens, "combat")
            self.assertEqual(game.power(wardens), 4 if pumped else 3, [c.name for c in others])

    def test_temur_battle_rage_adds_trample_only_with_a_big_creature(self):
        for big, trample in ((GIANT, True), (OGRE, False)):  # power 4, or power 3
            game, _ = table3(pick("Bear"))
            a = game.seats[0]
            bear = Permanent(BEAR)
            a.battlefield, a.hand = [bear, Permanent(big)] + lands(2), [RAGE]
            game._perform(a, CAST + RAGE.name)
            run_stack(game)
            self.assertEqual((game.has_keyword(bear, "double strike"), game.has_keyword(bear, "trample")), (True, trample), big.name)

    def test_stubborn_denial_cannot_be_paid_for_with_a_big_creature(self):
        for big, countered in ((GIANT, True), (OGRE, False)):  # with power 3 the spell's controller pays {1}
            game, _ = table3(None, lambda prompt, options: 0)  # B pays when asked
            a, b = game.seats[0], game.seats[1]
            a.battlefield = [Permanent(big)]
            b.battlefield = lands(1)
            spell = StackItem(DIVINATION, b, spell_effects(DIVINATION) or [], [])
            game.stack.append(spell)
            for effect in spell_effects(DENIAL) or []:
                effect.resolve(game, a, spell)
            self.assertEqual((spell in game.stack, DIVINATION in b.graveyard), (not countered, countered), big.name)


if __name__ == "__main__":
    unittest.main()
