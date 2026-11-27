"""Monstrosity (CR 701.37), from the cards' real Oracle text. All 19 cards whose only gap it was are fully playable. Hydra Broodmaster
(7/7, "{X}{X}{G}: Monstrosity X." and "When this creature becomes monstrous, create X X/X green Hydra creature tokens.") with five
lands: X is 2, two +1/+1 counters and two 2/2 Hydras; activated again it is already monstrous, so nothing happens. Fleecemane Lion has
hexproof and indestructible only once it is monstrous; a +1/+1 counter from elsewhere doesn't make it monstrous."""

import unittest

from infernal_machine.game import X_PROMPT, Permanent
from tests.helpers import activate, lands, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Chillerpillar", "Domesticated Hydra", "Ember Swallower", "Fleecemane Lion", "Fleetfeather Cockatrice", "Gluttonous Cyclops",
         "Hydra Broodmaster", "Hythonia the Cruel", "Ill-Tempered Cyclops", "Kalemne's Captain", "Keepsake Gorgon", "Nessian Asp",
         "Polis Crusher", "Ravenous Leucrocota", "Sinuous Vermin", "Skittering Crustacean", "Splitting Slime", "Vitality Hunter",
         "Wildfire Cerberus"]
BROODMASTER, LION = REAL["Hydra Broodmaster"], REAL["Fleecemane Lion"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_monstrosity).
MUTATIONS = [
    ("infernal_machine/effects/families/counters.py", "if target is not None and game.on_battlefield(target) and not target.monstrous:",
     "if target is not None and game.on_battlefield(target):", "only if it isn't monstrous"),
    ("infernal_machine/game.py", "        permanent.monstrous = True\n", "", "it becomes monstrous"),
    ("infernal_machine/game.py", '            self.trigger("becomes_monstrous", permanent, holder, x=count)', "            pass",
     "\"When this creature becomes monstrous\""),
    ("infernal_machine/game.py", "            return source is not None and source.monstrous", "            return source is not None",
     "\"As long as this creature is monstrous\""),
]


def largest_x(prompt, options):
    return len(options) - 1 if X_PROMPT.matches(prompt) else 0


def seat_with(card, mana):
    game, _ = table3(largest_x)
    a = game.seats[0]
    permanent = Permanent(card, sick=False)
    a.battlefield = [permanent] + lands(mana)
    return game, a, permanent


def hydras(seat):
    return [p for p in seat.battlefield if p.card.name == "Hydra"]


class MonstrosityTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_monstrosity_x_and_its_trigger(self):
        game, a, it = seat_with(BROODMASTER, 5)
        activate(game, a, "Monstrosity")
        self.assertEqual((it.monstrous, it.counters.get("+1/+1"), [(game.power(h), game.toughness(h)) for h in hydras(a)]),
                         (True, 2, [(2, 2), (2, 2)]))
        for p in a.battlefield:
            p.tapped = False
        activate(game, a, "Monstrosity")
        self.assertEqual((it.counters.get("+1/+1"), len(hydras(a))), (2, 2))

    def test_as_long_as_it_is_monstrous(self):
        game, a, lion = seat_with(LION, 5)
        game.put_counters(lion, "+1/+1", 1)
        self.assertEqual((game.has_keyword(lion, "hexproof"), game.has_keyword(lion, "indestructible")), (False, False))
        activate(game, a, "Monstrosity")
        self.assertEqual((lion.monstrous, game.has_keyword(lion, "hexproof"), game.has_keyword(lion, "indestructible")), (True, True, True))


if __name__ == "__main__":
    unittest.main()
