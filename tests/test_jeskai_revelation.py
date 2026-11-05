""""Return target spell or permanent to its owner's hand. Jeskai Revelation deals 4 damage to any target. Create two 1/1 white Monk
creature tokens with prowess. Draw two cards. You gain 4 life." (Jeskai Revelation)."""

import unittest

from infernal_machine.effects import spell_effects
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, lands, real, run_stack, table3

REVELATION = real("Jeskai Revelation", "{4}{U}{R}{W}", "Instant", "Return target spell or permanent to its owner's hand. Jeskai Revelation "
                  "deals 4 damage to any target. Create two 1/1 white Monk creature tokens with prowess. Draw two cards. You gain 4 life.")
DIVINATION = real("Divination", "{2}{U}", "Sorcery", "Draw two cards.")


def cast(answers, spell_on_stack=False):
    queue = list(answers)

    def policy(prompt, options):
        for want in queue:
            if want in options or any(o.startswith(want) for o in options):
                queue.remove(want)
                return next(i for i, o in enumerate(options) if o.startswith(want))
        return 0
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    a.hand, a.battlefield, a.library = [REVELATION], lands(7), [OGRE, OGRE, OGRE]
    b.battlefield, b.hand = [Permanent(BEAR)], []
    if spell_on_stack:
        game.stack.append(StackItem(DIVINATION, b, spell_effects(DIVINATION), []))
    game._perform(a, CAST + REVELATION.name)
    run_stack(game)
    return game, a, b


class JeskaiRevelationTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(REVELATION), [])

    def test_damage_to_the_creature_it_just_returned_is_not_dealt(self):
        game, a, b = cast(["Bear", "Bear"])  # the same creature for both targets: it is in its owner's hand by the damage
        self.assertEqual((b.hand, b.life, len(a.hand)), ([BEAR], 40, 2))

    def test_it_bounces_a_permanent_and_does_the_rest(self):
        game, a, b = cast(["Bear", "Player: B"])
        self.assertEqual(b.hand, [BEAR])
        self.assertEqual(b.life, 36)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Monk" in p.card.name), ["Monk", "Monk"])
        self.assertEqual((len(a.hand), a.life), (2, 44))

    def test_it_can_return_a_spell(self):
        game, a, b = cast(["Spell: Divination", "Player: B"], spell_on_stack=True)
        self.assertEqual(b.hand, [DIVINATION])
        self.assertNotIn(DIVINATION, b.graveyard)


if __name__ == "__main__":
    unittest.main()
