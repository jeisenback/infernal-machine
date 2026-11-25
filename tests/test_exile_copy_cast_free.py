"""Exiling a card from a graveyard, copying it and casting the copy without paying its mana cost, from the cards' real Oracle text. All
four cards are fully playable. Shiko, Paragon of the Way enters and exiles a three-drop sorcery from its controller's graveyard (not a
four-drop: "mana value 3 or less") and casts a copy of it; with only a four-drop there, nothing happens. Flawless Forgery takes an
instant from an opponent's graveyard, not its caster's. Narset, Enlightened Exile (power 3) attacks and takes a two-drop, not a
three-drop ("mana value less than Narset's power")."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import fire, lands, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Shiko, Paragon of the Way", "Narset, Enlightened Exile", "Arcane Proxy"]
NEED_A_TARGET = ["Flawless Forgery"]  # (the smoke table has no instant in an opponent's graveyard: read, and played below)
STUDY = real("Study", "{2}{U}", "Sorcery", "Draw two cards.")  # (mana value 3)
DEEP = real("Deep Study", "{3}{U}", "Sorcery", "Draw two cards.")  # (mana value 4)
ZAP = real("Zap", "{1}{U}", "Instant", "Draw a card.")  # (mana value 2)

# The guards these tests are there to catch (python tools/mutate.py tests.test_exile_copy_cast_free).
MUTATIONS = [
    ("infernal_machine/effects/outcomes.py", '''else f"|mv<={''.join(ch for ch in mana_value if ch.isdigit())}")''', '''else "")''',
     "mana value 3 or less"),
    ("infernal_machine/effects/outcomes.py", '''{"your": "yours", "a": "any", "an opponent's": "opponents"}''',
     '''{"your": "yours", "a": "any", "an opponent's": "any"}''', "an opponent's graveyard"),
    ("infernal_machine/game.py", '''f"mv<={max(power, 0)}").replace("mv<power", f"mv<{max(power, 0)}")''', '''f"mv<={max(power, 0)}")''',
     "less than the power, as it is"),
]


def seat0(graveyard=(), theirs=()):
    game, _ = table3()
    a, b, _ = game.seats
    a.graveyard, b.graveyard, a.library = list(graveyard), list(theirs), [STUDY] * 10
    return game, a, b


class ExileCopyCastFreeTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)
        for name in NEED_A_TARGET:
            self.assertEqual(unsupported_lines(REAL[name]), [], name)

    def test_a_three_drop_is_copied_and_cast(self):
        game, a, _ = seat0(graveyard=[DEEP, STUDY])
        game._enter(a, Permanent(REAL["Shiko, Paragon of the Way"]))
        run_stack(game)
        self.assertEqual((len(a.hand), [c.name for c in a.exile], [c.name for c in a.graveyard]), (2, ["Study"], ["Deep Study"]))

    def test_with_only_a_four_drop_nothing_happens(self):
        game, a, _ = seat0(graveyard=[DEEP])
        game._enter(a, Permanent(REAL["Shiko, Paragon of the Way"]))
        run_stack(game)
        self.assertEqual((a.hand, a.exile, a.graveyard), ([], [], [DEEP]))

    def test_only_an_opponents_graveyard(self):
        game, a, b = seat0(graveyard=[ZAP], theirs=[ZAP])
        a.battlefield, a.hand = lands(5), [REAL["Flawless Forgery"]]
        game._perform(a, CAST + "Flawless Forgery")
        run_stack(game)
        self.assertEqual((a.graveyard[0], b.graveyard, [c.name for c in b.exile], len(a.hand)), (ZAP, [], ["Zap"], 1))

    def test_less_than_narsets_power(self):
        game, a, b = seat0(theirs=[STUDY, ZAP])
        narset = Permanent(REAL["Narset, Enlightened Exile"], sick=False)
        a.battlefield = [narset]
        fire(game, a, narset, "attacks")
        self.assertEqual(([c.name for c in b.graveyard], [c.name for c in b.exile], len(a.hand)), (["Study"], ["Zap"], 1))


if __name__ == "__main__":
    unittest.main()
