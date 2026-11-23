"""Issue #846: "You may have this creature assign its combat damage as though it weren't blocked." (CR 510.1c), from the cards' real
Oracle text. All nine cards whose only gap it was are fully playable. Thorn Elemental (7/7), blocked by an Ogre (3/3): its controller
says yes and the defending player takes 7 while the Ogre takes none (and still deals its 3); says no and the Ogre takes the damage. A
7/7 without the ability, or the Elemental once it has lost its abilities, isn't asked; an unblocked one isn't asked either."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import AS_UNBLOCKED_PROMPT
from infernal_machine.game import Permanent
from tests.helpers import COURSEWORK, OGRE, combat_damage, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Deathcoil Wurm", "Imaryll, Elfhame Elite", "Lone Wolf", "Pride of Lions", "Rhox", "Spinebiter", "Thorn Elemental",
         "Tornado Elemental", "Wolf Pack"]
THORN = REAL["Thorn Elemental"]
GIANT = Card(name="Craw Giant", mana_cost="{5}{G}", type_line="Creature — Giant", power="7", toughness="7")

# The guards these tests are there to catch (python tools/mutate.py tests.test_as_unblocked).
MUTATIONS = [
    ("infernal_machine/combat.py", 'return controller.player.choose(AS_UNBLOCKED_PROMPT(self.game.label(attacker)), ["Yes", "No"]) == 0',
     "return True", "its controller's choice"),
    ("infernal_machine/combat.py", "        if self.game.loses_abilities(attacker) or not any(", "        if not any(",
     "not once it has lost its abilities"),
    ("infernal_machine/combat.py", ' or not any(r.kind == "as_unblocked" for r in combat_restrictions(attacker.card)):\n            return False',
     ":\n            return False", "only a creature with the ability"),
]


def fight(card, answer=0, blocked=True, lost=False):
    """Seat 0's `card` attacks seat 1, blocked by an Ogre (or not); its controller answers `answer` (0: yes)."""
    game, players = table3(lambda prompt, options: answer if AS_UNBLOCKED_PROMPT.matches(prompt) else 0)
    a, b, _ = game.seats
    attacker, ogre = Permanent(card, sick=False), Permanent(OGRE)
    a.battlefield, b.battlefield = [attacker], [ogre]
    if lost:
        b.battlefield.append(Permanent(COURSEWORK, attached_to=attacker))
    combat_damage(game, attacker, b, [ogre] if blocked else [])
    asked = [p for p, _ in players[0].prompts if AS_UNBLOCKED_PROMPT.matches(p)]
    return b, attacker, ogre, asked


class AsUnblockedTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_yes_the_player_takes_it_and_the_blocker_none(self):
        b, thorn, ogre, asked = fight(THORN)
        self.assertEqual((40 - b.life, ogre.damage, thorn.damage, len(asked)), (7, 0, 3, 1))

    def test_no_the_blocker_takes_it(self):
        b, _, ogre, _ = fight(THORN, answer=1)
        self.assertEqual((40 - b.life, ogre in b.battlefield), (0, False))

    def test_not_asked_without_it_lost_or_unblocked(self):
        for card, lost, blocked in ((GIANT, False, True), (THORN, True, True), (THORN, False, False)):
            b, _, _, asked = fight(card, lost=lost, blocked=blocked)
            self.assertEqual((asked, 40 - b.life), ([], 0 if blocked else 7), (card.name, lost, blocked))


if __name__ == "__main__":
    unittest.main()
