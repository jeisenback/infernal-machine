"""Issue #834: "This spell costs {N} less to cast if it targets a tapped creature." (CR 601.2f: the cost is locked in after the targets
are chosen), from the cards' real Oracle text. All ten cards whose only gap it was are fully playable. Casting Luminous Rebuke ({4}{W},
{3} less): at a tapped creature it costs {1}{W}, at an untapped one all five; with only two lands it is offered only while a tapped
creature is there to target, and then only a tapped one can be chosen."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, OGRE, choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Luminous Rebuke", "Fate of the Sun-Cryst", "Seized from Slumber", "Ajani's Response", "Grounded for Life", "Banish from Edoras",
         "Magnificent End", "Quicksand Whirlpool", "Fantastic Bounce", "Hawkeye's Shot"]
REBUKE = REAL["Luminous Rebuke"]
ACTION = CAST + "Luminous Rebuke"

# The guards these tests are there to catch (python tools/mutate.py tests.test_tapped_target_discount).
MUTATIONS = [
    ("infernal_machine/casting.py", "            tapped_discount = 0  # CR 601.2f", "            pass  # CR 601.2f", "only at a tapped creature"),
    ("infernal_machine/casting.py", " + self._tapped_target_discount(seat, card)\n", "\n", "offered with the discount"),
    ("infernal_machine/casting.py", "        return amount if any(o is t for e", "        return amount if True or any(o is t for e",
     "offered with the discount only if a tapped creature is there"),
    ("infernal_machine/casting.py", '            choosing = [dataclasses.replace(e, target="tapped creature")', "            choosing = [e if True else dataclasses.replace(e, target=\"tapped creature\")",
     "only a tapped creature when only the discount pays"),
]


def setup(mana, tapped=True, untapped=True):
    """Seat 0 has Luminous Rebuke and `mana` lands; seat 1 an untapped Bear (offered first) and a tapped Ogre."""
    game, players = table3()
    a, b, _ = game.seats
    a.hand, a.battlefield = [REBUKE], lands(mana)
    b.battlefield = ([Permanent(BEAR)] if untapped else []) + ([Permanent(OGRE, tapped=True)] if tapped else [])
    return game, players, a, b


def untapped_lands(seat):
    return sum(not p.tapped for p in seat.battlefield if "Land" in p.card.type_line)


class TappedTargetDiscountTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_it_costs_less_only_at_a_tapped_creature(self):
        for target_name, left in (("Ogre", 3), ("Bear", 0)):
            game, players, a, b = setup(5)
            target = next(p for p in b.battlefield if p.card.name == target_name)
            players[0].policy = choose(game, target)
            game._perform(a, ACTION)
            run_stack(game)
            self.assertEqual((untapped_lands(a), [p.card.name for p in b.battlefield if p is target]), (left, []), target_name)

    def test_with_only_the_discounted_mana_it_needs_a_tapped_creature_and_targets_one(self):
        game, players, a, b = setup(2, tapped=False)
        self.assertNotIn(ACTION, game.legal_actions(a))
        game, players, a, b = setup(2)
        self.assertIn(ACTION, game.legal_actions(a))
        game._perform(a, ACTION)  # (the policy picks the first option offered: the Bear, were it offered)
        run_stack(game)
        self.assertEqual(([p.card.name for p in b.battlefield], untapped_lands(a)), (["Bear"], 0))


if __name__ == "__main__":
    unittest.main()
