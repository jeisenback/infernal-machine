"""From the cards' real Oracle text: a named legendary token ("create Voja, a legendary 2/2 green and white Wolf creature token", CR 111.4:
the token has the name the effect gives it), Kiora's Scion of the Deep behind threshold, and Shoreline Looter's "Then discard a card unless there
are seven or more cards in your graveyard"."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, activate, fire, real, table3

TOLSIMIR = real("Tolsimir Wolfblood", "{4}{G}{W}", "Legendary Creature — Elf Warrior", "Other green creatures you control get +1/+1.\nOther white "
                "creatures you control get +1/+1.\n{T}: Create Voja, a legendary 2/2 green and white Wolf creature token.", "3", "4",
                colors=("G", "W"))
KIORA = real("Kiora, the Rising Tide", "{2}{U}", "Legendary Creature — Merfolk Noble", "When Kiora enters, draw two cards, then discard two "
             "cards.\nThreshold — Whenever Kiora attacks, if there are seven or more cards in your graveyard, you may create Scion of the Deep, "
             "a legendary 8/8 blue Octopus creature token.", "3", "2", colors=("U",))
LOOTER = real("Shoreline Looter", "{1}{U}", "Creature — Rat Rogue", "This creature can't be blocked.\nThreshold — Whenever this creature deals "
              "combat damage to a player, draw a card. Then discard a card unless there are seven or more cards in your graveyard.", "1", "1",
              colors=("U",))


def tokens(seat):
    return [p for p in seat.battlefield if p.card.type_line.startswith("Token")]


class NamedTokenTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (TOLSIMIR, KIORA, LOOTER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_voja_is_a_named_legendary_token(self):
        game, _ = table3()
        a = game.seats[0]
        tolsimir = Permanent(TOLSIMIR)
        a.battlefield = [tolsimir]
        activate(game, a, "Tolsimir")
        [voja] = tokens(a)
        self.assertEqual((voja.card.name, voja.card.type_line, game.power(voja), game.toughness(voja)),
                         ("Voja", "Token Legendary Creature — Wolf", 4, 4))  # 2/2, +1/+1 for green and +1/+1 for white

    def test_kiora_makes_the_scion_only_with_threshold(self):
        for cards, made in ((7, 1), (6, 0)):
            game, _ = table3()
            a = game.seats[0]
            kiora = Permanent(KIORA)
            a.battlefield, a.graveyard = [kiora], [FOREST] * cards
            fire(game, a, kiora, "attacks")
            self.assertEqual([p.card.name for p in tokens(a)], ["Scion of the Deep"] * made, cards)


class ShorelineLooterTests(unittest.TestCase):
    def test_it_discards_only_without_threshold(self):
        for cards, kept in ((6, 1), (7, 2)):  # a card in hand, then one drawn: one is discarded without threshold
            game, _ = table3()
            a = game.seats[0]
            looter = Permanent(LOOTER)
            a.battlefield, a.hand, a.library, a.graveyard = [looter], [FOREST], [FOREST] * 3, [FOREST] * cards
            fire(game, a, looter, "combat_damage_to_player")
            self.assertEqual(len(a.hand), kept, cards)


if __name__ == "__main__":
    unittest.main()
