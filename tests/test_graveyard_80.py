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


QUINTORIUS = Card(name="Quintorius, Loremaster", mana_cost="{3}{R}{W}", type_line="Legendary Creature — Elephant Cleric", power="4",
                  toughness="4",
                  oracle_text="Vigilance\nAt the beginning of your end step, exile target noncreature, nonland card from your "
                              "graveyard. Create a 3/2 red and white Spirit creature token.\n{1}{R}{W}, {T}, Sacrifice a Spirit: "
                              "Choose target card exiled with Quintorius. You may cast that card this turn without paying its mana "
                              "cost. If that spell would be put into a graveyard, put it on the bottom of its owner's library "
                              "instead.")
DRAW_TWO = Card(name="Study", mana_cost="{2}{U}", cmc=3.0, type_line="Sorcery", oracle_text="Draw two cards.")
CHARM = Card(name="Charm", mana_cost="{1}", cmc=1.0, type_line="Artifact")


class QuintoriusTests(unittest.TestCase):
    def table(self, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.quint = Permanent(QUINTORIUS)
        a.battlefield = [self.quint]
        a.library = [FOREST] * 10
        return game, a

    def end_step(self, game, a):
        fire(game, a, self.quint, "end_step")

    def spirits(self, a):
        return [p for p in a.battlefield if p.card.name == "Spirit"]

    def test_parse(self):
        self.assertEqual(unsupported_lines(QUINTORIUS), [])

    def test_the_end_step_exiles_a_noncreature_nonland_card_and_makes_a_spirit(self):
        game, a = self.table("Study")
        a.graveyard = [DRAW_TWO, GOLEM, FOREST]
        self.end_step(game, a)
        self.assertEqual(([c.name for c in a.exile], len(self.spirits(a))), (["Study"], 1))
        self.assertEqual([c.name for c, in [(c,) for c in a.graveyard]], ["Golem", "Forest"])
        self.assertEqual([c.name for _, c in self.quint.exiled_with], ["Study"])

    def test_the_spell_is_cast_free_and_goes_to_the_bottom_of_the_library(self):
        game, a = self.table("Study", "Study")
        a.graveyard = [DRAW_TWO]
        a.battlefield += lands(3)
        self.end_step(game, a)
        before = len(a.hand)
        activate(game, a, "Choose target card exiled")
        run_stack(game)
        self.assertEqual(len(a.hand) - before, 2)  # it resolved
        self.assertEqual(([c.name for c in a.graveyard], a.library[-1].name, a.exile), ([], "Study", []))
        self.assertEqual(self.spirits(a), [])  # the Spirit was sacrificed

    def test_a_permanent_card_cast_free_enters_the_battlefield(self):
        game, a = self.table("Charm", "Charm")
        a.graveyard = [CHARM]
        a.battlefield += lands(3)
        self.end_step(game, a)
        activate(game, a, "Choose target card exiled")
        run_stack(game)
        self.assertIn("Charm", [p.card.name for p in a.battlefield])

    def test_it_needs_a_spirit_and_an_exiled_card(self):
        game, a = self.table()
        a.battlefield += lands(3)
        self.assertFalse([x for x in game.legal_actions(a) if "Choose target card exiled" in x])  # nothing exiled, no Spirit
        a.battlefield.append(Permanent(Card(name="Spirit", type_line="Token Creature — Spirit", power="3", toughness="2")))
        self.assertFalse([x for x in game.legal_actions(a) if "Choose target card exiled" in x])  # a Spirit, nothing exiled
