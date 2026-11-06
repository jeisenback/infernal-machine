"""Pauper Spy combo's missing cards (#647), from their real Oracle text: Balustrade Spy (reveal until a land, all into the graveyard),
Mesmeric Fiend (a card exiled from a hand until it leaves, then back to the hand), Overgrown Battlement (a {G} for each creature with
defender), Wall of Roots (a -0/-1 counter for {G}, once each turn, without tapping) and Lotleth Giant (1 damage for each creature card in
your graveyard)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, enter, lands, pick, real, run_stack, table3

SPY = real("Balustrade Spy", "{3}{B}", "Creature — Vampire Rogue", "Flying\nWhen this creature enters, target player reveals cards from the top "
           "of their library until they reveal a land card, then puts those cards into their graveyard.", "2", "3", colors=("B",))
FIEND = real("Mesmeric Fiend", "{1}{B}", "Creature — Nightmare Horror", "When this creature enters, target opponent reveals their hand and you "
             "choose a nonland card from it. Exile that card.\nWhen this creature leaves the battlefield, return the exiled card to its owner's "
             "hand.", "1", "1", colors=("B",))
BATTLEMENT = real("Overgrown Battlement", "{1}{G}", "Creature — Wall", "Defender\n{T}: Add {G} for each creature you control with defender.",
                  "0", "4", colors=("G",))
ROOTS = real("Wall of Roots", "{1}{G}", "Creature — Plant Wall", "Defender\nPut a -0/-1 counter on this creature: Add {G}. Activate only once "
             "each turn.", "0", "5", colors=("G",))
GIANT = real("Lotleth Giant", "{6}{B}", "Creature — Zombie Giant", "Undergrowth — When this creature enters, it deals 1 damage to target opponent "
             "for each creature card in your graveyard.", "6", "5", colors=("B",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
TWO = real("Two Drop", "{1}{G}", "Sorcery", "Draw a card.", colors=("G",))


def green_sources(game, seat):
    return [m for m in game._mana_sources(seat) if m.permanent is not None and "G" in m.types]


class PauperSpyComboTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SPY, FIEND, BATTLEMENT, ROOTS, GIANT):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_balustrade_spy_mills_down_to_and_including_a_land(self):
        game, _ = table3(pick("Player: B"))
        a, b, _ = game.seats
        b.library = [BEAR, OPT, FOREST, OGRE]
        enter(game, a, SPY)
        run_stack(game)
        self.assertEqual(([c.name for c in b.graveyard], [c.name for c in b.library]), (["Bear", "Opt", "Forest"], ["Ogre"]))

    def test_mesmeric_fiend_holds_a_nonland_card_until_it_leaves(self):
        asked = []
        policy = pick("Player: B", "Opt")
        game, _ = table3(lambda prompt, options: asked.append(list(options)) or policy(prompt, options))
        a, b, _ = game.seats
        b.hand = [FOREST, OPT]
        fiend = enter(game, a, FIEND)
        run_stack(game)
        self.assertEqual(([c.name for c in b.hand], [c.name for c in b.exile]), (["Forest"], ["Opt"]))
        self.assertNotIn("Forest", asked[-1])  # a nonland card
        game.destroy(fiend)
        run_stack(game)
        self.assertEqual((sorted(c.name for c in b.hand), b.exile), (["Forest", "Opt"], []))

    def test_overgrown_battlement_counts_only_creatures_with_defender(self):
        game, _ = table3()
        a = game.seats[0]
        battlement = Permanent(BATTLEMENT)
        a.battlefield = [battlement, Permanent(ROOTS), Permanent(BEAR)]
        self.assertEqual(len([m for m in green_sources(game, a) if m.permanent is battlement]), 2)

    def test_wall_of_roots_makes_green_once_a_turn_without_tapping(self):
        game, _ = table3()
        a = game.seats[0]
        roots = Permanent(ROOTS, sick=True)
        a.battlefield, a.hand = [roots, *lands(1, FOREST)], [TWO, OPT]
        game._perform(a, CAST + "Two Drop")
        run_stack(game)
        self.assertEqual((roots.tapped, roots.counters, game.toughness(roots)), (False, {"-0/-1": 1}, 4))
        self.assertEqual(green_sources(game, a), [])  # used this turn (and the Forest is tapped)

    def test_lotleth_giant_deals_damage_for_each_creature_card_in_your_graveyard(self):
        game, _ = table3(pick("Player: B"))
        a, b, _ = game.seats
        a.graveyard = [BEAR, OGRE, OPT]
        life = b.life
        enter(game, a, GIANT)
        run_stack(game)
        self.assertEqual(b.life, life - 2)


if __name__ == "__main__":
    unittest.main()
