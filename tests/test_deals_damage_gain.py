"""Issue #847: "Whenever this creature deals damage, you gain that much life." (a trigger on the creature itself, like Spirit Link's on
the creature it enchants), from the cards' real Oracle text. All eight cards whose only gap it was are fully playable, and three with the
same trigger and another effect (Angel of Deliverance, Kiyomaro, Putrid Warrior). Exalted Angel (4/5): its combat damage to a player,
and to a blocking Ogre, gains its controller 4; a creature without it gains nothing, and neither does the Angel once it has lost its
abilities."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from tests.helpers import COURSEWORK, OGRE, combat_damage, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Doubtless One", "El-Hajjâj", "Exalted Angel", "Horned Cheetah", "Kjeldoran Gargoyle", "Mourning Thrull", "Warrior Angel",
         "Zebra Unicorn",
         "Angel of Deliverance", "Kiyomaro, First to Stand", "Putrid Warrior"]  # (the same trigger with another effect)
ANGEL = REAL["Exalted Angel"]
BEAST = Card(name="Plain Beast", mana_cost="{4}", type_line="Creature — Beast", power="4", toughness="5")

# The guards these tests are there to catch (python tools/mutate.py tests.test_deals_damage_gain).
MUTATIONS = [
    ("infernal_machine/game.py", '                self.trigger("deals_damage", source, dealer, x=amount)\n', "", "it triggers on its damage"),
    ("infernal_machine/effects/events.py", 'declare("deals_damage", re.compile(rf"Whenever {_SELF} deals damage, (.+)", re.I))',
     'declare("deals_damage", re.compile(rf"Whenever {_SELF} deals damage to a player, (.+)", re.I))', "any damage, not only to a player"),
]


def hit(card, blocked=False, lost=False):
    """Seat 0's `card` attacks seat 1 (blocked by an Ogre if `blocked`); seat 0's life after."""
    game, _ = table3()
    a, b, _ = game.seats
    attacker = Permanent(card, sick=False)
    a.battlefield = [attacker]
    ogre = Permanent(OGRE)
    b.battlefield = [ogre]
    if lost:
        b.battlefield.append(Permanent(COURSEWORK, attached_to=attacker))
    combat_damage(game, attacker, b, [ogre] if blocked else [])
    run_stack(game)
    return a.life - 40


class DealsDamageGainTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_its_damage_to_a_player_or_a_creature_gains_that_much(self):
        self.assertEqual((hit(ANGEL), hit(ANGEL, blocked=True)), (4, 4))

    def test_nothing_without_it_or_once_it_has_lost_it(self):
        self.assertEqual((hit(BEAST), hit(ANGEL, lost=True)), (0, 0))


if __name__ == "__main__":
    unittest.main()
