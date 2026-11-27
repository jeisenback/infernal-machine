"""Arrest-style Auras (CR 602.5): "Enchanted creature can't attack or block, and its activated abilities can't be activated.", from the
cards' real Oracle text. All 12 cards whose only gap it was are fully playable ("Enchanted permanent" and "Enchanted artifact" too).
A Seer ("{T}: Draw a card.") under Arrest can't attack, block or draw; the Seer beside it still can; once Arrest is destroyed it can
again. A mana creature under Prison Term adds no mana; under Faith's Fetters ("... unless they're mana abilities") it still does, while
its "{T}: Draw a card." is stopped. Petrify on a noncreature artifact stops its ability."""

import unittest

from infernal_machine.effects import CANT_ATTACK, CANT_BLOCK
from infernal_machine.game import ACTIVATE, Permanent
from tests.helpers import real, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Arrest", "Faith's Fetters", "Lawmage's Binding", "Nahiri's Binding", "Petrify", "Planar Disruption", "Prison Sentence",
         "Prison Term", "Realmbreaker's Grasp", "Secure Detention", "Suppression Bonds"]  # (and Stasis Cocoon, playable
# too, though the smoke table has no artifact for it to enchant)
ARREST, TERM, FETTERS, PETRIFY = REAL["Arrest"], REAL["Prison Term"], REAL["Faith's Fetters"], REAL["Petrify"]
SEER = real("Seer", "{1}{U}", "Creature — Human Wizard", "{T}: Draw a card.", "1", "1")
DRUID = real("Druid", "{G}", "Creature — Elf Druid", "{T}: Add {G}.\n{1}, {T}: Draw a card.", "1", "1")
ORB = real("Orb", "{2}", "Artifact", "{T}: Draw a card.")

# The guards these tests are there to catch (python tools/mutate.py tests.test_arrest).
MUTATIONS = [
    ("infernal_machine/game.py", "        locks = {NO_ACTIVATING} if mana else {NO_ACTIVATING, NO_ACTIVATING_NONMANA}",
     "        locks = set()", "its activated abilities can't be activated"),
    ("infernal_machine/game.py", "        locks = {NO_ACTIVATING} if mana else {NO_ACTIVATING, NO_ACTIVATING_NONMANA}",
     "        locks = {NO_ACTIVATING, NO_ACTIVATING_NONMANA}", "mana abilities stay under Faith's Fetters"),
    ("infernal_machine/game.py", "        locks = {NO_ACTIVATING} if mana else {NO_ACTIVATING, NO_ACTIVATING_NONMANA}",
     "        locks = {NO_ACTIVATING_NONMANA} if mana else {NO_ACTIVATING, NO_ACTIVATING_NONMANA}", "mana abilities stop under Prison Term"),
]


def draws(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE) and "Draw a card" in x]


def table(host_card, aura):
    game, _ = table3()
    a = game.seats[0]
    host = Permanent(host_card, sick=False)
    a.battlefield = [host, Permanent(aura, attached_to=host)]
    return game, a, host


class ArrestTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_it_cant_attack_block_or_activate_until_the_aura_leaves(self):
        game, a, seer = table(SEER, ARREST)
        free = Permanent(SEER, sick=False)
        a.battlefield.append(free)
        self.assertEqual((game.has_keyword(seer, CANT_ATTACK), game.has_keyword(seer, CANT_BLOCK), len(draws(game, a))), (True, True, 1))
        self.assertFalse(game.has_keyword(free, CANT_ATTACK))
        game.destroy(a.battlefield[1])
        self.assertEqual((game.has_keyword(seer, CANT_ATTACK), len(draws(game, a))), (False, 2))

    def test_its_mana_ability_too_unless_the_aura_says_otherwise(self):
        game, a, druid = table(DRUID, TERM)
        self.assertEqual(game._mana_sources(a), [])
        game, a, druid = table(DRUID, FETTERS)
        self.assertEqual(([s.permanent for s in game._mana_sources(a)], draws(game, a)), ([druid], []))

    def test_an_enchanted_artifact(self):
        game, a, _ = table(ORB, PETRIFY)
        self.assertEqual(draws(game, a), [])


if __name__ == "__main__":
    unittest.main()
