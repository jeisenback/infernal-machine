"""Issue #836: "This creature can block an additional creature each combat." (CR 509.1a), from the cards' real Oracle text. All ten cards
whose only gap it was are fully playable (and Tangleclaw Werewolf, double-faced). Ghastbark Twins (7/7) blocks both of two attacking
Ogres and divides its damage between them (CR 510.1d), killing both; a 7/7 without the ability, or the Twins once it has lost its
abilities, blocks only one. Its "whenever this creature blocks" is heard once."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import BLOCK_PROMPT, Attack
from infernal_machine.game import Permanent
from tests.helpers import COURSEWORK, OGRE, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Ghastbark Twins", "Spike-Tailed Ceratops", "Two-Headed Dragon", "Foriysian Interceptor", "Selesnya Sagittars", "Knight of Sorrows",
         "Trueheart Duelist", "Night Market Guard", "Two-Headed Giant of Foriys", "Foriysian Brigade"]
TWINS = REAL["Ghastbark Twins"]
GIANT = Card(name="Craw Giant", mana_cost="{5}{G}", type_line="Creature — Giant", power="7", toughness="7")
WURM = Card(name="Craw Wurm", mana_cost="{4}{G}{G}", type_line="Creature — Wurm", power="6", toughness="4")

# The guards these tests are there to catch (python tools/mutate.py tests.test_extra_blocks).
MUTATIONS = [
    ("infernal_machine/combat.py", '        return 1 + sum(int(r.what) for r in combat_restrictions(blocker.card) if r.kind == "extra_blocks")',
     "        return 2", "only a creature with the ability"),
    ("infernal_machine/combat.py", "        if self.game.loses_abilities(blocker):\n            return 1\n", "", "not once it has lost its abilities"),
    ("infernal_machine/combat.py", "                    if len(blocked) > 1:  # CR 510.1d", "                    if False:  # CR 510.1d",
     "its damage is divided"),
    ("infernal_machine/combat.py", "        if first:  # \"Whenever this creature blocks\"", "        if True:  # \"Whenever this creature blocks\"",
     "it blocks once"),
]


def blocks_all(prompt, options):
    return 1 if BLOCK_PROMPT.matches(prompt) and len(options) > 1 else 0


def two_ogres_attack(blocker_card, lost=False, attacker=OGRE):
    """Seat 1 attacks seat 0 with two Ogres (3/3), or two of `attacker`; seat 0's `blocker_card` blocks all it can."""
    game, _ = table3(blocks_all)
    a, b, _ = game.seats
    blocker = Permanent(blocker_card)
    a.battlefield = [blocker]
    if lost:
        b.battlefield.append(Permanent(COURSEWORK, attached_to=blocker))  # (enchanted creature loses all abilities)
    ogres = [Permanent(attacker, sick=False), Permanent(attacker, sick=False)]
    b.battlefield += ogres
    game.combat.attacks = [Attack(ogre, b, a, []) for ogre in ogres]
    game.combat.declare_blockers()
    return game, blocker, ogres


class ExtraBlockTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_it_blocks_both_and_divides_its_damage(self):
        game, twins, ogres = two_ogres_attack(TWINS)
        self.assertEqual([twins in a.blockers for a in game.combat.attacks], [True, True])
        game.combat.deal_damage(first_strike_step=False)
        game._check_state()
        self.assertEqual(([o in game.seats[1].battlefield for o in ogres], twins.damage), ([False, False], 6))

    def test_its_seven_damage_is_divided_not_dealt_to_each(self):
        game, twins, wurms = two_ogres_attack(TWINS, attacker=WURM)  # (two 6/4s)
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual(sorted(w.damage for w in wurms), [3, 4])

    def test_without_the_ability_it_blocks_one(self):
        for card, lost in ((GIANT, False), (TWINS, True)):
            game, blocker, _ = two_ogres_attack(card, lost)
            self.assertEqual([blocker in a.blockers for a in game.combat.attacks], [True, False], card.name)

    def test_whenever_it_blocks_is_heard_once(self):
        game, _ = table3(blocks_all)
        heard = []
        game.trigger = lambda event, *args, **kwargs: heard.append(event)
        a, b, _ = game.seats
        a.battlefield = [Permanent(TWINS)]
        ogres = [Permanent(OGRE, sick=False), Permanent(OGRE, sick=False)]
        b.battlefield = ogres
        game.combat.attacks = [Attack(ogre, b, a, []) for ogre in ogres]
        game.combat.declare_blockers()
        self.assertEqual(heard.count("blocks"), 1)


if __name__ == "__main__":
    unittest.main()
