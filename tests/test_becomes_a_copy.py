"""Permanents that become a copy of another, from the cards' real Oracle text: Mirage Mirror (of a target permanent until end of turn),
Shifting Woodland (of a permanent card in your graveyard until end of turn), The Mycosynth Gardens (of an artifact you control with mana
value X, for good) and Likeness Looter (of a creature card in your graveyard with mana value X, keeping flying and the ability)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, activate, end_turn, lands, pick, real, table3

MIRROR = real("Mirage Mirror", "{3}", "Artifact", "{2}: This artifact becomes a copy of target artifact, creature, enchantment, or land until "
              "end of turn.")
WOODLAND = real("Shifting Woodland", "", "Land", "This land enters tapped unless you control a Forest.\n{T}: Add {G}.\nDelirium — {2}{G}{G}: "
                "This land becomes a copy of target permanent card in your graveyard until end of turn. Activate only if there are four or "
                "more card types among cards in your graveyard.")
GARDENS = real("The Mycosynth Gardens", "", "Land — Sphere", "{T}: Add {C}.\n{1}, {T}: Add one mana of any color.\n{X}, {T}: This land "
               "becomes a copy of target nontoken artifact you control with mana value X.")
LOOTER = real("Likeness Looter", "{U}{B}", "Creature — Faerie Shapeshifter", "Flying\n{T}: Draw a card, then discard a card.\n{X}: This "
              "creature becomes a copy of target creature card in your graveyard with mana value X, except it has flying and this ability. "
              "Activate only as a sorcery.", "1", "1", colors=("B", "U"))
CARDS = (MIRROR, WOODLAND, GARDENS, LOOTER)

GIANT = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "3", "3", colors=("R",))  # mana value 4
COURSER = real("Centaur Courser", "{2}{G}", "Creature — Centaur Warrior", "", "3", "3", colors=("G",))  # mana value 3
RING = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")  # mana value 1
TALISMAN = real("Mind Stone", "{2}", "Artifact", "{T}: Add {C}.\n{1}, {T}, Sacrifice this artifact: Draw a card.")  # mana value 2
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.", colors=("R",))


def find(seat, card):
    return next(p for p in seat.battlefield if p.card is card or p.original is card)


class BecomesACopyTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_mirage_mirror_copies_until_end_of_turn(self):
        game, _ = table3(pick("Ogre"))
        a, b = game.seats[0], game.seats[1]
        mirror = Permanent(MIRROR)
        a.battlefield = [mirror] + lands(2)
        b.battlefield = [Permanent(OGRE)]
        activate(game, a, "becomes a copy")
        self.assertEqual((mirror.card.name, mirror.card.power), ("Ogre", "3"))
        end_turn(game, a)
        self.assertEqual(mirror.card.name, "Mirage Mirror")

    def test_shifting_woodland_copies_a_permanent_card_from_the_graveyard_with_delirium(self):
        for graveyard, active in (([OGRE, FOREST, RING, BOLT], True), ([OGRE, FOREST, RING], False)):  # four card types, or three
            game, _ = table3(pick("Ogre"))
            a = game.seats[0]
            woodland = Permanent(WOODLAND)
            a.battlefield, a.graveyard = [woodland] + lands(4), list(graveyard)
            offered = any("becomes a copy" in action for action in game.legal_actions(a))
            self.assertEqual(offered, active, len(graveyard))
            if active:
                activate(game, a, "becomes a copy")
                self.assertEqual(woodland.card.name, "Ogre")
                end_turn(game, a)
                self.assertEqual(woodland.card.name, "Shifting Woodland")

    def test_mycosynth_gardens_copies_an_artifact_with_mana_value_x_for_good(self):
        game, _ = table3(pick("2", "Mind Stone", "Sol Ring"))  # X is 2: Sol Ring (mana value 1) can't be the target
        a = game.seats[0]
        gardens = Permanent(GARDENS)
        a.battlefield = [gardens, Permanent(RING), Permanent(TALISMAN)] + lands(2)
        activate(game, a, "becomes a copy")
        self.assertEqual(gardens.card.name, "Mind Stone")
        end_turn(game, a)
        self.assertEqual(gardens.card.name, "Mind Stone")

    def test_likeness_looter_keeps_flying_and_its_ability(self):
        game, _ = table3(pick("3", "Centaur Courser", "Hill Giant"))  # X is 3: the Giant (mana value 4) can't be the target
        a = game.seats[0]
        looter = Permanent(LOOTER)
        a.battlefield, a.graveyard = [looter] + lands(3), [GIANT, COURSER, BEAR]
        activate(game, a, "becomes a copy")
        self.assertEqual((looter.card.name, game.has_keyword(looter, "flying"), "becomes a copy" in looter.card.oracle_text),
                         ("Centaur Courser", True, True))


if __name__ == "__main__":
    unittest.main()
