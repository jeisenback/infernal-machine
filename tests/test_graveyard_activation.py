"""Abilities that work from the graveyard with "Exile this card from your graveyard" as a cost: Bonebind Orator (return another target creature
card), Spectral Steel (another Aura or Equipment card), Soul of Zendikar and Stone Docent (sorcery speed). The targets are chosen while the
card is still in the graveyard, so "another" leaves it out; the card is exiled as the cost is paid."""

import unittest

from infernal_machine.game import ACTIVATE_GRAVEYARD, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, lands, real, run_stack, table3

ORATOR = real("Bonebind Orator", "{1}{B}", "Creature — Squirrel Warlock Bard", "{3}{B}, Exile this card from your graveyard: Return another "
              "target creature card from your graveyard to your hand.", "2", "2", colors=("B",))
STEEL = real("Spectral Steel", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +2/+2.\n{1}{W}, Exile this card from "
             "your graveyard: Return another target Aura or Equipment card from your graveyard to your hand.", colors=("W",))
ZENDIKAR = real("Soul of Zendikar", "{4}{G}{G}", "Creature — Avatar", "Reach\n{3}{G}{G}: Create a 3/3 green Beast creature token.\n{3}{G}{G}, "
                "Exile this card from your graveyard: Create a 3/3 green Beast creature token.", "6", "6", colors=("G",))
DOCENT = real("Stone Docent", "{1}{W}", "Creature — Spirit Chimera", "{W}, Exile this card from your graveyard: You gain 2 life. Surveil 1. "
              "Activate only as a sorcery.", "3", "1", colors=("W",))
AURA = real("Pacifism", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature can't attack or block.", colors=("W",))
BLADE = real("Short Sword", "{1}", "Artifact — Equipment", "Equipped creature gets +1/+1.\nEquip {1}")


def setup(graveyard, n=6):
    game, _ = table3()
    a = game.seats[0]
    a.battlefield = lands(n)
    a.graveyard = list(graveyard)
    a.library = [BEAR] * 5
    return game, a


def activate(game, a, name):
    game._perform(a, ACTIVATE_GRAVEYARD + name)
    run_stack(game)


def names(cards):
    return sorted(c.name for c in cards)


class GraveyardActivationTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (ORATOR, STEEL, ZENDIKAR, DOCENT):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_returns_another_card_and_exiles_itself(self):
        game, a = setup([ORATOR, OGRE])
        self.assertIn(ACTIVATE_GRAVEYARD + "Bonebind Orator", game.legal_actions(a))
        activate(game, a, "Bonebind Orator")
        self.assertEqual((names(a.hand), names(a.graveyard), names(a.exile)), (["Ogre"], [], ["Bonebind Orator"]))
        self.assertEqual(sum(p.tapped for p in a.battlefield), 4)

    def test_not_offered_with_no_other_card_to_return(self):
        game, a = setup([ORATOR, AURA])
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Bonebind Orator", game.legal_actions(a))  # an Aura is not a creature card
        game, a = setup([ORATOR])
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Bonebind Orator", game.legal_actions(a))  # it is not "another" card

    def test_an_identical_card_is_another_card(self):
        game, a = setup([ORATOR, ORATOR])
        activate(game, a, "Bonebind Orator")
        self.assertEqual((names(a.hand), names(a.exile)), (["Bonebind Orator"], ["Bonebind Orator"]))

    def test_another_aura_or_equipment_card(self):
        game, a = setup([STEEL, OGRE, BLADE, AURA])
        activate(game, a, "Spectral Steel")
        self.assertEqual(len(a.hand), 1)
        self.assertIn(a.hand[0].name, ("Short Sword", "Pacifism"))
        self.assertEqual(names(a.exile), ["Spectral Steel"])
        game, a = setup([STEEL, OGRE])
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Spectral Steel", game.legal_actions(a))

    def test_an_ability_without_targets(self):
        game, a = setup([ZENDIKAR])
        activate(game, a, "Soul of Zendikar")
        beasts = [p for p in a.battlefield if "Land" not in p.card.type_line]
        self.assertEqual(([p.card.name for p in beasts], names(a.exile), a.graveyard), (["Beast"], ["Soul of Zendikar"], []))
        self.assertEqual((beasts[0].card.power, beasts[0].card.toughness), ("3", "3"))

    def test_the_mana_is_needed(self):
        game, a = setup([ORATOR, OGRE], n=3)
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Bonebind Orator", game.legal_actions(a))

    def test_only_at_sorcery_speed_when_it_says_so(self):
        game, a = setup([DOCENT])
        self.assertIn(ACTIVATE_GRAVEYARD + "Stone Docent", game.legal_actions(a))
        game.step = "beginning_of_combat"
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Stone Docent", game.legal_actions(a))
        game, a = setup([ZENDIKAR])
        game.step = "beginning_of_combat"
        self.assertIn(ACTIVATE_GRAVEYARD + "Soul of Zendikar", game.legal_actions(a))  # the other one is at instant speed


if __name__ == "__main__":
    unittest.main()
