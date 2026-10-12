""""When this creature dies, return another target [kind] card from your graveyard to your hand.": Myr Retriever, Dutiful Attendant,
Elderfang Ritualist. "Another" leaves out the dying creature's own card, which is in the graveyard by the time the trigger resolves."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, real, run_stack, table3

RETRIEVER = real("Myr Retriever", "{2}", "Artifact Creature — Myr", "When this creature dies, return another target artifact card from your "
                 "graveyard to your hand.", "1", "1")
ATTENDANT = real("Dutiful Attendant", "{2}{B}", "Creature — Human Warrior", "When this creature dies, return another target creature card "
                 "from your graveyard to your hand.", "1", "2")
RITUALIST = real("Elderfang Ritualist", "{2}{B}", "Creature — Elf Cleric", "When this creature dies, return another target Elf card from your "
                 "graveyard to your hand.", "3", "1")
ARTIFACT = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")
ELF = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1")


def dies(card, graveyard):
    game, _ = table3()
    a = game.seats[0]
    creature = Permanent(card)
    a.battlefield = [creature]
    a.graveyard = list(graveyard)
    game._leave_battlefield(creature, "sacrificed")
    run_stack(game)
    return a


def names(cards):
    return sorted(c.name for c in cards)


class AnotherGraveyardTargetTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (RETRIEVER, ATTENDANT, RITUALIST):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_returns_the_other_card_not_itself(self):
        a = dies(RETRIEVER, [ARTIFACT])
        self.assertEqual((names(a.hand), names(a.graveyard)), (["Sol Ring"], ["Myr Retriever"]))

    def test_with_nothing_else_to_return_it_stays_in_the_graveyard(self):
        a = dies(RETRIEVER, [])
        self.assertEqual((a.hand, names(a.graveyard)), ([], ["Myr Retriever"]))

    def test_an_identical_card_in_the_graveyard_is_another_card(self):
        a = dies(RETRIEVER, [RETRIEVER])
        self.assertEqual((names(a.hand), names(a.graveyard)), (["Myr Retriever"], ["Myr Retriever"]))

    def test_only_the_named_kind(self):
        a = dies(RETRIEVER, [BEAR])
        self.assertEqual((a.hand, names(a.graveyard)), ([], ["Bear", "Myr Retriever"]))
        a = dies(ATTENDANT, [ARTIFACT, OGRE])
        self.assertEqual((names(a.hand), names(a.graveyard)), (["Ogre"], ["Dutiful Attendant", "Sol Ring"]))

    def test_a_creature_subtype(self):
        a = dies(RITUALIST, [OGRE, ELF])
        self.assertEqual(names(a.hand), ["Llanowar Elves"])
        a = dies(RITUALIST, [OGRE])
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
