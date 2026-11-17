"""Issue #804: Casualty N, "(As you cast this spell, you may sacrifice a creature with power N or greater. When you do, copy this
spell.)" (CR 702.153a), from the cards' real Oracle text. All nine cards whose only gap it was are fully playable. A Little Chat (Casualty
1) with a Bear sacrificed resolves twice, its copy too; declined, once, and the Bear stays; Illicit Shipment (Casualty 3) offers no
creature with less power than 3."""

import unittest

from infernal_machine.game import CAST, CASUALTY_NONE, CASUALTY_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["A Little Chat", "Cut of the Profits", "Cut Your Losses", "Illicit Shipment", "Join the Maestros", "Light 'Em Up", "Rob the Archives",
         "Rooftop Nuisance"]
NEEDS_A_SPELL = "Make Disappear"  # (it counters a spell: the smoke table has none on the stack, so it is only read)

# The guards these tests are there to catch (python tools/mutate.py tests.test_casualty).
MUTATIONS = [
    ("infernal_machine/casting.py", 'if "Creature" in p.card.type_line and self.game.power(p) >= n]', 'if "Creature" in p.card.type_line]',
     "power N or greater"),
    ("infernal_machine/casting.py", "        if not pick:\n            return 0\n        self.game._leave_together",
     "        if False:\n            return 0\n        self.game._leave_together", "only when a creature is sacrificed"),
    ("infernal_machine/casting.py", "self.game._sacrifice_for_copies(seat, card) + self._casualty(seat, card)",
     "self.game._sacrifice_for_copies(seat, card) + 0 * self._casualty(seat, card)", "the copy"),
]


def sacrifice(answer):
    """Answer casualty with the first creature offered (`answer` True) or with none."""
    return lambda prompt, options: (1 if answer else options.index(CASUALTY_NONE)) if CASUALTY_PROMPT.matches(prompt) else 0


def cast(name, answer, creature=BEAR):
    game, players = table3(sacrifice(answer))
    a = game.seats[0]
    a.hand, a.battlefield, a.library = [REAL[name]], lands(6) + [Permanent(creature)], [OGRE] * 6
    game._perform(a, CAST + name)
    run_stack(game)
    game._check_state()
    return game, players[0], a


class CasualtyTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)
        self.assertEqual(unsupported_lines(REAL[NEEDS_A_SPELL]), [])

    def test_a_creature_sacrificed_copies_the_spell(self):
        _, _, a = cast("A Little Chat", True)
        self.assertEqual((len(a.hand), [c.name for c in a.graveyard]), (2, ["Bear", "A Little Chat"]))

    def test_declined_it_resolves_once_and_the_creature_stays(self):
        _, _, a = cast("A Little Chat", False)
        self.assertEqual((len(a.hand), "Bear" in [p.card.name for p in a.battlefield]), (1, True))

    def test_a_creature_with_less_power_is_not_offered(self):
        _, player, a = cast("Illicit Shipment", True)
        self.assertEqual(([p for p, _ in player.prompts if CASUALTY_PROMPT.matches(p)], len(a.hand)), ([], 1))
        _, player, a = cast("Illicit Shipment", True, OGRE)
        self.assertEqual((len(a.hand), "Ogre" in [c.name for c in a.graveyard]), (2, True))


if __name__ == "__main__":
    unittest.main()
