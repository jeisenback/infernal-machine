"""Oko, Thief of Crowns, from its real Oracle text: "+1: Target artifact or creature loses all abilities and becomes a green Elk creature
with base power and toughness 3/3." (for good; it leaves as its real card) and "−5: Exchange control of target artifact or creature you
control and target creature an opponent controls with power 3 or less." (a creature with greater power is not offered)."""

import unittest

from infernal_machine.effects.outcomes import FOOD
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, SOL_RING, pick, real, run_stack, table3

OKO = real("Oko, Thief of Crowns", "{1}{G}{U}", "Legendary Planeswalker — Oko", "+2: Create a Food token. (It's an artifact with \"{2}, "
           "{T}, Sacrifice this token: You gain 3 life.\")\n+1: Target artifact or creature loses all abilities and becomes a green Elk "
           "creature with base power and toughness 3/3.\n−5: Exchange control of target artifact or creature you control and target "
           "creature an opponent controls with power 3 or less.", None, None, colors=("G", "U"))
ELVES = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))


def activate(text, policy, mine=(), theirs=()):
    """Seat 0 activates the Oko ability whose text contains `text`; `mine` and `theirs` are the permanents of seats 0 and 1."""
    game, _ = table3(policy)
    a, b, _ = game.seats
    a.battlefield = [Permanent(OKO, loyalty=5), *mine]
    b.battlefield = list(theirs)
    game.step, game.active = "main1", a.index
    (action,) = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Oko") and text in x]
    game._perform(a, action)
    run_stack(game)
    return game, a, b


class OkoTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(OKO), [])

    def test_plus_one_makes_a_creature_a_vanilla_green_elk_for_good(self):
        elves = Permanent(ELVES, sick=False)
        game, _, b = activate("+1:", pick("Llanowar Elves"), theirs=[elves])
        self.assertEqual((elves.card.name, elves.card.type_line, elves.card.colors, game.power(elves), game.toughness(elves),
                          elves.card.oracle_text), ("Llanowar Elves", "Creature — Elk", ("G",), 3, 3, ""))
        game.destroy(elves)
        self.assertEqual(b.graveyard, [ELVES])

    def test_an_artifact_becomes_an_elk_creature_too(self):
        ring = Permanent(SOL_RING)
        activate("+1:", pick("Sol Ring"), theirs=[ring])
        self.assertEqual((ring.card.type_line, ring.card.colors, ring.card.oracle_text), ("Creature — Elk", ("G",), ""))

    def test_minus_five_exchanges_your_artifact_for_their_small_creature(self):
        food, bear = Permanent(FOOD), Permanent(BEAR)
        seen = []
        def policy(prompt, options):
            seen.extend(options)
            return pick("Food", "Bear")(prompt, options)
        game, a, b = activate("−5:", policy, mine=[food], theirs=[bear, Permanent(BIG)])
        self.assertEqual(([p.card.name for p in a.battlefield], [p.card.name for p in b.battlefield]),
                         (["Oko, Thief of Crowns", "Bear"], ["Big", "Food"]))
        self.assertFalse(any(o.startswith("Big") for o in seen))  # power 5: not offered


if __name__ == "__main__":
    unittest.main()
