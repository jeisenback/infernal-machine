"""Graveyard exile, return and cast lines of issue #80: Currency Converter, Quintorius, Excava, Augusta, Renegade Bull and
Sevinne's Reclamation. Lines are the cards' own Oracle text from Scryfall; each has cases where it must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import activate, fire
from tests.test_triggers_80 import FOREST, RELIC, SHRINE, card

CONVERTER = Card(name="Currency Converter", mana_cost="{1}", cmc=1.0, type_line="Artifact",
                 oracle_text="Whenever you discard a card, you may exile that card from your graveyard.\n{2}, {T}: Draw a card, "
                             "then discard a card.\n{T}: Put a card exiled with this artifact into its owner's graveyard. If it's a "
                             "land card, create a Treasure token. If it's a nonland card, create a 2/2 black Rogue creature token.")
GOLEM = Card(name="Golem", mana_cost="{3}", cmc=3.0, type_line="Artifact Creature — Golem", power="3", toughness="3")


class CurrencyConverterTests(unittest.TestCase):
    def table(self, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.converter = Permanent(CONVERTER)
        a.battlefield = [self.converter]
        a.library = [FOREST] * 10
        return game, a

    def discard_and_exile(self, game, a, *cards):
        for c in cards:
            a.hand = [c]
            game.discard(a, 1)
            run_stack(game)

    def tokens(self, a):
        return sorted(p.card.name for p in a.battlefield if p.card.type_line.startswith("Token"))

    def test_parse(self):
        self.assertEqual(unsupported_lines(CONVERTER), [])

    def test_a_nonland_card_becomes_a_rogue(self):
        game, a = self.table("Yes", "Golem")
        self.discard_and_exile(game, a, GOLEM)
        self.assertEqual([c.name for c in a.exile], ["Golem"])
        activate(game, a, "Put a card exiled")
        run_stack(game)
        self.assertEqual((self.tokens(a), [c.name for c in a.graveyard], a.exile), (["Rogue"], ["Golem"], []))
        rogue = next(p for p in a.battlefield if p.card.name == "Rogue")
        self.assertEqual((rogue.card.power, rogue.card.toughness, rogue.card.colors), ("2", "2", ("B",)))

    def test_a_land_card_becomes_a_treasure(self):
        game, a = self.table("Yes", "Forest")
        self.discard_and_exile(game, a, FOREST)
        activate(game, a, "Put a card exiled")
        run_stack(game)
        self.assertEqual((self.tokens(a), [c.name for c in a.graveyard]), (["Treasure"], ["Forest"]))

    def test_you_choose_which_exiled_card(self):
        game, a = self.table("Yes", "Yes", "Forest")
        self.discard_and_exile(game, a, GOLEM, FOREST)
        activate(game, a, "Put a card exiled")
        run_stack(game)
        self.assertEqual((self.tokens(a), [c.name for c in a.exile]), (["Treasure"], ["Golem"]))

    def test_it_cannot_be_activated_with_nothing_exiled_with_it(self):
        game, a = self.table()
        self.assertFalse([x for x in game.legal_actions(a) if "Put a card exiled" in x])

    def test_a_card_exiled_by_something_else_is_not_exiled_with_it(self):
        game, a = self.table()
        a.graveyard = [GOLEM]
        a.exile = []
        game.exile_card_from_graveyard(a, GOLEM, False)  # no source ability is resolving
        self.assertFalse([x for x in game.legal_actions(a) if "Put a card exiled" in x])
