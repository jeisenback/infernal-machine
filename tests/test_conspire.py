"""Issue #841: Conspire, "(As you cast this spell, you may tap two untapped creatures you control that share a color with it. When you
do, copy it and you may choose a new target for the copy.)" (CR 702.78a), from the cards' real Oracle text. All eight cards whose only
gap it was are fully playable. Burn Trail (red, 3 damage): its caster taps two red creatures and the copy deals 3 more; declined, 3;
with one red creature (and a green one) it isn't asked; the green one is never offered."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.report import unsupported_lines
from infernal_machine.game import CAST, CONSPIRE_NONE, CONSPIRE_PROMPT, Permanent
from tests.helpers import choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Barkshell Blessing", "Burn Trail", "Ghastly Discovery", "Giantbaiting", "Memory Sluice", "Rally the Galadhrim"]
NEED_A_TARGET = ["Aethertow", "Gleeful Sabotage"]  # (an attacking or blocking creature, an artifact or enchantment: the smoke table has none, so only read)
TRAIL = REAL["Burn Trail"]
GOBLIN = Card(name="Goblin Piker", mana_cost="{1}{R}", type_line="Creature — Goblin", power="2", toughness="1", colors=("R",))
ELF = Card(name="Llanowar Elves", mana_cost="{G}", type_line="Creature — Elf", power="1", toughness="1", colors=("G",))

# The guards these tests are there to catch (python tools/mutate.py tests.test_conspire).
MUTATIONS = [
    ("infernal_machine/casting.py", ' and set(p.card.colors) & set(card.colors)]', "]", "only creatures that share a color"),
    ("infernal_machine/casting.py", "        if len(options) < 2:\n            return False\n", "", "two of them"),
    ("infernal_machine/casting.py", "            if not tapped and not pick:\n                return False\n", "", "the caster may decline"),
    ("infernal_machine/casting.py", "        for p in tapped:\n            self.game.tap(p)\n", "", "they are tapped"),
    ("infernal_machine/casting.py", '        if not has_keyword(card, "conspire"):\n            return False\n', "", "only a spell with conspire"),
    ("infernal_machine/effects/costs.py", "_CASUALTY, _CONSPIRE, _SACRIFICE_DISCOUNT,", "_CASUALTY, _SACRIFICE_DISCOUNT,", "the line is read"),
]


def cast(creatures, conspire=True, spell=TRAIL):
    """Seat 0, with `creatures`, casts `spell` (Burn Trail) at seat 1 (conspiring if asked and `conspire`)."""
    game, players = table3()
    a, b, _ = game.seats
    mine = [Permanent(c) for c in creatures]
    a.hand, a.battlefield = [spell], lands(4) + mine
    aim = choose(game, b)
    players[0].policy = lambda prompt, options: ((int(conspire and CONSPIRE_NONE in options)) if CONSPIRE_PROMPT.matches(prompt)
                                                 else aim(prompt, options))
    game._perform(a, CAST + spell.name)
    run_stack(game)
    asked = [options for prompt, options in players[0].prompts if CONSPIRE_PROMPT.matches(prompt)]
    return b, mine, asked


class ConspireTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)
        for name in NEED_A_TARGET:
            self.assertEqual(unsupported_lines(REAL[name]), [], name)

    def test_two_creatures_that_share_its_color_are_tapped_for_a_copy(self):
        b, mine, asked = cast([GOBLIN, GOBLIN, ELF])
        self.assertEqual((40 - b.life, [p.tapped for p in mine]), (6, [True, True, False]))
        self.assertEqual([o.split(" ")[0] for o in asked[0]], ["Don't", "Goblin", "Goblin"])  # (the Elf is not offered)
        self.assertEqual(asked[0][0], CONSPIRE_NONE)

    def test_declined_no_copy(self):
        b, mine, _ = cast([GOBLIN, GOBLIN], conspire=False)
        self.assertEqual((40 - b.life, [p.tapped for p in mine]), (3, [False, False]))

    def test_a_spell_without_conspire_asks_nothing(self):
        b, mine, asked = cast([GOBLIN, GOBLIN], spell=REAL["Lightning Bolt"])
        self.assertEqual((40 - b.life, asked, [p.tapped for p in mine]), (3, [], [False, False]))

    def test_one_creature_of_its_color_is_not_enough(self):
        b, mine, asked = cast([GOBLIN, ELF])
        self.assertEqual((40 - b.life, asked, [p.tapped for p in mine]), (3, [], [False, False]))


if __name__ == "__main__":
    unittest.main()
