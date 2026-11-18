"""Issue #807: Afterlife N, "(When this creature dies, create N 1/1 white and black Spirit creature tokens with flying.)" (CR 702.135a),
from the cards' real Oracle text. All seven cards whose only gap it was are fully playable. Imperious Oligarch (Afterlife 1) dies for one
Spirit, Seraph of the Scales (Afterlife 2) for two, each a 1/1 white and black flier; exiled, not dying, it makes none."""

import unittest

from tests.helpers import enter, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Debtors' Transport", "Imperious Oligarch", "Ministrant of Obligation", "Orzhov Enforcer", "Orzhov Racketeers",
         "Seraph of the Scales", "Syndicate Messenger"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_afterlife).
MUTATIONS = [
    ("infernal_machine/effects/triggers.py", '            abilities.append(TriggeredAbility("dies", tuple(tokens or ()), False, line))',
     '            abilities.append(TriggeredAbility("leaves", tuple(tokens or ()), False, line))', "only when it dies"),
    ("infernal_machine/effects/triggers.py", "_AFTERLIFE_COUNT = {1: \"a\", 2: \"two\", 3: \"three\"}",
     "_AFTERLIFE_COUNT = {1: \"a\", 2: \"a\", 3: \"a\"}", "N tokens"),
]


def spirits(seat):
    return [p for p in seat.battlefield if p.card.name == "Spirit"]


def dies(name, exiled=False):
    game, _ = table3()
    a = game.seats[0]
    creature = enter(game, a, REAL[name])
    game.exile(creature) if exiled else game.destroy(creature)
    run_stack(game)
    return game, a


class AfterlifeTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_n_white_and_black_spirits_with_flying_when_it_dies(self):
        for name, n in (("Imperious Oligarch", 1), ("Seraph of the Scales", 2)):
            game, a = dies(name)
            made = spirits(a)
            self.assertEqual(len(made), n, name)
            self.assertTrue(all(set(p.card.colors) == {"W", "B"} and (p.card.power, p.card.toughness) == ("1", "1")
                                and game.has_keyword(p, "flying") for p in made), name)

    def test_none_when_it_is_exiled(self):
        _, a = dies("Seraph of the Scales", exiled=True)
        self.assertEqual(spirits(a), [])


if __name__ == "__main__":
    unittest.main()
