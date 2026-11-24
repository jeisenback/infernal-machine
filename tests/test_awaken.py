"""Issue #849: Awaken N—{cost}, "(If you cast this spell for {cost}, also put N +1/+1 counters on target land you control and it becomes a
0/0 Elemental creature with haste. It's still a land.)" (CR 702.113), from the cards' real Oracle text. All twelve cards whose only gap
it was are fully playable. Coastal Discovery ({3}{U}, "Draw two cards."; Awaken 4—{5}{U}) cast for its awaken cost draws two cards and
makes a land its caster controls a 4/4 Elemental creature land with haste, which stays one after the turn ends and is a land card again
in the graveyard; cast for {3}{U}, it only draws. Clutch of Currents for its awaken cost returns the creature it targets and awakens a
land: two targets."""

import unittest

from infernal_machine.game import CAST, COST_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, end_turn, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Part the Waterveil", "Boiling Earth", "Ruinous Path", "Clutch of Currents", "Earthen Arms", "Coastal Discovery", "Rush of Ice", "Roil Spout",
         "Rising Miasma", "Mire's Malice"]
NEED_A_TARGET = ["Scatter to the Winds", "Sheer Drop"]  # (a spell, a tapped creature: the smoke table has none, so only read)
DISCOVERY = REAL["Coastal Discovery"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_awaken).
MUTATIONS = [
    ("infernal_machine/casting.py", "            effects = list(effects or []) + [Awaken(alternative.awaken)]\n", "            pass\n",
     "the awaken cost awakens a land"),
    ("infernal_machine/effects/costs.py", "_WARP, _OVERLOAD, _AWAKEN, _SPELL_KEYWORDS,", "_WARP, _OVERLOAD, _SPELL_KEYWORDS,", "the line is read"),
    ("infernal_machine/game.py", "and not permanent.earthbent and not permanent.awakened and", "and not permanent.earthbent and",
     "it stays a creature"),
    ("infernal_machine/game.py", '.split() + ["Elemental"]), False, frozenset())', ".split()), False, frozenset())", "an Elemental"),
]


def cast(way):
    """Seat 0, with six lands and two Bears in its library, casts Coastal Discovery the way whose option starts with `way`."""
    game, _ = table3(lambda prompt, options: next(i for i, o in enumerate(options) if o.startswith(way)) if COST_PROMPT.matches(prompt) else 0)
    a = game.seats[0]
    a.hand, a.battlefield, a.library = [DISCOVERY], lands(6), [BEAR, BEAR]
    game._perform(a, CAST + DISCOVERY.name)
    run_stack(game)
    return game, a


def creatures(game, seat):
    return [p for p in seat.battlefield if game.toughness(p) is not None]


class AwakenTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)
        for name in NEED_A_TARGET:
            self.assertEqual(unsupported_lines(REAL[name]), [], name)

    def test_its_awaken_cost_also_makes_a_land_a_four_four_elemental_with_haste(self):
        game, a = cast("Awaken")
        (land,) = creatures(game, a)
        self.assertEqual(([c.name for c in a.hand], game.power(land), game.toughness(land), game.has_keyword(land, "haste")),
                         (["Bear", "Bear"], 4, 4, True))
        self.assertIn("Land", land.card.type_line)
        self.assertIn("Elemental", game.subtypes(land))
        end_turn(game, a)
        self.assertEqual(creatures(game, a), [land])  # (for good, not until end of turn)
        game.destroy(land)
        self.assertEqual([c.type_line for c in a.graveyard if c is not DISCOVERY], [lands(1)[0].card.type_line])  # (a land card again)

    def test_a_spell_with_its_own_target_also_targets_the_land(self):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Awaken")), 0)
                         if COST_PROMPT.matches(prompt) else next((i for i, o in enumerate(options) if "Bear" in o), 0))
        a, b, _ = game.seats
        clutch = REAL["Clutch of Currents"]  # ({U}: "Return target creature to its owner's hand."; Awaken 3—{4}{U})
        a.hand, a.battlefield, b.battlefield = [clutch], lands(5), [Permanent(BEAR)]
        game._perform(a, CAST + clutch.name)
        run_stack(game)
        (land,) = creatures(game, a)
        self.assertEqual((b.hand, b.battlefield, game.power(land), game.toughness(land)), ([BEAR], [], 3, 3))

    def test_its_mana_cost_only_draws(self):
        game, a = cast("Pay")
        self.assertEqual((len(a.hand), creatures(game, a)), (2, []))


if __name__ == "__main__":
    unittest.main()
