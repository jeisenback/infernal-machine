"""Hullbreaker Horror, from its Oracle text: whenever you cast a spell, bounce a spell you don't control or a nonland permanent."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, OGRE, real, run_stack, script, table3

HORROR = real("Hullbreaker Horror", "{5}{U}{U}", "Creature — Kraken Horror",
              "Flash\nThis spell can't be countered.\nFlying, trample\nWhenever you cast a spell, choose up to one —\n"
              "• Return target spell you don't control to its owner's hand.\n• Return target nonland permanent to its owner's hand.", "7", "8")
CANTRIP = real("Cantrip", "{U}", "Sorcery", "Draw a card.")
THEIRS = real("Their Spell", "{1}", "Instant", "Draw a card.")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


class HorrorTests(unittest.TestCase):
    def table(self, *answers):
        game, _ = table3(script(*answers), script(*answers[:0]))
        a, b, _ = game.seats
        a.battlefield = [Permanent(HORROR, sick=False)] + lands(2)
        a.hand, a.library = [CANTRIP], [FOREST] * 5
        b.battlefield = [Permanent(BEAR), Permanent(FOREST)]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(HORROR), [])

    def test_bounce_a_nonland_permanent_when_you_cast_a_spell(self):
        game, a, b = self.table("Return target nonland", "Bear")
        game._perform(a, CAST + "Cantrip")
        run_stack(game)
        self.assertEqual(([p.card.name for p in b.battlefield], [c.name for c in b.hand]), (["Forest"], ["Bear"]))

    def test_bounce_an_opponents_spell_on_the_stack(self):
        game, _ = table3(script("Return target spell", "Their Spell"), script())
        a, b, _ = game.seats
        a.battlefield = [Permanent(HORROR, sick=False)] + lands(2)
        a.hand, a.library = [CANTRIP], [FOREST] * 5
        b.hand, b.battlefield = [THEIRS], lands(1)
        # their spell is already on the stack when the Horror's controller casts one
        game._perform(b, CAST + "Their Spell")
        game._perform(a, CAST + "Cantrip")
        run_stack(game)
        self.assertEqual(([c.name for c in b.hand], b.graveyard), (["Their Spell"], []))
        self.assertEqual(len(a.hand), 1)  # the Cantrip still resolved

    def test_it_cannot_bounce_your_own_spell(self):
        seen = []

        def policy(prompt, options):
            seen.append(list(options))
            return len(options) - 1  # the last choice: done choosing modes
        game, _ = table3(policy, script())
        a, b, _ = game.seats
        a.battlefield = [Permanent(HORROR, sick=False)] + lands(2)
        a.hand, a.library = [CANTRIP], [FOREST] * 5
        game._perform(a, CAST + "Cantrip")
        game._put_triggers_on_stack()
        modes = [o for options in seen for o in options if o.startswith("Return target")]
        self.assertEqual(modes, ["Return target nonland permanent to its owner's hand."])  # the spell mode has nothing to aim at

    def test_up_to_one_means_it_may_be_declined(self):
        game, a, b = self.table("Done")
        game._perform(a, CAST + "Cantrip")
        run_stack(game)
        self.assertEqual([p.card.name for p in b.battlefield], ["Bear", "Forest"])

    def test_a_land_is_never_offered_as_a_target(self):
        offered = []

        def policy(prompt, options):
            offered.append(list(options))
            return 0
        game, _ = table3(policy, script())
        a, b, _ = game.seats
        a.battlefield = [Permanent(HORROR, sick=False)] + lands(2)
        a.hand, a.library = [CANTRIP], [FOREST] * 5
        b.battlefield = [Permanent(BEAR), Permanent(FOREST)]
        game._perform(a, CAST + "Cantrip")
        run_stack(game)
        targets = [o for options in offered for o in options if "(seat" in o]
        self.assertTrue(targets)
        self.assertFalse(any(o.startswith("Forest") or o.startswith("City of Brass") for o in targets))


if __name__ == "__main__":
    unittest.main()
