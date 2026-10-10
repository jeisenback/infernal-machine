"""Brudiclad, Telchor Engineer with its current Oracle text (issue #80): the other tokens become copies for good, not until
end of turn. (tests/test_tokens_3.py covers the older wording.)"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import TokensBecomeCopies, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import OGRE
from tests.test_effects import pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

BRUDICLAD = Card(name="Brudiclad, Telchor Engineer", mana_cost="{4}{U}{R}", type_line="Legendary Artifact Creature — Phyrexian Artificer",
                 power="3", toughness="3",
                 oracle_text="Creature tokens you control have haste.\nAt the beginning of combat on your turn, create a 2/1 blue "
                             "Phyrexian Myr artifact creature token. Then you may choose a token you control. If you do, each other "
                             "token you control becomes a copy of that token.")
TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure", oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")
BEAR_TOKEN = Card(name="Bear", type_line="Token Creature — Bear", power="2", toughness="2")


class BrudicladTests(unittest.TestCase):
    def combat(self, policy):
        game, _ = table3(policy)
        a = game.seats[0]
        treasure, bear, ogre = Permanent(TREASURE), Permanent(BEAR_TOKEN, counters={"+1/+1": 1}), Permanent(OGRE)
        a.battlefield = [Permanent(BRUDICLAD), treasure, bear, ogre]
        game.step = "beginning_of_combat"
        game._turn_based_actions(a)
        run_stack(game)
        return game, a, treasure, bear, ogre

    def test_parse(self):
        self.assertEqual(unsupported_lines(BRUDICLAD), [])
        [trigger] = triggered_abilities(BRUDICLAD)
        self.assertEqual(trigger.effects[1], TokensBecomeCopies(False))

    def test_the_other_tokens_stay_copies_after_the_turn_ends(self):
        game, a, treasure, bear, ogre = self.combat(pick("Bear"))
        myr = next(p for p in a.battlefield if p not in (treasure, bear, ogre) and "Brudiclad" not in p.card.name)
        self.assertEqual([p.card.name for p in (treasure, myr, bear, ogre)], ["Bear", "Bear", "Bear", "Ogre"])
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual([p.card.name for p in (treasure, myr, bear, ogre)], ["Bear", "Bear", "Bear", "Ogre"])
        self.assertEqual(bear.counters, {"+1/+1": 1})

    def test_choosing_nothing_leaves_them_alone(self):
        game, a, treasure, bear, ogre = self.combat(pick("Don't copy"))
        self.assertEqual(sorted(p.card.name for p in a.battlefield),
                         ["Bear", "Brudiclad, Telchor Engineer", "Ogre", "Phyrexian Myr", "Treasure"])
