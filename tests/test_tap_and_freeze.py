"""Issue #806: "Tap up to two target creatures. Those creatures don't untap during their controller's next untap step." from the cards'
real Oracle text, beside Tamiyo, Field Researcher's "nonland permanents ... They don't untap" (one template). All the cards whose only gap
it was are fully playable, Adverse Conditions too, and Saiba Trespassers' channel with "creatures you don't control". Frost Breath taps two
creatures, which stay tapped through their controller's next untap step and untap at the one after (CR 502.3); a third is left alone."""

import unittest

from infernal_machine.effects import activated_abilities, hand_abilities
from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, OGRE, choose, lands, run_stack, table3, untap_step, wording_unlocked
from tests.real import REAL

CARDS = ["Frost Breath", "Frostveil Ambush", "Snow Day", "Chilling Grasp", "Will of the Naga", "Decision Paralysis", "Adverse Conditions",
         "Saiba Trespassers"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_tap_and_freeze).
MUTATIONS = [
    ("infernal_machine/effects/outcomes.py", "     [Tap(m[1] + (m[2] or \"\"), optional_target=True, skip_untap=True),",
     "     [Tap(m[1], optional_target=True, skip_untap=True),", "\"you don't control\" is kept"),
    ("infernal_machine/effects/outcomes.py",
     "      Tap(m[1] + (m[2] or \"\"), distinct=True, optional_target=True, skip_untap=True)]),",
     "      Tap(m[1] + (m[2] or \"\"), distinct=True, optional_target=True)]),", "the second one doesn't untap either"),
]


class TapAndFreezeTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_two_creatures_tapped_skip_their_controllers_next_untap_step_only(self):
        game, players = table3()
        a, b, _ = game.seats
        first, second, third = Permanent(BEAR), Permanent(OGRE), Permanent(BEAR)
        a.hand, a.battlefield, b.battlefield = [REAL["Frost Breath"]], lands(3), [first, second, third]
        players[0].policy = choose(game, first, second)
        game._perform(a, CAST + "Frost Breath")
        run_stack(game)
        self.assertEqual([p.tapped for p in (first, second, third)], [True, True, False])
        untap_step(game, b)
        self.assertEqual([p.tapped for p in (first, second)], [True, True])
        untap_step(game, b)
        self.assertEqual([p.tapped for p in (first, second)], [False, False])

    def test_saiba_trespassers_targets_only_creatures_you_dont_control(self):
        card = REAL["Saiba Trespassers"]
        targets = {e.target for a in (*activated_abilities(card), *hand_abilities(card)) for e in getattr(a, "effects", ())
                   if getattr(e, "skip_untap", False)}
        self.assertEqual(targets, {"creature you don't control"})


if __name__ == "__main__":
    unittest.main()
