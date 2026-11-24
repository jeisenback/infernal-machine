"""Issue #853: Sneak {cost}, "(You may cast this spell for {cost} if you also return an unblocked attacker you control to hand during the
declare blockers step.)" (CR 702.190), from the cards' real Oracle text. All seven cards whose only gap it was are fully playable, and six more.
Oroku Saki, Shredder Rising ({2}{B}, Sneak {1}{B}): during its controller's declare blockers step, with two lands, an unblocked Bear is
returned to hand and Oroku Saki enters tapped and attacking the player the Bear attacked; Splinter's Technique, a sorcery, may be cast
then too; its targets are chosen before the attacker goes back (Karai's Technique may target it). It isn't offered before blockers are declared, when the attacker was blocked, or on another player's turn."""

import unittest

from infernal_machine.game import SNEAK, Permanent
from tests.helpers import BEAR, OGRE, attack_all, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Splinter's Technique", "Donatello, Gadget Master", "New Generation's Technique", "Raphael's Technique",
         "Oroku Saki, Shredder Rising", "Karai's Technique", "Foot Ninjas",
         "Donatello's Technique", "Elektra, Daughter of the Hand", "Jennika's Technique", "Leonardo, Cutting Edge", "Raphael, the Nightwatcher",
         "Splinter, Hamato Yoshi"]  # (and six more with sneak)
SAKI, TECHNIQUE = REAL["Oroku Saki, Shredder Rising"], REAL["Splinter's Technique"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_sneak).
MUTATIONS = [
    ("infernal_machine/game.py", 'if self.step != "declare_blockers" or self.active != seat.index or not self._unblocked_attackers(seat):',
     'if self.active != seat.index or not self._unblocked_attackers(seat):', "only in the declare blockers step"),
    ("infernal_machine/game.py", 'if self.step != "declare_blockers" or self.active != seat.index or not self._unblocked_attackers(seat):',
     'if self.step != "declare_blockers" or not self._unblocked_attackers(seat):', "only its controller's"),
    ("infernal_machine/casting.py", "            self.game.return_to_hand(attack.attacker)\n            self.sneaked", "            self.sneaked",
     "the attacker is returned"),
    ("infernal_machine/casting.py", "prototyped=bool(alternative and alternative.prototype), sneaked=self.sneaked)",
     "prototyped=bool(alternative and alternative.prototype))", "the spell knows whom it attacks"),
    ("infernal_machine/game.py", "            if item.sneaked is not None and self.on_battlefield(entering):  # CR 702.190b",
     "            if False:  # CR 702.190b", "it enters attacking"),
    ("infernal_machine/effects/costs.py", "_NINJUTSU, _SNEAK,", "_NINJUTSU,", "the line is read"),
]


def combat(hand, blockers=(), step="declare_blockers"):
    """Seat 0 has two lands and attacks with a Bear; seat 1 has `blockers`; the step is `step`."""
    game, _ = table3(attack_all)
    a, b, _ = game.seats
    bear = Permanent(BEAR, sick=False)
    a.hand, a.battlefield, a.library = list(hand), lands(2) + [bear], [BEAR]
    b.battlefield = [Permanent(c, sick=False) for c in blockers]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    game.step = step
    return game, a, b, bear


def offered(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(SNEAK)]


class SneakTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_the_bear_goes_back_and_it_enters_tapped_and_attacking(self):
        game, a, b, bear = combat([SAKI])
        self.assertEqual(offered(game, a), [SNEAK + SAKI.name])  # (two lands: {1}{B}, not {2}{B})
        game._perform(a, SNEAK + SAKI.name)
        run_stack(game)
        (saki,) = [p for p in a.battlefield if p.card is SAKI]
        self.assertEqual((BEAR in a.hand, bear in a.battlefield, saki.tapped), (True, False, True))
        self.assertEqual([(x.attacker, x.defender) for x in game.combat.attacks], [(saki, b)])

    def test_a_sorcery_may_be_cast_then(self):
        game, a, _, _ = combat([TECHNIQUE])
        game._perform(a, SNEAK + TECHNIQUE.name)
        run_stack(game)
        self.assertEqual((sorted(c.name for c in a.hand), TECHNIQUE in a.graveyard), (["Bear", "Bear"], True))  # (the Bear returned, and one found)

    def test_its_targets_are_chosen_before_the_attacker_goes_back(self):
        game, a, _, bear = combat([REAL["Karai's Technique"]])  # (the Bear, its only creature, is a legal target: CR 601.2c before 601.2h)
        game._perform(a, SNEAK + "Karai's Technique")
        (item,) = game.stack
        self.assertEqual((bear in item.targets, BEAR in a.hand), (True, True))

    def test_not_before_blockers_nor_when_blocked_nor_on_another_turn(self):
        self.assertEqual(offered(*combat([SAKI], step="declare_attackers")[:2]), [])
        game, a, b, _ = combat([SAKI], blockers=[OGRE])
        game.combat.attacks[0].blockers = [b.battlefield[0]]
        self.assertEqual(offered(game, a), [])
        game, a, _, _ = combat([SAKI])
        game.active = 1
        self.assertEqual(offered(game, a), [])


if __name__ == "__main__":
    unittest.main()
