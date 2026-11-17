"""Issue #798: Scavenge {cost}, "({cost}, Exile this card from your graveyard: Put a number of +1/+1 counters equal to the power of the card
you exiled on target creature. Scavenge only as a sorcery.)" (CR 702.97a), from the cards' real Oracle text. All eleven cards whose only
gap it was are fully playable. On Sewer Shambler, a 2/1: from the graveyard, two counters on any target creature and the card exiled;
only at sorcery speed, with the mana, and with a creature to target. A card whose power is "*" (Dodgy Jalopy) is not read."""

import unittest

from infernal_machine.effects import activated_abilities
from infernal_machine.game import ACTIVATE_GRAVEYARD, Permanent
from tests.helpers import BEAR, OGRE, choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Deadbridge Goliath", "Dreg Mangler", "Drudge Beetle", "Golgari Decoy", "Korozda Monitor", "Sewer Shambler", "Slitherhead",
         "Sluiceway Scorpion", "Terrus Wurm", "Thrashing Mossdog", "Zanikev Locust"]
SHAMBLER = REAL["Sewer Shambler"]  # 2/1, Scavenge {2}{B}
ACTION = ACTIVATE_GRAVEYARD + "Sewer Shambler"

# The guards these tests are there to catch (python tools/mutate.py tests.test_scavenge).
MUTATIONS = [
    ("infernal_machine/effects/activated.py", 'if (m := _SCAVENGE.fullmatch(line)) and (card.power or "").isdigit():',
     "if (m := _SCAVENGE.fullmatch(line)):", "a \"*\" power is not read"),
    ("infernal_machine/effects/activated.py", 'PutCounters(int(card.power or 0), "+1/+1", "creature")', 'PutCounters(1, "+1/+1", "creature")',
     "as many counters as its power"),
    ("infernal_machine/effects/activated.py", "                                              sorcery_speed=True, exile_from_graveyard=True, from_graveyard=True))",
     "                                              exile_from_graveyard=True, from_graveyard=True))", "only as a sorcery"),
    ("infernal_machine/effects/activated.py", "                                              sorcery_speed=True, exile_from_graveyard=True, from_graveyard=True))",
     "                                              sorcery_speed=True, from_graveyard=True))", "the card is exiled"),
]


def setup(mana=3, creatures=True):
    """Seat 0 has Sewer Shambler in its graveyard, `mana` lands and a Bear; seat 1 an Ogre."""
    game, players = table3()
    a, b, _ = game.seats
    a.graveyard = [SHAMBLER]
    a.battlefield = lands(mana) + ([Permanent(BEAR)] if creatures else [])
    b.battlefield = [Permanent(OGRE)] if creatures else []
    return game, players, a, b


class ScavengeTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_counters_equal_to_its_power_on_any_target_creature_and_the_card_exiled(self):
        for seat in (0, 1):
            game, players, a, b = setup()
            target = (a if seat == 0 else b).battlefield[-1]
            players[0].policy = choose(game, target)
            game._perform(a, ACTION)
            run_stack(game)
            self.assertEqual((target.counters, a.graveyard, a.exile), ({"+1/+1": 2}, [], [SHAMBLER]), seat)

    def test_only_as_a_sorcery_with_the_mana_and_a_creature_to_target(self):
        game, _, a, _ = setup()
        self.assertIn(ACTION, game.legal_actions(a))
        game.step = "combat"
        self.assertNotIn(ACTION, game.legal_actions(a))
        game, _, a, _ = setup(mana=2)
        self.assertNotIn(ACTION, game.legal_actions(a))
        game, _, a, _ = setup(creatures=False)
        self.assertNotIn(ACTION, game.legal_actions(a))

    def test_a_star_power_is_not_read(self):
        self.assertEqual([a for a in activated_abilities(REAL["Dodgy Jalopy"]) if a.from_graveyard], [])


if __name__ == "__main__":
    unittest.main()
