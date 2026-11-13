"""Cipher (CR 702.99), from the cards' real Oracle text: Last Thoughts is exiled encoded on a creature its caster controls as it resolves,
and each time that creature deals combat damage to a player its controller may cast a copy of it without paying its mana cost. With no
creature, or when the caster declines, it goes to the graveyard as usual."""

import unittest

from infernal_machine.effects.families.copying import CAST_COPY_PROMPT
from infernal_machine.game import CAST, DECLINE, ENCODE_PROMPT, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, fire, lands, real, run_stack, table3

REMINDER = ("Cipher (Then you may exile this spell card encoded on a creature you control. Whenever that creature deals combat damage to a "
            "player, its controller may cast a copy of the encoded card without paying its mana cost.)")
LAST_THOUGHTS = real("Last Thoughts", "{3}{U}", "Sorcery", "Draw a card.\n" + REMINDER, colors=("U",))
ARCANE_HEIST = real("Arcane Heist", "{2}{U}{U}", "Sorcery", "You may cast target instant or sorcery card from an opponent's graveyard "
                    "without paying its mana cost. If that spell would be put into their graveyard, exile it instead.\n" + REMINDER,
                    colors=("U",))
STOLEN_IDENTITY = real("Stolen Identity", "{4}{U}{U}", "Sorcery", "Create a token that's a copy of target artifact or creature.\n" + REMINDER,
                       colors=("U",))


def answering(encode=True, copy=True):
    def policy(prompt, options):
        if ENCODE_PROMPT.matches(prompt):
            return 0 if encode else options.index(DECLINE)
        if CAST_COPY_PROMPT.matches(prompt):
            return 0 if copy else 1
        return 0
    return policy


def cast_thoughts(policy, creatures=1):
    game, _ = table3(policy)
    a = game.seats[0]
    bears = [Permanent(BEAR) for _ in range(creatures)]
    a.battlefield, a.hand, a.library = [*lands(4), *bears], [LAST_THOUGHTS], [FOREST] * 10
    game._perform(a, CAST + LAST_THOUGHTS.name)
    run_stack(game)
    return game, a, bears


class CipherTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (LAST_THOUGHTS, ARCANE_HEIST, STOLEN_IDENTITY):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_it_is_encoded_and_each_combat_hit_casts_a_copy(self):
        game, a, [bear] = cast_thoughts(answering())
        self.assertEqual((len(a.hand), a.graveyard, a.exile, bear.encoded), (1, [], [LAST_THOUGHTS], [LAST_THOUGHTS]))
        for hits in (1, 2):
            fire(game, a, bear, "combat_damage_to_player")
            self.assertEqual((len(a.hand), a.exile, a.graveyard), (1 + hits, [LAST_THOUGHTS], []), hits)  # the copy ceases to exist

    def test_the_copy_may_be_declined(self):
        game, a, [bear] = cast_thoughts(answering(copy=False))
        fire(game, a, bear, "combat_damage_to_player")
        self.assertEqual(len(a.hand), 1)

    def test_with_no_creature_or_declined_it_goes_to_the_graveyard(self):
        for encode, creatures in ((True, 0), (False, 1)):
            asked = []

            def policy(prompt, options):
                asked.append(ENCODE_PROMPT.matches(prompt))
                return answering(encode)(prompt, options)
            game, a, bears = cast_thoughts(policy, creatures)
            self.assertEqual((len(a.hand), a.graveyard, a.exile, [b.encoded for b in bears], any(asked)),
                             (1, [LAST_THOUGHTS], [], [[]] * creatures, creatures > 0))  # with no creature there is nothing to ask

    def test_a_spell_whose_target_is_gone_is_not_encoded(self):
        def theirs_targeted(prompt, options):
            if TARGET_PROMPT.matches(prompt):
                return next(i for i, o in enumerate(options) if "seat 1" in o)
            return answering()(prompt, options)
        game, _ = table3(theirs_targeted)
        a, b = game.seats[0], game.seats[1]
        mine, theirs = Permanent(BEAR), Permanent(BEAR)
        a.battlefield, a.hand, b.battlefield = [*lands(6), mine], [STOLEN_IDENTITY], [theirs]
        game._perform(a, CAST + STOLEN_IDENTITY.name)
        game.destroy(theirs)
        run_stack(game)  # CR 608.2b: with its only target gone it doesn't resolve, so it isn't encoded
        self.assertEqual((a.graveyard, a.exile, mine.encoded), ([STOLEN_IDENTITY], [], []))

if __name__ == "__main__":
    unittest.main()
