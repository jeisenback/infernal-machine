"""Transmute Artifact, from its real Oracle text: "Sacrifice an artifact. If you do, search your library for an artifact card. If that
card's mana value is less than or equal to the sacrificed artifact's mana value, put it onto the battlefield. If it's greater, you may pay
{X}, where X is the difference. If you do, put it onto the battlefield. If you don't, put it into its owner's graveyard. Then shuffle." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import spell_effects
from infernal_machine.game import Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, RELIC, lands, pick, real, table3

TRANSMUTE = real("Transmute Artifact", "{U}{U}", "Sorcery", "Sacrifice an artifact. If you do, search your library for an artifact card. If "
                 "that card's mana value is less than or equal to the sacrificed artifact's mana value, put it onto the battlefield. If it's "
                 "greater, you may pay {X}, where X is the difference. If you do, put it onto the battlefield. If you don't, put it into its "
                 "owner's graveyard. Then shuffle.", colors=("U",))
ANVIL = Card(name="Anvil", type_line="Artifact", mana_cost="{3}", cmc=3.0)
TRINKET = Card(name="Trinket", type_line="Artifact", mana_cost="{1}", cmc=1.0)


def transmute(find, mana=0, artifact=True, pay=True):
    game, _ = table3(pick(find, "Pay" if pay else "Don't pay"))
    a = game.seats[0]
    a.battlefield = ([Permanent(RELIC)] if artifact else [Permanent(BEAR)]) + lands(mana)
    a.library = [ANVIL, TRINKET]
    game._apply_effects(StackItem(TRANSMUTE, a, spell_effects(TRANSMUTE)))
    return a


def names(cards):
    return sorted(c.name for c in cards)


class TransmuteArtifactTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(TRANSMUTE), [])

    def test_an_artifact_of_no_greater_mana_value_comes_in_free(self):
        a = transmute("Trinket", pay=False)  # nothing to pay: it comes in even for a player who would pay nothing
        self.assertEqual(([p.card.name for p in a.battlefield], names(a.graveyard)), (["Trinket"], ["Relic"]))

    def test_a_greater_one_comes_in_when_the_difference_is_paid(self):
        a = transmute("Anvil", mana=2)
        self.assertEqual(([p.card.name for p in a.battlefield if p.card.name == "Anvil"], sum(p.tapped for p in a.battlefield)), (["Anvil"], 2))

    def test_unpaid_it_goes_to_the_graveyard(self):
        a = transmute("Anvil", mana=1)  # the difference is {2}
        self.assertEqual((names(a.graveyard), [p.card.name for p in a.battlefield if p.card.name == "Anvil"]), (["Anvil", "Relic"], []))

    def test_without_an_artifact_nothing_is_searched(self):
        a = transmute("Anvil", artifact=False)
        self.assertEqual(([c.name for c in a.library], a.graveyard), (["Anvil", "Trinket"], []))


if __name__ == "__main__":
    unittest.main()
