"""Issue #874: suspect (CR 701.60): a suspected creature has menace and "This creature can't block" until it leaves the battlefield, from
the cards' real Oracle text. Seven cards whose only gap it was are fully playable. Caught Red-Handed suspects the creature it takes;
Barbed Servitor and Person of Interest suspect themselves as they enter, Convenient Target the creature it enchants, Reasonable Doubt
its target, It Doesn't Add Up the creature it returns. A suspected creature has menace and can't block; one that isn't, or that left
the battlefield and came back, can block and has no menace."""

import unittest

from infernal_machine.effects import CANT_BLOCK
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Caught Red-Handed", "Barbed Servitor", "Person of Interest", "Convenient Target", "Incriminating Impetus", "It Doesn't Add Up"]
NEED_A_TARGET = ["Reasonable Doubt"]  # (it counters a spell too: the smoke table has none, so only read)

# The guards these tests are there to catch (python tools/mutate.py tests.test_suspect).
MUTATIONS = [
    ("infernal_machine/game.py", 'or (permanent.suspected and keyword in ("menace", CANT_BLOCK))', 'or (permanent.suspected and keyword in ("menace",))',
     "it can't block"),
    ("infernal_machine/game.py", 'or (permanent.suspected and keyword in ("menace", CANT_BLOCK))', 'or (permanent.suspected and keyword in (CANT_BLOCK,))',
     "it has menace"),
    ("infernal_machine/effects/outcomes.py", "        effects[0] = replace(effects[0], binds=SOURCE)  # \"When this creature enters, suspect it.\"",
     "        pass  # \"When this creature enters, suspect it.\"", "an enters trigger's \"it\" is the creature itself"),
    ("infernal_machine/game.py", "for p in reversed(s.battlefield) if p.card is creature.card", "for p in s.battlefield if p.card is creature.card",
     "the copy that was returned"),
    ("infernal_machine/game.py", "        if isinstance(creature, GraveyardTarget):\n            found = next(", "        if False:\n            found = next(",
     "a returned card is the permanent it became"),
]


def suspected(game, permanent):
    return permanent.suspected, game.has_keyword(permanent, "menace"), game.has_keyword(permanent, CANT_BLOCK)


def cast(name, mana, policy_targets=(), theirs=(), graveyard=()):
    """Seat 0, with `mana` lands, casts `name`; seat 1 has `theirs`; seat 0's graveyard is `graveyard`."""
    game, players = table3()
    a, b, _ = game.seats
    a.battlefield, a.hand, a.graveyard = lands(mana), [REAL[name]], list(graveyard)
    b.battlefield = [Permanent(c, sick=False) for c in theirs]
    players[0].policy = choose(game, *(b.battlefield + list(policy_targets)))
    game._perform(a, CAST + name)
    run_stack(game)
    return game, a, b


class SuspectTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)
        for name in NEED_A_TARGET:
            self.assertEqual(unsupported_lines(REAL[name]), [], name)

    def test_the_creature_it_takes_is_suspected(self):
        game, a, _ = cast("Caught Red-Handed", 5, theirs=[OGRE])
        (ogre,) = [p for p in a.battlefield if p.card is OGRE]
        self.assertEqual(suspected(game, ogre), (True, True, True))

    def test_it_suspects_itself_as_it_enters(self):
        game, a, _ = cast("Barbed Servitor", 4)
        (servitor,) = [p for p in a.battlefield if p.card.name == "Barbed Servitor"]
        self.assertEqual(suspected(game, servitor), (True, True, True))

    def test_the_aura_suspects_the_creature_it_enchants(self):
        game, players = table3()
        a = game.seats[0]
        bear = Permanent(BEAR, sick=False)
        a.battlefield, a.hand = lands(3) + [bear], [REAL["Convenient Target"]]
        players[0].policy = choose(game, bear)
        game._perform(a, CAST + "Convenient Target")
        run_stack(game)
        self.assertEqual(suspected(game, bear), (True, True, True))

    def test_the_creature_it_returns_is_suspected(self):
        game, a, _ = cast("It Doesn't Add Up", 5, graveyard=[OGRE])
        (ogre,) = [p for p in a.battlefield if p.card is OGRE]
        self.assertEqual(suspected(game, ogre), (True, True, True))

    def test_the_returned_copy_is_suspected_not_another_copy(self):
        game, players = table3()
        a = game.seats[0]
        older = Permanent(OGRE, sick=False)  # (another copy of the same card already on the battlefield)
        a.battlefield, a.hand, a.graveyard = lands(5) + [older], [REAL["It Doesn't Add Up"]], [OGRE]
        game._perform(a, CAST + "It Doesn't Add Up")
        run_stack(game)
        (returned,) = [p for p in a.battlefield if p.card is OGRE and p is not older]
        self.assertEqual((returned.suspected, older.suspected), (True, False))

    def test_not_a_creature_never_suspected_nor_one_that_came_back(self):
        game, a, _ = cast("Barbed Servitor", 4)
        (servitor,) = [p for p in a.battlefield if p.card.name == "Barbed Servitor"]
        bear = Permanent(BEAR, sick=False)
        a.battlefield.append(bear)
        self.assertEqual(suspected(game, bear), (False, False, False))
        game.return_to_hand(servitor)
        back = Permanent(servitor.card)
        game._enter(a, back)  # (a new object: it isn't suspected until its trigger resolves)
        self.assertEqual(back.suspected, False)


if __name__ == "__main__":
    unittest.main()
