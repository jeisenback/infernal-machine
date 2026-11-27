"""Auras that stop one thing of combat, from the cards' real Oracle text: "Enchanted creature can't attack." (Cessation), "... can't
block." (Sluggishness), "... can't block, and its activated abilities can't be activated." (Demotion) and "... can't attack, block,
or crew Vehicles." (Revoke Privileges; Intercessor's Arrest and Bound in Gold also lock its nonmana activated abilities). All seven
cards whose only gap it was are fully playable. Under Cessation a Bear can still block; under Sluggishness it can still attack; under
Demotion it can attack but not block or draw. Under Revoke Privileges it can't crew the Cart (crew 1), and a Bear beside it still
can."""

import unittest

from infernal_machine.effects import CANT_ATTACK, CANT_BLOCK, CANT_CREW
from infernal_machine.game import ACTIVATE, Permanent
from tests.helpers import BEAR, real, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Bound in Gold", "Cessation", "Demotion", "Forced Worship", "Intercessor's Arrest", "Revoke Privileges", "Sluggishness"]
SEER = real("Seer", "{1}{U}", "Creature — Human Wizard", "{T}: Draw a card.", "1", "1")
CART = real("Cart", "{1}", "Artifact — Vehicle", "Crew 1", "3", "3")

# The guards these tests are there to catch (python tools/mutate.py tests.test_attached_restrictions).
MUTATIONS = [
    ("infernal_machine/effects/statics.py", '_ARREST_KEYWORDS = {"attack": {CANT_ATTACK}, "block": {CANT_BLOCK},',
     '_ARREST_KEYWORDS = {"attack": {CANT_ATTACK, CANT_BLOCK}, "block": {CANT_ATTACK, CANT_BLOCK},', "only what it says"),
    ("infernal_machine/effects/statics.py", '            locks = set() if "activated" not in line else',
     '            locks = {NO_ACTIVATING} if "activated" not in line else', "abilities only when it says so"),
    ("infernal_machine/game.py", "            return [p for p in self._crew_candidates(seat, vehicle) if not self.has_keyword(p, CANT_CREW)]",
     "            return self._crew_candidates(seat, vehicle)", "it can't crew"),
]


def enchanted(name, host_card=SEER):
    game, _ = table3()
    a = game.seats[0]
    host = Permanent(host_card, sick=False)
    a.battlefield = [host, Permanent(REAL[name], attached_to=host)]
    return game, a, host


def crews(game, seat):
    return any(x.startswith(ACTIVATE) and "Crew" in x for x in game.legal_actions(seat))


class AttachedRestrictionTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_each_stops_only_what_it_says(self):
        for name, expected in (("Cessation", (True, False, True)), ("Sluggishness", (False, True, True)),
                               ("Demotion", (False, True, False))):
            game, a, seer = enchanted(name)
            draws = any(x.startswith(ACTIVATE) and "Draw a card" in x for x in game.legal_actions(a))
            self.assertEqual((game.has_keyword(seer, CANT_ATTACK), game.has_keyword(seer, CANT_BLOCK), draws), expected, name)

    def test_it_cant_crew_vehicles(self):
        game, a, bear = enchanted("Revoke Privileges", BEAR)
        a.battlefield.append(Permanent(CART))
        self.assertEqual((game.has_keyword(bear, CANT_CREW), crews(game, a)), (True, False))
        a.battlefield.append(Permanent(BEAR, sick=False))
        self.assertTrue(crews(game, a))


if __name__ == "__main__":
    unittest.main()
